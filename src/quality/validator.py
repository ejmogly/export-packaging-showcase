import pandas as pd
from typing import Dict, Any, List, Tuple


class DataQualityValidator:
    """
    Data Quality & Business Rules Validation Engine:
      1. Quantity Mismatch: pack_qty * work_qty == sticker_qty
         (with domain-aware recognition of valid special work patterns:
          outer box 'box' 1x, consumables pack_qty=0 1x, tray 4x, double sticker 2x)
      2. Missing Worker Count: worker_count == 0 or NULL
      3. Master Matching Health: is_unmatched_item check
      4. Summary Metrics & Anomaly Diagnostics
    """

    AUXILIARY_ITEMS = {
        "box", "box (외포장 라벨링)", "나무포크", "나무숟가락", "나무나이프", "트레이(자몽)"
    }

    @staticmethod
    def audit_dataset(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Runs comprehensive quality audits on the dataset.
        Returns:
          (audited_df_with_flags, quality_report_summary)
        """
        audited = df.copy()

        # 1. Quantity & Special Work Pattern Check
        pack = pd.to_numeric(audited["pack_qty"], errors="coerce").fillna(0).astype(int)
        work = pd.to_numeric(audited["work_qty"], errors="coerce").fillna(0).astype(int)
        sticker = pd.to_numeric(audited["sticker_qty"], errors="coerce").fillna(0).astype(int)

        raw_item = audited.get("item_name", pd.Series([""] * len(audited))).astype(str).str.strip().str.lower()
        norm_item = audited.get("normalized_item_name", raw_item).astype(str).str.strip().str.lower()
        cat1 = audited.get("category_1", pd.Series([""] * len(audited))).astype(str).str.strip()

        audited["calc_sticker_qty"] = pack * work
        audited["qty_diff"] = sticker - audited["calc_sticker_qty"]

        # Domain-valid special patterns
        is_std = (sticker == pack * work) & (pack > 0)
        is_box = (raw_item.isin({"box", "box (외포장 라벨링)"}) | norm_item.isin({"box", "box (외포장 라벨링)"})) & (sticker == work) & (work > 0)
        is_consumable = ((pack == 0) & (sticker == work) & (work > 0) & (~is_box)) | (cat1 == "물류소모품") & (sticker == work)
        is_tray = (work > 0) & ((sticker == 4 * work) | ((pack > 0) & (sticker == 4 * pack * work)))
        is_double = (pack > 0) & (work > 0) & (sticker == 2 * pack * work)

        # Assign work_pattern_type for transparency in UI & Quality Center
        pattern_types = pd.Series(["일반 단품 작업"] * len(audited), index=audited.index)
        pattern_types = pattern_types.mask(is_double, "2장 부착(x2) 특수작업")
        pattern_types = pattern_types.mask(is_tray, "트레이(x4) 특수작업")
        pattern_types = pattern_types.mask(is_consumable, "소모품/부자재 작업")
        pattern_types = pattern_types.mask(is_box, "외박스(box) 부착작업")

        valid_work_pattern = is_std | is_box | is_consumable | is_tray | is_double
        pattern_types = pattern_types.mask(~valid_work_pattern, "수량 불일치 (검수 필요)")

        audited["work_pattern_type"] = pattern_types
        audited["is_special_valid_work"] = (is_box | is_consumable | is_tray | is_double) & (~is_std)
        audited["is_auxiliary_item"] = (
            raw_item.isin(DataQualityValidator.AUXILIARY_ITEMS) |
            norm_item.isin(DataQualityValidator.AUXILIARY_ITEMS) |
            (cat1 == "물류소모품")
        )
        audited["qty_mismatch_flag"] = ~valid_work_pattern

        # 2. Worker Count Audit
        worker = pd.to_numeric(audited["worker_count"], errors="coerce").fillna(0)
        audited["worker_missing_flag"] = worker <= 0

        # 3. Overall Anomaly Flag
        unmatched = audited.get("is_unmatched_item", pd.Series([False] * len(audited), index=audited.index))
        audited["has_quality_issue"] = (
            audited["qty_mismatch_flag"] |
            audited["worker_missing_flag"] |
            unmatched
        )

        # Generate Metrics Report
        total_rows = len(audited)
        mismatch_count = int(audited["qty_mismatch_flag"].sum())
        special_valid_count = int(audited["is_special_valid_work"].sum())
        worker_missing_count = int(audited["worker_missing_flag"].sum())
        unmatched_count = int(unmatched.sum()) if "is_unmatched_item" in audited else 0

        # Calculate rates
        match_rate = round(((total_rows - unmatched_count) / total_rows * 100), 2) if total_rows > 0 else 100.0
        mismatch_rate = round((mismatch_count / total_rows * 100), 2) if total_rows > 0 else 0.0
        clean_rows_count = int((~audited["has_quality_issue"]).sum())
        clean_rate = round((clean_rows_count / total_rows * 100), 2) if total_rows > 0 else 100.0

        summary = {
            "total_rows": total_rows,
            "clean_rows_count": clean_rows_count,
            "clean_rate_pct": clean_rate,
            "qty_mismatch_count": mismatch_count,
            "qty_mismatch_pct": mismatch_rate,
            "special_valid_work_count": special_valid_count,
            "worker_missing_count": worker_missing_count,
            "unmatched_item_count": unmatched_count,
            "item_match_rate_pct": match_rate
        }

        return audited, summary

    @staticmethod
    def get_flagged_rows(df: pd.DataFrame, issue_type: str = "all") -> pd.DataFrame:
        """Filters dataset to return only rows with specific data quality issues."""
        if issue_type == "qty_mismatch":
            return df[df["qty_mismatch_flag"] == True]
        elif issue_type == "missing_worker":
            return df[df["worker_missing_flag"] == True]
        elif issue_type == "unmatched_item":
            return df[df.get("is_unmatched_item", False) == True]
        else:
            return df[df.get("has_quality_issue", False) == True]
