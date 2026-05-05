from __future__ import annotations

from pathlib import Path

import pandas as pd

from emd.loader.base import BaseLoader


class XLSXLoader(BaseLoader):
    SUPPORTED_EXTENSIONS = (".xlsx", ".xls", ".xlsm")

    def load(
        self,
        path: Path,
        sheet: str | int | None = None,
        parse_dates: list[str] | None = None,
        **kwargs: object,
    ) -> pd.DataFrame:
        self.validate_extension(path)
        df = pd.read_excel(
            path,
            sheet_name=sheet or 0,
            engine="openpyxl",
            parse_dates=parse_dates or [],
        )
        df.columns = [str(c).strip() for c in df.columns]
        df.attrs["source_path"] = str(path)
        df.attrs["original_shape"] = df.shape
        return df

    def list_sheets(self, path: Path) -> list[str]:
        self.validate_extension(path)
        xl = pd.ExcelFile(path, engine="openpyxl")
        return xl.sheet_names
