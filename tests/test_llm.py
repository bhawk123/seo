"""Tests for LLM client."""

import pytest
from unittest.mock import Mock, patch
from seo.llm import LLMClient


class TestLLMClient:
    """Test cases for LLMClient."""

    def test_llm_initialization_with_key(self):
        """Test LLM client initialization with API key."""
        client = LLMClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.model == "gpt-4"
        assert client.provider == "openai"
        assert client.max_tokens == 8192

    def test_llm_initialization_with_custom_max_tokens(self):
        """Test LLM client initialization with custom max_tokens."""
        client = LLMClient(api_key="test-key", max_tokens=4096)
        assert client.max_tokens == 4096

    def test_llm_initialization_without_key(self):
        """Test LLM client initialization without API key raises error."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API key must be provided"):
                LLMClient()

    def test_llm_initialization_from_env(self):
        """Test LLM client initialization from environment variable."""
        with patch.dict("os.environ", {"LLM_API_KEY": "env-key"}):
            client = LLMClient()
            assert client.api_key == "env-key"

    def test_build_seo_prompt(self):
        """Test SEO prompt building."""
        client = LLMClient(api_key="test-key")
        metadata = {
            "title": "Test Title",
            "description": "Test description",
            "h1_tags": ["Heading 1"],
            "word_count": 500,
        }

        prompt = client._build_seo_prompt(
            "Sample content", metadata, "https://example.com"
        )

        assert "https://example.com" in prompt
        assert "Test Title" in prompt
        assert "Test description" in prompt
        assert "500" in prompt

    def test_parse_seo_response_valid_toon(self):
        """Test parsing valid TOON response."""
        client = LLMClient(api_key="test-key")
        response = """
overall_score: 85
title_score: 90
description_score: 80
content_score: 85
technical_score: 90
strengths[1]: Good title
weaknesses[1]: Improve description
recommendations[1]: Add keywords
        """

        result = client._parse_seo_response(response)

        assert result["overall_score"] == 85
        assert result["title_score"] == 90
        assert len(result["strengths"]) == 1
        assert len(result["recommendations"]) == 1

    def test_parse_seo_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        client = LLMClient(api_key="test-key")
        response = "This is not valid JSON"

        result = client._parse_seo_response(response)

        assert result["overall_score"] == 0
        assert "Failed to parse LLM response" in result["weaknesses"]
        assert "error" in result

    @patch("openai.OpenAI")
    def test_call_openai(self, mock_openai_class):
        """Test calling OpenAI API."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key="test-key", provider="openai")
        response = client._call_openai("Test prompt")

        assert response == "Test response"
        mock_client.chat.completions.create.assert_called_once()
