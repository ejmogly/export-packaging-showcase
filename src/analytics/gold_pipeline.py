import pandas as pd
import numpy as np
from typing import Dict, Any, List


class GoldAnalyticsPipeline:
    """
    Gold Layer Analytical Marts Generator:
      - Daily Productivity Mart
      - Item & Category Difficulty Mart
      - Buyer & Export Country Mart
      - Capacity & Workforce Simulation Model
    """

    @staticmethod
    def build_daily_productivity_mart(silver_df: pd.DataFrame) -> pd.DataFrame:
        """
        Grain: 1 Row per work_date
        """
        if silver_df.empty:
            return pd.DataFrame(columns=[
                "work_date", "work_month", "worker_count", "effective_worker_count",
                "total_man_hours", "total_stickers", "total_boxes", "line_items_count",
                "mismatch_count", "unmatched_items_count", "stickers_per_man_hour",
                "boxes_per_man_hour", "stickers_per_worker"
            ])

        mart = silver_df.groupby("work_date").agg(
            work_month=("work_month", "first"),
            worker_count=("worker_count", "max"),
            effective_worker_count=("effective_worker_count", "max"),
            total_man_hours=("total_man_hours", "max"),
            total_stickers=("sticker_qty", "sum"),
            total_boxes=("work_qty", "sum"),
            line_items_count=("line_no", "count"),
            mismatch_count=("qty_mismatch_flag", "sum"),
            unmatched_items_count=("is_unmatched_item", "sum")
        ).reset_index()

        mart["stickers_per_man_hour"] = (
            mart["total_stickers"] / mart["total_man_hours"].replace(0, np.nan)
        ).round(1)

        mart["boxes_per_man_hour"] = (
            mart["total_boxes"] / mart["total_man_hours"].replace(0, np.nan)
        ).round(1)

        mart["stickers_per_worker"] = (
            mart["total_stickers"] / mart["effective_worker_count"].replace(0, np.nan)
        ).round(0)

        mart = mart.sort_values("work_date", ascending=False)
        return mart

    @staticmethod
    def build_item_difficulty_mart(silver_df: pd.DataFrame) -> pd.DataFrame:
        """
        Grain: 1 Row per normalized_item_name
        """
        if silver_df.empty:
            return pd.DataFrame(columns=[
                "normalized_item_name", "raw_aliases_count", "manufacturer",
                "category_1", "category_2", "standard_volume", "order_count",
                "active_days", "total_boxes", "total_stickers", "avg_pack_qty",
                "allocated_man_hours", "stickers_per_hour", "boxes_per_hour",
                "difficulty_tier"
            ])

        mart = silver_df.groupby("normalized_item_name").agg(
            raw_aliases_count=("item_name", "nunique"),
            manufacturer=("manufacturer", "first"),
            category_1=("category_1", "first"),
            category_2=("category_2", "first"),
            standard_volume=("standard_volume", "first"),
            order_count=("line_no", "count"),
            active_days=("work_date", "nunique"),
            total_boxes=("work_qty", "sum"),
            total_stickers=("sticker_qty", "sum"),
            avg_pack_qty=("pack_qty", "mean"),
            allocated_man_hours=("row_man_hours", "sum")
        ).reset_index()

        mart["avg_pack_qty"] = mart["avg_pack_qty"].round(1)
        mart["allocated_man_hours"] = mart["allocated_man_hours"].round(1)

        # Calculate productivity benchmark ($Stickers/Hour$ and $Boxes/Hour$)
        mart["stickers_per_hour"] = (
            mart["total_stickers"] / mart["allocated_man_hours"].replace(0, np.nan)
        ).round(1)

        mart["boxes_per_hour"] = (
            mart["total_boxes"] / mart["allocated_man_hours"].replace(0, np.nan)
        ).round(1)

        # Assign Difficulty Tier based on pack_qty
        # Korean export snacks carton pack sizes:
        # High (>=32 pcs/box): High packaging density (e.g. Pepero 32~40, Jardin stick coffees 50, Ice cream 40)
        # Medium (16~31 pcs/box): Standard export carton density (e.g. Chocopie, Custard, general biscuits)
        # Low (<16 pcs/box): Bulk / small pack carton density (e.g. large snack bags 8~12, canned/bottled drinks)
        def assign_tier(row):
            pack = row["avg_pack_qty"]
            if pack >= 32:
                return "고난이도 (High - 32개↑)"
            elif pack >= 16:
                return "중간 (Medium - 16~31개)"
            else:
                return "단순 (Low - 16개↓)"

        mart["difficulty_tier"] = mart.apply(assign_tier, axis=1)
        mart = mart.sort_values("total_stickers", ascending=False)
        return mart

    @staticmethod
    def build_buyer_summary_mart(silver_df: pd.DataFrame) -> pd.DataFrame:
        """
        Grain: 1 Row per buyer_normalized
        """
        if silver_df.empty:
            return pd.DataFrame(columns=[
                "buyer_normalized", "export_country", "export_region",
                "order_count", "active_days", "total_boxes", "total_stickers",
                "allocated_man_hours", "distinct_items", "sticker_share_pct",
                "box_share_pct", "top_items"
            ])

        total_system_stickers = silver_df["sticker_qty"].sum()
        total_system_boxes = silver_df["work_qty"].sum()

        country_col = "export_country" if "export_country" in silver_df.columns else "buyer_normalized"
        region_col = "export_region" if "export_region" in silver_df.columns else "buyer_normalized"

        mart = silver_df.groupby("buyer_normalized").agg(
            export_country=(country_col, "first"),
            export_region=(region_col, "first"),
            order_count=("line_no", "count"),
            active_days=("work_date", "nunique"),
            total_boxes=("work_qty", "sum"),
            total_stickers=("sticker_qty", "sum"),
            allocated_man_hours=("row_man_hours", "sum"),
            distinct_items=("normalized_item_name", "nunique")
        ).reset_index()

        mart["allocated_man_hours"] = mart["allocated_man_hours"].round(1)
        mart["sticker_share_pct"] = (
            mart["total_stickers"] / total_system_stickers * 100
        ).round(2)

        mart["box_share_pct"] = (
            mart["total_boxes"] / total_system_boxes * 100
        ).round(2)

        # Find top 3 items for each buyer
        top_items_map = {}
        for buyer, group in silver_df.groupby("buyer_normalized"):
            top = group.groupby("normalized_item_name")["sticker_qty"].sum().nlargest(3).index.tolist()
            top_items_map[buyer] = ", ".join(top)

        mart["top_items"] = mart["buyer_normalized"].map(top_items_map)
        mart = mart.sort_values("total_stickers", ascending=False)
        return mart

    @staticmethod
    def build_country_summary_mart(silver_df: pd.DataFrame) -> pd.DataFrame:
        """
        Grain: 1 Row per export_country
        """
        if silver_df.empty:
            return pd.DataFrame(columns=[
                "export_country", "export_region", "order_count", "active_days",
                "total_boxes", "total_stickers", "allocated_man_hours",
                "distinct_buyers", "distinct_items", "sticker_share_pct",
                "box_share_pct", "top_items"
            ])

        total_system_stickers = silver_df["sticker_qty"].sum()
        total_system_boxes = silver_df["work_qty"].sum()

        country_col = "export_country" if "export_country" in silver_df.columns else "buyer_normalized"
        region_col = "export_region" if "export_region" in silver_df.columns else "buyer_normalized"

        mart = silver_df.groupby(country_col).agg(
            export_region=(region_col, "first"),
            order_count=("line_no", "count"),
            active_days=("work_date", "nunique"),
            total_boxes=("work_qty", "sum"),
            total_stickers=("sticker_qty", "sum"),
            allocated_man_hours=("row_man_hours", "sum"),
            distinct_buyers=("buyer_normalized", "nunique"),
            distinct_items=("normalized_item_name", "nunique")
        ).reset_index().rename(columns={country_col: "export_country"})

        mart["allocated_man_hours"] = mart["allocated_man_hours"].round(1)
        mart["sticker_share_pct"] = (
            mart["total_stickers"] / max(1, total_system_stickers) * 100
        ).round(2)
        mart["box_share_pct"] = (
            mart["total_boxes"] / max(1, total_system_boxes) * 100
        ).round(2)

        # Top 3 items per country
        top_items_map = {}
        for country, group in silver_df.groupby(country_col):
            top = group.groupby("normalized_item_name")["sticker_qty"].sum().nlargest(3).index.tolist()
            top_items_map[country] = ", ".join(top)

        mart["top_items"] = mart["export_country"].map(top_items_map)
        mart = mart.sort_values("total_stickers", ascending=False)
        return mart

    @staticmethod
    def build_category_summary_mart(silver_df: pd.DataFrame) -> pd.DataFrame:
        """
        Grain: 1 Row per category_1, category_2
        """
        if silver_df.empty:
            return pd.DataFrame(columns=[
                "category_1", "category_2", "item_count", "order_count",
                "total_boxes", "total_stickers", "allocated_man_hours",
                "stickers_per_hour"
            ])

        mart = silver_df.groupby(["category_1", "category_2"]).agg(
            item_count=("normalized_item_name", "nunique"),
            order_count=("line_no", "count"),
            total_boxes=("work_qty", "sum"),
            total_stickers=("sticker_qty", "sum"),
            allocated_man_hours=("row_man_hours", "sum")
        ).reset_index()

        mart["allocated_man_hours"] = mart["allocated_man_hours"].round(1)
        mart["stickers_per_hour"] = (
            mart["total_stickers"] / mart["allocated_man_hours"].replace(0, np.nan)
        ).round(1)

        mart = mart.sort_values("total_stickers", ascending=False)
        return mart

    @staticmethod
    def forecast_capacity_requirements(
        order_list: List[Dict[str, Any]],
        silver_df: pd.DataFrame,
        hours_per_shift: float = 8.0,
        available_workers: int = 8,
        overtime_hours: float = 0.0,
        target_days: float = 1.0
    ) -> Dict[str, Any]:
        """
        Forecasts required man-hours, required worker count, and estimated days
        for a planned batch of orders.
        
        order_list example:
          [{'item_name': '초코파이', 'work_qty': 500, 'pack_qty': 8}, ...]
        """
        item_mart = GoldAnalyticsPipeline.build_item_difficulty_mart(silver_df)
        item_speed_map = dict(zip(item_mart["normalized_item_name"], item_mart["stickers_per_hour"]))
        default_speed = silver_df["sticker_qty"].sum() / silver_df["total_man_hours"].sum() if not silver_df.empty else 180.0

        total_forecast_stickers = 0
        total_forecast_boxes = 0
        total_forecast_hours = 0.0
        item_details = []

        for item in order_list:
            name = item.get("item_name", "기본품목")
            boxes = int(item.get("work_qty", 0))
            pack = int(item.get("pack_qty", 16))
            stickers = boxes * pack
            
            speed = item_speed_map.get(name, default_speed)
            if pd.isna(speed) or speed <= 0:
                speed = default_speed

            req_hours = stickers / speed if speed > 0 else 0.0
            total_forecast_stickers += stickers
            total_forecast_boxes += boxes
            total_forecast_hours += req_hours

            # Difficulty tier
            if pack < 16:
                tier = "저난이도 (16개 미만)"
            elif pack <= 31:
                tier = "중난이도 (16~31개)"
            else:
                tier = "고난이도 (32개 이상)"

            item_details.append({
                "item_name": name,
                "work_qty": boxes,
                "pack_qty": pack,
                "sticker_qty": stickers,
                "benchmark_speed_hr": round(speed, 1),
                "required_hours": round(req_hours, 1),
                "difficulty_tier": tier
            })

        # Calculate share percentage
        for d in item_details:
            d["share_pct"] = round((d["required_hours"] / max(0.001, total_forecast_hours)) * 100, 1)

        # Worker & Time Scenarios
        effective_daily_hours = max(1.0, hours_per_shift + overtime_hours)
        standard_daily_hours = max(1.0, hours_per_shift)
        
        workers_needed_for_1day = round(total_forecast_hours / effective_daily_hours, 1) if effective_daily_hours > 0 else 0
        workers_needed_for_target = round(total_forecast_hours / (max(0.1, target_days) * effective_daily_hours), 1)
        
        days_needed_with_available = round(total_forecast_hours / (max(1, available_workers) * effective_daily_hours), 1)
        days_needed_without_ot = round(total_forecast_hours / (max(1, available_workers) * standard_daily_hours), 1)
        ot_saved_days = round(max(0.0, days_needed_without_ot - days_needed_with_available), 1)

        # Worker Sensitivity curve [2, 4, 6, 8, 10, 12, 16, 20]
        sensitivity_scenarios = []
        for w in [2, 4, 6, 8, 10, 12, 16, 20]:
            d_std = round(total_forecast_hours / (w * standard_daily_hours), 1)
            d_ot = round(total_forecast_hours / (w * effective_daily_hours), 1)
            sensitivity_scenarios.append({
                "worker_count": w,
                "days_standard": d_std,
                "days_with_ot": d_ot
            })

        return {
            "total_planned_stickers": total_forecast_stickers,
            "total_planned_boxes": total_forecast_boxes,
            "total_required_man_hours": round(total_forecast_hours, 1),
            "estimated_workers_1day_target": max(1, int(np.ceil(workers_needed_for_1day))),
            "estimated_workers_target_days": max(1, int(np.ceil(workers_needed_for_target))),
            "estimated_days_with_available_workers": days_needed_with_available,
            "estimated_days_without_ot": days_needed_without_ot,
            "overtime_saved_days": ot_saved_days,
            "estimated_days_with_8workers": round(total_forecast_hours / (8.0 * standard_daily_hours), 1),
            "effective_daily_hours": effective_daily_hours,
            "standard_daily_hours": standard_daily_hours,
            "sensitivity_scenarios": sensitivity_scenarios,
            "item_details": item_details
        }

