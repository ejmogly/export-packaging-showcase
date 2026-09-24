import unittest
import pandas as pd
from src.analytics.lineage_visualizer import (
    determine_consolidation_reason,
    build_lineage_dataset,
    render_interactive_lineage_studio_html,
    build_value_chain_sankey
)

class TestLineageVisualizer(unittest.TestCase):
    def test_determine_consolidation_reason(self):
        self.assertEqual(determine_consolidation_reason("The빠새", "The빠새"), "표준 일치 (Exact)")
        self.assertEqual(determine_consolidation_reason("the빠새", "The빠새"), "대소문자 통일 (Case Normalization)")
        self.assertEqual(determine_consolidation_reason("The 빠새", "The빠새"), "띄어쓰기 정규화 (Whitespace Trim)")
        self.assertEqual(determine_consolidation_reason("쿠쿠다스 화이트", "쿠크다스화이트"), "수기/OCR 오타 교정 (Typo Correction)")

    def test_build_lineage_dataset_and_html(self):
        silver_data = pd.DataFrame([
            {"item_name": "The 빠새", "normalized_item_name": "The빠새", "work_date": "2026-03-01", "sticker_qty": 500, "match_type": "alias"},
            {"item_name": "The빠새", "normalized_item_name": "The빠새", "work_date": "2026-03-02", "sticker_qty": 1000, "match_type": "exact"},
            {"item_name": "포카칩 어니언", "normalized_item_name": "포카칩어니언", "work_date": "2026-03-03", "sticker_qty": 800, "match_type": "alias"},
            {"item_name": "포카칩어니언", "normalized_item_name": "포카칩어니언", "work_date": "2026-03-04", "sticker_qty": 1200, "match_type": "exact"},
        ])
        dim_item_data = pd.DataFrame([
            {"item_name": "The빠새", "item_code": "ITM-001", "manufacturer_name": "해태", "category_1": "과자", "category_2": "스낵", "standard_volume": "60g"},
            {"item_name": "포카칩어니언", "item_code": "ITM-002", "manufacturer_name": "오리온", "category_1": "과자", "category_2": "스낵", "standard_volume": "66g"},
        ])

        lineage_df, multi_variant_items, items_catalog = build_lineage_dataset(silver_data, dim_item_data)
        self.assertEqual(len(multi_variant_items), 2)
        self.assertEqual(len(items_catalog), 2)
        self.assertEqual(items_catalog[0]["canon_name"], "The빠새")

        html_str = render_interactive_lineage_studio_html(items_catalog, initial_focus="The빠새")
        self.assertIn("The빠새", html_str)
        self.assertIn("flow-svg", html_str)
        self.assertIn("canvasWrap", html_str)

    def test_build_value_chain_sankey(self):
        base_df = pd.DataFrame([
            {"buyer_normalized": "신세계푸드", "manufacturer": "오리온", "category_2": "스낵", "sticker_qty": 1000},
            {"buyer_normalized": "오리온베트남", "manufacturer": "롯데웰푸드", "category_2": "초콜릿", "sticker_qty": 2000},
        ])
        fig = build_value_chain_sankey(base_df, focus_buyer="신세계푸드")
        self.assertIsNotNone(fig)
        self.assertEqual(len(fig.data), 1)

    def test_variant_counts_and_subtab3_filtering(self):
        silver_data = pd.DataFrame([
            {"item_name": "The 빠새", "normalized_item_name": "The빠새", "work_date": "2026-03-01", "work_month": "2026-03", "sticker_qty": 500, "buyer_normalized": "신세계", "manufacturer": "해태", "match_type": "alias"},
            {"item_name": "the빠새", "normalized_item_name": "The빠새", "work_date": "2026-03-02", "work_month": "2026-03", "sticker_qty": 300, "buyer_normalized": "신세계", "manufacturer": "해태", "match_type": "case"},
            {"item_name": "The빠새", "normalized_item_name": "The빠새", "work_date": "2026-04-02", "work_month": "2026-04", "sticker_qty": 1000, "buyer_normalized": "이마트", "manufacturer": "해태", "match_type": "exact"},
            {"item_name": "포카칩 어니언", "normalized_item_name": "포카칩어니언", "work_date": "2026-03-03", "work_month": "2026-03", "sticker_qty": 800, "buyer_normalized": "신세계", "manufacturer": "오리온", "match_type": "alias"},
            {"item_name": "포카칩어니언", "normalized_item_name": "포카칩어니언", "work_date": "2026-04-04", "work_month": "2026-04", "sticker_qty": 1200, "buyer_normalized": "이마트", "manufacturer": "오리온", "match_type": "exact"},
            {"item_name": "화이트화임", "normalized_item_name": "화이트하임", "work_date": "2026-03-05", "work_month": "2026-03", "sticker_qty": 400, "buyer_normalized": "신세계", "manufacturer": "크라운", "match_type": "typo"},
            {"item_name": "화이트하임", "normalized_item_name": "화이트하임", "work_date": "2026-03-06", "work_month": "2026-03", "sticker_qty": 600, "buyer_normalized": "신세계", "manufacturer": "크라운", "match_type": "exact"},
        ])
        dim_item_data = pd.DataFrame([
            {"item_name": "The빠새", "item_code": "ITM-001", "manufacturer_name": "해태", "category_1": "과자", "category_2": "스낵", "standard_volume": "60g"},
            {"item_name": "포카칩어니언", "item_code": "ITM-002", "manufacturer_name": "오리온", "category_1": "과자", "category_2": "스낵", "standard_volume": "66g"},
            {"item_name": "화이트하임", "item_code": "ITM-003", "manufacturer_name": "크라운", "category_1": "과자", "category_2": "비스킷", "standard_volume": "142g"},
        ])

        lineage_df, multi_variant_items, items_catalog = build_lineage_dataset(silver_data, dim_item_data)
        
        # Test 3 or more filter
        cand_3_plus = [it["canon_name"] for it in items_catalog if it["variants_count"] >= 3]
        self.assertEqual(cand_3_plus, ["The빠새"])
        
        # Test typo and space catalog flags
        cand_typo = [it["canon_name"] for it in items_catalog if it["has_typo"]]
        self.assertEqual(cand_typo, ["화이트하임"])
        cand_space = [it["canon_name"] for it in items_catalog if it["has_space"]]
        self.assertIn("The빠새", cand_space)
        self.assertIn("포카칩어니언", cand_space)

        # Test date filtering affects cross-tab
        filtered_march = silver_data[silver_data["work_month"] == "2026-03"]
        filtered_april = silver_data[silver_data["work_month"] == "2026-04"]
        ct_march = pd.crosstab(filtered_march["buyer_normalized"], filtered_march["manufacturer"], values=filtered_march["sticker_qty"], aggfunc="sum").fillna(0)
        ct_april = pd.crosstab(filtered_april["buyer_normalized"], filtered_april["manufacturer"], values=filtered_april["sticker_qty"], aggfunc="sum").fillna(0)

        # In March, buyer was 신세계; in April, buyer was 이마트
        self.assertIn("신세계", ct_march.index)
        self.assertNotIn("이마트", ct_march.index)
        self.assertIn("이마트", ct_april.index)
        self.assertNotIn("신세계", ct_april.index)

if __name__ == "__main__":
    unittest.main()
