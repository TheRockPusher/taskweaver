"""Interactive setup with offline defaults and securely persisted preferences."""

import os
import sys
import tempfile
import tomllib
from pathlib import Path

import tomli_w
from dotenv import dotenv_values, set_key
from rich.console import Console
from rich.prompt import Confirm, Prompt

from .config import Config, get_config, get_paths

console = Console()
_PROVIDERS = {
    "0": ("Offline (local task management)", "offline", "", ""),
    "1": ("OpenAI", "openai", "gpt-4o-mini", "https://api.openai.com/v1"),
    "2": ("OpenRouter", "openrouter", "anthropic/claude-sonnet-4", "https://openrouter.ai/api/v1"),
    "3": ("Anthropic", "anthropic", "claude-sonnet-4-20250514", "https://api.anthropic.com"),
    "4": ("Google", "google-genai", "gemini-2.5-flash", "https://generativelanguage.googleapis.com"),
    "5": ("Local / OpenAI-compatible", "local", "llama3.2", "http://localhost:11434/v1"),
}
_KEYS = {
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google-genai": "GOOGLE_API_KEY",
    "google": "GOOGLE_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "local": "TASKWEAVER_API_KEY",
}


def _secure_write(path: Path, content: str, secrets: dict[str, str] | None = None) -> None:
    """Replace a file atomically; the temporary and final POSIX mode is 0600."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        if secrets:
            for key, value in secrets.items():
                set_key(temporary, key, value, quote_mode="always")
        if os.name != "nt":
            temporary_path.chmod(0o600)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _secret(provider: str, existing: dict[str, str | None], updates: dict[str, str]) -> bool:
    variable = _KEYS[provider]
    current = existing.get(variable) or os.environ.get(variable)
    suffix = " (blank for anonymous)" if provider == "local" else " (blank keeps existing)" if current else ""
    value = Prompt.ask(f"{variable}{suffix}", password=True, default="").strip()
    if "\n" in value or "\r" in value:
        console.print("[red]API keys must be a single line.[/red]")
        return False
    if provider == "local" or value:
        updates[variable] = value
    elif not current:
        console.print(
            f"[red]{variable} is required for this cloud provider. "
            "Choose offline or local to use TaskWeaver without it.[/red]"
        )
        return False
    return True


def run_first_time_setup(*, force: bool = False) -> bool:
    """Return True after configuration, False on skip/non-TTY/cancellation.

    Noninteractive startup never reads input. Offline setup is fully configured
    even without an env file. Windows permissions inherit the directory ACL;
    POSIX 0600 is not claimed to provide equivalent Windows ACL protection.
    """
    if not sys.stdin.isatty() or not console.is_terminal:
        return False
    try:
        return _run_setup(force=force)
    except (EOFError, KeyboardInterrupt):
        console.print("\nSetup cancelled; existing configuration is unchanged.")
        return False


def _run_setup(*, force: bool) -> bool:  # noqa: PLR0911, PLR0912, PLR0915
    paths = get_paths()
    config_file = paths.config_file
    env_file = paths.env_file
    if config_file.is_file() and not force and not Confirm.ask("Reconfigure TaskWeaver?", default=False):
        return True
    current = get_config()
    data = tomllib.loads(config_file.read_text(encoding="utf-8")) if config_file.is_file() else {}
    existing_keys = dotenv_values(env_file, interpolate=False) if env_file.is_file() else {}
    secrets: dict[str, str] = {}
    console.print("\n[bold cyan]TaskWeaver setup[/bold cyan]\nLocal task management never requires an API key.")
    for choice, (label, _, _, _) in _PROVIDERS.items():
        console.print(f"  {choice}: {label}")
    console.print("  6: Skip")
    choice = Prompt.ask("Provider", choices=[*_PROVIDERS, "6"], default="0")
    if choice == "6":
        return False
    _, provider, default_model, default_endpoint = _PROVIDERS[choice]
    data["llm_model"] = "offline:none"
    if provider != "offline":
        prior_provider, _, prior_model = current.llm_model.partition(":")
        model = Prompt.ask(
            "Model",
            default=prior_model if prior_provider == provider and prior_model else default_model,
        ).strip()
        endpoint = Prompt.ask(
            "API endpoint",
            default=current.api_endpoint if prior_provider == provider and current.api_endpoint else default_endpoint,
        ).strip()
        if not model or not endpoint:
            console.print("[red]A model and endpoint are required.[/red]")
            return False
        data.update(llm_model=f"{provider}:{model}", api_endpoint=endpoint)
        if not _secret(provider, existing_keys, secrets):
            return False
    database = Prompt.ask("SQLite database path", default=str(paths.database_file)).strip()
    if not database:
        console.print("[red]A database path is required.[/red]")
        return False
    database_path = Path(database).expanduser()
    data["database_file"] = str(
        database_path if database_path.is_absolute() else (config_file.parent / database_path).resolve()
    )
    repositories = Prompt.ask(
        "GitHub repositories (comma-separated owner/repo; blank disables)",
        default=",".join(current.github_repos),
    ).strip()
    data["github_repos"] = [repo.strip() for repo in repositories.split(",") if repo.strip()]
    if data["github_repos"]:
        github_key = Prompt.ask("GITHUB_TOKEN (optional; blank keeps existing)", password=True, default="").strip()
        if "\n" in github_key or "\r" in github_key:
            console.print("[red]GitHub tokens must be a single line.[/red]")
            return False
        if github_key:
            secrets["GITHUB_TOKEN"] = github_key
    data["memory_enabled"] = Confirm.ask(
        "Enable optional semantic memory backend? (requires memory extra and embedding service)",
        default=False,
    )
    if data["memory_enabled"]:
        for role in ("LLM", "embedding"):
            default = (
                current.mem0_llm_model or "openai:gpt-4o-mini"
                if role == "LLM"
                else f"{current.mem0_embedding_provider}:{current.mem0_embedding}"
            )
            selected = Prompt.ask(f"Memory {role} provider:model", default=default).strip()
            memory_provider, separator, memory_model = selected.partition(":")
            if not separator or not memory_model or memory_provider not in _KEYS:
                console.print("[red]Use an explicit supported provider:model for memory.[/red]")
                return False
            if role == "embedding" and memory_provider == "anthropic":
                console.print(
                    "[red]Anthropic does not provide an embedding service. Choose a separate "
                    "local, OpenAI, OpenRouter, or Gemini embedding service.[/red]"
                )
                return False
            if memory_provider in {"google", "google-genai"}:
                memory_provider = "gemini"
            endpoint = Prompt.ask(
                f"Memory {role} endpoint (local requires its own service URL)",
                default=(current.mem0_site_url if role == "LLM" else current.mem0_embedding_endpoint) or "",
            ).strip()
            if memory_provider == "local" and not endpoint:
                console.print("[red]Local memory requires a real endpoint for each service.[/red]")
                return False
            if _KEYS[memory_provider] not in secrets and not _secret(memory_provider, existing_keys, secrets):
                return False
            if role == "LLM":
                data.update(mem0_llm_model=selected, mem0_llm_provider=memory_provider)
                data.pop("mem0_site_url", None)
                if endpoint:
                    data["mem0_site_url"] = endpoint
            else:
                data.update(mem0_embedding=memory_model, mem0_embedding_provider=memory_provider)
                data.pop("mem0_embedding_endpoint", None)
                if endpoint:
                    data["mem0_embedding_endpoint"] = endpoint
    Config(**data)
    _secure_write(config_file, tomli_w.dumps(data))
    if secrets:
        previous = env_file.read_text(encoding="utf-8") if env_file.is_file() else ""
        _secure_write(env_file, previous, secrets)
        os.environ.update(secrets)
    get_config.cache_clear()
    get_paths.cache_clear()
    get_config()
    if os.name == "nt":
        console.print(
            "Secrets inherit the directory's Windows ACL. Restrict that ACL to your account; "
            "chmod is not Windows access control."
        )
    console.print("[green]Configuration saved. Local task management is ready.[/green]")
    return True


def check_configuration() -> bool:
    """Offline/local preferences count as configured; a cloud key is not required."""
    return get_paths().config_file.is_file()
