#!/usr/bin/env python3
"""Audit candidate AUMC `samp` / suspected-infection policies.

This is a research audit script, not a pipeline stage. It tests whether
AmsterdamUMCdb can reconstruct culture sampling and culture-result signals
needed for an iCareFM-style `samp` feature and Sepsis-3-style suspected
infection definitions.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


MS_PER_HOUR = 3_600_000


@dataclass(frozen=True)
class PolicyFrames:
    """Container for event-level evidence used by the policy audit."""

    admissions: pd.DataFrame
    culture_orders: pd.DataFrame
    sepsis_two_blood_cultures: pd.DataFrame
    blood_culture_results: pd.DataFrame
    line_bacteremia_flags: pd.DataFrame
    antibiotics: dict[str, pd.DataFrame]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("/msc/home/avahda55/Datasets/AmsterdamUMCdb"))
    parser.add_argument(
        "--vocab",
        type=Path,
        default=Path("/msc/home/avahda55/dataset_EDA/MetaICU/mappings/aumc_supplied_vocab.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/msc/home/avahda55/dataset_EDA/audits/aumc_samp_policy_audit"),
    )
    parser.add_argument("--chunksize", type=int, default=1_000_000)
    return parser.parse_args()


def read_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.casefold().isin({"true", "1", "yes"})


def hours_from_ms(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") / MS_PER_HOUR


def unique_admissions(frame: pd.DataFrame) -> set[int]:
    if frame.empty:
        return set()
    return set(pd.to_numeric(frame["admissionid"], errors="coerce").dropna().astype(int).unique())


def load_admissions(raw_dir: Path) -> pd.DataFrame:
    admissions = pd.read_csv(raw_dir / "admissions.csv", usecols=["admissionid", "location"], encoding="latin1")
    admissions["admissionid"] = admissions["admissionid"].astype(int)
    return admissions


def load_culture_orders(raw_dir: Path) -> pd.DataFrame:
    cols = ["admissionid", "ordercategoryid", "ordercategoryname", "itemid", "item", "registeredat"]
    orders = pd.read_csv(raw_dir / "procedureorderitems.csv", usecols=cols, encoding="latin1")
    orders["registered_hours"] = hours_from_ms(orders["registeredat"])
    orders["sampling_compartment"] = orders["item"].map(classify_culture_compartment)
    culture = orders[
        orders["ordercategoryid"].eq(74)
        | orders["ordercategoryname"].fillna("").str.contains("Kweken afnemen", case=False, regex=False)
    ].copy()
    culture = culture[culture["item"].fillna("").str.contains(r"kweek|kwek|culture", case=False, regex=True)].copy()
    return culture


def classify_culture_compartment(item: object) -> str:
    text = "" if item is None or pd.isna(item) else str(item).casefold()
    if "bloed" in text:
        return "blood"
    if "urine" in text:
        return "urine"
    if any(term in text for term in ["sputum", "keel", "neus", "nasophar", "rectum", "perineum"]):
        return "respiratory_or_screening"
    if "liquor" in text:
        return "csf"
    if any(term in text for term in ["faeces", "feces"]):
        return "stool"
    if any(term in text for term in ["catheter", "drain", "wond", "ascites"]):
        return "line_wound_or_fluid"
    if "research" in text:
        return "research"
    return "other_or_unspecified"


def load_sepsis_two_blood_culture_checkbox(raw_dir: Path, chunksize: int) -> pd.DataFrame:
    cols = ["admissionid", "itemid", "item", "valueid", "value", "measuredat"]
    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(raw_dir / "listitems.csv", usecols=cols, encoding="latin1", chunksize=chunksize):
        matched = chunk[chunk["itemid"].eq(16961)].copy()
        if not matched.empty:
            matched["measured_hours"] = hours_from_ms(matched["measuredat"])
            parts.append(matched)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols + ["measured_hours"])


def load_line_bacteremia_flags(raw_dir: Path, chunksize: int) -> pd.DataFrame:
    cols = ["admissionid", "itemid", "item", "valueid", "value", "measuredat"]
    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(raw_dir / "listitems.csv", usecols=cols, encoding="latin1", chunksize=chunksize):
        matched = chunk[
            chunk["itemid"].eq(14143)
            & chunk["value"].fillna("").str.contains("Bacteriemie|lijnensepsis", case=False, regex=True)
        ].copy()
        if not matched.empty:
            matched["measured_hours"] = hours_from_ms(matched["measuredat"])
            parts.append(matched)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols + ["measured_hours"])


def load_blood_culture_result_text(raw_dir: Path) -> pd.DataFrame:
    cols = ["admissionid", "itemid", "item", "value", "comment", "measuredat"]
    freetext = pd.read_csv(raw_dir / "freetextitems.csv", usecols=cols, encoding="latin1")
    result = freetext[freetext["itemid"].eq(19907)].copy()
    result["measured_hours"] = hours_from_ms(result["measuredat"])
    return result


def antibiotic_source_pairs(vocab_path: Path) -> dict[str, set[tuple[int, int]]]:
    vocab = pd.read_csv(vocab_path, low_memory=False).fillna("")
    drugs = vocab[vocab["source_table"].eq("drugitems")].copy()
    drugs["emit"] = read_bool(drugs["emit_as_model_token"])
    drugs["source_itemid"] = pd.to_numeric(drugs["source_itemid"], errors="coerce").astype("Int64")
    drugs["source_ordercategoryid"] = pd.to_numeric(drugs["source_ordercategoryid"], errors="coerce").astype("Int64")
    drugs["target_code"] = drugs["target_code"].astype(str)
    drugs["source_label"] = drugs["source_label"].astype(str)

    usable = drugs[drugs["emit"] & drugs["source_itemid"].notna() & drugs["source_ordercategoryid"].notna()].copy()

    def pairs(mask: pd.Series) -> set[tuple[int, int]]:
        sub = usable[mask]
        return set(zip(sub["source_itemid"].astype(int), sub["source_ordercategoryid"].astype(int)))

    target_code = usable["target_code"].str.upper()
    source_label = usable["source_label"].str.casefold()
    return {
        "abx_j01": pairs(target_code.str.startswith("J01")),
        "abx_j01_j02_j04_j05": pairs(target_code.str.match(r"^(J01|J02|J04|J05)", na=False)),
        "abx_ordercategory_antimicrobial": pairs(usable["source_ordercategoryid"].isin([15, 21])),
        "abx_ordercategory_injectable_antimicrobial": pairs(usable["source_ordercategoryid"].eq(15)),
        "abx_j01_excluding_sdd": pairs(target_code.str.startswith("J01") & ~source_label.str.contains("sdd", na=False)),
    }


def load_antibiotics(raw_dir: Path, vocab_path: Path, chunksize: int) -> dict[str, pd.DataFrame]:
    pair_sets = antibiotic_source_pairs(vocab_path)
    cols = ["admissionid", "itemid", "ordercategoryid", "item", "ordercategory", "start", "stop", "duration"]
    parts: dict[str, list[pd.DataFrame]] = {name: [] for name in pair_sets}

    for chunk in pd.read_csv(raw_dir / "drugitems.csv", usecols=cols, encoding="latin1", chunksize=chunksize):
        item = pd.to_numeric(chunk["itemid"], errors="coerce").astype("Int64")
        ordercat = pd.to_numeric(chunk["ordercategoryid"], errors="coerce").astype("Int64")
        chunk_pairs = pd.Series(list(zip(item.fillna(-1).astype(int), ordercat.fillna(-1).astype(int))), index=chunk.index)
        for name, valid_pairs in pair_sets.items():
            matched = chunk[chunk_pairs.isin(valid_pairs)].copy()
            if not matched.empty:
                matched["start_hours"] = hours_from_ms(matched["start"])
                matched["stop_hours"] = hours_from_ms(matched["stop"])
                parts[name].append(matched)

    return {
        name: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols + ["start_hours", "stop_hours"])
        for name, frames in parts.items()
    }


def event_min(frame: pd.DataFrame, time_col: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["admissionid", "time_hours"])
    tmp = frame[["admissionid", time_col]].copy()
    tmp["admissionid"] = pd.to_numeric(tmp["admissionid"], errors="coerce")
    tmp["time_hours"] = pd.to_numeric(tmp[time_col], errors="coerce")
    tmp = tmp.dropna(subset=["admissionid", "time_hours"])
    tmp["admissionid"] = tmp["admissionid"].astype(int)
    return tmp.groupby("admissionid", as_index=False)["time_hours"].min()


def ricu_temporal_and(abx: pd.DataFrame, samp: pd.DataFrame, abx_win_h: float = 24.0, samp_win_h: float = 72.0) -> pd.DataFrame:
    """Approximate ricu::susp_inf(si_mode='and') at admission level.

    A suspected infection exists if antibiotic and sampling occur in either
    order under ricu's default asymmetric windows:
    - ABX then sampling within 24h
    - sampling then ABX within 72h
    The event time is the earlier of the two times.
    """

    abx_ev = event_min(abx, "start_hours").rename(columns={"time_hours": "abx_time"})
    samp_ev = event_min(samp, "time_hours").rename(columns={"time_hours": "samp_time"})
    both = abx_ev.merge(samp_ev, on="admissionid", how="inner")
    if both.empty:
        return pd.DataFrame(columns=["admissionid", "susp_inf_time", "abx_time", "samp_time"])
    delta = both["samp_time"] - both["abx_time"]
    ok = ((delta >= 0) & (delta <= abx_win_h)) | ((delta < 0) & ((-delta) <= samp_win_h))
    res = both[ok].copy()
    res["susp_inf_time"] = res[["abx_time", "samp_time"]].min(axis=1)
    return res[["admissionid", "susp_inf_time", "abx_time", "samp_time"]]


def build_policy_frames(args: argparse.Namespace) -> PolicyFrames:
    admissions = load_admissions(args.raw_dir)
    culture_orders = load_culture_orders(args.raw_dir)
    sepsis_two = load_sepsis_two_blood_culture_checkbox(args.raw_dir, args.chunksize)
    line_bacteremia = load_line_bacteremia_flags(args.raw_dir, args.chunksize)
    blood_results = load_blood_culture_result_text(args.raw_dir)
    antibiotics = load_antibiotics(args.raw_dir, args.vocab, args.chunksize)
    return PolicyFrames(admissions, culture_orders, sepsis_two, blood_results, line_bacteremia, antibiotics)


def summarize_boolean_policy(name: str, frame: pd.DataFrame, total_admissions: int, description: str) -> dict[str, object]:
    admissions = unique_admissions(frame)
    return {
        "policy": name,
        "description": description,
        "event_rows": int(len(frame)),
        "positive_admissions": int(len(admissions)),
        "positive_admission_pct": round(100 * len(admissions) / total_admissions, 4),
    }


def frame_from_admissions(admissions: set[int]) -> pd.DataFrame:
    return pd.DataFrame({"admissionid": sorted(admissions)})


def write_outputs(args: argparse.Namespace, frames: PolicyFrames) -> dict[str, str]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    total_admissions = int(frames.admissions["admissionid"].nunique())

    culture = frames.culture_orders.copy()
    non_research_culture = culture[
        ~culture["item"].fillna("").str.contains("Research|COUrSe", case=False, regex=True)
        & ~culture["item"].fillna("").str.contains("nader te bepalen", case=False, regex=False)
    ].copy()
    blood_culture = culture[culture["sampling_compartment"].eq("blood")].copy()
    urine_culture = culture[culture["sampling_compartment"].eq("urine")].copy()
    blood_or_urine = culture[culture["sampling_compartment"].isin(["blood", "urine"])].copy()
    respiratory_or_blood_or_urine = culture[
        culture["sampling_compartment"].isin(["blood", "urine", "respiratory_or_screening"])
    ].copy()

    sepsis_two_yes = frames.sepsis_two_blood_cultures[
        frames.sepsis_two_blood_cultures["value"].astype(str).str.casefold().eq("ja")
    ].copy()
    result_like = pd.concat(
        [
            frames.blood_culture_results[["admissionid"]].copy(),
            frames.line_bacteremia_flags[["admissionid"]].copy(),
        ],
        ignore_index=True,
    )

    samp_policies = {
        "ricu_aumc_samp_any_culture_order": (culture, "Any procedureorderitems culture order; equivalent to ricu order-only TRUE flag."),
        "samp_nonresearch_culture_order": (non_research_culture, "Culture orders excluding research and unspecified X-Kweek."),
        "samp_blood_culture_order": (blood_culture, "Bloedkweken afnemen order only."),
        "samp_urine_culture_order": (urine_culture, "Urinekweek afnemen order only."),
        "samp_blood_or_urine_culture_order": (blood_or_urine, "Blood or urine culture order."),
        "samp_blood_urine_resp_culture_order": (
            respiratory_or_blood_or_urine,
            "Blood, urine, sputum/respiratory/screening culture order.",
        ),
        "samp_blood_order_or_sepsis_two_blood_yes": (
            frame_from_admissions(unique_admissions(blood_culture) | unique_admissions(sepsis_two_yes)),
            "Blood culture order OR sepsis bundle checkbox for two blood cultures = Ja.",
        ),
        "samp_result_like_positive_strict": (
            result_like,
            "Only sparse result-like blood culture text or line bacteremia complication.",
        ),
    }

    policy_rows = [
        summarize_boolean_policy(name, frame, total_admissions, desc)
        for name, (frame, desc) in samp_policies.items()
    ]

    abx_rows = []
    for name, abx in frames.antibiotics.items():
        abx_rows.append(summarize_boolean_policy(name, abx, total_admissions, "Antibiotic exposure candidate."))

    susp_rows = []
    for samp_name, (samp_frame, samp_desc) in samp_policies.items():
        samp_time = samp_frame.copy()
        if "registered_hours" in samp_time.columns:
            samp_time["time_hours"] = samp_time["registered_hours"]
        elif "measured_hours" in samp_time.columns:
            samp_time["time_hours"] = samp_time["measured_hours"]
        else:
            samp_time["time_hours"] = 0.0
        samp_adm = unique_admissions(samp_time)
        for abx_name, abx_frame in frames.antibiotics.items():
            abx_adm = unique_admissions(abx_frame)
            ever_and = samp_adm & abx_adm
            temporal = ricu_temporal_and(abx_frame, samp_time)
            susp_rows.append(
                {
                    "samp_policy": samp_name,
                    "abx_policy": abx_name,
                    "samp_description": samp_desc,
                    "ever_and_admissions": int(len(ever_and)),
                    "ever_and_pct": round(100 * len(ever_and) / total_admissions, 4),
                    "ricu_temporal_and_admissions": int(temporal["admissionid"].nunique()),
                    "ricu_temporal_and_pct": round(100 * temporal["admissionid"].nunique() / total_admissions, 4),
                }
            )

    culture_item_counts = (
        culture.groupby(["itemid", "item", "sampling_compartment"], dropna=False)
        .agg(rows=("admissionid", "size"), admissions=("admissionid", "nunique"))
        .reset_index()
        .sort_values("rows", ascending=False)
    )
    compartment_counts = (
        culture.groupby("sampling_compartment", dropna=False)
        .agg(rows=("admissionid", "size"), admissions=("admissionid", "nunique"))
        .reset_index()
        .sort_values("rows", ascending=False)
    )

    policy_counts = pd.DataFrame(policy_rows).sort_values("positive_admissions", ascending=False)
    abx_counts = pd.DataFrame(abx_rows).sort_values("positive_admissions", ascending=False)
    susp_counts = pd.DataFrame(susp_rows).sort_values("ricu_temporal_and_admissions", ascending=False)

    policy_counts.to_csv(args.output_dir / "samp_policy_counts.csv", index=False)
    abx_counts.to_csv(args.output_dir / "antibiotic_policy_counts.csv", index=False)
    susp_counts.to_csv(args.output_dir / "susp_inf_policy_counts.csv", index=False)
    culture_item_counts.to_csv(args.output_dir / "culture_order_item_counts.csv", index=False)
    compartment_counts.to_csv(args.output_dir / "culture_order_compartment_counts.csv", index=False)
    frames.blood_culture_results.to_csv(args.output_dir / "blood_culture_result_like_rows.csv", index=False)
    frames.line_bacteremia_flags.to_csv(args.output_dir / "line_bacteremia_result_like_rows.csv", index=False)

    target = 5357
    nearest = policy_counts.assign(abs_delta=(policy_counts["positive_admissions"] - target).abs()).sort_values("abs_delta").head(5)
    nearest_susp = susp_counts.assign(abs_delta=(susp_counts["ricu_temporal_and_admissions"] - target).abs()).sort_values("abs_delta").head(10)
    summary = {
        "total_admissions": total_admissions,
        "target_count_from_paper": target,
        "nearest_samp_policy_counts": nearest.to_dict(orient="records"),
        "nearest_susp_inf_temporal_counts": nearest_susp.to_dict(orient="records"),
        "notes": [
            "Order-only culture sampling is expected to be closest to ricu AUMC samp.",
            "ricu::susp_inf defaults use antibiotic and sampling co-occurrence, positive_cultures=FALSE, abx_win=24h, samp_win=72h.",
            "Positive culture/growth evidence remains sparse and is audited separately.",
        ],
    }
    summary_path = args.output_dir / "samp_policy_audit_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    return {
        "summary": str(summary_path),
        "samp_policy_counts": str(args.output_dir / "samp_policy_counts.csv"),
        "antibiotic_policy_counts": str(args.output_dir / "antibiotic_policy_counts.csv"),
        "susp_inf_policy_counts": str(args.output_dir / "susp_inf_policy_counts.csv"),
        "culture_order_item_counts": str(args.output_dir / "culture_order_item_counts.csv"),
        "culture_order_compartment_counts": str(args.output_dir / "culture_order_compartment_counts.csv"),
        "blood_culture_result_like_rows": str(args.output_dir / "blood_culture_result_like_rows.csv"),
        "line_bacteremia_result_like_rows": str(args.output_dir / "line_bacteremia_result_like_rows.csv"),
    }


def main() -> None:
    args = parse_args()
    print(f"[samp audit] raw_dir={args.raw_dir}", flush=True)
    print(f"[samp audit] vocab={args.vocab}", flush=True)
    print(f"[samp audit] output_dir={args.output_dir}", flush=True)
    frames = build_policy_frames(args)
    outputs = write_outputs(args, frames)
    print(json.dumps(outputs, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
