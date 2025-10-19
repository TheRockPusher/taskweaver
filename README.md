# [TaskWeaver](https://github.com/TheRockPusher/taskweaver)

An AI-powered task organiser and decomposer that helps you break down complex goals into manageable, actionable tasks.

TaskWeaver is a conversational AI agent that intelligently organises, prioritises, and decomposes your tasks. It analyses your skill level, identifies knowledge gaps, and creates learning paths to help you accomplish your goals efficiently.

**Target Audience:** Anyone looking to organise complex projects, learn new skills systematically, or improve task management through AI-powered decomposition and prioritisation.

**Project Status:** Version 0.1.0 (early development – MVP foundation stage)

[![CI](https://github.com/TheRockPusher/taskweaver/actions/workflows/ci.yml/badge.svg)](https://github.com/TheRockPusher/taskweaver/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL-3.0-blue.svg)](LICENSE)

## Quick Start

TaskWeaver helps you accomplish complex goals by breaking them down into achievable tasks, detecting skill gaps, and creating personalised learning paths.

### Installation

```bash
# Clone the repository
git clone https://github.com/TheRockPusher/taskweaver.git
cd taskweaver

# Install UV if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
make install

# Run tests to verify installation
make test
```

**Prerequisites:**
- Python 3.13 or higher
- [UV](https://github.com/astral-sh/uv) package manager

### Current Capabilities

TaskWeaver currently provides a command-line interface for task management with a SQLite database backend:

```bash
# Create a new task
uv run taskweaver create "Build authentication system" -d "Implement user login and registration"

# List all tasks
uv run taskweaver ls

# Filter tasks by status
uv run taskweaver ls --status pending

# View task details
uv run taskweaver show <task-uuid>

# Update a task
uv run taskweaver edit <task-uuid> --status in_progress

# Delete a task
uv run taskweaver rm <task-uuid> --force
```

**Note:** The AI-powered features (task decomposition, skill gap analysis, intelligent prioritisation) are under development and will be available in future releases.

## Why TaskWeaver?

TaskWeaver addresses a common challenge: **complex goals often fail because they're too overwhelming to start or unclear how to proceed.**

### The Problem

- Large projects feel insurmountable without proper breakdown
- You don't know what skills you're missing until you start
- Learning feels disconnected from doing (violates JIT learning principles)
- Task prioritisation is subjective and inconsistent
- Dependencies between tasks aren't always clear

### The Solution (Planned)

TaskWeaver will provide:

- **Intelligent Task Decomposition:** Automatically breaks complex goals into manageable chunks
- **Skill Gap Analysis:** Identifies what you need to learn before starting tasks
- **Just-In-Time Learning:** Creates learning tasks that directly unblock your goals
- **Smart Prioritisation:** Uses multi-criteria decision analysis (MCDA) for objective task scoring
- **Dependency Management:** Tracks task relationships and detects circular dependencies
- **Adaptive Learning:** Remembers your preferences and adjusts recommendations over time

### Core Principles

1. **JIT Learning:** Learning without action isn't learning – all learning tasks directly support doing
2. **Skill-Based Planning:** Tasks are matched to your current Dreyfus skill level
3. **Progressive Disclosure:** Focus on what's immediately actionable, not everything at once
4. **Dogfooding:** Built to improve itself – the first user is the project itself

## Development Status

**Current Implementation Status:** Database and CLI Foundation (✅ Complete)
- SQLite database with schema versioning
- Full CRUD operations via CLI
- Auto-database initialisation
- Comprehensive test coverage (80%+)
- Type-safe Pydantic models

**Not Yet Implemented:** AI Features
- Conversational interface with PydanticAI agent
- Automatic task decomposition
- Skill gap analysis (Dreyfus model)
- Multi-criteria priority scoring (MCDA)
- Dependency DAG management
- User preference learning

See [Development](#development) for contribution guidelines.

## Usage

### Task Management Commands

#### Create a Task

```bash
# Minimal – title only
uv run taskweaver create "Learn Python"

# With description
uv run taskweaver create "Learn Python" -d "Focus on async programming"

# Custom database location
uv run taskweaver create "Task" --db /path/to/custom.db
```

#### List Tasks

```bash
# List all tasks (most recent first)
uv run taskweaver ls

# Filter by status
uv run taskweaver ls --status pending
uv run taskweaver ls -s in_progress
uv run taskweaver ls -s completed
uv run taskweaver ls -s cancelled
```

Status values: `pending`, `in_progress`, `completed`, `cancelled`

#### View Task Details

```bash
# Show full task information
uv run taskweaver show <task-uuid>
```

#### Update a Task

```bash
# Update title
uv run taskweaver edit <task-uuid> --title "New Title"

# Update description
uv run taskweaver edit <task-uuid> -d "New description"

# Update status
uv run taskweaver edit <task-uuid> --status completed

# Combine multiple updates
uv run taskweaver edit <task-uuid> -t "Title" -d "Desc" -s in_progress
```

#### Delete a Task

```bash
# Delete with confirmation prompt
uv run taskweaver rm <task-uuid>

# Force delete without confirmation
uv run taskweaver rm <task-uuid> --force
```

### Database Configuration

By default, TaskWeaver stores tasks in `~/.taskweaver/tasks.db`. You can specify a custom location:

```bash
# All commands support custom database paths
uv run taskweaver create "Task" --db /home/user/my-tasks.db
uv run taskweaver ls --db /home/user/my-tasks.db
```

## Project Structure

```tree
taskweaver/
├── src/taskweaver/              # Main package code
│   ├── __init__.py              # Version and entry point
│   ├── cli.py                   # Command-line interface (143 lines)
│   ├── database/                # Database layer
│   │   ├── __init__.py          # Module exports
│   │   ├── connection.py        # SQLite connection management
│   │   ├── models.py            # Pydantic data models
│   │   ├── repository.py        # Task CRUD operations
│   │   ├── schema.py            # SQL schema definitions
│   │   ├── exceptions.py        # Custom exceptions
│   │   └── tests/               # Database tests
│   │       ├── conftest.py      # Pytest fixtures
│   │       └── test_repository.py
│   └── tests/
│       ├── conftest.py
│       └── test_cli.py          # CLI integration tests
├── .github/
│   └── workflows/
│       ├── ci.yml               # Continuous integration
│       └── release.yml          # Automated releases
├── pyproject.toml               # Project configuration
├── Makefile                     # Development commands
├── CLAUDE.md                    # Development guidelines
└── README.md                    # This file
```

## Development

### Setup Development Environment

```bash
# Clone and install
git clone https://github.com/TheRockPusher/taskweaver.git
cd taskweaver
make install
```

### Available Development Commands

```bash
make help              # Show all available commands
make install          # Install dependencies (uses UV)
make format           # Format code with Ruff
make format-check     # Check formatting without changes
make lint-check       # Run linting checks
make type-check       # Run static type checking
make check            # Run all quality checks
make test             # Run test suite with coverage
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
make test FILE=src/taskweaver/database/tests/test_repository.py

# Run with coverage report
uv run pytest --cov=taskweaver --cov-report=html
```

### Code Quality Standards

This project maintains high code quality standards:

- **Formatting:** Automated with Ruff (120 character line length)
- **Linting:** Comprehensive rules including security checks (Bandit)
- **Type Checking:** Enforced with Ty
- **Testing:** Minimum 80% code coverage required
- **Documentation:** Google-style docstrings

All checks run automatically via pre-commit hooks and CI/CD.

### Python Version & Tools

- **Python:** 3.13+
- **Package Manager:** [UV](https://github.com/astral-sh/uv)
- **Formatter:** [Ruff](https://github.com/astral-sh/ruff)
- **Linter:** Ruff (includes security checks from Bandit)
- **Type Checker:** [Ty](https://github.com/python/ty)
- **Testing:** [pytest](https://pytest.org/) with coverage

### Project Guidelines

This project follows principles outlined in [CLAUDE.md](CLAUDE.md):

- **KISS (Keep It Simple, Stupid):** Favour straightforward solutions
- **YAGNI (You Aren't Gonna Need It):** Build features when needed, not speculatively
- **Vertical Slice Architecture:** Tests live next to code
- **File Limits:** Max 500 lines per file, 50 lines per function
- **Pythonic Patterns:** Leverage Python's data model and built-in idioms

## Contributing

Contributions are welcome! We actively encourage bug reports, feature requests, and pull requests from the community.

### How to Participate

- **Bug Reports:** Open an [issue](https://github.com/TheRockPusher/taskweaver/issues) with detailed information
- **Feature Requests:** Open an [issue](https://github.com/TheRockPusher/taskweaver/issues) describing the proposed feature
- **Pull Requests:** We accept and review PRs – ensure your code passes all quality checks before submitting
- **Questions/Discussions:** Use [GitHub Discussions](https://github.com/TheRockPusher/taskweaver/discussions)

### Contribution Requirements

- All code must pass automated quality checks (Ruff formatting, Ruff linting, Ty type checking)
- Test coverage must remain at or above 80%
- New features should include tests and documentation
- Follow the existing code style (Google-style docstrings, 120 character line length)
- No Contributor License Agreement required

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and quality checks (`make check && make test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Releasing

This project uses automated releases via GitHub Actions:

1. Go to Actions → Release workflow
2. Click "Run workflow"
3. Select version bump type (patch/minor/major)
4. Optionally select pre-release type (alpha/beta/rc)
5. The workflow will:
   - Run all tests
   - Bump the version
   - Update the lockfile
   - Create a git tag
   - Build the package
   - Create a GitHub release

## Architecture

TaskWeaver uses a clean vertical slice architecture:

```architecture
┌─────────────────────────────────────────────────┐
│            CLI Layer (Typer)                    │
│        Rich formatted output                    │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│        Repository Pattern                       │
│   (TaskRepository CRUD operations)              │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│      Pydantic Models + Validation               │
│   (Task, TaskCreate, TaskUpdate)                │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│      SQLite Connection Management               │
│    (Auto-initialisation, pooling)               │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│         SQLite Database                         │
│     (Local-first, encrypted ready)              │
└─────────────────────────────────────────────────┘
```

See [AI/project.md](AI/project.md) for detailed architecture and roadmap.

## License

This project is licensed under the AGPL-3.0 License – see the [LICENSE](LICENSE) file for details.

## Authors

**Nelson Sousa** – Primary Maintainer

- GitHub: [@TheRockPusher](https://github.com/TheRockPusher)
- Email: [github@orvit.simplelogin.com](mailto:github@orvit.simplelogin.com)

## Community Guidelines

This project aims to be welcoming and inclusive. We expect all contributors and participants to:

- Be respectful and considerate in discussions
- Provide constructive feedback
- Focus on what is best for the community and project
- Show empathy towards other community members

## Privacy First

All data stays local on your device. TaskWeaver uses SQLite for storage and does not transmit any user data or telemetry anywhere. Your tasks, skills, and preferences remain completely private.

## Acknowledgements

### Core Technologies

- **AI Framework:** [PydanticAI](https://ai.pydantic.dev/) – Production-grade agent framework
- **Package Manager:** [UV](https://github.com/astral-sh/uv) – Blazing fast Python package management
- **Code Quality:** [Ruff](https://github.com/astral-sh/ruff) – Lightning-fast Python linter and formatter
- **Type Checking:** [Ty](https://github.com/python/ty) – Static type analysis
- **Testing:** [pytest](https://pytest.org/) – Comprehensive Python testing framework
- **CLI:** [Typer](https://typer.tiangolo.com/) – Modern CLI framework
- **Output:** [Rich](https://rich.readthedocs.io/) – Beautiful terminal output

### Methodologies

- **Skill Assessment:** Dreyfus Model of Skill Acquisition
- **Prioritisation:** Multi-Criteria Decision Analysis (MCDA)
- **Learning Philosophy:** Just-In-Time (JIT) Learning principles
- **Dependency Management:** Directed Acyclic Graphs (DAG) with DFS cycle detection

## Support

For help using or developing TaskWeaver:

- **Documentation:** See [README.md](README.md) and [AI/project.md](AI/project.md)
- **Issues:** [GitHub Issues](https://github.com/TheRockPusher/taskweaver/issues)
- **Discussions:** [GitHub Discussions](https://github.com/TheRockPusher/taskweaver/discussions)
- **Feedback:** Report issues at https://github.com/anthropics/claude-code/issues (for Claude Code–specific feedback)

## Repository Links

- **Repository:** [https://github.com/TheRockPusher/taskweaver](https://github.com/TheRockPusher/taskweaver)
- **Issues:** [https://github.com/TheRockPusher/taskweaver/issues](https://github.com/TheRockPusher/taskweaver/issues)
- **Discussions:** [https://github.com/TheRockPusher/taskweaver/discussions](https://github.com/TheRockPusher/taskweaver/discussions)
