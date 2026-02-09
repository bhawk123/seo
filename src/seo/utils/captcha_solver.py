"""
CAPTCHA solver integration framework.

Addresses Critical Gap #1: CAPTCHA solving integration.

This module provides a pluggable framework for integrating with external
CAPTCHA solving services like 2Captcha, Anti-Captcha, CapMonster, etc.

Usage:
    from seo.utils.captcha_solver import CaptchaSolver, TwoCaptchaSolver

    # Configure solver with API key
    solver = TwoCaptchaSolver(api_key="your-api-key")

    # Solve reCAPTCHA on page
    result = await solver.solve_recaptcha(page, sitekey="...")

Note: This provides the integration framework. You need an API key from
a solving service to actually solve CAPTCHAs.
"""
import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CaptchaType(Enum):
    """Types of CAPTCHAs we can handle."""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V2_INVISIBLE = "recaptcha_v2_invisible"
    RECAPTCHA_V3 = "recaptcha_v3"
    RECAPTCHA_ENTERPRISE = "recaptcha_enterprise"
    HCAPTCHA = "hcaptcha"
    FUNCAPTCHA = "funcaptcha"
    TURNSTILE = "turnstile"  # Cloudflare
    IMAGE_CAPTCHA = "image_captcha"


class SolverStatus(Enum):
    """Status of a solve request."""
    PENDING = "pending"
    PROCESSING = "processing"
    SOLVED = "solved"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNSUPPORTED = "unsupported"


@dataclass
class SolveResult:
    """Result from a CAPTCHA solve attempt."""
    status: SolverStatus
    captcha_type: CaptchaType
    solution: Optional[str] = None  # The token/response to submit
    task_id: Optional[str] = None
    solve_time_seconds: float = 0.0
    cost: float = 0.0  # Cost in USD if known
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "captcha_type": self.captcha_type.value,
            "solution": self.solution,
            "task_id": self.task_id,
            "solve_time_seconds": self.solve_time_seconds,
            "cost": self.cost,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseCaptchaSolver(ABC):
    """
    Abstract base class for CAPTCHA solvers.

    Implement this class to integrate with different solving services.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: int = 120,
        poll_interval: float = 5.0,
    ):
        """
        Initialize solver.

        Args:
            api_key: API key for the solving service
            timeout_seconds: Maximum time to wait for solution
            poll_interval: Seconds between status checks
        """
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval

        # Statistics
        self._total_requests = 0
        self._successful_solves = 0
        self._failed_solves = 0
        self._total_cost = 0.0

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Name of the solving service."""
        pass

    @property
    @abstractmethod
    def supported_types(self) -> list[CaptchaType]:
        """List of supported CAPTCHA types."""
        pass

    @abstractmethod
    async def _submit_task(
        self,
        captcha_type: CaptchaType,
        sitekey: str,
        page_url: str,
        **kwargs,
    ) -> str:
        """
        Submit a CAPTCHA solving task.

        Returns task_id for tracking.
        """
        pass

    @abstractmethod
    async def _get_result(self, task_id: str) -> SolveResult:
        """Get result for a submitted task."""
        pass

    async def solve(
        self,
        captcha_type: CaptchaType,
        sitekey: str,
        page_url: str,
        **kwargs,
    ) -> SolveResult:
        """
        Solve a CAPTCHA.

        Args:
            captcha_type: Type of CAPTCHA
            sitekey: Site key from the CAPTCHA element
            page_url: URL where CAPTCHA appears
            **kwargs: Additional solver-specific options

        Returns:
            SolveResult with solution or error
        """
        if captcha_type not in self.supported_types:
            return SolveResult(
                status=SolverStatus.UNSUPPORTED,
                captcha_type=captcha_type,
                error=f"{self.service_name} does not support {captcha_type.value}",
            )

        self._total_requests += 1
        start_time = asyncio.get_event_loop().time()

        try:
            # Submit task
            task_id = await self._submit_task(
                captcha_type=captcha_type,
                sitekey=sitekey,
                page_url=page_url,
                **kwargs,
            )

            # Poll for result
            elapsed = 0.0
            while elapsed < self.timeout_seconds:
                await asyncio.sleep(self.poll_interval)
                elapsed = asyncio.get_event_loop().time() - start_time

                result = await self._get_result(task_id)

                if result.status == SolverStatus.SOLVED:
                    result.solve_time_seconds = elapsed
                    self._successful_solves += 1
                    self._total_cost += result.cost
                    logger.info(
                        f"{self.service_name} solved {captcha_type.value} "
                        f"in {elapsed:.1f}s"
                    )
                    return result

                if result.status == SolverStatus.FAILED:
                    self._failed_solves += 1
                    return result

            # Timeout
            self._failed_solves += 1
            return SolveResult(
                status=SolverStatus.TIMEOUT,
                captcha_type=captcha_type,
                task_id=task_id,
                solve_time_seconds=elapsed,
                error=f"Timeout after {self.timeout_seconds}s",
            )

        except Exception as e:
            self._failed_solves += 1
            logger.error(f"{self.service_name} solve error: {e}")
            return SolveResult(
                status=SolverStatus.FAILED,
                captcha_type=captcha_type,
                error=str(e),
            )

    async def solve_recaptcha_v2(
        self,
        page,
        sitekey: Optional[str] = None,
    ) -> SolveResult:
        """
        Convenience method to solve reCAPTCHA v2 on a page.

        Args:
            page: Playwright Page instance
            sitekey: Site key (auto-detected if not provided)

        Returns:
            SolveResult with solution
        """
        page_url = page.url

        # Auto-detect sitekey if not provided
        if not sitekey:
            sitekey = await page.evaluate("""
                () => {
                    const el = document.querySelector('.g-recaptcha');
                    return el ? el.getAttribute('data-sitekey') : null;
                }
            """)

        if not sitekey:
            return SolveResult(
                status=SolverStatus.FAILED,
                captcha_type=CaptchaType.RECAPTCHA_V2,
                error="Could not detect reCAPTCHA sitekey",
            )

        result = await self.solve(
            captcha_type=CaptchaType.RECAPTCHA_V2,
            sitekey=sitekey,
            page_url=page_url,
        )

        # Inject solution if successful
        if result.status == SolverStatus.SOLVED and result.solution:
            await self._inject_recaptcha_response(page, result.solution)

        return result

    async def _inject_recaptcha_response(self, page, token: str) -> None:
        """Inject reCAPTCHA response token into page."""
        await page.evaluate(
            """
            (token) => {
                // Set the response textarea
                const textarea = document.getElementById('g-recaptcha-response');
                if (textarea) {
                    textarea.value = token;
                    textarea.style.display = 'block';
                }

                // Also set any hidden textareas
                document.querySelectorAll('[name="g-recaptcha-response"]').forEach(el => {
                    el.value = token;
                });

                // Trigger callback if defined
                if (typeof ___grecaptcha_cfg !== 'undefined') {
                    Object.entries(___grecaptcha_cfg.clients).forEach(([key, client]) => {
                        try {
                            const callback = Object.values(client).find(v => v && v.callback);
                            if (callback && callback.callback) {
                                callback.callback(token);
                            }
                        } catch (e) {}
                    });
                }
            }
            """,
            token,
        )
        logger.debug("Injected reCAPTCHA response token")

    def get_stats(self) -> Dict[str, Any]:
        """Get solver statistics."""
        return {
            "service": self.service_name,
            "total_requests": self._total_requests,
            "successful_solves": self._successful_solves,
            "failed_solves": self._failed_solves,
            "success_rate": (
                self._successful_solves / self._total_requests
                if self._total_requests > 0
                else 0.0
            ),
            "total_cost_usd": self._total_cost,
        }


class TwoCaptchaSolver(BaseCaptchaSolver):
    """
    2Captcha solving service integration.

    API Documentation: https://2captcha.com/2captcha-api

    Requires: pip install 2captcha-python
    """

    API_BASE = "https://2captcha.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: int = 120,
        poll_interval: float = 5.0,
    ):
        super().__init__(
            api_key=api_key or os.getenv("TWOCAPTCHA_API_KEY"),
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
        )

    @property
    def service_name(self) -> str:
        return "2Captcha"

    @property
    def supported_types(self) -> list[CaptchaType]:
        return [
            CaptchaType.RECAPTCHA_V2,
            CaptchaType.RECAPTCHA_V2_INVISIBLE,
            CaptchaType.RECAPTCHA_V3,
            CaptchaType.HCAPTCHA,
            CaptchaType.FUNCAPTCHA,
            CaptchaType.TURNSTILE,
            CaptchaType.IMAGE_CAPTCHA,
        ]

    async def _submit_task(
        self,
        captcha_type: CaptchaType,
        sitekey: str,
        page_url: str,
        **kwargs,
    ) -> str:
        """Submit task to 2Captcha."""
        try:
            import aiohttp
        except ImportError:
            raise ImportError("aiohttp required for 2Captcha: pip install aiohttp")

        params = {
            "key": self.api_key,
            "json": 1,
        }

        if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V2_INVISIBLE):
            params.update({
                "method": "userrecaptcha",
                "googlekey": sitekey,
                "pageurl": page_url,
                "invisible": 1 if captcha_type == CaptchaType.RECAPTCHA_V2_INVISIBLE else 0,
            })
        elif captcha_type == CaptchaType.RECAPTCHA_V3:
            params.update({
                "method": "userrecaptcha",
                "version": "v3",
                "googlekey": sitekey,
                "pageurl": page_url,
                "action": kwargs.get("action", "verify"),
                "min_score": kwargs.get("min_score", 0.3),
            })
        elif captcha_type == CaptchaType.HCAPTCHA:
            params.update({
                "method": "hcaptcha",
                "sitekey": sitekey,
                "pageurl": page_url,
            })
        elif captcha_type == CaptchaType.TURNSTILE:
            params.update({
                "method": "turnstile",
                "sitekey": sitekey,
                "pageurl": page_url,
            })
        else:
            raise ValueError(f"Unsupported captcha type: {captcha_type}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.API_BASE}/in.php",
                data=params,
            ) as resp:
                data = await resp.json()

        if data.get("status") != 1:
            raise Exception(f"2Captcha submit error: {data.get('error_text', data)}")

        return data["request"]

    async def _get_result(self, task_id: str) -> SolveResult:
        """Get result from 2Captcha."""
        try:
            import aiohttp
        except ImportError:
            raise ImportError("aiohttp required for 2Captcha: pip install aiohttp")

        params = {
            "key": self.api_key,
            "action": "get",
            "id": task_id,
            "json": 1,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.API_BASE}/res.php",
                params=params,
            ) as resp:
                data = await resp.json()

        if data.get("status") == 1:
            return SolveResult(
                status=SolverStatus.SOLVED,
                captcha_type=CaptchaType.RECAPTCHA_V2,  # Generic, actual type tracked elsewhere
                solution=data["request"],
                task_id=task_id,
                cost=0.003,  # Approximate cost per solve
            )

        error = data.get("request", "Unknown error")
        if error == "CAPCHA_NOT_READY":
            return SolveResult(
                status=SolverStatus.PROCESSING,
                captcha_type=CaptchaType.RECAPTCHA_V2,
                task_id=task_id,
            )

        return SolveResult(
            status=SolverStatus.FAILED,
            captcha_type=CaptchaType.RECAPTCHA_V2,
            task_id=task_id,
            error=error,
        )


class MockCaptchaSolver(BaseCaptchaSolver):
    """
    Mock solver for testing.

    Always returns a fake solution after a configurable delay.
    """

    def __init__(
        self,
        solve_delay: float = 2.0,
        fail_rate: float = 0.0,
    ):
        super().__init__(api_key="mock", timeout_seconds=30, poll_interval=0.5)
        self.solve_delay = solve_delay
        self.fail_rate = fail_rate
        self._task_start_times: Dict[str, float] = {}

    @property
    def service_name(self) -> str:
        return "MockSolver"

    @property
    def supported_types(self) -> list[CaptchaType]:
        return list(CaptchaType)

    async def _submit_task(
        self,
        captcha_type: CaptchaType,
        sitekey: str,
        page_url: str,
        **kwargs,
    ) -> str:
        import uuid
        task_id = str(uuid.uuid4())
        self._task_start_times[task_id] = asyncio.get_event_loop().time()
        return task_id

    async def _get_result(self, task_id: str) -> SolveResult:
        import random

        start_time = self._task_start_times.get(task_id, 0)
        elapsed = asyncio.get_event_loop().time() - start_time

        if elapsed < self.solve_delay:
            return SolveResult(
                status=SolverStatus.PROCESSING,
                captcha_type=CaptchaType.RECAPTCHA_V2,
                task_id=task_id,
            )

        if random.random() < self.fail_rate:
            return SolveResult(
                status=SolverStatus.FAILED,
                captcha_type=CaptchaType.RECAPTCHA_V2,
                task_id=task_id,
                error="Random failure (mock)",
            )

        return SolveResult(
            status=SolverStatus.SOLVED,
            captcha_type=CaptchaType.RECAPTCHA_V2,
            solution="mock-solution-token-" + task_id[:8],
            task_id=task_id,
            cost=0.0,
        )


# Factory function
def get_solver(
    service: str = "2captcha",
    api_key: Optional[str] = None,
    **kwargs,
) -> BaseCaptchaSolver:
    """
    Get a CAPTCHA solver instance.

    Args:
        service: Solver service name (2captcha, mock)
        api_key: API key for the service
        **kwargs: Additional solver options

    Returns:
        Configured solver instance
    """
    service = service.lower()

    if service == "2captcha":
        return TwoCaptchaSolver(api_key=api_key, **kwargs)
    elif service == "mock":
        return MockCaptchaSolver(**kwargs)
    else:
        raise ValueError(f"Unknown solver service: {service}")
