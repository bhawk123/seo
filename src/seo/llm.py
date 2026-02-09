"""LLM client for SEO analysis."""

from typing import Optional
from datetime import datetime
from pathlib import Path
import hashlib
import os
import time
import logging
import toon

logger = logging.getLogger(__name__)

from seo.models import (
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)

# Import AICache for response caching (ported from Spectrum)
try:
    from seo.intelligence import AICache
    AICACHE_AVAILABLE = True
except ImportError:
    AICACHE_AVAILABLE = False
    AICache = None


class LLMClient:
    """Client for interacting with LLM for SEO analysis.

    Supports optional response caching via AICache to reduce API costs.
    """

    # Source label for evidence provenance
    SOURCE_LABEL = "LLM Inference"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        provider: str = "openai",
        max_tokens: int = 8192,
        cache_enabled: bool = True,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 24,
    ):
        """Initialize the LLM client.

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, etc.)
            max_tokens: Maximum tokens for LLM response (default: 8192)
            cache_enabled: Whether to cache LLM responses (default: True)
            cache_dir: Directory for cache storage (default: ~/.seo/cache)
            cache_ttl_hours: Cache TTL in hours (default: 24)
        """
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model
        self.provider = provider
        self.max_tokens = max_tokens

        if not self.api_key:
            raise ValueError(
                "API key must be provided or set in LLM_API_KEY environment variable"
            )

        # Initialize cache if available and enabled
        self._cache: Optional[AICache] = None
        self._cache_hits = 0
        self._cache_misses = 0

        if cache_enabled and AICACHE_AVAILABLE:
            cache_path = cache_dir or Path.home() / ".seo" / "cache"
            try:
                self._cache = AICache(
                    cache_dir=cache_path,
                    ttl_hours=cache_ttl_hours,
                    max_size_mb=100,
                    enabled=True,
                )
                logger.info(f"LLM cache enabled at {cache_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM cache: {e}")
                self._cache = None

    @property
    def source_api(self) -> str:
        """Get full source API identifier for evidence provenance."""
        return f"{self.provider}_{self.model}".replace("-", "_").replace(".", "_")

    def analyze_seo(
        self, content: str, metadata: dict, url: str
    ) -> dict[str, any]:
        """Analyze SEO using LLM.

        Args:
            content: Page content (HTML or text)
            metadata: Page metadata dictionary
            url: Page URL

        Returns:
            Dictionary containing SEO analysis results with evidence trail
        """
        # Capture input summary for evidence trail
        input_summary = self._build_input_summary(content, metadata, url)

        prompt = self._build_seo_prompt(content, metadata, url)

        # Generate prompt hash for reproducibility
        prompt_hash = self._compute_prompt_hash(prompt)

        # Check cache first
        cache_context = {'model': self.model, 'provider': self.provider, 'url': url}
        if self._cache:
            cached_response = self._cache.get(prompt, context=cache_context)
            if cached_response:
                self._cache_hits += 1
                logger.debug(f"Cache hit for {url} (total hits: {self._cache_hits})")
                # Return cached result with cache metadata
                cached_response['from_cache'] = True
                return cached_response

        self._cache_misses += 1

        try:
            response = self._call_llm(prompt)

            # Handle empty response (edge case)
            if not response or not response.strip():
                return self._create_error_result(
                    error_message="LLM returned empty response",
                    input_summary=input_summary,
                    prompt_hash=prompt_hash,
                    url=url,
                    raw_response=response,
                )

            result = self._parse_seo_response(response)

            # Check for parsing failure (edge case)
            if not result or result.get('parse_error'):
                return self._create_error_result(
                    error_message=result.get('parse_error', 'Failed to parse LLM response'),
                    input_summary=input_summary,
                    prompt_hash=prompt_hash,
                    url=url,
                    raw_response=response,
                )

            # Create evidence collection for this LLM analysis
            evidence = self._create_evidence(
                result=result,
                input_summary=input_summary,
                prompt_hash=prompt_hash,
                raw_response=response,
                url=url,
            )

            # Add evidence to result
            result['evidence'] = evidence
            result['ai_generated'] = True
            result['model_id'] = self.model
            result['provider'] = self.provider
            result['from_cache'] = False

            # Cache the successful result
            if self._cache:
                try:
                    self._cache.put(
                        prompt=prompt,
                        response=result,
                        model=self.model,
                        context=cache_context,
                    )
                    logger.debug(f"Cached LLM response for {url}")
                except Exception as e:
                    logger.warning(f"Failed to cache response: {e}")

            return result

        except Exception as e:
            # Edge case: LLM API failure - still capture partial evidence
            logger.error(f"LLM analysis failed for {url}: {e}")
            return self._create_error_result(
                error_message=str(e),
                input_summary=input_summary,
                prompt_hash=prompt_hash,
                url=url,
                raw_response=None,
            )

    def _create_error_result(
        self,
        error_message: str,
        input_summary: dict,
        prompt_hash: str,
        url: str,
        raw_response: Optional[str] = None,
    ) -> dict:
        """Create a result dict for LLM errors, preserving partial evidence.

        PARTIAL EVIDENCE CAPTURE
        ========================
        Even when LLM analysis fails, we capture what evidence is available.
        This serves several purposes:

        1. DEBUGGING:
           - Error messages are preserved in evidence records
           - Raw response (if any) is captured for investigation
           - Prompt hash allows reproduction of the exact prompt

        2. AUDIT TRAIL:
           - Records that an analysis was attempted
           - Shows what inputs were provided
           - Documents the failure for transparency

        3. RECOVERY:
           - Preserved input_summary allows retry with same data
           - prompt_hash enables comparison across retries
           - regenerate_recommendations.py can use this info

        WHAT IS CAPTURED:
        - component_id: 'llm_scoring' (identifies the failing component)
        - finding: 'llm_error' (categorizes as error)
        - evidence_string: The error message
        - confidence: LOW (errors never have high confidence)
        - model_id, provider: Which LLM was attempted
        - prompt_hash: For reproducibility
        - input_summary: What data was sent
        - raw_response: First 1000 chars if available (truncated for storage)
        - recommendation: Suggests using regenerate script

        DISTINGUISHING FROM COMPLETE EVIDENCE:
        - error_flag=True in result dict
        - confidence is always LOW
        - severity='error' in evidence record
        - overall_score and sub-scores are 0

        Args:
            error_message: Description of the error
            input_summary: Summary of inputs to LLM
            prompt_hash: Hash of the prompt
            url: URL being analyzed
            raw_response: Raw LLM response if available (truncated to 1000 chars)

        Returns:
            Result dict with error info and partial evidence
        """
        # Create evidence record even for failures
        evidence_collection = EvidenceCollection(
            finding='seo_analysis_error',
            component_id='llm_scoring',
        )

        error_record = EvidenceRecord(
            component_id='llm_scoring',
            finding='llm_error',
            evidence_string=error_message,
            confidence=ConfidenceLevel.LOW,  # Errors always have low confidence
            timestamp=datetime.now(),
            source=self.SOURCE_LABEL,
            source_type=EvidenceSourceType.LLM_INFERENCE,
            source_location=url,
            ai_generated=True,
            model_id=self.model,
            provider=self.provider,
            source_api=self.source_api,
            prompt_hash=prompt_hash,
            input_summary=input_summary,
            severity='error',
            recommendation='Run regenerate_recommendations.py to retry LLM analysis',
        )

        # Capture raw response if available (for debugging)
        if raw_response:
            error_record.measured_value = {'raw_response': raw_response[:1000]}

        evidence_collection.add_record(error_record)

        return {
            'overall_score': 0,
            'title_score': 0,
            'description_score': 0,
            'content_score': 0,
            'technical_score': 0,
            'strengths': [],
            'weaknesses': [],
            'recommendations': [],
            'reasoning': f"Analysis failed: {error_message}",
            'evidence': evidence_collection.to_dict(),
            'ai_generated': True,
            'model_id': self.model,
            'provider': self.provider,
            'error': error_message,
            'error_flag': True,
        }

    def _build_input_summary(
        self, content: str, metadata: dict, url: str
    ) -> dict:
        """Build a summary of inputs provided to the LLM.

        This captures what data was sent to the LLM for audit trail purposes.

        Args:
            content: Page content
            metadata: Page metadata
            url: Page URL

        Returns:
            Dictionary summarizing inputs
        """
        title = metadata.get('title', '')
        description = metadata.get('description', '')
        h1_tags = metadata.get('h1_tags', [])

        return {
            'url': url,
            'title': title,
            'title_length': len(title) if title else 0,
            'description': description,
            'description_length': len(description) if description else 0,
            'h1_count': len(h1_tags) if h1_tags else 0,
            'h1_tags': h1_tags[:5] if h1_tags else [],  # First 5 H1s
            'word_count': metadata.get('word_count', 0),
            'content_snippet': content[:1000] if content else '',
            'content_length': len(content) if content else 0,
            'keywords': metadata.get('keywords', [])[:10],  # First 10 keywords
        }

    def _compute_prompt_hash(self, prompt: str) -> str:
        """Compute SHA-256 hash of the prompt for reproducibility.

        Args:
            prompt: The full prompt text

        Returns:
            SHA-256 hash string
        """
        return hashlib.sha256(prompt.encode('utf-8')).hexdigest()

    def _create_evidence(
        self,
        result: dict,
        input_summary: dict,
        prompt_hash: str,
        raw_response: str,
        url: str,
    ) -> dict:
        """Create evidence collection for LLM analysis.

        Args:
            result: Parsed LLM result
            input_summary: Summary of inputs to LLM
            prompt_hash: Hash of the prompt
            raw_response: Raw LLM response text
            url: URL being analyzed

        Returns:
            Evidence collection as dictionary
        """
        evidence_collection = EvidenceCollection(
            finding='seo_analysis',
            component_id='llm_scoring',
        )

        # Extract reasoning if present
        reasoning = result.get('reasoning', '')
        if not reasoning and 'weaknesses' in result:
            # Build reasoning from weaknesses if not explicitly provided
            reasoning = '; '.join(result.get('weaknesses', []))

        # Create evidence record for overall score
        overall_record = EvidenceRecord.from_llm(
            component_id='llm_scoring',
            finding=f"overall_score:{result.get('overall_score', 0)}",
            model_id=self.model,
            reasoning=reasoning,
            input_summary=input_summary,
            prompt_hash=prompt_hash,
            provider=self.provider,
        )
        overall_record.source_location = url
        overall_record.measured_value = result.get('overall_score', 0)
        evidence_collection.add_record(overall_record)

        # Create evidence records for individual scores
        score_fields = [
            ('title_score', 'Title optimization score'),
            ('description_score', 'Meta description score'),
            ('content_score', 'Content quality score'),
            ('technical_score', 'Technical SEO score'),
        ]

        for field, description in score_fields:
            if field in result:
                record = EvidenceRecord(
                    component_id='llm_scoring',
                    finding=f"{field}:{result[field]}",
                    evidence_string=description,
                    confidence=ConfidenceLevel.MEDIUM,  # LLM outputs capped at MEDIUM
                    timestamp=datetime.now(),
                    source=self.SOURCE_LABEL,
                    source_type=EvidenceSourceType.LLM_INFERENCE,
                    source_location=url,
                    ai_generated=True,
                    model_id=self.model,
                    provider=self.provider,
                    source_api=self.source_api,
                    measured_value=result[field],
                    confidence_override_reason='LLM-only evaluations capped at MEDIUM per hallucination mitigation policy',
                )
                evidence_collection.add_record(record)

        return evidence_collection.to_dict()

    def _build_seo_prompt(
        self, content: str, metadata: dict, url: str
    ) -> str:
        """Build the prompt for SEO analysis.

        Args:
            content: Page content
            metadata: Page metadata
            url: Page URL

        Returns:
            Formatted prompt string
        """
        title = metadata.get('title', 'N/A')
        description = metadata.get('description', 'N/A')
        h1_tags = metadata.get('h1_tags', [])
        word_count = metadata.get('word_count', 0)

        return f"""Analyze the following web page for SEO quality and provide recommendations.

URL: {url}

Metadata:
- Title: {title} (Length: {len(title) if title != 'N/A' else 0} characters)
- Description: {description} (Length: {len(description) if description != 'N/A' else 0} characters)
- H1 Tags: {', '.join(h1_tags) if h1_tags else 'None'} (Count: {len(h1_tags)})
- Word Count: {word_count}

Content Preview (first 1000 chars):
{content[:1000]}

Please provide:
1. An overall SEO score (0-100)
2. Individual scores for:
   - Title optimization (consider: length 50-60 chars ideal, keyword presence)
   - Meta description (consider: length 120-160 chars ideal, compelling copy)
   - Content quality (consider: word count > 300, readability, structure)
   - Technical SEO (consider: proper tags, structure, accessibility)
3. List of strengths
4. List of weaknesses
5. Actionable recommendations for improvement
6. A DETAILED reasoning explaining the overall score

CRITICAL REASONING REQUIREMENTS:
- You MUST reference EXACT measured values from the metadata above
- For title issues: cite the actual title length (e.g., "Title is 23 characters, below the recommended 50-60")
- For content issues: cite the actual word count (e.g., "Only 187 words, well below 300 minimum")
- For description issues: cite the actual length (e.g., "Description at 45 chars is too short")
- For H1 issues: cite the actual count (e.g., "Page has 0 H1 tags" or "Page has 3 H1 tags, should have exactly 1")
- Reference thresholds when explaining deductions

Format your response ONLY as TOON (Token-Oriented Object Notation) with NO additional text.
Use this exact structure:
overall_score: <number>
title_score: <number>
description_score: <number>
content_score: <number>
technical_score: <number>
strengths[N]: <comma-separated values>
weaknesses[N]: <comma-separated values>
recommendations[N]: <comma-separated values>
reasoning: <paragraph with SPECIFIC data references like "title at X chars", "word count of Y", "Z H1 tags">

Where [N] is the count of items in each array.
"""

    def _call_llm(
        self,
        prompt: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        backoff_factor: float = 2.0,
    ) -> str:
        """Call the LLM with the given prompt, with retry logic.

        Implements exponential backoff for transient failures (connection errors,
        rate limits, timeouts). Non-retryable errors (auth, invalid model) are
        raised immediately.

        Args:
            prompt: The prompt to send
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 2.0)
            backoff_factor: Multiplier for delay after each retry (default: 2.0)

        Returns:
            LLM response text

        Raises:
            Exception: If all retries are exhausted or non-retryable error occurs
        """
        last_exception = None
        current_delay = retry_delay

        for attempt in range(max_retries + 1):
            try:
                if self.provider == "openai":
                    return self._call_openai(prompt)
                elif self.provider == "anthropic":
                    return self._call_anthropic(prompt)
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")

            except Exception as e:
                error_str = str(e).lower()
                last_exception = e

                # Non-retryable errors - fail fast
                non_retryable = [
                    'invalid api key',
                    'authentication',
                    'unauthorized',
                    'invalid_api_key',
                    'model not found',
                    'invalid model',
                ]
                if any(err in error_str for err in non_retryable):
                    logger.error(f"Non-retryable LLM error: {e}")
                    raise

                # Retryable errors - connection, rate limit, timeout
                if attempt < max_retries:
                    logger.warning(
                        f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
                else:
                    logger.error(
                        f"LLM call failed after {max_retries + 1} attempts: {e}"
                    )

        raise last_exception

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API.

        Args:
            prompt: The prompt to send

        Returns:
            Response text
        """
        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert SEO analyst.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content
        except ImportError:
            raise ImportError(
                "openai package not installed. Install with: poetry add openai"
            )

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API.

        Args:
            prompt: The prompt to send

        Returns:
            Response text
        """
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Install with: poetry add anthropic"
            )

    def _parse_seo_response(self, response: str) -> dict[str, any]:
        """Parse the LLM response into structured data.

        Args:
            response: Raw LLM response

        Returns:
            Parsed dictionary
        """
        try:
            # Extract TOON content (remove any markdown or explanatory text)
            lines = response.strip().split('\n')
            toon_lines = []

            # Look for lines that match TOON format (key: value or key[N]: values)
            for line in lines:
                stripped = line.strip()
                # Match TOON format: field_name: value or field_name[N]: values
                if stripped and (':' in stripped):
                    # Check if it's a valid TOON field
                    key_part = stripped.split(':', 1)[0].strip()
                    # Valid if it's alphanumeric with underscores, optionally with [N]
                    if key_part.replace('[', '').replace(']', '').replace('_', '').replace(' ', '').isalnum():
                        toon_lines.append(stripped)

            toon_str = '\n'.join(toon_lines) if toon_lines else response

            # Decode TOON format to Python dict
            result = toon.decode(toon_str)

            # Clean up result if it contains unexpected keys
            expected_keys = {
                'overall_score', 'title_score', 'description_score',
                'content_score', 'technical_score', 'strengths',
                'weaknesses', 'recommendations', 'reasoning'
            }

            # Filter to only expected keys
            filtered_result = {k: v for k, v in result.items() if k in expected_keys}

            # Return filtered result if it has the main keys, otherwise return all
            if 'overall_score' in filtered_result:
                return filtered_result
            return result

        except Exception as e:
            return {
                "overall_score": 0,
                "title_score": 0,
                "description_score": 0,
                "content_score": 0,
                "technical_score": 0,
                "strengths": [],
                "weaknesses": ["Failed to parse LLM response"],
                "recommendations": [
                    "Unable to analyze - please try again"
                ],
                "error": str(e),
            }

    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with cache hit/miss stats and storage info
        """
        stats = {
            'cache_enabled': self._cache is not None,
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
        }

        if self._cache:
            cache_stats = self._cache.stats()
            stats.update({
                'cache_entries': cache_stats.get('entry_count', 0),
                'cache_size_mb': cache_stats.get('size_mb', 0),
                'cache_ttl_hours': cache_stats.get('ttl_hours', 0),
            })

        return stats

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        if self._cache:
            self._cache.clear()
            logger.info("LLM cache cleared")
