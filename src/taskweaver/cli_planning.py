"""Local planning commands and shared CLI rendering/error boundaries."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Error as SQLiteError
from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .config import get_paths
from .database.exceptions import DependencyError, TaskNotFoundError
from .database.models import CompletionStatus, TaskStatus, TaskUpdate
from .database.planning import PlanningService
from .database.priority_service import PriorityService, PriorityWeights
from .database.repository import TaskRepository

console = Console()
app = typer.Typer(help="Goals, skills, and evidence-based planning")
goals = typer.Typer(help="Manage goals and linked task progress")
skills = typer.Typer(help="Record evidence-backed skill assessments")
weights = typer.Typer(help="Inspect or customize MCDA weights")
app.add_typer(goals, name="goals")
app.add_typer(skills, name="skills")
app.add_typer(weights, name="weights")
DB = Annotated[Path | None, typer.Option("--db", help="Database file path (overrides root --db)")]


def resolve_db(ctx: typer.Context, db_path: Path | None) -> Path:
    """Resolve command override, root override, then fresh configured location."""
    if db_path is not None:
        return db_path
    root = ctx.find_root()
    if isinstance(root.obj, dict) and root.obj.get("db") is not None:
        return root.obj["db"]
    return get_paths().database_file


@contextmanager
def command_errors() -> Iterator[None]:
    """Turn expected domain/storage failures into useful nonzero command errors."""
    try:
        yield
    except (ValueError, RuntimeError, OSError, SQLiteError, TaskNotFoundError, DependencyError) as exc:
        console.print(f"Error: {exc}", style="red", markup=False)
        raise typer.Exit(1) from exc


def render_priority(service: PriorityService, task_id: UUID, *, history: bool = True) -> None:
    """Display exact service contributions, inherited score, trend, and changed events."""
    explanation = service.explain(task_id)
    console.print(f"MCDA: {explanation['score']:.1f}/100; inherited: {explanation['effective_score']:.1f}/100")
    console.print(
        f"Trend: {service.trend(task_id)}; weights: {explanation['preference_source']}; "
        f"learning samples: {explanation['learning_samples']}"
    )
    table = Table(title="Priority components (contributions in score points)")
    for heading in ("Factor", "Raw", "Normalized", "Weight", "Contribution", "Visual"):
        table.add_column(heading)
    for name, component in explanation["components"].items():
        table.add_row(
            name,
            repr(component["raw"]),
            repr(component["normalized"]),
            repr(component["weight"]),
            repr(component["contribution"]),
            "█" * round(component["contribution"] / 2),
        )
    console.print(table)
    if history:
        events = service.history(task_id)
        table = Table(title="Changed-score history")
        table.add_column("Recorded at")
        table.add_column("MCDA")
        table.add_column("Visual")
        for event in events:
            table.add_row(event["recorded_at"], str(event["score"]), "█" * round(event["score"] / 5))
        console.print(table)


@app.command()
def score(ctx: typer.Context, task_id: UUID, db_path: DB = None) -> None:
    """Explain a task's current MCDA score without mutating history."""
    with command_errors():
        render_priority(PriorityService(resolve_db(ctx, db_path)), task_id)


@app.command(name="recalc-priorities")
def recalculate(ctx: typer.Context, status: TaskStatus | None = None, db_path: DB = None) -> None:
    """Persist changed MCDA scores (active tasks by default)."""
    with command_errors():
        count = PriorityService(resolve_db(ctx, db_path)).update_all_priorities(status)
        console.print(f"Updated {count} priority score(s)")


@app.command()
def focus(ctx: typer.Context, limit: Annotated[int, typer.Option(min=0)] = 10, db_path: DB = None) -> None:
    """Rank dependency- and skill-ready work; show learning gaps separately."""
    with command_errors():
        path = resolve_db(ctx, db_path)
        tasks = PriorityService(path).get_top_priorities(limit, match_skills=True)
        table = Table(title="Actionable focus")
        for heading in ("ID", "Title", "Estimate", "MCDA"):
            table.add_column(heading)
        for task in tasks:
            table.add_row(str(task.task_id), Text(task.title), f"{task.duration_min}m", str(task.priority_score))
        console.print(table)
        gaps = PlanningService(path).recommendations().learning_gaps
        table = Table(title="Learning gaps (not actionable work)")
        for heading in ("Task", "Assessed", "Required", "Reason"):
            table.add_column(heading)
        repo = TaskRepository(path)
        for gap in gaps:
            task = repo.get_task(gap.task_id)
            table.add_row(
                Text(task.title if task else str(gap.task_id)),
                str(gap.known_level),
                str(gap.required_level),
                gap.reason,
            )
        console.print(table)


@app.command()
def complete(
    ctx: typer.Context,
    task_id: UUID,
    actual: Annotated[int, typer.Option("--actual", min=1, help="Actual minutes spent")],
    conclusion: str | None = None,
    db_path: DB = None,
) -> None:
    """Atomically complete a task, record actual time, and release its dependencies."""
    with command_errors():
        result = PlanningService(resolve_db(ctx, db_path)).complete_task(task_id, actual, conclusion)
        console.print(
            f"Completed {result.task_id}: {result.duration_actual}m actual; {result.duration_expected}m expected"
        )


@app.command()
def cancel(
    ctx: typer.Context,
    task_id: UUID,
    actual: Annotated[int | None, typer.Option("--actual", min=1, help="Actual minutes, if known")] = None,
    conclusion: str | None = None,
    db_path: DB = None,
) -> None:
    """Cancel and release dependencies; without --actual, no duration evidence is recorded."""
    with command_errors():
        path = resolve_db(ctx, db_path)
        if actual is None:
            if conclusion is not None:
                raise ValueError("--conclusion requires --actual when cancelling")
            TaskRepository(path).update_task(task_id, TaskUpdate(status=TaskStatus.CANCELLED))
        else:
            PlanningService(path).complete_task(task_id, actual, conclusion, CompletionStatus.CANCELLED)
        console.print(f"Cancelled {task_id}")


@goals.command(name="create")
def create_goal(ctx: typer.Context, title: str, description: str | None = None, db_path: DB = None) -> None:
    """Create a named goal."""
    with command_errors():
        goal = PlanningService(resolve_db(ctx, db_path)).create_goal(title, description)
        console.print(f"Created goal {goal.goal_id}: {goal.title}", markup=False)


@goals.command(name="list")
def list_goals(ctx: typer.Context, db_path: DB = None) -> None:
    """List goals with progress, excluding cancelled work from the denominator."""
    with command_errors():
        service = PlanningService(resolve_db(ctx, db_path))
        table = Table(title="Goals")
        for heading in ("ID", "Title", "Completed/total", "Progress", "Cancelled"):
            table.add_column(heading)
        for goal in service.list_goals():
            progress = service.goal_progress(goal.goal_id)
            table.add_row(
                str(goal.goal_id),
                Text(goal.title),
                f"{progress.completed}/{progress.total}",
                f"{progress.fraction:.0%}",
                str(progress.cancelled),
            )
        console.print(table)


@goals.command(name="show")
@goals.command(name="progress")
def show_goal(ctx: typer.Context, goal_id: UUID, db_path: DB = None) -> None:
    """Show a goal, description, and linked-task progress."""
    with command_errors():
        progress = PlanningService(resolve_db(ctx, db_path)).goal_progress(goal_id)
        console.print(f"{progress.goal.goal_id}: {progress.goal.title}", markup=False)
        console.print(progress.goal.description or "", markup=False)
        console.print(
            f"{progress.completed}/{progress.total} completed ({progress.fraction:.0%}); {progress.cancelled} cancelled"
        )


@goals.command(name="edit")
def edit_goal(
    ctx: typer.Context,
    goal_id: UUID,
    title: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
    db_path: DB = None,
) -> None:
    """Edit supplied fields; --clear-description intentionally removes the description."""
    with command_errors():
        if description is not None and clear_description:
            raise ValueError("Use either --description or --clear-description")
        if title is None and description is None and not clear_description:
            raise ValueError("Specify at least one goal field")
        service = PlanningService(resolve_db(ctx, db_path))
        goal = service.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")
        description = None if clear_description else description if description is not None else goal.description
        goal = service.update_goal(goal_id, title, description)
        console.print(f"Updated goal {goal.goal_id}: {goal.title}", markup=False)


@goals.command(name="delete")
def delete_goal(ctx: typer.Context, goal_id: UUID, db_path: DB = None) -> None:
    """Delete the goal and unlink, without deleting its tasks."""
    with command_errors():
        PlanningService(resolve_db(ctx, db_path)).delete_goal(goal_id)
        console.print(f"Deleted goal {goal_id}")


@goals.command(name="link")
def link_goal(
    ctx: typer.Context, task_id: UUID, goal_id: UUID | None = None, clear: bool = False, db_path: DB = None
) -> None:
    """Link TASK_ID --goal-id UUID, or explicitly unlink with --clear."""
    with command_errors():
        if (goal_id is None) == (not clear):
            raise ValueError("Specify either --goal-id or --clear")
        task = PlanningService(resolve_db(ctx, db_path)).link_task(task_id, goal_id)
        console.print(f"Task {task.task_id}: goal {task.goal_id}")


@skills.command(name="set")
def set_skill(
    ctx: typer.Context,
    domain: str,
    level: Annotated[int, typer.Argument(min=1, max=5)],
    evidence: Annotated[str, typer.Option(help="Evidence supporting the assessment")],
    db_path: DB = None,
) -> None:
    """Append a skill assessment with evidence, retaining history."""
    with command_errors():
        skill = PlanningService(resolve_db(ctx, db_path)).set_skill(domain, level, evidence)
        console.print(f"{skill.domain}: level {int(skill.level)} — {skill.evidence}", markup=False)


@skills.command(name="list")
def list_skills(ctx: typer.Context, db_path: DB = None) -> None:
    """Show latest evidence-backed assessments."""
    with command_errors():
        for skill in PlanningService(resolve_db(ctx, db_path)).list_skills():
            console.print(
                f"{skill.domain}: level {int(skill.level)}; {skill.assessed_at.isoformat()}; {skill.evidence}",
                markup=False,
            )


@skills.command(name="history")
def skill_history(ctx: typer.Context, domain: str, db_path: DB = None) -> None:
    """Show chronological evidence and corrections for one domain."""
    with command_errors():
        for skill in PlanningService(resolve_db(ctx, db_path)).skill_history(domain):
            console.print(f"{skill.assessed_at.isoformat()}: level {int(skill.level)}; {skill.evidence}", markup=False)


@app.command()
def insights(
    ctx: typer.Context,
    category: str | None = None,
    baseline: Annotated[int, typer.Option(min=1)] = 30,
    db_path: DB = None,
) -> None:
    """Show category duration ratios, sample counts, and descriptive confidence."""
    with command_errors():
        service = PlanningService(resolve_db(ctx, db_path))
        observed = {insight.category: insight for insight in service.insights()}
        categories = [category] if category is not None else list(observed)
        table = Table(title="Category duration evidence (MAD is ratio dispersion)")
        for heading in ("Category", "Raw → adjusted", "Multiplier", "Samples", "Median", "MAD", "Automatic"):
            table.add_column(heading)
        for name in categories:
            estimate = service.estimate(name, baseline)
            confidence = estimate.confidence
            table.add_row(
                Text(name),
                f"{baseline}m → {estimate.adjusted_minutes}m",
                str(estimate.multiplier),
                str(estimate.sample_count),
                str(confidence.median_ratio),
                str(confidence.median_absolute_deviation),
                str(confidence.automatic_adjustment),
            )
            if name in observed:
                insight = observed[name]
                console.print(f"{name}: {insight.completed} completed; {insight.cancelled} cancelled", markup=False)
        console.print(table)


@app.command()
def analysis(
    ctx: typer.Context,
    max_minutes: Annotated[int, typer.Option(min=1)] = 30,
    limit: Annotated[int, typer.Option(min=0)] = 5,
    db_path: DB = None,
) -> None:
    """Show the working-duration critical path and ready CD3 quick wins."""
    with command_errors():
        result = PlanningService(resolve_db(ctx, db_path)).work_analysis(max_minutes, limit)
        console.print(f"Critical path: {result.critical_path_minutes}m")
        console.print("Unlimited parallel capacity; excludes skill-learning time; not completion dates.")
        console.print(
            " → ".join(f"{task.task_id} ({task.duration_min}m)" for task in result.critical_path) or "(empty)"
        )
        table = Table(title=f"Ready quick wins (≤{max_minutes}m; CD3, not MCDA)")
        for heading in ("ID", "Title", "Duration", "Value/min"):
            table.add_column(heading)
        for task in result.quick_wins:
            table.add_row(str(task.task_id), Text(task.title), f"{task.duration_min}m", f"{task.priority:.3f}")
        console.print(table)


@weights.command(name="show")
def show_weights(ctx: typer.Context, db_path: DB = None) -> None:
    """Display current exact MCDA weights."""
    with command_errors():
        for name, weight in PriorityService(resolve_db(ctx, db_path)).weights.model_dump().items():
            console.print(f"{name}: {weight}")


@weights.command(name="set")
def set_weights(
    ctx: typer.Context,
    urgency: Annotated[float, typer.Option()],
    importance: Annotated[float, typer.Option()],
    effort: Annotated[float, typer.Option()],
    dependencies: Annotated[float, typer.Option()],
    age: Annotated[float, typer.Option()],
    db_path: DB = None,
) -> None:
    """Persist all five finite, nonnegative weights; they must sum to one."""
    with command_errors():
        values = PriorityWeights(
            urgency=urgency, importance=importance, effort=effort, dependencies=dependencies, age=age
        )
        PriorityService(resolve_db(ctx, db_path)).adjust_weights(values)
        console.print("Saved custom priority weights")
