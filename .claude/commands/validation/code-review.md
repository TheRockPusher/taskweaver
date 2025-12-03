---
description: Multi-pass AI code review with parallel category analysis
allowed-tools:
  - Read
  - Glob
  - Grep
  - Task
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git show:*)
  - Bash(git ls-files:*)
  - Bash(git branch:*)
  - Bash(npm run lint:*)
  - Bash(npm run test:*)
  - Bash(npx tsc:*)
  - Bash(npx eslint:*)
  - Bash(python -m pytest:*)
  - Bash(python -m mypy:*)
  - Bash(python -m ruff:*)
  - Bash(cargo test:*)
  - Bash(cargo clippy:*)
  - Bash(cargo check:*)
  - Bash(make:*)
  - Write
argument-hint: <mode> [target] — modes: codebase | commit <sha> | branch [base]
model: sonnet
---

# Code Review: Multi-Pass Analysis

## Objective

Perform comprehensive code review using parallel category-specific analysis agents.
Output structured findings to `.agents/code-reviews/` for downstream processing.

## Arguments

Parse `$ARGUMENTS` to determine review mode:

| Mode | Syntax | Scope |
|------|--------|-------|
| **codebase** | `/code-review codebase` | All tracked files |
| **commit** | `/code-review commit <sha>` | Single commit changes |
| **branch** | `/code-review branch [base]` | Current branch vs base (default: main) |

If no arguments provided, default to `branch main`.

---

## Phase 1: Context Gathering

### Step 1: Load project standards

Read these files to understand codebase conventions:

```text
Read("CLAUDE.md")
Read(".agents/PRD.md") — if exists
Read("README.md") — if exists
```

Extract from CLAUDE.md:

- **Validation commands** (e.g., `make check`, `npm run lint`, `ruff check`)
- **Code style** requirements
- **Testing approach**
- **Language/framework** specifics

### Step 2: Identify validation tools

Search CLAUDE.md for validation/check commands. Common patterns:

```text
# Python projects
ruff check .
python -m mypy .
python -m pytest

# JavaScript/TypeScript projects
npm run lint
npm run test
npx tsc --noEmit

# Rust projects
cargo clippy
cargo test

# Makefile projects
make check
make test
make lint
```

Store identified commands for Phase 4 validation.

---

## Phase 2: Change Analysis

Based on mode, gather changes:

### Mode: codebase

```bash
git ls-files --exclude-standard
```

Read all source files (exclude: node_modules, .venv, dist, build, **pycache**).

### Mode: commit

```bash
git show --stat <sha>
git diff <sha>^..<sha>
```

### Mode: branch

```bash
git log --oneline main..HEAD
git diff main...HEAD --stat
git diff main...HEAD
```

For all modes:

- Get list of modified/added/deleted files
- Read FULL content of changed files (not just diffs)
- Note new untracked files: `git ls-files --others --exclude-standard`

---

## Phase 3: Multi-Pass Parallel Review

Launch **5 parallel Task agents**, each focused on one category.
All agents receive the same context: file list, diffs, and codebase standards.

### Agent 1: Security Review (CRITICAL)

```text
Task(subagent_type="Explore", prompt="""
Security-focused code review. Analyse for:

CRITICAL Issues:
- SQL injection (string interpolation in queries)
- XSS vulnerabilities (unescaped user input in HTML)
- Command injection (shell commands with user input)
- Path traversal (user-controlled file paths)
- SSRF (user-controlled URLs in server requests)
- Hardcoded secrets (API keys, passwords, tokens)
- Insecure cryptography (weak algorithms, hardcoded IVs)
- Authentication/authorisation flaws
- Insecure deserialisation

HIGH Issues:
- Missing input validation at boundaries
- Improper error handling exposing internals
- Insecure default configurations
- Missing rate limiting on sensitive endpoints

Files to review: [LIST]
Diff context: [DIFF]

Output format for each issue:
severity: critical | high
file: path/to/file.ext
line: 42
category: security
issue: One-line description
detail: Why this is a security risk
suggestion: How to fix with code example
reachable: true/false (is this code path actually executed?)

If no security issues found, output: "No security issues detected."
""")
```

### Agent 2: Logic and Correctness Review (BLOCKING)

```text
Task(subagent_type="Explore", prompt="""
Logic and correctness review. Analyse for:

BLOCKING Issues:
- Off-by-one errors in loops/indices
- Incorrect boolean logic (&&/|| confusion, negation errors)
- Null/undefined reference errors
- Race conditions in concurrent code
- Resource leaks (unclosed files, connections, streams)
- Exception handling gaps (missing catches, swallowed errors)
- Type mismatches and coercion bugs
- Infinite loops or recursion without base case
- Dead code that should execute
- Missing return statements

Files to review: [LIST]
Diff context: [DIFF]

Output format for each issue:
severity: blocking
file: path/to/file.ext
line: 42
category: logic
issue: One-line description
detail: Explanation of the bug
suggestion: Corrected code

If no logic issues found, output: "No logic issues detected."
""")
```

### Agent 3: Performance Review (MAJOR/MINOR)

```text
Task(subagent_type="Explore", prompt="""
Performance-focused code review. Analyse for:

MAJOR Issues:
- N+1 query patterns (queries in loops)
- O(n squared) or worse algorithms where O(n) is possible
- Unbounded memory growth (growing lists without limits)
- Blocking I/O in async contexts
- Missing database indices for frequent queries
- Large data structures copied unnecessarily

MINOR Issues:
- Inefficient string concatenation in loops
- Redundant computations (cacheable values recalculated)
- Suboptimal data structure choice
- Unnecessary object allocations in hot paths

Files to review: [LIST]
Diff context: [DIFF]

Output format for each issue:
severity: major | minor
file: path/to/file.ext
line: 42
category: performance
issue: One-line description
detail: Performance impact explanation
suggestion: Optimised approach with code

If no performance issues found, output: "No performance issues detected."
""")
```

### Agent 4: Code Quality Review (SUGGESTIONS)

```text
Task(subagent_type="Explore", prompt="""
Code quality review. Analyse for:

SUGGESTIONS:
- Functions exceeding 50 lines (split recommended)
- Functions with more than 4 parameters (object/struct recommended)
- Deeply nested conditionals (more than 3 levels)
- Duplicated code blocks (DRY violations)
- Misleading or unclear variable/function names
- Missing error messages in exceptions
- Magic numbers without named constants
- Complex expressions without explanatory variables
- Inconsistent naming conventions within file
- Missing type hints/annotations on public APIs

Files to review: [LIST]
Diff context: [DIFF]
Codebase conventions: [FROM CLAUDE.md]

Output format for each issue:
severity: suggestion
file: path/to/file.ext
line: 42
category: quality
issue: One-line description
detail: Why this impacts maintainability
suggestion: Improved approach

If no quality issues found, output: "No quality issues detected."
""")
```

### Agent 5: Pattern Adherence Review (NITS)

```text
Task(subagent_type="Explore", prompt="""
Pattern and convention review. Compare against codebase standards.

NITS (non-blocking polish):
- Deviations from project naming conventions
- Inconsistent code formatting (if not auto-formatted)
- Missing or outdated comments/docstrings
- Import ordering inconsistencies
- Inconsistent error handling patterns vs codebase
- Deviations from established architectural patterns
- Test naming convention violations
- File organisation inconsistencies

Files to review: [LIST]
Diff context: [DIFF]
Codebase conventions: [FROM CLAUDE.md]

Output format for each issue:
severity: nit
file: path/to/file.ext
line: 42
category: patterns
issue: One-line description
detail: How it deviates from codebase patterns
suggestion: Aligned approach

If no pattern issues found, output: "Code follows established patterns."
""")
```

---

## Phase 4: Validation

Run project-specific validation tools identified in Phase 1.

Execute validation commands (examples):

```bash
# Run whatever commands were found in CLAUDE.md
make check        # If Makefile exists
npm run lint      # If package.json exists
ruff check .      # If Python project
cargo clippy      # If Rust project
```

Cross-reference results:

- Confirm agent findings with tool output
- Flag any tool errors not caught by agents
- Note passing validations as confidence signal

---

## Phase 5: Output Generation

Generate timestamped review file:

```text
.agents/code-reviews/review-YYYY-MM-DD-HHMMSS.md
```

Use the following output structure for the review file.

The file should contain:

1. Header with mode, target, timestamp, reviewer info
2. Summary table showing issue counts by category and severity
3. Risk level assessment (LOW, MEDIUM, HIGH, CRITICAL)
4. Files analysed count and lines changed
5. Sections for each severity level with detailed issue entries
6. Validation results showing tool execution outcomes
7. Positive observations section
8. Next steps pointing to the fix command

Each issue entry should include:

- severity (critical, high, blocking, major, minor, suggestion, nit)
- file path with line number
- category (security, logic, performance, quality, patterns)
- issue description (one line)
- detail (explanation)
- suggestion (fix with code if applicable)
- reachable flag for security issues

---

## Important Notes

- **Read full files**, not just diffs — context prevents false positives
- **Verify reachability** — only flag issues in actually-executed code paths
- **Be specific** — line numbers, not vague complaints
- **Suggest fixes** — actionable code, not just criticism
- **Respect conventions** — judge against CLAUDE.md standards, not personal preference
- **Acknowledge good code** — note positive patterns in final section

ultrathink
