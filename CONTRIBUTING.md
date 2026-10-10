# Contributing

TaskWeaver's objective and current boundaries are in [README.md](README.md); path/provider/data safety details are in [CONFIG.md](CONFIG.md). Be respectful, report reproducible behavior, and do not include credentials or private task/chat data in reports.

## Development

Use Python 3.13+ and uv. Work on a feature branch, not directly on `main`.

```sh
uv sync --locked --all-extras
# Equivalent installation convenience: make install
uv run taskweaver --db ./development.db ls
```

`make install` installs development dependencies and optional integrations; it does not install git hooks. Default users do not need all extras or any API key.

Keep behavior in shared services/repositories rather than duplicating logic between CLI, TUI, and agent tools. Preserve explicit-null versus omitted updates, raw duration baselines, database transactions/foreign keys, user-scoped memory, cycle rejection, and deliberate external-write boundaries. Agents use request-time models; do not eagerly construct cloud clients at import. Follow existing typed, focused code and Google-style docstrings. Regression tests belong beside the existing subsystem tests (`tests/` and `src/**/tests/`).

Keep review invocations read-only at tool boundaries, not just in prompts. Duration critical-path analysis is not inherited priority or a date prediction; quick wins use CD3. Preserve single-snapshot readiness ranking across CLI/slash/tool callers. Automatic GitHub sync never pushes. UI integrations own and cancel their subprocesses, avoid overlapping syncs, preserve request/UI context across owned executor work, and close provider transports/semantic clients; test held network requests and quit behavior rather than hiding provider failures.

Recommended checks before proposing a change:

```sh
make check                  # locked dependency consistency, Ruff formatting/lint, ty
make test                   # pytest and coverage gate
# Individual checks accept FILE=path where applicable:
make test FILE=src/taskweaver/tests/test_cli.py
make format                 # deliberately modifies formatting/lint fixes
uv build --no-sources
uv tool run --from twine twine check --strict dist/*
```

These commands describe the workflow, not a claim that this branch has just passed them. The configured coverage floor is 80%; report actual output rather than badges or invented counts. Exercise offline first-run, no-key local workflows, database migrations, wheel resources, and installation outside the checkout. For providers, use disposable data/config and report the real endpoint/model exercised without revealing credentials. Fake/mocked boundaries do not establish live provider, remote-write, or native-platform success.

Observed dependency warnings are not suppressed: Qdrant's SQLite thread-safety probe opens a temporary in-memory connection without closing it (`qdrant_client/local/persistence.py`), and the locked Google SDK warns about a deprecated validator. An initial unbounded install also exposed PydanticAI 1.107.7's deprecated `Agent(instrument=...)`; that generation is outside the final compatible resolution. Report SDK versions and allocation traces rather than patching installed dependencies. Insights rendering coalesces updates on the UI queue; cancelling Markdown replacement can cancel its child widget pumps.

The supported SDK contract is OpenAI 1.x (`openai>=1.109.1,<2`), OpenTelemetry API 1.37–1.38 (`opentelemetry-api>=1.37.0,<1.39`), and optional Mem0 1.x (`mem0ai>=1.0.11,<2`). Newer OpenAI majors enforce authentication even for anonymous local endpoints; newer OpenTelemetry removes event APIs used by the compatible PydanticAI generation. Declare compatible ranges rather than fabricated local credentials or compatibility shims. Telemetry storage is conditional on the SDK telemetry setting; all actually owned clients are closed.

Anthropic is restricted to the tested 0.71 API family (`anthropic>=0.71.0,<0.72`) and Google GenAI to 1.x (`google-genai>=1.45.0,<2`). The compatible PydanticAI Anthropic adapter imports beta types removed by later SDK releases. A working locked development environment alone does not prove a fresh consumer install; exercise provider routing and cleanup with the resolved package environment.

## Dependency-retention tradeoff (#7)

Closing/cancelling a blocker deletes its outgoing edges; reopening does not reconstruct them. Closed downstream tasks can retain inactive incoming edges while a blocker remains open. This sacrifices automatic resurrection/historical edge storage in favor of retaining relationships only while their blocker remains active; task/completion history remains separate.

A supplied synthetic disk-backed SQLite benchmark used **12,000 tasks, 10,000 edges, five predecessors per target, 80% terminal blockers**, and **10,000 indexed lookups**:

| Measurement | Result |
| --- | --- |
| Filtered lookup before cleanup | 126.82 ms |
| Filtered lookup after cleanup | 126.22 ms |
| Unfiltered lookup after cleanup | 129.99 ms |
| Cleanup | 8,000 removed / 2,000 retained in 7.27 ms |
| Database pages | 148 × 4,096 bytes; 74 reusable free pages |

**No material lookup speed gain was observed.** Cleanup reclaims logical space for reuse; it does not immediately shrink the database file. The retention relation is `E = sum(outdegree(v) for active blocker v)`. An approximation `E ≈ 5*A` requires bounded active **fan-out**; five predecessors per target alone does not prove that condition. A long-lived blocker can retain edges to many closed downstream tasks until it closes. No empirical production dependency lifetime, median retention, or annual growth dataset is available. Do not present the toy relation as a measured production result.

A separate core synthetic run scored 1,000 tasks in 10.09 ms. Timing observations are environment-specific; permanent query-count regressions are more stable than universal millisecond promises.

## Safe release workflow

Package metadata is 1.0.0 on `product/taskweaver-completion`, not evidence of publication. The existing `.github/workflows/release.yml` calls CI before building, validates matching version tags, inspects wheel/source metadata and resources, installs the wheel outside the checkout, and uploads artifacts. These are configured steps, not a claim of an observed hosted run.

1. Review the changes and run the quality, migration, packaging, installed-product, and native-platform checks. Native macOS/Windows runners are required to make native validation claims.
2. Use manual release workflow dispatch with `publish=none` for build-only artifacts. Inspect them before approving publication.
3. TestPyPI publication is an explicit manual `publish=testpypi` choice using the `testpypi` environment/trusted publisher.
4. PyPI requires an existing matching `v<package-version>` tag and the `pypi` environment/trusted publisher. Manual tagged dispatch uses `publish=pypi`; tag-push publication additionally requires repository variable `PYPI_PUBLISH_ENABLED=true`. Ordinary tags do not authorize automatic publication by default.
5. Have an authorized maintainer explicitly approve tagging/pushing/publishing and configure protected environments/trusted publishers. Homebrew/AUR need released artifacts, channel ownership, and separate publication work; neither is implied by building a wheel.

Do not tag, push, publish, change remote issues, or issue live GitHub writes as a side effect of local development. Keep secrets out of distributions/build contexts. Docker runtime validation requires a Docker engine; an absent engine cannot be replaced by claiming a build passed.

## Honest roadmap reporting

Track [#7](https://github.com/TheRockPusher/taskweaver/issues/7), [#9](https://github.com/TheRockPusher/taskweaver/issues/9), [#21](https://github.com/TheRockPusher/taskweaver/issues/21), [#22](https://github.com/TheRockPusher/taskweaver/issues/22), [#24](https://github.com/TheRockPusher/taskweaver/issues/24), [#27](https://github.com/TheRockPusher/taskweaver/issues/27), and [#37](https://github.com/TheRockPusher/taskweaver/issues/37) without equating implementation to closure. Local goals/DAGs, bounded priorities, skills/JIT learning, adaptive estimates/preferences, corrective memory, CLI/TUI/GitHub interfaces, and packaging are implemented. Public distribution, native validation, authorized authenticated integration evidence, and real-user metrics remain distinct acceptance work. Daily users, estimate-within-20% rates, planning acceptance, completion rates, and longitudinal memory quality require actual users/data—not synthetic tests.
