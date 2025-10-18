# [TaskWeaver](https://github.com/TheRockPusher/taskweaver)

AI task master agent

This is a [Python](https://www.python.org/) library and command-line tool built using [UV](https://github.com/astral-sh/uv) (a fast Python package manager) and released under the [AGPL-3.0 License](LICENSE).

**Target Audience:** Python developers, command-line users, and software engineers looking for a modern, well-structured Python project foundation.

**Project Status:** Version 0.1.0 (initial release)

[![CI](https://github.com/TheRockPusher/taskweaver/actions/workflows/ci.yml/badge.svg)](https://github.com/TheRockPusher/taskweaver/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL-3.0-blue.svg)](LICENSE)
## Getting Started

This section will help you get up and running with TaskWeaver quickly.

### Quick Start

```bash
# Install UV if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install TaskWeaver
make install taskweaver

# Use it in your code
uv run ...
```

### Full Documentation

- **Installation Guide**: See [Installation](#installation) section below
- **Usage Examples**: See [Usage](#usage) section below
- **Contributing**: See [Contributing](#contributing) section below
- **API Reference**: Coming soon

## Why TaskWeaver?

This project was created to ai task master agent. It aims ...:

- ...
- ...

The goal is to ...

## Features

- Modern Python packaging with [UV](https://github.com/astral-sh/uv) - 10-100× faster than traditional tools
- `src/` layout for better project structure and testing isolation
- Comprehensive code quality tools:
  - [Ruff](https://github.com/astral-sh/ruff) for linting and formatting (replaces Flake8, isort, Black)
  - [Ty](https://github.com/python/ty) for static type checking
  - [pytest](https://pytest.org/) with coverage reporting (80% minimum coverage enforced)
- Pre-commit hooks for automated code quality checks on every commit
- GitHub Actions CI/CD workflows with matrix testing across Python versions
- Automated releases with version bumping and changelog generation

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
# Install from PyPI (when published)
uv pip install taskweaver

# Install from source
git clone https://github.com/TheRockPusher/taskweaver.git
cd taskweaver
uv sync
```

## Usage

### Basic Usage

...

### More Examples

For more detailed usage examples and API documentation, see the [examples](examples/) directory in the repository (coming soon).

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

```
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

This is an individual/community open source project created to ai task master agent. It is not affiliated with any corporate entity or commercial service offering. The software does not transmit any user data or telemetry off the device on which it runs.

## Acknowledgments

- Built with [UV](https://github.com/astral-sh/uv) - Fast Python package manager (10-100× faster than pip)
- Linting and formatting by [Ruff](https://github.com/astral-sh/ruff) - An extremely fast Python linter and formatter
- Type checking with [Ty](https://github.com/python/ty) - Static type checker for Python
- Testing with [pytest](https://pytest.org/) - A mature full-featured Python testing framework

## Links

- **Repository**: [https://github.com/TheRockPusher/taskweaver](https://github.com/TheRockPusher/taskweaver)
- **Issues**: [https://github.com/TheRockPusher/taskweaver/issues](https://github.com/TheRockPusher/taskweaver/issues)
- **Documentation**: [https://github.com/TheRockPusher/taskweaver#readme](https://github.com/TheRockPusher/taskweaver#readme)
