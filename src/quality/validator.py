import pandas as pd
from typing import Dict, Any, List, Tuple


class DataQualityValidator:
    """
    Data Quality & Business Rules Validation Engine:
      1. Quantity Mismatch: pack_qty * work_qty == sticker_qty
      2. Missing Worker Count: worker_count == 0 or NULL
      3. Master Matching Health: is_unmatched_item check
      4. Summary Metrics & Anomaly Diagnostics
    """

    @staticmethod
    def audit_dataset(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Runs comprehensive quality audits on the dataset.
        Returns:
          (audited_df_with_flags, quality_report_summary)
        """
        audited = df.copy()

        # 1. Quantity Mismatch Check
        pack = pd.to_numeric(audited["pack_qty"], errors="coerce").fillna(0).astype(int)
        work = pd.to_numeric(audited["work_qty"], errors="coerce").fillna(0).astype(int)
        sticker = pd.to_numeric(audited["sticker_qty"], errors="coerce").fillna(0).astype(int)
        
        audited["calc_sticker_qty"] = pack * work
        audited["qty_diff"] = sticker - audited["calc_sticker_qty"]
        audited["qty_mismatch_flag"] = audited["qty_diff"] != 0

        # 2. Worker Count Audit
        worker = pd.to_numeric(audited["worker_count"], errors="coerce").fillna(0)
        audited["worker_missing_flag"] = worker <= 0

        # 3. Overall Anomaly Flag
        unmatched = audited.get("is_unmatched_item", pd.Series([False] * len(audited)))
        audited["has_quality_issue"] = (
            audited["qty_mismatch_flag"] | 
            audited["worker_missing_flag"] | 
            unmatched
        )

        # Generate Metrics Report
        total_rows = len(audited)
        mismatch_count = int(audited["qty_mismatch_flag"].sum())
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
