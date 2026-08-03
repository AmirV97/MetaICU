"""Canonical raw schemas for the large MIMIC-IV source tables. Confirmed via a grep against the
reviewed manifest's KEPT matches that only these 5 tables are actually referenced -- datetimeevents
and ingredientevents (present in raw MIMIC-IV, both cheap enough to scan directly anyway at
63MB/311MB compressed) have zero kept matches, so they're not cached here."""

from __future__ import annotations

import polars as pl

LARGE_TABLE_RAW_SCHEMAS: dict[str, dict[str, type]] = {
    "chartevents": {
        "subject_id": pl.Int64, "hadm_id": pl.Int64, "stay_id": pl.Int64, "caregiver_id": pl.Int64,
        "charttime": pl.Datetime, "storetime": pl.Datetime, "itemid": pl.Int64, "value": pl.String,
        "valuenum": pl.Float64, "valueuom": pl.String, "warning": pl.Int64,
    },
    "labevents": {
        "labevent_id": pl.Int64, "subject_id": pl.Int64, "hadm_id": pl.Int64, "specimen_id": pl.Int64,
        "itemid": pl.Int64, "order_provider_id": pl.String, "charttime": pl.Datetime, "storetime": pl.Datetime,
        "value": pl.String, "valuenum": pl.Float64, "valueuom": pl.String, "ref_range_lower": pl.Float64,
        "ref_range_upper": pl.Float64, "flag": pl.String, "priority": pl.String, "comments": pl.String,
    },
    "inputevents": {
        "subject_id": pl.Int64, "hadm_id": pl.Int64, "stay_id": pl.Int64, "caregiver_id": pl.Int64,
        "starttime": pl.Datetime, "endtime": pl.Datetime, "storetime": pl.Datetime, "itemid": pl.Int64,
        "amount": pl.Float64, "amountuom": pl.String, "rate": pl.Float64, "rateuom": pl.String,
        "orderid": pl.Int64, "linkorderid": pl.Int64, "ordercategoryname": pl.String,
        "secondaryordercategoryname": pl.String, "ordercomponenttypedescription": pl.String,
        "ordercategorydescription": pl.String, "patientweight": pl.Float64, "totalamount": pl.Float64,
        "totalamountuom": pl.String, "isopenbag": pl.Int64, "continueinnextdept": pl.Int64,
        "statusdescription": pl.String, "originalamount": pl.Float64, "originalrate": pl.Float64,
    },
    "outputevents": {
        "subject_id": pl.Int64, "hadm_id": pl.Int64, "stay_id": pl.Int64, "caregiver_id": pl.Int64,
        "charttime": pl.Datetime, "storetime": pl.Datetime, "itemid": pl.Int64, "value": pl.Float64,
        "valueuom": pl.String,
    },
    "procedureevents": {
        "subject_id": pl.Int64, "hadm_id": pl.Int64, "stay_id": pl.Int64, "caregiver_id": pl.Int64,
        "starttime": pl.Datetime, "endtime": pl.Datetime, "storetime": pl.Datetime, "itemid": pl.Int64,
        "value": pl.Float64, "valueuom": pl.String, "location": pl.String, "locationcategory": pl.String,
        "orderid": pl.Int64, "linkorderid": pl.Int64, "ordercategoryname": pl.String,
        "ordercategorydescription": pl.String, "patientweight": pl.Float64, "isopenbag": pl.Int64,
        "continueinnextdept": pl.Int64, "statusdescription": pl.String, "originalamount": pl.Float64,
        "originalrate": pl.Float64,
    },
}


def cast_raw_schema(table: str, frame: pl.DataFrame) -> pl.DataFrame:
    """Cast known columns without requiring every raw column in bounded fixtures. Datetime
    columns are ISO strings ("YYYY-MM-DD HH:MM:SS") in MIMIC-IV's raw export -- unlike AUMCdb's
    already-integer-millisecond timestamps, these need str.to_datetime() parsing, not a plain
    cast; doing it here means it happens ONCE per row at shard-build time, not on every scan."""

    if table not in LARGE_TABLE_RAW_SCHEMAS:
        raise ValueError(f"Unsupported large table: {table!r}")
    expressions = []
    for column, dtype in LARGE_TABLE_RAW_SCHEMAS[table].items():
        if column not in frame.columns:
            continue
        if dtype == pl.Datetime:
            expressions.append(pl.col(column).str.to_datetime(strict=False))
        else:
            expressions.append(pl.col(column).cast(dtype, strict=False))
    return frame.with_columns(expressions) if expressions else frame
