"""
Content-Addressable AI Response Cache.

Ported from Spectrum per EPIC-SEO-INFRA-001 (STORY-INFRA-005).

This module provides caching for AI/LLM responses to reduce API costs
and improve performance. Uses SQLite for the index and individual JSON
files for response storage.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import hashlib
import json
import sqlite3
import threading


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""
    key: str
    prompt_hash: str
    response: dict[str, Any]
    model: str
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
    last_hit: datetime | None = None

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return datetime.now() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "prompt_hash": self.prompt_hash,
            "response": self.response,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "hit_count": self.hit_count,
            "last_hit": self.last_hit.isoformat() if self.last_hit else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Deserialize from dictionary."""
        return cls(
            key=data["key"],
            prompt_hash=data["prompt_hash"],
            response=data["response"],
            model=data["model"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            hit_count=data.get("hit_count", 0),
            last_hit=datetime.fromisoformat(data["last_hit"]) if data.get("last_hit") else None,
        )


class AICache:
    """
    Content-addressable cache for AI responses.

    Uses SQLite for metadata index (scalable to millions of entries)
    and individual JSON files for response storage.
    """

    # SQL schema for cache index
    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS cache_entries (
        key TEXT PRIMARY KEY,
        prompt_hash TEXT NOT NULL,
        model TEXT NOT NULL,
        response_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        hit_count INTEGER DEFAULT 0,
        last_hit TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_expires_at ON cache_entries(expires_at);
    CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at);
    CREATE INDEX IF NOT EXISTS idx_prompt_hash ON cache_entries(prompt_hash);
    """

    def __init__(
        self,
        cache_dir: Path,
        ttl_hours: int = 24,
        max_size_mb: int = 100,
        enabled: bool = True,
    ):
        """
        Initialize the AI cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Time-to-live for cache entries in hours
            max_size_mb: Maximum cache size in megabytes
            enabled: Whether caching is enabled
        """
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.max_size_mb = max_size_mb
        self.enabled = enabled
        self._db_path = cache_dir / "cache_index.db"
        self._responses_dir = cache_dir / "responses"
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

        if enabled:
            self._ensure_cache_dir()
            self._init_db()

    def _ensure_cache_dir(self) -> None:
        """Create cache directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._responses_dir.mkdir(exist_ok=True)

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()
        # Clean expired on startup
        self._clean_expired()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection, initializing if needed."""
        if self._conn is None:
            self._init_db()
        return self._conn  # type: ignore

    def _compute_key(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """
        Compute a content-addressable key from prompt and context.
        """
        content = prompt
        if context:
            content += json.dumps(context, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _compute_prompt_hash(self, prompt: str) -> str:
        """Compute hash of just the prompt for similarity detection."""
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def _get_response_path(self, key: str) -> Path:
        """Get the file path for storing a response."""
        # Use first 2 chars as subdirectory to avoid too many files in one dir
        subdir = key[:2]
        return self._responses_dir / subdir / f"{key}.json"

    def get(self, prompt: str, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """
        Retrieve a cached response if available and not expired.

        Args:
            prompt: The AI prompt
            context: Additional context that affects the response

        Returns:
            Cached response dict or None if not found/expired
        """
        if not self.enabled:
            return None

        key = self._compute_key(prompt, context)

        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT * FROM cache_entries WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                # Expired - remove and return None
                self._remove_entry_unlocked(conn, key)
                return None

            # Load response from file
            response_path = Path(row["response_path"])
            if not response_path.exists():
                # File missing - remove entry
                self._remove_entry_unlocked(conn, key)
                return None

            with open(response_path) as f:
                response = json.load(f)

            # Update hit count atomically
            conn.execute(
                """UPDATE cache_entries
                   SET hit_count = hit_count + 1, last_hit = ?
                   WHERE key = ?""",
                (datetime.now().isoformat(), key)
            )
            conn.commit()

            return response

    def put(
        self,
        prompt: str,
        response: dict[str, Any],
        model: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Store an AI response in the cache.

        Args:
            prompt: The AI prompt
            response: The AI response to cache
            model: The model that generated the response
            context: Additional context that affects the response

        Returns:
            The cache key
        """
        if not self.enabled:
            return ""

        key = self._compute_key(prompt, context)
        prompt_hash = self._compute_prompt_hash(prompt)
        response_path = self._get_response_path(key)
        now = datetime.now()
        expires_at = now + timedelta(hours=self.ttl_hours)

        # Store response to file
        response_path.parent.mkdir(parents=True, exist_ok=True)
        with open(response_path, "w") as f:
            json.dump(response, f, indent=2)

        # Store metadata in SQLite
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO cache_entries
                   (key, prompt_hash, model, response_path, created_at, expires_at, hit_count, last_hit)
                   VALUES (?, ?, ?, ?, ?, ?, 0, NULL)""",
                (key, prompt_hash, model, str(response_path), now.isoformat(), expires_at.isoformat())
            )
            conn.commit()

            # Enforce size limit
            self._enforce_size_limit_unlocked(conn)

        return key

    def invalidate(self, prompt: str, context: dict[str, Any] | None = None) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            prompt: The AI prompt
            context: Additional context

        Returns:
            True if entry was found and removed
        """
        key = self._compute_key(prompt, context)
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("SELECT key FROM cache_entries WHERE key = ?", (key,))
            if cursor.fetchone():
                self._remove_entry_unlocked(conn, key)
                return True
        return False

    def _remove_entry_unlocked(self, conn: sqlite3.Connection, key: str) -> None:
        """Remove a cache entry (must hold lock)."""
        # Get response path before deleting
        cursor = conn.execute(
            "SELECT response_path FROM cache_entries WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        if row:
            response_path = Path(row["response_path"])
            if response_path.exists():
                response_path.unlink()

        conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
        conn.commit()

    def _clean_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        if not self.enabled:
            return 0

        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()

            # Get paths of expired entries
            cursor = conn.execute(
                "SELECT key, response_path FROM cache_entries WHERE expires_at < ?",
                (now,)
            )
            expired = cursor.fetchall()

            # Delete files
            for row in expired:
                response_path = Path(row["response_path"])
                if response_path.exists():
                    response_path.unlink()

            # Delete from DB
            conn.execute("DELETE FROM cache_entries WHERE expires_at < ?", (now,))
            conn.commit()

            return len(expired)

    def _get_cache_size_mb(self) -> float:
        """Calculate total cache size in megabytes."""
        total = 0
        if self._responses_dir.exists():
            for path in self._responses_dir.rglob("*.json"):
                total += path.stat().st_size
        # Add DB file size
        if self._db_path.exists():
            total += self._db_path.stat().st_size
        return total / (1024 * 1024)

    def _enforce_size_limit_unlocked(self, conn: sqlite3.Connection) -> None:
        """Evict oldest entries if cache exceeds size limit (must hold lock)."""
        while self._get_cache_size_mb() > self.max_size_mb:
            # Find oldest entry
            cursor = conn.execute(
                "SELECT key FROM cache_entries ORDER BY created_at ASC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                break
            self._remove_entry_unlocked(conn, row["key"])

    def clear(self) -> None:
        """Clear all cache entries."""
        if not self.enabled:
            return

        with self._lock:
            conn = self._get_conn()

            # Get all response paths
            cursor = conn.execute("SELECT response_path FROM cache_entries")
            for row in cursor.fetchall():
                response_path = Path(row["response_path"])
                if response_path.exists():
                    response_path.unlink()

            # Clear DB
            conn.execute("DELETE FROM cache_entries")
            conn.commit()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        if not self.enabled:
            return {"enabled": False}

        with self._lock:
            conn = self._get_conn()

            # Count entries
            cursor = conn.execute("SELECT COUNT(*) as count FROM cache_entries")
            entry_count = cursor.fetchone()["count"]

            # Sum hit counts
            cursor = conn.execute("SELECT SUM(hit_count) as total FROM cache_entries")
            row = cursor.fetchone()
            total_hits = row["total"] if row["total"] else 0

        return {
            "enabled": True,
            "entry_count": entry_count,
            "size_mb": round(self._get_cache_size_mb(), 2),
            "max_size_mb": self.max_size_mb,
            "ttl_hours": self.ttl_hours,
            "total_hits": total_hits,
        }

    def find_similar(self, prompt: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Find cached entries with similar prompts.

        Uses prompt_hash prefix matching for fast similarity lookup.

        Args:
            prompt: The prompt to find similar entries for
            limit: Maximum number of results

        Returns:
            List of similar cache entry metadata
        """
        if not self.enabled:
            return []

        prompt_hash = self._compute_prompt_hash(prompt)
        prefix = prompt_hash[:8]  # Use first 8 chars for prefix match

        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """SELECT key, prompt_hash, model, created_at, hit_count
                   FROM cache_entries
                   WHERE prompt_hash LIKE ?
                   ORDER BY hit_count DESC
                   LIMIT ?""",
                (f"{prefix}%", limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """Cleanup on deletion."""
        self.close()
