"""Unit tests for CaptchaSolver.

Tests the CAPTCHA solver framework addressing Critical Gap #1.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from seo.utils.captcha_solver import (
    BaseCaptchaSolver,
    TwoCaptchaSolver,
    MockCaptchaSolver,
    CaptchaType,
    SolverStatus,
    SolveResult,
    get_solver,
)


class TestCaptchaType:
    """Tests for CaptchaType enum."""

    def test_captcha_types_exist(self):
        """Verify all captcha types are defined."""
        assert CaptchaType.RECAPTCHA_V2.value == "recaptcha_v2"
        assert CaptchaType.RECAPTCHA_V2_INVISIBLE.value == "recaptcha_v2_invisible"
        assert CaptchaType.RECAPTCHA_V3.value == "recaptcha_v3"
        assert CaptchaType.RECAPTCHA_ENTERPRISE.value == "recaptcha_enterprise"
        assert CaptchaType.HCAPTCHA.value == "hcaptcha"
        assert CaptchaType.TURNSTILE.value == "turnstile"


class TestSolverStatus:
    """Tests for SolverStatus enum."""

    def test_solver_statuses_exist(self):
        """Verify all solver statuses are defined."""
        assert SolverStatus.PENDING.value == "pending"
        assert SolverStatus.PROCESSING.value == "processing"
        assert SolverStatus.SOLVED.value == "solved"
        assert SolverStatus.FAILED.value == "failed"
        assert SolverStatus.TIMEOUT.value == "timeout"
        assert SolverStatus.UNSUPPORTED.value == "unsupported"


class TestSolveResult:
    """Tests for SolveResult dataclass."""

    def test_create_solve_result(self):
        """Test creating a solve result."""
        result = SolveResult(
            status=SolverStatus.SOLVED,
            captcha_type=CaptchaType.RECAPTCHA_V2,
            solution="token123",
            task_id="task-abc",
            solve_time_seconds=5.5,
            cost=0.003,
        )

        assert result.status == SolverStatus.SOLVED
        assert result.solution == "token123"
        assert result.solve_time_seconds == 5.5
        assert result.timestamp is not None

    def test_solve_result_to_dict(self):
        """Test serialization to dictionary."""
        result = SolveResult(
            status=SolverStatus.SOLVED,
            captcha_type=CaptchaType.RECAPTCHA_V2,
            solution="token123",
            task_id="task-abc",
        )

        data = result.to_dict()

        assert data["status"] == "solved"
        assert data["captcha_type"] == "recaptcha_v2"
        assert data["solution"] == "token123"
        assert "timestamp" in data

    def test_solve_result_failed(self):
        """Test creating a failed result."""
        result = SolveResult(
            status=SolverStatus.FAILED,
            captcha_type=CaptchaType.HCAPTCHA,
            error="API error: invalid key",
        )

        assert result.status == SolverStatus.FAILED
        assert result.solution is None
        assert "invalid key" in result.error


class TestMockCaptchaSolver:
    """Tests for MockCaptchaSolver."""

    @pytest.fixture
    def solver(self):
        """Create a mock solver for testing."""
        return MockCaptchaSolver(solve_delay=0.1, fail_rate=0.0)

    def test_service_name(self, solver):
        """Test service name property."""
        assert solver.service_name == "MockSolver"

    def test_supported_types(self, solver):
        """Test all captcha types are supported."""
        assert CaptchaType.RECAPTCHA_V2 in solver.supported_types
        assert CaptchaType.HCAPTCHA in solver.supported_types
        assert len(solver.supported_types) == len(CaptchaType)

    @pytest.mark.asyncio
    async def test_solve_success(self, solver):
        """Test successful solve."""
        result = await solver.solve(
            captcha_type=CaptchaType.RECAPTCHA_V2,
            sitekey="test-sitekey",
            page_url="https://example.com",
        )

        assert result.status == SolverStatus.SOLVED
        assert result.solution is not None
        assert "mock-solution-token" in result.solution

    @pytest.mark.asyncio
    async def test_solve_with_delay(self):
        """Test that solve respects delay."""
        solver = MockCaptchaSolver(solve_delay=0.5)

        start = asyncio.get_event_loop().time()
        result = await solver.solve(
            captcha_type=CaptchaType.RECAPTCHA_V2,
            sitekey="test",
            page_url="https://example.com",
        )
        elapsed = asyncio.get_event_loop().time() - start

        assert result.status == SolverStatus.SOLVED
        assert elapsed >= 0.5

    @pytest.mark.asyncio
    async def test_solve_with_fail_rate(self):
        """Test that fail_rate causes failures."""
        solver = MockCaptchaSolver(solve_delay=0.1, fail_rate=1.0)

        result = await solver.solve(
            captcha_type=CaptchaType.RECAPTCHA_V2,
            sitekey="test",
            page_url="https://example.com",
        )

        assert result.status == SolverStatus.FAILED

    def test_get_stats(self, solver):
        """Test getting solver statistics."""
        stats = solver.get_stats()

        assert stats["service"] == "MockSolver"
        assert stats["total_requests"] == 0
        assert stats["successful_solves"] == 0
        assert stats["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_update_after_solve(self, solver):
        """Test stats update after solving."""
        await solver.solve(
            captcha_type=CaptchaType.RECAPTCHA_V2,
            sitekey="test",
            page_url="https://example.com",
        )

        stats = solver.get_stats()

        assert stats["total_requests"] == 1
        assert stats["successful_solves"] == 1
        assert stats["success_rate"] == 1.0


class TestTwoCaptchaSolver:
    """Tests for TwoCaptchaSolver."""

    def test_service_name(self):
        """Test service name property."""
        solver = TwoCaptchaSolver(api_key="test-key")
        assert solver.service_name == "2Captcha"

    def test_supported_types(self):
        """Test supported captcha types."""
        solver = TwoCaptchaSolver(api_key="test-key")

        assert CaptchaType.RECAPTCHA_V2 in solver.supported_types
        assert CaptchaType.RECAPTCHA_V3 in solver.supported_types
        assert CaptchaType.HCAPTCHA in solver.supported_types
        assert CaptchaType.TURNSTILE in solver.supported_types

    def test_api_key_from_env(self):
        """Test API key loaded from environment."""
        with patch.dict("os.environ", {"TWOCAPTCHA_API_KEY": "env-key"}):
            solver = TwoCaptchaSolver()
            assert solver.api_key == "env-key"

    @pytest.mark.asyncio
    async def test_solve_unsupported_type(self):
        """Test solving unsupported captcha type returns UNSUPPORTED."""
        solver = TwoCaptchaSolver(api_key="test")

        # Remove a type from supported list temporarily
        original_types = solver.supported_types.copy()

        class LimitedSolver(TwoCaptchaSolver):
            @property
            def supported_types(self):
                return []

        limited = LimitedSolver(api_key="test")
        result = await limited.solve(
            captcha_type=CaptchaType.RECAPTCHA_V2,
            sitekey="test",
            page_url="https://example.com",
        )

        assert result.status == SolverStatus.UNSUPPORTED


class TestSolveRecaptchaV2:
    """Tests for solve_recaptcha_v2 convenience method."""

    @pytest.fixture
    def solver(self):
        """Create a mock solver."""
        return MockCaptchaSolver(solve_delay=0.1)

    @pytest.mark.asyncio
    async def test_solve_with_sitekey(self, solver):
        """Test solving with provided sitekey."""
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/form"

        result = await solver.solve_recaptcha_v2(
            page=mock_page,
            sitekey="explicit-sitekey",
        )

        assert result.status == SolverStatus.SOLVED

    @pytest.mark.asyncio
    async def test_solve_auto_detect_sitekey(self, solver):
        """Test auto-detecting sitekey from page."""
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/form"
        mock_page.evaluate = AsyncMock(return_value="detected-sitekey")

        result = await solver.solve_recaptcha_v2(page=mock_page)

        assert result.status == SolverStatus.SOLVED
        mock_page.evaluate.assert_called()

    @pytest.mark.asyncio
    async def test_solve_no_sitekey_found(self, solver):
        """Test failure when sitekey cannot be detected."""
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/form"
        mock_page.evaluate = AsyncMock(return_value=None)

        result = await solver.solve_recaptcha_v2(page=mock_page)

        assert result.status == SolverStatus.FAILED
        assert "sitekey" in result.error.lower()


class TestInjectRecaptchaResponse:
    """Tests for _inject_recaptcha_response method."""

    @pytest.fixture
    def solver(self):
        """Create a mock solver."""
        return MockCaptchaSolver(solve_delay=0.1)

    @pytest.mark.asyncio
    async def test_inject_token(self, solver):
        """Test injecting token into page."""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock()

        await solver._inject_recaptcha_response(mock_page, "test-token")

        mock_page.evaluate.assert_called_once()
        call_args = mock_page.evaluate.call_args
        assert "test-token" in str(call_args)


class TestGetSolver:
    """Tests for get_solver factory function."""

    def test_get_2captcha_solver(self):
        """Test getting 2Captcha solver."""
        solver = get_solver("2captcha", api_key="test-key")

        assert isinstance(solver, TwoCaptchaSolver)
        assert solver.api_key == "test-key"

    def test_get_mock_solver(self):
        """Test getting mock solver."""
        solver = get_solver("mock", solve_delay=1.0)

        assert isinstance(solver, MockCaptchaSolver)
        assert solver.solve_delay == 1.0

    def test_get_unknown_solver_raises(self):
        """Test that unknown solver raises ValueError."""
        with pytest.raises(ValueError, match="Unknown solver"):
            get_solver("unknown_service")

    def test_case_insensitive(self):
        """Test that service name is case insensitive."""
        solver = get_solver("2CAPTCHA", api_key="test")
        assert isinstance(solver, TwoCaptchaSolver)

        solver = get_solver("Mock")
        assert isinstance(solver, MockCaptchaSolver)
