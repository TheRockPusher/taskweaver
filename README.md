# [TaskWeaver](https://github.com/TheRockPusher/taskweaver)

An AI-powered task organizer and decomposer that helps you break down complex goals into manageable, actionable tasks.

TaskWeaver is a conversational AI agent that intelligently organizes, prioritizes, and decomposes your tasks. It analyzes your skill level, identifies knowledge gaps, and creates learning paths to help you accomplish your goals efficiently.

**Target Audience:** Anyone looking to organize complex projects, learn new skills systematically, or improve task management through AI-powered decomposition and prioritization.

**Project Status:** Version 0.1.0 (early development - MVP stage)

[![CI](https://github.com/TheRockPusher/taskweaver/actions/workflows/ci.yml/badge.svg)](https://github.com/TheRockPusher/taskweaver/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL-3.0-blue.svg)](LICENSE)

## Getting Started

TaskWeaver helps you accomplish complex goals by breaking them down into achievable tasks, detecting skill gaps, and creating personalized learning paths.

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

Note: TaskWeaver is currently in active development. The CLI is not yet functional. Development focus is on core infrastructure and feature implementation. Check back soon for updates!

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

**Project Stage:** Early Development - Scaffolding Only

The project is currently in the initial scaffolding phase. Core infrastructure and project structure have been set up, but no features have been implemented yet. The roadmap below outlines the planned features for the MVP.

## Features (Roadmap)

### Planned Features for MVP

🎯 **Conversational Task Management**

- Add tasks naturally through conversation, no CLI flags needed
- AI understands context and extracts task details automatically
- **Status:** Not yet implemented

🧠 **Intelligent Task Analysis**

- Automatic decomposition of complex tasks into subtasks
- Skill gap detection based on Dreyfus model
- Multi-criteria priority scoring (MCDA)
- **Status:** Not yet implemented

🔗 **Dependency Management**
- Task blocking relationships (DAG structure)
- Circular dependency detection using DFS
- Learning tasks that unblock parent tasks
- **Status:** Not yet implemented

📊 **Adaptive System**
- Learns your preferences from task completion patterns
- Updates skill assessments based on demonstrated capabilities
- Adjusts scoring over time
- **Status:** Not yet implemented

### Technical Features

- Built with [PydanticAI](https://ai.pydantic.dev/) for robust agent implementation
- SQLite database for local-first task storage
- Modern Python packaging with [UV](https://github.com/astral-sh/uv)
- Comprehensive code quality tools (Ruff, Ty, pytest with 80% coverage)
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

TaskWeaver is currently in early development and is not yet ready for end-user usage. The following example illustrates the intended usage pattern once implementation is complete:

### Planned Usage Example

```bash
# Start a conversation with TaskWeaver
uv run taskweaver

# Example conversation (planned functionality):
You: "I want to build a web application with authentication"

TaskWeaver: I'll help you break this down. Let me analyze this task...

[TaskWeaver will analyze your goal and create:]
- Main task: Build web application with authentication
  - Subtask: Design database schema for users
  - Subtask: Implement authentication backend
  - Subtask: Create login/signup UI
  - Learning task: Learn JWT basics (blocks authentication backend)
  - Learning task: Study password hashing best practices (blocks authentication backend)

Based on your current skill level (beginner in web auth), I recommend starting with
the learning tasks. Would you like me to add these to your task list?
```

**Status:** This functionality is currently being designed and implemented. Check the project roadmap for updates on feature availability.

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
│       └── py.typed                      # PEP 561 type marker
├── tests/                                 # Test suite
│   └── test_main.py
├── .github/
│   ├── actions/
│   │   └── setup-python-env/             # Reusable setup action
│   └── workflows/
│       ├── ci.yml                        # CI pipeline
│       └── release.yml                   # Release automation
├── pyproject.toml                        # Project configuration
├── Makefile                              # Development commands
├── .pre-commit-config.yaml               # Pre-commit hooks
└── README.md                             # This file
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
- **Dependency Management**: Directed Acyclic Graphs (DAG) with DFS cycle detection

## Links

- **Repository**: [https://github.com/TheRockPusher/taskweaver](https://github.com/TheRockPusher/taskweaver)
- **Issues**: [https://github.com/TheRockPusher/taskweaver/issues](https://github.com/TheRockPusher/taskweaver/issues)
- **Documentation**: [https://github.com/TheRockPusher/taskweaver#readme](https://github.com/TheRockPusher/taskweaver#readme)
