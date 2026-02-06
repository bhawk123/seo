# Proposal: Optional Turso DB Integration

## 1. Executive Summary

This document proposes an enhancement to the SEO Analyzer's persistence layer to support both the existing local SQLite database and a remote Turso database. This change will be driven by a new configuration setting, allowing users to seamlessly switch between a simple, local file-based database and a powerful, distributed database for larger-scale use.

The core of this proposal is to refactor `src/seo/database.py` to use a factory pattern that selects the appropriate database client (`sqlite3` for local, `turso-python` for remote) based on the application's configuration.

---

## 2. Proposed Changes

### Step 1: Configuration Update (`config.py` and `.env.example`)

We will introduce new environment variables to manage the database backend selection.

**New Environment Variables:**

-   `DB_BACKEND`: Specifies the database backend.
    -   `local` (Default): Uses the existing SQLite file setup.
    -   `turso`: Uses the remote Turso database.
-   `TURSO_DATABASE_URL`: The connection URL for the Turso database (e.g., `libsql://your-db-name.turso.io`).
-   `TURSO_AUTH_TOKEN`: The authentication token for accessing the Turso database.

The `config.py` module will be updated to read these new variables.

### Step 2: Dependency Management (`pyproject.toml`)

The official `turso-python` SDK will be added to the project's dependencies.

```bash
poetry add turso-python
```

### Step 3: Refactor `database.py`

The existing `MetricsDatabase` class will be refactored into a more flexible, multi-backend architecture.

1.  **Abstract Base Class:** An abstract base class, `AbstractDatabase`, will define the required interface (`connect`, `close`, `save_snapshot`, `get_snapshots_by_domain`, etc.).

2.  **Local Database Implementation:** A `LocalSqliteDatabase` class will be created, inheriting from `AbstractDatabase`. It will contain the existing logic that uses Python's built-in `sqlite3` module to connect to a local file.

3.  **Turso Database Implementation:** A `TursoDatabase` class will be created, also inheriting from `AbstractDatabase`. It will implement the same interface but use the `turso-python` SDK to connect to and interact with the remote database. The core SQL queries will remain the same.

4.  **Database Factory:** A factory function, `get_db_client(config)`, will be created. This function will read the `DB_BACKEND` setting from the configuration and return an instance of either `LocalSqliteDatabase` or `TursoDatabase`.

### Step 4: Update Analyzer (`analyzer.py`)

The `_save_metrics_snapshot` method in `src/seo/analyzer.py` will be modified. Instead of directly instantiating `MetricsDatabase`, it will now use the new factory function `get_db_client(config)` to obtain the correct database client instance. This ensures the rest of the application remains decoupled from the specific database implementation.

---

## 3. Example Configuration

### Local Database (Default)

File: `.env`

```
# .env for local SQLite
DB_BACKEND=local
DATABASE_URL=sqlite:///seo.db
```

### Remote Turso Database

File: `.env`

```
# .env for remote Turso DB
DB_BACKEND=turso
TURSO_DATABASE_URL="libsql://your-db-name.turso.io"
TURSO_AUTH_TOKEN="your-super-secret-token"
```

---

## 4. BDD Feature for Validation

To ensure the implementation is correct, a new BDD feature should be created.

**Feature:** Database Backend Selection

  **Scenario 1:** Saving data to the local database
    Given the environment variable `DB_BACKEND` is set to "local"
    And the `DATABASE_URL` is set to "sqlite:///test.db"
    When the SEO analyzer is run and saves a metrics snapshot
    Then the snapshot data should exist in the local "test.db" file.

  **Scenario 2:** Saving data to the remote Turso database
    Given the environment variable `DB_BACKEND` is set to "turso"
    And `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are configured for a test database
    When the SEO analyzer is run and saves a metrics snapshot
    Then the snapshot data should exist in the remote Turso database.

---

## 5. Summary

This proposal outlines a clear and non-disruptive path to enhance the SEO Analyzer with powerful, flexible persistence options. By abstracting the database logic and using a configuration-driven factory, we can support both simple local use cases and scalable, distributed deployments with Turso.
