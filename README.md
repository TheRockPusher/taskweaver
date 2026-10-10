# TaskWeaver

Local-first goal planning: turn an objective into an actionable task DAG, surface ready work, identify just-in-time learning needs, and improve estimates from recorded completions. AI is optional; task management works without credentials or a network.

**Status:** package metadata is **1.0.0** on `product/taskweaver-completion`; this branch is not a published release. Python 3.13+; AGPL-3.0 ([LICENSE](LICENSE)). No claim of native macOS/Windows validation, public package publication, or live authenticated GitHub writes is implied.

## Start locally

From a checkout with [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked
uv run taskweaver --version
uv run tw setup
uv run tw
```

`taskweaver` and `tw` are equivalent installed entry points. In an interactive terminal, no arguments run first-time setup if needed, then launch the TUI. Noninteractive no-argument invocation prints help. Setup defaults to offline; `tw tui` opens the local workspace directly. Use `tw --help` and `tw COMMAND --help` for the full interface.

To install this checkout as a tool, use `uv tool install .`; optional integrations are `uv tool install '.[memory]'`, `'.[observability]'`, or `'.[memory,observability]'`. Development equivalents are `uv sync --extra memory` and `uv sync --extra observability`. These extras install SDKs, not model services or credentials. Do not assume that a public index already contains this branch's version.

## Local workflow

Replace UUID placeholders with IDs printed by create/list/show commands:

```sh
tw --db ./work.db goals create "Ship a useful tool"
tw --db ./work.db create "Prototype CLI" --duration 30 --value 80 --req "Usable offline" --category coding --urgency 4 --importance 5
tw --db ./work.db ls --sort score --limit 10
tw --db ./work.db show TASK_UUID --explain-priority
tw --db ./work.db createDep DOWNSTREAM_UUID BLOCKER_UUID
tw --db ./work.db goals link TASK_UUID --goal-id GOAL_UUID
tw --db ./work.db skills set python 3 --evidence "Built and reviewed a working CLI"
tw --db ./work.db edit TASK_UUID --domain python --required-skill-level 3
tw --db ./work.db focus
tw --db ./work.db analysis --max-minutes 30 --limit 5
tw --db ./work.db complete TASK_UUID --actual 45 --conclusion "Ready for review"
tw --db ./work.db insights --category coding --baseline 30
```

Root `--db` sets the command default; command-local `--db` overrides it. `edit` preserves omitted fields; `--clear-description`, `--clear-goal`, `--clear-domain`, and `--clear-required-skill-level` explicitly remove nullable values. Other commands include `rm`, `lso`, `blocker`, `rmdep`, `cancel`, `score`, `recalc-priorities`, `weights show/set`, and goals/skills history and management. Cancellation without actual time is not duration evidence.

### Planning, priority, and learning

- Goals link tasks and report progress; cancelled tasks are excluded from the denominator. Deleting a goal unlinks, rather than deletes, its tasks.
- Dependencies reject cycles. Closing a blocker removes its outgoing blocking edges; reopening it does not resurrect them. Edges into a closed downstream task can remain inactive until their blocker closes.
- **MCDA** is a bounded weighted score: urgency .30, importance .35, inverse effort .15, dependencies .10, age .10. `ls --sort score` orders intrinsic MCDA; `--sort priority` orders inherited MCDA. `show --explain-priority` exposes components, weights, effective score, and trend. **CD3** is the separate value/minute metric (`--sort cd3`), not an alias for MCDA.
- `focus`, `/focus`, and agent recommendations rank dependency- and skill-ready work by inherited MCDA; `ls --match-skills` filters readiness while retaining its chosen sort. Dreyfus levels 1–5 represent novice through expert; assessments retain evidence/history. Completion never automatically promotes a skill. Learning gaps guide just-in-time learning rather than marking blocked work ready.
- Category estimates use the median actual/raw-duration ratio after at least three valid samples. The original baseline prevents compounded adjustment. Confidence reports sample count, median, and median absolute deviation; it is descriptive evidence, not a calibrated success probability.
- Completion-derived priority preferences require at least 20 valid completions; explicitly chosen weights remain protected. No real-user accuracy or productivity improvement is claimed.
- `analysis` finds the longest working-duration path in the active DAG, assuming unlimited independent parallel capacity. It excludes skill-learning time and resource constraints and predicts no dates. Ready quick wins are dependency-/skill-matched, at most 30 minutes by default, and ordered by descending **CD3**, not MCDA (`--max-minutes`, `--limit`).

## Terminal workspace

Five views share the same SQLite/services as the CLI:

| Key | View | Purpose |
| --- | --- | --- |
| `1` | List | Task state, duration, intrinsic/effective MCDA, CD3 |
| `2` | Board | Status columns with numeric MCDA prefixes |
| `3` | Graph | Active blocker → blocked DAG, readiness, duration critical path |
| `4` | Chat | Optional AI and local slash commands |
| `5` | Insights | Goals, skill evidence, learning gaps, duration confidence, quick wins |

`Ctrl+Tab` cycles views; `j/k` move, `Enter` opens detail, `Space` starts/pauses, `n/e` create/edit, `c/x` complete/cancel, `d` edits dependencies, `f` toggles focus, `g` creates a goal, `s` records a skill assessment, `r` refreshes, and `q`/`Ctrl+C` quit. Chat uses `Ctrl+Enter` or `F2` to send. Text editing and modal dialogs take precedence over workspace shortcuts. Selection is retained by task identity across refreshes.

MCDA colors are red at ≥70, yellow at ≥40, and green below 40; numeric values remain visible, including when `NO_COLOR` disables colors. Completion dialogs require actual minutes rather than silently using estimates. Cancelling with unknown actual time leaves the actual field blank and records no completion-learning sample; a conclusion requires an actual duration.

## Conversation and memory

`tw chat` and the Chat view share these commands:

- `/plan GOAL` creates a goal and linked tasks through planning tools.
- `/breakdown DESCRIPTION` decomposes work and dependencies.
- `/review TASK_UUID` loads real task, scoring, dependency, and skill context for read-only AI review; mutating tools and research-side issue imports are denied for that invocation.
- `/focus`, `/help [command]`, `/memories [CATEGORY]` are local.
- `/github [OWNER/REPO ...]` imports issues; never pushes.
- `/remember [--category CATEGORY] [--expires ISO_TIMESTAMP] KEY=VALUE` and `/forget KEY` explicitly manage facts.

Unknown commands and malformed arguments fail locally. Command-specific instructions apply only to their invocation; ordinary conversation history is retained. Planning, breakdown, review, and ordinary conversation require a configured model. Provider failures are reported, not represented as successful work. Numerical tools use bounded arithmetic, not model guesses; see the [calculator reference](.agents/plans/add-calculator-tool-for-agents.md).

Memory categories are `preference`, `skill`, `goal`, and `context`. Local facts are authoritative and user-scoped; updates, expiry, and tombstones prevent stale retrieval. `tw memory remember/list/update/search/forget/expire` work locally by default. Optional semantic memory adds provider IDs with `semantic-list`, `semantic-update`, and `semantic-forget`; it requires explicit configuration and the `memory` extra. Chat does not blindly extract/store every utterance. Retrieved memory is untrusted context. Forgetting is logical deletion, not secure physical erasure or deletion of every provider record, backup, or conversation history.

## GitHub integration

```sh
tw github import OWNER/REPO --state open
tw github sync OWNER/REPO
# Only when you intend and are authorized to change remote issue state:
tw github sync OWNER/REPO --push
```

Durable repository/issue mappings make repeated pulls idempotent. Pulls reconcile title, description, and status against the last common snapshot, retaining divergent edits as reported conflicts (nonzero CLI exit). Local planning fields remain local. Explicit `--push` writes only unconflicted status changes—not titles, descriptions, comments, or new issues. Public reads can be anonymous; authenticated operations use `GH_TOKEN` or `GITHUB_TOKEN`. Inspect conflicts and resolve the underlying field before retrying. No authenticated remote-write validation is claimed here.

With `github_repos` configured, the TUI imports open issues and pulls mapped issues on startup and periodically (default 3,600 seconds; minimum configurable interval 30 seconds). Automatic sync is **read-only**, skips overlapping work, and runs in an owned cancellable process so exit does not wait on remote backoff. It never substitutes for explicit push authorization.

## Architecture and data safety

Typer CLI and Textual TUI → shared planning/priority/memory/GitHub services → repositories → SQLite. PydanticAI orchestrates task and research agents only on demand; delegated runs share the request's event loop and model, and model transports close after each turn. TOML preferences and environment credentials select request-time providers; Mem0/Qdrant and Langfuse are opt-in boundaries, not startup requirements. Enabled semantic memory in the TUI uses an owned cancellable process to keep provider waits off the UI loop.

See [CONFIG.md](CONFIG.md) for native OS paths, anonymous local endpoints, credential permissions, optional memory/observability, schema migration, and backups. Schema 6 upgrades older databases including v4/v5 while preserving data; newer unsupported schemas are refused. Make an explicit backup before upgrade. `restartDB` initializes/migrates; **`restartDB --delete` destroys the selected database**.

### Docker

The image installs the built wheel, runs as UID/GID 1000, and keeps native-path overrides under `/data`. It does not bake in credentials or probe provider connectivity.

```sh
docker compose build
docker compose run --rm taskweaver setup
docker compose run --rm taskweaver tui
docker compose run --rm taskweaver ls
# Optional semantic SDKs at build time:
TASKWEAVER_MEMORY=true docker compose build
```

Compose retains `/data` in a named volume. Host bind mounts must be writable by UID 1000. Pass secrets only at runtime (for example a protected `--env-file`), never as build arguments. A container-local `localhost` endpoint is not the host's endpoint; configure reachable networking explicitly. The observability extra is not included by this Docker build option. These are usage instructions, not evidence of a Docker-engine run.

## Evidence and open work

A core synthetic benchmark scored 1,000 tasks in **10.09 ms**; this is not a production SLA. Dependency retention measurements and limitations are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

These issue links track the broader work; implemented code does **not** imply issue closure:

| Tracking | Implemented here / remaining evidence |
| --- | --- |
| [#7](https://github.com/TheRockPusher/taskweaver/issues/7) | Active-blocker edge cleanup; production dependency lifetimes remain unmeasured |
| [#9](https://github.com/TheRockPusher/taskweaver/issues/9) | Bounded MCDA, weights, rankings, explanations, trends and completion-based preferences; real-user priority agreement unmeasured |
| [#21](https://github.com/TheRockPusher/taskweaver/issues/21) | Installable package, `tw` alias and first-run setup; publication, Homebrew/AUR and native validation remain external |
| [#22](https://github.com/TheRockPusher/taskweaver/issues/22) | Evidence-backed Dreyfus skills and learning-gap matching; real-user learning outcomes unmeasured |
| [#24](https://github.com/TheRockPusher/taskweaver/issues/24) | Five-view TUI, automatic read-only GitHub pulls, goals, completion-adaptive estimates, critical paths and quick wins; roadmap accuracy/adoption metrics require real users |
| [#27](https://github.com/TheRockPusher/taskweaver/issues/27) | Invocation-scoped planning, read-only review, breakdown, focus and help; provider quality requires evaluation |
| [#37](https://github.com/TheRockPusher/taskweaver/issues/37) | Categorized corrective memory, forgetting, expiry and optional semantic retrieval; longitudinal retrieval quality unmeasured |

The roadmap is validation and distribution, not fabricated usage statistics: native runners, approved releases/channel maintainers, authorized live integration checks, and real completion histories. See [CONTRIBUTING.md](CONTRIBUTING.md) for development and safe release procedures.
