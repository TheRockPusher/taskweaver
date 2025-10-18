# Contributing to TaskWeaver

Thank you for considering contributing to TaskWeaver! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful and inclusive. We aim to create a welcoming environment for all contributors.

## Getting Started

### Prerequisites

- Python 3.13 or higher
- [UV](https://github.com/astral-sh/uv) package manager
- Git

### Setup Development Environment

1. **Fork and Clone**

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/taskweaver.git
cd taskweaver
```

2. **Install Dependencies**

```bash
# Install the project with development dependencies
make install

# This will:
# - Create a virtual environment with uv
# - Install all dependencies
# - Install pre-commit hooks
```

3. **Create a Branch**

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## Development Workflow

### Making Changes

1. **Write Code**
   - Follow the existing code style
   - Add type hints to all functions
   - Write Google-style docstrings
   - Keep functions focused and testable

2. **Write Tests**
   - Add tests for new features in `tests/`
   - Ensure tests are clear and descriptive
   - Aim for high code coverage (minimum 80%)

3. **Run Quality Checks**

```bash
# Format code
make format

# Run all quality checks (format, lint, type-check)
make check

# Run tests
make test

# Run specific test file
make test FILE=tests/test_specific.py
```

### Code Quality Standards

#### Formatting (Ruff)
- Line length: 120 characters
- Automatic formatting with `make format`
- Pre-commit hooks will auto-format on commit

#### Linting (Ruff)
- Comprehensive rule set including:
  - PEP 8 style (E, W, F)
  - Import sorting (I)
  - Security checks (S - Bandit)
  - Code simplification (SIM)
  - Best practices (B, PT, PL)
- Run: `make lint-check`

#### Type Checking (Ty)
- All functions must have type hints
- Run: `make type-check`

#### Testing (pytest)
- Minimum 80% coverage required
- Tests fail if coverage drops
- Use fixtures for setup/teardown
- Descriptive test names: `test_function_does_something_when_condition()`

#### Docstrings
- Google-style docstrings required
- Include Args, Returns, Raises sections
- Example:

```python
def example_function(value: str, count: int = 1) -> str:
    """Return the value repeated count times.

    Args:
        value: The string to repeat.
        count: Number of times to repeat. Defaults to 1.

    Returns:
        The repeated string.

    Raises:
        ValueError: If count is negative.

    """
    if count < 0:
        raise ValueError("count must be non-negative")
    return value * count
```

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:
- Ruff formatting
- Ruff linting with auto-fix

If hooks fail:
1. Review the changes
2. Stage the auto-fixed files: `git add .`
3. Commit again

To run hooks manually:
```bash
uv run pre-commit run --all-files
```

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add new feature X
fix: resolve issue with Y
docs: update README installation instructions
test: add tests for Z
refactor: simplify function W
chore: update dependencies
```

## Pull Request Process

1. **Ensure Quality**
   ```bash
   make check  # All checks must pass
   make test   # All tests must pass
   ```

2. **Update Documentation**
   - Update README.md if adding features
   - Add docstrings to new code
   - Update CHANGELOG.md (if exists)

3. **Submit PR**
   - Push your branch to your fork
   - Open a Pull Request against `master` branch
   - Fill out the PR template
   - Link any related issues

4. **PR Review**
   - Maintainers will review your code
   - Address feedback by pushing new commits
   - Once approved, your PR will be merged

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] All tests pass (`make test`)
- [ ] Code coverage is maintained/improved
- [ ] Type hints are present and correct
- [ ] Docstrings are complete and accurate
- [ ] No linting errors (`make check`)
- [ ] Commit messages are clear
- [ ] Documentation is updated
- [ ] PR description explains changes

## Running CI Locally

The CI pipeline runs automatically on GitHub, but you can verify locally:

```bash
# Run all quality checks (same as CI)
make check

# Run tests with coverage (same as CI)
make test
```

## Project Structure

```bash
taskweaver/
├── src/taskweaver/  # Main package code
├── tests/                               # Test suite
├── .github/workflows/                   # CI/CD configuration
├── pyproject.toml                       # Project metadata and tool config
├── Makefile                             # Development commands
└── .pre-commit-config.yaml             # Pre-commit hook configuration
```

## Reporting Issues

### Bug Reports

Include:

- Clear description of the bug
- Steps to reproduce
- Expected vs actual behaviour
- Python version and OS
- Relevant error messages/tracebacks

### Feature Requests

Include:

- Clear description of the feature
- Use case / motivation
- Proposed implementation (if you have ideas)

## Questions?

- Open an issue with the `question` label
- Check existing issues and documentation first

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 License.

## Thank You

Your contributions make TaskWeaver better for everyone. We appreciate your time and effort!
