# tests/test_database.py
import os
import pytest
import sqlite3
from src.seo.database import MetricsDatabase

# Define a test database path
TEST_DB_PATH = "test_seo_data.db"

@pytest.fixture
def test_db():
    """Pytest fixture to set up and tear down a test database."""
    # Ensure the old test DB is removed before a run
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Setup: Create a MetricsDatabase instance for the test
    db = MetricsDatabase(db_url=f"sqlite:///{TEST_DB_PATH}")
    yield db
    
    # Teardown: Close connection and remove the database file
    db.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_get_snapshots_for_domain(test_db):
    """Tests if snapshots for a domain can be retrieved correctly and are ordered."""
    from datetime import datetime, timedelta

    domain_name = "testdomain.com"
    
    # Save multiple snapshots
    snapshot1 = {
        "domain": domain_name,
        "crawl_date": datetime.now() - timedelta(days=2),
        "technical_score": 70
    }
    snapshot2 = {
        "domain": domain_name,
        "crawl_date": datetime.now() - timedelta(days=1),
        "technical_score": 80
    }
    snapshot3 = {
        "domain": domain_name,
        "crawl_date": datetime.now(),
        "technical_score": 90
    }
    
    test_db.save_snapshot(snapshot1)
    test_db.save_snapshot(snapshot2)
    test_db.save_snapshot(snapshot3)

    # Save a snapshot for a different domain
    test_db.save_snapshot({
        "domain": "otherdomain.com",
        "crawl_date": datetime.now(),
        "technical_score": 50
    })

    snapshots = test_db.get_snapshots_for_domain(domain_name)

    assert len(snapshots) == 3
    assert snapshots[0]['technical_score'] == 70
    assert snapshots[1]['technical_score'] == 80
    assert snapshots[2]['technical_score'] == 90
    assert snapshots[0]['domain'] == domain_name

def test_save_and_retrieve_snapshot(test_db):
    """Tests if a metrics snapshot can be saved and then retrieved."""
    from datetime import datetime

    metrics_data = {
        "domain": "example.com",
        "crawl_date": datetime.now(),
        "technical_score": 85,
        "total_issues": 10,
        "organic_sessions": 1200,
        "avg_position": 25.5,
        "non_existent_column": "should_be_ignored" # To test robustness
    }
    
    test_db.save_snapshot(metrics_data)

    # Now, try to retrieve the data to verify it was saved correctly
    cursor = test_db.conn.cursor()
    cursor.execute("SELECT * FROM seo_metrics_snapshots WHERE domain = ?", ("example.com",))
    snapshot = cursor.fetchone()

    assert snapshot is not None
    assert snapshot['domain'] == "example.com"
    assert snapshot['technical_score'] == 85
    assert snapshot['organic_sessions'] == 1200
    assert snapshot['avg_position'] == 25.5

def test_database_creation(test_db):
    """Tests if the database file is created."""
    assert os.path.exists(TEST_DB_PATH)

def test_schema_creation(test_db):
    """Tests if the 'seo_metrics_snapshots' table is created correctly."""
    # Check if the table exists in the database
    cursor = test_db.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='seo_metrics_snapshots';")
    table = cursor.fetchone()
    assert table is not None, "The 'seo_metrics_snapshots' table was not created."
    assert table['name'] == 'seo_metrics_snapshots'

    # Check if a few key columns exist in the table
    cursor.execute("PRAGMA table_info(seo_metrics_snapshots);")
    columns = {row['name'] for row in cursor.fetchall()}
    
    assert 'id' in columns
    assert 'domain' in columns
    assert 'crawl_date' in columns
    assert 'technical_score' in columns
    assert 'gsc_clicks' in columns
    assert 'total_backlinks' in columns

