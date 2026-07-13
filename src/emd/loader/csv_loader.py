from __future__ import annotations

import csv
from pathlib import Path

import chardet
import pandas as pd

from emd.loader.base import BaseLoader


class CSVLoader(BaseLoader):
    SUPPORTED_EXTENSIONS = (".csv", ".tsv", ".txt")

    def load(self, path: Path, parse_dates: list[str] | None = None, **kwargs: object) -> pd.DataFrame:
        self.validate_extension(path)
        encoding = self._detect_encoding(path)
        delimiter = self._detect_delimiter(path, encoding)
        df = pd.read_csv(
            path,
            encoding=encoding,
            sep=delimiter,
            parse_dates=parse_dates or [],
            low_memory=False,
        )
        df.columns = [str(c).strip() for c in df.columns]
        df.attrs["source_path"] = str(path)
        df.attrs["original_shape"] = df.shape
        return df

    def _detect_encoding(self, path: Path) -> str:
        raw = path.read_bytes()[:65536]
        result = chardet.detect(raw)
        encoding = result.get("encoding") or "utf-8"
        # ASCII is a strict subset of UTF-8, so normalising is safe.
        if encoding.lower() == "ascii":
            encoding = "utf-8"
        return encoding

    def _detect_delimiter(self, path: Path, encoding: str) -> str:
        try:
            sample = path.read_bytes()[:4096].decode(encoding, errors="replace")
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            return dialect.delimiter
        except csv.Error:
            return ","
