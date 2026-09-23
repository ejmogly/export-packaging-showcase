import os
import sys
import unittest
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.loader import (
    load_raw_sticker_data,
    load_item_master,
    load_item_alias_mapping,
    load_workforce_plan,
    load_dim_item,
    load_dim_manufacturer,
    load_dim_buyer
)
from src.transformation.item_normalizer import ItemNormalizer
from src.quality.validator import DataQualityValidator
from src.transformation.silver_pipeline import build_silver_layer
from src.analytics.gold_pipeline import GoldAnalyticsPipeline
from src.reporting.email_reporter import generate_weekly_report_html


class TestStickerPackagingAnalytics(unittest.TestCase):

    def test_01_loader_data_exists(self):
        """Test that data loader successfully fetches raw data, item master, and aliases."""
        raw_df, status = load_raw_sticker_data()
        self.assertFalse(raw_df.empty, "Raw sticker dataset should not be empty")
        self.assertIn("item_name", raw_df.columns)
        self.assertIn("sticker_qty", raw_df.columns)

        master_df = load_item_master()
        self.assertFalse(master_df.empty, "Item master should not be empty")
        self.assertIn("제품명", master_df.columns)

        alias_df = load_item_alias_mapping()
        self.assertIn("raw_alias", alias_df.columns)

    def test_02_item_normalizer_tiers(self):
        """Test Multi-Layer item normalization and defense buffers."""
        master_df = load_item_master()
        alias_df = load_item_alias_mapping()
        normalizer = ItemNormalizer(master_df, alias_df)

        # 1. Alias match test
        res_alias = normalizer.resolve_item("촉칩")
        self.assertIn("초코", res_alias["normalized_item_name"])

        # 2. Exact match test
        res_exact = normalizer.resolve_item("초코파이")
        self.assertEqual(res_exact["normalized_item_name"], "초코파이")
        self.assertEqual(res_exact["manufacturer"], "오리온")

        # 3. Token-Sort Order Invariance test (콘스프 꼬북칩 -> 꼬북칩 콘스프)
        res_ts = normalizer.resolve_item("콘스프 꼬북칩")
        self.assertEqual(res_ts["match_type"], "TOKEN_SORT")
        self.assertIn("꼬북", res_ts["normalized_item_name"])
        self.assertIn("콘스프", res_ts["normalized_item_name"])

        # 4. Packaging / Spec Stripping test
        res_spec = normalizer.resolve_item("허니버터칩 60g")
        self.assertTrue(res_spec["match_confidence"] > 0.8)
        self.assertEqual(res_spec["normalized_item_name"], "허니버터칩")

        # 5. Contextual pack_qty disambiguation test (홈런볼)
        res_bulk = normalizer.resolve_item("홈런볼", pack_qty=12)
        self.assertIn("벌크", res_bulk["normalized_item_name"])

        res_single = normalizer.resolve_item("홈런볼", pack_qty=30)
        self.assertFalse("벌크" in res_single["normalized_item_name"])
        self.assertIn("홈런볼", res_single["normalized_item_name"])

    def test_03_data_quality_validator(self):
        """Test Data Quality quantity mismatch detection."""
        test_df = pd.DataFrame([
            {"item_name": "초코파이", "pack_qty": 8, "work_qty": 10, "sticker_qty": 80, "worker_count": 5},
            {"item_name": "초코파이", "pack_qty": 8, "work_qty": 10, "sticker_qty": 100, "worker_count": 0}, # Mismatch & zero worker
        ])
        audited, summary = DataQualityValidator.audit_dataset(test_df)
        self.assertEqual(summary["qty_mismatch_count"], 1)
        self.assertEqual(summary["worker_missing_count"], 1)
        self.assertTrue(audited.loc[1, "qty_mismatch_flag"])
        self.assertTrue(audited.loc[1, "worker_missing_flag"])

    def test_04_silver_pipeline_and_gold_marts(self):
        """Test end-to-end Silver and Gold transformation."""
        silver_df, dq_report, status = build_silver_layer()
        self.assertFalse(silver_df.empty)
        self.assertIn("normalized_item_name", silver_df.columns)
        self.assertIn("manufacturer", silver_df.columns)
        self.assertIn("buyer_normalized", silver_df.columns)
        self.assertIn("stickers_per_man_hour", silver_df.columns)

        # Gold Marts
        daily_mart = GoldAnalyticsPipeline.build_daily_productivity_mart(silver_df)
        self.assertFalse(daily_mart.empty)
        self.assertIn("stickers_per_man_hour", daily_mart.columns)

        item_mart = GoldAnalyticsPipeline.build_item_difficulty_mart(silver_df)
        self.assertFalse(item_mart.empty)
        self.assertIn("difficulty_tier", item_mart.columns)

        buyer_mart = GoldAnalyticsPipeline.build_buyer_summary_mart(silver_df)
        self.assertFalse(buyer_mart.empty)
        self.assertIn("sticker_share_pct", buyer_mart.columns)

    def test_05_capacity_forecast_model(self):
        """Test the workforce capacity forecasting simulator."""
        silver_df, _, _ = build_silver_layer()
        sample_orders = [
            {"item_name": "초코파이", "work_qty": 500, "pack_qty": 8},
            {"item_name": "허니버터칩", "work_qty": 200, "pack_qty": 16}
        ]
        forecast = GoldAnalyticsPipeline.forecast_capacity_requirements(sample_orders, silver_df)
        self.assertEqual(forecast["total_planned_stickers"], (500*8 + 200*16))
        self.assertTrue(forecast["total_required_man_hours"] > 0)
        self.assertTrue(forecast["estimated_workers_1day_target"] >= 1)

    def test_06_email_report_html_generation(self):
        """Test that the weekly HTML report generates properly."""
        silver_df, _, _ = build_silver_layer()
        html, stats = generate_weekly_report_html(silver_df)
        self.assertIn("📦 스티커 작업 주간 실적 리포트", html)
        self.assertIn("총 부착 스티커 수량", html)
        self.assertTrue(stats["total_stickers"] > 0)

    def test_07_master_dimensions(self):
        """Test master dimension tables generation and schema."""
        dim_mfg = load_dim_manufacturer()
        self.assertFalse(dim_mfg.empty)
        self.assertIn("manufacturer_id", dim_mfg.columns)
        self.assertIn("business_category", dim_mfg.columns)
        self.assertGreaterEqual(len(dim_mfg), 25)

        dim_buyer = load_dim_buyer()
        self.assertFalse(dim_buyer.empty)
        self.assertIn("buyer_id", dim_buyer.columns)
        self.assertIn("export_country", dim_buyer.columns)
        self.assertIn("buyer_type", dim_buyer.columns)
        self.assertGreaterEqual(len(dim_buyer), 70)

        dim_item = load_dim_item()
        self.assertFalse(dim_item.empty)
        self.assertIn("item_code", dim_item.columns)
        self.assertIn("difficulty_tier", dim_item.columns)
        self.assertIn("benchmark_speed_hr", dim_item.columns)
        self.assertGreaterEqual(len(dim_item), 400)

    def test_08_profitability_financial_engine(self):
        """Test financial margin analyzer formulas, labor cost at 13,000 KRW/hr, and tiered pricing."""
        silver_df, _, _ = build_silver_layer()
        self.assertFalse(silver_df.empty)

        hourly_wage = 13000
        unit_stk = 30.0

        # Labor cost
        silver_df["labor_cost"] = silver_df["row_man_hours"] * hourly_wage
        total_labor = silver_df["labor_cost"].sum()
        self.assertGreater(total_labor, 150000000)  # Over 1.5억 원

        # Revenue (Flat 30 KRW/sticker)
        silver_df["revenue_flat"] = silver_df["sticker_qty"] * unit_stk
        total_rev_flat = silver_df["revenue_flat"].sum()
        self.assertGreater(total_rev_flat, 170000000)  # Over 1.7억 원

        # Gross profit
        gross_profit_flat = total_rev_flat - total_labor
        self.assertGreater(gross_profit_flat, 0)  # Flat pricing maintains positive gross margin

        # Tiered pricing (25 KRW for <16, 30 KRW for 16~31, 40 KRW for >=32)
        import numpy as np
        conditions = [
            silver_df["pack_qty"] < 16,
            (silver_df["pack_qty"] >= 16) & (silver_df["pack_qty"] < 32),
            silver_df["pack_qty"] >= 32
        ]
        rates = np.select(conditions, [25.0, 30.0, 40.0], default=30.0)
        silver_df["revenue_tiered"] = silver_df["sticker_qty"] * rates
        total_rev_tiered = silver_df["revenue_tiered"].sum()

        # Tiered pricing should yield higher revenue than flat 30 KRW due to high-density items
        self.assertGreater(total_rev_tiered, total_rev_flat)

    def test_09_buyer_trends_and_supply_chain(self):
        """Test quarterly derivation, customer health classification, and Sankey graph balance."""
        silver_df, _, _ = build_silver_layer()

        # 1. Quarter derivation
        df = silver_df.copy()
        df["quarter"] = pd.to_datetime(df["work_date"]).dt.to_period("Q").astype(str)
        quarters = sorted(df["quarter"].dropna().unique())
        self.assertIn("2026Q1", quarters)
        self.assertIn("2026Q2", quarters)
        self.assertIn("2026Q3", quarters)

        # 2. Customer health MoM calculation
        months = sorted(df["work_month"].dropna().unique())
        latest_m, prev_m = months[-1], months[-2]
        hp = df[df["work_month"].isin([prev_m, latest_m])].groupby(["buyer_normalized", "work_month"])["sticker_qty"].sum().unstack(fill_value=0)
        self.assertIn("거복", hp.index)
        self.assertGreater(hp.loc["거복", latest_m], hp.loc["거복", prev_m])  # High growth

        # 3. Supply chain Sankey balance
        top_buyers = df.groupby("buyer_normalized")["sticker_qty"].sum().nlargest(5).index.tolist()
        top_mfgs = df.groupby("manufacturer")["sticker_qty"].sum().nlargest(4).index.tolist()
        top_cats = df.groupby("category_2")["sticker_qty"].sum().nlargest(4).index.tolist()

        df["b_node"] = df["buyer_normalized"].apply(lambda x: x if x in top_buyers else "Other_Buyer")
        df["m_node"] = df["manufacturer"].apply(lambda x: x if x in top_mfgs else "Other_Mfg")
        df["c_node"] = df["category_2"].apply(lambda x: x if x in top_cats else "Other_Cat")

        f1 = df.groupby(["b_node", "m_node"])["sticker_qty"].sum().reset_index()
        f2 = df.groupby(["m_node", "c_node"])["sticker_qty"].sum().reset_index()

        # Flow conservation: total stickers in flow 1 equals flow 2
        self.assertEqual(f1["sticker_qty"].sum(), f2["sticker_qty"].sum())


if __name__ == "__main__":
    unittest.main()
