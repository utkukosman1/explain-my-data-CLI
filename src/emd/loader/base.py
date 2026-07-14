from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd


class BaseLoader(ABC):
    SUPPORTED_EXTENSIONS: tuple[str, ...] = ()

    def validate_extension(self, path: Path) -> None:
        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension '{path.suffix}'. "
                f"Expected one of: {self.SUPPORTED_EXTENSIONS}"
            )

    @abstractmethod
    def load(self, path: Path, **kwargs: Any) -> pd.DataFrame: ...
