PACKAGE_VERSION := $(shell grep -m1 '^version' pyproject.toml | sed -E 's/version *= *"(.*)"/\1/')

# Capture additional arguments as FILE variable
FILE ?= $(filter-out $@,$(MAKECMDGOALS))

# Prevent make from treating arguments as targets
%:
	@:

.PHONY: install
install: ## Install the virtual environment
	@echo "🚀 Creating virtual environment using uv"
	@uv sync


.PHONY: format
format: ## Format with ruff (use FILE=path to check specific file)
	@echo "🚀 Formatting code: Running ruff format"
ifdef FILE
	@uv run ruff format $(FILE)
	@uv run ruff check --fix $(FILE)
else
	@uv run ruff format
	@uv run ruff check --fix
endif

.PHONY: format-check
format-check: ## Check code formatting with ruff format (use FILE=path to check specific file)
	@echo "🚀 Formatting code: Running ruff format"
ifdef FILE
	@uv run ruff format --check $(FILE)
else
	@uv run ruff format --check
endif

.PHONY: lint-check
lint-check: ## Lint code with ruff check (use FILE=path to check specific file)
	@echo "🚀 Linting code: Running ruff check"
ifdef FILE
	@uv run ruff check $(FILE)
else
	@uv run ruff check
endif

.PHONY: type-check
type-check: ## Run static type checking with ty (use FILE=path to check specific file)
	@echo "🚀 Static type checking: Running ty"
ifdef FILE
	@uv run ty check $(FILE)
else
	@uv run ty check
endif

.PHONY: check
check: ## Run all code quality tools (format-check, lint-check, type-check)
	@echo "🚀 Checking lock file consistency with 'pyproject.toml'"
	@uv lock --locked
	@$(MAKE) format-check
	@$(MAKE) lint-check
	@$(MAKE) type-check

.PHONY: test
test: ## Test the code with pytest (use FILE=path to test specific file)
	@echo "🚀 Testing code: Running pytest"
ifdef FILE
	@PYTHONTRACEMALLOC=20 uv run python -m pytest $(FILE)
else
	@PYTHONTRACEMALLOC=20 uv run python -m pytest
endif

.PHONY: help
help:
	@uv run python -c "import re; \
	[[print(f'\033[36m{m[0]:<20}\033[0m {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open(makefile).read(), re.M)] for makefile in ('$(MAKEFILE_LIST)').strip().split()]"

.DEFAULT_GOAL := help
