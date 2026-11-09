import os
import re
import pandas as pd
from src.ingestion.loader import (
    load_raw_sticker_data,
    load_item_master,
    load_item_alias_mapping,
    load_workforce_plan,
    get_data_filepath
)
from src.transformation.item_normalizer import ItemNormalizer
from src.quality.validator import DataQualityValidator


def _load_confirmed_buyer_overrides() -> dict[str, tuple[str, str]]:
    """
    Loads confirmed buyer and country mappings from buyer_dimension_review_list.csv
    (including D01 -> 해태제과 and any future stakeholder-confirmed codes).
    """
    overrides: dict[str, tuple[str, str]] = {
        "D01": ("해태제과", ""),
    }
    review_path = get_data_filepath("buyer_dimension_review_list.csv")
    if os.path.exists(review_path):
        try:
            df_rev = pd.read_csv(review_path)
            for _, row in df_rev.iterrows():
                raw_rem = str(row.get("원본_비고(remark)", "")).strip()
                conf_buyer = str(row.get("현업확인_표준바이어명(작성란)", "")).strip()
                conf_country = str(row.get("현업확인_수출국가(작성란)", "")).strip()
                if raw_rem and conf_buyer and conf_buyer.lower() != "nan":
                    c_val = "" if conf_country.lower() == "nan" else conf_country
                    overrides[raw_rem] = (conf_buyer, c_val)
        except Exception:
            pass
    return overrides


def normalize_buyer(remark_val: any, buyer_overrides: dict[str, tuple[str, str]] | None = None) -> str:
    """Normalizes the remark column into standard buyer / export destination."""
    if not remark_val or pd.isna(remark_val):
        return "기타/일반"

    remark_str = str(remark_val).strip()

    # 1. Stakeholder-confirmed dimension overrides (e.g. D01 -> 해태제과)
    if buyer_overrides and remark_str in buyer_overrides:
        return buyer_overrides[remark_str][0]
    if remark_str.upper() == "D01":
        return "해태제과"

    # Showcase Sanitized Patterns (for export_packaging_showcase compatibility)
    if "Global_Mart_Canada" in remark_str:
        return "Global_Mart_Canada (캐나다)"
    elif "Pacific_Trade" in remark_str:
        return "Pacific_Trade (캐나다)"
    elif "Euro_PanAsia" in remark_str:
        if "오스트리아" in remark_str:
            return "Euro_PanAsia (오스트리아)"
        elif "독일" in remark_str:
            return "Euro_PanAsia (독일)"
        return "Euro_PanAsia"
    elif "Central_Asia" in remark_str:
        return "Central_Asia_Logistics (몽골)"
    elif "K-Mart_Canada" in remark_str:
        return "K-Mart_Canada (캐나다)"
    elif "Oceania_Health" in remark_str:
        return "Oceania_Health (호주)"
    elif "H-Mart_Global" in remark_str:
        return "H-Mart_Global (미주)"
    elif "Global_Trading_H" in remark_str:
        return "Global_Trading_H"
    elif "HanSang_Partners" in remark_str:
        return "HanSang_Partners"
    elif "Hamchorom_Global" in remark_str:
        return "Hamchorom_Global"
    elif "Vancouver_Logistics" in remark_str:
        return "Vancouver_Logistics"
    elif "Distributor_007" in remark_str:
        return "Distributor_007 (캐나다)"

    # 2. Common Patterns
    if "판아시아" in remark_str:
        if "오스트리아" in remark_str:
            return "판아시아 (오스트리아)"
        elif "독일" in remark_str:
            return "판아시아 (독일)"
        return "판아시아"
    elif "롯데" in remark_str and ("캐나다" in remark_str or "케나다" in remark_str):
        return "롯데 (캐나다)"
    elif "KFT" in remark_str:
        return "KFT (캐나다)"
    elif "007" in remark_str:
        return "007 (캐나다)"
    elif "캐나다" in remark_str or "케나다" in remark_str:
        return "캐나다 직수출"
    elif "몽골" in remark_str or "아눈구" in remark_str:
        return "아눈구 (몽골)"
    elif "거복" in remark_str:
        return "거복"
    elif "KR" in remark_str and "트레이딩" in remark_str:
        return "KR 트레이딩"
    elif "희창" in remark_str:
        return "희창물산"
    elif "함초롬" in remark_str or "함초롱" in remark_str:
        return "함초롬"
    elif "광동" in remark_str:
        if "싱가폴" in remark_str or "싱가포르" in remark_str or "싱동" in remark_str or "싱롱" in remark_str:
            return "광동 (싱가포르)"
        elif "인도네시아" in remark_str:
            return "광동 (인도네시아)"
        elif "뉴질랜드" in remark_str:
            return "광동 (뉴질랜드)"
        elif "호주" in remark_str:
            return "광동 (호주)"
        return "광동 해외"
    elif "호주" in remark_str and ("코스월드" in remark_str or "신미" in remark_str):
        return "광동 (호주)"
    elif "피지" in remark_str:
        return "피지 (오세아니아)"
    elif "H마트" in remark_str or "H-Mart" in remark_str or "267" in remark_str:
        return "H-Mart (미주)"
    elif "팔라마" in remark_str:
        return "팔라마 (미주)"
    elif "대만" in remark_str:
        return "대만 직수출"
    elif remark_str in ("해태제과(DK)", "해태 오크라", "해태오크라", "해태 BFG리테일"):
        return "해태제과"
    elif remark_str.isdigit():
        return f"Order #{remark_str}"
    elif re.match(r"^[A-Z]\d{2}", remark_str):
        return f"Order #{remark_str}"

    return remark_str


def extract_export_country(buyer_val: any) -> tuple[str, str]:
    """Extracts standard export destination country and continental region."""
    b = str(buyer_val).strip() if buyer_val and not pd.isna(buyer_val) else ""
    if "독일" in b:
        return "독일", "유럽"
    elif "오스트리아" in b:
        return "오스트리아", "유럽"
    elif any(k in b for k in ["캐나다", "케나다", "KFT", "벤쿠버", "토론토", "센츄리"]):
        return "캐나다", "북미"
    elif any(k in b for k in ["H-Mart", "H마트", "미주", "미국", "팔라마", "하와이"]):
        return "미국", "북미"
    elif "몽골" in b or "아눈구" in b:
        return "몽골", "아시아"
    elif "피지" in b:
        return "피지", "오세아니아"
    elif "뉴질랜드" in b:
        return "뉴질랜드", "오세아니아"
    elif "호주" in b:
        return "호주", "오세아니아"
    elif "인도네시아" in b:
        return "인도네시아", "아시아"
    elif any(k in b for k in ["싱가포르", "싱가폴", "싱동", "싱롱"]):
        return "싱가포르", "아시아"
    elif "대만" in b:
        return "대만", "아시아"
    elif "러시아" in b or "사이베리아" in b:
        return "러시아", "유라시아"
    elif any(vendor in b for vendor in ["거복", "한상", "함초롬", "함초롱", "희창", "KR 트레이딩", "지오엔", "다온", "경북통상", "케이글로벌", "Global_Trading_H", "HanSang_Partners", "Hamchorom_Global", "KR_Trading_Corp"]):
        return "수출 벤더사", "글로벌 무역상사"
    elif b.startswith("Order #") or b == "해태제과":
        return "수출 오더코드", "일반 오더"
    else:
        return "기타 수출처", "기타"


def build_silver_layer() -> tuple[pd.DataFrame, dict, str]:
    """
    Executes Silver Layer transformation:
      1. Load Bronze Raw Data + Master Data + Alias Mapping
      2. Run Item Normalizer (multi-tier resolution)
      3. Run Data Quality Validator (including special work pattern recognition)
      4. Standardize Buyers & Export Countries via Buyer Dimension overrides
      5. Join with Workforce Actuals & Calculate Effective Man-Hours

    Returns:
      (silver_df, quality_report, source_status)
    """
    raw_df, source_status = load_raw_sticker_data()
    master_df = load_item_master()
    alias_df = load_item_alias_mapping()
    wf_df = load_workforce_plan()
    buyer_overrides = _load_confirmed_buyer_overrides()

    # 1. Basic Type Casting & Cleaning
    df = raw_df.copy()
    df["work_date"] = pd.to_datetime(df["work_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["work_month"] = df["work_date"].str.slice(0, 7)
    df["worker_count"] = pd.to_numeric(df["worker_count"], errors="coerce").fillna(0.0)
    df["pack_qty"] = pd.to_numeric(df["pack_qty"], errors="coerce").fillna(0).astype(int)
    df["work_qty"] = pd.to_numeric(df["work_qty"], errors="coerce").fillna(0).astype(int)
    df["sticker_qty"] = pd.to_numeric(df["sticker_qty"], errors="coerce").fillna(0).astype(int)

    # 2. Item Normalization with Multi-Layer Defense Buffers
    normalizer = ItemNormalizer(master_df=master_df, alias_df=alias_df)
    try:
        normalized_df = normalizer.batch_normalize(df, item_col="item_name", pack_qty_col="pack_qty")
    except TypeError:
        normalized_df = normalizer.batch_normalize(df, item_col="item_name")

    # 3. Data Quality Audit (recognizes tray x4, double sticker x2, outer box, consumables)
    silver_df, quality_summary = DataQualityValidator.audit_dataset(normalized_df)

    # Distinguish product cartons from outer box ('box') / consumable rows
    silver_df["shipped_box_qty"] = silver_df["work_qty"].where(~silver_df["is_auxiliary_item"], 0)

    # 4. Buyer Normalization & Country/Region Enrichment
    silver_df["buyer_normalized"] = silver_df["remark"].apply(lambda r: normalize_buyer(r, buyer_overrides))
    country_region = silver_df["buyer_normalized"].apply(extract_export_country)
    silver_df["export_country"] = [cr[0] for cr in country_region]
    silver_df["export_region"] = [cr[1] for cr in country_region]
    silver_df["is_confirmed_country"] = ~silver_df["export_country"].isin(["수출 벤더사", "수출 오더코드", "기타 수출처"])

    # 5. Enrich with Workforce Data (Effective Man-Hours)
    daily_stats = silver_df.groupby("work_date").agg(
        day_total_stickers=("sticker_qty", "sum"),
        day_total_boxes=("work_qty", "sum"),
        day_lines=("line_no", "count"),
        day_worker_count=("worker_count", "max")
    ).reset_index()

    if not wf_df.empty:
        wf_df["plan_date"] = pd.to_datetime(wf_df["plan_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        daily_stats = daily_stats.merge(
            wf_df[["plan_date", "base_work_hours", "planned_overtime_hours", "estimated_total_worker_hours"]],
            left_on="work_date",
            right_on="plan_date",
            how="left"
        )
    else:
        daily_stats["base_work_hours"] = 8.0
        daily_stats["planned_overtime_hours"] = 0.0
        daily_stats["estimated_total_worker_hours"] = daily_stats["day_worker_count"] * 8.0

    daily_stats["base_work_hours"] = daily_stats["base_work_hours"].fillna(8.0)
    daily_stats["planned_overtime_hours"] = daily_stats["planned_overtime_hours"].fillna(0.0)

    avg_workers = daily_stats[daily_stats["day_worker_count"] > 0]["day_worker_count"].mean()
    if pd.isna(avg_workers) or avg_workers <= 0:
        avg_workers = 9.0

    daily_stats["effective_worker_count"] = daily_stats["day_worker_count"].apply(
        lambda w: avg_workers if w <= 0 else w
    )
    daily_stats["total_man_hours"] = (
        daily_stats["effective_worker_count"] * daily_stats["base_work_hours"] +
        daily_stats["effective_worker_count"] * daily_stats["planned_overtime_hours"]
    )

    silver_df = silver_df.merge(
        daily_stats[["work_date", "effective_worker_count", "total_man_hours", "day_total_stickers", "day_total_boxes"]],
        on="work_date",
        how="left"
    )

    # Row-level allocated man-hours (proportional to sticker volume share within the day)
    silver_df["row_man_hours"] = (
        silver_df["sticker_qty"] / silver_df["day_total_stickers"].replace(0, 1)
    ) * silver_df["total_man_hours"]

    silver_df["stickers_per_man_hour"] = (
        silver_df["sticker_qty"] / silver_df["row_man_hours"].replace(0, 1)
    ).round(1)

    return silver_df, quality_summary, source_status
