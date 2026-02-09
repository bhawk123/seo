"""Unit tests for SessionManager.

Tests the session persistence system addressing Critical Gap #5.
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from seo.utils.session_manager import SessionManager, SessionData


class TestSessionData:
    """Tests for SessionData dataclass."""

    def test_create_session_data(self):
        """Test creating session data."""
        session = SessionData(
            domain="example.com",
            cookies=[{"name": "session_id", "value": "abc123"}],
            local_storage={"user": "test"},
            session_storage={"temp": "data"},
        )

        assert session.domain == "example.com"
        assert len(session.cookies) == 1
        assert session.local_storage["user"] == "test"
        assert session.created_at is not None

    def test_session_not_expired(self):
        """Test session that hasn't expired."""
        session = SessionData(
            domain="example.com",
            created_at=datetime.now(),
        )

        assert not session.is_expired(ttl_hours=24)

    def test_session_expired_by_ttl(self):
        """Test session expired by TTL."""
        session = SessionData(
            domain="example.com",
            created_at=datetime.now() - timedelta(hours=48),
        )

        assert session.is_expired(ttl_hours=24)

    def test_session_expired_by_expires_at(self):
        """Test session expired by explicit expires_at."""
        session = SessionData(
            domain="example.com",
            created_at=datetime.now(),
            expires_at=datetime.now() - timedelta(hours=1),
        )

        assert session.is_expired()

    def test_to_dict(self):
        """Test serialization to dictionary."""
        session = SessionData(
            domain="example.com",
            cookies=[{"name": "test", "value": "123"}],
            local_storage={"key": "value"},
            login_url="https://example.com/login",
        )

        data = session.to_dict()

        assert data["domain"] == "example.com"
        assert len(data["cookies"]) == 1
        assert data["local_storage"]["key"] == "value"
        assert data["login_url"] == "https://example.com/login"
        assert "created_at" in data

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        now = datetime.now()
        data = {
            "domain": "test.com",
            "cookies": [{"name": "auth", "value": "token"}],
            "local_storage": {"setting": "on"},
            "session_storage": {},
            "created_at": now.isoformat(),
            "expires_at": None,
            "login_url": "https://test.com/login",
            "user_agent": "Mozilla/5.0",
        }

        session = SessionData.from_dict(data)

        assert session.domain == "test.com"
        assert len(session.cookies) == 1
        assert session.local_storage["setting"] == "on"
        assert session.user_agent == "Mozilla/5.0"

    def test_from_dict_with_missing_fields(self):
        """Test deserialization handles missing optional fields."""
        data = {
            "domain": "minimal.com",
        }

        session = SessionData.from_dict(data)

        assert session.domain == "minimal.com"
        assert session.cookies == []
        assert session.local_storage == {}


class TestSessionManager:
    """Tests for SessionManager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a session manager for testing."""
        return SessionManager(
            storage_dir=tmp_path / "sessions",
            ttl_hours=24,
        )

    def test_init_creates_directory(self, tmp_path):
        """Test that init creates storage directory."""
        storage_dir = tmp_path / "new_sessions"
        manager = SessionManager(storage_dir=storage_dir)

        assert storage_dir.exists()

    def test_get_session_path(self, manager):
        """Test session path generation."""
        path = manager._get_session_path("example.com")

        assert "example_com" in str(path)
        assert path.suffix == ".json"

    def test_get_session_path_sanitizes_domain(self, manager):
        """Test that domain is sanitized for filename."""
        path = manager._get_session_path("sub.example.com:8080")

        # Should not contain invalid filename characters
        assert ":" not in path.name
        assert "/" not in path.name

    @pytest.mark.asyncio
    async def test_save_session(self, manager, tmp_path):
        """Test saving a session."""
        # Mock page and context
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_page.context = mock_context

        # Mock cookies
        mock_context.cookies = AsyncMock(return_value=[
            {"name": "session", "value": "abc123", "domain": "example.com"}
        ])

        # Mock page.evaluate for storage and user agent
        mock_page.evaluate = AsyncMock(side_effect=[
            {"local": {"user_id": "123"}, "session": {"temp": "data"}},
            "Mozilla/5.0 Test Browser",
        ])

        session = await manager.save_session(
            mock_page,
            domain="example.com",
            login_url="https://example.com/login",
        )

        assert session.domain == "example.com"
        assert len(session.cookies) == 1
        assert session.local_storage["user_id"] == "123"
        assert session.login_url == "https://example.com/login"

        # Verify file was created
        session_path = manager._get_session_path("example.com")
        assert session_path.exists()

    @pytest.mark.asyncio
    async def test_restore_session_no_saved_session(self, manager):
        """Test restore returns False when no session exists."""
        mock_context = AsyncMock()

        result = await manager.restore_session(mock_context, "nonexistent.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_session_success(self, manager):
        """Test restoring a saved session."""
        # Create a session file manually
        session_data = SessionData(
            domain="example.com",
            cookies=[{"name": "auth", "value": "token123", "domain": "example.com"}],
            local_storage={"user": "test"},
            created_at=datetime.now(),
        )

        session_path = manager._get_session_path("example.com")
        with open(session_path, "w") as f:
            json.dump(session_data.to_dict(), f)

        # Mock context
        mock_context = AsyncMock()
        mock_context.add_cookies = AsyncMock()

        result = await manager.restore_session(mock_context, "example.com")

        assert result is True
        mock_context.add_cookies.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_session_with_page(self, manager):
        """Test restoring session including localStorage."""
        # Create a session file
        session_data = SessionData(
            domain="example.com",
            cookies=[],
            local_storage={"key": "value"},
            session_storage={"temp": "data"},
            created_at=datetime.now(),
        )

        session_path = manager._get_session_path("example.com")
        with open(session_path, "w") as f:
            json.dump(session_data.to_dict(), f)

        # Mock context and page
        mock_context = AsyncMock()
        mock_context.add_cookies = AsyncMock()
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock()

        result = await manager.restore_session(
            mock_context, "example.com", page=mock_page
        )

        assert result is True
        mock_page.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_expired_session(self, manager):
        """Test that expired sessions are not restored."""
        # Create an expired session
        session_data = SessionData(
            domain="example.com",
            cookies=[{"name": "old", "value": "session"}],
            created_at=datetime.now() - timedelta(hours=48),
        )

        session_path = manager._get_session_path("example.com")
        with open(session_path, "w") as f:
            json.dump(session_data.to_dict(), f)

        mock_context = AsyncMock()

        result = await manager.restore_session(mock_context, "example.com")

        assert result is False
        # Session file should be deleted
        assert not session_path.exists()

    def test_has_session_true(self, manager):
        """Test has_session returns True for valid session."""
        session_data = SessionData(
            domain="example.com",
            created_at=datetime.now(),
        )

        session_path = manager._get_session_path("example.com")
        with open(session_path, "w") as f:
            json.dump(session_data.to_dict(), f)

        assert manager.has_session("example.com") is True

    def test_has_session_false_no_file(self, manager):
        """Test has_session returns False when no file exists."""
        assert manager.has_session("nonexistent.com") is False

    def test_has_session_false_expired(self, manager):
        """Test has_session returns False for expired session."""
        session_data = SessionData(
            domain="example.com",
            created_at=datetime.now() - timedelta(hours=48),
        )

        session_path = manager._get_session_path("example.com")
        with open(session_path, "w") as f:
            json.dump(session_data.to_dict(), f)

        assert manager.has_session("example.com") is False

    def test_delete_session(self, manager):
        """Test deleting a session."""
        # Create a session file
        session_path = manager._get_session_path("example.com")
        session_path.write_text("{}")

        result = manager.delete_session("example.com")

        assert result is True
        assert not session_path.exists()

    def test_delete_session_not_found(self, manager):
        """Test deleting non-existent session returns False."""
        result = manager.delete_session("nonexistent.com")

        assert result is False

    def test_list_sessions(self, manager):
        """Test listing all sessions."""
        # Create multiple session files
        for domain in ["site1.com", "site2.com"]:
            session_data = SessionData(
                domain=domain,
                cookies=[{"name": "test", "value": "123"}],
                created_at=datetime.now(),
            )
            session_path = manager._get_session_path(domain)
            with open(session_path, "w") as f:
                json.dump(session_data.to_dict(), f)

        sessions = manager.list_sessions()

        assert len(sessions) == 2
        domains = [s["domain"] for s in sessions]
        assert "site1.com" in domains
        assert "site2.com" in domains

    def test_clear_expired(self, manager):
        """Test clearing expired sessions."""
        # Create an expired session
        expired_session = SessionData(
            domain="expired.com",
            created_at=datetime.now() - timedelta(hours=48),
        )
        expired_path = manager._get_session_path("expired.com")
        with open(expired_path, "w") as f:
            json.dump(expired_session.to_dict(), f)

        # Create a valid session
        valid_session = SessionData(
            domain="valid.com",
            created_at=datetime.now(),
        )
        valid_path = manager._get_session_path("valid.com")
        with open(valid_path, "w") as f:
            json.dump(valid_session.to_dict(), f)

        deleted = manager.clear_expired()

        assert deleted == 1
        assert not expired_path.exists()
        assert valid_path.exists()
