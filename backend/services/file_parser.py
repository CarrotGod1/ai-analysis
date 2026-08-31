import io
import json
from typing import Any

import pandas as pd

from config import settings
from models.schemas import FileInfo


class FileParser:
    MAX_PREVIEW_ROWS = 10

    def parse(self, filename: str, content: bytes) -> pd.DataFrame:
        lower = filename.lower()
        if lower.endswith(".csv"):
            return self._parse_csv(content)
        elif lower.endswith((".xlsx", ".xls")):
            return self._parse_excel(content)
        elif lower.endswith(".json"):
            return self._parse_json(content)
        else:
            raise ValueError(f"Неподдерживаемый формат: {filename}")

    def _parse_csv(self, content: bytes) -> pd.DataFrame:
        for encoding in ("utf-8", "cp1251", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(content), encoding=encoding)
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        raise ValueError("Не удалось прочитать CSV файл")

    def _parse_excel(self, content: bytes) -> pd.DataFrame:
        return pd.read_excel(io.BytesIO(content), engine="openpyxl")

    def _parse_json(self, content: bytes) -> pd.DataFrame:
        decoded = content.decode("utf-8")
        data = json.loads(decoded)
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                return pd.DataFrame(data["data"])
            return pd.json_normalize(data)
        raise ValueError("JSON должен быть списком объектов или объектом с ключом 'data'")

    def get_file_info(self, filename: str, df: pd.DataFrame) -> FileInfo:
        preview_records = df.head(self.MAX_PREVIEW_ROWS).fillna("").to_dict(orient="records")

        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        nulls = {col: int(count) for col, count in df.isnull().sum().items() if count > 0}

        numeric_summary = None
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            desc = df[numeric_cols].describe()
            numeric_summary = {
                col: {stat: round(float(desc[col][stat]), 2) for stat in desc.index}
                for col in numeric_cols
            }

        return FileInfo(
            filename=filename,
            rows=len(df),
            columns=list(df.columns),
            dtypes=dtypes,
            preview=preview_records,
            nulls=nulls,
            numeric_summary=numeric_summary,
        )

    def truncate_for_context(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) > settings.max_pandas_rows:
            return df.head(settings.max_pandas_rows)
        return df


file_parser = FileParser()
