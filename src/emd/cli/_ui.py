"""Shared terminal UI: consoles, colors, section helpers, and the step checklist."""
from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
from types import TracebackType
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

STATUS_COLORS = {"PASSED": "green", "PASSED WITH WARNINGS": "yellow", "FAILED": "red"}
SEVERITY_COLORS = {
    "FATAL": "red", "WARNING": "yellow", "INFO": "blue", "error": "red", "warning": "yellow",
}
BAND_COLORS = {
    "Excellent": "green", "Good": "green", "Fair": "yellow", "Poor": "red", "Critical": "red",
}

# Force UTF-8 on stdout/stderr: on Windows, redirected/piped output falls back to the
# system codepage (e.g. cp1252), which can't encode the spinner/box-drawing characters
# rich uses — this crashes analyze/compare with UnicodeEncodeError whenever output isn't
# a live terminal (piping to a file, CI logs, etc).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        with contextlib.suppress(ValueError, OSError):
            _stream.reconfigure(encoding="utf-8", errors="replace")

console = Console()
err_console = Console(stderr=True)


def header(title: str, subtitle: str = "") -> None:
    """Rule-style section header shown at the start of a command run."""
    text = f"[bold]{title}[/bold]"
    if subtitle:
        text += f" [dim]· {subtitle}[/dim]"
    console.rule(text, style="dim", align="left")


def output_panel(items: dict[str, str]) -> None:
    """Boxed summary of generated artifacts, shown at the end of a command run."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    for label, value in items.items():
        grid.add_row(label, value)
    console.print(Panel(grid, title="Output", title_align="left", border_style="dim", expand=False))


def make_table(*columns: str) -> Table:
    """Table with the house style shared by check/info/schema output."""
    table = Table(show_header=True, header_style="bold cyan")
    for col in columns:
        table.add_column(col)
    return table


def status(label: str, quiet: bool = False):  # type: ignore[no-untyped-def]
    """Spinner for a single-shot operation; a no-op under --quiet."""
    if quiet:
        return contextlib.nullcontext()
    return console.status(label)


class Steps:
    """Persistent step checklist: spinner while a step runs, checkmark once it's done.

    Unlike a fresh transient Progress per step, this keeps every completed step visible
    for the whole command run, so the terminal reads as a history of what happened
    rather than a sequence of messages that vanish as soon as the next one starts.
    A no-op under --quiet.
    """

    def __init__(self, quiet: bool) -> None:
        self._progress: Progress | None = None
        if not quiet:
            self._progress = Progress(
                SpinnerColumn(finished_text="[green]✓[/green]"),
                TextColumn("{task.description}"),
                console=console,
                transient=False,
            )

    def __enter__(self) -> Steps:
        if self._progress is not None:
            self._progress.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc_val, exc_tb)

    def stop(self) -> None:
        """Close the checklist early — call before printing an error to a different
        console, so a failed step doesn't leave a frozen spinner glyph behind it."""
        if self._progress is not None:
            self._progress.stop()

    def run(
        self, label: str, fn: Callable[[], Any], detail: Callable[[Any], str] | None = None
    ) -> Any:
        """Run fn() as one checklist step. `detail`, if given, formats a status suffix
        from the result — pass its own rich markup (e.g. "[dim]...[/dim]" or a color).
        If fn() raises, the spinner row is replaced with a plain "✗ label" line (rather
        than left as a frozen spinner glyph) and the exception is re-raised unchanged."""
        if self._progress is None:
            return fn()
        task_id = self._progress.add_task(f"[cyan]{label}[/cyan]", total=1)
        try:
            result = fn()
        except Exception:
            # Remove the failed row, then fully stop (not just pause) the live display —
            # this flushes already-completed steps to real scrollback in the right order
            # before printing the failure line as a plain, static line below them.
            self._progress.remove_task(task_id)
            self._progress.stop()
            console.print(f"[red]✗[/red] {label}")
            raise
        description = label
        if detail is not None:
            with contextlib.suppress(Exception):
                description = f"{label}  {detail(result)}"
        self._progress.update(task_id, completed=1, description=description)
        return result
