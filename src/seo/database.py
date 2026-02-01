# src/seo/database.py
import sqlite3
from typing import Optional

from src.seo.config import settings

class MetricsDatabase:
    """Handles database operations for storing and retrieving SEO metrics."""

    def __init__(self, db_url: Optional[str] = None):
        """
        Initializes the database connection and creates the schema if it doesn't exist.

        Args:
            db_url: The database connection URL. Defaults to the one in settings.
        """
        self.db_url = db_url or settings.DATABASE_URL
        # For SQLite, the db_url is typically 'sqlite:///path/to/database.db'
        # We need to extract the actual path for the connect function.
        db_path = self.db_url.replace("sqlite:///", "")
        
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_schema()

    def get_snapshots_for_domain(self, domain: str) -> list[dict]:
        """
        Retrieves all SEO metrics snapshots for a given domain, ordered by crawl date.

        Args:
            domain: The domain for which to retrieve snapshots.

        Returns:
            A list of dictionaries, where each dictionary represents a snapshot.
        """
        query_sql = "SELECT * FROM seo_metrics_snapshots WHERE domain = ? ORDER BY crawl_date ASC"
        cursor = self.conn.cursor()
        cursor.execute(query_sql, (domain,))
        return [dict(row) for row in cursor.fetchall()]

    def save_snapshot(self, metrics: dict):
        """
        Saves a snapshot of SEO metrics to the database.

        Args:
            metrics: A dictionary containing the SEO metrics to save.
                     Keys should match the column names in the table.
        """
        if 'domain' not in metrics or 'crawl_date' not in metrics:
            raise ValueError("The 'domain' and 'crawl_date' fields are required in metrics.")

        # Filter out any keys in the metrics dict that are not columns in the table
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(seo_metrics_snapshots);")
        table_columns = {row['name'] for row in cursor.fetchall()}
        
        valid_metrics = {k: v for k, v in metrics.items() if k in table_columns}
        
        columns = ', '.join(valid_metrics.keys())
        placeholders = ', '.join('?' for _ in valid_metrics)
        
        insert_sql = f"INSERT INTO seo_metrics_snapshots ({columns}) VALUES ({placeholders})"
        
        with self.conn:
            self.conn.execute(insert_sql, tuple(valid_metrics.values()))

    def create_schema(self):
        """
        Creates the necessary database table(s) if they don't already exist.
        The schema is adapted for SQLite from the SEO_TRACKING_GUIDE.
        """
        create_table_sql = """
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
        with self.conn:
            self.conn.execute(create_table_sql)

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()

