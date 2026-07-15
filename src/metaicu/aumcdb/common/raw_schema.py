"""Canonical raw schemas for the large AmsterdamUMCdb source tables."""

from __future__ import annotations

import polars as pl


LARGE_TABLE_RAW_SCHEMAS: dict[str, dict[str, type]] = {
    "numericitems": {
        "admissionid": pl.Int64,
        "itemid": pl.Int64,
        "item": pl.String,
        "tag": pl.String,
        "value": pl.Float64,
        "unitid": pl.Int64,
        "unit": pl.String,
        "comment": pl.String,
        "measuredat": pl.Int64,
        "registeredat": pl.Int64,
        "registeredby": pl.String,
        "updatedat": pl.Int64,
        "updatedby": pl.String,
        "islabresult": pl.Int64,
        "fluidout": pl.Int64,
    },
    "listitems": {
        "admissionid": pl.Int64,
        "itemid": pl.Int64,
        "item": pl.String,
        "valueid": pl.Int64,
        "value": pl.String,
        "measuredat": pl.Int64,
        "registeredat": pl.Int64,
        "registeredby": pl.String,
        "updatedat": pl.Int64,
        "updatedby": pl.String,
        "islabresult": pl.Int64,
    },
    "drugitems": {
        "admissionid": pl.Int64,
        "orderid": pl.Int64,
        "ordercategoryid": pl.Int64,
        "ordercategory": pl.String,
        "itemid": pl.Int64,
        "item": pl.String,
        "isadditive": pl.Int64,
        "isconditional": pl.Int64,
        "rate": pl.Float64,
        "rateunit": pl.String,
        "rateunitid": pl.Int64,
        "ratetimeunitid": pl.Int64,
        "doserateperkg": pl.Int64,
        "dose": pl.Float64,
        "doseunit": pl.String,
        "doserateunit": pl.String,
        "doseunitid": pl.Int64,
        "doserateunitid": pl.Int64,
        "administered": pl.Float64,
        "administeredunit": pl.String,
        "administeredunitid": pl.Int64,
        "action": pl.String,
        "start": pl.Int64,
        "stop": pl.Int64,
        "duration": pl.Int64,
        "solutionitemid": pl.Int64,
        "solutionitem": pl.String,
        "solutionadministered": pl.Float64,
        "solutionadministeredunit": pl.String,
        "fluidin": pl.Float64,
        "iscontinuous": pl.Int64,
    },
}


def cast_raw_schema(table: str, frame: pl.DataFrame) -> pl.DataFrame:
    """Cast known columns without requiring every raw column in bounded fixtures."""
    if table not in LARGE_TABLE_RAW_SCHEMAS:
        raise ValueError(f"Unsupported large table: {table!r}")
    expressions = [
        pl.col(column).cast(dtype, strict=False)
        for column, dtype in LARGE_TABLE_RAW_SCHEMAS[table].items()
        if column in frame.columns
    ]
    return frame.with_columns(expressions) if expressions else frame

