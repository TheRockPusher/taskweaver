# Configuration and data

Use `taskweaver setup` in an interactive terminal, or edit flat TOML preferences and a separate `.env`. `taskweaver info` shows resolved paths/model and task counts without printing keys. See [README.md](README.md) for product workflows.

## Resolution and native locations

Preferences merge **defaults → user config → detected project config**. Project detection walks upward from the working directory and stops at a directory containing `config.toml`, `tasks.db`, `pyproject.toml`, or `.git`; it is not limited to the current directory. Existing project `config.toml`/`.env` are preferred for setup writes. User secrets load before project secrets; explicit process environment variables win over file values. Environment interpolation in secret files is disabled.

Each native root gains a `taskweaver` subdirectory:

| Platform | Config | Data | Cache | State/logs |
| --- | --- | --- | --- | --- |
| Linux | `~/.config` | `~/.local/share` | `~/.cache` | `~/.local/state` |
| macOS | `~/Library/Application Support` | same | `~/Library/Caches` | `~/Library/Logs` |
| Windows | `%APPDATA%` | `%LOCALAPPDATA%` | `%LOCALAPPDATA%` | `%LOCALAPPDATA%` |

`XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, and `XDG_STATE_HOME` override the corresponding roots on every platform. Config files are `config.toml` and `.env`; the database is `tasks.db`; logs are `taskweaver.log` in state. Optional Qdrant storage is `qdrant_store` beside the selected database. The optional Mem0 SDK state defaults to application data unless `MEM0_DIR` is explicitly supplied. Native path selection is implemented; that is not evidence of native OS execution.

Database precedence is command-local `--db`, root `--db`, configured `database_file`, an existing detected-project `tasks.db`, then native data. The selected database also determines the semantic vector/history directory for CLI memory and CLI/TUI chat; an explicit override does not silently use the configured database's store. A relative TOML `database_file` is anchored to that TOML file's directory (and `~` expands). A relative CLI path is relative to the invocation directory.

## Models and credentials

The wizard defaults to `offline:none`. Built-in preferences without a config file instead default to `openai:gpt-4o-mini`, but no model is constructed until requested. Local CLI/TUI task workflows never require a cloud key.

| `llm_model` prefix | Credential | Endpoint |
| --- | --- | --- |
| `offline:none` | None | AI disabled |
| `local:MODEL` | Optional `TASKWEAVER_API_KEY` | Required OpenAI-compatible URL |
| `openai:MODEL` | `OPENAI_API_KEY` | Defaults to `https://api.openai.com/v1` |
| `openrouter:PROVIDER/MODEL` | `OPENROUTER_API_KEY` | Defaults to `https://openrouter.ai/api/v1` |
| `anthropic:MODEL` | `ANTHROPIC_API_KEY` | Defaults to `https://api.anthropic.com` |
| `google-genai:MODEL` (also `google`) | `GOOGLE_API_KEY` | Provider default unless overridden |

`api_endpoint` is honored by the shared request-time provider constructor, including delegated agents. Model names must be available on your selected service. An anonymous local endpoint example:

```toml
llm_model = "local:your-model-alias"
api_endpoint = "http://127.0.0.1:8080/v1"
memory_enabled = false
```

Leave `TASKWEAVER_API_KEY` unset or empty for anonymous local requests: no Authorization header is sent and cloud keys are not borrowed. Configure a key if that local endpoint requires authentication. Main LLM and embedding services are separate; a chat endpoint does not imply embedding support.

Setup preserves unrelated preferences/keys and replaces each saved file atomically. POSIX temporary/final files have mode `0600`; newly created parent directories request `0700`. Existing parent directories are not recursively hardened. Config and secrets are separate file replacements, not a cross-file transaction. Secrets are plaintext on disk, not an encrypted vault/keychain. Windows files inherit directory ACLs; POSIX modes are **not** equivalent Windows protection. Restrict ACLs yourself. Protect database, semantic stores, backups, and logs too; never commit `.env` or pass secrets as Docker build arguments.

## Preference reference

Copy the existing [config.toml.example](config.toml.example) as a starting point; it is offline and disables external backends.

| Key | Default / behavior |
| --- | --- |
| `llm_model` | `openai:gpt-4o-mini`; wizard default offline |
| `api_endpoint` | Unset; provider default except required for local |
| `database_file` | Unset; path resolution above |
| `user_id` | `default`; scopes explicit memory |
| `github_repos` | `[]`; default repositories for imports |
| `github_sync_interval_seconds` | `3600`, minimum 30; configured-repository TUI read-only sync interval |
| `memory_enabled` | `false`; optional semantic backend only |
| `mem0_llm_provider` | `openai`; `local`/`openrouter` translate to compatible SDK provider, Google names to Gemini |
| `mem0_llm_model` | Unset; explicit memory provider:model can be configured independently |
| `mem0_site_url` | Unset; separate memory LLM endpoint; OpenRouter has a gateway default |
| `mem0_embedding_provider` | `openai` |
| `mem0_embedding` | `text-embedding-3-small` |
| `mem0_embedding_endpoint` | Unset; independent embedding-service URL |
| `mem0_max_memories` | `10`, allowed 1–100 |

MCDA weights are database-backed (`weights show/set`), not TOML aliases. All five custom weights must be finite, nonnegative, and sum to one. UI shortcuts and sorting are not configurable TOML fields.

## Explicit optional boundaries

**Memory:** local facts work without extras. For semantic memory install `[memory]`, enable `memory_enabled`, and configure a real LLM **and** embedding provider/model/endpoint plus their credentials. Anthropic has no embedding service; select another provider for that role. Local semantic services each require their own reachable endpoint. Optional provider failure does not revoke authoritative local facts. Logical forget/tombstones do not securely erase SQLite free pages, backups, provider histories, or chat transcripts.

**Observability:** install `[observability]`, configure `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST`, then explicitly use `taskweaver chat --o` or `taskweaver tui --o`. Merely setting keys does not enable tracing. Opt-in instrumentation can export model prompts, responses, and tool data; review your provider/retention policy before enabling it. Default application logging is not intended to capture private conversation content.

**GitHub:** `GH_TOKEN` takes precedence over `GITHUB_TOKEN`; absent a token, public reads may work subject to GitHub limits. Configured `github_repos` enables TUI read-only imports/pulls on mount and periodically via `github_sync_interval_seconds`; overlapping jobs are skipped and owned processes are cancelled on exit. CLI imports/sync remain explicit. Configuration never authorizes remote writes: only `github sync --push` requests status writes. Use minimally scoped credentials and inspect conflicts first.

## Migration and backups

SQLite schema **6** is initialized/migrated when repositories open the database. The v4 task layout and v5 data/history are preserved through upgrade; unsupported newer schemas are rejected instead of downgraded. There is no automatic pre-upgrade backup or rollback command.

Before upgrading, stop writers and use SQLite's backup facility (example for an explicitly selected database):

```sh
sqlite3 /path/to/tasks.db ".backup '/path/to/tasks-before-upgrade.db'"
```

Alternatively copy a database only after all application connections have closed; an active database may have journal/WAL files and cannot safely be backed up by blindly copying one file. Back up semantic stores separately while their SDK clients are closed, and protect configuration/secrets separately. Restore with the application stopped, retain the original backup, and use a compatible application version. A SQLite backup alone is not a full semantic/provider-history backup.

`restartDB` preserves data while initializing/migrating. **`restartDB --delete` deletes the selected SQLite file**; it is not a secure erasure feature or a semantic-store reset. Deleting edges makes database pages reusable but does not automatically shrink the file.
