# src/seo/database.py
"""Database abstraction layer supporting local SQLite and remote Turso backends."""

import sqlite3
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import logging

from seo.config import settings

logger = logging.getLogger(__name__)

# SQL schema shared between backends
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS seo_metrics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    crawl_date TIMESTAMP NOT NULL,

    -- Technical Health
    technical_score INTEGER,
    total_issues INTEGER,
    critical_issues INTEGER,
    high_issues INTEGER,
    medium_issues INTEGER,
    low_issues INTEGER,

    -- Content
    avg_readability_score REAL,
    avg_word_count INTEGER,
    thin_content_count INTEGER,

    -- Performance
    avg_load_time REAL,
    lcp_score REAL,
    fid_score INTEGER,
    cls_score REAL,

    -- Indexability
    crawlable_pages INTEGER,
    indexed_pages INTEGER,
    noindex_pages INTEGER,

    -- Organic Traffic (from GA4)
    organic_sessions INTEGER,
    organic_users INTEGER,
    bounce_rate REAL,
    conversion_rate REAL,

    -- Rankings (from rank tracking tool)
    keywords_top_10 INTEGER,
    keywords_top_50 INTEGER,
    avg_position REAL,

    -- Backlinks (from Ahrefs/SEMrush API)
    total_backlinks INTEGER,
    referring_domains INTEGER,
    domain_rating INTEGER,

    -- Search Console
    gsc_impressions INTEGER,
    gsc_clicks INTEGER,
    gsc_ctr REAL,
    gsc_avg_position REAL,

    UNIQUE(domain, crawl_date)
);
"""


class AbstractDatabase(ABC):
    """Abstract base class defining the database interface."""

    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    def create_schema(self) -> None:
        """Create the necessary database tables."""
        pass

    @abstractmethod
    def save_snapshot(self, metrics: Dict[str, Any]) -> None:
        """Save a snapshot of SEO metrics to the database.

        Args:
            metrics: Dictionary containing SEO metrics. Must include 'domain' and 'crawl_date'.
        """
        pass

    @abstractmethod
    def get_snapshots_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve all snapshots for a given domain.

        Args:
            domain: The domain to query.

        Returns:
            List of snapshot dictionaries ordered by crawl_date ascending.
        """
        pass

    @abstractmethod
    def get_table_columns(self) -> set:
        """Get the set of column names in the snapshots table.

        Returns:
            Set of column name strings.
        """
        pass


class LocalSqliteDatabase(AbstractDatabase):
    """SQLite database implementation for local storage."""

    def __init__(self, db_url: Optional[str] = None):
        """Initialize local SQLite database.

        Args:
            db_url: Database URL (sqlite:///path/to/db.db). Defaults to settings.DATABASE_URL.
        """
        self.db_url = db_url or settings.DATABASE_URL
        self.db_path = self.db_url.replace("sqlite:///", "")
        self.conn: Optional[sqlite3.Connection] = None
        self.connect()
        self.create_schema()

    def connect(self) -> None:
        """Establish SQLite connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.debug(f"Connected to local SQLite database: {self.db_path}")

    def close(self) -> None:
        """Close SQLite connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Closed local SQLite connection")

    def create_schema(self) -> None:
        """Create the snapshots table if it doesn't exist."""
        with self.conn:
            self.conn.execute(CREATE_TABLE_SQL)
        logger.debug("Schema verified/created for local SQLite")

    def get_table_columns(self) -> set:
        """Get column names from the snapshots table."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(seo_metrics_snapshots);")
        return {row['name'] for row in cursor.fetchall()}

    def save_snapshot(self, metrics: Dict[str, Any]) -> None:
        """Save metrics snapshot to SQLite."""
        if 'domain' not in metrics or 'crawl_date' not in metrics:
            raise ValueError("The 'domain' and 'crawl_date' fields are required.")

        table_columns = self.get_table_columns()
        valid_metrics = {k: v for k, v in metrics.items() if k in table_columns}

        columns = ', '.join(valid_metrics.keys())
        placeholders = ', '.join('?' for _ in valid_metrics)
        insert_sql = f"INSERT INTO seo_metrics_snapshots ({columns}) VALUES ({placeholders})"

        with self.conn:
            self.conn.execute(insert_sql, tuple(valid_metrics.values()))
        logger.debug(f"Saved snapshot for domain: {metrics['domain']}")

    def get_snapshots_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve snapshots for a domain from SQLite."""
        query_sql = "SELECT * FROM seo_metrics_snapshots WHERE domain = ? ORDER BY crawl_date ASC"
        cursor = self.conn.cursor()
        cursor.execute(query_sql, (domain,))
        return [dict(row) for row in cursor.fetchall()]


class TursoDatabase(AbstractDatabase):
    """Turso (libSQL) database implementation for remote storage."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        auth_token: Optional[str] = None,
    ):
        """Initialize Turso database connection.

        Args:
            database_url: Turso database URL (libsql://...). Defaults to settings.TURSO_DATABASE_URL.
            auth_token: Turso auth token. Defaults to settings.TURSO_AUTH_TOKEN.
        """
        self.database_url = database_url or settings.TURSO_DATABASE_URL
        self.auth_token = auth_token or settings.TURSO_AUTH_TOKEN
        self.client = None
        self._table_columns: Optional[set] = None

        if not self.database_url:
            raise ValueError("TURSO_DATABASE_URL is required for Turso backend")
        if not self.auth_token:
            raise ValueError("TURSO_AUTH_TOKEN is required for Turso backend")

        self.connect()
        self.create_schema()

    def connect(self) -> None:
        """Establish Turso connection using libsql-client."""
        try:
            import libsql_client
            self.client = libsql_client.create_client_sync(
                url=self.database_url,
                auth_token=self.auth_token,
            )
            logger.info(f"Connected to Turso database: {self.database_url}")
        except ImportError:
            raise ImportError(
                "libsql-client is required for Turso backend. "
                "Install it with: poetry add libsql-client"
            )

    def close(self) -> None:
        """Close Turso connection."""
        if self.client:
            self.client.close()
            self.client = None
            logger.debug("Closed Turso connection")

    def create_schema(self) -> None:
        """Create the snapshots table in Turso if it doesn't exist."""
        self.client.execute(CREATE_TABLE_SQL)
        logger.debug("Schema verified/created for Turso database")

    def get_table_columns(self) -> set:
        """Get column names from the Turso snapshots table."""
        if self._table_columns is None:
            result = self.client.execute("PRAGMA table_info(seo_metrics_snapshots);")
            self._table_columns = {row['name'] for row in result.rows}
        return self._table_columns

    def save_snapshot(self, metrics: Dict[str, Any]) -> None:
        """Save metrics snapshot to Turso."""
        if 'domain' not in metrics or 'crawl_date' not in metrics:
            raise ValueError("The 'domain' and 'crawl_date' fields are required.")

        table_columns = self.get_table_columns()
        valid_metrics = {k: v for k, v in metrics.items() if k in table_columns}

        columns = ', '.join(valid_metrics.keys())
        placeholders = ', '.join('?' for _ in valid_metrics)
        insert_sql = f"INSERT INTO seo_metrics_snapshots ({columns}) VALUES ({placeholders})"

        # Convert datetime to string for Turso
        values = []
        for v in valid_metrics.values():
            if hasattr(v, 'isoformat'):
                values.append(v.isoformat())
            else:
                values.append(v)

        self.client.execute(insert_sql, values)
        logger.debug(f"Saved snapshot to Turso for domain: {metrics['domain']}")

    def get_snapshots_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve snapshots for a domain from Turso."""
        query_sql = "SELECT * FROM seo_metrics_snapshots WHERE domain = ? ORDER BY crawl_date ASC"
        result = self.client.execute(query_sql, [domain])
        return [dict(row) for row in result.rows]


def get_db_client(
    backend: Optional[str] = None,
    **kwargs,
) -> AbstractDatabase:
    """Factory function to create the appropriate database client.

    Args:
        backend: Database backend ('local' or 'turso'). Defaults to settings.DB_BACKEND.
        **kwargs: Additional arguments passed to the database constructor.

    Returns:
        An instance of AbstractDatabase (either LocalSqliteDatabase or TursoDatabase).

    Raises:
        ValueError: If an unknown backend is specified.
    """
    backend = backend or settings.DB_BACKEND

    if backend == "local":
        logger.info("Using local SQLite database backend")
        return LocalSqliteDatabase(**kwargs)
    elif backend == "turso":
        logger.info("Using Turso database backend")
        return TursoDatabase(**kwargs)
    else:
        raise ValueError(
            f"Unknown database backend: '{backend}'. "
            "Supported backends: 'local', 'turso'"
        )


# Backwards compatibility alias
class MetricsDatabase(LocalSqliteDatabase):
    """Alias for LocalSqliteDatabase for backwards compatibility.

    Deprecated: Use get_db_client() factory function instead.
    """
    pass
