"""Real SQLite/Textual workflows, with no mocked app or chat worker."""

import asyncio
import threading

import pytest
from rich.console import Console
from rich.text import Text
from textual.widgets import Button, DataTable, Input, Label, Select, Static, TabbedContent, TabPane, TextArea

from taskweaver.database.connection import init_database
from taskweaver.database.models import TaskCreate, TaskStatus, TaskUpdate
from taskweaver.tui import TaskWeaverApp
from taskweaver.tui.screens import TaskDetailScreen, TaskFormScreen


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "TASKWEAVER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    database = tmp_path / "workspace.db"
    init_database(database)
    return TaskWeaverApp(database)


def create(app, title, **fields):
    return app.task_repo.create_task(
        TaskCreate(title=title, duration_min=30, llm_value=60, requirement="Deliver the outcome", **fields)
    )


def fill(app, **fields):
    for name, value in fields.items():
        app.screen.query_one(f"#{name}", Input).value = str(value)


async def select_task(app, pilot, task_id):
    table = app.query_one("#task-table", DataTable)
    table.focus()
    table.move_cursor(row=table.get_row_index(str(task_id)))
    await pilot.pause()


async def wait_choices(app, pilot):
    async with asyncio.timeout(3):
        while any(selector.disabled for selector in app.screen.query(Select)):
            await pilot.pause(0.01)


async def save_form(app, pilot):
    """Click Save and return once that attempt has finished: dismissed on success, error shown on failure."""
    await wait_choices(app, pilot)
    screen = app.screen
    error = screen.query_one("#form-error", Static)
    error.update("")
    # press() avoids pointer hit-testing, which can miss after an error message reflows the dialog.
    screen.query_one("#save", Button).press()
    async with asyncio.timeout(5):
        while app.screen is screen and not str(error.content):
            await pilot.pause(0.01)


async def test_local_create_edit_clear_and_score_detail_without_keys(app):
    goal = app.planning.create_goal("Ship a useful product")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("n")
        fill(
            app,
            **{
                "task-title": "Write release notes",
                "task-requirement": "Explain all user-facing changes",
                "task-description": "Full notes",
                "task-duration_min": 45,
                "task-llm_value": 90,
                "task-urgency": 5,
                "task-importance": 4,
                "task-effort": 2,
                "task-category": "writing",
                "task-skill_domain": "writing",
                "task-required_skill_level": 2,
            },
        )
        await wait_choices(app, pilot)
        app.screen.query_one("#task-goal_id", Select).value = str(goal.goal_id)
        await save_form(app, pilot)
        await pilot.pause()
        task = next(task for task in app.task_repo.list_tasks() if task.title == "Write release notes")
        assert (task.urgency, task.importance, task.effort, task.category) == (5, 4, 2, "writing")
        assert (task.goal_id, task.skill_domain, task.required_skill_level) == (goal.goal_id, "writing", 2)
        await pilot.press("e")
        fill(
            app,
            **{
                "task-title": "Publish release notes",
                "task-description": "",
                "task-skill_domain": "",
                "task-required_skill_level": "",
                "task-duration_min": 60,
            },
        )
        await wait_choices(app, pilot)
        app.screen.query_one("#task-goal_id", Select).value = Select.BLANK
        await save_form(app, pilot)
        await pilot.pause()
        updated = app.task_repo.get_task(task.task_id)
        assert updated.title == "Publish release notes"
        assert (updated.description, updated.goal_id, updated.skill_domain, updated.required_skill_level) == (None,) * 4
        assert (updated.duration_min, updated.raw_duration_min) == (60, 45)
        await pilot.press("enter")
        assert isinstance(app.screen, TaskDetailScreen)
        assert app.screen.task_data.task_id == task.task_id
        assert str(task.task_id) in app.screen.details
        assert "Explain all user-facing changes" in app.screen.details


async def test_invalid_creation_keeps_fields_and_reports_repair(app):
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("n")
        fill(app, **{"task-title": "Keep my draft", "task-requirement": "Deliver", "task-duration_min": 0})
        await save_form(app, pilot)
        assert isinstance(app.screen, TaskFormScreen)
        assert app.screen.query_one("#task-title", Input).value == "Keep my draft"
        assert app.screen.query_one("#form-error", Static).content
        assert app.task_repo.list_tasks() == []
        fill(app, **{"task-duration_min": 20})
        await save_form(app, pilot)
        saved = app.task_repo.list_tasks()[0]
        assert (saved.title, saved.duration_min) == ("Keep my draft", 20)


async def test_selection_survives_priority_reorder_and_view_navigation(app):
    first = create(app, "High urgency", urgency=5)
    selected = create(app, "Selected task", urgency=1)
    async with app.run_test(size=(80, 24)) as pilot:
        await select_task(app, pilot, selected.task_id)
        app.task_repo.update_task(selected.task_id, TaskUpdate(urgency=5, importance=5, effort=1))
        app.refresh_tasks()
        await pilot.pause()
        table = app.query_one("#task-table", DataTable)
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == str(selected.task_id)
        await pilot.press("2")
        assert app.query_one("#views", TabbedContent).active == "board-view"
        board = app.query_one("#board-pending", DataTable)
        assert board.coordinate_to_cell_key(board.cursor_coordinate).row_key.value == str(selected.task_id)
        await pilot.press("ctrl+tab")
        assert app.query_one("#views", TabbedContent).active == "graph-view"
        await pilot.press("1", "j", "enter")
        assert app.screen.task_data.task_id == first.task_id
        await pilot.press("escape", "k", "enter")
        assert app.screen.task_data.task_id == selected.task_id


async def test_dependency_workflow_rejects_cycle_and_completion_releases_focus(app):
    blocker = create(app, "Prepare environment")
    dependent = create(app, "Run experiment", skill_domain="science", required_skill_level=3)
    async with app.run_test(size=(80, 24)) as pilot:
        await select_task(app, pilot, dependent.task_id)
        await pilot.press("d")
        await wait_choices(app, pilot)
        app.screen.query_one("#dependency-blocker", Select).value = str(blocker.task_id)
        await save_form(app, pilot)
        await pilot.pause()
        assert [task.task_id for task in app.dep_repo.get_blockers(dependent.task_id)] == [blocker.task_id]
        await pilot.press("3")
        graph = str(app.query_one("#dependency-graph", Static).render())
        assert f"Prepare environment [{str(blocker.task_id)[:8]}] → Run experiment" in graph
        assert "Learning gap → Run experiment" in graph
        await pilot.press("1")
        await select_task(app, pilot, blocker.task_id)
        await pilot.press("d")
        await wait_choices(app, pilot)
        app.screen.query_one("#dependency-blocker", Select).value = str(dependent.task_id)
        await save_form(app, pilot)
        assert app.dep_repo.get_blockers(blocker.task_id) == []
        assert app.screen.query_one("#dependency-blocker", Select).value == str(dependent.task_id)
        await pilot.press("escape", "space")
        await pilot.pause()
        assert app.task_repo.get_task(blocker.task_id).status == TaskStatus.IN_PROGRESS
        await pilot.press("c")
        fill(app, **{"actual-minutes": 50, "conclusion": "Environment ready"})
        await save_form(app, pilot)
        await pilot.pause()
        completion = app.completions.get_completion_by_task_id(blocker.task_id)
        assert (completion.duration_actual, completion.conclusion) == (50, "Environment ready")
        assert app.dep_repo.get_blockers(dependent.task_id) == []
        await pilot.press("f")
        table = app.query_one("#task-table", DataTable)
        assert list(table.rows) == []
        app.planning.set_skill("science", 3, "Independently conducted experiments")
        app.refresh_tasks()
        await pilot.pause()
        assert table.get_row(str(dependent.task_id))[0].plain == "Run experiment"
        await pilot.press("space")
        await pilot.pause()
        assert app.task_repo.get_task(dependent.task_id).status == TaskStatus.IN_PROGRESS


async def test_dependency_remove_and_cancel_are_durable(app):
    blocker = create(app, "Draft")
    dependent = create(app, "Publish")
    app.dep_repo.add_dependency(dependent.task_id, blocker.task_id)
    async with app.run_test(size=(80, 24)) as pilot:
        await select_task(app, pilot, dependent.task_id)
        await pilot.press("d")
        await wait_choices(app, pilot)
        app.screen.query_one("#dependency-blocker", Select).value = str(blocker.task_id)
        app.screen.query_one("#dependency-operation", Select).value = "remove"
        await save_form(app, pilot)
        await pilot.pause()
        assert app.dep_repo.get_blockers(dependent.task_id) == []
        await pilot.press("x")
        fill(app, **{"actual-minutes": 5, "conclusion": "No longer needed"})
        await save_form(app, pilot)
        await pilot.pause()
        assert app.task_repo.get_task(dependent.task_id).status == TaskStatus.CANCELLED
        assert app.completions.get_completion_by_task_id(dependent.task_id).conclusion == "No longer needed"


async def test_goal_skill_and_category_learning_surface(app):
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("g")
        fill(app, **{"planning-name": "Release", "planning-evidence": "Ship to users"})
        await save_form(app, pilot)
        await pilot.pause()
        goal = app.planning.list_goals()[0]
        await pilot.press("s")
        fill(
            app,
            **{"planning-name": "engineering", "planning-level": 3, "planning-evidence": "Built production systems"},
        )
        await save_form(app, pilot)
        await pilot.pause()
        assert app.planning.skill_history("engineering")[0].evidence == "Built production systems"
        for index in range(3):
            task = create(app, f"Release {index}", goal_id=goal.goal_id, category="engineering")
            app.planning.complete_task(task.task_id, 60, "Delivered")
        create(app, "Needs expert review", skill_domain="engineering", required_skill_level=4)
        app.refresh_tasks()
        await pilot.press("5")
        await pilot.pause()
        text = "\n".join(panel.source for panel in app.query(".insight-panel"))
        assert "Release**: 3/3 (100%)" in text
        assert "engineering · level 3" in text
        assert "Built production systems" in text
        assert "samples 3, median actual/raw 2.0" in text
        assert "automatic adjustment on" in text
        assert "60/30 min actual/expected" in text
        assert "Needs expert review" in text


async def test_shared_local_chat_help_focus_and_shutdown_without_provider(app):
    task = create(app, "Ready without cloud")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("4")
        text = app.query_one("#input-field", TextArea)
        text.text = "/focus"
        await pilot.press("ctrl+enter")
        for _ in range(20):
            await pilot.pause(0.05)
            if str(task.task_id) in str(app.query_one("#notice", Static).render()):
                break
            if any("Ready without cloud" in widget.source for widget in app.query("#chat-view Markdown")):
                break
        assert any("Ready without cloud" in widget.source for widget in app.query("#chat-view Markdown"))
        text.text = "/help"
        await pilot.press("ctrl+enter")
        for _ in range(20):
            await pilot.pause(0.05)
            if any(
                "/review" in widget.source and "/focus" in widget.source for widget in app.query("#chat-view Markdown")
            ):
                break
        assert any(
            "/review" in widget.source and "/focus" in widget.source for widget in app.query("#chat-view Markdown")
        )
        text.text = "/not-a-command"
        await pilot.press("ctrl+enter")
        for _ in range(20):
            await pilot.pause(0.05)
            if "unknown" in str(app.query_one("#notice", Static).render()).lower():
                break
        assert "unknown" in str(app.query_one("#notice", Static).render()).lower()
        await pilot.press("ctrl+tab")
        assert app.query_one("#views", TabbedContent).active == "insights-view"
    assert app.chat_handler.should_exit


async def test_cancellation_with_unknown_effort_releases_edges_without_learning(app):
    blocker = create(app, "Cancelled experiment")
    downstream = create(app, "Replacement experiment")
    app.dep_repo.add_dependency(downstream.task_id, blocker.task_id)
    async with app.run_test(size=(80, 24)) as pilot:
        await select_task(app, pilot, blocker.task_id)
        await pilot.press("x")
        fill(app, **{"actual-minutes": "", "conclusion": "Unsupported learning evidence"})
        await save_form(app, pilot)
        assert app.task_repo.get_task(blocker.task_id).status == TaskStatus.PENDING
        assert app.dep_repo.get_blockers(downstream.task_id)[0].task_id == blocker.task_id
        fill(app, conclusion="")
        await save_form(app, pilot)
        assert app.task_repo.get_task(blocker.task_id).status == TaskStatus.CANCELLED
        assert app.dep_repo.get_blockers(downstream.task_id) == []
        assert app.completions.get_completion_by_task_id(blocker.task_id) is None
        assert app.planning.insights() == []


async def test_rapid_refresh_keeps_latest_data_and_workspace_interactive(app):
    task = create(app, "Initial")
    async with app.run_test(size=(80, 24)) as pilot:
        for index in range(12):
            app.task_repo.update_task(task.task_id, TaskUpdate(title=f"Updated {index}"))
            app.refresh_tasks()
            await asyncio.sleep(0)
        table = app.query_one("#task-table", DataTable)
        # Refreshes load off the UI loop; slow runners need more than one pause for the last one to land.
        async with asyncio.timeout(5):
            while table.row_count == 0 or table.get_row(str(task.task_id))[0].plain != "Updated 11":
                await pilot.pause(0.02)
        await pilot.press("n")
        fill(app, **{"task-title": "Still interactive", "task-requirement": "Saved after refresh"})
        await save_form(app, pilot)
        await pilot.pause()
        assert {task.title for task in app.task_repo.list_tasks()} == {"Updated 11", "Still interactive"}


async def test_task_titles_are_literal_text(app):
    task = create(app, "[red]Release[/] [draft]")
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#task-table", DataTable)
        cell = table.get_row(str(task.task_id))[0]
        rendered = Text.from_markup(cell) if isinstance(cell, str) else cell
        assert rendered.plain == task.title
        await pilot.press("c")
        label = app.screen.query(Label).first()
        assert task.title in str(label.visual)


async def test_clicking_chat_tab_moves_focus_to_editor(app):
    create(app, "Draft")
    async with app.run_test() as pilot:
        await pilot.click("#--content-tab-chat-tab")
        await pilot.press("n")
        assert isinstance(app.focused, TextArea)
        assert app.focused.text == "n"


async def test_completion_requires_actual_effort_and_cancel_starts_blank(app):
    task = create(app, "Deliver a fix")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("c")
        assert app.screen.query_one("#actual-minutes", Input).value == ""
        await save_form(app, pilot)
        assert app.task_repo.get_task(task.task_id).status == TaskStatus.PENDING
        assert app.completions.get_completion_by_task_id(task.task_id) is None
        fill(app, **{"actual-minutes": -3})
        await save_form(app, pilot)
        assert app.task_repo.get_task(task.task_id).status == TaskStatus.PENDING
        fill(app, **{"actual-minutes": 12})
        await save_form(app, pilot)
        await pilot.pause()
        assert app.completions.get_completion_by_task_id(task.task_id).duration_actual == 12
        await pilot.press("x")
        assert app.screen.query_one("#actual-minutes", Input).value == ""


async def test_editing_precedence_and_all_view_cycle_bindings(app):
    create(app, "Draft")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("n")
        title = app.screen.query_one("#task-title", Input)
        title.focus()
        await pilot.press(*"jkn ecxdfgsrq".replace(" ", ""), "space", "1", "2", "3", "4", "5")
        assert title.value == "jknecxdfgsrq 12345"
        await pilot.press("ctrl+tab")
        assert isinstance(app.screen, TaskFormScreen)
        await pilot.press("escape")
        for view in ("board-view", "graph-view", "chat-tab", "insights-view", "list-view"):
            await pilot.press("ctrl+tab")
            assert app.query_one("#views", TabbedContent).active == view
        await pilot.press("space")
        await pilot.pause()
        assert app.task_repo.list_tasks()[0].status == TaskStatus.IN_PROGRESS
        await pilot.press("space")
        await pilot.pause()
        assert app.task_repo.list_tasks()[0].status == TaskStatus.PENDING
        await pilot.press("r", "q")
    assert app.chat_handler.should_exit


async def test_slow_database_refresh_does_not_freeze_keyboard(app, monkeypatch):
    create(app, "Draft")
    async with app.run_test() as pilot:
        await pilot.pause()
        original = app.task_repo.list_tasks_by_priority
        started = threading.Event()
        release = threading.Event()

        def delayed_read():
            started.set()
            release.wait(3)
            return original()

        monkeypatch.setattr(app.task_repo, "list_tasks_by_priority", delayed_read)
        app.refresh_tasks()
        try:
            await asyncio.wait_for(asyncio.to_thread(started.wait), 1)
            await asyncio.wait_for(pilot.press("n"), 1)
            assert isinstance(app.screen, TaskFormScreen)
            assert not release.is_set()
        finally:
            release.set()


async def test_github_sync_is_nonoverlapping_and_cancelled_on_quit(app, monkeypatch):
    started = asyncio.Event()
    cancelled = asyncio.Event()
    calls = 0

    async def blocked_sync(_db, _repos):
        nonlocal calls
        calls += 1
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr("taskweaver.tui.app.run_github_sync", blocked_sync)
    async with app.run_test() as pilot:
        app.github_repos = ("owner/project",)
        app.sync_github()
        await asyncio.wait_for(started.wait(), 1)
        app.sync_github()
        await pilot.pause()
        assert calls == 1
        await pilot.press("q")
    await asyncio.wait_for(cancelled.wait(), 1)
    assert not app.github_syncing


@pytest.mark.parametrize(
    ("score", "color"), [(0, "green"), (39.9, "green"), (40, "yellow"), (69.9, "yellow"), (70, "red"), (100, "red")]
)
def test_mcda_thresholds_preserve_numeric_scores_with_no_color(app, monkeypatch, score, color):
    monkeypatch.setenv("NO_COLOR", "1")
    value = app._score(score)
    assert value.style == color
    console = Console(force_terminal=True, no_color=True)
    with console.capture() as output:
        console.print(value)
    assert output.get().strip() == f"{score:.1f}"


async def test_burst_chat_messages_keep_recent_history_in_order(app):
    async with app.run_test() as pilot:
        await pilot.press("4")
        for index in range(105):
            app._post_message_with_limit(f"Message {index}", "system-message")
        await pilot.pause()
        messages = list(app.query("#chat-view Markdown"))
        assert len(messages) == 100
        assert messages[0].source == "Message 5"
        assert messages[-1].source == "Message 104"


async def test_board_selection_follows_task_moving_between_status_columns(app):
    selected = create(app, "Selected")
    create(app, "Other pending")
    async with app.run_test() as pilot:
        await select_task(app, pilot, selected.task_id)
        await pilot.press("2")
        app.task_repo.update_task(selected.task_id, TaskUpdate(status=TaskStatus.IN_PROGRESS))
        app.refresh_tasks()
        await app.workers.wait_for_complete([worker for worker in app.workers if worker.group == "workspace-refresh"])
        await pilot.pause()
        assert app.selected_task_id == selected.task_id
        assert app.focused is app.query_one("#board-in_progress", DataTable)
        await pilot.press("enter")
        assert app.screen.task_data.task_id == selected.task_id


async def test_delayed_focus_messages_cannot_undo_tab_selection(app):
    create(app, "Draft")
    async with app.run_test() as pilot:
        await pilot.press("4")
        old_pane = app.query_one("#list-view", TabPane)
        old_pane.post_message(TabPane.Focused(old_pane))
        app.refresh_tasks()
        await pilot.pause()
        assert app.query_one("#views", TabbedContent).active == "chat-tab"
        assert isinstance(app.focused, TextArea)
        await pilot.press("ctrl+tab")
        assert app.query_one("#views", TabbedContent).active == "insights-view"


async def test_table_resize_uses_space_without_losing_titles_or_selection(app):
    task = create(app, "Build a responsive workspace with readable task titles")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        table = app.query_one("#task-table", DataTable)
        wide = table.ordered_columns[0].width
        assert table.get_row(str(task.task_id))[0].plain == task.title
        assert wide >= len(task.title)
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert table.ordered_columns[0].width < wide
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == str(task.task_id)
        await pilot.press("2")
        columns = list(app.query(".board-column"))
        assert [column for column in columns if column.show_cursor] == [app.focused]
        app.query_one("#board-in_progress", DataTable).focus()
        await pilot.pause()
        assert [column for column in columns if column.show_cursor] == [app.focused]
