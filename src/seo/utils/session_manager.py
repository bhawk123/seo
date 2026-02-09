"""
Session persistence for browser-based crawling.

Addresses Critical Gap #5: Session persistence - maintaining login state across crawls.

This module provides utilities for saving and restoring browser session state
including cookies, localStorage, and sessionStorage.

Usage:
    from seo.utils.session_manager import SessionManager

    # Save session after login
    session_mgr = SessionManager(storage_dir="~/.seo/sessions")
    await session_mgr.save_session(page, "example.com")

    # Restore session on next crawl
    await session_mgr.restore_session(context, "example.com")
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """Stored session data for a domain."""

    domain: str
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    login_url: Optional[str] = None
    user_agent: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def is_expired(self, ttl_hours: int = 24) -> bool:
        """Check if session has expired."""
        if self.expires_at:
            return datetime.now() > self.expires_at
        if self.created_at:
            expiry = self.created_at + timedelta(hours=ttl_hours)
            return datetime.now() > expiry
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "domain": self.domain,
            "cookies": self.cookies,
            "local_storage": self.local_storage,
            "session_storage": self.session_storage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "login_url": self.login_url,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Deserialize from dictionary."""
        created_at = None
        expires_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])

        return cls(
            domain=data["domain"],
            cookies=data.get("cookies", []),
            local_storage=data.get("local_storage", {}),
            session_storage=data.get("session_storage", {}),
            created_at=created_at,
            expires_at=expires_at,
            login_url=data.get("login_url"),
            user_agent=data.get("user_agent"),
        )


class SessionManager:
    """
    Manages browser session persistence across crawls.

    Features:
    - Save cookies, localStorage, and sessionStorage
    - Restore sessions on new browser contexts
    - TTL-based session expiration
    - Domain-specific session isolation
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        ttl_hours: int = 24,
        encrypt: bool = False,
    ):
        """
        Initialize session manager.

        Args:
            storage_dir: Directory to store sessions (default: ~/.seo/sessions)
            ttl_hours: Session TTL in hours (default: 24)
            encrypt: Whether to encrypt stored sessions (future feature)
        """
        self.storage_dir = Path(storage_dir or Path.home() / ".seo" / "sessions")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        self.encrypt = encrypt

        logger.info(f"SessionManager initialized with storage at {self.storage_dir}")

    def _get_session_path(self, domain: str) -> Path:
        """Get file path for a domain's session."""
        # Sanitize domain for filename
        safe_domain = domain.replace(":", "_").replace("/", "_").replace(".", "_")
        return self.storage_dir / f"{safe_domain}.json"

    async def save_session(
        self,
        page,
        domain: str,
        login_url: Optional[str] = None,
    ) -> SessionData:
        """
        Save current page session state.

        Args:
            page: Playwright Page instance
            domain: Domain identifier for session storage
            login_url: URL where login was performed (for reference)

        Returns:
            SessionData that was saved
        """
        # Get cookies from browser context
        context = page.context
        cookies = await context.cookies()

        # Get localStorage and sessionStorage via page evaluation
        storage_data = await page.evaluate("""
            () => {
                const local = {};
                const session = {};

                try {
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        local[key] = localStorage.getItem(key);
                    }
                } catch (e) {}

                try {
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        session[key] = sessionStorage.getItem(key);
                    }
                } catch (e) {}

                return { local, session };
            }
        """)

        # Create session data
        session = SessionData(
            domain=domain,
            cookies=cookies,
            local_storage=storage_data.get("local", {}),
            session_storage=storage_data.get("session", {}),
            login_url=login_url,
            user_agent=await page.evaluate("() => navigator.userAgent"),
        )

        # Save to file
        session_path = self._get_session_path(domain)
        with open(session_path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

        logger.info(
            f"Session saved for {domain}: {len(cookies)} cookies, "
            f"{len(session.local_storage)} localStorage items"
        )

        return session

    async def restore_session(
        self,
        context,
        domain: str,
        page=None,
    ) -> bool:
        """
        Restore a saved session to a browser context.

        Args:
            context: Playwright BrowserContext instance
            domain: Domain identifier
            page: Optional Page instance (for localStorage/sessionStorage)

        Returns:
            True if session was restored, False if no valid session found
        """
        session_path = self._get_session_path(domain)

        if not session_path.exists():
            logger.debug(f"No saved session found for {domain}")
            return False

        try:
            with open(session_path) as f:
                data = json.load(f)
            session = SessionData.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load session for {domain}: {e}")
            return False

        # Check expiration
        if session.is_expired(self.ttl_hours):
            logger.info(f"Session for {domain} has expired, not restoring")
            session_path.unlink(missing_ok=True)
            return False

        # Restore cookies
        if session.cookies:
            await context.add_cookies(session.cookies)
            logger.debug(f"Restored {len(session.cookies)} cookies for {domain}")

        # Restore localStorage and sessionStorage (requires page)
        if page and (session.local_storage or session.session_storage):
            await page.evaluate(
                """
                ([local, session]) => {
                    try {
                        for (const [key, value] of Object.entries(local)) {
                            localStorage.setItem(key, value);
                        }
                    } catch (e) {}

                    try {
                        for (const [key, value] of Object.entries(session)) {
                            sessionStorage.setItem(key, value);
                        }
                    } catch (e) {}
                }
                """,
                [session.local_storage, session.session_storage],
            )
            logger.debug(
                f"Restored {len(session.local_storage)} localStorage, "
                f"{len(session.session_storage)} sessionStorage items"
            )

        logger.info(f"Session restored for {domain}")
        return True

    def has_session(self, domain: str) -> bool:
        """Check if a valid session exists for domain."""
        session_path = self._get_session_path(domain)
        if not session_path.exists():
            return False

        try:
            with open(session_path) as f:
                data = json.load(f)
            session = SessionData.from_dict(data)
            return not session.is_expired(self.ttl_hours)
        except Exception:
            return False

    def delete_session(self, domain: str) -> bool:
        """Delete a saved session."""
        session_path = self._get_session_path(domain)
        if session_path.exists():
            session_path.unlink()
            logger.info(f"Session deleted for {domain}")
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions with their status."""
        sessions = []
        for path in self.storage_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                session = SessionData.from_dict(data)
                sessions.append({
                    "domain": session.domain,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "expired": session.is_expired(self.ttl_hours),
                    "cookie_count": len(session.cookies),
                    "local_storage_count": len(session.local_storage),
                })
            except Exception as e:
                logger.warning(f"Failed to read session {path}: {e}")

        return sessions

    def clear_expired(self) -> int:
        """Clear all expired sessions. Returns count of deleted sessions."""
        deleted = 0
        for path in self.storage_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                session = SessionData.from_dict(data)
                if session.is_expired(self.ttl_hours):
                    path.unlink()
                    deleted += 1
                    logger.debug(f"Deleted expired session: {session.domain}")
            except Exception as e:
                logger.warning(f"Failed to check session {path}: {e}")

        if deleted > 0:
            logger.info(f"Cleared {deleted} expired sessions")
        return deleted
