# TaskWeaver Configuration Guide

TaskWeaver follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) for configuration, making it a well-behaved Linux citizen.

## Configuration Hierarchy

TaskWeaver loads configuration in this order (later overrides earlier):

1. **Built-in defaults** - Hardcoded fallback values
2. **XDG user config** (`~/.config/taskweaver/config.toml`) - System-wide user preferences
3. **Project-local config** (`./config.toml`) - **Takes precedence!** (for development)

This means you can have both a system-wide config for general use AND project-specific overrides when working in a cloned repository.

## Directory Structure

```
# Project-local (for development)
./config.toml                      # Project-specific preferences (gitignored)
./.env                             # Project API keys (gitignored)
./tasks.db                         # Optional local database (gitignored)

# XDG user directories (system-wide)
~/.config/taskweaver/
├── config.toml          # User preferences (model selection, display settings)
└── .env                 # API keys (secrets - gitignored)

~/.local/share/taskweaver/
└── tasks.db             # SQLite database (application data)

~/.cache/taskweaver/
└── (future: LLM cache)

~/.local/state/taskweaver/
└── taskweaver.log       # Application logs
```

## Configuration Files

### 1. User Preferences (`~/.config/taskweaver/config.toml`)

Copy `config.toml.example` from the repository to get started:

```bash
cp config.toml.example ~/.config/taskweaver/config.toml
```

**Example configuration:**

```toml
# Simple, flat configuration - no nested sections!

# LLM model name
model = "gpt-4o-mini"

# API endpoint URL (OpenAI, Anthropic, local, or custom)
api_endpoint = "https://api.openai.com/v1"

# Automatically decompose complex tasks into subtasks
auto_decompose = true
```

### 2. API Keys (`~/.config/taskweaver/.env`)

Copy `.env.example` from the repository:

```bash
cp .env.example ~/.config/taskweaver/.env
```

**Add your API keys:**

```bash
# OpenAI API Key (required for OpenAI models)
OPENAI_API_KEY=sk-...

# Anthropic API Key (required for Claude models)
ANTHROPIC_API_KEY=sk-ant-...
```

**⚠️ Security Note:** Never commit `.env` files to version control!

### 3. Project-Local Configuration (Development)

**For Developers**: When working on TaskWeaver itself or contributing, you can create local config files in the project root:

```bash
cd /path/to/taskweaver

# Create local config (overrides your XDG config)
cp config.toml.example config.toml

# Create local .env (overrides your XDG .env)
cp .env.example .env

# Add your dev API keys
echo "OPENAI_API_KEY=sk-dev-..." >> .env
```

**How it works:**

- TaskWeaver detects project roots by looking for `pyproject.toml` or `.git/`
- If `./config.toml` exists, it **overrides** settings from `~/.config/taskweaver/config.toml`
- If `./tasks.db` exists, it will be used instead of `~/.local/share/taskweaver/tasks.db`
- Perfect for testing without affecting your system-wide tasks!

**Example use case:**

```toml
# ~/.config/taskweaver/config.toml (system-wide)
model = "gpt-4"
api_endpoint = "https://api.openai.com/v1"

# ./config.toml (project-local override)
model = "gpt-4o-mini"  # Cheaper model for development
```

When running from the project directory, TaskWeaver will use `gpt-4o-mini` (local) instead of `gpt-4` (system).

**⚠️ Gitignore Note:** Local `config.toml`, `.env`, and `tasks.db` are gitignored to prevent accidentally committing dev secrets.

## Environment Variable Overrides

You can override XDG directories using environment variables:

```bash
# Override config directory (default: ~/.config)
export XDG_CONFIG_HOME=/custom/config

# Override data directory (default: ~/.local/share)
export XDG_DATA_HOME=/custom/data

# Override cache directory (default: ~/.cache)
export XDG_CACHE_HOME=/custom/cache

# Override state directory (default: ~/.local/state)
export XDG_STATE_HOME=/custom/state
```

## CLI Flags

All commands support the `--db` flag to override the database path:

```bash
taskweaver create "Test task" --db /tmp/test.db
taskweaver ls --db /tmp/test.db
```

## Complete Configuration Hierarchy

Settings are loaded in this order (later overrides earlier):

1. **Built-in defaults** (hardcoded in `config.py`)
2. **XDG user config** (`~/.config/taskweaver/config.toml`)
3. **Project-local config** (`./config.toml`) - **overrides XDG settings**
4. **Environment variables** (`XDG_*` for paths only)
5. **CLI flags** (`--db` for temporary overrides)

**Example:**

```toml
# ~/.config/taskweaver/config.toml
model = "gpt-4"
api_endpoint = "https://api.openai.com/v1"
auto_decompose = true

# ./config.toml (in project directory)
model = "claude-3-5-sonnet-20241022"  # Overrides "gpt-4"
api_endpoint = "https://api.anthropic.com/v1"  # Overrides OpenAI endpoint
# auto_decompose stays true from XDG config
```

Result: Uses Claude model with Anthropic endpoint, auto-decompose enabled.

## Accessing Configuration in Code

```python
from taskweaver.config import get_config, get_paths

# Get configuration (cached)
config = get_config()
print(config.model)  # "gpt-4o-mini"
print(config.api_endpoint)  # "https://api.openai.com/v1"
print(config.auto_decompose)  # True

# Get XDG paths (cached)
paths = get_paths()
print(paths.database_file)  # PosixPath('/home/user/.local/share/taskweaver/tasks.db')
print(paths.project_root)  # PosixPath('/path/to/project') or None
```

## Migration from Old Path

If you used TaskWeaver before XDG compliance, migrate your data:

```bash
# Old location
OLD_DB="~/.taskweaver/tasks.db"

# New location
NEW_DB="~/.local/share/taskweaver/tasks.db"

# Copy database
mkdir -p ~/.local/share/taskweaver
cp $OLD_DB $NEW_DB

# Remove old directory (optional)
rm -rf ~/.taskweaver
```

## Troubleshooting

### Database Not Found

If you see "Database does not exist" errors, check permissions:

```bash
# Verify data directory is writable
ls -la ~/.local/share/taskweaver/

# Create manually if needed
mkdir -p ~/.local/share/taskweaver
```

### API Keys Not Working

Verify your `.env` file is in the correct location:

```bash
# Should be here:
cat ~/.config/taskweaver/.env

# Not here:
cat .env  # ❌ (project root - wrong!)
```

### Custom Model Not Available

Check your `config.toml` syntax:

```bash
# Validate TOML syntax
python3 -c "import tomllib; tomllib.load(open('~/.config/taskweaver/config.toml', 'rb'))"
```

## Best Practices

1. **Version control your config.toml** - It's safe to share (no secrets)
2. **Never commit .env files** - Use `.gitignore`
3. **Use environment variables in CI/CD** - Don't rely on files in automated environments
4. **Back up your database** - `~/.local/share/taskweaver/tasks.db` contains all your tasks

## Further Reading

- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
- [TOML Specification](https://toml.io/)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
