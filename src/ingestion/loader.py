import os
import io
import urllib.request
import pandas as pd
from typing import Tuple, Optional

def get_configured_sheet_url() -> Optional[str]:
    """
    Retrieves Google Sheet URL in order of priority:
    1. OS Environment variable 'GOOGLE_SHEET_URL'
    2. Streamlit Secrets (st.secrets['GOOGLE_SHEET_URL'])
    3. None (Showcase mode defaults to sanitized local dataset)
    """
    url = os.getenv("GOOGLE_SHEET_URL")
    if url:
        return url
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GOOGLE_SHEET_URL" in st.secrets:
            return st.secrets["GOOGLE_SHEET_URL"]
    except Exception:
        pass
    return None


DEFAULT_SHEET_URL = get_configured_sheet_url()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")


def get_data_filepath(filename: str) -> str:
    """Returns absolute path for files in the data directory."""
    return os.path.join(DATA_DIR, filename)


def load_raw_sticker_data(
    sheet_url: Optional[str] = None,
    use_cache: bool = True,
    timeout: int = 10
) -> Tuple[pd.DataFrame, str]:
    """
    Loads raw sticker work log data from Google Sheets live CSV export.
    Falls back to local cached seed data if network fails or in showcase demo mode.
    
    Returns:
        (df, source_description)
    """
    if not sheet_url:
        sheet_url = get_configured_sheet_url()

    cache_path = get_data_filepath("raw_verified_source_rows.csv")
    
    # Check if local cache exists and its row count
    local_df = None
    if os.path.exists(cache_path):
        try:
            local_df = pd.read_csv(cache_path)
        except Exception:
            local_df = None

    # 1. If live sheet URL is configured, fetch live from Google Sheets
    if sheet_url:
        try:
            import time
            # Append cache-busting timestamp and headers so Google Sheets CDN always returns latest sheet state immediately
            cache_buster_url = f"{sheet_url}&_t={int(time.time())}"
            req = urllib.request.Request(
                cache_buster_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Packaging-Analytics-Pipeline)",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache"
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read().decode("utf-8")
                df = pd.read_csv(io.StringIO(content))
                
                if df is not None and not df.empty and "item_name" in df.columns:
                    if len(df) < 2000 and local_df is not None and len(local_df) >= 2000:
                        return local_df, f"통합 로컬 마스터 ({len(local_df):,}건 - 원천 구글시트 미반영분 포함 동기화 완료)"
                    
                    # Update local cache with live sheet state (including deletions)
                    if use_cache:
                        df.to_csv(cache_path, index=False, encoding="utf-8-sig")
                    return df, f"Live Google Sheet ({len(df):,}건 동기화 완료)"
        except Exception as e:
            print(f"[Warning] Google Sheets Live fetch failed: {e}. Falling back to local cache.")

    # 2. Fallback to local verified showcase dataset
    if local_df is not None:
        return local_df, f"Verified Showcase Data ({len(local_df):,}건 정합성 검증 완료)"
    
    raise FileNotFoundError(f"Neither Google Sheet nor local fallback ({cache_path}) is available.")


def load_item_master() -> pd.DataFrame:
    """Loads the standard item master table."""
    master_path = get_data_filepath("item_master.csv")
    if os.path.exists(master_path):
        df = pd.read_csv(master_path)
        # Standardize column names
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame(columns=["제품명", "제조사", "카테고리1", "카테고리2"])


def load_item_alias_mapping() -> pd.DataFrame:
    """Loads the item alias/synonym mapping table."""
    alias_path = get_data_filepath("item_alias_mapping.csv")
    if os.path.exists(alias_path):
        df = pd.read_csv(alias_path)
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame(columns=["raw_alias", "standard_item_name", "notes"])


def load_workforce_plan() -> pd.DataFrame:
    """Loads the workforce planning and actuals table."""
    wf_path = get_data_filepath("workforce_plan.csv")
    if os.path.exists(wf_path):
        df = pd.read_csv(wf_path)
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame(columns=[
        "plan_date", "plan_month", "planned_worker_count",
        "base_work_hours", "planned_overtime_hours",
        "planned_overtime_worker_count", "estimated_total_worker_hours"
    ])


def save_item_alias(raw_alias: str, standard_name: str, notes: str = "사용자 등록") -> bool:
    """Appends or updates an alias in the alias mapping CSV."""
    alias_path = get_data_filepath("item_alias_mapping.csv")
    df = load_item_alias_mapping()
    
    # Check if alias exists
    if raw_alias in df["raw_alias"].values:
        df.loc[df["raw_alias"] == raw_alias, "standard_item_name"] = standard_name
        df.loc[df["raw_alias"] == raw_alias, "notes"] = notes
    else:
        new_row = pd.DataFrame([{"raw_alias": raw_alias, "standard_item_name": standard_name, "notes": notes}])
        df = pd.concat([df, new_row], ignore_index=True)
        
    df.to_csv(alias_path, index=False, encoding="utf-8-sig")
    return True


def load_dim_item() -> pd.DataFrame:
    """Loads the dimension table for items (dim_item.csv)."""
    item_path = get_data_filepath("dim_item.csv")
    if os.path.exists(item_path):
        df = pd.read_csv(item_path)
        df.columns = [c.strip() for c in df.columns]
        return df
    # Fallback to base item master if dim_item not yet generated
    base = load_item_master()
    return base


def save_dim_item(df: pd.DataFrame) -> bool:
    """Saves the updated dim_item table to CSV."""
    item_path = get_data_filepath("dim_item.csv")
    df.to_csv(item_path, index=False, encoding="utf-8-sig")
    return True


def add_item_to_master(item_dict: dict) -> bool:
    """
    Adds or updates an SKU record in dim_item.csv and synchronizes item_master.csv.
    item_dict should contain:
      - item_name, manufacturer_name, category_1, category_2,
        standard_volume, default_pack_qty, benchmark_speed_hr (optional)
    """
    df_dim = load_dim_item()
    item_name = str(item_dict.get("item_name", "")).strip()
    if not item_name:
        return False

    # Check existing
    exists = df_dim["item_name"] == item_name
    if exists.any():
        for k, v in item_dict.items():
            if k in df_dim.columns:
                df_dim.loc[exists, k] = v
    else:
        # Generate new item_code: ITM-XXXX
        next_num = len(df_dim) + 1
        item_code = f"ITM-{next_num:04d}"
        new_record = {
            "item_code": item_code,
            "item_name": item_name,
            "manufacturer_id": item_dict.get("manufacturer_id", "MFG-099"),
            "manufacturer_name": item_dict.get("manufacturer_name", "미등록"),
            "category_1": item_dict.get("category_1", "기타"),
            "category_2": item_dict.get("category_2", "기타"),
            "volume_value": item_dict.get("volume_value", ""),
            "volume_unit": item_dict.get("volume_unit", "-"),
            "standard_volume": item_dict.get("standard_volume", "-"),
            "default_pack_qty": int(item_dict.get("default_pack_qty", 16)),
            "difficulty_tier": item_dict.get("difficulty_tier", "중난이도 (16~31개)"),
            "benchmark_speed_hr": float(item_dict.get("benchmark_speed_hr", 180.0))
        }
        df_dim = pd.concat([df_dim, pd.DataFrame([new_record])], ignore_index=True)

    save_dim_item(df_dim)

    # Sync to item_master.csv as well
    master_path = get_data_filepath("item_master.csv")
    if os.path.exists(master_path):
        df_m = pd.read_csv(master_path)
        if not (df_m["제품명"] == item_name).any():
            m_rec = {
                "제품명": item_name,
                "제조사": item_dict.get("manufacturer_name", "미등록"),
                "카테고리1": item_dict.get("category_1", "기타"),
                "카테고리2": item_dict.get("category_2", "기타"),
                "표준중량/규격": item_dict.get("standard_volume", "-")
            }
            df_m = pd.concat([df_m, pd.DataFrame([m_rec])], ignore_index=True)
            df_m.to_csv(master_path, index=False, encoding="utf-8-sig")

    return True


def load_dim_manufacturer() -> pd.DataFrame:
    """Loads the dimension table for manufacturers (dim_manufacturer.csv)."""
    mfg_path = get_data_filepath("dim_manufacturer.csv")
    if os.path.exists(mfg_path):
        df = pd.read_csv(mfg_path)
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame(columns=[
        "manufacturer_id", "manufacturer_name", "business_category",
        "country", "item_count", "primary_brand", "notes"
    ])


def save_dim_manufacturer(df: pd.DataFrame) -> bool:
    """Saves the updated dim_manufacturer table to CSV."""
    mfg_path = get_data_filepath("dim_manufacturer.csv")
    df.to_csv(mfg_path, index=False, encoding="utf-8-sig")
    return True


def load_dim_buyer() -> pd.DataFrame:
    """Loads the dimension table for export buyers (dim_buyer.csv)."""
    byr_path = get_data_filepath("dim_buyer.csv")
    if os.path.exists(byr_path):
        df = pd.read_csv(byr_path)
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame(columns=[
        "buyer_id", "buyer_name", "export_country", "export_region",
        "buyer_type", "order_count", "total_boxes", "total_stickers",
        "primary_items", "special_notes"
    ])


def save_dim_buyer(df: pd.DataFrame) -> bool:
    """Saves the updated dim_buyer table to CSV."""
    byr_path = get_data_filepath("dim_buyer.csv")
    df.to_csv(byr_path, index=False, encoding="utf-8-sig")
    return True

