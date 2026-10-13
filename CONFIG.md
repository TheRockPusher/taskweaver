# Configuration and data

## Setup

Run `tw setup` interactively, or copy [config.toml.example](config.toml.example) and [.env.example](.env.example). `tw` and `taskweaver` are equivalent. `tw info` reports paths, model, and counts without credentials.

The wizard/example defaults to `offline:none`. Local task management needs no key; AI models load on request.

## File locations

Each platform root below gets a `taskweaver` subdirectory.

| Platform | Config | Data | Cache | State/logs |
| --- | --- | --- | --- | --- |
| Linux | `~/.config` | `~/.local/share` | `~/.cache` | `~/.local/state` |
| macOS | `~/Library/Application Support` | `~/Library/Application Support` | `~/Library/Caches` | `~/Library/Logs` |
| Windows | `%APPDATA%` | `%LOCALAPPDATA%` | `%LOCALAPPDATA%` | `%LOCALAPPDATA%` |

`XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, and `XDG_STATE_HOME` override these roots on every platform. Set them in the process environment before launch.

- **Preferences:** defaults → user `config.toml` → project `config.toml`.
- **Secrets:** user `.env` → project `.env` → explicit process environment. Values are not interpolated.
- **Project:** nearest ancestor (including the working directory) containing `config.toml`, `tasks.db`, `pyproject.toml`, or `.git`. Setup uses existing project config/secret files, otherwise user files.
- **Database:** command-local `--db` → root `--db` → `database_file` → existing project `tasks.db` → native data `tasks.db`. TOML paths expand `~` and resolve relative to their file; CLI paths resolve relative to the working directory.

Logs: state `taskweaver.log`. Semantic storage: `qdrant_store` beside the selected database, including `--db` overrides. Mem0 SDK state: native data `mem0`, overridable with `MEM0_DIR`.

## Models & credentials

| `llm_model` | Environment credential | Default endpoint |
| --- | --- | --- |
| `offline:none` | None | AI disabled |
| `local:MODEL` | Optional `TASKWEAVER_API_KEY` | Required `api_endpoint` |
| `openai:MODEL` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `openrouter:PROVIDER/MODEL` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `anthropic:MODEL` | `ANTHROPIC_API_KEY` | `https://api.anthropic.com` |
| `google-genai:MODEL` (or `google:MODEL`) | `GOOGLE_API_KEY` | Google SDK default |

`api_endpoint` overrides the main model endpoint, including delegated agents. Local OpenAI-compatible example:

```toml
llm_model = "local:your-model-alias"
api_endpoint = "http://127.0.0.1:8080/v1"
```

Unset/empty `TASKWEAVER_API_KEY` sends no Authorization header and borrows no cloud key. Set it for authenticated local services.

## Preference reference

Flat TOML keys; “Unset” means `None` (omit the key).

| Key | Built-in default | Purpose |
| --- | --- | --- |
| `llm_model` | `"openai:gpt-4o-mini"` | Main provider:model |
| `api_endpoint` | Unset | Main model endpoint |
| `database_file` | Unset | SQLite path; precedence above |
| `user_id` | `"default"` | Scope for explicit memory |
| `github_repos` | `[]` | Repositories as `owner/repo` |
| `github_sync_interval_seconds` | `3600` | TUI read-only sync interval; minimum 30 |
| `memory_enabled` | `false` | Enable optional semantic backend |
| `mem0_llm_provider` | `"openai"` | Memory LLM provider |
| `mem0_llm_model` | Unset | Memory model; falls back to `llm_model` |
| `mem0_site_url` | Unset | Memory LLM endpoint; OpenRouter has a gateway default |
| `mem0_embedding_provider` | `"openai"` | Embedding provider |
| `mem0_embedding` | `"text-embedding-3-small"` | Embedding model |
| `mem0_embedding_endpoint` | Unset | Independent embedding endpoint |
| `mem0_max_memories` | `10` | Retrieval limit; 1–100 |

MCDA weights use SQLite (`tw weights`), not TOML. Memory maps `local`/`openrouter` to OpenAI-compatible providers, Google names to `gemini`.

## Optional integrations

### Semantic memory

Install `taskweaver[memory]` and enable `memory_enabled`. Configure LLM and embedding services/credentials separately; chat endpoints need not support embeddings. Local services require an endpoint per role; Anthropic has no embeddings. Local facts work without this backend.

`MEM0_TELEMETRY` defaults to `False`. Forgetting facts does not securely erase pages, backups, or provider history.

### Langfuse observability

Install `taskweaver[observability]`; set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST`. Only `tw chat --o` / `tw tui --o` enables tracing. Traces can export prompts, responses, and tool data; review retention.

### GitHub

`GH_TOKEN` overrides `GITHUB_TOKEN`. Public reads allow anonymous access within GitHub limits. Configured repositories pull read-only on TUI startup and periodically. Remote writes require explicit `tw github sync --push` and authorization.

## File permissions & secrets

Setup preserves unrelated settings and atomically replaces each file, not both together. POSIX files use `0600`; new TaskWeaver directories request `0700`. Ancestors follow umask; existing directories are unchanged. Restrict inherited Windows ACLs.

Secrets are plaintext. Never commit `.env` or use secrets as Docker build arguments. Protect databases, stores, logs, and backups.

## Migration & backups

Repositories initialize/migrate to **schema 6**, preserving v4/v5 data/history and rejecting newer schemas. No automatic pre-upgrade backup or rollback command exists. Stop writers before backing up:

```sh
sqlite3 /path/to/tasks.db ".backup '/path/to/tasks-before-upgrade.db'"
```

Do not blindly copy active SQLite files with journal/WAL state. Back up semantic stores with clients closed; save config/secrets separately. Restore with the app stopped and a compatible version; retain the backup.

`tw restartDB` initializes/migrates without deletion. `tw restartDB --delete` confirms before deleting the selected existing SQLite file, then creates an empty database. Semantic stores remain; deletion is not secure erasure.
