# [TaskWeaver](https://github.com/TheRockPusher/taskweaver)

An AI-powered task organizer and decomposer that helps you break down complex goals into manageable, actionable tasks.

TaskWeaver is a conversational AI agent that intelligently organizes, prioritizes, and decomposes your tasks. It analyzes your skill level, identifies knowledge gaps, and creates learning paths to help you accomplish your goals efficiently.

**Target Audience:** Anyone looking to organize complex projects, learn new skills systematically, or improve task management through AI-powered decomposition and prioritization.

**Project Status:** Version 0.2.0 (active development - Phase 2 - 95% complete)

[![CI](https://github.com/TheRockPusher/taskweaver/actions/workflows/ci.yml/badge.svg)](https://github.com/TheRockPusher/taskweaver/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL-3.0-blue.svg)](LICENSE)

## Getting Started

TaskWeaver helps you accomplish complex goals by breaking them down into achievable tasks, detecting skill gaps, and creating personalised learning paths.

### Quick Start

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

Note: TaskWeaver is currently in active development. The CLI is functional for basic task management. Development focus is on AI-powered decomposition and intelligent analysis. Check back soon for updates on advanced features!

### Full Documentation

- **Installation Guide**: See [Installation](#installation) section below
- **Usage Examples**: See [Usage](#usage) section below
- **Contributing**: See [Contributing](#contributing) section below
- **Project Goals**: See [Why TaskWeaver?](#why-taskweaver) section below

## Why TaskWeaver?

TaskWeaver addresses a common challenge: **complex goals often fail because they're too overwhelming to start or unclear how to proceed.**

### The Problem

- Large projects feel insurmountable without proper breakdown
- You don't know what skills you're missing until you start
- Learning feels disconnected from doing (violates JIT learning principles)
- Task prioritization is subjective and inconsistent
- Dependencies between tasks aren't always clear

### The Solution

TaskWeaver provides:

- **Intelligent Task Decomposition**: Automatically breaks complex goals into manageable chunks
- **Skill Gap Analysis**: Identifies what you need to learn before starting tasks
- **Just-In-Time Learning**: Creates learning tasks that directly unblock your goals
- **Smart Prioritization**: Uses multi-criteria decision analysis (MCDA) for objective task scoring
- **Dependency Management**: Tracks task relationships and detects circular dependencies
- **Adaptive Learning**: Remembers your preferences and adjusts recommendations over time

### Core Principles

1. **JIT Learning**: Learning without action isn't learning - all learning tasks directly support doing
2. **Skill-Based Planning**: Tasks are matched to your current Dreyfus skill level
3. **Progressive Disclosure**: Focus on what's immediately actionable, not everything at once
4. **Dogfooding**: Built to improve itself - the first user is the project itself

## Current Status

**Project Stage:** Phase 2 – AI Integration & Dependency Management (95% Complete)

Core infrastructure complete (Phase 1 ✅). PydanticAI agent fully integrated with 11 task management and dependency tools. Dependency management system implemented with BFS-based cycle detection. Ready for integration testing with real LLM API.

## Features (Roadmap)

### Phase 1: Foundation ✅ COMPLETE

- ✅ SQLite database with schema versioning
- ✅ Full CRUD CLI interface (Typer + Rich)
- ✅ Pydantic models for validation
- ✅ 80%+ test coverage

### Phase 2: AI Integration & Dependency Management ✅ 95% COMPLETE

🤖 **Conversational Task Management** (COMPLETE)

- ✅ PydanticAI agent framework integrated
- ✅ 11 agent tools registered (6 task management + 5 dependency tools)
- ✅ Interactive `taskweaver chat` command
- ✅ Production orchestrator prompt (1,161 lines, extensively optimised)
- ✅ Dependency-aware task analysis
- **Status:** Feature complete, ready for API integration testing

🔗 **Dependency Management** (COMPLETE - Phase 2)

- ✅ Task blocking relationships (DAG structure)
- ✅ Circular dependency detection using BFS algorithm
- ✅ TaskDependencyRepository with full CRUD operations
- ✅ Active blocker retrieval (filters completed/cancelled tasks)
- ✅ TaskWithDependencies model with aggregated counts
- ✅ tasks_full database view with dependency metrics
- ✅ CLI commands: `lso` (list open), `createDep`, `rmdep`, `blocker`
- ✅ Comprehensive test suite (17 dependency tests, all passing)
- **Status:** Complete and thoroughly tested

🧠 **Intelligent Task Analysis**

- Automatic decomposition of complex tasks into subtasks
- Skill gap detection based on Dreyfus model
- Multi-criteria priority scoring (MCDA)
- **Status:** Not yet implemented

📊 **Adaptive System**
- Learns your preferences from task completion patterns
- Updates skill assessments based on demonstrated capabilities
- Adjusts scoring over time
- **Status:** Not yet implemented

### Technical Features

- Built with [PydanticAI](https://ai.pydantic.dev/) for robust agent implementation
- SQLite database for local-first task storage
- Comprehensive dependency tracking with cycle detection
- Modern Python packaging with [UV](https://github.com/astral-sh/uv)
- Comprehensive code quality tools (Ruff, Ty, pytest with 85%+ coverage)
- Pre-commit hooks and CI/CD automation

## Installation

### Prerequisites

- **Python 3.13 or higher**
- **[UV](https://github.com/astral-sh/uv) package manager** (a fast Python package and project manager written in [Rust](https://www.rust-lang.org/))

#### Installing Prerequisites

**Ubuntu/Debian:**

```bash
# Install Python (if not already installed)
sudo apt-get update
sudo apt-get install -y python3 python3.13 python3-pip

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**macOS:**

```bash
# Install Python via Homebrew (if needed)
brew install python@3.13

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
# Install Python from python.org first, then:
# Install UV
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Arch Linux:**

```bash
# Install Python (usually pre-installed)
sudo pacman -S python

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install the package

```bash
# Clone from source (currently the only installation method)
git clone https://github.com/TheRockPusher/taskweaver.git
cd taskweaver

# Install dependencies
make install

# Or manually with UV
uv sync
```

## Usage

### Interactive Chat Mode (Phase 2 - NEW)

Start an interactive conversation with the AI task orchestrator:

```bash
# Start chat session
uv run taskweaver chat

# Example conversation:
You: "I want to build a web app with authentication"

TaskWeaver: Let me break this down strategically...

You: "I'm new to web development"

TaskWeaver: [Creates a structured breakdown with foundational tasks first]
- Learn HTTP basics and REST principles
- Set up development environment (Python/Flask)
- Design database schema for users
- Implement basic authentication
- Create login UI
- Add security hardening

Ready to get started? Which task interests you most?
```

### CLI Task Management (Phase 1 - Available Now)

```bash
# Create a task
uv run taskweaver create "Build authentication system" -d "Implement OAuth2 or JWT"

# List all tasks
uv run taskweaver ls

# List open tasks with dependency counts
uv run taskweaver lso

# Show task details
uv run taskweaver show <task-id>

# Mark tasks as in progress
uv run taskweaver edit <task-id> -s in_progress

# Complete a task
uv run taskweaver edit <task-id> -s completed

# Delete a task
uv run taskweaver rm <task-id>
```

### Dependency Management (Phase 2 - Complete)

Create and manage task relationships with automatic cycle detection:

```bash
# Create a dependency (task is blocked by blocker)
uv run taskweaver createDep <task-id> <blocker-id>

# Remove a dependency
uv run taskweaver rmdep <task-id> <blocker-id>

# View tasks blocking a specific task
uv run taskweaver blocker <task-id>
```

**Key Features:**

- Automatic circular dependency detection using breadth-first search
- Active blocker filtering (only pending/in_progress tasks block)
- Prevented dependencies on completed/cancelled tasks
- Dependency counts aggregated in tasks_full view

### Configuration

Set your LLM provider:

```bash
# Option 1: Environment variable
export API_KEY="sk-..."

# Option 2: .env file
echo "API_KEY=sk-..." > .env

# Option 3: config.toml
cat > config.toml << EOF
model = "gpt-4o-mini"
api_endpoint = "https://api.openai.com/v1"
EOF
```

Supports any LLM provider compatible with the endpoint format (OpenAI, Anthropic, local models).

### Success Metrics (MVP Targets)

The MVP implementation will aim to achieve these goals:

- Add complex tasks via conversation (no CLI flags required)
- Automatic task decomposition, gap detection, and prioritization
- User approval and adjustment workflow before committing to database
- Learning tasks correctly unblock parent tasks
- Score inference accuracy >70% (user accepts without edits)
- Decomposition acceptance rate >70%
- System learns preferences after 20+ task completions

### Development Approach

The project is being developed using a "dogfooding" approach - TaskWeaver will be used to organize its own development. This means the project roadmap, development tasks, and progress will be managed through the system as it's being built, providing real-world validation of the approach.

More detailed usage examples and workflows will be added as features are implemented.

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/TheRockPusher/taskweaver.git
cd taskweaver

# Install dependencies and pre-commit hooks
make install
```

### Available Make Commands

Run `make help` to see all available commands:

```bash
make install         # Install the virtual environment and pre-commit hooks
make format          # Format code with ruff
make format-check    # Check code formatting
make lint-check      # Lint code with ruff
make type-check      # Run static type checking with ty
make check           # Run all code quality checks
make test            # Run tests with pytest
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
make test FILE=tests/test_main.py

# Run with coverage report
uv run pytest --cov=taskweaver --cov-report=html
```

### Code Quality

This project maintains high code quality standards:

- **Formatting**: Automated with Ruff (120 character line length)
- **Linting**: Comprehensive rules including security checks (Bandit)
- **Type Checking**: Enforced with Ty
- **Testing**: Minimum 80% code coverage required
- **Documentation**: Google-style docstrings

All checks run automatically via pre-commit hooks and CI/CD.

## Project Structure

```bash
taskweaver/
├── src/
│   └── taskweaver/     # Main package code
│       ├── __init__.py
│       ├── cli.py                          # CLI commands
│       ├── config.py                       # Configuration management
│       ├── database/                       # Data layer
│       │   ├── __init__.py
│       │   ├── connection.py               # Database connection
│       │   ├── models.py                   # Pydantic models
│       │   ├── repository.py               # Task CRUD operations
│       │   ├── dependency_repository.py    # Dependency management
│       │   ├── schema.py                   # SQL schema definitions
│       │   ├── exceptions.py               # Custom exceptions
│       │   └── tests/
│       │       ├── conftest.py
│       │       ├── test_repository.py
│       │       └── test_dependency_repository.py
│       ├── agents/                         # AI agent layer
│       │   ├── __init__.py
│       │   ├── task_agent.py               # Agent setup
│       │   ├── tools.py                    # Tool definitions
│       │   ├── chat_handler.py             # I/O protocol
│       │   ├── prompts/
│       │   │   └── orchestrator_prompt.md  # Agent system prompt
│       │   └── tests/
│       │       ├── conftest.py
│       │       └── test_task_agent.py
│       ├── tests/
│       │   ├── conftest.py
│       │   ├── test_cli.py
│       │   └── test_config.py
│       └── py.typed                        # PEP 561 type marker
├── .github/
│   ├── actions/
│   │   └── setup-python-env/               # Reusable setup action
│   └── workflows/
│       ├── ci.yml                          # CI pipeline
│       └── release.yml                     # Release automation
├── pyproject.toml                          # Project configuration
├── Makefile                                # Development commands
├── CLAUDE.md                               # Claude Code guidance
├── AI/project.md                           # Technical documentation
├── .pre-commit-config.yaml                 # Pre-commit hooks
└── README.md                               # This file
```

## Contributing

Contributions are welcome! We actively encourage bug reports, feature requests, and pull requests from the community.

**How to participate:**

- **Bug Reports:** Please open an [issue](https://github.com/TheRockPusher/taskweaver/issues) on GitHub with detailed information about the problem.
- **Feature Requests:** Open an [issue](https://github.com/TheRockPusher/taskweaver/issues) describing your proposed feature and use case.
- **Pull Requests:** We accept and review pull requests. Please ensure your code passes all quality checks (`make check && make test`) before submitting.
- **Questions/Discussions:** Use [GitHub Discussions](https://github.com/TheRockPusher/taskweaver/discussions) for general questions and community discussions.

**Contribution Requirements:**

- All code must pass automated quality checks (Ruff formatting, Ruff linting, Ty type checking)
- Test coverage must remain at or above 80%
- New features should include tests and documentation
- Follow the existing code style (Google-style docstrings, 120 character line length)
- No Contributor License Agreement (CLA) is required - contributions are licensed under the same AGPL-3.0 license as the project

For detailed contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

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

## License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Authors

**Nelson Sousa** - Primary maintainer

- GitHub: [@TheRockPusher](https://github.com/TheRockPusher)
- Email: [github@orvit.simplelogin.com](mailto:github@orvit.simplelogin.com)

## Community Guidelines

This project aims to be welcoming and inclusive. While we don't currently have a formal Code of Conduct, we expect all contributors and participants to:

- Be respectful and considerate in discussions
- Provide constructive feedback
- Focus on what is best for the community and project
- Show empathy towards other community members

## Project Context

TaskWeaver is an individual open source project created to solve the challenge of managing complex goals through intelligent task decomposition and skill-based learning paths. It is not affiliated with any corporate entity or commercial service offering.

**Privacy First**: All data stays local on your device. TaskWeaver uses SQLite for storage and does not transmit any user data or telemetry anywhere. Your tasks, skills, and preferences remain completely private.

## Acknowledgments

### Core Technologies

- **AI Framework**: [PydanticAI](https://ai.pydantic.dev/) - Production-grade agent framework
- **Package Manager**: [UV](https://github.com/astral-sh/uv) - Blazing fast Python package management
- **Code Quality**: [Ruff](https://github.com/astral-sh/ruff) - Lightning-fast Python linter and formatter
- **Type Checking**: [Ty](https://github.com/python/ty) - Static type analysis
- **Testing**: [pytest](https://pytest.org/) - Comprehensive Python testing framework

### Methodologies

- **Skill Assessment**: Dreyfus Model of Skill Acquisition
- **Prioritization**: Multi-Criteria Decision Analysis (MCDA)
- **Learning Philosophy**: Just-In-Time (JIT) Learning principles
- **Dependency Management**: Directed Acyclic Graphs (DAG) with BFS cycle detection

## Links

- **Repository**: [https://github.com/TheRockPusher/taskweaver](https://github.com/TheRockPusher/taskweaver)
- **Issues**: [https://github.com/TheRockPusher/taskweaver/issues](https://github.com/TheRockPusher/taskweaver/issues)
- **Documentation**: [https://github.com/TheRockPusher/taskweaver#readme](https://github.com/TheRockPusher/taskweaver#readme)
