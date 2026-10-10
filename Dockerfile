FROM ghcr.io/astral-sh/uv:0.9.2 AS uv

FROM python:3.13-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/taskweaver
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Only packaging inputs enter the build; never copy credentials or a developer environment.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/taskweaver ./src/taskweaver
ARG TASKWEAVER_MEMORY=false
RUN case "$TASKWEAVER_MEMORY" in \
      false) uv sync --locked --no-dev --no-install-project ;; \
      true) uv sync --locked --no-dev --no-install-project --extra memory ;; \
      *) echo 'TASKWEAVER_MEMORY must be true or false' >&2; exit 1 ;; \
    esac \
    && uv build --no-sources --wheel \
    && uv pip install --python /opt/taskweaver/.venv/bin/python --no-deps dist/*.whl

FROM python:3.13-slim AS runtime
ENV PATH=/opt/taskweaver/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    XDG_CONFIG_HOME=/data/config \
    XDG_DATA_HOME=/data/data \
    XDG_CACHE_HOME=/data/cache \
    XDG_STATE_HOME=/data/state
RUN groupadd --gid 1000 taskweaver \
    && useradd --uid 1000 --gid taskweaver --create-home taskweaver \
    && mkdir -p /data/config /data/data /data/cache /data/state \
    && chown -R taskweaver:taskweaver /data
COPY --from=build /opt/taskweaver/.venv /opt/taskweaver/.venv
USER taskweaver
WORKDIR /home/taskweaver
VOLUME ["/data"]
ENTRYPOINT ["taskweaver"]
