"""Database schema definitions and queries."""

SCHEMA_VERSION = 2

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

CREATE_TASKS_INDEX_ID = """
CREATE INDEX IF NOT EXISTS idx_tasks_task ON tasks(task_id);
"""

CREATE_TASKS_INDEX_STATUS = """
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
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

# Task Dependency CRUD queries
CREATE_DEPENDENCY_TABLE = """
CREATE TABLE IF NOT EXISTS task_dependencies(
    dependency_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    blocker_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (blocker_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    UNIQUE(task_id, blocker_id),
    CHECK(task_id != blocker_id)
);
"""

CREATE_DEPENDENCY_INDEX_TASK = """
CREATE INDEX IF NOT EXISTS idx_task_dependencies_task ON task_dependencies(task_id);
"""

CREATE_DEPENDENCY_INDEX_BLOCKER = """
CREATE INDEX IF NOT EXISTS idx_task_dependencies_blocker ON task_dependencies(blocker_id);
"""

INSERT_DEPENDENCY = """
INSERT INTO task_dependencies (dependency_id, task_id, blocker_id, created_at)
VALUES (?, ?, ?, ?);
"""

SELECT_DEPENDENCY_BY_ID = """
SELECT * FROM task_dependencies WHERE dependency_id = ?;
"""

SELECT_BLOCKERS = """
SELECT blocker_id FROM task_dependencies
WHERE task_id = ?
ORDER BY created_at;
"""

SELECT_BLOCKED_TASKS = """
SELECT task_id FROM task_dependencies
WHERE blocker_id = ?
ORDER BY created_at;
"""

SELECT_ACTIVE_BLOCKERS = """
SELECT td.blocker_id as blocker_id
FROM task_dependencies td
JOIN tasks t ON td.blocker_id = t.task_id
WHERE td.task_id = ?
AND t.status IN ('pending', 'in_progress')
ORDER BY td.created_at;
"""

DELETE_DEPENDENCY = """
DELETE FROM task_dependencies
WHERE task_id = ? AND blocker_id = ?;
"""

CHECK_DEPENDENCY_EXISTS = """
SELECT dependency_id FROM task_dependencies
WHERE task_id = ? AND blocker_id = ?;
"""
