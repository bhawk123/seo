"""
Utilities Package.

Ported from Spectrum per EPIC-SEO-INFRA-001.

Provides utility functions for CAPTCHA detection, human intervention,
and human-like interaction simulation.
"""

from .challenge_handler import (
    detect_challenge,
    is_challenge_page,
    pause_for_human,
    handle_challenge_if_present,
    get_challenge_instructions,
    CHALLENGE_INDICATORS,
    CHALLENGE_URL_PATTERNS,
    # Epic 9.2.2: Enhanced reCAPTCHA detection
    RecaptchaDetectionResult,
    detect_recaptcha,
    # Epic 9.2.3: reCAPTCHA blocking check
    BlockingCheckResult,
    check_recaptcha_blocking,
    check_recaptcha_blocking_async,
    # Evidence capture for reCAPTCHA (Gemini Recommendation)
    create_recaptcha_evidence,
    create_blocking_evidence,
)

from .human_simulator import (
    HumanSimulator,
    HumanSimulatorConfig,
    create_human_simulator,
    create_human_simulator_from_thresholds,
)

# Session persistence (Critical Gap #5)
from .session_manager import (
    SessionManager,
    SessionData,
)

# CAPTCHA solver integration (Critical Gap #1)
from .captcha_solver import (
    BaseCaptchaSolver,
    TwoCaptchaSolver,
    MockCaptchaSolver,
    CaptchaType,
    SolverStatus,
    SolveResult,
    get_solver,
)

__all__ = [
    # Challenge handling
    "detect_challenge",
    "is_challenge_page",
    "pause_for_human",
    "handle_challenge_if_present",
    "get_challenge_instructions",
    "CHALLENGE_INDICATORS",
    "CHALLENGE_URL_PATTERNS",
    # Enhanced reCAPTCHA detection (Epic 9.2.2)
    "RecaptchaDetectionResult",
    "detect_recaptcha",
    # reCAPTCHA blocking check (Epic 9.2.3)
    "BlockingCheckResult",
    "check_recaptcha_blocking",
    "check_recaptcha_blocking_async",
    # Evidence capture for reCAPTCHA (Gemini Recommendation)
    "create_recaptcha_evidence",
    "create_blocking_evidence",
    # Human-like simulation (Epic 9.2.4)
    "HumanSimulator",
    "HumanSimulatorConfig",
    "create_human_simulator",
    "create_human_simulator_from_thresholds",
    # Session persistence (Critical Gap #5)
    "SessionManager",
    "SessionData",
    # CAPTCHA solver integration (Critical Gap #1)
    "BaseCaptchaSolver",
    "TwoCaptchaSolver",
    "MockCaptchaSolver",
    "CaptchaType",
    "SolverStatus",
    "SolveResult",
    "get_solver",
]
