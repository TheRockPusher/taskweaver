"""Database schema definitions and queries."""

SCHEMA_VERSION = 6

# Schema creation SQL
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(title) <= 500),
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    duration_min INTEGER NOT NULL CHECK (duration_min >= 1),
    raw_duration_min INTEGER NOT NULL CHECK (raw_duration_min >= 1),
    llm_value REAL NOT NULL CHECK (llm_value BETWEEN 0 AND 100),
    requirement TEXT NOT NULL,
    urgency INTEGER NOT NULL DEFAULT 3 CHECK (urgency BETWEEN 1 AND 5),
    importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
    effort INTEGER NOT NULL DEFAULT 3 CHECK (effort BETWEEN 1 AND 5),
    category TEXT NOT NULL DEFAULT 'general' CHECK (length(category) > 0),
    goal_id TEXT REFERENCES goals(goal_id) ON DELETE SET NULL,
    skill_domain TEXT,
    required_skill_level INTEGER CHECK (required_skill_level BETWEEN 1 AND 5),
    priority_score REAL CHECK (priority_score BETWEEN 0 AND 100),
    priority_updated_at TEXT
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
TASK_COLUMNS = (
    "task_id",
    "title",
    "description",
    "status",
    "created_at",
    "updated_at",
    "duration_min",
    "raw_duration_min",
    "llm_value",
    "requirement",
    "urgency",
    "importance",
    "effort",
    "category",
    "goal_id",
    "skill_domain",
    "required_skill_level",
    "priority_score",
    "priority_updated_at",
)
# Only constant column identifiers enter SQL; task values remain named parameters.
INSERT_TASK = (
    "INSERT INTO tasks ("  # noqa: S608
    + ", ".join(TASK_COLUMNS)
    + ") VALUES ("
    + ", ".join(":" + column for column in TASK_COLUMNS)
    + ");"
)

SELECT_TASK_BY_ID = """
SELECT * FROM tasks WHERE task_id = ?;
"""

SELECT_ALL_TASKS = """
SELECT * FROM tasks ORDER BY created_at DESC;
"""

UPDATE_TASK = (
    "UPDATE tasks SET "  # noqa: S608
    + ", ".join(column + " = :" + column for column in TASK_COLUMNS if column != "task_id")
    + " WHERE task_id = :task_id;"
)

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
SELECT blocker.* FROM task_dependencies td
JOIN tasks blocker ON blocker.task_id = td.blocker_id
JOIN tasks downstream ON downstream.task_id = td.task_id
WHERE td.task_id = ?
AND blocker.status IN ('pending', 'in_progress')
AND downstream.status IN ('pending', 'in_progress')
ORDER BY td.created_at;
"""

SELECT_BLOCKED_TASKS = """
SELECT downstream.* FROM task_dependencies td
JOIN tasks downstream ON downstream.task_id = td.task_id
JOIN tasks blocker ON blocker.task_id = td.blocker_id
WHERE td.blocker_id = ?
AND downstream.status IN ('pending', 'in_progress')
AND blocker.status IN ('pending', 'in_progress')
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

CREATE_VIEW_TASKS_FULL = """
CREATE VIEW IF NOT EXISTS tasks_full AS
SELECT
    t.*,
    COALESCE(n_blocked.blocked_count, 0) as tasks_blocked_count,
    COALESCE(n_blocker.blocker_count, 0) as active_blocker_count
FROM tasks as t
LEFT JOIN (
    SELECT td.blocker_id, COUNT(*) as blocked_count
    FROM task_dependencies td
    JOIN tasks downstream ON downstream.task_id = td.task_id
    WHERE downstream.status IN ('pending', 'in_progress')
    GROUP BY td.blocker_id
) as n_blocked ON t.task_id = n_blocked.blocker_id
LEFT JOIN (
    SELECT td.task_id as blocked_id, COUNT(*) as blocker_count
    FROM task_dependencies td
    JOIN tasks blocker ON td.blocker_id = blocker.task_id
    WHERE blocker.status IN ('pending', 'in_progress')
    GROUP BY td.task_id
) as n_blocker ON t.task_id = n_blocker.blocked_id
WHERE t.status IN ('pending', 'in_progress')
"""
SELECT_ALL_TASKS_DEPENDENCY = """
SELECT * FROM tasks_full ORDER BY created_at DESC;
"""
CREATE_COMPLETION = """
CREATE TABLE IF NOT EXISTS completion(
    completion_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE REFERENCES tasks(task_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('completed', 'cancelled')),
    closed_at TEXT NOT NULL,
    duration_expected INTEGER NOT NULL,
    duration_actual INTEGER NOT NULL,
    conclusion TEXT,
    created_at TEXT NOT NULL,
    raw_duration_min INTEGER NOT NULL CHECK (raw_duration_min >= 1),
    category TEXT NOT NULL,
    priority_factors TEXT
);
"""

CREATE_COMPLETION_INDEX_TASK = """
CREATE INDEX IF NOT EXISTS idx_completion_task ON completion(task_id);
"""

CREATE_COMPLETION_INDEX_STATUS = """
CREATE INDEX IF NOT EXISTS idx_completion_status ON completion(status);
"""

CREATE_COMPLETION_INDEX_CLOSED = """
CREATE INDEX IF NOT EXISTS idx_completion_closed_at ON completion(closed_at);
"""

# Completion CRUD queries
INSERT_COMPLETION = """
INSERT INTO completion (
    completion_id, task_id, status, closed_at, duration_expected, duration_actual, conclusion, created_at,
    raw_duration_min, category, priority_factors
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

SELECT_COMPLETION_BY_ID = """
SELECT * FROM completion WHERE completion_id = ?;
"""

SELECT_COMPLETION_BY_TASK_ID = """
SELECT * FROM completion WHERE task_id = ?;
"""

SELECT_ALL_COMPLETIONS = """
SELECT * FROM completion ORDER BY closed_at DESC;
"""

SELECT_COMPLETIONS_BY_STATUS = """
SELECT * FROM completion WHERE status = ? ORDER BY closed_at DESC;
"""

DELETE_COMPLETION = """
DELETE FROM completion WHERE completion_id = ?;
"""

CREATE_GOALS_TABLE = """
CREATE TABLE IF NOT EXISTS goals (
    goal_id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_SKILL_ASSESSMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS skill_assessments (
    assessment_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL CHECK (length(domain) > 0),
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 5),
    evidence TEXT NOT NULL CHECK (length(evidence) > 0),
    assessed_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
"""

CREATE_SKILL_ASSESSMENTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_skill_assessments_domain
ON skill_assessments(domain, assessed_at, recorded_at);
"""

CREATE_PRIORITY_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS priority_preferences (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    weights TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('custom', 'learned')),
    sample_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""

CREATE_PRIORITY_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS priority_history (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    score REAL NOT NULL CHECK (score BETWEEN 0 AND 100),
    recorded_at TEXT NOT NULL
);
"""

CREATE_PRIORITY_HISTORY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_priority_history_task ON priority_history(task_id, event_id);
"""

CREATE_MEMORY_FACTS_TABLE = """
CREATE TABLE IF NOT EXISTS memory_facts (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    deleted INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1)),
    backend_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    PRIMARY KEY (user_id, key)
);
"""

CREATE_MEMORY_TOMBSTONES_TABLE = """
CREATE TABLE IF NOT EXISTS memory_tombstones (
    user_id TEXT NOT NULL,
    backend_id TEXT NOT NULL,
    PRIMARY KEY (user_id, backend_id)
);
"""

CREATE_GITHUB_ISSUE_MAPPINGS_TABLE = """
CREATE TABLE IF NOT EXISTS github_issue_mappings (
    repo TEXT NOT NULL COLLATE NOCASE,
    issue_number INTEGER NOT NULL CHECK (issue_number > 0),
    task_id TEXT NOT NULL UNIQUE REFERENCES tasks(task_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    remote_state TEXT NOT NULL,
    local_state TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (repo, issue_number)
);
"""

CREATE_GITHUB_ISSUE_MAPPINGS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_github_issue_mappings_updated
ON github_issue_mappings(updated_at);
"""

SCHEMA_STATEMENTS = (
    CREATE_GOALS_TABLE,
    CREATE_TASKS_TABLE,
    CREATE_TASKS_INDEX_ID,
    CREATE_TASKS_INDEX_STATUS,
    CREATE_DEPENDENCY_TABLE,
    CREATE_DEPENDENCY_INDEX_TASK,
    CREATE_DEPENDENCY_INDEX_BLOCKER,
    CREATE_COMPLETION,
    CREATE_COMPLETION_INDEX_TASK,
    CREATE_COMPLETION_INDEX_STATUS,
    CREATE_COMPLETION_INDEX_CLOSED,
    CREATE_SKILL_ASSESSMENTS_TABLE,
    CREATE_SKILL_ASSESSMENTS_INDEX,
    CREATE_PRIORITY_PREFERENCES_TABLE,
    CREATE_PRIORITY_HISTORY_TABLE,
    CREATE_PRIORITY_HISTORY_INDEX,
    CREATE_MEMORY_FACTS_TABLE,
    CREATE_MEMORY_TOMBSTONES_TABLE,
    CREATE_GITHUB_ISSUE_MAPPINGS_TABLE,
    CREATE_GITHUB_ISSUE_MAPPINGS_INDEX,
    CREATE_VIEW_TASKS_FULL,
)
