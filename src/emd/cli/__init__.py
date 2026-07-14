"""emd command-line interface.

`_app.py` owns the Typer app; each command lives in its own module and registers
itself onto the shared app at import time. Importing this package assembles the
full CLI, so `emd.cli:app` stays a valid entry point. Command modules keep heavy
imports (pandas, analyzers, matplotlib) inside their functions so startup is fast.
"""
# Importing the command modules registers their commands on `app` via decorators.
from emd.cli import (  # noqa: E402, F401
    analyze,
    batch,
    check,
    compare,
    doctor,
    info,
    schema,
    sheets,
    summary,
)
from emd.cli._app import app

__all__ = ["app"]
