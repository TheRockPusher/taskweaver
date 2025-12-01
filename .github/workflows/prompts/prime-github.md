---
description: Prime agent with codebase understanding (GitHub Actions)
allowed-tools:
  - Read
  - Glob
  - Grep
  - Task
  - Bash(git ls-files:*)
  - Bash(git log:*)
  - Bash(git status:*)
  - Bash(gh:*)
model: sonnet
---

# Prime: Load Project Context

## GitHub Context

- **Repository**: $REPOSITORY
- **Triggered By**: $TRIGGERED_BY

## Objective

Build comprehensive understanding of the codebase by analysing structure,
documentation, and key files.

## Process

### 1. Analyse Project Structure

**Step 1: Get tracked files** (respects `.gitignore`):

```bash
git ls-files
```

**Step 2: Discover AI config files** (may be untracked):

```text
Glob("CLAUDE.md")
Glob("AGENTS.md")
Glob(".agents/**/*.md")
Glob(".claude/**/*.md")
Glob(".cursor/**/*")
Glob(".github/copilot-instructions.md")
Glob(".github/prompts/**/*.md")
```

**Step 3: For large codebases**, launch parallel Task agents:

- Agent 1: Analyse directory structure and identify key folders
- Agent 2: Read configuration files (package.json, pyproject.toml, etc.)
- Agent 3: Search for patterns in src/ or main code directories

**NEVER glob these** (use `git ls-files` instead):

- `.venv/`, `node_modules/`, `vendor/`, `__pycache__/`
- `dist/`, `build/`, `target/`, `.git/`

### 2. Read Core Documentation

- Read CLAUDE.md (or AGENTS.md if no CLAUDE.md exists)
- Read README files at project root and major directories
- Check for `.agents/` folder - read PRD.md and AI-ARCHITECTURE.md if present
- Read any architecture documentation

### 3. Identify Key Files

Based on the structure, identify and read:

- Main entry points (main.py, index.ts, app.py, etc.)
- Core configuration files (pyproject.toml, package.json, tsconfig.json)
- Key model/schema definitions
- Important service or controller files

### 4. Understand Current State

Check recent activity:

```bash
git log -10 --oneline
```

Check current branch and status:

```bash
git status
```

## Output Report

Provide a concise summary covering:

### Project Overview

- Purpose and type of application
- Primary technologies and frameworks
- Current version/state

### Architecture

- Overall structure and organization
- Key architectural patterns identified
- Important directories and their purposes

### Tech Stack

- Languages and versions
- Frameworks and major libraries
- Build tools and package managers
- Testing frameworks

### Core Principles

- Code style and conventions observed
- Documentation standards
- Testing approach

### Current State

- Active branch
- Recent changes or development focus
- Any immediate observations or concerns

**Make this summary easy to scan - use bullet points and clear headers.**

## Priming Complete

Context loaded. Ready for planning or implementation tasks.
