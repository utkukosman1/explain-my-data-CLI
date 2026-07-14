from __future__ import annotations

from emd import __version__
from emd.cli._app import app
from emd.cli._ui import console, header, make_table


@app.command()
def info() -> None:
    """Show version and dependency status."""
    header("info", f"v{__version__}")

    deps = [
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("matplotlib", "matplotlib"),
        ("seaborn", "seaborn"),
        ("statsmodels", "statsmodels"),
        ("openpyxl", "openpyxl"),
        ("chardet", "chardet"),
        ("typer", "typer"),
        ("pyyaml", "yaml"),
    ]
    optional = [("scikit-learn (Isolation Forest)", "sklearn")]

    table = make_table("Package", "Version", "Status")

    for name, mod in deps + optional:
        try:
            import importlib
            m = importlib.import_module(mod)
            version = getattr(m, "__version__", "installed")
            status = "[green]OK[/green]"
        except ImportError:
            version = "—"
            status = (
                "[yellow]optional — not installed[/yellow]"
                if (name, mod) in optional
                else "[red]MISSING[/red]"
            )
        table.add_row(name, version, status)

    console.print()
    console.print(table)
