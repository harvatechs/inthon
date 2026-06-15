from __future__ import annotations
from typing import Any
from ...runtime.values import InthonPyObject


class PandasAdapter:
    """
    Ergonomic wrapper around a pandas DataFrame that exposes
    INTHON-idiomatic method names and returns InthonPyObject values.
    """

    def __init__(self, df: Any) -> None:
        self._df = df

    def drop_nulls(self) -> PandasAdapter:
        return PandasAdapter(self._df.dropna())

    def filter(self, condition: Any) -> PandasAdapter:
        """condition is a pandas BooleanArray or similar."""
        return PandasAdapter(self._df[condition])

    def group_by(self, column: str) -> PandasGroupByAdapter:
        return PandasGroupByAdapter(self._df.groupby(column))

    def select(self, *columns: str) -> PandasAdapter:
        return PandasAdapter(self._df[list(columns)])

    def sort(self, column: str, ascending: bool = True) -> PandasAdapter:
        return PandasAdapter(self._df.sort_values(column, ascending=ascending))

    def head(self, n: int = 5) -> PandasAdapter:
        return PandasAdapter(self._df.head(n))

    def describe(self) -> InthonPyObject:
        return InthonPyObject(self._df.describe(), "pandas")

    def to_dict(self) -> InthonPyObject:
        return InthonPyObject(self._df.to_dict(orient="records"), "pandas")

    def shape(self) -> list[int]:
        return list(self._df.shape)

    @property
    def underlying(self) -> Any:
        return self._df

    def __repr__(self) -> str:
        return f"<IntHon PandasAdapter: DataFrame {self._df.shape}>"


class PandasGroupByAdapter:
    def __init__(self, grp: Any) -> None:
        self._grp = grp

    def sum(self, column: str) -> PandasAdapter:
        return PandasAdapter(self._grp[column].sum().reset_index())

    def mean(self, column: str) -> PandasAdapter:
        return PandasAdapter(self._grp[column].mean().reset_index())

    def count(self) -> PandasAdapter:
        return PandasAdapter(self._grp.size().reset_index(name="count"))

    def agg(self, **kwargs: str) -> PandasAdapter:
        return PandasAdapter(self._grp.agg(kwargs).reset_index())

    def __repr__(self) -> str:
        return "<IntHon PandasGroupByAdapter>"
