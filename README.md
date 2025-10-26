# [TaskWeaver](https://github.com/TheRockPusher/taskweaver)

An AI-powered task organiser and decomposer that helps you break down complex goals into manageable, actionable tasks.

TaskWeaver is a conversational AI agent that intelligently organises, prioritises, and decomposes your tasks. It analyses your skill level, identifies knowledge gaps, and creates learning paths to help you accomplish your goals efficiently.

**Target Audience:** Anyone looking to organise complex projects, learn new skills systematically, or improve task management through AI-powered decomposition and prioritisation.

**Project Status:** Version 0.7.0 (Active development - Completion tracking & pattern learning)

**Technology:** Python 3.13+ | PydanticAI 1.1.0 | SQLite | Typer CLI | UV package manager | Mem0 + Qdrant (Semantic Memory)

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

**Current Capabilities (v0.7.0):**

- ✅ Full CLI CRUD operations for tasks
- ✅ Dependency tracking with cycle detection (BFS algorithm)
- ✅ Interactive AI chat with conversational task decomposition
- ✅ Web search integration (DuckDuckGo)
- ✅ DAG-aware priority calculation with upstream inheritance
- ✅ Requirement/conclusion dual-purpose field
- ✅ Effective priority surfacing for critical path identification
- ✅ Semantic memory with Mem0 + Qdrant (local-first, persistent)
- ✅ GitHub issue integration for task import and synchronisation
- ✅ Optimised orchestrator prompt (1,704+ lines, 20% token efficiency improvement)
- ✅ Completion tracking with optional estimated vs actual duration tracking
- ✅ Variance analysis for automatic calculation of percentage variance
- ✅ Pattern learning foundation (CompletionRepository for CRUD operations)

**Next Up (v0.8.0+):** Pattern-based duration adjustment, TUI interface, enhanced memory features.

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
- Task prioritisation is subjective and inconsistent
- Dependencies between tasks aren't always clear

### The Solution

TaskWeaver provides:

- **Intelligent Task Decomposition**: Automatically breaks complex goals into manageable chunks
- **Skill Gap Analysis**: Identifies what you need to learn before starting tasks
- **Just-In-Time Learning**: Creates learning tasks that directly unblock your goals
- **Smart Prioritisation**: Uses multi-criteria decision analysis (MCDA) for objective task scoring
- **Dependency Management**: Tracks task relationships and detects circular dependencies
- **Semantic Memory**: Remembers your preferences and context across sessions
- **Adaptive Learning**: Learns from completion data and adjusts recommendations over time

### Core Principles

1. **JIT Learning**: Learning without action isn't learning - all learning tasks directly support doing
2. **Skill-Based Planning**: Tasks are matched to your current Dreyfus skill level
3. **Progressive Disclosure**: Focus on what's immediately actionable, not everything at once
4. **Dogfooding**: Built to improve itself - the first user is the project itself

## Current Status

**Version:** 0.7.0 (Active development)
**Development Stage:** Completion tracking implemented, refining pattern learning

**Recently Completed:**

- ✅ Completion tracking system with variance analysis (v0.7.0)
- ✅ CompletionRepository for completion CRUD operations (v0.7.0)
- ✅ Database schema v4 with completions table (v0.7.0)
- ✅ Orchestrator prompt documentation for completion workflows (v0.7.0)
- ✅ Semantic memory with Mem0 + Qdrant vector database (v0.6.0)
- ✅ GitHub issue integration for task import and status sync (v0.6.0)
- ✅ Web search integration via DuckDuckGo (v0.5.0)
- ✅ DAG-aware priority calculation with effective priority inheritance

**Active Development (v0.7.0+):**

- 🔄 Pattern-based duration adjustment from completion data (#20)
- 🔄 TUI with Textual for visual task management (#17)
- 🔄 Enhanced memory features and categorisation

See [Roadmap](#roadmap) for full version plan.

## Roadmap

### ✅ Completed (v0.1.0 - v0.6.0)

**Foundation:**

- ✅ SQLite database with schema versioning
- ✅ Full CRUD CLI interface (Typer + Rich)
- ✅ Pydantic models for validation
- ✅ 85%+ test coverage

**AI & Dependencies:**

- ✅ PydanticAI agent framework
- ✅ 12 agent tools (6 task management + 5 dependency + 1 web search)
- ✅ Interactive chat interface
- ✅ Optimised orchestrator prompt (1,704 lines)
- ✅ Task dependency tracking with DAG structure
- ✅ BFS-based cycle detection
- ✅ Dependency-aware task analysis

**Intelligence & Priority:**

- ✅ Intrinsic priority calculation (llm_value / duration_min)
- ✅ DAG-aware effective priority with upstream inheritance
- ✅ Requirement/conclusion dual-purpose field
- ✅ Web search integration via DuckDuckGo (v0.5.0)
- ✅ Semantic memory with Mem0 + Qdrant (v0.6.0)
- ✅ GitHub integration (v0.6.0)

### 🔄 v0.7.0: Completion Tracking & Enhanced Memory

**Goal:** Learn from completion data and improve estimates
**Timeline:** Active development (2025 Q1)

**v0.7.0 Features (Complete/In Progress):**

- ✅ **Completion Tracking** (#19) - Track estimated vs actual, variance analysis
- ✅ **CompletionRepository** - Full CRUD operations for completion records
- ✅ **Variance Analysis** - Automatic percentage variance calculation
- ✅ **Orchestrator Prompt Enhancements** - 300+ lines on completion workflows
- 🔄 **Pattern-based Duration Adjustment** - Use completion data for better estimates
- 🔄 **Enhanced Memory** - Structured memory extraction and categorisation
- 🔄 **TUI with Textual** (#17) - Visual task board with kanban-style interface
- 📋 Goal tracking and progress visualisation
- 📋 Better task recommendations based on learned patterns

### 📦 v1.0.0: Production Ready

**Goal:** Shareable, installable, documented
**Timeline:** After v0.6.0-0.7.0 complete

- 📋 Packaging (#21) - `pipx install taskweaver`
- 📋 First-run setup wizard
- 📋 Comprehensive documentation
- 📋 Cross-platform support (Linux, macOS, Windows)
- 📋 PyPI publication

### 🚀 v1.1+: Advanced Features

**Goal:** Research features and advanced intelligence
**Timeline:** Post-1.0, based on validated user needs

- 📋 Dreyfus skill tracking (#22)
- 📋 Observability & prompt tracking (#23)
- 📋 Multi-agent orchestration
- 📋 Database migrations with Alembic
- 📋 Advanced memory features (enhanced search, automatic categorisation)

See [Issue #24](https://github.com/TheRockPusher/taskweaver/issues/24) for detailed roadmap and decision criteria.

### Technical Features

- Built with [PydanticAI](https://ai.pydantic.dev/) for robust agent implementation
- Web search integration via DuckDuckGo for real-time information retrieval
- Semantic memory with [Mem0](https://docs.mem0.ai/) and [Qdrant](https://qdrant.tech/) vector database (v0.6.0)
- GitHub integration with [PyGithub](https://github.com/PyGithub/PyGithub) for issue synchronisation
- Completion tracking with variance analysis for pattern learning (v0.7.0)
- SQLite database for local-first task storage (v4 schema with completions table)
- Comprehensive dependency tracking with cycle detection (BFS-based)
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

### Interactive Chat Mode

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

**Web Search Integration:**

The agent can search the web for current information when decomposing tasks. This enables:

- Looking up current best practices and library versions
- Finding recent tutorials and documentation
- Verifying technology choices and recommendations
- Grounding task creation in up-to-date information

The web search tool is powered by DuckDuckGo and activates automatically when the agent needs current information.

**Semantic Memory (v0.6.0):**

TaskWeaver uses Mem0 with Qdrant vector database to remember context across conversations:

- **Persistent Context**: Remembers your preferences, tech stack, and past decisions
- **Local-First Storage**: All memory stored locally at `~/.local/share/taskweaver/qdrant/`
- **Semantic Search**: Retrieves relevant context automatically during conversations
- **Privacy**: No data leaves your machine - complete privacy

The memory system activates automatically, learning from your conversations to provide increasingly personalised and context-aware task recommendations.

**GitHub Integration (v0.6.0):**

Import and synchronise tasks with GitHub issues:

```bash
# The agent can import GitHub issues as tasks
# Configure with: github_repos = ["owner/repo"] in config.toml
# Status automatically syncs on PR merge or issue close
```

### CLI Task Management

```bash
# Create a task (title is required, rest optional)
uv run taskweaver create "Build authentication system" \
  --duration 120 \
  --value 85.0 \
  --req "JWT tokens working with test coverage" \
  --desc "Implement OAuth2 or JWT"

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

# Complete a task with duration tracking (v0.7.0+)
# The agent will prompt for actual duration and conclusion
# These are optional but enable pattern learning

# Delete a task
uv run taskweaver rm <task-id>
```

**Completion Tracking (v0.7.0):**

When marking tasks as completed or cancelled via the AI agent, you can provide:

- **`duration_actual`**: Actual time spent in minutes (enables variance analysis)
- **`conclusion`**: What was learned or delivered (captures insights for future tasks)

The system automatically calculates:
- **Variance (minutes)**: `duration_actual - duration_expected`
- **Variance (%)**: `(variance_minutes / duration_expected) * 100`

This data is stored in the completion record for pattern learning and future estimate improvement.

Example conversation with the agent:

```
You: "I finished the authentication task"

Agent: "Great! How long did it take? You estimated 120 minutes."

You: "It took about 90 minutes"

Agent: "✅ Completed 'Build authentication system' (120min estimated, 90min actual, -25.0% variance)"
```

### Dependency Management

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

### Value Scoring (0-100 Scale)

The system uses a standardised 0-100 value scoring scale for all tasks:

**Direct Value Tiers:**

- **90-100**: High immediate impact (critical bug fix, major feature, revenue-generating work)
- **70-89**: Substantial impact (useful functionality, noticeable improvement)
- **50-69**: Moderate impact (routine value, maintenance work)
- **30-49**: Minor impact (small improvement, exploration)
- **1-9**: Minimal impact (optional work, low priority)

**Learning Tasks (Special Handling):**

Pure learning has minimal intrinsic value because learning alone produces no deliverable. Learning derives value from what it unblocks:

- **Pure tutorials/study** (no immediate output): 10-20
- **Research with documented decision** (produces artifact): 40-50
- **Spike/prototype** (produces working code): 50-60

Learning tasks inherit priority from the work they enable via the DAG dependency system (effective priority).

**Example Priority Flow:**

```
Learning Task: "Study OAuth2 flow"
- Intrinsic value: 15 (low, it's just learning)
- Duration: 60 minutes
- Intrinsic priority: 0.25

Blocks: "Implement OAuth2 authentication"
- Implementation value: 85
- Duration: 120 minutes
- Intrinsic priority: 0.71

Result: Learning task inherits effective priority of 0.71
→ Learning becomes urgent despite low intrinsic value
```

### Configuration

TaskWeaver uses a flexible configuration system with support for multiple LLM providers and providers-specific settings for Mem0 semantic memory.

**Configuration Hierarchy (later overrides earlier):**

1. Built-in defaults
2. XDG user config (`~/.config/taskweaver/config.toml`)
3. Project-local config (`./config.toml`) - takes precedence

**Configuration Methods:**

```bash
# Option 1: Environment variables
export OPENAI_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."

# Option 2: .env file (project-local or ~/.config/taskweaver/.env)
echo "OPENAI_API_KEY=sk-..." > .env

# Option 3: config.toml (project-local or ~/.config/taskweaver/)
cat > config.toml << EOF
model = "gpt-4o-mini"
github_repos = ["owner/repo"]
EOF
```

**LLM Provider Support:**

TaskWeaver works with any LLM provider supported by PydanticAI:

```toml
# OpenAI (default)
model = "gpt-4o-mini"

# OpenRouter (multi-provider gateway)
model = "openrouter:anthropic/claude-3.5-sonnet"

# Anthropic
model = "anthropic:claude-3-5-sonnet-latest"

# Google
model = "google-genai:gemini-1.5-flash"
```

**Mem0 Semantic Memory Configuration:**

Mem0 stores and retrieves semantic memories across conversations. You can configure the LLM provider and embedding model independently from your main TaskWeaver model:

```toml
# Memory LLM provider (openai, anthropic, google, or openrouter)
mem0_llm_provider = "openai"

# Embedding model for semantic search
mem0_embedding = "text-embedding-3-small"
mem0_embedding_provider = "openai"

# Control memory retrieval (higher = more context, more tokens)
mem0_max_memories = 10  # Range: 1-100, default: 10
```

**Advanced: OpenRouter for Mem0**

Use OpenRouter as the Mem0 provider to access many LLM models through one API:

```toml
# config.toml
model = "gpt-4o-mini"  # Main model (can use any provider)

# Mem0 provider configuration
mem0_llm_provider = "openrouter"  # Automatically translates to openai provider
mem0_embedding = "text-embedding-3-small"
mem0_embedding_provider = "openai"
```

```bash
# .env
OPENAI_API_KEY="sk-..."           # For main model
OPENROUTER_API_KEY="sk-or-..."    # For Mem0 via OpenRouter
```

When you set `mem0_llm_provider = "openrouter"`:
- The provider automatically translates to `"openai"` (OpenRouter is OpenAI-compatible)
- The site_url automatically becomes `"https://openrouter.ai/api/v1"`
- You only need to provide `OPENROUTER_API_KEY`

**Custom Endpoints:**

For self-hosted models or API proxies:

```toml
# Main model endpoint
api_endpoint = "https://your-proxy.example.com/v1"

# Mem0 custom endpoint (if not using openrouter)
mem0_site_url = "https://your-proxy.example.com/v1"
```

**GitHub Integration:**

Import and sync tasks with GitHub repositories:

```toml
# config.toml
github_repos = ["TheRockPusher/taskweaver", "owner/another-repo"]
```

Requires GitHub API access (personal access token recommended for public/private repos).

### Success Metrics (MVP Targets)

The MVP implementation will aim to achieve these goals:

- Add complex tasks via conversation (no CLI flags required)
- Automatic task decomposition, gap detection, and prioritisation
- User approval and adjustment workflow before committing to database
- Learning tasks correctly unblock parent tasks
- Score inference accuracy >70% (user accepts without edits)
- Decomposition acceptance rate >70%
- System learns preferences after 20+ task completions

### Development Approach

The project is being developed using a "dogfooding" approach - TaskWeaver will be used to organise its own development. This means the project roadmap, development tasks, and progress will be managed through the system as it's being built, providing real-world validation of the approach.

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

- **Formatting**: Automated with Ruff (100 character line length)
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
│       │   ├── github_issues.py            # GitHub integration
│       │   ├── dependencies.py             # Agent dependencies container
│       │   ├── prompts/
│       │   │   └── orchestrator_prompt.md  # Agent system prompt (1,704 lines)
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
- Follow the existing code style (Google-style docstrings, 100 character line length)
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

**Privacy First**: All data stays local on your device. TaskWeaver uses SQLite for task storage and Qdrant for vector memory (v0.6.0+), both stored locally. No user data or telemetry is transmitted anywhere. Your tasks, conversations, and preferences remain completely private.

## Acknowledgments

### Core Technologies

- **AI Framework**: [PydanticAI](https://ai.pydantic.dev/) - Production-grade agent framework
- **Memory System**: [Mem0](https://docs.mem0.ai/) - Semantic memory for AI agents (v0.6.0+)
- **Vector Database**: [Qdrant](https://qdrant.tech/) - High-performance vector search engine (v0.6.0+)
- **GitHub Integration**: [PyGithub](https://github.com/PyGithub/PyGithub) - Python GitHub API client (v0.6.0+)
- **Package Manager**: [UV](https://github.com/astral-sh/uv) - Blazing fast Python package management
- **Code Quality**: [Ruff](https://github.com/astral-sh/ruff) - Lightning-fast Python linter and formatter
- **Type Checking**: [Ty](https://github.com/python/ty) - Static type analysis
- **Testing**: [pytest](https://pytest.org/) - Comprehensive Python testing framework

### Methodologies

- **Skill Assessment**: Dreyfus Model of Skill Acquisition
- **Prioritisation**: Multi-Criteria Decision Analysis (MCDA)
- **Learning Philosophy**: Just-In-Time (JIT) Learning principles
- **Dependency Management**: Directed Acyclic Graphs (DAG) with BFS cycle detection

## Links

- **Repository**: [https://github.com/TheRockPusher/taskweaver](https://github.com/TheRockPusher/taskweaver)
- **Issues**: [https://github.com/TheRockPusher/taskweaver/issues](https://github.com/TheRockPusher/taskweaver/issues)
- **Documentation**: [https://github.com/TheRockPusher/taskweaver#readme](https://github.com/TheRockPusher/taskweaver#readme)
