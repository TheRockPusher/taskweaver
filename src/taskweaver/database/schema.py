"""Database schema definitions and queries."""

SCHEMA_VERSION = 1

# Schema creation SQL
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(title) <= 500),
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

INSERT_SCHEMA_VERSION = """
INSERT OR IGNORE INTO schema_version (version, applied_at)
VALUES (?, datetime('now'));
"""

# Task CRUD queries
INSERT_TASK = """
INSERT INTO tasks (task_id, title, description, status, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?);
"""

SELECT_TASK_BY_ID = """
SELECT * FROM tasks WHERE task_id = ?;
"""

SELECT_ALL_TASKS = """
SELECT * FROM tasks ORDER BY created_at DESC;
"""

UPDATE_TASK = """
UPDATE tasks
SET title = ?, description = ?, status = ?, updated_at = ?
WHERE task_id = ?;
"""

DELETE_TASK = """
DELETE FROM tasks WHERE task_id = ?;
"""
