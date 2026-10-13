# Contributing

Read [README.md](README.md) for product scope and [CONFIG.md](CONFIG.md) for configuration and data safety. Report reproducible behavior without credentials or private task/chat data.

## Setup

Use Python 3.13+ and [uv](https://docs.astral.sh/uv/). Work on a feature branch.

```sh
uv sync --locked --all-extras
# Or use the development convenience target:
make install
```

`make install` runs `uv sync --all-extras` without `--locked`; it installs development dependencies and optional integrations, but no git hooks.

## Checks

| Command | Purpose |
| --- | --- |
| `make check` | Check lock consistency, Ruff formatting/lint, and ty types |
| `make test` | Run pytest with coverage and the 80% coverage floor |
| `make test FILE=src/taskweaver/tests/test_cli.py` | Run focused tests without the full-suite coverage options |
| `make format` | Apply Ruff formatting and lint fixes |
| `uv build` | Build a wheel and source distribution |

Formatting, lint, and type targets also accept `FILE=path`. For release-equivalent packaging, use `uv build --no-sources` and `uv tool run --from twine twine check --strict dist/*`.

Report the checks actually run. Exercise affected offline workflows, migrations, packaged resources, and installation outside the checkout. Use disposable data for live integrations; native-platform and Docker checks need the corresponding runner or engine.

## Architecture and conventions

- Put shared behavior in services under `src/taskweaver/database/` and `src/taskweaver/agents/`. CLI, TUI, and agent tools call those services instead of duplicating business logic.
- Keep code focused and typed, with Google-style docstrings. Preserve omitted-versus-null updates, raw duration baselines, transactions, foreign keys, cycle rejection, and user-scoped memory.
- Keep tests beside their subsystems in `src/taskweaver/**/tests/`. Test behavior and state changes, not exact wording unless the text is a public contract.
- Keep blocking UI work off the event loop. Cancel and reap owned subprocesses on shutdown; close owned provider transports and semantic clients.
- Construct provider models at request time. Keep review tools read-only at their write boundaries, not only through prompts.
- Automatic GitHub sync never pushes. External writes require explicit user authorization.

The [calculator reference](docs/calculator.md) describes the agent arithmetic interface and limits.

## Dependency pins

Keep the compatibility ranges in `pyproject.toml` aligned with the service adapters. When changing them, exercise provider routing and cleanup in the resolved environment, including anonymous local endpoints.

| Package | Range | Reason |
| --- | --- | --- |
| `pydantic-ai-slim[openai,anthropic,google,duckduckgo]` | `>=1.1.0,<2` | Keep the 1.x agent/provider contract with only the selected integrations |
| `openai` | `>=1.109.1,<2` | Preserve empty-key support for anonymous local endpoints |
| `anthropic` | `>=0.71.0,<0.72` | Keep beta types used by the compatible PydanticAI adapter |
| `google-genai` | `>=1.45.0,<2` | Keep the 1.x client and provider cleanup API |
| `opentelemetry-api` | `>=1.37.0,<1.39` | Retain event APIs used by the compatible PydanticAI generation |
| `mem0ai` (memory extra) | `>=1.0.11,<2` | Keep the optional semantic-memory adapter on its 1.x API |
| `uv_build` (build backend) | `>=0.9.2,<0.10.0` | Keep the distribution backend in the configured 0.9 family |

## Dependency-retention tradeoff (#7)

Closing or cancelling a blocker deletes its outgoing dependency edges; reopening does not restore them. Closed downstream tasks can retain incoming edges until their blocker closes. This favors active relationships over historical edge storage; task and completion history are separate.

A supplied synthetic disk-backed SQLite benchmark used **12,000 tasks, 10,000 edges, five predecessors per target, 80% terminal blockers**, and **10,000 indexed lookups**:

| Measurement | Result |
| --- | --- |
| Filtered lookup before cleanup | 126.82 ms |
| Filtered lookup after cleanup | 126.22 ms |
| Unfiltered lookup after cleanup | 129.99 ms |
| Cleanup | 8,000 removed / 2,000 retained in 7.27 ms |
| Database pages | 148 × 4,096 bytes; 74 reusable free pages |

No material lookup speed gain was observed. Cleanup makes logical space reusable without immediately shrinking the file. Retained edges equal the sum of active blockers' outgoing edges; `E ≈ 5*A` requires bounded active fan-out, not merely five predecessors per target. A long-lived blocker can retain many edges. These synthetic timings do not measure production retention or growth.

## Release workflow

1. Review changes and run the applicable checks above. Keep secrets out of distributions and build contexts.
2. Dispatch [.github/workflows/release.yml](.github/workflows/release.yml) with `publish=none` for build-only artifacts. The workflow runs CI, builds with Python 3.13 and uv 0.9.2, validates tag/version agreement, inspects metadata/resources, exercises the installed wheel outside the checkout, and uploads artifacts.
3. Inspect the artifacts. For TestPyPI, dispatch with `publish=testpypi`; publication uses the `testpypi` environment and trusted publishing.
4. For PyPI, use an existing `v<package-version>` tag matching `pyproject.toml` and dispatch with `publish=pypi`. Tag-push publication is enabled only when `PYPI_PUBLISH_ENABLED=true`. Publication uses the `pypi` environment and trusted publishing.
5. Have an authorized maintainer approve tagging, pushing, and publishing, and configure protected environments and trusted publishers. Homebrew/AUR publication is separate work.

Do not tag, push, publish, or change remote issues as a side effect of local development. Track remaining work in [GitHub issues](https://github.com/TheRockPusher/taskweaver/issues).
