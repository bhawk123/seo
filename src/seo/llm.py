"""LLM client for SEO analysis."""

from typing import Optional
import os
import toon


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
            Dictionary containing SEO analysis results
        """
        prompt = self._build_seo_prompt(content, metadata, url)

        response = self._call_llm(prompt)

        return self._parse_seo_response(response)

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
        return f"""Analyze the following web page for SEO quality and provide recommendations.

URL: {url}

Metadata:
- Title: {metadata.get('title', 'N/A')}
- Description: {metadata.get('description', 'N/A')}
- H1 Tags: {', '.join(metadata.get('h1_tags', []))}
- Word Count: {metadata.get('word_count', 0)}

Content Preview (first 1000 chars):
{content[:1000]}

Please provide:
1. An overall SEO score (0-100)
2. Individual scores for:
   - Title optimization
   - Meta description
   - Content quality
   - Technical SEO
3. List of strengths
4. List of weaknesses
5. Actionable recommendations for improvement

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
                'weaknesses', 'recommendations'
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
