import re
import pandas as pd
from src.ingestion.loader import (
    load_raw_sticker_data,
    load_item_master,
    load_item_alias_mapping,
    load_workforce_plan
)
from src.transformation.item_normalizer import ItemNormalizer
from src.quality.validator import DataQualityValidator


def normalize_buyer(remark_val: any) -> str:
    """Normalizes the remark column into standard buyer / export destination."""
    if not remark_val or pd.isna(remark_val):
        return "기타/일반"
    
    remark_str = str(remark_val).strip()
    
    # Showcase Sanitized Patterns
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
    
    # Common Patterns
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
        if "싱가폴" in remark_str or "싱가포르" in remark_str or "싱동" in remark_str:
            return "광동 (싱가포르)"
        elif "인도네시아" in remark_str:
            return "광동 (인도네시아)"
        elif "뉴질랜드" in remark_str:
            return "광동 (뉴질랜드)"
        return "광동 해외"
    elif "피지" in remark_str:
        return "피지 (오세아니아)"
    elif "H마트" in remark_str or "H-Mart" in remark_str or "267" in remark_str:
        return "H-Mart (미주)"
    elif "팔라마" in remark_str:
        return "팔라마 (미주)"
    elif "대만" in remark_str:
        return "대만 직수출"
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
    elif "캐나다" in b or "케나다" in b or "KFT" in b:
        return "캐나다", "북미"
    elif "H-Mart" in b or "미주" in b or "미국" in b or "팔라마" in b:
        return "미국", "북미"
    elif "몽골" in b or "아눈구" in b:
        return "몽골", "아시아"
    elif "피지" in b:
        return "피지", "오세아니아"
    elif "뉴질랜드" in b:
        return "뉴질랜드", "오세아니아"
    elif "인도네시아" in b:
        return "인도네시아", "아시아"
    elif "싱가포르" in b or "싱가폴" in b or "싱동" in b:
        return "싱가포르", "아시아"
    elif "대만" in b:
        return "대만", "아시아"
    elif "러시아" in b:
        return "러시아", "유라시아"
    elif any(vendor in b for vendor in ["거복", "한상", "함초롬", "희창", "KR 트레이딩", "Global_Trading_H", "HanSang_Partners", "Hamchorom_Global", "KR_Trading_Corp"]):
        return "수출 벤더사", "글로벌 무역상사"
    elif b.startswith("Order #"):
        return "수출 오더코드", "일반 오더"
    else:
        return "기타 수출처", "기타"


def build_silver_layer() -> tuple[pd.DataFrame, dict, str]:
    """
    Executes Silver Layer transformation:
      1. Load Bronze Raw Data + Master Data + Alias Mapping
      2. Run Item Normalizer (4-tier resolution)
      3. Run Data Quality Validator
      4. Standardize Buyers & Dates
      5. Join with Workforce Actuals & Calculate Effective Man-Hours
    
    Returns:
      (silver_df, quality_report, source_status)
    """
    raw_df, source_status = load_raw_sticker_data()
    master_df = load_item_master()
    alias_df = load_item_alias_mapping()
    wf_df = load_workforce_plan()

    # 1. Basic Type Casting & Cleaning
    df = raw_df.copy()
    df["work_date"] = pd.to_datetime(df["work_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["work_month"] = df["work_date"].str.slice(0, 7)
    df["worker_count"] = pd.to_numeric(df["worker_count"], errors="coerce").fillna(0.0)
    df["pack_qty"] = pd.to_numeric(df["pack_qty"], errors="coerce").fillna(0).astype(int)
    df["work_qty"] = pd.to_numeric(df["work_qty"], errors="coerce").fillna(0).astype(int)
    df["sticker_qty"] = pd.to_numeric(df["sticker_qty"], errors="coerce").fillna(0).astype(int)

    # 2. Item Normalization
    normalizer = ItemNormalizer(master_df=master_df, alias_df=alias_df)
    normalized_df = normalizer.batch_normalize(df, item_col="item_name")

    # 3. Data Quality Audit
    silver_df, quality_summary = DataQualityValidator.audit_dataset(normalized_df)

    # 4. Buyer Normalization & Country/Region Enrichment
    silver_df["buyer_normalized"] = silver_df["remark"].apply(normalize_buyer)
    country_region = silver_df["buyer_normalized"].apply(extract_export_country)
    silver_df["export_country"] = [cr[0] for cr in country_region]
    silver_df["export_region"] = [cr[1] for cr in country_region]

    # 5. Enrich with Workforce Data (Effective Man-Hours)
    # Calculate daily total stickers and lines per date
    daily_stats = silver_df.groupby("work_date").agg(
        day_total_stickers=("sticker_qty", "sum"),
        day_total_boxes=("work_qty", "sum"),
        day_lines=("line_no", "count"),
        day_worker_count=("worker_count", "max")
    ).reset_index()

    # If workforce plan exists, join it
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

    # Fill default work hours: worker_count * 8.0
    daily_stats["base_work_hours"] = daily_stats["base_work_hours"].fillna(8.0)
    daily_stats["planned_overtime_hours"] = daily_stats["planned_overtime_hours"].fillna(0.0)
    
    # Effective worker count (if 0, estimate from non-zero days average ~9.0)
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

    # Merge daily man-hours back into silver
    silver_df = silver_df.merge(
        daily_stats[["work_date", "effective_worker_count", "total_man_hours", "day_total_stickers", "day_total_boxes"]],
        on="work_date",
        how="left"
    )

    # Row-level allocated man-hours (proportional to sticker volume share within the day)
    silver_df["row_man_hours"] = (
        silver_df["sticker_qty"] / silver_df["day_total_stickers"].replace(0, 1)
    ) * silver_df["total_man_hours"]

    # Calculate row-level productivity
    silver_df["stickers_per_man_hour"] = (
        silver_df["sticker_qty"] / silver_df["row_man_hours"].replace(0, 1)
    ).round(1)

    return silver_df, quality_summary, source_status
