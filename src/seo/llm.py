"""LLM client for SEO analysis."""

from typing import Optional
from datetime import datetime
import hashlib
import os
import toon

from seo.models import (
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)


class LLMClient:
    """Client for interacting with LLM for SEO analysis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        provider: str = "openai",
        max_tokens: int = 8192,
    ):
        """Initialize the LLM client.

        Args:
            api_key: API key for the LLM provider
            model: Model name to use
            provider: LLM provider (openai, anthropic, etc.)
            max_tokens: Maximum tokens for LLM response (default: 8192)
        """
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model
        self.provider = provider
        self.max_tokens = max_tokens

        if not self.api_key:
            raise ValueError(
                "API key must be provided or set in LLM_API_KEY environment variable"
            )

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

        response = self._call_llm(prompt)

        result = self._parse_seo_response(response)

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

        return result

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
                    source='LLM Inference',
                    source_type=EvidenceSourceType.LLM_INFERENCE,
                    source_location=url,
                    ai_generated=True,
                    model_id=self.model,
                    measured_value=result[field],
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
6. A brief reasoning explaining the overall score, referencing specific measurements

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
reasoning: <one paragraph explaining the overall score with specific data references>

Where [N] is the count of items in each array.
"""

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the given prompt.

        Args:
            prompt: The prompt to send

        Returns:
            LLM response text
        """
        if self.provider == "openai":
            return self._call_openai(prompt)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

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
