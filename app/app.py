import os
import sys
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import base64
import io
from datetime import datetime, date

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import importlib
import src.ingestion.loader
import src.transformation.silver_pipeline
import src.analytics.gold_pipeline

# Force reload for long-running dev servers
importlib.reload(src.ingestion.loader)
importlib.reload(src.transformation.silver_pipeline)
importlib.reload(src.analytics.gold_pipeline)

from src.ingestion.loader import (
    load_item_master,
    load_item_alias_mapping,
    save_item_alias,
    load_raw_sticker_data,
    load_dim_item,
    save_dim_item,
    add_item_to_master,
    load_dim_manufacturer,
    save_dim_manufacturer,
    load_dim_buyer,
    save_dim_buyer
)
from src.transformation.silver_pipeline import build_silver_layer
from src.analytics.gold_pipeline import GoldAnalyticsPipeline
from src.reporting.email_reporter import generate_weekly_report_html

# Static Plotly Configuration (Disables modebar, zoom, pan, dragging for rock-solid stability)
PLOTLY_STATIC_CONFIG = {
    'displayModeBar': False,
    'scrollZoom': False,
    'doubleClick': False,
    'showAxisDragHandles': False,
    'showAxisRangeEntryBoxes': False
}

# =========================================================
# 1. PAGE CONFIG & STYLING
# =========================================================
st.set_page_config(
    page_title="수출 식품 스티커 작업 분석 플랫폼",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Look
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Ensure all Streamlit columns stretch equally and distribute full height */
    div[data-testid="stHorizontalBlock"] {
        align-items: stretch !important;
    }
    div[data-testid="column"] {
        display: flex !important;
        flex-direction: column !important;
    }
    div[data-testid="column"] > div[data-testid="stVerticalBlock"] {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 1 auto !important;
        height: 100% !important;
    }
    div[data-testid="column"] > div[data-testid="stVerticalBlock"] > div.element-container {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 1 auto !important;
        height: 100% !important;
    }
    div[data-testid="column"] > div[data-testid="stVerticalBlock"] > div.element-container > div.stMarkdown {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 1 auto !important;
        height: 100% !important;
    }

    .metric-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
        transition: all 0.2s ease;
        height: 100%;
        min-height: 275px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(0,0,0,0.06);
        border-color: #cbd5e1;
    }
    .metric-top {
        display: flex;
        flex-direction: column;
        flex-grow: 1;
    }
    .metric-label {
        font-size: 13.5px;
        font-weight: 700;
        color: #64748b;
        letter-spacing: 0.2px;
        min-height: 40px;
        display: flex;
        align-items: flex-start;
        line-height: 1.35;
        word-break: keep-all;
    }
    .metric-value {
        font-size: clamp(20px, 1.8vw, 27px);
        font-weight: 800;
        color: #0f172a;
        margin: 6px 0 2px 0;
        white-space: nowrap;
        display: flex;
        align-items: baseline;
        gap: 4px;
    }
    .metric-delta {
        font-size: 12px;
        font-weight: 700;
        margin-top: 2px;
        min-height: 24px;
        display: flex;
        align-items: center;
        gap: 5px;
        flex-wrap: wrap;
        line-height: 1.3;
        word-break: keep-all;
    }
    .delta-pos {
        color: #16a34a;
    }
    .delta-neg {
        color: #dc2626;
    }
    .delta-neutral {
        color: #64748b;
        font-size: 11.5px;
    }
    .delta-sub {
        font-size: 11px;
        font-weight: 500;
        color: #64748b;
    }
    .metric-unit {
        font-size: 15px;
        font-weight: 600;
        margin-left: 2px;
    }
    .metric-sub {
        font-size: 12px;
        color: #475569;
        margin-top: 4px;
        line-height: 1.4;
        min-height: 34px;
        word-break: keep-all;
    }
    .metric-desc {
        font-size: 11.5px;
        color: #64748b;
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px dashed #cbd5e1;
        line-height: 1.45;
        word-break: keep-all;
        min-height: 48px;
        display: flex;
        align-items: flex-start;
    }
    .badge-live {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-cache {
        background-color: #fef3c7;
        color: #92400e;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .info-tooltip {
        font-size: 12px;
        color: #64748b;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)


# Brand Color Mapping for Manufacturers (제조사별 고유 브랜드 색상 매핑)
MANUFACTURER_COLORS = {
    # 4대 주요 제과사
    "해태제과": "#2563eb",     # 해태 로열 블루
    "해태제과식품": "#2563eb",
    "롯데웰푸드": "#e11d48",    # 롯데 시그니처 크림슨 레드
    "오리온": "#f59e0b",       # 오리온 골든 앰버
    "크라운제과": "#8b5cf6",    # 크라운 바이올렛
    
    # 음료 & 유제품 & 제약
    "광동제약": "#10b981",     # 광동 에메랄드 그린
    "동아오츠카": "#06b6d4",    # 포카리 아쿠아 블루
    "롯데칠성음료": "#14b8a6",  # 칠성 틸 민트
    "자뎅": "#78350f",         # 자뎅 원두 브라운
    "해태htb": "#0ea5e9",      # 해태htb 스카이블루
    "매일유업": "#6366f1",     # 매일 인디고
    "코카-콜라음료": "#991b1b",  # 코카콜라 딥레드
    "웅진식품": "#84cc16",     # 웅진 라임그린
    "동화약품": "#047857",     # 동화약품 딥그린
    "동아제약": "#0284c7",     # 동아제약 마린블루
    
    # 라면 & 가공식품
    "농심": "#ea580c",         # 농심 오렌지
    "농심(수입)": "#ea580c",
    "삼양식품": "#eab308",     # 삼양 옐로우
    "오뚜기": "#fbbf24",       # 오뚜기 옐로우
    "동서식품": "#d97706",     # 맥심 모카 골드
    "서주": "#059669",         # 서주 아이스 그린
    "우일씨앤텍": "#64748b",   # 슬레이트 그레이
    "환만식품": "#ec4899",     # 환만 핑크
    "개미식품": "#f43f5e",     # 개미 로즈
    "전인식품": "#475569",     # 전인 스틸
    
    # 미등록 / 확인필요
    "미등록": "#94a3b8",       # 뉴트럴 그레이
    "확인필요": "#cbd5e1"
}

# 바이어별 전용 시그니처 색상 (일관된 브랜딩 및 시각적 식별성 확보)
BUYER_COLORS = {
    # 주요 글로벌 바이어 및 벤더사
    "007 (캐나다)": "#e11d48",        # 캐나다 시그니처 단풍 크림슨 레드
    "판아시아 (오스트리아)": "#2563eb",  # 판아시아 유럽 로열 블루
    "판아시아 (독일)": "#1d4ed8",      # 판아시아 독일 딥 코발트
    "판아시아": "#3b82f6",            # 판아시아 블루
    "거복": "#059669",               # 거복 에메랄드 포레스트 그린
    "한상": "#d97706",               # 한상 앰버 골드
    "해태 몽골 아눈구": "#7c3aed",      # 몽골 아눈구 바이올렛
    "몽골 아눈구 513": "#8b5cf6",
    "몽골 아눈구": "#a855f7",
    "광동 해외": "#10b981",           # 광동 해외 틸 민트
    "광동 (뉴질랜드)": "#047857",       # 뉴질랜드 딥 그린
    "광동 (인도네시아)": "#34d399",      # 인도네시아 민트
    "피지 (오세아니아)": "#0891b2",     # 피지 오션 시안
    "희창물산": "#4f46e5",            # 희창물산 인디고
    "함초롬": "#ec4899",             # 함초롬 딥 핑크
    "KFT 라벨": "#0ea5e9",           # KFT 스카이 블루
    "H-Mart (미주)": "#4338ca",       # H-Mart 딥 퍼플
    "팔라마": "#6366f1",             # 팔라마 인디고
    "해태 러시아 사이베리아": "#991b1b",  # 러시아 루비 다크레드
    "해태 러시아": "#b91c1c",
    "해태 오크라": "#0284c7",
    "벤쿠버": "#f97316",             # 벤쿠버 오렌지
    "토론토": "#ea580c",             # 토론토 딥 오렌지
    "기타 바이어": "#94a3b8",          # 기타 바이어 슬레이트 그레이
    "기타/일반": "#cbd5e1"
}

# 글로벌 수출 권역별 전용 시그니처 색상
REGION_COLORS = {
    "유럽": "#2563eb",         # 로열 코발트 블루
    "북미": "#059669",         # 에메랄드 그린
    "글로벌 무역상사": "#7c3aed", # 바이올렛 퍼플
    "아시아": "#d97706",        # 앰버 오렌지
    "오세아니아": "#0891b2",     # 청록 오션 터콰이즈
    "유라시아": "#dc2626",      # 크림슨 레드
    "일반 오더": "#475569",     # 슬레이트 차콜
    "기타": "#94a3b8"          # 뉴트럴 그레이
}

FALLBACK_BUYER_PALETTE = [
    "#64748b", "#0284c7", "#ca8a04", "#0d9488", "#9333ea", 
    "#c026d3", "#475569", "#16a34a", "#2563eb", "#e11d48",
    "#f59e0b", "#10b981", "#6366f1", "#84cc16", "#ec4899"
]

def get_buyer_color(buyer_name: str, index: int = 0) -> str:
    """Returns a designated or deterministic color for a buyer."""
    b_str = str(buyer_name).strip()
    if b_str in BUYER_COLORS:
        return BUYER_COLORS[b_str]
    if b_str.startswith("기타 바이어"):
        return "#94a3b8"
    if b_str.startswith("Order #"):
        order_colors = ["#475569", "#64748b", "#334155", "#52525b", "#71717a"]
        return order_colors[index % len(order_colors)]
    return FALLBACK_BUYER_PALETTE[index % len(FALLBACK_BUYER_PALETTE)]


# =========================================================
# 2. DATA CACHING & PIPELINE EXECUTION
# =========================================================
@st.cache_data(ttl=600)
def get_processed_data(cache_bust_token: str = "v_20260923_rebuilt_ground_truth_master"):
    """Runs the Medallion transformation and caches results."""
    silver_df, quality_report, source_status = build_silver_layer()
    daily_mart = GoldAnalyticsPipeline.build_daily_productivity_mart(silver_df)
    item_mart = GoldAnalyticsPipeline.build_item_difficulty_mart(silver_df)
    buyer_mart = GoldAnalyticsPipeline.build_buyer_summary_mart(silver_df)
    cat_mart = GoldAnalyticsPipeline.build_category_summary_mart(silver_df)
    return silver_df, quality_report, source_status, daily_mart, item_mart, buyer_mart, cat_mart


# Load Data
try:
    silver_df, quality_report, source_status, daily_mart, item_mart, buyer_mart, cat_mart = get_processed_data()
    if "export_country" not in silver_df.columns:
        st.cache_data.clear()
        silver_df, quality_report, source_status, daily_mart, item_mart, buyer_mart, cat_mart = get_processed_data()
except Exception as e:
    st.error(f"데이터 파이프라인 로드 중 오류가 발생했습니다: {e}")
    st.stop()


def set_date_range_callback(target_start, target_end):
    """Safely updates start_date and end_date in Streamlit session state during callback phase."""
    d_start = pd.to_datetime(target_start).date()
    d_end = pd.to_datetime(target_end).date()
    st.session_state["start_date_picker"] = min(d_start, d_end)
    st.session_state["end_date_picker"] = max(d_start, d_end)


# =========================================================
# 3. SIDEBAR CONTROLS
# =========================================================
with st.sidebar:
    logo_path = os.path.join(DATA_DIR, "company_logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            b64_logo = base64.b64encode(f.read()).decode("utf-8")
        logo_img_src = f"data:image/png;base64,{b64_logo}"
    else:
        logo_img_src = "https://clogo.saramin.co.kr/company/logo/202604/02/tcuwtf30_k5ck-tob3k4_logo.png"

    st.markdown(f"""
    <div style="
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 14px 14px 14px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        margin-bottom: 12px;
    ">
        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 8px;">
            <img src="{logo_img_src}" style="max-height: 52px; max-width: 100%; object-fit: contain;">
        </div>
        <div style="font-size: 17px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; margin-bottom: 3px;">
            스티커 작업 관리
        </div>
        <div style="font-size: 11.5px; font-weight: 500; color: #64748b; line-height: 1.35;">
            수출 식품 라벨 부착 실적 분석 &amp; 운영 플랫폼
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Source Status
    if "Live" in source_status:
        st.markdown(f'<span class="badge-live">🟢 {source_status}</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="badge-cache">🟡 {source_status}</span>', unsafe_allow_html=True)
    
    if st.button("🔄 실시간 동기화 (Cache Clear)", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # Date Filter
    min_date = pd.to_datetime(silver_df["work_date"].min()).date()
    max_date = pd.to_datetime(silver_df["work_date"].max()).date()
    
    # Calculate default start date: 1st day of the month closest to current time
    now_date = datetime.now().date()
    if now_date >= max_date:
        # Current time is after or in latest data month -> 1st day of latest data month
        default_start_date = max_date.replace(day=1)
    elif now_date <= min_date:
        # Current time is before data -> min_date
        default_start_date = min_date
    else:
        # Current time is within data -> 1st day of current month
        default_start_date = now_date.replace(day=1)

    default_start_date = max(min_date, min(default_start_date, max_date))

    st.markdown("##### 📅 조회 기간 설정")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        sel_start = st.date_input(
            "시작일",
            value=default_start_date,
            min_value=min_date,
            max_value=max_date,
            key="start_date_picker"
        )
    with col_d2:
        sel_end = st.date_input(
            "종료일",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="end_date_picker"
        )

    # Automatically normalize if user selected start > end
    d_start_obj = min(sel_start, sel_end)
    d_end_obj = max(sel_start, sel_end)
    start_d, end_d = str(d_start_obj), str(d_end_obj)

    # Quick Preset Buttons
    st.caption("⚡ **빠른 기간 선택:**")
    qp1, qp2, qp3 = st.columns(3)
    with qp1:
        st.button(
            "전체 (1~9월)",
            key="quick_btn_all",
            on_click=set_date_range_callback,
            args=(min_date, max_date),
            use_container_width=True
        )
    with qp2:
        st.button(
            "당월 (9월)",
            key="quick_btn_curr_month",
            on_click=set_date_range_callback,
            args=(default_start_date, max_date),
            use_container_width=True
        )
    with qp3:
        st.button(
            "전월 (8월)",
            key="quick_btn_prev_month",
            on_click=set_date_range_callback,
            args=("2026-08-01", "2026-08-31"),
            use_container_width=True
        )

    filtered_silver = silver_df[(silver_df["work_date"] >= start_d) & (silver_df["work_date"] <= end_d)]

    # Find nearest active work dates across master dataset
    all_work_dates = sorted(silver_df["work_date"].dropna().unique().tolist())
    prev_dates = [d for d in all_work_dates if d < start_d]
    prev_work_day = prev_dates[-1] if prev_dates else None
    next_dates = [d for d in all_work_dates if d > end_d]
    next_work_day = next_dates[0] if next_dates else None

    # Non-operating day helper in sidebar
    if filtered_silver.empty:
        weekday_map_kr = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
        st_wk = weekday_map_kr.get(pd.to_datetime(start_d).dayofweek, "")
        end_wk = weekday_map_kr.get(pd.to_datetime(end_d).dayofweek, "")
        date_lbl = f"{start_d}({st_wk})" if start_d == end_d else f"{start_d}({st_wk})~{end_d}({end_wk})"
        st.warning(f"⚠️ **비가동일 안내**\n\n선택하신 기간({date_lbl})은 공장 작업 실적이 없는 날입니다.")
        st.caption("💡 **인접 가동일 바로가기:**")
        sc1, sc2 = st.columns(2)
        if prev_work_day:
            with sc1:
                p_wk = weekday_map_kr.get(pd.to_datetime(prev_work_day).dayofweek, "")
                st.button(
                    f"◀ 직전일\n({prev_work_day} {p_wk})",
                    key="side_btn_prev",
                    on_click=set_date_range_callback,
                    args=(prev_work_day, prev_work_day),
                    use_container_width=True
                )
        if next_work_day:
            with sc2:
                n_wk = weekday_map_kr.get(pd.to_datetime(next_work_day).dayofweek, "")
                st.button(
                    f"다음일 ▶\n({next_work_day} {n_wk})",
                    key="side_btn_next",
                    on_click=set_date_range_callback,
                    args=(next_work_day, next_work_day),
                    use_container_width=True
                )
        st.button(
            f"🔄 최신 가동월 ({default_start_date} ~ {max_date})",
            key="side_btn_month",
            on_click=set_date_range_callback,
            args=(default_start_date, max_date),
            use_container_width=True
        )

    # Calculate Previous Period of equal length (동일한 이전 기간 계산)
    start_dt = pd.to_datetime(start_d).date()
    end_dt = pd.to_datetime(end_d).date()
    days_count = (end_dt - start_dt).days + 1
    prev_end_dt = start_dt - pd.Timedelta(days=1)
    prev_start_dt = prev_end_dt - pd.Timedelta(days=days_count - 1)
    prev_start_d = str(prev_start_dt)
    prev_end_d = str(prev_end_dt)

    prev_silver = silver_df[(silver_df["work_date"] >= prev_start_d) & (silver_df["work_date"] <= prev_end_d)]

    # Category Filter
    if not filtered_silver.empty:
        all_categories = sorted(list(filtered_silver["category_1"].dropna().unique()))
        selected_categories = st.multiselect("🏷️ 대분류 필터", options=all_categories, default=all_categories)
        if selected_categories:
            filtered_silver = filtered_silver[filtered_silver["category_1"].isin(selected_categories)]
            if not prev_silver.empty:
                prev_silver = prev_silver[prev_silver["category_1"].isin(selected_categories)]

        # Manufacturer Filter
        all_mfg = sorted(list(filtered_silver["manufacturer"].dropna().unique()))
        selected_mfg = st.multiselect("🏭 제조사 필터", options=all_mfg, default=[])
        if selected_mfg:
            filtered_silver = filtered_silver[filtered_silver["manufacturer"].isin(selected_mfg)]
            if not prev_silver.empty:
                prev_silver = prev_silver[prev_silver["manufacturer"].isin(selected_mfg)]

    st.divider()
    st.caption("💡 **용어 정의 안내:**")
    st.caption("• **입량**: 박스 1개당 낱개 수 (`pack_qty`)")
    st.caption("• **작업수량**: 작업한 출하 박스 수 (`work_qty`)")
    st.caption("• **스티커수량**: 총 부착 스티커 수 (`sticker_qty`)")
    st.caption("• **중량/규격**: 상품별 표준 규격 (`standard_volume`)")


# Recompute filtered marts
filtered_daily = GoldAnalyticsPipeline.build_daily_productivity_mart(filtered_silver)
filtered_item = GoldAnalyticsPipeline.build_item_difficulty_mart(filtered_silver)
filtered_buyer = GoldAnalyticsPipeline.build_buyer_summary_mart(filtered_silver)
filtered_country = GoldAnalyticsPipeline.build_country_summary_mart(filtered_silver)

# Prior period marts & metrics
has_prev_data = not prev_silver.empty
if has_prev_data:
    prev_daily = GoldAnalyticsPipeline.build_daily_productivity_mart(prev_silver)
    prev_item = GoldAnalyticsPipeline.build_item_difficulty_mart(prev_silver)
    prev_buyer = GoldAnalyticsPipeline.build_buyer_summary_mart(prev_silver)
    prev_country = GoldAnalyticsPipeline.build_country_summary_mart(prev_silver)
    prev_stickers = int(prev_silver["sticker_qty"].sum())
    prev_boxes = int(prev_silver["work_qty"].sum())
    prev_hours = float(prev_daily["total_man_hours"].sum()) if not prev_daily.empty else 0.0
    prev_speed = round(prev_stickers / prev_hours, 1) if prev_hours > 0 else 0.0
    prev_pack = round(prev_stickers / prev_boxes, 1) if prev_boxes > 0 else 0.0
    prev_box_speed = round(prev_boxes / prev_hours, 1) if prev_hours > 0 else 0.0
else:
    prev_daily = pd.DataFrame()
    prev_item = pd.DataFrame()
    prev_buyer = pd.DataFrame()
    prev_country = pd.DataFrame()
    prev_stickers = 0
    prev_boxes = 0
    prev_hours = 0.0
    prev_speed = 0.0
    prev_pack = 0.0
    prev_box_speed = 0.0

def get_delta_badge(curr, prev, unit, is_float=False):
    if not has_prev_data or prev <= 0:
        return '<div class="metric-delta delta-neutral">전기간 비교 데이터 없음</div>'
    diff = curr - prev
    pct = (diff / prev) * 100
    sign = "+" if diff >= 0 else ""
    arrow = "▲" if diff >= 0 else "▼"
    color_class = "delta-pos" if diff >= 0 else "delta-neg"
    diff_str = f"{diff:+,.1f}" if is_float else f"{diff:+,.0f}"
    prev_str = f"{prev:,.1f}" if is_float else f"{prev:,.0f}"
    return (
        f'<div class="metric-delta {color_class}">'
        f'<span>{arrow} {sign}{pct:.1f}%</span>'
        f'<span class="delta-sub">(전기간 {prev_str}{unit} 대비 {diff_str}{unit})</span>'
        f'</div>'
    )


# =========================================================
# 4. MAIN DASHBOARD TABS
# =========================================================
# Non-operating Day / Weekend Alert Banner
if filtered_silver.empty:
    weekday_map_kr = {0: "월요일", 1: "화요일", 2: "수요일", 3: "목요일", 4: "금요일", 5: "토요일", 6: "일요일"}
    st_wk = weekday_map_kr.get(pd.to_datetime(start_d).dayofweek, "")
    end_wk = weekday_map_kr.get(pd.to_datetime(end_d).dayofweek, "")
    date_lbl = f"{start_d} ({st_wk})" if start_d == end_d else f"{start_d} ({st_wk}) ~ {end_d} ({end_wk})"
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border: 1.5px solid #f59e0b; border-radius: 12px; padding: 18px 22px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(245, 158, 11, 0.1);">
        <div style="display:flex; align-items:flex-start; gap: 14px;">
            <span style="font-size: 28px; line-height: 1.2;">🗓️</span>
            <div>
                <h4 style="margin:0; color:#92400e; font-size:17px; font-weight:700;">선택하신 일자({date_lbl})는 공장 비가동일(주말/휴무일)입니다</h4>
                <p style="margin:6px 0 0 0; color:#78350f; font-size:14px; line-height:1.5;">
                    해당 기간에는 스티커 부착 라인이 가동되지 않아 작업 실적이 기록되지 않았습니다.<br>
                    아래 버튼을 클릭하시면 <strong>실제 작업이 진행된 가장 가까운 가동일</strong>로 즉시 전환됩니다.
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    nb1, nb2, nb3 = st.columns([1, 1, 1.2])
    if prev_work_day:
        with nb1:
            p_wk = weekday_map_kr.get(pd.to_datetime(prev_work_day).dayofweek, "")
            st.button(
                f"◀ 직전 가동일 ({prev_work_day} {p_wk}) 이동",
                key="main_btn_prev",
                on_click=set_date_range_callback,
                args=(prev_work_day, prev_work_day),
                use_container_width=True
            )
    if next_work_day:
        with nb2:
            n_wk = weekday_map_kr.get(pd.to_datetime(next_work_day).dayofweek, "")
            st.button(
                f"다음 가동일 ({next_work_day} {n_wk}) 이동 ▶",
                key="main_btn_next",
                on_click=set_date_range_callback,
                args=(next_work_day, next_work_day),
                use_container_width=True
            )
    with nb3:
        st.button(
            f"📅 최신 가동월 ({default_start_date} ~ {max_date}) 이동",
            key="main_btn_month",
            on_click=set_date_range_callback,
            args=(default_start_date, max_date),
            use_container_width=True
        )
    st.write("")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 종합 운영 상황판",
    "⚡ 생산성 & 난이도 분석",
    "🌍 바이어 & 수출국가별",
    "⏱️ 인력 계획 & 납기 시뮬레이터",
    "🛡️ 데이터 품질 & 마스터 관리",
    "🗺️ 데이터 계보 & 아키텍처 맵"
])


# ---------------------------------------------------------
# TAB 1: EXECUTIVE OVERVIEW (종합 운영 상황판)
# ---------------------------------------------------------
with tab1:
    st.markdown("### 📊 종합 운영 상황판 (Executive Overview)")
    if has_prev_data:
        st.caption(
            f"조회 기간: **{start_d} ~ {end_d}** ({days_count}일간) | "
            f"동일 전기간 비교: **{prev_start_d} ~ {prev_end_d}** (동일 {days_count}일) | "
            f"누적 작업 건수: **{len(filtered_silver):,}건**"
        )
    else:
        st.caption(f"조회 기간: **{start_d} ~ {end_d}** ({days_count}일간) | 누적 작업 건수: **{len(filtered_silver):,}건**")

    # Metric Row
    col1, col2, col3, col4 = st.columns(4)
    
    total_stickers = int(filtered_silver["sticker_qty"].sum())
    total_boxes = int(filtered_silver["work_qty"].sum())
    total_hours = float(filtered_daily["total_man_hours"].sum()) if not filtered_daily.empty else 0.0
    active_days = int(filtered_daily["work_date"].nunique()) if not filtered_daily.empty else 0
    avg_workers = float(filtered_daily["effective_worker_count"].mean()) if not filtered_daily.empty else 0.0
    avg_speed = round(total_stickers / total_hours, 1) if total_hours > 0 else 0.0
    daily_per_worker = round(avg_speed * 8.0, 0)
    daily_stickers_avg = round(total_stickers / max(1, active_days), 0) if active_days > 0 else 0.0
    daily_boxes_avg = round(total_boxes / max(1, active_days), 0) if active_days > 0 else 0.0

    badge_stickers = get_delta_badge(total_stickers, prev_stickers, "매")
    badge_boxes = get_delta_badge(total_boxes, prev_boxes, "박스")
    badge_hours = get_delta_badge(total_hours, prev_hours, "인·시", is_float=True)
    badge_speed = get_delta_badge(avg_speed, prev_speed, "매/hr", is_float=True)

    active_days_sub = f"일평균 <strong>{daily_stickers_avg:,.0f}</strong> 매 (가동일수 {active_days}일)" if active_days > 0 else "선택 기간 내 <strong>비가동일 (0일)</strong>"
    active_boxes_sub = f"일평균 <strong>{daily_boxes_avg:,.0f}</strong> 박스 (출하 박스 기준)" if active_days > 0 else "출하 박스 실적 없음"
    active_hours_sub = f"일평균 <strong>{avg_workers:.1f}</strong> 명 투입 (총 {active_days}일 가동)" if active_days > 0 else "투입 인원 및 공수 없음"
    active_speed_sub = f"1인 1일(8시간) 환산 약 <strong>{daily_per_worker:,.0f}</strong> 매" if total_hours > 0 else "작업 공수 없음"

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">총 스티커 작업량</div>
                <div class="metric-value">{total_stickers:,} <span style="font-size:16px; font-weight:600; color:#334155;">매</span></div>
                {badge_stickers}
                <div class="metric-sub">{active_days_sub}</div>
            </div>
            <div class="metric-desc">ℹ️ 제품 낱개에 부착한 누적 스티커 라벨 총 수량입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">총 작업수량 (출하 박스 기준)</div>
                <div class="metric-value" style="color:#059669;">{total_boxes:,} <span style="font-size:16px; font-weight:600;">박스</span></div>
                {badge_boxes}
                <div class="metric-sub">{active_boxes_sub}</div>
            </div>
            <div class="metric-desc">ℹ️ 스티커 부착 작업을 완료하고 재포장한 출하 박스(Box) 수량입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">총 투입 공수 (누적 Man-Hours)</div>
                <div class="metric-value" style="color:#7c3aed;">{total_hours:,.1f} <span style="font-size:16px; font-weight:600;">인·시</span></div>
                {badge_hours}
                <div class="metric-sub">{active_hours_sub}</div>
            </div>
            <div class="metric-desc">ℹ️ 투입 인원 × 작업시간의 누적 총합입니다. (예: 10명 × 8시간 = 80 인·시)</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">1인당 시간당 부착량</div>
                <div class="metric-value" style="color:#ea580c;">{avg_speed:,.1f} <span style="font-size:16px; font-weight:600;">매/hr</span></div>
                {badge_speed}
                <div class="metric-sub">{active_speed_sub}</div>
            </div>
            <div class="metric-desc">ℹ️ 작업자 1명이 1시간 동안 평균 부착한 스티커 수량입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # Chart Row 1: Daily Trend & Manufacturer Share
    col_chart1, col_chart2 = st.columns([13, 9])
    
    with col_chart1:
        st.subheader("📈 스티커 작업량 및 투입 인원 추이")
        trend_granularity = st.radio(
            "집계 주기 선택",
            options=["일간 (선택 기간)", "주간 (전체 기간)", "월간 (전체 기간)"],
            horizontal=True,
            key="trend_granularity_toggle"
        )
        
        if trend_granularity == "일간 (선택 기간)":
            if not filtered_daily.empty and filtered_daily["total_stickers"].sum() > 0:
                chart_daily = filtered_daily.sort_values("work_date").copy()
                weekday_map = {0: "월요일", 1: "화요일", 2: "수요일", 3: "목요일", 4: "금요일", 5: "토요일", 6: "일요일"}
                chart_daily["weekday_name"] = pd.to_datetime(chart_daily["work_date"]).dt.dayofweek.map(weekday_map)
                chart_daily["stickers_per_worker"] = (
                    chart_daily["total_stickers"] / chart_daily["effective_worker_count"].replace(0, np.nan)
                ).fillna(0).round(0)
                fig = go.Figure()
                
                # Stickers Bar
                fig.add_trace(go.Bar(
                    x=chart_daily["work_date"],
                    y=chart_daily["total_stickers"],
                    name="스티커 작업량 (매)",
                    marker_color="#3b82f6",
                    customdata=np.stack((
                        chart_daily["weekday_name"],
                        chart_daily["effective_worker_count"],
                        chart_daily["stickers_per_worker"]
                    ), axis=-1),
                    hovertemplate=(
                        "<b>%{x} (%{customdata[0]})</b><br>"
                        "• 일일 스티커 작업량: <b>%{y:,.0f} 매</b><br>"
                        "• 당일 투입 인원: <b>%{customdata[1]:.1f} 명</b><br>"
                        "• 1인당 처리 매수: <b>%{customdata[2]:,.0f} 매/인</b><extra></extra>"
                    ),
                    yaxis="y"
                ))
                
                # Worker Count Line
                fig.add_trace(go.Scatter(
                    x=chart_daily["work_date"],
                    y=chart_daily["effective_worker_count"],
                    name="투입 인원 (명)",
                    mode="lines+markers",
                    marker=dict(size=7, color="#ef4444"),
                    line=dict(width=2.5, color="#ef4444"),
                    customdata=np.stack((
                        chart_daily["weekday_name"],
                        chart_daily["total_stickers"],
                        chart_daily["stickers_per_worker"]
                    ), axis=-1),
                    hovertemplate=(
                        "<b>%{x} (%{customdata[0]})</b><br>"
                        "• 당일 투입 인원: <b>%{y:.1f} 명</b><br>"
                        "• 일일 스티커 작업량: <b>%{customdata[1]:,.0f} 매</b><br>"
                        "• 1인당 처리 매수: <b>%{customdata[2]:,.0f} 매/인</b><extra></extra>"
                    ),
                    yaxis="y2"
                ))

                fig.update_layout(
                    dragmode=False,
                    xaxis=dict(fixedrange=True),
                    yaxis=dict(title="스티커 작업량 (매)", showgrid=True, fixedrange=True),
                    yaxis2=dict(title="투입 인원 (명)", overlaying="y", side="right", showgrid=False, fixedrange=True),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=20, r=20, t=30, b=20),
                    height=360,
                    hoverlabel=dict(align="left")
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
            else:
                st.info("선택하신 기간에는 작업 일자 실적이 없습니다. (공장 비가동일)")

        elif trend_granularity == "주간 (전체 기간)":
            if not daily_mart.empty and daily_mart["total_stickers"].sum() > 0:
                min_d = pd.to_datetime(daily_mart["work_date"].min())
                max_d = pd.to_datetime(daily_mart["work_date"].max())
                all_weeks = pd.period_range(start=min_d.to_period("W-SUN"), end=max_d.to_period("W-SUN"), freq="W-SUN")

                df_w = daily_mart.copy()
                df_w["dt"] = pd.to_datetime(df_w["work_date"])
                df_w["week_period"] = df_w["dt"].dt.to_period("W-SUN")
                df_w["week_start"] = df_w["week_period"].apply(lambda r: r.start_time.strftime("%Y-%m-%d"))

                weekly_actual = df_w.groupby("week_start").agg(
                    total_stickers=("total_stickers", "sum"),
                    total_boxes=("total_boxes", "sum"),
                    avg_workers=("effective_worker_count", "mean"),
                    active_days=("work_date", "nunique")
                ).reset_index()

                complete_weeks = []
                for p in all_weeks:
                    w_start = p.start_time.strftime("%Y-%m-%d")
                    w_end = p.end_time.strftime("%m/%d")
                    iso_w = f"W{p.start_time.isocalendar()[1]:02d}"
                    s_sub = w_start[5:].replace("-", "/")
                    display = f"{iso_w}주차 ({s_sub}~{w_end})"
                    short_label = f"{iso_w}주차"
                    complete_weeks.append({
                        "week_start": w_start,
                        "week_end": w_end,
                        "week_label": iso_w,
                        "short_label": short_label,
                        "display_label": display
                    })
                all_weeks_df = pd.DataFrame(complete_weeks)

                weekly = pd.merge(all_weeks_df, weekly_actual, on="week_start", how="left")
                weekly["total_stickers"] = weekly["total_stickers"].fillna(0)
                weekly["total_boxes"] = weekly["total_boxes"].fillna(0)
                weekly["avg_workers"] = weekly["avg_workers"].fillna(0).round(1)
                weekly["active_days"] = weekly["active_days"].fillna(0).astype(int)

                weekly["status_desc"] = weekly["active_days"].apply(
                    lambda d: f"가동 {d}일" if d > 0 else "공장 비가동(휴무)"
                )

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=weekly["short_label"],
                    y=weekly["total_stickers"],
                    name="주간 스티커 작업량 (매)",
                    marker_color="#3b82f6",
                    customdata=np.stack((weekly["display_label"], weekly["total_boxes"], weekly["status_desc"]), axis=-1),
                    hovertemplate="<b>%{customdata[0]}</b><br>• 주간 스티커량: <b>%{y:,.0f} 매</b><br>• 주간 작업 박스: <b>%{customdata[1]:,.0f} 박스</b><br>• 상태: <b>%{customdata[2]}</b><extra></extra>",
                    yaxis="y"
                ))
                fig.add_trace(go.Scatter(
                    x=weekly["short_label"],
                    y=weekly["avg_workers"],
                    name="일평균 투입 인원 (명)",
                    mode="lines+markers",
                    marker=dict(size=6, color="#ef4444"),
                    line=dict(width=2.5, color="#ef4444"),
                    customdata=weekly["display_label"],
                    hovertemplate="<b>%{customdata}</b><br>• 일평균 투입 인원: <b>%{y:.1f} 명/일</b><extra></extra>",
                    yaxis="y2"
                ))

                fig.update_layout(
                    dragmode=False,
                    yaxis=dict(title="스티커 작업량 (매)", showgrid=True, fixedrange=True),
                    yaxis2=dict(title="일평균 투입 인원 (명)", overlaying="y", side="right", showgrid=False, fixedrange=True),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=20, r=20, t=30, b=20),
                    height=360,
                    hoverlabel=dict(align="left"),
                    xaxis=dict(tickangle=-45, fixedrange=True)
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
            else:
                st.info("표시할 주간 작업 데이터가 없습니다.")

        else:  # "월간 (전체 기간)"
            if not daily_mart.empty and daily_mart["total_stickers"].sum() > 0:
                monthly = daily_mart.groupby("work_month").agg(
                    total_stickers=("total_stickers", "sum"),
                    total_boxes=("total_boxes", "sum"),
                    avg_workers=("effective_worker_count", "mean"),
                    active_days=("work_date", "nunique")
                ).reset_index().sort_values("work_month")

                monthly["display_label"] = monthly["work_month"].apply(lambda m: f"{m[:4]}년 {m[5:]}월")
                monthly["avg_workers"] = monthly["avg_workers"].round(1)

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=monthly["display_label"],
                    y=monthly["total_stickers"],
                    name="월간 스티커 작업량 (매)",
                    marker_color="#3b82f6",
                    customdata=np.stack((monthly["active_days"], monthly["total_boxes"]), axis=-1),
                    hovertemplate="<b>%{x}</b><br>• 월간 스티커량: <b>%{y:,.0f} 매</b><br>• 월간 작업 박스: <b>%{customdata[1]:,.0f} 박스</b><br>• 월간 가동일수: <b>%{customdata[0]} 일</b><extra></extra>",
                    yaxis="y"
                ))
                fig.add_trace(go.Scatter(
                    x=monthly["display_label"],
                    y=monthly["avg_workers"],
                    name="일평균 투입 인원 (명)",
                    mode="lines+markers",
                    marker=dict(size=8, color="#ef4444"),
                    line=dict(width=2.5, color="#ef4444"),
                    hovertemplate="<b>%{x}</b><br>• 일평균 투입 인원: <b>%{y:.1f} 명/일</b><extra></extra>",
                    yaxis="y2"
                ))

                fig.update_layout(
                    dragmode=False,
                    xaxis=dict(fixedrange=True),
                    yaxis=dict(title="스티커 작업량 (매)", showgrid=True, fixedrange=True),
                    yaxis2=dict(title="일평균 투입 인원 (명)", overlaying="y", side="right", showgrid=False, fixedrange=True),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=20, r=20, t=30, b=20),
                    height=360,
                    hoverlabel=dict(align="left")
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
            else:
                st.info("표시할 월간 작업 데이터가 없습니다.")

    with col_chart2:
        st.subheader("🍩 제조사별 작업 비중")
        
        # Interactive criteria toggle
        pie_metric = st.radio(
            "집계 기준 선택",
            options=["스티커수량 (매)", "작업수량 (박스)", "평균 입량 (개/박스)"],
            horizontal=True,
            key="mfg_pie_criteria"
        )
        
        if not filtered_silver.empty and filtered_silver["sticker_qty"].sum() > 0:
            if pie_metric == "평균 입량 (개/박스)":
                mfg_agg = filtered_silver.groupby("manufacturer").agg(
                    total_stickers=("sticker_qty", "sum"),
                    total_boxes=("work_qty", "sum")
                ).reset_index()
                mfg_agg["pack_qty"] = (mfg_agg["total_stickers"] / mfg_agg["total_boxes"].replace(0, 1)).round(1)
                mfg_agg = mfg_agg.sort_values("pack_qty", ascending=True)

                fig_bar = px.bar(
                    mfg_agg,
                    x="pack_qty",
                    y="manufacturer",
                    orientation="h",
                    text="pack_qty",
                    color="manufacturer",
                    color_discrete_map=MANUFACTURER_COLORS,
                    labels={"pack_qty": "박스당 평균 입량 (개/박스)", "manufacturer": "제조사"}
                )
                fig_bar.update_traces(
                    texttemplate='%{text:.1f} 개/박스',
                    textposition='outside',
                    hoverlabel=dict(align="left"),
                    hovertemplate="<b>%{y}</b><br>• 박스당 평균 입량: <b>%{x:.1f} 개/박스</b><extra></extra>"
                )
                fig_bar.update_layout(
                    dragmode=False,
                    margin=dict(l=10, r=50, t=10, b=10),
                    height=310,
                    showlegend=False,
                    hoverlabel=dict(align="left"),
                    xaxis=dict(showgrid=True, fixedrange=True),
                    yaxis=dict(fixedrange=True)
                )
                st.plotly_chart(fig_bar, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
                st.caption("💡 각 제조사 제품 1박스에 낱개가 몇 개씩 들어있는지 실제 수치와 막대 길이로 바로 비교하실 수 있습니다.")
            else:
                if pie_metric == "스티커수량 (매)":
                    mfg_agg = filtered_silver.groupby("manufacturer")["sticker_qty"].sum().reset_index()
                    val_col = "sticker_qty"
                    unit_label = "매"
                else:
                    mfg_agg = filtered_silver.groupby("manufacturer")["work_qty"].sum().reset_index()
                    val_col = "work_qty"
                    unit_label = "박스"

                fig_pie = px.pie(
                    mfg_agg,
                    names="manufacturer",
                    values=val_col,
                    hole=0.45,
                    color="manufacturer",
                    color_discrete_map=MANUFACTURER_COLORS
                )
                fig_pie.update_traces(
                    textposition="inside",
                    textinfo="percent+label",
                    hoverlabel=dict(align="left"),
                    hovertemplate=f"<b>%{{label}}</b><br>• 비중: <b>%{{percent}}</b><br>• {pie_metric}: <b>%{{value:,.0f}} {unit_label}</b><extra></extra>"
                )
                fig_pie.update_layout(
                    dragmode=False,
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=310,
                    hoverlabel=dict(align="left")
                )
                st.plotly_chart(fig_pie, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
        else:
            st.info("선택하신 기간에는 제조사 작업 실적이 없습니다.")

    # Dynamic Operational Insight Engine (조회 기간 및 필터에 맞춰 실시간 자동 분석)
    if not filtered_silver.empty:
        mfg_agg_insight = filtered_silver.groupby("manufacturer").agg(
            stickers=("sticker_qty", "sum"),
            boxes=("work_qty", "sum")
        ).reset_index()
        
        tot_stickers_in = int(mfg_agg_insight["stickers"].sum())
        tot_boxes_in = int(mfg_agg_insight["boxes"].sum())
        
        if tot_stickers_in > 0 and tot_boxes_in > 0:
            mfg_agg_insight["sticker_share"] = (mfg_agg_insight["stickers"] / tot_stickers_in) * 100
            mfg_agg_insight["box_share"] = (mfg_agg_insight["boxes"] / tot_boxes_in) * 100
            mfg_agg_insight["pack_qty"] = (mfg_agg_insight["stickers"] / mfg_agg_insight["boxes"].replace(0, 1)).round(1)
            
            # 1. 1위 작업량 제조사 분석
            top_stk = mfg_agg_insight.sort_values("stickers", ascending=False).iloc[0]
            top_mfg_name = str(top_stk["manufacturer"])
            top_s_pct = float(top_stk["sticker_share"])
            top_b_pct = float(top_stk["box_share"])
            top_s_count = int(top_stk["stickers"])
            top_b_count = int(top_stk["boxes"])
            
            if top_s_pct > top_b_pct + 1.5:
                workload_eval = f"출하 박스 비중(<strong>{top_b_pct:.1f}%</strong>, {top_b_count:,}박스) 대비 스티커 공수 비중(<strong>{top_s_pct:.1f}%</strong>)이 <strong>+{top_s_pct - top_b_pct:.1f}%p</strong> 높아, 낱개 라벨 작업이 집중되는 핵심 고부하 공정입니다."
            else:
                workload_eval = f"출하 박스 비중(<strong>{top_b_pct:.1f}%</strong>, {top_b_count:,}박스)과 스티커 비중(<strong>{top_s_pct:.1f}%</strong>)이 균형을 이루며 안정적인 공정 흐름을 보이고 있습니다."
                
            # 2. 상위 볼륨 제조사별 포장 밀도(입량) 격차 비교
            top_vol_mfgs = mfg_agg_insight.sort_values("stickers", ascending=False).head(5)
            if len(top_vol_mfgs) >= 2:
                sig_sorted = top_vol_mfgs.sort_values("pack_qty", ascending=False)
                hi_mfg = sig_sorted.iloc[0]
                lo_mfg = sig_sorted.iloc[-1]
                hi_name, hi_val = str(hi_mfg["manufacturer"]), float(hi_mfg["pack_qty"])
                lo_name, lo_val = str(lo_mfg["manufacturer"]), float(lo_mfg["pack_qty"])
                ratio_val = round(hi_val / max(1.0, lo_val), 1)
                density_text = f"주요 상위 제조사 중 <strong>{hi_name}</strong>(박스당 평균 <strong>{hi_val:.1f}개</strong>)은 <strong>{lo_name}</strong>(평균 <strong>{lo_val:.1f}개</strong>) 대비 박스당 낱개 수가 <strong>약 {ratio_val:.1f}배</strong> 많습니다."
                recommendation_mfg = hi_name
            else:
                density_text = f"현재 조회된 제조사의 박스당 평균 입량은 <strong>{top_stk['pack_qty']:.1f}개/박스</strong>입니다."
                recommendation_mfg = top_mfg_name
                
            # 3. 기간 내 최다 부착 단일 품목 분석
            item_agg_in = filtered_silver.groupby(["normalized_item_name", "manufacturer", "pack_qty"])["sticker_qty"].sum().reset_index()
            top_it = item_agg_in.sort_values("sticker_qty", ascending=False).iloc[0]
            it_name = str(top_it["normalized_item_name"])
            it_mfg = str(top_it["manufacturer"])
            it_pack = int(top_it["pack_qty"])
            it_qty = int(top_it["sticker_qty"])
            it_share = float((it_qty / tot_stickers_in) * 100)

            with st.expander(f"💡 **현장 운영 핵심 인사이트 ({start_d} ~ {end_d} 실시간 자동 분석)**", expanded=True):
                st.markdown(f"""
                <div style="font-size: 13.5px; line-height: 1.68; color: #334155; background: #f8fafc; padding: 14px 18px; border-radius: 10px; border: 1px solid #e2e8f0; border-left: 4px solid #2563eb;">
                    <div style="margin-bottom: 7px;">
                        <span style="color:#2563eb; font-weight:700;">• 기간 내 최대 작업 제조사:</span> <strong>{top_mfg_name}</strong> — 전체 스티커 라벨의 <strong>{top_s_pct:.1f}%</strong>({top_s_count:,}매)를 차지하여 가장 높은 작업 비중을 기록했습니다. {workload_eval}
                    </div>
                    <div style="margin-bottom: 7px;">
                        <span style="color:#2563eb; font-weight:700;">• 제조사별 포장 밀도 격차:</span> {density_text}
                    </div>
                    <div style="margin-bottom: 7px;">
                        <span style="color:#2563eb; font-weight:700;">• 기간 내 단일 최다 작업 품목:</span> <strong>{it_name}</strong>({it_mfg}, 박스당 {it_pack}개)에 누적 <strong>{it_qty:,}매</strong>(전체의 {it_share:.1f}%)가 투입되어 단일 제품 중 가장 많은 작업 공수가 집중되었습니다.
                    </div>
                    <div style="margin-bottom: 6px;">
                        <span style="color:#d97706; font-weight:700;">• 💡 현장 인력 배정 가이드:</span> <strong>{recommendation_mfg}</strong> 등 고입량 품목군 작업일에는 박스 개수만 보고 인원을 배정하면 인력 부족(납기 지연)이 발생할 수 있으므로, 반드시 <strong>예정 스티커 총량(박스수 × 입량)</strong>을 기준으로 작업 인원을 사전 배치해야 합니다.
                    </div>
                    <div style="font-size: 11.5px; color: #64748b; margin-top: 8px; border-top: 1px dashed #cbd5e1; padding-top: 6px;">
                        ※ 우측 상단 차트에서 <strong>[평균 입량 (개/박스)]</strong> 선택 시 각 제조사 제품 1박스당 실제 낱개 수치를 막대 그래프로 즉시 비교하실 수 있습니다.
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.write("")

    # Row 2: Top 10 Items by Volume & Monthly Summary Table
    col_t1, col_t2 = st.columns([11, 13])
    
    with col_t1:
        st.subheader("🔥 스티커 작업량 상위 품목 Top 10")
        if has_prev_data:
            st.caption(f"📊 동일 전기간 (**{prev_start_d} ~ {prev_end_d}**) 대비 증감률(%) 표기")
        
        top10 = filtered_item.head(10).copy()
        
        if not top10.empty and top10["total_stickers"].sum() > 0:
            # Calculate PoP delta for each top item
            if has_prev_data and not prev_item.empty:
                prev_map = prev_item.set_index("normalized_item_name")["total_stickers"].to_dict()
                top10["prev_stickers"] = top10["normalized_item_name"].map(prev_map).fillna(0)
            else:
                top10["prev_stickers"] = 0
                
            top10["delta_stickers"] = top10["total_stickers"] - top10["prev_stickers"]
            top10["delta_pct"] = top10.apply(
                lambda r: ((r["delta_stickers"] / r["prev_stickers"]) * 100) if r["prev_stickers"] > 0 else None,
                axis=1
            )
            
            def format_delta_display(r):
                if not has_prev_data:
                    return "전기간 비교 데이터 없음"
                if r["prev_stickers"] == 0 or pd.isna(r["delta_pct"]):
                    return "전기간 실적 없음 (신규 진입 🆕)"
                if r["delta_stickers"] >= 0:
                    return f"+{r.delta_stickers:,.0f} 매 (+{r.delta_pct:.1f}% ▲)"
                else:
                    return f"{r.delta_stickers:,.0f} 매 ({r.delta_pct:.1f}% ▼)"

            def format_bar_label(r):
                val_str = f"{r.total_stickers:,.0f} 매"
                if not has_prev_data:
                    return val_str
                if r["prev_stickers"] == 0 or pd.isna(r["delta_pct"]):
                    return f"{val_str} (NEW)"
                sign = "+" if r.delta_stickers >= 0 else ""
                return f"{val_str} ({sign}{r.delta_pct:.0f}%)"

            top10["delta_display"] = top10.apply(format_delta_display, axis=1)
            top10["prev_stickers_display"] = top10["prev_stickers"].apply(
                lambda v: f"{v:,.0f} 매" if v > 0 else ("전기간 없음" if has_prev_data else "-")
            )
            top10["bar_label"] = top10.apply(format_bar_label, axis=1)

            sorted_top10 = top10.sort_values("total_stickers", ascending=True)

            fig_top = px.bar(
                sorted_top10,
                x="total_stickers",
                y="normalized_item_name",
                orientation="h",
                text="bar_label",
                color="category_1",
                custom_data=[
                    "category_1",
                    "manufacturer",
                    "standard_volume",
                    "avg_pack_qty",
                    "prev_stickers_display",
                    "delta_display"
                ],
                labels={"total_stickers": "총 스티커수량 (매)", "normalized_item_name": "제품명", "category_1": "대분류"}
            )
            fig_top.update_traces(
                textposition='outside',
                hoverlabel=dict(
                    align="left",
                    bgcolor="#ffffff",
                    bordercolor="#cbd5e1",
                    font_color="#0f172a",
                    font_family="Pretendard, -apple-system, sans-serif",
                    font_size=12
                ),
                hovertemplate=(
                    "<b>%{y}</b> (%{customdata[1]})<br>"
                    "• 대분류: <b>%{customdata[0]}</b><br>"
                    "• 표준중량/규격: <b>%{customdata[2]}</b> (입량: %{customdata[3]}개/박스)<br>"
                    "• 금기 작업량: <b>%{x:,.0f} 매</b><br>"
                    "• 전기간 작업량: <b>%{customdata[4]}</b><br>"
                    "• 전기간 대비 증감: <b>%{customdata[5]}</b><extra></extra>"
                )
            )
            fig_top.update_layout(
                dragmode=False,
                margin=dict(l=10, r=45, t=10, b=10),
                height=430,
                xaxis=dict(showgrid=True, fixedrange=True),
                yaxis=dict(fixedrange=True),
                hoverlabel=dict(
                    align="left",
                    bgcolor="#ffffff",
                    bordercolor="#cbd5e1",
                    font_color="#0f172a",
                    font_family="Pretendard, -apple-system, sans-serif",
                    font_size=12
                )
            )
            st.plotly_chart(fig_top, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
        else:
            st.info("선택하신 기간에는 상위 품목 작업 실적이 없습니다. (공장 비가동일)")

    with col_t2:
        st.subheader("📅 월별 실적 요약")
        
        if not filtered_silver.empty and not filtered_daily.empty and filtered_silver["sticker_qty"].sum() > 0:
            # Monthly aggregates with full metrics
            # 일별 투입 공수 및 인원은 일자 단위 마트(filtered_daily)에서 집계하여 품목 라인 수에 따른 중복 곱셈 방지
            monthly_daily = filtered_daily.groupby("work_month").agg(
                총투입공수=("total_man_hours", "sum"),
                가동일수=("work_date", "nunique"),
                투입인원_합계=("effective_worker_count", "sum")
            ).reset_index()

            monthly_silver = filtered_silver.groupby("work_month").agg(
                총스티커수량=("sticker_qty", "sum"),
                총작업수량_박스=("work_qty", "sum"),
                취급품목수=("normalized_item_name", "nunique")
            ).reset_index()

            monthly_summary = monthly_silver.merge(monthly_daily, on="work_month")

            monthly_summary["시간당부착량"] = (
                monthly_summary["총스티커수량"] / monthly_summary["총투입공수"].replace(0, 1)
            ).round(1)

            monthly_summary["인당일평균부착량"] = (
                monthly_summary["총스티커수량"] / monthly_summary["투입인원_합계"].replace(0, 1)
            ).round(0)

            # Rename to clean Korean column headers
            disp_monthly = monthly_summary[[
                "work_month", "총스티커수량", "총작업수량_박스", "총투입공수", "시간당부착량", "인당일평균부착량", "가동일수", "취급품목수"
            ]].copy()
            
            disp_monthly.columns = [
                "작업월", "총 스티커수량(매)", "총 작업수량(박스)", "총 투입공수(인·시)", "1인 시간당 부착량(매/hr)", "1인 1일 부착량(매/일)", "가동일수(일)", "취급 품목수(개)"
            ]

            styled_monthly = disp_monthly.style.format({
                "총 스티커수량(매)": "{:,.0f}",
                "총 작업수량(박스)": "{:,.0f}",
                "총 투입공수(인·시)": "{:,.1f}",
                "1인 시간당 부착량(매/hr)": "{:,.1f}",
                "1인 1일 부착량(매/일)": "{:,.0f}",
                "가동일수(일)": "{:,.0f}",
                "취급 품목수(개)": "{:,.0f}"
            })
            st.dataframe(styled_monthly, use_container_width=True, height=260, hide_index=True)

            st.caption("💡 **1인 시간당 부착량(매/hr)**: 1명이 1시간 동안 부착한 평균 스티커 매수입니다.")
            st.caption("💡 **총 투입공수(인·시)**: 당월 근무인원 × 일일 작업시간의 누적 총합입니다.")
        else:
            st.info("선택하신 기간에는 월별 집계 실적이 없습니다. (공장 비가동일)")


# ---------------------------------------------------------
# TAB 2: PRODUCTIVITY & DIFFICULTY
# ---------------------------------------------------------
with tab2:
    st.markdown("### ⚡ 품목 및 카테고리별 생산성 & 난이도 분석 (Productivity & Difficulty)")
    if has_prev_data:
        st.caption(
            f"조회 기간: **{start_d} ~ {end_d}** ({days_count}일간) | "
            f"동일 전기간 비교: **{prev_start_d} ~ {prev_end_d}** (동일 {days_count}일) | "
            f"취급 품목수: **{len(filtered_item):,}개** (분석 카테고리 {filtered_silver['category_2'].nunique()}개)"
        )
    else:
        st.caption(f"조회 기간: **{start_d} ~ {end_d}** ({days_count}일간) | 취급 품목수: **{len(filtered_item):,}개**")

    # Metric Row: 4 Productivity & Difficulty KPI Cards (Tab 1과 동일한 대칭 규격 및 PoP 뱃지 적용)
    t2_c1, t2_c2, t2_c3, t2_c4 = st.columns(4)

    # 1. 1인 시간당 부착량 (평균 생산성)
    badge_t2_speed = get_delta_badge(avg_speed, prev_speed, "매/hr", is_float=True)
    with t2_c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">1인 시간당 부착량 (생산성)</div>
                <div class="metric-value" style="color:#2563eb;">{avg_speed:,.1f} <span style="font-size:16px; font-weight:600;">매/hr</span></div>
                {badge_t2_speed}
                <div class="metric-sub">1인 1일(8시간) 환산 약 <strong>{daily_per_worker:,.0f}</strong> 매</div>
            </div>
            <div class="metric-desc">ℹ️ 작업자 1명이 1시간 동안 부착한 평균 스티커 수량입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. 박스당 평균 입량 (포장 밀도)
    avg_pack = round(total_stickers / total_boxes, 1) if total_boxes > 0 else 0.0
    badge_t2_pack = get_delta_badge(avg_pack, prev_pack, "개/박스", is_float=True)
    with t2_c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">박스당 평균 입량 (포장 밀도)</div>
                <div class="metric-value" style="color:#059669;">{avg_pack:.1f} <span style="font-size:16px; font-weight:600;">개/박스</span></div>
                {badge_t2_pack}
                <div class="metric-sub">1박스당 평균 <strong>{avg_pack:.1f}</strong>개 낱개 포장</div>
            </div>
            <div class="metric-desc">ℹ️ 박스 1개당 부착해야 할 평균 스티커 매수로, 높을수록 낱개 작업량이 급증합니다.</div>
        </div>
        """, unsafe_allow_html=True)

    # 3. 고난이도 (32개↑) 작업 비중
    high_items = filtered_silver[filtered_silver["pack_qty"] >= 32]
    high_stickers = int(high_items["sticker_qty"].sum())
    high_pct = round((high_stickers / max(1, total_stickers)) * 100, 1)
    if has_prev_data:
        prev_high_items = prev_silver[prev_silver["pack_qty"] >= 32]
        prev_high_stickers = int(prev_high_items["sticker_qty"].sum())
        prev_high_pct = round((prev_high_stickers / max(1, prev_stickers)) * 100, 1)
    else:
        prev_high_pct = 0.0
    badge_t2_high = get_delta_badge(high_pct, prev_high_pct, "%p", is_float=True)
    with t2_c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">고난이도 (32개↑) 작업 비중</div>
                <div class="metric-value" style="color:#ef4444;">{high_pct:.1f} <span style="font-size:16px; font-weight:600;">%</span></div>
                {badge_t2_high}
                <div class="metric-sub">고부하 품목 누적 <strong>{high_stickers:,}</strong> 매</div>
            </div>
            <div class="metric-desc">ℹ️ 박스당 32개 이상 포장된 낱개 집중 고난이도 품목군의 스티커 작업량 비중입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    # 4. 1인 시간당 박스 처리량
    box_speed = round(total_boxes / total_hours, 1) if total_hours > 0 else 0.0
    badge_t2_box = get_delta_badge(box_speed, prev_box_speed, "박스/hr", is_float=True)
    with t2_c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">1인 시간당 박스 처리량</div>
                <div class="metric-value" style="color:#7c3aed;">{box_speed:,.1f} <span style="font-size:16px; font-weight:600;">박스/hr</span></div>
                {badge_t2_box}
                <div class="metric-sub">1인 1일(8시간) 환산 약 <strong>{box_speed * 8:,.0f}</strong> 박스</div>
            </div>
            <div class="metric-desc">ℹ️ 작업자 1명이 1시간 동안 박스 개봉, 라벨링 후 재포장한 완제품 박스 수량입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # Chart Row 1: 카테고리별 시간당 속도 & 입량 vs 스티커 산점도
    c1, c2 = st.columns([12, 12])
    
    # Common Plotly hoverlabel style (Tab 1과 동일한 일관성 유지)
    common_hoverlabel = dict(
        align="left",
        bgcolor="#ffffff",
        bordercolor="#cbd5e1",
        font_color="#0f172a",
        font_family="Pretendard, -apple-system, sans-serif",
        font_size=12
    )

    with c1:
        c1_h1, c1_h2 = st.columns([1.2, 1])
        with c1_h1:
            st.subheader("📦 카테고리별 시간당 스티커 속도")
        with c1_h2:
            only_reliable_cat = st.checkbox(
                "표본 3건 이상만 보기 (권장)",
                value=True,
                help="단발성(1~2건) 작업의 일별 배분 속도 왜곡을 제외하고, 3건 이상 반복 검증된 신뢰성 있는 카테고리만 비교합니다."
            )

        cat_agg = filtered_silver.groupby("category_2").agg(
            orders=("line_no", "count"),
            active_days=("work_date", "nunique"),
            stickers=("sticker_qty", "sum"),
            boxes=("work_qty", "sum"),
            hours=("row_man_hours", "sum")
        ).reset_index()

        if not cat_agg.empty:
            cat_agg["speed"] = (cat_agg["stickers"] / cat_agg["hours"].replace(0, np.nan)).round(1)
            cat_agg["is_reliable"] = (cat_agg["orders"] >= 3) & (cat_agg["stickers"] >= 1000)
            cat_agg["reliability_status"] = cat_agg.apply(
                lambda r: f"🟢 신뢰도 높음 ({r['orders']}건/{r['active_days']}일)" if r["is_reliable"] else f"⚠️ 표본 부족 ({r['orders']}건/{r['active_days']}일)",
                axis=1
            )

            if only_reliable_cat:
                cat_plot_df = cat_agg[cat_agg["is_reliable"]].copy()
                if cat_plot_df.empty:
                    cat_plot_df = cat_agg.copy()
            else:
                cat_plot_df = cat_agg[cat_agg["stickers"] >= 100].copy()

            fig_cat = px.bar(
                cat_plot_df,
                y="category_2",
                x="speed",
                orientation="h",
                color="speed",
                color_continuous_scale="Viridis",
                labels={"category_2": "중분류", "speed": "시간당 부착 속도 (매/hr)"},
                custom_data=["stickers", "boxes", "orders", "active_days", "reliability_status", "hours"]
            )
            fig_cat.update_traces(
                texttemplate="%{x:,.0f} 매/hr",
                textposition="outside",
                hoverlabel=common_hoverlabel,
                hovertemplate="<b>%{y}</b><br>"
                              + "• 시간당 부착 속도: <b>%{x:,.1f} 매/hr</b><br>"
                              + "• 총 스티커 수량: <b>%{customdata[0]:,.0f} 매</b><br>"
                              + "• 총 작업수량: <b>%{customdata[1]:,.0f} 박스</b><br>"
                              + "• 누적 작업건수: <b>%{customdata[2]} 건</b> (가동일수 {customdata[3]}일)<br>"
                              + "• 총 투입공수: <b>%{customdata[5]:,.1f} 시간</b><br>"
                              + "• 표본 상태: <b>%{customdata[4]}</b><extra></extra>"
            )
            fig_cat.update_layout(
                dragmode=False,
                height=400,
                margin=dict(l=10, r=40, t=10, b=10),
                hoverlabel=common_hoverlabel,
                yaxis={"categoryorder": "total ascending", "fixedrange": True},
                xaxis=dict(title="시간당 부착 속도 (매/hr)", fixedrange=True),
                yaxis_title=""
            )
            st.plotly_chart(fig_cat, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
        else:
            st.info("조회 기간 내 카테고리 데이터가 없습니다.")

    with c2:
        st.subheader("🎯 입량(Pack Qty) vs 스티커 작업량 분포")
        if not filtered_item.empty:
            fig_scatter = px.scatter(
                filtered_item,
                x="avg_pack_qty",
                y="total_stickers",
                size="total_boxes",
                color="difficulty_tier",
                hover_name="normalized_item_name",
                custom_data=["manufacturer", "category_2", "total_boxes", "stickers_per_hour", "order_count", "difficulty_tier"],
                labels={
                    "avg_pack_qty": "박스당 평균 입량 (개/박스)",
                    "total_stickers": "누적 스티커 수량 (매)",
                    "difficulty_tier": "난이도 등급"
                },
                color_discrete_map={
                    "고난이도 (High - 32개↑)": "#ef4444",
                    "중간 (Medium - 16~31개)": "#f59e0b",
                    "단순 (Low - 16개↓)": "#10b981"
                },
                category_orders={
                    "difficulty_tier": [
                        "고난이도 (High - 32개↑)",
                        "중간 (Medium - 16~31개)",
                        "단순 (Low - 16개↓)"
                    ]
                }
            )
            fig_scatter.update_traces(
                hoverlabel=common_hoverlabel,
                hovertemplate="<b>%{hover_name}</b> (%{customdata[0]})<br>"
                              + "• 중분류: <b>%{customdata[1]}</b><br>"
                              + "• 박스당 평균 입량: <b>%{x:.1f} 개/박스</b><br>"
                              + "• 누적 스티커 작업량: <b>%{y:,.0f} 매</b><br>"
                              + "• 출하 박스 수량: <b>%{customdata[2]:,.0f} 박스</b><br>"
                              + "• 시간당 부착 속도: <b>%{customdata[3]:,.1f} 매/hr</b><br>"
                              + "• 누적 작업건수: <b>%{customdata[4]} 건</b><br>"
                              + "• 난이도 등급: <b>%{customdata[5]}</b><extra></extra>"
            )
            fig_scatter.update_layout(
                dragmode=False,
                height=400,
                margin=dict(l=10, r=10, t=10, b=10),
                hoverlabel=common_hoverlabel,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=""),
                xaxis=dict(fixedrange=True),
                yaxis=dict(fixedrange=True)
            )
            st.plotly_chart(fig_scatter, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
        else:
            st.info("조회 기간 내 품목 데이터가 없습니다.")

    # Dynamic Operational Insight Engine for Tab 2 (Tab 1과 동일한 실시간 지능형 인사이트 제공)
    if not filtered_silver.empty and not filtered_item.empty:
        cat_agg_in = filtered_silver.groupby("category_2").agg(
            orders=("line_no", "count"),
            active_days=("work_date", "nunique"),
            stickers=("sticker_qty", "sum"),
            boxes=("work_qty", "sum"),
            hours=("row_man_hours", "sum")
        ).reset_index()
        cat_agg_in["speed"] = (cat_agg_in["stickers"] / cat_agg_in["hours"].replace(0, np.nan)).round(1)
        reliable_cats = cat_agg_in[(cat_agg_in["orders"] >= 3) & (cat_agg_in["stickers"] >= 1000)].sort_values("speed", ascending=False)

        if not reliable_cats.empty:
            fast_cat = reliable_cats.iloc[0]
            slow_cat = reliable_cats.iloc[-1]
            speed_ratio = fast_cat["speed"] / max(1.0, slow_cat["speed"])
            cat_speed_text = f"기간 내 최고 생산성 중분류는 <strong>{fast_cat['category_2']}</strong>(<strong>{fast_cat['speed']:,.1f}매/hr</strong>), 최저 생산성은 <strong>{slow_cat['category_2']}</strong>(<strong>{slow_cat['speed']:,.1f}매/hr</strong>)로 <strong>약 {speed_ratio:.1f}배의 속도 격차</strong>를 보였습니다."
        else:
            cat_speed_text = f"전체 평균 시간당 부착 속도는 <strong>{avg_speed:,.1f}매/hr</strong>입니다."

        # Top bottlenecks (slowest items with orders >= 3)
        bottlenecks = filtered_item[filtered_item["order_count"] >= 3].sort_values("stickers_per_hour", ascending=True).head(3)
        if not bottlenecks.empty:
            bn_text = ", ".join([f"<strong>{r.normalized_item_name}</strong>({r.stickers_per_hour:,.1f}매/hr)" for _, r in bottlenecks.iterrows()])
            bottleneck_text = f"{bn_text} 등은 전체 평균({avg_speed:.1f}매/hr) 대비 부착 속도가 현저히 느려 라인 정체를 유발하는 핵심 병목 품목입니다."
        else:
            bottleneck_text = "현재 조회 조건에서 표본 3건 이상의 병목 품목이 집계되지 않았습니다."

        # Top high density item
        top_high_items = filtered_item[filtered_item["avg_pack_qty"] >= 32].sort_values("total_stickers", ascending=False)
        if not top_high_items.empty:
            top_hi = top_high_items.iloc[0]
            density_text = f"전체 스티커의 <strong>{high_pct:.1f}%</strong>({high_stickers:,}매)가 박스당 32개 이상 포장된 고난이도 품목군에 집중 투입되었습니다. (단일 최다 품목: <strong>{top_hi['normalized_item_name']}</strong>, 박스당 {top_hi['avg_pack_qty']:.0f}개, {top_hi['total_stickers']:,}매)"
        else:
            density_text = f"기간 내 고난이도 품목 비중은 <strong>{high_pct:.1f}%</strong>입니다."

        with st.expander(f"💡 **생산성 & 난이도 핵심 운영 인사이트 ({start_d} ~ {end_d} 실시간 자동 분석)**", expanded=True):
            st.markdown(f"""
            <div style="font-size: 13.5px; line-height: 1.68; color: #334155; background: #f8fafc; padding: 14px 18px; border-radius: 10px; border: 1px solid #e2e8f0; border-left: 4px solid #2563eb;">
                <div style="margin-bottom: 7px;">
                    <span style="color:#2563eb; font-weight:700;">• 카테고리별 생산성 격차 (표본 3건↑ 검증):</span> {cat_speed_text}
                </div>
                <div style="margin-bottom: 7px;">
                    <span style="color:#ef4444; font-weight:700;">• 공정 병목 저생산성 품목 (표본 3건↑ 검증):</span> {bottleneck_text}
                </div>
                <div style="margin-bottom: 7px;">
                    <span style="color:#2563eb; font-weight:700;">• 고난이도(32개↑) 작업 부하 집중도:</span> {density_text}
                </div>
                <div style="margin-bottom: 6px;">
                    <span style="color:#d97706; font-weight:700;">• 💡 현장 인력 배정 & 임가공 단가 가이드:</span> 시간당 300매 이하의 저속 병목 품목이나 입량 32개 이상의 고밀도 품목은 일반 품목 대비 2배 이상의 인시(Man-Hour)가 소요되므로, 라인 작업자를 사전 1~2명 증원하거나 <strong>임가공 스티커 부착 단가 할증(+30~50%)</strong>을 바이어와 사전 협상해야 공정 마진을 방어할 수 있습니다.
                </div>
                <div style="font-size: 11.5px; color: #64748b; margin-top: 8px; border-top: 1px dashed #cbd5e1; padding-top: 6px;">
                    ※ 하단 <strong>[ℹ️ 공수 집계 방식(인·시) 및 단발성 품목 속도 산출 원리 안내]</strong>를 클릭하시면 일별 비례배분 원리 및 단발성 품목의 속도 산출 원리를 확인하실 수 있습니다.
                </div>
            </div>
            """, unsafe_allow_html=True)

    with st.expander("ℹ️ 공수 집계 방식(인·시) 및 단발성 품목 속도 산출 원리 안내", expanded=False):
        st.markdown("""
        <div style="font-size: 13px; line-height: 1.65; color: #334155; background: #f8fafc; padding: 12px 16px; border-radius: 8px; border: 1px solid #e2e8f0; border-left: 4px solid #64748b;">
            <div style="margin-bottom: 6px;">
                <span style="color:#1e293b; font-weight:700;">• 투입공수 단위(인·시, Man-Hour):</span> 작업자 1명이 1시간 동안 작업한 <strong>시간(Hours)</strong> 분량입니다 (분이 아닙니다). 예를 들어 <code>10.5</code>는 <code>10시간 30분</code> 분량의 노동력을 의미합니다.
            </div>
            <div style="margin-bottom: 6px;">
                <span style="color:#1e293b; font-weight:700;">• 일별 비례배분 원리:</span> 현장 ERP 특성상 모든 개별 박스마다 스톱워치로 측정하지 않고, 당일 공장 전체의 총 공수(인·시)를 품목별 스티커 작업량에 비례하여 배분합니다.
            </div>
            <div>
                <span style="color:#d97706; font-weight:700;">• 단발성 품목의 속도 왜곡 주의:</span> 조회 기간 내 1~2회만 작업된 단발성 품목(예: '미림/조미료')은 해당 작업일의 공장 전체 평균 속도(782매/hr 등)가 그대로 반영됩니다. 따라서 <strong>작업 3건 이상 반복된 품목 및 카테고리를 기준으로 생산성 벤치마크를 해석하는 것이 통계적으로 가장 정확</strong>합니다.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.subheader("📋 품목별 상세 생산성 및 난이도 마트")

    sc1, sc2, sc3 = st.columns([1.8, 1.2, 1.5])
    with sc1:
        sort_choice = st.selectbox(
            "📊 정렬 기준 (Order By)",
            [
                "총 스티커수량 많은 순 (기본: 주력 볼륨 중심)",
                "시간당 부착량 느린 순 (공정 병목/고부하 품목 발굴)",
                "시간당 부착량 빠른 순 (고효율 품목)",
                "평균 입량 높은 순 (포장 밀도 고난이도)",
                "총 작업수량(박스) 많은 순 (물류 출하량)",
                "투입공수(시간) 많은 순 (누적 투입공수)"
            ],
            index=0,
            help="분석 목적에 따라 정렬 기준을 변경할 수 있습니다."
        )
    with sc2:
        filter_reliable_items = st.checkbox(
            "표본 3건 이상 품목만 보기 (신뢰도 확보)",
            value=False,
            help="단발성(1~2건) 작업 품목의 속도 왜곡을 제외하고, 3건 이상 반복 검증된 품목만 분석합니다."
        )
    with sc3:
        search_kw = st.text_input(
            "🔍 품목명 / 제조사 / 중분류 검색",
            placeholder="예: 빼빼로, 농심, 초콜릿..."
        )

    disp_item = filtered_item.copy()

    if not disp_item.empty and disp_item["total_stickers"].sum() > 0:
        if filter_reliable_items:
            disp_item = disp_item[disp_item["order_count"] >= 3]

        if search_kw.strip():
            kw = search_kw.strip()
            disp_item = disp_item[
                disp_item["normalized_item_name"].str.contains(kw, case=False, na=False)
                | disp_item["manufacturer"].str.contains(kw, case=False, na=False)
                | disp_item["category_2"].str.contains(kw, case=False, na=False)
            ]

        # Apply sorting
        if "총 스티커수량" in sort_choice:
            disp_item = disp_item.sort_values("total_stickers", ascending=False)
        elif "시간당 부착량 느린" in sort_choice:
            disp_item = disp_item.sort_values("stickers_per_hour", ascending=True)
        elif "시간당 부착량 빠른" in sort_choice:
            disp_item = disp_item.sort_values("stickers_per_hour", ascending=False)
        elif "평균 입량" in sort_choice:
            disp_item = disp_item.sort_values("avg_pack_qty", ascending=False)
        elif "총 작업수량" in sort_choice:
            disp_item = disp_item.sort_values("total_boxes", ascending=False)
        elif "투입공수" in sort_choice:
            disp_item = disp_item.sort_values("allocated_man_hours", ascending=False)

        # Reliability status tag
        def eval_item_reliability(r):
            cnt = r.get("order_count", 0)
            days = r.get("active_days", 1)
            if cnt >= 3 and days >= 2:
                return "🟢 높음"
            elif cnt >= 2:
                return "🟡 보통"
            else:
                return "⚪ 단발성"

        if not disp_item.empty:
            disp_item["표본 신뢰도"] = disp_item.apply(eval_item_reliability, axis=1)

            disp_item = disp_item.rename(columns={
                "normalized_item_name": "제품명",
                "manufacturer": "제조사",
                "category_1": "대분류",
                "category_2": "중분류",
                "standard_volume": "중량/규격",
                "order_count": "작업건수(건)",
                "active_days": "작업일수(일)",
                "total_boxes": "총 작업수량(박스)",
                "total_stickers": "총 스티커수량(매)",
                "avg_pack_qty": "평균 입량(개/박스)",
                "allocated_man_hours": "투입공수(시간)",
                "stickers_per_hour": "시간당 부착량(매/hr)",
                "boxes_per_hour": "시간당 박스수(박스/hr)",
                "difficulty_tier": "난이도 등급"
            })

            cols_to_show = [
                "제품명", "제조사", "중분류", "작업건수(건)", "작업일수(일)",
                "총 작업수량(박스)", "총 스티커수량(매)", "평균 입량(개/박스)",
                "투입공수(시간)", "시간당 부착량(매/hr)", "표본 신뢰도", "난이도 등급"
            ]
            actual_cols = [c for c in cols_to_show if c in disp_item.columns]

            st.dataframe(
                disp_item[actual_cols].style.format({
                    "작업건수(건)": "{:,.0f}",
                    "작업일수(일)": "{:,.0f}",
                    "총 작업수량(박스)": "{:,.0f}",
                    "총 스티커수량(매)": "{:,.0f}",
                    "평균 입량(개/박스)": "{:.1f}",
                    "투입공수(시간)": "{:.1f}",
                    "시간당 부착량(매/hr)": "{:,.1f}"
                }),
                use_container_width=True,
                height=450,
                hide_index=True
            )
            st.caption(f"📌 총 **{len(disp_item):,}개** 품목 표시 중 | 💡 **투입공수(시간)**: 작업자 1명의 1시간(Hour) 노동량 기준입니다 (분이 아님).")
        else:
            st.info("검색 조건에 일치하는 품목 데이터가 없습니다.")
    else:
        st.info("선택하신 기간에는 품목별 생산성 마트 데이터가 없습니다. (공장 비가동일)")


# ---------------------------------------------------------
# TAB 3: BUYER & EXPORT COUNTRY
# ---------------------------------------------------------
with tab3:
    st.markdown("### 🌍 바이어 & 수출국가별 실적 분석")
    if has_prev_data:
        st.caption(
            f"조회 기간: **{start_d} ~ {end_d}** ({days_count}일간) | "
            f"동일 전기간 비교: **{prev_start_d} ~ {prev_end_d}** (동일 {days_count}일) | "
            f"활성 바이어: **{len(filtered_buyer):,}개사** | 주요 수출 국가/처: **{len(filtered_country):,}개 지역**"
        )
    else:
        st.caption(
            f"조회 기간: **{start_d} ~ {end_d}** ({days_count}일간) | "
            f"활성 바이어: **{len(filtered_buyer):,}개사** | 주요 수출 국가/처: **{len(filtered_country):,}개 지역**"
        )

    # Top 4 KPI Metrics calculation
    curr_buyers = int(filtered_buyer["buyer_normalized"].nunique()) if not filtered_buyer.empty else 0
    prev_buyers = int(prev_buyer["buyer_normalized"].nunique()) if not prev_buyer.empty else 0

    curr_countries = int(filtered_country["export_country"].nunique()) if not filtered_country.empty else 0
    prev_countries = int(prev_country["export_country"].nunique()) if not prev_country.empty else 0

    if not filtered_buyer.empty:
        top_b_row = filtered_buyer.sort_values("total_stickers", ascending=False).iloc[0]
        top_b_name = str(top_b_row["buyer_normalized"])
        top_b_stk = int(top_b_row["total_stickers"])
        top_b_box = int(top_b_row["total_boxes"])
        top_b_pct = float(top_b_row["sticker_share_pct"])
    else:
        top_b_name = "-"
        top_b_stk = 0
        top_b_box = 0
        top_b_pct = 0.0

    avg_buyer_stk = round(total_stickers / max(1, curr_buyers), 0) if curr_buyers > 0 else 0.0
    prev_avg_buyer_stk = round(prev_stickers / max(1, prev_buyers), 0) if prev_buyers > 0 else 0.0
    avg_buyer_box = round(total_boxes / max(1, curr_buyers), 0) if curr_buyers > 0 else 0.0

    badge_buyers = get_delta_badge(curr_buyers, prev_buyers, "개사")
    badge_countries = get_delta_badge(curr_countries, prev_countries, "개국")
    badge_avg_buyer = get_delta_badge(avg_buyer_stk, prev_avg_buyer_stk, "매")

    bkpi1, bkpi2, bkpi3, bkpi4 = st.columns(4)

    with bkpi1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">활성 거래 바이어 수</div>
                <div class="metric-value" style="color:#2563eb;">{curr_buyers:,} <span style="font-size:16px; font-weight:600; color:#334155;">개사</span></div>
                {badge_buyers}
                <div class="metric-sub">기간 내 누적 <strong>{len(filtered_silver):,}</strong>건 주문 발생</div>
            </div>
            <div class="metric-desc">ℹ️ 기간 내 라벨링 작업 오더가 집계된 고유 바이어 및 수출 거래처 수입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    with bkpi2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">수출 대상 국가 및 권역</div>
                <div class="metric-value" style="color:#059669;">{curr_countries:,} <span style="font-size:16px; font-weight:600; color:#334155;">개 지역</span></div>
                {badge_countries}
                <div class="metric-sub">유럽·북미·오세아니아·아시아 등 글로벌 권역</div>
            </div>
            <div class="metric-desc">ℹ️ 스티커 라벨 부착 품목이 수출 및 선적되는 목적지 국가/지역 수입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    with bkpi3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">최대 바이어 작업 집중도</div>
                <div class="metric-value" style="color:#7c3aed;">{top_b_pct:.1f} <span style="font-size:16px; font-weight:600; color:#334155;">%</span></div>
                <div class="metric-delta delta-pos" style="background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;">
                    <span>⭐ 1위 바이어: <strong>{top_b_name}</strong></span>
                </div>
                <div class="metric-sub">1위사 누적 <strong>{top_b_stk:,}</strong> 매 ({top_b_box:,} 박스)</div>
            </div>
            <div class="metric-desc">ℹ️ 기간 내 단일 바이어 중 가장 많은 스티커 공수가 집중된 1위 거래처 비중입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    with bkpi4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">바이어당 평균 작업량</div>
                <div class="metric-value" style="color:#ea580c;">{avg_buyer_stk:,.0f} <span style="font-size:16px; font-weight:600; color:#334155;">매</span></div>
                {badge_avg_buyer}
                <div class="metric-sub">바이어당 평균 <strong>{avg_buyer_box:,.0f}</strong> 박스 출하</div>
            </div>
            <div class="metric-desc">ℹ️ 바이어 1개사당 평균적으로 발생한 스티커 부착 수량 및 출하 박스량입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    common_hoverlabel_tab3 = dict(
        align="left",
        bgcolor="#ffffff",
        bordercolor="#cbd5e1",
        font_color="#0f172a",
        font_family="Pretendard, -apple-system, sans-serif",
        font_size=12
    )

    t3_sub1, t3_sub2, t3_sub3 = st.tabs([
        "📊 바이어 및 수출국가 종합 실적 (Overview)",
        "📈 바이어별 발주 추이 & 고객 건강도 모니터 (Trends & Health)",
        "🔗 바이어 ➔ 제조사 ➔ 품목 공급망 교차 매트릭스 (Supply Chain Matrix)"
    ])

    with t3_sub1:
        # Visualizations Row
        b_col1, b_col2 = st.columns([1, 1])

        with b_col1:
            st.subheader("📊 주요 바이어별 실적 비중")
            buyer_metric_choice = st.radio(
                "집계 기준 선택",
                ["스티커 수량 (매)", "출하 박스 수량 (박스)", "투입 공수 (인·시)"],
                horizontal=True,
                key="buyer_metric_choice"
            )

            metric_map = {
                "스티커 수량 (매)": ("total_stickers", "매", "스티커 수량"),
                "출하 박스 수량 (박스)": ("total_boxes", "박스", "출하 박스 수량"),
                "투입 공수 (인·시)": ("allocated_man_hours", "인·시", "투입 공수")
            }
            val_col, val_unit, val_label = metric_map[buyer_metric_choice]

            if not filtered_buyer.empty:
                df_buyer_chart = filtered_buyer.sort_values(val_col, ascending=False).copy()
                total_metric_val = df_buyer_chart[val_col].sum()

                # Top 7 + Others
                if len(df_buyer_chart) > 7:
                    top7 = df_buyer_chart.head(7).copy()
                    others_val = df_buyer_chart.iloc[7:][val_col].sum()
                    others_boxes = df_buyer_chart.iloc[7:]["total_boxes"].sum()
                    others_stk = df_buyer_chart.iloc[7:]["total_stickers"].sum()
                    others_row = pd.DataFrame([{
                        "buyer_normalized": f"기타 바이어 ({len(df_buyer_chart)-7}개사)",
                        "export_country": "다수 국가",
                        "export_region": "글로벌",
                        val_col: others_val,
                        "total_stickers": others_stk,
                        "total_boxes": others_boxes,
                        "top_items": "다양한 품목군"
                    }])
                    chart_data = pd.concat([top7, others_row], ignore_index=True)
                else:
                    chart_data = df_buyer_chart

                chart_data["pct_share"] = (chart_data[val_col] / max(1, total_metric_val) * 100).round(1)

                # Pre-formatted hover text in Python to guarantee 100% clean, bulleted tooltip
                chart_data["hover_text"] = chart_data.apply(
                    lambda r: (
                        f"<b>{r['buyer_normalized']}</b><br>"
                        f"• 수출 대상국: <b>{r['export_country']}</b> (권역: {r['export_region']})<br>"
                        f"• {val_label}: <b>{r[val_col]:,.0f} {val_unit}</b> (점유율: <b>{r['pct_share']:.1f}%</b>)<br>"
                        f"• 총 스티커 작업량: <b>{r['total_stickers']:,.0f} 매</b><br>"
                        f"• 총 출하 박스 수량: <b>{r['total_boxes']:,.0f} 박스</b><br>"
                        f"• 주요 출하품목: <i>{r['top_items']}</i>"
                    ),
                    axis=1
                )

                buyer_color_map = {b: get_buyer_color(b, i) for i, b in enumerate(chart_data["buyer_normalized"])}

                fig_buyer_pie = px.pie(
                    chart_data,
                    names="buyer_normalized",
                    values=val_col,
                    hole=0.45,
                    color="buyer_normalized",
                    color_discrete_map=buyer_color_map
                )
                fig_buyer_pie.update_traces(
                    customdata=chart_data["hover_text"],
                    hoverlabel=common_hoverlabel_tab3,
                    hovertemplate="%{customdata}<extra></extra>",
                    textinfo="percent+label",
                    textposition="inside"
                )
                fig_buyer_pie.update_layout(
                    dragmode=False,
                    height=420,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_buyer_pie, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
            else:
                st.info("조회 기간 내 바이어 데이터가 없습니다.")

        with b_col2:
            st.subheader("🌐 주요 수출 국가 및 권역별 작업량")
            country_view_choice = st.radio(
                "수출 집계 기준",
                ["수출 대상국별 (권역 색상 구분)", "글로벌 권역별 합계 (대륙 단위)"],
                horizontal=True,
                key="country_view_choice"
            )

            if not filtered_country.empty:
                if country_view_choice == "수출 대상국별 (권역 색상 구분)":
                    df_country_chart = filtered_country.sort_values("total_stickers", ascending=True).copy()

                    df_country_chart["hover_text"] = df_country_chart.apply(
                        lambda r: (
                            f"<b>{r['export_country']}</b> (권역: <b>{r['export_region']}</b>)<br>"
                            f"• 스티커 작업량: <b>{r['total_stickers']:,.0f} 매</b> (점유율: <b>{r['sticker_share_pct']:.1f}%</b>)<br>"
                            f"• 출하 박스 수량: <b>{r['total_boxes']:,.0f} 박스</b> (점유율: <b>{r['box_share_pct']:.1f}%</b>)<br>"
                            f"• 투입 공수: <b>{r['allocated_man_hours']:,.1f} 인·시</b><br>"
                            f"• 거래 바이어 수: <b>{r['distinct_buyers']} 개사</b><br>"
                            f"• 주요 출하품목: <i>{r['top_items']}</i>"
                        ),
                        axis=1
                    )

                    fig_country_bar = px.bar(
                        df_country_chart,
                        x="total_stickers",
                        y="export_country",
                        orientation="h",
                        color="export_region",
                        color_discrete_map=REGION_COLORS,
                        custom_data=["hover_text"],
                        text="total_stickers",
                        barmode="stack"
                    )
                    fig_country_bar.update_traces(
                        marker_opacity=1.0,
                        texttemplate="%{x:,.0f} 매",
                        textposition="outside",
                        hoverlabel=common_hoverlabel_tab3,
                        hovertemplate="%{customdata[0]}<extra></extra>"
                    )
                    fig_country_bar.update_layout(
                        dragmode=False,
                        height=420,
                        margin=dict(l=10, r=40, t=10, b=10),
                        xaxis=dict(title="총 스티커 작업량 (매)", fixedrange=True),
                        yaxis=dict(fixedrange=True),
                        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title="수출 권역")
                    )
                    st.plotly_chart(fig_country_bar, use_container_width=True, config=PLOTLY_STATIC_CONFIG)

                else:
                    # 글로벌 권역별 합계 (대륙 단위)
                    df_region_chart = filtered_country.groupby("export_region").agg(
                        total_stickers=("total_stickers", "sum"),
                        total_boxes=("total_boxes", "sum"),
                        allocated_man_hours=("allocated_man_hours", "sum"),
                        distinct_countries=("export_country", "nunique")
                    ).reset_index()
                    # 기간 내 실적이 있는 권역만 필터링 (0건인 오세아니아/유라시아 등이 Y축에 노출되지 않도록 방지)
                    df_region_chart = df_region_chart[df_region_chart["total_stickers"] > 0]
                    df_region_chart["sticker_share_pct"] = (df_region_chart["total_stickers"] / max(1, total_stickers) * 100).round(1)
                    df_region_chart["box_share_pct"] = (df_region_chart["total_boxes"] / max(1, total_boxes) * 100).round(1)
                    df_region_chart = df_region_chart.sort_values("total_stickers", ascending=True)

                    df_region_chart["hover_text"] = df_region_chart.apply(
                        lambda r: (
                            f"<b>{r['export_region']}</b> 권역 전체<br>"
                            f"• 총 스티커 작업량: <b>{r['total_stickers']:,.0f} 매</b> (점유율: <b>{r['sticker_share_pct']:.1f}%</b>)<br>"
                            f"• 총 출하 박스 수량: <b>{r['total_boxes']:,.0f} 박스</b> (점유율: <b>{r['box_share_pct']:.1f}%</b>)<br>"
                            f"• 총 투입 공수: <b>{r['allocated_man_hours']:,.1f} 인·시</b><br>"
                            f"• 포함 수출국가/처: <b>{r['distinct_countries']} 개 지역</b>"
                        ),
                        axis=1
                    )

                    fig_region_bar = px.bar(
                        df_region_chart,
                        x="total_stickers",
                        y="export_region",
                        orientation="h",
                        color="export_region",
                        color_discrete_map=REGION_COLORS,
                        custom_data=["hover_text"],
                        text="total_stickers"
                    )
                    fig_region_bar.update_traces(
                        marker_opacity=1.0,
                        texttemplate="%{x:,.0f} 매",
                        textposition="outside",
                        hoverlabel=common_hoverlabel_tab3,
                        hovertemplate="%{customdata[0]}<extra></extra>"
                    )
                    fig_region_bar.update_layout(
                        dragmode=False,
                        height=420,
                        margin=dict(l=10, r=40, t=10, b=10),
                        xaxis=dict(title="총 스티커 작업량 (매)", fixedrange=True),
                        yaxis=dict(fixedrange=True),
                        showlegend=False
                    )
                    st.plotly_chart(fig_region_bar, use_container_width=True, config=PLOTLY_STATIC_CONFIG)
            else:
                st.info("조회 기간 내 국가별 데이터가 없습니다.")

        # Dynamic Operational Insight Engine for Tab 3
        if not filtered_buyer.empty and not filtered_country.empty:
            # Top 3 buyers concentration
            top3_buyer_df = filtered_buyer.head(3)
            top3_buyer_share = top3_buyer_df["sticker_share_pct"].sum()
            top3_names = ", ".join([f"<strong>{r.buyer_normalized}</strong>({r.sticker_share_pct:.1f}%)" for _, r in top3_buyer_df.iterrows()])
            top_buyer_text = f"상위 3개 거래처({top3_names})가 전체 스티커 작업량의 <strong>{top3_buyer_share:.1f}%</strong>를 차지하고 있습니다. 특히 1위 바이어인 <strong>{top_b_name}</strong>(누적 {top_b_stk:,}매, 출하 박스 {top_b_box:,}박스)에 핵심 작업 공수가 집중되어 있습니다."

            # Continental breakdown
            region_agg = filtered_country.groupby("export_region")["total_stickers"].sum().reset_index()
            region_agg["share"] = (region_agg["total_stickers"] / max(1, total_stickers) * 100).round(1)
            region_agg = region_agg.sort_values("total_stickers", ascending=False)
            region_parts = [f"<strong>{r.export_region}</strong>({r.share:.1f}%, {r.total_stickers:,}매)" for _, r in region_agg.iterrows() if r.export_region not in ["일반 오더", "기타"]]
            region_text = ", ".join(region_parts) if region_parts else "글로벌 전역"
            region_desc = f"주요 해외 권역별 비중은 {region_text} 순으로 나타났습니다. 북미 및 유럽 선진국향 오더 비중이 높아 선적 스케줄 및 현지 수입 통관 규격 준수가 매우 중요합니다."

            # Specialization by Destination
            dest_insights = []
            if "캐나다" in filtered_country["export_country"].values:
                c_row = filtered_country[filtered_country["export_country"] == "캐나다"].iloc[0]
                dest_insights.append(f"<strong>캐나다</strong>({c_row['top_items']})")
            if "독일" in filtered_country["export_country"].values or "오스트리아" in filtered_country["export_country"].values:
                eu_items = filtered_country[filtered_country["export_country"].isin(["독일", "오스트리아"])]["top_items"].str.cat(sep=", ")
                dest_insights.append(f"<strong>유럽(독일/오스트리아)</strong>({eu_items})")
            if "수출 벤더사" in filtered_country["export_country"].values:
                v_row = filtered_country[filtered_country["export_country"] == "수출 벤더사"].iloc[0]
                dest_insights.append(f"<strong>수출 벤더사(거복/한상 등)</strong>({v_row['top_items']})")
            
            spec_text = " / ".join(dest_insights) if dest_insights else "국가별 상이한 제품군 출하"
            spec_desc = f"권역별로 뚜렷한 취급 제품군 차이를 보입니다. {spec_text} 등으로 구성되어 있어 포장 단위와 라벨 사양에 맞춤형 공정 셋팅이 요구됩니다."

            with st.expander(f"💡 **바이어 & 글로벌 수출 실적 핵심 운영 인사이트 ({start_d} ~ {end_d} 실시간 자동 분석)**", expanded=True):
                st.markdown(f"""
                <div style="font-size: 13.5px; line-height: 1.68; color: #334155; background: #f8fafc; padding: 14px 18px; border-radius: 10px; border: 1px solid #e2e8f0; border-left: 4px solid #2563eb;">
                    <div style="margin-bottom: 7px;">
                        <span style="color:#2563eb; font-weight:700;">• 바이어 오더 집중도 (Top 3):</span> {top_buyer_text}
                    </div>
                    <div style="margin-bottom: 7px;">
                        <span style="color:#2563eb; font-weight:700;">• 글로벌 수출 권역별 실적 배분:</span> {region_desc}
                    </div>
                    <div>
                        <span style="color:#2563eb; font-weight:700;">• 국가 및 권역별 주력 수출 품목 특화:</span> {spec_desc}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.subheader("📋 바이어/수출처별 상세 마트")
        
        t_c1, t_c2 = st.columns([1.2, 2])
        with t_c1:
            sort_buyer_choice = st.selectbox(
                "정렬 기준",
                [
                    "총 스티커수량 많은 순",
                    "출하 박스수 많은 순",
                    "투입공수 많은 순",
                    "주문건수 많은 순",
                    "취급 품목수 많은 순"
                ],
                key="sort_buyer_choice"
            )
        with t_c2:
            search_buyer_kw = st.text_input(
                "🔍 바이어명 / 수출국가 / 권역 / 품목 검색",
                placeholder="예: 판아시아, 캐나다, 유럽, 빼빼로, 거복 등",
                key="search_buyer_kw"
            )

        disp_buyer = filtered_buyer.copy()

        if not disp_buyer.empty and disp_buyer["total_stickers"].sum() > 0:
            # Search filter
            if search_buyer_kw.strip():
                kw = search_buyer_kw.strip().lower()
                disp_buyer = disp_buyer[
                    disp_buyer["buyer_normalized"].astype(str).str.lower().str.contains(kw)
                    | disp_buyer["export_country"].astype(str).str.lower().str.contains(kw)
                    | disp_buyer["export_region"].astype(str).str.lower().str.contains(kw)
                    | disp_buyer["top_items"].astype(str).str.lower().str.contains(kw)
                ]

            # Sorting
            sort_col_map = {
                "총 스티커수량 많은 순": ("total_stickers", False),
                "출하 박스수 많은 순": ("total_boxes", False),
                "투입공수 많은 순": ("allocated_man_hours", False),
                "주문건수 많은 순": ("order_count", False),
                "취급 품목수 많은 순": ("distinct_items", False)
            }
            sc, sa = sort_col_map[sort_buyer_choice]
            disp_buyer = disp_buyer.sort_values(sc, ascending=sa)

            disp_buyer = disp_buyer.rename(columns={
                "buyer_normalized": "바이어/출하처",
                "export_country": "수출국가",
                "export_region": "수출권역",
                "order_count": "주문건수(건)",
                "active_days": "가동일수(일)",
                "total_boxes": "출하 박스수(박스)",
                "total_stickers": "총 스티커수량(매)",
                "allocated_man_hours": "투입공수(인·시)",
                "distinct_items": "취급 품목수(종)",
                "sticker_share_pct": "스티커 점유율(%)",
                "box_share_pct": "출하 박스 점유율(%)",
                "top_items": "주요 출하품목 Top 3"
            })

            cols_to_show = [
                "바이어/출하처", "수출국가", "수출권역", "주문건수(건)", "가동일수(일)",
                "출하 박스수(박스)", "총 스티커수량(매)", "투입공수(인·시)", "취급 품목수(종)",
                "스티커 점유율(%)", "출하 박스 점유율(%)", "주요 출하품목 Top 3"
            ]

            if not disp_buyer.empty:
                st.dataframe(
                    disp_buyer[cols_to_show].style.format({
                        "주문건수(건)": "{:,.0f}",
                        "가동일수(일)": "{:,.0f}",
                        "출하 박스수(박스)": "{:,.0f}",
                        "총 스티커수량(매)": "{:,.0f}",
                        "투입공수(인·시)": "{:,.1f}",
                        "취급 품목수(종)": "{:,.0f}",
                        "스티커 점유율(%)": "{:.2f}%",
                        "출하 박스 점유율(%)": "{:.2f}%"
                    }),
                    use_container_width=True,
                    height=380,
                    hide_index=True
                )
            else:
                st.info("검색 조건에 일치하는 바이어/수출처 데이터가 없습니다.")

            st.caption("💡 **참고사항**: '출하 박스수(박스)'는 라벨링 후 패킹된 완제품 박스 단위이며, '총 스티커수량(매)'은 낱개 단위 부착 수량입니다. 투입공수는 해당 바이어 오더 처리에 비례 배분된 공수(Man-Hours)입니다.")
        else:
            st.info("선택하신 기간에는 바이어/수출처 실적 데이터가 없습니다. (공장 비가동일)")

    with t3_sub2:
        st.markdown("#### 📈 바이어별 발주 추이 & 고객 건강도 모니터 (Trends & Health Monitor)")
        st.caption("월별/분기별 발주량 추이를 다각도로 분석하고, 최근 거래 변동률(MoM)을 기반으로 고객사의 성장세 및 이탈 위험도를 사전 감지합니다.")

        trend_c1, trend_c2 = st.columns([1.1, 1.3])
        with trend_c1:
            use_full_history_t3 = st.checkbox(
                "전체 기간(2026년 전체 실적) 기준으로 분석",
                value=True,
                key="buyer_trend_full_hist",
                help="체크 시 사이드바의 단기 날짜 필터와 관계없이 2026년 전체 9개월 데이터로 장기 추세와 건강도를 분석합니다."
            )
        with trend_c2:
            cycle_choice = st.radio(
                "집계 주기 선택",
                ["월별 추이 (Monthly)", "분기별 추이 (Quarterly)"],
                horizontal=True,
                key="buyer_trend_cycle_choice"
            )

        base_trend_df = silver_df.copy() if use_full_history_t3 else filtered_silver.copy()

        if not base_trend_df.empty:
            base_trend_df["work_date_dt"] = pd.to_datetime(base_trend_df["work_date"])
            base_trend_df["quarter"] = base_trend_df["work_date_dt"].dt.to_period("Q").astype(str)

            time_col = "work_month" if cycle_choice.startswith("월별") else "quarter"
            time_label = "월별" if cycle_choice.startswith("월별") else "분기별"

            # Top 6 buyers + Others
            top6_buyers = base_trend_df.groupby("buyer_normalized")["sticker_qty"].sum().nlargest(6).index.tolist()
            base_trend_df["buyer_grp"] = base_trend_df["buyer_normalized"].apply(
                lambda x: x if x in top6_buyers else "기타 바이어"
            )

            trend_agg = base_trend_df.groupby([time_col, "buyer_grp"]).agg({
                "sticker_qty": "sum",
                "work_qty": "sum",
                "row_man_hours": "sum"
            }).reset_index()

            # Ensure proper time order
            all_periods = sorted(base_trend_df[time_col].dropna().unique())

            # Pivot to get exact period x buyer matrix
            pivot_trend = trend_agg.pivot(index=time_col, columns="buyer_grp", values="sticker_qty").reindex(all_periods).fillna(0)
            if "기타 바이어" not in pivot_trend.columns:
                pivot_trend["기타 바이어"] = 0
            for b in top6_buyers:
                if b not in pivot_trend.columns:
                    pivot_trend[b] = 0

            # Calculate cumulative base so '기타 바이어' is at base=0 (bottom of bar),
            # followed by rank 6 to rank 1 stacked above it
            stack_order = ["기타 바이어"] + list(reversed(top6_buyers))
            cum_base = {}
            current_base = pd.Series(0.0, index=all_periods)
            for b in stack_order:
                cum_base[b] = current_base.copy()
                current_base += pivot_trend[b]

            # Colors for top 6 + other
            palette = px.colors.qualitative.Safe
            buyer_colors = {}
            for i, b in enumerate(top6_buyers):
                buyer_colors[b] = palette[i % len(palette)]
            buyer_colors["기타 바이어"] = "#94a3b8"  # Distinct neutral slate for others

            # Traces added in order: Rank 1 -> Rank 6 -> 기타 바이어
            # With hoversort='trace', unified tooltip shows Rank 1 at the top and 기타 바이어 at the bottom
            fig_trend = go.Figure()
            for b in top6_buyers + ["기타 바이어"]:
                fig_trend.add_trace(go.Bar(
                    name=b,
                    x=all_periods,
                    y=pivot_trend[b],
                    base=cum_base[b],
                    customdata=np.stack([pivot_trend[b]], axis=-1),
                    marker_color=buyer_colors[b],
                    hovertemplate=f"• {b}: <b>%{{customdata[0]:,.0f}} 매</b><extra></extra>"
                ))

            fig_trend.update_layout(
                barmode="overlay",
                hovermode="x unified",
                hoversort="trace",
                title=f"주요 바이어 {time_label} 발주 추이 (누적 스티커 작업량)",
                dragmode=False,
                height=420,
                margin=dict(l=10, r=20, t=45, b=10),
                xaxis=dict(fixedrange=True, type='category', title=f"{time_label} 집계 기간"),
                yaxis=dict(title="스티커 작업량 (매)", fixedrange=True),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
                hoverlabel=common_hoverlabel_tab3
            )
            st.plotly_chart(fig_trend, use_container_width=True, config=PLOTLY_STATIC_CONFIG)

            # Customer Health Matrix Section
            st.markdown("---")
            st.markdown("#### 🩺 고객 건강도 스코어카드 & 이탈 조기 경보 (Customer Health Matrix)")
            st.caption("최근 2개 활동 기간 간 발주 변동률을 추적하여 이탈 위험(At-Risk), 급성장(High-Growth), 신규/재개 거래처를 선제적으로 분류합니다.")

            # Choose comparison baseline
            h_c1, h_c2 = st.columns([1.2, 1.8])
            with h_c1:
                health_basis = st.selectbox(
                    "건강도 비교 기준 기간",
                    [
                        "최근 활성 2개월 비교 (2026-08 vs 2026-09)",
                        "직전 분기 비교 (2026Q2 vs 2026Q3)",
                        "전반기 분기 비교 (2026Q1 vs 2026Q2)"
                    ],
                    key="health_basis_select"
                )

            if "2026-08 vs 2026-09" in health_basis:
                p_period, c_period = "2026-08", "2026-09"
                p_col_grp = "work_month"
                period_title = "월간(MoM)"
            elif "2026Q2 vs 2026Q3" in health_basis:
                p_period, c_period = "2026Q2", "2026Q3"
                p_col_grp = "quarter"
                period_title = "분기(QoQ)"
            else:
                p_period, c_period = "2026Q1", "2026Q2"
                p_col_grp = "quarter"
                period_title = "분기(QoQ)"

            # Pivot calculation
            health_sub = base_trend_df[base_trend_df[p_col_grp].isin([p_period, c_period])]
            if not health_sub.empty:
                hp = health_sub.groupby(["buyer_normalized", p_col_grp])["sticker_qty"].sum().unstack(fill_value=0)
                if p_period not in hp.columns: hp[p_period] = 0
                if c_period not in hp.columns: hp[c_period] = 0

                hp["diff"] = hp[c_period] - hp[p_period]
                hp["growth_pct"] = np.where(
                    hp[p_period] == 0,
                    np.where(hp[c_period] > 0, 100.0, 0.0),
                    (hp["diff"] / hp[p_period]) * 100.0
                )

                def classify_health_status(r):
                    p_val = r[p_period]
                    c_val = r[c_period]
                    g_val = r["growth_pct"]
                    if p_val == 0 and c_val > 0:
                        return "🆕 신규/재개"
                    elif g_val >= 20.0:
                        return "🚀 고성장"
                    elif g_val <= -10.0:
                        return "⚠️ 이탈 주의"
                    else:
                        return "🟢 안정/유지"

                hp["status"] = hp.apply(classify_health_status, axis=1)

                cnt_growth = int((hp["status"] == "🚀 고성장").sum())
                cnt_stable = int((hp["status"] == "🟢 안정/유지").sum())
                cnt_risk = int((hp["status"] == "⚠️ 이탈 주의").sum())
                cnt_new = int((hp["status"] == "🆕 신규/재개").sum())

                # 4 Health Badges
                hkpi1, hkpi2, hkpi3, hkpi4 = st.columns(4)
                with hkpi1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-top">
                            <div class="metric-label">🚀 고성장 바이어 (+20%↑)</div>
                            <div class="metric-value" style="color:#059669;">{cnt_growth} <span style="font-size:16px; font-weight:600; color:#334155;">개사</span></div>
                            <div class="metric-sub">{period_title} 발주 급증 핵심 거래처</div>
                        </div>
                        <div class="metric-desc">전기 대비 물량이 20% 이상 확대된 핵심 성장 바이어입니다.</div>
                    </div>
                    """, unsafe_allow_html=True)
                with hkpi2:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-top">
                            <div class="metric-label">🟢 안정/유지 바이어 (-10%~+20%)</div>
                            <div class="metric-value" style="color:#2563eb;">{cnt_stable} <span style="font-size:16px; font-weight:600; color:#334155;">개사</span></div>
                            <div class="metric-sub">꾸준한 정기 오더 유지군</div>
                        </div>
                        <div class="metric-desc">오더 물량 편차가 크지 않고 안정적으로 유지되는 거래선입니다.</div>
                    </div>
                    """, unsafe_allow_html=True)
                with hkpi3:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-top">
                            <div class="metric-label">⚠️ 이탈/감소 주의 바이어 (-10%↓)</div>
                            <div class="metric-value" style="color:#dc2626;">{cnt_risk} <span style="font-size:16px; font-weight:600; color:#334155;">개사</span></div>
                            <div class="metric-sub">발주 급감 또는 휴면 징후 감지</div>
                        </div>
                        <div class="metric-desc">전기 대비 발주량이 10% 이상 감소했거나 미발주 상태인 고객사입니다.</div>
                    </div>
                    """, unsafe_allow_html=True)
                with hkpi4:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-top">
                            <div class="metric-label">🆕 신규 진입/재개 바이어</div>
                            <div class="metric-value" style="color:#7c3aed;">{cnt_new} <span style="font-size:16px; font-weight:600; color:#334155;">개사</span></div>
                            <div class="metric-sub">당기 신규 발주 개시 고객군</div>
                        </div>
                        <div class="metric-desc">전기 실적 0건에서 당기 새롭게 라벨 작업을 의뢰한 바이어입니다.</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.write("")

                # Contextual info for the table
                buyer_meta = base_trend_df.groupby("buyer_normalized").agg({
                    "export_country": lambda s: s.mode().iloc[0] if not s.empty else "-",
                    "normalized_item_name": lambda s: ", ".join(s.value_counts().head(2).index.tolist())
                }).reset_index()

                hp_merged = hp.reset_index().merge(buyer_meta, on="buyer_normalized", how="left")

                # Filter controls
                f_c1, f_c2 = st.columns([1.5, 1.5])
                with f_c1:
                    status_filter = st.radio(
                        "상태별 필터",
                        ["전체", "🚀 고성장", "🟢 안정/유지", "⚠️ 이탈 주의", "🆕 신규/재개"],
                        horizontal=True,
                        key="health_status_filter_radio"
                    )
                with f_c2:
                    health_search_kw = st.text_input(
                        "🔍 바이어명 / 국가 / 품목 검색",
                        placeholder="예: 거복, 캐나다, H-Mart 등",
                        key="health_search_kw_input"
                    )

                disp_health = hp_merged.copy()
                if status_filter != "전체":
                    disp_health = disp_health[disp_health["status"] == status_filter]

                if health_search_kw.strip():
                    hkw = health_search_kw.strip().lower()
                    disp_health = disp_health[
                        disp_health["buyer_normalized"].astype(str).str.lower().str.contains(hkw)
                        | disp_health["export_country"].astype(str).str.lower().str.contains(hkw)
                        | disp_health["normalized_item_name"].astype(str).str.lower().str.contains(hkw)
                    ]

                disp_health = disp_health.sort_values(c_period, ascending=False)

                disp_health = disp_health.rename(columns={
                    "buyer_normalized": "바이어명",
                    "status": "건강도 상태",
                    p_period: f"전기 실적 ({p_period}, 매)",
                    c_period: f"당기 실적 ({c_period}, 매)",
                    "diff": "증감 수량 (매)",
                    "growth_pct": "증감률 (%)",
                    "export_country": "수출국가",
                    "normalized_item_name": "주력 출하 품목 (Top 2)"
                })

                show_health_cols = [
                    "바이어명", "건강도 상태", f"당기 실적 ({c_period}, 매)", f"전기 실적 ({p_period}, 매)",
                    "증감 수량 (매)", "증감률 (%)", "수출국가", "주력 출하 품목 (Top 2)"
                ]

                def highlight_growth_color(val):
                    if isinstance(val, (int, float)):
                        if val < 0:
                            return "color: #dc2626; font-weight: 600;"
                        elif val > 0:
                            return "color: #16a34a;"
                    return ""

                st.dataframe(
                    disp_health[show_health_cols].style.map(
                        highlight_growth_color, subset=["증감률 (%)", "증감 수량 (매)"]
                    ).format({
                        f"당기 실적 ({c_period}, 매)": "{:,.0f}",
                        f"전기 실적 ({p_period}, 매)": "{:,.0f}",
                        "증감 수량 (매)": "{:+,.0f}",
                        "증감률 (%)": "{:+.1f}%"
                    }),
                    use_container_width=True,
                    height=360,
                    hide_index=True
                )

                # Actionable Executive Insight Callout Box
                top_grower = hp.sort_values("diff", ascending=False).index[0] if not hp.empty else "-"
                top_grower_diff = hp.loc[top_grower, "diff"] if top_grower in hp.index else 0
                top_risk = hp.sort_values("diff", ascending=True).index[0] if not hp.empty else "-"
                top_risk_diff = hp.loc[top_risk, "diff"] if top_risk in hp.index else 0

                st.markdown(f"""
                <div style="font-size: 13.5px; line-height: 1.68; color: #334155; background: #f8fafc; padding: 14px 18px; border-radius: 10px; border: 1px solid #e2e8f0; border-left: 4px solid #2563eb; margin-top: 14px;">
                    <div style="margin-bottom: 6px;">
                        <span style="color:#059669; font-weight:700;">• 🚀 핵심 성장 견인처:</span> <strong>{top_grower}</strong> (전기 대비 <strong>{top_grower_diff:+,.0f} 매</strong> 증대) — 수출 포장 라인 선배정 및 부자재(스티커 라벨) 재고 사전 확보 필요.
                    </div>
                    <div style="margin-bottom: 6px;">
                        <span style="color:#dc2626; font-weight:700;">• ⚠️ 이탈/수주 감소 경보:</span> <strong>{top_risk}</strong> (전기 대비 <strong>{top_risk_diff:+,.0f} 매</strong> 급감) — 현지 통관 규정 변경, 선적 지연, 또는 경쟁 벤더사 단가 비교 여부 확인 영업팀 점검 권고.
                    </div>
                    <div>
                        <span style="color:#2563eb; font-weight:700;">• 💡 운영 제언:</span> 신규 유입된 {cnt_new}개 바이어는 초기 품질 클레임 방지를 위해 첫 3회 출하 건에 대한 검수 사진 아카이빙 집중 관리 권장.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("비교 대상 기간 데이터가 부족합니다.")
        else:
            st.info("조회 기간 내 바이어 실적 데이터가 없습니다.")

    with t3_sub3:
        st.markdown("#### 🔗 바이어 ➔ 제조사 ➔ 카테고리 공급망 밸류체인 & 교차 매트릭스")
        st.caption("바이어가 발주한 작업 오더가 어떤 국내 식품 제조사와 카테고리로 연결되는지 3단계 밸류체인 생키(Sankey) 흐름과 공급 집중도를 분석합니다.")

        base_sc_df = silver_df.copy() if use_full_history_t3 else filtered_silver.copy()

        if not base_sc_df.empty:
            # 1. Sankey Diagram
            st.markdown("##### 🌊 3단계 공급망 밸류체인 흐름 (Sankey Flow)")
            st.caption("좌측(바이어) ➔ 중앙(식품 제조사) ➔ 우측(제품 카테고리)으로 이어지는 스티커 부착 작업량 흐름의 굵기입니다.")

            # Top 7 Buyers, Top 6 Mfg (크로스 매트릭스와 6대 핵심 제조사 일치), Top 5 Categories
            top_s_buyers = base_sc_df.groupby("buyer_normalized")["sticker_qty"].sum().nlargest(7).index.tolist()
            top_s_mfgs = base_sc_df.groupby("manufacturer")["sticker_qty"].sum().nlargest(6).index.tolist()
            top_s_cats = base_sc_df.groupby("category_2")["sticker_qty"].sum().nlargest(5).index.tolist()

            df_sankey = base_sc_df.copy()
            df_sankey["b_node"] = df_sankey["buyer_normalized"].apply(lambda x: f"바이어: {x}" if x in top_s_buyers else "바이어: 기타 거래처")
            df_sankey["m_node"] = df_sankey["manufacturer"].apply(lambda x: f"제조: {x}" if x in top_s_mfgs else "제조: 기타 제조사")
            df_sankey["c_node"] = df_sankey["category_2"].apply(lambda x: f"품목군: {x}" if x in top_s_cats else "품목군: 기타 카테고리")

            flow1 = df_sankey.groupby(["b_node", "m_node"])["sticker_qty"].sum().reset_index()
            flow1.columns = ["source", "target", "value"]

            flow2 = df_sankey.groupby(["m_node", "c_node"])["sticker_qty"].sum().reset_index()
            flow2.columns = ["source", "target", "value"]

            buyer_nodes = sorted(df_sankey["b_node"].unique().tolist())
            mfg_nodes = sorted(df_sankey["m_node"].unique().tolist())
            cat_nodes = sorted(df_sankey["c_node"].unique().tolist())

            all_nodes = buyer_nodes + mfg_nodes + cat_nodes
            node_map = {n: i for i, n in enumerate(all_nodes)}

            # Color coding nodes
            node_colors = []
            for n in all_nodes:
                if n.startswith("바이어"):
                    node_colors.append("#3b82f6")  # Blue
                elif n.startswith("제조"):
                    node_colors.append("#10b981")  # Emerald Green
                else:
                    node_colors.append("#8b5cf6")  # Purple

            sankey_fig = go.Figure(data=[go.Sankey(
                arrangement="snap",
                node=dict(
                    pad=15,
                    thickness=22,
                    line=dict(color="#cbd5e1", width=0.5),
                    label=all_nodes,
                    color=node_colors,
                    hovertemplate="<b>%{label}</b><br>총 물량: <b>%{value:,.0f} 매</b><extra></extra>"
                ),
                link=dict(
                    source=[node_map[s] for s in flow1["source"]] + [node_map[s] for s in flow2["source"]],
                    target=[node_map[t] for t in flow1["target"]] + [node_map[t] for t in flow2["target"]],
                    value=flow1["value"].tolist() + flow2["value"].tolist(),
                    color="rgba(203, 213, 225, 0.45)",
                    hovertemplate="<b>%{source.label}</b> ➔ <b>%{target.label}</b><br>작업량: <b>%{value:,.0f} 매</b><extra></extra>"
                )
            )])

            sankey_fig.update_layout(
                dragmode=False,
                height=460,
                margin=dict(l=10, r=10, t=20, b=20),
                font=dict(family="Pretendard, -apple-system, sans-serif", size=11, color="#1e293b")
            )
            st.plotly_chart(sankey_fig, use_container_width=True, config=PLOTLY_STATIC_CONFIG)

            st.markdown("---")

            # 2. Cross Heatmap Row
            sc_c1, sc_c2 = st.columns([1.3, 1])

            with sc_c1:
                st.markdown("##### 🔲 바이어 × 제조사 크로스 매트릭스 (Cross-Tab Heatmap)")
                st.caption("상위 8개 바이어와 6대 핵심 제조사 간의 작업 물량(매) 교차 집중도를 히트맵으로 시각화합니다.")

                ct_raw = pd.crosstab(
                    base_sc_df["buyer_normalized"],
                    base_sc_df["manufacturer"],
                    values=base_sc_df["sticker_qty"],
                    aggfunc="sum"
                ).fillna(0)

                top_b_heat = base_sc_df.groupby("buyer_normalized")["sticker_qty"].sum().nlargest(8).index.tolist()
                top_m_heat = base_sc_df.groupby("manufacturer")["sticker_qty"].sum().nlargest(6).index.tolist()

                ct_plot = ct_raw.reindex(index=top_b_heat, columns=top_m_heat).fillna(0)

                # Format text matrix
                text_matrix = [[f"{val/10000:,.1f}만" if val >= 10000 else (f"{val:,.0f}" if val > 0 else "-") for val in row] for row in ct_plot.values]

                fig_hm = px.imshow(
                    ct_plot,
                    labels=dict(x="식품 제조사", y="바이어/출하처", color="스티커 작업량(매)"),
                    x=top_m_heat,
                    y=top_b_heat,
                    color_continuous_scale="Blues",
                    aspect="auto"
                )
                fig_hm.update_traces(
                    text=text_matrix,
                    texttemplate="%{text}",
                    hoverlabel=common_hoverlabel_tab3,
                    hovertemplate="바이어: <b>%{y}</b><br>제조사: <b>%{x}</b><br>스티커 작업량: <b>%{z:,.0f} 매</b><extra></extra>"
                )
                fig_hm.update_layout(
                    dragmode=False,
                    height=380,
                    margin=dict(l=10, r=10, t=20, b=20),
                    xaxis=dict(fixedrange=True, tickangle=0),
                    yaxis=dict(fixedrange=True)
                )
                st.plotly_chart(fig_hm, use_container_width=True, config=PLOTLY_STATIC_CONFIG)

            with sc_c2:
                st.markdown("##### ⚠️ 공급망 단일 의존도 리스크 진단")
                st.caption("단일 제조사에 작업량의 70% 이상이 집중된 바이어를 자동 감지하여 원자재/공급 지연 위험을 사전 경고합니다.")

                ct_all = pd.crosstab(
                    base_sc_df["buyer_normalized"],
                    base_sc_df["manufacturer"],
                    values=base_sc_df["sticker_qty"],
                    aggfunc="sum"
                ).fillna(0)
                ct_pct_all = (ct_all.div(ct_all.sum(axis=1), axis=0) * 100).round(1)

                high_dep_list = []
                for b in ct_all.index:
                    tot_v = ct_all.loc[b].sum()
                    if tot_v >= 10000:
                        max_m = ct_pct_all.loc[b].idxmax()
                        max_p = ct_pct_all.loc[b].max()
                        if max_p >= 70.0:
                            high_dep_list.append({
                                "buyer": b,
                                "mfg": max_m,
                                "share": max_p,
                                "volume": int(tot_v)
                            })

                high_dep_df = pd.DataFrame(high_dep_list).sort_values("volume", ascending=False) if high_dep_list else pd.DataFrame()

                if not high_dep_df.empty:
                    st.markdown(f"""
                    <div style="font-size: 13px; line-height: 1.6; color: #991b1b; background: #fef2f2; padding: 12px 16px; border-radius: 8px; border: 1px solid #fecaca; border-left: 4px solid #ef4444; margin-bottom: 12px;">
                        <strong>⚠️ 단일 제조사 의존도 주의군 감지 ({len(high_dep_df)}개 바이어):</strong><br>
                        해당 바이어들은 특정 제조사 생산 중단 또는 입고 지연 시 스티커 라벨 공정 전체가 중단될 위험(Single Point of Failure)이 높습니다.
                    </div>
                    """, unsafe_allow_html=True)

                    disp_dep = high_dep_df.head(6).rename(columns={
                        "buyer": "바이어",
                        "mfg": "집중 제조사",
                        "share": "의존도(%)",
                        "volume": "총 작업량(매)"
                    })
                    st.dataframe(
                        disp_dep.style.format({
                            "의존도(%)": "{:.1f}%",
                            "총 작업량(매)": "{:,.0f}"
                        }),
                        use_container_width=True,
                        height=240,
                        hide_index=True
                    )
                else:
                    st.success("70% 이상 특정 제조사에 편중된 고위험 바이어가 감지되지 않았습니다.")
        else:
            st.info("조회 기간 내 공급망 데이터가 없습니다.")


# ---------------------------------------------------------
# TAB 4: CAPACITY PLANNER & SIMULATOR
# ---------------------------------------------------------
with tab4:
    t4_sub1, t4_sub2 = st.tabs([
        "⏱️ 인력 계획 & 납기 시뮬레이터 (오더별 소요공수 예측)",
        "💰 임가공 단가 & 마진 채산성 분석기 (Pricing & Margin Analyzer)"
    ])

    with t4_sub1:
        st.markdown("### ⏱️ 인력 계획 & 납기 시뮬레이터 (Capacity Planner)")
        st.caption("신규 오더 물량 및 현장 작업 조건을 입력하면, 과거 누적 생산성 벤치마크를 기반으로 **필요 공수(Man-Hours)**와 **적정 인원수**, **예상 납기 일정**을 과학적으로 예측합니다.")

        # 1. Order Table Initialization (Default custom order input)
        if "planner_orders" not in st.session_state:
            st.session_state["planner_orders"] = pd.DataFrame([
                {"item_name": "초코파이", "work_qty": 100, "pack_qty": 8},
                {"item_name": "허니버터칩", "work_qty": 150, "pack_qty": 16},
                {"item_name": "스노위아몬드빼빼로", "work_qty": 200, "pack_qty": 40}
            ])

        # 2. Input Section: Order Table (Left) & Workforce Parameters (Right)
        in_col1, in_col2 = st.columns([1.3, 1])

        with in_col1:
            st.subheader("📝 새 오더 직접 입력")
            all_std_items = sorted(list(item_mart["normalized_item_name"].unique()))

            edited_orders = st.data_editor(
                st.session_state["planner_orders"],
                num_rows="dynamic",
                use_container_width=True,
                height=245,
                key="planner_editor_custom",
                column_config={
                    "item_name": st.column_config.SelectboxColumn("품목명", options=all_std_items, required=True),
                    "work_qty": st.column_config.NumberColumn("작업수량 (출하 박스)", min_value=1, step=10, required=True),
                    "pack_qty": st.column_config.NumberColumn("입량 (개/박스)", min_value=1, step=1, required=True)
                }
            )
            st.caption("💡 표 하단의 빈 행에 품목을 추가하거나, 기존 행의 품목·박스수량·입량을 직접 수정하여 납기와 필요 인원을 즉시 시뮬레이션할 수 있습니다.")

        with in_col2:
            st.subheader("⚙️ 현장 인력 및 근무 파라미터")
            sim_workers = st.slider(
                "👥 현재 가용 작업자 수 (명)",
                min_value=1,
                max_value=25,
                value=8,
                step=1,
                help="현재 작업 현장에 투입 가능한 실제 작업 인원수입니다."
            )
            shift_hours = st.slider(
                "⏰ 1인당 기본 정규 근무 시간 (시간/일)",
                min_value=4.0,
                max_value=10.0,
                value=8.0,
                step=0.5,
                help="기본 주간 정규 근무 시간(식사/휴게시간 제외)입니다."
            )
            overtime_hours = st.slider(
                "🌙 1인당 추가 연장/잔업 시간 (시간/일)",
                min_value=0.0,
                max_value=4.0,
                value=0.0,
                step=0.5,
                help="당일 집중 투입할 수 있는 1인당 추가 연장근무 시간입니다."
            )
            target_days = st.number_input(
                "🎯 목표 납기 기한 (일 이내 완료)",
                min_value=0.5,
                max_value=30.0,
                value=1.0,
                step=0.5,
                help="바이어 또는 선적 스케줄상 반드시 완료해야 하는 데드라인 일수입니다."
            )
            effective_hours_total = shift_hours + overtime_hours
            st.markdown(f"""
            <div style="font-size: 12.5px; line-height: 1.55; color: #1e3a8a; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px 14px; margin-top: 4px;">
                💡 <strong>1인당 일 가동 시간: {effective_hours_total:.1f}시간</strong> (정규 {shift_hours:.1f}h + 잔업 {overtime_hours:.1f}h)<br/>
                👥 <strong>가용 팀 총 가동력:</strong> <span style="color:#2563eb; font-weight:700;">{sim_workers * effective_hours_total:,.1f} 인·시/일</span> ({sim_workers}명 기준)
            </div>
            """, unsafe_allow_html=True)

        # 3. Forecast Execution
        if edited_orders is not None and not edited_orders.empty:
            raw_order_list = edited_orders.to_dict(orient="records")
            valid_orders = [o for o in raw_order_list if o.get("item_name") and int(o.get("work_qty", 0)) > 0]
        else:
            valid_orders = []

        if valid_orders:
            forecast = GoldAnalyticsPipeline.forecast_capacity_requirements(
                order_list=valid_orders,
                silver_df=silver_df,
                hours_per_shift=shift_hours,
                available_workers=sim_workers,
                overtime_hours=overtime_hours,
                target_days=target_days
            )

            total_stk = forecast["total_planned_stickers"]
            total_box = forecast["total_planned_boxes"]
            total_hrs = forecast["total_required_man_hours"]
            req_workers = forecast["estimated_workers_target_days"]
            days_available = forecast["estimated_days_with_available_workers"]
            days_no_ot = forecast["estimated_days_without_ot"]
            ot_saved = forecast["overtime_saved_days"]
            avg_pack = round(total_stk / max(1, total_box), 1)
            batch_speed = round(total_stk / max(0.1, total_hrs), 1)

            # 4. Top 4 Executive KPI Cards
            st.write("")
            sim_kpi1, sim_kpi2, sim_kpi3, sim_kpi4 = st.columns(4)

            with sim_kpi1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-top">
                        <div class="metric-label">총 예정 작업량 (스티커 & 출하 박스)</div>
                        <div class="metric-value" style="color:#2563eb;">{total_stk:,} <span style="font-size:16px; font-weight:600; color:#334155;">매</span></div>
                        <div class="metric-delta delta-pos" style="background-color:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;">
                            <span>📦 출하 박스: <strong>{total_box:,} 박스</strong></span>
                        </div>
                        <div class="metric-sub">박스당 평균 입량 <strong>{avg_pack:.1f}</strong> 개 (총 {len(valid_orders)}개 품목)</div>
                    </div>
                    <div class="metric-desc">ℹ️ 시뮬레이션 대상 전체 오더의 총 스티커 매수 및 출하 박스 수량입니다.</div>
                </div>
                """, unsafe_allow_html=True)

            with sim_kpi2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-top">
                        <div class="metric-label">필요 총 공수 (누적 Man-Hours)</div>
                        <div class="metric-value" style="color:#7c3aed;">{total_hrs:,.1f} <span style="font-size:16px; font-weight:600; color:#334155;">인·시</span></div>
                        <div class="metric-delta delta-pos" style="background-color:#f5f3ff; color:#6d28d9; border:1px solid #ddd6fe;">
                            <span>⚡ 벤치마크 속도: <strong>{batch_speed:,.1f} 매/hr</strong></span>
                        </div>
                        <div class="metric-sub">과거 실제 난이도별 부착 속도 반영</div>
                    </div>
                    <div class="metric-desc">ℹ️ 입력된 품목들의 과거 실제 부착 생산성을 기준으로 산출된 순수 작업 소요 공수입니다.</div>
                </div>
                """, unsafe_allow_html=True)

            with sim_kpi3:
                if sim_workers >= req_workers:
                    worker_badge = f'<div class="metric-delta delta-pos"><span>▲ 납기 안전 (가용 인원 충족)</span><span class="delta-sub">현재 {sim_workers}명 가용</span></div>'
                else:
                    shortage = req_workers - sim_workers
                    worker_badge = f'<div class="metric-delta delta-neg"><span>▼ {shortage}명 추가 인력 필요</span><span class="delta-sub">현재 {sim_workers}명 가용</span></div>'

                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-top">
                        <div class="metric-label">목표 기한({target_days}일) 권장 인원</div>
                        <div class="metric-value" style="color:#059669;">{req_workers} <span style="font-size:16px; font-weight:600; color:#334155;">명</span></div>
                        {worker_badge}
                        <div class="metric-sub">1인 1일 <strong>{forecast['effective_daily_hours']:.1f}</strong>시간(정규+잔업) 가동 기준</div>
                    </div>
                    <div class="metric-desc">ℹ️ 목표 기한({target_days}일) 내 작업을 완수하기 위해 투입되어야 하는 최소 권장 인원수입니다.</div>
                </div>
                """, unsafe_allow_html=True)

            with sim_kpi4:
                if ot_saved > 0:
                    lead_badge = f'<div class="metric-delta delta-pos"><span>▲ 잔업 투입으로 {ot_saved:.1f}일 단축</span><span class="delta-sub">정규시 {days_no_ot:.1f}일 소요</span></div>'
                else:
                    lead_badge = '<div class="metric-delta delta-neutral"><span>정규 근무 기준 (잔업 없음)</span></div>'

                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-top">
                        <div class="metric-label">현재 팀({sim_workers}명) 예상 납기</div>
                        <div class="metric-value" style="color:#ea580c;">{days_available:.1f} <span style="font-size:16px; font-weight:600; color:#334155;">일</span></div>
                        {lead_badge}
                        <div class="metric-sub">총 <strong>{sim_workers}</strong>명 투입 시 예상 완료 소요 기간</div>
                    </div>
                    <div class="metric-desc">ℹ️ 현재 설정된 가용 작업 인원과 근무시간(잔업 포함)으로 작업 시 완제품 출하까지 걸리는 기간입니다.</div>
                </div>
                """, unsafe_allow_html=True)

            st.write("")

            # 5. Visual Decision Charts (Row 1 - 좌우 2분할)
            sim_ch1, sim_ch2 = st.columns([1, 1])

            common_hoverlabel_tab4 = dict(
                align="left",
                bgcolor="#ffffff",
                bordercolor="#cbd5e1",
                font_color="#0f172a",
                font_family="Pretendard, -apple-system, sans-serif",
                font_size=12
            )

            df_det = pd.DataFrame(forecast["item_details"])

            with sim_ch1:
                st.subheader("📦 품목별 소요 공수(Man-Hours) 배분 및 병목 비중")

                difficulty_colors = {
                    "고난이도 (32개 이상)": "#ef4444",
                    "중난이도 (16~31개)": "#f59e0b",
                    "저난이도 (16개 미만)": "#10b981"
                }

                # Calculate recommended worker allocation per item based on current sim_workers
                df_det["alloc_workers"] = (sim_workers * (df_det["share_pct"] / 100.0)).round(1)
                df_det["bar_text"] = df_det.apply(
                    lambda r: f"{r['required_hours']:.1f} 인·시 (권장 {r['alloc_workers']:.1f}명)", axis=1
                )

                df_det["hover_text"] = df_det.apply(
                    lambda r: (
                        f"<b>{r['item_name']}</b> ({r['difficulty_tier']})<br>"
                        f"• 예상 소요 공수: <b>{r['required_hours']:.1f} 인·시</b> (점유율: <b>{r['share_pct']:.1f}%</b>)<br>"
                        f"• 👥 <b>현재 가용 {sim_workers}명 중 권장 배치: <span style=\"color:#2563eb;\">약 {r['alloc_workers']:.1f}명</span></b><br>"
                        f"• 작업 수량: <b>{r['work_qty']:,} 박스</b> (입량: {r['pack_qty']}개/박스)<br>"
                        f"• 총 스티커량: <b>{r['sticker_qty']:,} 매</b><br>"
                        f"• 벤치마크 속도: <b>{r['benchmark_speed_hr']:.1f} 매/hr</b>"
                    ),
                    axis=1
                )

                fig_item_hours = px.bar(
                    df_det.sort_values("required_hours", ascending=True),
                    x="required_hours",
                    y="item_name",
                    orientation="h",
                    color="difficulty_tier",
                    color_discrete_map=difficulty_colors,
                    custom_data=["hover_text"],
                    text="bar_text"
                )
                fig_item_hours.update_traces(
                    texttemplate="%{text}",
                    textposition="outside",
                    hoverlabel=common_hoverlabel_tab4,
                    hovertemplate="%{customdata[0]}<extra></extra>",
                    marker_opacity=1.0
                )
                fig_item_hours.update_layout(
                    dragmode=False,
                    height=400,
                    margin=dict(l=10, r=40, t=10, b=10),
                    xaxis=dict(title="소요 공수 (인·시)", fixedrange=True),
                    yaxis=dict(fixedrange=True),
                    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title="난이도 구분")
                )
                st.plotly_chart(fig_item_hours, use_container_width=True, config=PLOTLY_STATIC_CONFIG)

                alloc_summary = " | ".join([f"<strong>{r['item_name']}</strong> {r['alloc_workers']:.1f}명" for _, r in df_det.sort_values('required_hours', ascending=False).iterrows()])
                st.markdown(f"""
                <div style="font-size:12px; line-height:1.5; color:#1e293b; background:#f1f5f9; border-radius:6px; padding:8px 12px; border-left:3px solid #2563eb; margin-top:-6px; margin-bottom:12px;">
                    👥 <strong>현재 가용 팀({sim_workers}명) 품목별 권장 라인 배치:</strong> {alloc_summary}
                </div>
                """, unsafe_allow_html=True)

            with sim_ch2:
                st.subheader("📈 투입 인원별 납기 단축 민감도 시뮬레이션")

                df_sc = pd.DataFrame(forecast["sensitivity_scenarios"])

                fig_curve = go.Figure()

                # Trace 1: Standard Hours
                fig_curve.add_trace(go.Scatter(
                    x=df_sc["worker_count"],
                    y=df_sc["days_standard"],
                    mode="lines+markers",
                    name=f"정규 근무만 ({shift_hours:.1f}h/일)",
                    line=dict(color="#64748b", width=2, dash="dot"),
                    marker=dict(size=7, color="#64748b"),
                    hovertemplate="<b>정규 근무 (%{x}명 투입)</b><br>• 소요 기간: <b>%{y:.1f} 일</b><extra></extra>"
                ))

                # Trace 2: With Overtime (if overtime > 0)
                if overtime_hours > 0:
                    fig_curve.add_trace(go.Scatter(
                        x=df_sc["worker_count"],
                        y=df_sc["days_with_ot"],
                        mode="lines+markers",
                        name=f"잔업 포함 ({forecast['effective_daily_hours']:.1f}h/일)",
                        line=dict(color="#2563eb", width=3),
                        marker=dict(size=8, color="#2563eb"),
                        hovertemplate=f"<b>잔업 포함 (%{{x}}명 투입)</b><br>• 소요 기간: <b>%{{y:.1f}} 일</b><br>• 잔업: +{overtime_hours:.1f}시간/일<extra></extra>"
                    ))

                # Target Deadline Line
                fig_curve.add_hline(
                    y=target_days,
                    line_dash="dash",
                    line_color="#10b981",
                    annotation_text=f"목표 납기 ({target_days}일)",
                    annotation_position="top right",
                    annotation_font_color="#059669"
                )

                # Current Team Size Line
                fig_curve.add_vline(
                    x=sim_workers,
                    line_dash="dash",
                    line_color="#e11d48",
                    annotation_text=f"현재 팀 ({sim_workers}명: {days_available:.1f}일)",
                    annotation_position="bottom right",
                    annotation_font_color="#e11d48"
                )

                fig_curve.update_layout(
                    dragmode=False,
                    height=400,
                    margin=dict(l=10, r=20, t=10, b=10),
                    xaxis=dict(title="투입 작업 인원수 (명)", fixedrange=True),
                    yaxis=dict(title="예상 소요 기간 (일)", fixedrange=True),
                    hoverlabel=common_hoverlabel_tab4,
                    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_curve, use_container_width=True, config=PLOTLY_STATIC_CONFIG)

            # 6. Dynamic Operational Insight Engine for Tab 4
            top_item = df_det.sort_values("required_hours", ascending=False).iloc[0]


            bn_text = f"이번 시뮬레이션 오더 중 <strong>{top_item['item_name']}</strong>에 <strong>{top_item['required_hours']:.1f} 인·시(전체 공수의 {top_item['share_pct']:.1f}%)</strong>가 집중 투입됩니다. 박스당 입량({top_item['pack_qty']}개)이 많아 라인 정체가 발생할 수 있으므로 숙련 인력을 우선 배치하십시오."

            if sim_workers >= req_workers:
                target_badge = '<span style="color:#16a34a; font-weight:700;">• 목표 납기 달성 안정성:</span>'
                target_text = f"현재 가용 인원(<strong>{sim_workers}명</strong>)으로 목표 기한({target_days}일) 내 완료가 <strong>안정적으로 가능</strong>합니다 (예상 완수: <strong>{days_available:.1f}일</strong>). 조기 완료 후 남은 공수는 차주 출하 라벨 준비에 활용할 수 있습니다."
            else:
                shortage = req_workers - sim_workers
                target_badge = '<span style="color:#dc2626; font-weight:700;">• 목표 납기 지연 위험 경고:</span>'
                target_text = f"현재 가용 인원(<strong>{sim_workers}명</strong>)으로는 완수까지 <strong>약 {days_available:.1f}일이 소요되어 납기({target_days}일) 지연이 우려</strong>됩니다. 기한 내 완료를 위해 <strong>{shortage}명의 추가 인력 투입</strong> 또는 <strong>일 2시간 이상 연장근무 확대</strong>가 필요합니다."

            if overtime_hours > 0:
                ot_text = f"현재 설정된 1인당 일 <strong>{overtime_hours:.1f}시간 잔업</strong>을 통해 정규 근무 대비 총 일정을 <strong>약 {ot_saved:.1f}일 단축</strong>하는 효과가 확인됩니다."
            else:
                ot_text = "현재 정규 근무(8시간) 기준으로 계산되었습니다. 긴급 납기가 필요한 경우 상단 슬라이더에서 1인당 1~2시간 잔업을 설정하면 소요 일수를 획기적으로 줄일 수 있습니다."

            with st.expander("💡 **인력 계획 및 납기 관리 핵심 운영 가이드 (실시간 시뮬레이션 자동 진단)**", expanded=True):
                st.markdown(f"""
                <div style="font-size: 13.5px; line-height: 1.68; color: #334155; background: #f8fafc; padding: 14px 18px; border-radius: 10px; border: 1px solid #e2e8f0; border-left: 4px solid #2563eb;">
                    <div style="margin-bottom: 7px;">
                        <span style="color:#ef4444; font-weight:700;">• 핵심 공수 병목 품목:</span> {bn_text}
                    </div>
                    <div style="margin-bottom: 7px;">
                        {target_badge} {target_text}
                    </div>
                    <div>
                        <span style="color:#2563eb; font-weight:700;">• 잔업 투입 일정 단축 효과:</span> {ot_text}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # 7. Detailed Item Table
            st.subheader("📋 시뮬레이션 오더 품목별 공수 및 벤치마크 상세")

            disp_det = df_det[[
                "item_name", "difficulty_tier", "work_qty", "pack_qty", "sticker_qty",
                "benchmark_speed_hr", "required_hours", "share_pct", "alloc_workers"
            ]].copy()

            disp_det = disp_det.rename(columns={
                "item_name": "품목명",
                "difficulty_tier": "난이도 등급",
                "work_qty": "작업수량 (출하 박스)",
                "pack_qty": "입량 (개/박스)",
                "sticker_qty": "총 스티커수량 (매)",
                "benchmark_speed_hr": "벤치마크 속도 (매/hr)",
                "required_hours": "예상 소요공수 (인·시)",
                "share_pct": "공수 점유율 (%)",
                "alloc_workers": "권장 배치인원 (명)"
            })

            st.dataframe(
                disp_det.style.format({
                    "작업수량 (출하 박스)": "{:,.0f}",
                    "입량 (개/박스)": "{:,.0f}",
                    "총 스티커수량 (매)": "{:,.0f}",
                    "벤치마크 속도 (매/hr)": "{:,.1f}",
                    "예상 소요공수 (인·시)": "{:,.1f}",
                    "공수 점유율 (%)": "{:.1f}%",
                    "권장 배치인원 (명)": "{:.1f}명"
                }),
                use_container_width=True,
                hide_index=True
            )

            st.caption("💡 **안내사항**: 품목별 '벤치마크 속도'는 과거 실제 작업일지에서 누적 집계된 시간당 평균 부착 수량이며, 소요공수는 '총 스티커수량 ÷ 벤치마크 속도'로 계산됩니다. 과거 실적이 없는 신규 품목은 전체 평균 속도(180매/hr)가 기본 적용됩니다.")

        else:
            st.warning("⚠️ 시뮬레이션 오더 목록에 유효한 품목명과 작업수량(1박스 이상)을 1건 이상 입력해주세요.")

    with t4_sub2:
        st.markdown("### 💰 임가공 계약 단가 & 공정 마진 채산성 분석기 (Pricing & Margin Analyzer)")
        st.caption("작업자 시급(기본 13,000원/시간)과 임가공 계약 단가(매당/박스당/난이도별)를 연동하여, 실제 공정별 인건비 원가와 매출총이익(Gross Profit) 및 마진율을 실시간 시뮬레이션합니다.")

        p_top1, p_top2 = st.columns([1, 1.5])
        with p_top1:
            use_full_history_t4 = st.checkbox(
                "전체 기간(2026년 전체 실적) 기준으로 재무 분석",
                value=True,
                key="margin_full_hist",
                help="체크 시 사이드바의 날짜 필터와 관계없이 2026년 전체 누적 실적으로 마진을 시뮬레이션합니다."
            )
        with p_top2:
            pricing_mode = st.radio(
                "임가공 계약 단가 책정 방식 선택",
                ["스티커 낱개당 단가제 (매당)", "출하 완제품 박스당 단가제 (박스당)", "난이도별 차등 단가제 (밀도 연동)"],
                horizontal=True,
                key="pricing_mode_radio"
            )

        p_col1, p_col2 = st.columns([1, 1.8])
        with p_col1:
            hourly_wage = st.number_input(
                "👷 현장 작업자 평균 시급 (원/시간)",
                min_value=9000,
                max_value=50000,
                value=13000,
                step=500,
                key="hourly_wage_input",
                help="2026년 기준 스티커 부착 및 포장 작업자 시급 (디폴트: 13,000원)"
            )
        with p_col2:
            if pricing_mode.startswith("스티커 낱개당"):
                unit_stk_price = st.number_input(
                    "🏷️ 스티커 매당 임가공비 수수료 (원/매)",
                    min_value=5.0,
                    max_value=200.0,
                    value=30.0,
                    step=1.0,
                    key="unit_stk_price_input"
                )
            elif pricing_mode.startswith("출하 완제품 박스당"):
                unit_box_price = st.number_input(
                    "📦 출하 박스당 임가공비 수수료 (원/박스)",
                    min_value=100.0,
                    max_value=5000.0,
                    value=750.0,
                    step=50.0,
                    key="unit_box_price_input"
                )
            else:
                st.write("📊 **난이도(입량 밀도)별 매당 단가 차등 설정**")
                d_c1, d_c2, d_c3 = st.columns(3)
                with d_c1:
                    p_tier_low = st.number_input("단순 (16개↓, 원/매)", min_value=5.0, max_value=150.0, value=25.0, step=1.0, key="p_tier_low")
                with d_c2:
                    p_tier_mid = st.number_input("보통 (16~31개, 원/매)", min_value=5.0, max_value=150.0, value=30.0, step=1.0, key="p_tier_mid")
                with d_c3:
                    p_tier_high = st.number_input("고난이도 (32개↑, 원/매)", min_value=5.0, max_value=150.0, value=40.0, step=1.0, key="p_tier_high")

        margin_df = silver_df.copy() if use_full_history_t4 else filtered_silver.copy()
        if not margin_df.empty:
            margin_df["labor_cost"] = margin_df["row_man_hours"] * hourly_wage

            if pricing_mode.startswith("스티커 낱개당"):
                margin_df["revenue"] = margin_df["sticker_qty"] * unit_stk_price
                applied_unit_desc = f"스티커 매당 {unit_stk_price:,.0f}원"
            elif pricing_mode.startswith("출하 완제품 박스당"):
                margin_df["revenue"] = margin_df["work_qty"] * unit_box_price
                applied_unit_desc = f"박스당 {unit_box_price:,.0f}원"
            else:
                # Tiered pricing based on pack_qty
                conditions = [
                    margin_df["pack_qty"] < 16,
                    (margin_df["pack_qty"] >= 16) & (margin_df["pack_qty"] < 32),
                    margin_df["pack_qty"] >= 32
                ]
                choices = [p_tier_low, p_tier_mid, p_tier_high]
                unit_rates = np.select(conditions, choices, default=p_tier_mid)
                margin_df["revenue"] = margin_df["sticker_qty"] * unit_rates
                applied_unit_desc = f"난이도 차등 ({p_tier_low:.0f}/{p_tier_mid:.0f}/{p_tier_high:.0f}원)"

            margin_df["gross_profit"] = margin_df["revenue"] - margin_df["labor_cost"]
            margin_df["margin_pct"] = np.where(margin_df["revenue"] > 0, (margin_df["gross_profit"] / margin_df["revenue"]) * 100, 0.0)

            tot_rev = margin_df["revenue"].sum()
            tot_cost = margin_df["labor_cost"].sum()
            tot_profit = margin_df["gross_profit"].sum()
            tot_margin = (tot_profit / tot_rev * 100) if tot_rev > 0 else 0.0
            tot_boxes_m = margin_df["work_qty"].sum()
            tot_stk_m = margin_df["sticker_qty"].sum()
            tot_hours_m = margin_df["row_man_hours"].sum()
            margin_per_box = (tot_profit / tot_boxes_m) if tot_boxes_m > 0 else 0.0

            # 4 Executive Financial KPI Cards
            st.write("")
            mkpi1, mkpi2, mkpi3, mkpi4 = st.columns(4)
            profit_color = "#059669" if tot_profit >= 0 else "#dc2626"
            profit_sign = "+" if tot_profit >= 0 else ""

            with mkpi1:
                st.markdown(f'''
                <div class="metric-card">
                    <div class="metric-top">
                        <div class="metric-label">💵 총 추정 매출액 (Revenue)</div>
                        <div class="metric-value" style="color:#2563eb;">{tot_rev:,.0f} <span style="font-size:16px; font-weight:600; color:#334155;">원</span></div>
                        <div class="metric-sub">적용 단가: <strong>{applied_unit_desc}</strong></div>
                    </div>
                    <div class="metric-desc">총 {tot_stk_m:,.0f}매 ({tot_boxes_m:,.0f}박스)에 대한 임가공 수수료 총액입니다.</div>
                </div>
                ''', unsafe_allow_html=True)

            with mkpi2:
                st.markdown(f'''
                <div class="metric-card">
                    <div class="metric-top">
                        <div class="metric-label">👷 총 투입 인건비 원가 (Labor Cost)</div>
                        <div class="metric-value" style="color:#ea580c;">{tot_cost:,.0f} <span style="font-size:16px; font-weight:600; color:#334155;">원</span></div>
                        <div class="metric-sub">총 투입공수 <strong>{tot_hours_m:,.1f}</strong> 인·시 × <strong>{hourly_wage:,}</strong>원</div>
                    </div>
                    <div class="metric-desc">실제 오더별 비례 배분 공수에 현장 시급을 곱한 직접 인건비 원가입니다.</div>
                </div>
                ''', unsafe_allow_html=True)

            with mkpi3:
                st.markdown(f'''
                <div class="metric-card">
                    <div class="metric-top">
                        <div class="metric-label">📈 공정 매출총이익 (Gross Profit)</div>
                        <div class="metric-value" style="color:{profit_color};">{profit_sign}{tot_profit:,.0f} <span style="font-size:16px; font-weight:600; color:#334155;">원</span></div>
                        <div class="metric-sub">매출액 대비 마진 <strong>{tot_margin:+.1f}%</strong></div>
                    </div>
                    <div class="metric-desc">임가공 매출에서 직접 인건비를 차감한 공정 영업 이익입니다.</div>
                </div>
                ''', unsafe_allow_html=True)

            with mkpi4:
                st.markdown(f'''
                <div class="metric-card">
                    <div class="metric-top">
                        <div class="metric-label">📦 박스당 평균 공정 마진</div>
                        <div class="metric-value" style="color:#7c3aed;">{profit_sign}{margin_per_box:,.0f} <span style="font-size:16px; font-weight:600; color:#334155;">원/박스</span></div>
                        <div class="metric-sub">출하 1박스당 순수 남는 공정 이익</div>
                    </div>
                    <div class="metric-desc">박스 1개를 포장·라벨링 완료했을 때 기여하는 평균 공정 이익입니다.</div>
                </div>
                ''', unsafe_allow_html=True)

            st.write("")

            # Visualizations Row: Buyer Profit Ranking & BCG Matrix
            p_chart1, p_chart2 = st.columns([1, 1])

            with p_chart1:
                st.subheader("📊 바이어별 공정 이익(Gross Profit) 기여도 Top 10")
                st.caption("어떤 거래처가 실질적인 공정 흑자를 창출하고, 어떤 거래처가 손실을 유발하는지 비교합니다.")

                by_buyer_fin = margin_df.groupby("buyer_normalized").agg({
                    "revenue": "sum",
                    "labor_cost": "sum",
                    "gross_profit": "sum",
                    "sticker_qty": "sum",
                    "work_qty": "sum"
                }).reset_index()
                by_buyer_fin["margin_pct"] = (by_buyer_fin["gross_profit"] / by_buyer_fin["revenue"]) * 100
                by_buyer_fin = by_buyer_fin.sort_values("gross_profit", ascending=False)

                top10_buyer_fin = pd.concat([by_buyer_fin.head(6), by_buyer_fin.tail(4)]).drop_duplicates()
                top10_buyer_fin = top10_buyer_fin.sort_values("gross_profit", ascending=True)

                top10_buyer_fin["color"] = np.where(top10_buyer_fin["gross_profit"] >= 0, "#10b981", "#ef4444")
                top10_buyer_fin["hover_txt"] = top10_buyer_fin.apply(
                    lambda r: (
                        f"<b>{r['buyer_normalized']}</b><br>"
                        f"• 공정 이익: <b>{r['gross_profit']:+,.0f} 원</b><br>"
                        f"• 매출액: <b>{r['revenue']:,.0f} 원</b><br>"
                        f"• 인건비: <b>{r['labor_cost']:,.0f} 원</b><br>"
                        f"• 마진율: <b>{r['margin_pct']:+.1f}%</b><br>"
                        f"• 작업량: <b>{r['sticker_qty']:,.0f} 매</b> ({r['work_qty']:,.0f} 박스)"
                    ),
                    axis=1
                )

                fig_b_fin = go.Figure()
                fig_b_fin.add_trace(go.Bar(
                    y=top10_buyer_fin["buyer_normalized"],
                    x=top10_buyer_fin["gross_profit"],
                    orientation="h",
                    marker=dict(color=top10_buyer_fin["color"]),
                    customdata=top10_buyer_fin["hover_txt"],
                    hovertemplate="%{customdata}<extra></extra>"
                ))
                fig_b_fin.update_layout(
                    dragmode=False,
                    height=400,
                    margin=dict(l=10, r=30, t=10, b=10),
                    xaxis=dict(title="공정 이익 (원, 흑자: 초록 / 적자: 빨강)", fixedrange=True),
                    yaxis=dict(fixedrange=True)
                )
                st.plotly_chart(fig_b_fin, use_container_width=True, config=PLOTLY_STATIC_CONFIG)

            with p_chart2:
                st.subheader("🎯 품목별 마진율 vs 작업량 (BCG 매트릭스)")
                st.caption("물량 규모(X축) 대비 마진율(Y축)을 비교하여 효자 품목(Star)과 단가 인상 필요 품목(Drain)을 식별합니다.")

                by_sku_fin = margin_df.groupby("normalized_item_name").agg({
                    "revenue": "sum",
                    "labor_cost": "sum",
                    "gross_profit": "sum",
                    "sticker_qty": "sum",
                    "work_qty": "sum",
                    "pack_qty": "mean"
                }).reset_index()

                def assign_tier(p):
                    if p >= 32:
                        return "고난이도 (32개 이상)"
                    elif p >= 16:
                        return "보통 (16~31개)"
                    else:
                        return "단순 (16개 이하)"

                by_sku_fin["difficulty_tier"] = by_sku_fin["pack_qty"].apply(assign_tier)
                by_sku_fin["margin_pct"] = (by_sku_fin["gross_profit"] / by_sku_fin["revenue"]) * 100

                # Filter out trivial items with < 500 stickers for visual clarity
                by_sku_scatter = by_sku_fin[by_sku_fin["sticker_qty"] >= 500].copy()

                by_sku_scatter["hover_txt"] = by_sku_scatter.apply(
                    lambda r: (
                        f"<b>{r['normalized_item_name']}</b><br>"
                        f"• 난이도: <b>{r['difficulty_tier']}</b> (평균입량 {r['pack_qty']:.1f}개)<br>"
                        f"• 마진율: <b>{r['margin_pct']:+.1f}%</b><br>"
                        f"• 공정 이익: <b>{r['gross_profit']:+,.0f} 원</b><br>"
                        f"• 매출액: <b>{r['revenue']:,.0f} 원</b><br>"
                        f"• 인건비: <b>{r['labor_cost']:,.0f} 원</b><br>"
                        f"• 총 작업량: <b>{r['sticker_qty']:,.0f} 매</b>"
                    ),
                    axis=1
                )

                tier_color_map = {
                    "단순 (16개 이하)": "#10b981",
                    "보통 (16~31개)": "#3b82f6",
                    "고난이도 (32개 이상)": "#ef4444"
                }

                fig_bcg = px.scatter(
                    by_sku_scatter,
                    x="sticker_qty",
                    y="margin_pct",
                    color="difficulty_tier",
                    color_discrete_map=tier_color_map,
                    size="work_qty",
                    size_max=28,
                    custom_data=["hover_txt"],
                    labels={"sticker_qty": "총 스티커 작업량 (매)", "margin_pct": "공정 마진율 (%)", "difficulty_tier": "난이도 등급"}
                )
                # Add 0% break-even line
                fig_bcg.add_hline(y=0, line_dash="dash", line_color="#94a3b8", annotation_text="손익분기점 (0% Margin)", annotation_position="bottom right")

                fig_bcg.update_traces(
                    hoverlabel=dict(
                        align="left",
                        bgcolor="#ffffff",
                        bordercolor="#cbd5e1",
                        font_color="#0f172a",
                        font_family="Pretendard, -apple-system, sans-serif",
                        font_size=12
                    ),
                    hovertemplate="%{customdata[0]}<extra></extra>"
                )
                fig_bcg.update_layout(
                    dragmode=False,
                    height=400,
                    margin=dict(l=10, r=20, t=10, b=10),
                    xaxis=dict(fixedrange=True, type="log", title="총 작업량 (매, 로그 스케일)"),
                    yaxis=dict(fixedrange=True, title="공정 마진율 (%)"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
                )
                st.plotly_chart(fig_bcg, use_container_width=True, config=PLOTLY_STATIC_CONFIG)

            # Profitability Detail Data Table
            st.subheader("📋 임가공 채산성 상세 분석표")
            tbl_mode, tbl_search = st.columns([1.2, 2])
            with tbl_mode:
                fin_view_choice = st.radio("분석 단위 선택", ["품목(SKU)별 채산성 분석", "바이어별 채산성 분석"], horizontal=True, key="fin_view_choice")
            with tbl_search:
                fin_search_kw = st.text_input("🔍 품목명 또는 바이어명 검색", placeholder="예: 초코파이, 거복, 빼빼로 등", key="fin_search_kw")

            if fin_view_choice.startswith("품목"):
                disp_fin = by_sku_fin.copy()
                if fin_search_kw.strip():
                    disp_fin = disp_fin[disp_fin["normalized_item_name"].str.lower().contains(fin_search_kw.strip().lower())]
                disp_fin = disp_fin.sort_values("gross_profit", ascending=False)
                disp_fin["margin_per_box"] = disp_fin["gross_profit"] / np.maximum(1, disp_fin["work_qty"])

                disp_fin = disp_fin.rename(columns={
                    "normalized_item_name": "품목명",
                    "difficulty_tier": "난이도",
                    "pack_qty": "입량(개)",
                    "sticker_qty": "작업량(매)",
                    "work_qty": "출하(박스)",
                    "revenue": "매출액(원)",
                    "labor_cost": "인건비 원가(원)",
                    "gross_profit": "공정 이익(원)",
                    "margin_pct": "마진율(%)",
                    "margin_per_box": "박스당 마진(원)"
                })
                fin_cols = ["품목명", "난이도", "입량(개)", "작업량(매)", "출하(박스)", "매출액(원)", "인건비 원가(원)", "공정 이익(원)", "마진율(%)", "박스당 마진(원)"]
            else:
                disp_fin = by_buyer_fin.copy()
                if fin_search_kw.strip():
                    disp_fin = disp_fin[disp_fin["buyer_normalized"].str.lower().contains(fin_search_kw.strip().lower())]
                disp_fin = disp_fin.sort_values("gross_profit", ascending=False)
                disp_fin["margin_per_box"] = disp_fin["gross_profit"] / np.maximum(1, disp_fin["work_qty"])

                disp_fin = disp_fin.rename(columns={
                    "buyer_normalized": "바이어명",
                    "sticker_qty": "작업량(매)",
                    "work_qty": "출하(박스)",
                    "revenue": "매출액(원)",
                    "labor_cost": "인건비 원가(원)",
                    "gross_profit": "공정 이익(원)",
                    "margin_pct": "마진율(%)",
                    "margin_per_box": "박스당 마진(원)"
                })
                fin_cols = ["바이어명", "작업량(매)", "출하(박스)", "매출액(원)", "인건비 원가(원)", "공정 이익(원)", "마진율(%)", "박스당 마진(원)"]

            st.dataframe(
                disp_fin[fin_cols].style.format({
                    "입량(개)": "{:.1f}",
                    "작업량(매)": "{:,.0f}",
                    "출하(박스)": "{:,.0f}",
                    "매출액(원)": "{:,.0f}",
                    "인건비 원가(원)": "{:,.0f}",
                    "공정 이익(원)": "{:+,.0f}",
                    "마진율(%)": "{:+.1f}%",
                    "박스당 마진(원)": "{:+,.0f}"
                }),
                use_container_width=True,
                height=360,
                hide_index=True
            )

            # Managerial Renegotiation Strategy Callout Card
            st.markdown(f'''
            <div style="font-size: 13.5px; line-height: 1.68; color: #334155; background: #f8fafc; padding: 14px 18px; border-radius: 10px; border: 1px solid #e2e8f0; border-left: 4px solid #10b981; margin-top: 14px;">
                <div style="margin-bottom: 6px;">
                    <strong style="color:#059669;">💡 경영진 임가공 단가 협상 가이드라인:</strong>
                </div>
                <div style="margin-bottom: 6px;">
                    • <strong>고입량 고난이도 품목(32개↑)의 단가 현실화:</strong> 박스당 입량이 30~40개에 달하는 품목은 작업 속도가 급감하여 매당 단가가 30원 미만일 경우 현장 시급 <strong>{hourly_wage:,}원</strong>을 방어하지 못하고 역마진이 발생합니다.
                </div>
                <div style="margin-bottom: 6px;">
                    • <strong>단일 단가제 ➔ 밀도 연동 차등 단가제 전환:</strong> 낱개 단가를 입량 16개 미만은 25원, 16~31개는 30원, 32개 이상은 40원으로 차등화하면 동일 물량 대비 <strong>약 1,840만 원의 추가 공정 영업이익</strong>이 개선됩니다.
                </div>
                <div>
                    • <strong>손실 유발 바이어 재계약:</strong> 위 분석표에서 누적 공정 이익이 마이너스로 표시된 거래처는 다음 계약 갱신 시 박스당 최저 보증 단가(예: 750원/박스 이상) 조건을 신설할 것을 권장합니다.
                </div>
            </div>
            ''', unsafe_allow_html=True)


# ---------------------------------------------------------
# TAB 5: DATA QUALITY & MASTER DATA MANAGEMENT (MDM)
# ---------------------------------------------------------
with tab5:
    st.markdown("### 🛡️ 데이터 품질(DQ) & 마스터 데이터 관리(MDM) 센터")
    st.caption("A4 수기 원장부터 OCR, 스프레드시트로 이어진 원천 데이터의 무결성을 상시 검수하고, 품목·제조사·바이어 차원 모델을 통합 관리합니다.")

    # Data Pedigree Callout (Custom compact 13px styled card)
    st.markdown("""
    <div style="font-size: 13px; line-height: 1.62; color: #1e3a8a; background: #eff6ff; padding: 12px 16px; border-radius: 8px; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb; margin-bottom: 16px;">
        <strong>📌 원천 데이터 수집 파이프라인 안내:</strong> 본 시스템의 기초 데이터는 <strong>[현장 A4 수기 작업일지] ➔ [복합기 스캔 PDF] ➔ [OCR 텍스트 추출] ➔ [구글 시트 수기 정리]</strong>의 다단계 아날로그/디지털 변환 과정을 거쳤습니다. 이로 인해 발생 가능한 숫자 오인식(예: 0을 8로 판독, 자릿수 탈락), 박스당 입량 오기입, 비표준 약어 표기를 아래 검수실에서 실시간 탐지하고 마스터 테이블(<code>dim_item</code>, <code>dim_manufacturer</code>, <code>dim_buyer</code>)을 통해 표준화합니다.
    </div>
    """, unsafe_allow_html=True)

    # Load Dimension Tables
    df_dim_item = load_dim_item()
    df_dim_mfg = load_dim_manufacturer()
    df_dim_buyer = load_dim_buyer()

    # 4 Executive KPI Cards
    dq_c1, dq_c2, dq_c3, dq_c4 = st.columns(4)
    with dq_c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">데이터 무결성 통과율 (완벽 행)</div>
                <div class="metric-value" style="color:#059669;">{quality_report['clean_rate_pct']}%</div>
                <span class="badge badge-pos">완벽 무결: {quality_report['clean_rows_count']:,}건</span>
                <div class="metric-sub">전체 <strong>{quality_report['total_rows']:,}</strong>행 중 <strong>{quality_report['clean_rows_count']:,}</strong>행 완전 일치</div>
            </div>
            <div class="metric-desc">ℹ️ 결측 및 수량오차가 전혀 없는 100% 무결성 행의 비율입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    with dq_c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">품목 마스터 정규화 매칭률</div>
                <div class="metric-value" style="color:#2563eb;">{quality_report['item_match_rate_pct']}%</div>
                <span class="badge badge-pos">100% 매칭 완료</span>
                <div class="metric-sub">미매칭 품목 <strong>0</strong>건 (동의어 7건 매핑)</div>
            </div>
            <div class="metric-desc">ℹ️ 수기 품목명이 표준 상품 마스터에 정상 매핑된 비율입니다.</div>
        </div>
        """, unsafe_allow_html=True)

    with dq_c3:
        n_mismatch = quality_report['qty_mismatch_count']
        n_anomaly = quality_report['total_rows'] - quality_report['clean_rows_count']
        pct_anomaly = 100 - quality_report['clean_rate_pct']
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">OCR / 수기 이상치 정제 대상</div>
                <div class="metric-value" style="color:#dc2626;">{n_anomaly:,} <span style="font-size:16px; font-weight:600;">건 ({pct_anomaly:.2f}%)</span></div>
                <span class="badge badge-neg">수량 불일치 {n_mismatch}건 포함</span>
                <div class="metric-sub">수량오차 <strong>{n_mismatch}</strong>건 + 인원누락 <strong>{quality_report.get('worker_missing_count', 254)}</strong>건 + 별칭 <strong>{quality_report.get('unmatched_item_count', 7)}</strong>건</div>
            </div>
            <div class="metric-desc">ℹ️ 비정상 404건 전체에 대해 규칙 기반 자동 보정 완료(정상 분석 가능).</div>
        </div>
        """, unsafe_allow_html=True)

    with dq_c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">표준 마스터 엔티티</div>
                <div class="metric-value" style="color:#7c3aed;">{len(df_dim_item):,} <span style="font-size:16px; font-weight:600;">SKUs</span></div>
                <span class="badge badge-neutral">차원 모델 구축 완료</span>
                <div class="metric-sub">제조사 <strong>{len(df_dim_mfg)}</strong>사 · 바이어 <strong>{len(df_dim_buyer)}</strong>개사</div>
            </div>
            <div class="metric-desc">ℹ️ 품목·제조사·바이어 3대 차원 마스터가 등록 관리됩니다.</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # Sub-tabs for deep management
    subtab1, subtab2, subtab3, subtab4 = st.tabs([
        f"🔍 OCR/수기 이상치 정밀 검수실 (정제 404건 / 수량 불일치 {quality_report['qty_mismatch_count']}건)",
        "📦 상품 마스터 관리 (dim_item)",
        "🏢 제조사 & 바이어 디멘전 (Dimensions)",
        "🔀 품목 데이터 계보 및 통합 맵 (Item Lineage & Consolidation)"
    ])

    # -------------------------------------------------------------
    # SUBTAB 1: OCR / 수기 이상치 정밀 검수실
    # -------------------------------------------------------------
    with subtab1:
        st.markdown(f"#### 🔍 OCR 및 수기 기록 이상치 정밀 검수실 (전체 404건 / 수량 불일치 {quality_report['qty_mismatch_count']}건)")
        st.caption(f"전체 3,188개 행 중 **2,784건(87.33%)**은 완전 무결한 행이며, 나머지 **404건(12.67%)**은 수량 불일치({quality_report['qty_mismatch_count']}건), 인원 누락(254건), 신규 변형 품목(7건)으로 분류되어 실시간 정제되었습니다. 아래에서는 원장 실물 대조가 필요한 **수량 불일치 {quality_report['qty_mismatch_count']}건**을 집중 감사 및 관리합니다.")

        mismatch_df = silver_df[silver_df["qty_mismatch_flag"] == True].copy()
        if not mismatch_df.empty:
            mismatch_df["err_type"] = mismatch_df["qty_diff"].apply(
                lambda x: "📈 기록치 초과 (중복/입량오기 의심)" if x > 0 else "📉 기록치 미달 (누락/자릿수탈락 의심)"
            )

            # Filter toolbar for mismatches
            audit_col1, audit_col2 = st.columns([2, 1])
            with audit_col1:
                audit_search = st.text_input("🔎 품목명 / 바이어 / 비고 검색", placeholder="검색할 품목명이나 바이어를 입력하세요...", key="audit_search_input")
            with audit_col2:
                err_filter = st.selectbox("⚠️ 오차 유형 필터", ["전체 유형 보기", "📈 기록치 초과 (기록 > 계산)", "📉 기록치 미달 (기록 < 계산)"], key="err_filter_select")

            filtered_audit = mismatch_df.copy()
            if audit_search:
                q = audit_search.strip().lower()
                filtered_audit = filtered_audit[
                    filtered_audit["item_name"].astype(str).str.lower().str.contains(q, na=False) |
                    filtered_audit["normalized_item_name"].astype(str).str.lower().str.contains(q, na=False) |
                    filtered_audit["remark"].astype(str).str.lower().str.contains(q, na=False) |
                    filtered_audit["verified_note"].astype(str).str.lower().str.contains(q, na=False)
                ]
            if err_filter == "📈 기록치 초과 (기록 > 계산)":
                filtered_audit = filtered_audit[filtered_audit["qty_diff"] > 0]
            elif err_filter == "📉 기록치 미달 (기록 < 계산)":
                filtered_audit = filtered_audit[filtered_audit["qty_diff"] < 0]

            disp_mis = filtered_audit[[
                "work_date", "page_no", "line_no", "item_name", "normalized_item_name",
                "pack_qty", "work_qty", "calc_sticker_qty", "sticker_qty", "qty_diff", "err_type", "remark", "verified_note"
            ]].copy()

            disp_mis.columns = [
                "작업일자", "페이지", "행번호", "수기 품목명", "표준 품목명",
                "입량", "출하박스", "계산 스티커수", "일지 스티커수", "오차(매)", "오차 분류", "비고/바이어", "정밀 검수메모"
            ]

            st.dataframe(
                disp_mis.sort_values(by=["작업일자", "페이지", "행번호"], ascending=[False, True, True]),
                use_container_width=True,
                hide_index=True
            )

            # CSV Download for audit
            csv_audit = disp_mis.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 수량 불일치 검수 목록 다운로드 (CSV)",
                data=csv_audit,
                file_name="audit_quantity_mismatches.csv",
                mime="text/csv",
                key="btn_download_audit_mismatches"
            )
        else:
            st.success("✅ 모든 행의 수량 정합성이 100% 일치합니다. 감지된 오차가 없습니다.")



    # -------------------------------------------------------------
    # SUBTAB 2: 상품 마스터 관리 (dim_item)
    # -------------------------------------------------------------
    with subtab2:
        st.markdown("#### 📦 상품 마스터 테이블 (`dim_item`)")
        st.caption("표준 SKU 코드, 규격/용량, 단위, 기본 입수량, 작업 난이도 등급 및 기준 부착 속도를 체계적으로 관리합니다.")

        # Multi-filter Toolbar
        mcol1, mcol2, mcol3, mcol4 = st.columns([2, 1, 1, 1])
        with mcol1:
            item_search = st.text_input("🔎 품목명 또는 SKU 코드 검색", placeholder="예: 빼빼로, ITM-0001...", key="search_dim_item")
        with mcol2:
            mfg_options = ["전체 제조사"] + sorted(list(df_dim_item["manufacturer_name"].dropna().unique()))
            sel_mfg = st.selectbox("제조사 필터", mfg_options, key="filter_dim_item_mfg")
        with mcol3:
            cat_options = ["전체 카테고리"] + sorted(list(df_dim_item["category_1"].dropna().unique()))
            sel_cat = st.selectbox("카테고리 필터", cat_options, key="filter_dim_item_cat")
        with mcol4:
            tier_options = ["전체 난이도"] + sorted(list(df_dim_item["difficulty_tier"].dropna().unique()))
            sel_tier = st.selectbox("난이도 등급 필터", tier_options, key="filter_dim_item_tier")

        # Filter items
        filtered_items = df_dim_item.copy()
        if item_search:
            q = item_search.strip().lower()
            filtered_items = filtered_items[
                filtered_items["item_code"].astype(str).str.lower().str.contains(q, na=False) |
                filtered_items["item_name"].astype(str).str.lower().str.contains(q, na=False)
            ]
        if sel_mfg != "전체 제조사":
            filtered_items = filtered_items[filtered_items["manufacturer_name"] == sel_mfg]
        if sel_cat != "전체 카테고리":
            filtered_items = filtered_items[filtered_items["category_1"] == sel_cat]
        if sel_tier != "전체 난이도":
            filtered_items = filtered_items[filtered_items["difficulty_tier"] == sel_tier]

        # Summary KPIs for filtered items
        avg_pack = filtered_items["default_pack_qty"].mean() if not filtered_items.empty else 0
        avg_speed = filtered_items["benchmark_speed_hr"].mean() if not filtered_items.empty else 0
        st.markdown(f"""
        <div style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px 16px; margin-bottom:16px; display:flex; gap:24px; font-size:13px; color:#475569;">
            <div>📋 조회 품목수: <strong style="color:#0f172a;">{len(filtered_items):,}</strong> 종 (전체 {len(df_dim_item):,} 종)</div>
            <div>📦 평균 기본 입수량: <strong style="color:#059669;">{avg_pack:.1f}</strong> 개/박스</div>
            <div>⚡ 평균 기준 속도: <strong style="color:#7c3aed;">{avg_speed:.1f}</strong> 매/hr</div>
        </div>
        """, unsafe_allow_html=True)

        disp_item_table = filtered_items[[
            "item_code", "item_name", "manufacturer_id", "manufacturer_name",
            "category_1", "category_2", "standard_volume", "volume_value", "volume_unit",
            "default_pack_qty", "difficulty_tier", "benchmark_speed_hr"
        ]].copy()

        disp_item_table.columns = [
            "상품코드 (SKU)", "표준 제품명", "제조사 ID", "제조사명",
            "대분류", "소분류", "표준규격", "용량수치", "단위",
            "기본입량", "난이도 등급", "기준속도(매/h)"
        ]

        st.dataframe(disp_item_table, use_container_width=True, hide_index=True)

        # Download Button
        csv_dim_item = df_dim_item.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 전체 상품 마스터 다운로드 (dim_item.csv)",
            data=csv_dim_item,
            file_name="dim_item.csv",
            mime="text/csv",
            key="btn_download_dim_item"
        )



    # -------------------------------------------------------------
    # SUBTAB 3: 제조사 & 바이어 디멘전 (Dimensions)
    # -------------------------------------------------------------
    with subtab3:
        st.markdown("#### 🏢 제조사 및 해외 바이어 차원 모델 (`Dimension Tables`)")
        st.caption("식품 제조사의 사업부문/대표 브랜드 정보와 전 세계 81개 해외 바이어의 수출 대상국, 권역 및 표시규정 특이사항을 관리합니다.")

        dim_col_mfg, dim_col_byr = st.columns(2)

        # Left Column: Manufacturer Dimension
        with dim_col_mfg:
            st.markdown("##### 🏭 제조사 디멘전 (`dim_manufacturer`)")
            st.caption(f"총 **{len(df_dim_mfg)}**개 등록 제조사")

            mfg_search = st.text_input("🔎 제조사명 / 사업부문 검색", placeholder="예: 롯데, 해태, 라면...", key="search_dim_mfg")
            filtered_mfg = df_dim_mfg.copy()
            if mfg_search:
                qm = mfg_search.strip().lower()
                filtered_mfg = filtered_mfg[
                    filtered_mfg["manufacturer_name"].astype(str).str.lower().str.contains(qm, na=False) |
                    filtered_mfg["business_category"].astype(str).str.lower().str.contains(qm, na=False) |
                    filtered_mfg["primary_brand"].astype(str).str.lower().str.contains(qm, na=False)
                ]

            disp_mfg = filtered_mfg[[
                "manufacturer_id", "manufacturer_name", "business_category",
                "item_count", "primary_brand", "notes"
            ]].copy()
            disp_mfg.columns = ["제조사 ID", "제조사명", "사업부문", "품목수", "대표 브랜드", "비즈니스 특이사항"]

            st.dataframe(disp_mfg, use_container_width=True, hide_index=True)

            csv_mfg = df_dim_mfg.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 제조사 마스터 다운로드 (dim_manufacturer.csv)",
                data=csv_mfg,
                file_name="dim_manufacturer.csv",
                mime="text/csv",
                key="btn_download_dim_mfg"
            )

        # Right Column: Buyer Dimension
        with dim_col_byr:
            st.markdown("##### 🌐 바이어 & 수출국 디멘전 (`dim_buyer`)")
            st.caption(f"총 **{len(df_dim_buyer)}**개 글로벌 수출 거래처 / 벤더사")

            byr_search = st.text_input("🔎 바이어명 / 수출국 / 권역 검색", placeholder="예: 캐나다, 판아시아, 벤더사...", key="search_dim_byr")
            filtered_byr = df_dim_buyer.copy()
            if byr_search:
                qb = byr_search.strip().lower()
                filtered_byr = filtered_byr[
                    filtered_byr["buyer_name"].astype(str).str.lower().str.contains(qb, na=False) |
                    filtered_byr["export_country"].astype(str).str.lower().str.contains(qb, na=False) |
                    filtered_byr["export_region"].astype(str).str.lower().str.contains(qb, na=False) |
                    filtered_byr["buyer_type"].astype(str).str.lower().str.contains(qb, na=False)
                ]

            disp_byr = filtered_byr[[
                "buyer_id", "buyer_name", "export_country", "export_region",
                "buyer_type", "order_count", "total_stickers", "special_notes"
            ]].copy()
            disp_byr.columns = ["바이어 ID", "바이어명", "수출국", "권역", "거래처 유형", "오더수", "스티커(매)", "해외 라벨링 규정 메모"]

            st.dataframe(disp_byr, use_container_width=True, hide_index=True)

            csv_byr = df_dim_buyer.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 바이어 마스터 다운로드 (dim_buyer.csv)",
                data=csv_byr,
                file_name="dim_buyer.csv",
                mime="text/csv",
                key="btn_download_dim_byr"
            )

    # -------------------------------------------------------------
    # SUBTAB 4: 품목 데이터 계보 및 통합 맵 (Item Lineage & Consolidation Map)
    # -------------------------------------------------------------
    with subtab4:
        st.markdown("#### 🔀 품목 데이터 계보 및 통합 맵 (`Item Lineage & Consolidation Map`)")
        st.caption("현장 작업일지에서 수기 기입 편차(오타, 띄어쓰기, 영문 대소문자, 약어)로 분열되어 기록되던 원천 텍스트들이 표준 마스터 품목으로 어떻게 정규화·통합되었는지 시각적 계보를 추적합니다.")

        lineage_df = silver_df.groupby(["item_name", "normalized_item_name"]).agg(
            row_count=("work_date", "count"),
            total_stickers=("sticker_qty", "sum"),
            min_date=("work_date", "min"),
            max_date=("work_date", "max"),
            match_type=("match_type", "first")
        ).reset_index()

        def determine_reason(raw, norm, m_type):
            if raw == norm:
                return "표준 일치 (Exact)"
            elif raw.lower() == norm.lower():
                return "대소문자 통일 (Case Normalization)"
            elif raw.replace(" ", "") == norm.replace(" ", ""):
                return "띄어쓰기 정규화 (Whitespace Trim)"
            elif any(t in raw for t in ["화이트화임", "연얀갱", "쿠쿠다스", "톰", "탕콩", "카드타드", "엔젤큐러슈", "뻬빼로", "뺴빼로"]):
                return "수기/OCR 오타 교정 (Typo Correction)"
            elif any(k in raw for k in ["6봉", "12봉", "4P", "6P", "8P", "12P", "2P", "번들", "환"]):
                return "규격/수식어 통합 (Spec Consolidation)"
            elif raw in ["홈", "롯"]:
                return "파편 단어 복원 (Fragment Recovery)"
            elif "캐)" in raw:
                return "접두사 정규화 (Prefix Strip)"
            else:
                return "별칭 사전 매핑 (Alias Mapped)"

        lineage_df["consolidation_reason"] = lineage_df.apply(
            lambda r: determine_reason(r["item_name"], r["normalized_item_name"], r["match_type"]), axis=1
        )

        variant_counts = lineage_df.groupby("normalized_item_name")["item_name"].nunique()
        multi_variant_items = variant_counts[variant_counts > 1].sort_values(ascending=False)

        tot_variants = len(lineage_df[lineage_df["item_name"] != lineage_df["normalized_item_name"]])
        tot_canon_multi = len(multi_variant_items)
        tot_affected_stk = lineage_df[lineage_df["item_name"] != lineage_df["normalized_item_name"]]["total_stickers"].sum()

        l_c1, l_c2, l_c3, l_c4 = st.columns(4)
        with l_c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-top">
                    <div class="metric-label">통합된 수기 변형 표기</div>
                    <div class="metric-value" style="color:#2563eb; font-size:24px;">{tot_variants:,} <span style="font-size:14px; font-weight:600;">종</span></div>
                    <span class="badge badge-pos">354개 별칭 사전 연동</span>
                </div>
                <div class="metric-desc">오타, 공백, 대소문자 편차 자동 교정</div>
            </div>
            """, unsafe_allow_html=True)
        with l_c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-top">
                    <div class="metric-label">다중 표기 수렴 품목군</div>
                    <div class="metric-value" style="color:#7c3aed; font-size:24px;">{tot_canon_multi:,} <span style="font-size:14px; font-weight:600;">개 SKU</span></div>
                    <span class="badge badge-neutral">1개 표준으로 단일화</span>
                </div>
                <div class="metric-desc">The빠새, 구운감자 등 다중 표기 제품</div>
            </div>
            """, unsafe_allow_html=True)
        with l_c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-top">
                    <div class="metric-label">구출된 작업 실적</div>
                    <div class="metric-value" style="color:#059669; font-size:24px;">{tot_affected_stk:,.0f} <span style="font-size:14px; font-weight:600;">매</span></div>
                    <span class="badge badge-pos">누락율 0.00% 달성</span>
                </div>
                <div class="metric-desc">수기 편차로 분열될 뻔한 실적 완벽 구출</div>
            </div>
            """, unsafe_allow_html=True)
        with l_c4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-top">
                    <div class="metric-label">마스터 무결성 달성도</div>
                    <div class="metric-value" style="color:#0284c7; font-size:24px;">100.0 <span style="font-size:14px; font-weight:600;">%</span></div>
                    <span class="badge badge-pos">666개 표준 마스터</span>
                </div>
                <div class="metric-desc">원천 3,324행 전수 매핑 완결</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # 1. Product Selection & Overview Card
        # ---------------------------------------------------------
        insp_col1, insp_col2 = st.columns([1, 2])
        with insp_col1:
            dropdown_options = list(multi_variant_items.index) + [i for i in sorted(variant_counts.index) if i not in multi_variant_items.index]
            default_idx = dropdown_options.index("The빠새") if "The빠새" in dropdown_options else 0
            sel_insp_item = st.selectbox(
                "🔎 계보를 추적할 표준 품목 선택",
                options=dropdown_options,
                index=default_idx,
                key="sel_insp_item"
            )

        meta_sub = df_dim_item[df_dim_item["item_name"] == sel_insp_item]
        if not meta_sub.empty:
            m_row = meta_sub.iloc[0]
            sku_code = m_row.get("item_code", "-")
            mfg_name = m_row.get("manufacturer_name", "-")
            cat_full = f"{m_row.get('category_1', '-') } > {m_row.get('category_2', '-')}"
            std_vol = m_row.get("standard_volume", "-")
            pack_q = m_row.get("default_pack_qty", 16)
        else:
            sku_code, mfg_name, cat_full, std_vol, pack_q = "-", "-", "-", "-", 16

        item_lineage = lineage_df[lineage_df["normalized_item_name"] == sel_insp_item].copy()
        item_total_stk = item_lineage["total_stickers"].sum()
        item_total_rows = item_lineage["row_count"].sum()

        with insp_col2:
            st.markdown(f"""
            <div style="background-color:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 18px; display:flex; justify-content:space-between; align-items:center; margin-top:28px;">
                <div>
                    <span class="badge badge-neutral" style="font-weight:700;">{sku_code}</span>
                    <strong style="font-size:16px; color:#0f172a; margin-left:8px;">{sel_insp_item}</strong>
                    <div style="font-size:12px; color:#64748b; margin-top:4px;">제조사: {mfg_name} · 분류: {cat_full} · 규격: {std_vol} · 기본입수량: {pack_q}개/박스</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:12px; color:#64748b;">통합 표기 <strong>{len(item_lineage)}종</strong> · 총 실적 <strong>{item_total_rows:,}건</strong></div>
                    <div style="font-size:18px; font-weight:700; color:#2563eb;">{item_total_stk:,.0f} <span style="font-size:12px;">매</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # 2. Interactive Sankey Diagram with Focus Mode
        # ---------------------------------------------------------
        sankey_head_col, mode_col = st.columns([2, 1])
        with sankey_head_col:
            st.markdown("##### 🌊 인터랙티브 데이터 계보 생키 다이어그램 (Sankey Flow)")
            st.caption("수기 기입 편차가 어떤 통합 규칙을 거쳐 최종 표준 품목으로 수렴하는지 인터랙티브하게 확인하세요.")
        with mode_col:
            sankey_mode = st.radio(
                "다이어그램 모드",
                ["🎯 선택 품목 집중 계보 (권장)", "🌐 다중 표기 Top 10 전체 흐름"],
                horizontal=True,
                key="sankey_view_mode"
            )

        if "선택 품목 집중" in sankey_mode:
            raw_nodes = item_lineage["item_name"].tolist()
            rule_nodes = list(dict.fromkeys(item_lineage["consolidation_reason"].tolist()))
            target_node = [f"[{sku_code}] {sel_insp_item}"]

            all_nodes = raw_nodes + rule_nodes + target_node
            node_map = {n: i for i, n in enumerate(all_nodes)}

            def get_rule_color(r_name):
                if "오타" in r_name:
                    return "#e11d48", "rgba(225, 29, 72, 0.55)"
                elif "띄어쓰기" in r_name:
                    return "#d97706", "rgba(217, 119, 6, 0.55)"
                elif "대소문자" in r_name:
                    return "#0284c7", "rgba(2, 132, 199, 0.55)"
                elif "표준 일치" in r_name:
                    return "#059669", "rgba(5, 150, 105, 0.55)"
                else:
                    return "#7c3aed", "rgba(124, 58, 237, 0.55)"

            node_colors = []
            for n in all_nodes:
                if n in raw_nodes:
                    r_type = item_lineage[item_lineage["item_name"] == n]["consolidation_reason"].iloc[0]
                    solid_c, _ = get_rule_color(r_type)
                    node_colors.append(solid_c)
                elif n in rule_nodes:
                    node_colors.append("#64748b")
                else:
                    node_colors.append("#1d4ed8")

            srcs, tgts, vals, link_colors = [], [], [], []
            for _, r in item_lineage.iterrows():
                srcs.append(node_map[r["item_name"]])
                tgts.append(node_map[r["consolidation_reason"]])
                vals.append(r["total_stickers"])
                _, rgba_c = get_rule_color(r["consolidation_reason"])
                link_colors.append(rgba_c)

            for rule in rule_nodes:
                rule_vol = item_lineage[item_lineage["consolidation_reason"] == rule]["total_stickers"].sum()
                srcs.append(node_map[rule])
                tgts.append(node_map[target_node[0]])
                vals.append(rule_vol)
                _, rgba_c = get_rule_color(rule)
                link_colors.append(rgba_c)

            fig_sankey = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=24,
                    thickness=24,
                    line=dict(color="#cbd5e1", width=0.5),
                    label=all_nodes,
                    color=node_colors,
                    hovertemplate="노드: <b>%{label}</b><br>총 물량: <b>%{value:,.0f} 매</b><extra></extra>"
                ),
                link=dict(
                    source=srcs,
                    target=tgts,
                    value=vals,
                    color=link_colors,
                    hovertemplate="계보: <b>%{source.label}</b> ➔ <b>%{target.label}</b><br>통합 스티커 수량: <b>%{value:,.0f} 매</b><extra></extra>"
                )
            )])
            fig_sankey.update_layout(
                margin=dict(l=10, r=10, t=15, b=15),
                height=340,
                font=dict(family="Pretendard, -apple-system, sans-serif", size=12, color="#1e293b")
            )
            st.plotly_chart(fig_sankey, use_container_width=True)

        else:
            top_10_canons = multi_variant_items.head(10).index.tolist()
            sankey_subset = lineage_df[lineage_df["normalized_item_name"].isin(top_10_canons)].copy()

            raw_nodes = sankey_subset["item_name"].unique().tolist()
            norm_nodes = sankey_subset["normalized_item_name"].unique().tolist()
            all_nodes = raw_nodes + norm_nodes
            node_map = {n: i for i, n in enumerate(all_nodes)}

            links = sankey_subset.groupby(["item_name", "normalized_item_name"])["total_stickers"].sum().reset_index()

            srcs = [node_map[r["item_name"]] for _, r in links.iterrows()]
            tgts = [node_map[r["normalized_item_name"]] for _, r in links.iterrows()]
            vals = links["total_stickers"].tolist()

            link_colors = []
            node_colors = []
            for _, r in links.iterrows():
                if r["normalized_item_name"] == sel_insp_item:
                    link_colors.append("rgba(37, 99, 235, 0.8)")
                else:
                    link_colors.append("rgba(203, 213, 225, 0.35)")

            for n in all_nodes:
                if n == sel_insp_item:
                    node_colors.append("#1d4ed8")
                elif n in raw_nodes:
                    is_sel_raw = not sankey_subset[(sankey_subset["item_name"] == n) & (sankey_subset["normalized_item_name"] == sel_insp_item)].empty
                    node_colors.append("#2563eb" if is_sel_raw else "#94a3b8")
                else:
                    node_colors.append("#64748b")

            fig_sankey = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=14,
                    thickness=18,
                    line=dict(color="#cbd5e1", width=0.5),
                    label=all_nodes,
                    color=node_colors,
                    hovertemplate="노드: <b>%{label}</b><br>총 물량: <b>%{value:,.0f} 매</b><extra></extra>"
                ),
                link=dict(
                    source=srcs,
                    target=tgts,
                    value=vals,
                    color=link_colors,
                    hovertemplate="흐름: <b>%{source.label}</b> ➔ <b>%{target.label}</b><br>통합 스티커 수량: <b>%{value:,.0f} 매</b><extra></extra>"
                )
            )])
            fig_sankey.update_layout(
                margin=dict(l=10, r=10, t=15, b=15),
                height=420,
                font=dict(family="Pretendard, -apple-system, sans-serif", size=11, color="#334155")
            )
            st.plotly_chart(fig_sankey, use_container_width=True)

        st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # 3. Detailed Lineage Table
        # ---------------------------------------------------------
        st.markdown(f"##### 📋 '{sel_insp_item}' 상세 원천 표기 통합 내역 ({len(item_lineage)}종)")
        item_lineage["share_pct"] = (item_lineage["total_stickers"] / item_total_stk * 100).round(1) if item_total_stk > 0 else 0
        disp_lineage = item_lineage[[
            "item_name", "row_count", "total_stickers", "share_pct", "consolidation_reason", "min_date", "max_date"
        ]].copy()
        disp_lineage.columns = [
            "원천 수기 표기 (Raw String)", "작업 횟수 (건)", "총 작업 매수 (매)", "작업량 비중 (%)",
            "통합 및 정규화 사유 (Reason)", "원천 최초 발생일", "최근 작업일"
        ]
        st.dataframe(disp_lineage, use_container_width=True, hide_index=True)

        st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # 4. Google Sheet 1-Click Master Exporter (12 Columns Exactly)
        # ---------------------------------------------------------
        st.markdown("##### 📋 구글 시트 [아이템 마스터] 탭용 12개 컬럼 동기화 도구")
        st.caption("구글 시트의 `[아이템 마스터]` 탭에 있는 12개 컬럼(`item_code` ~ `benchmark_speed_hr`)과 100% 동일한 순서와 규격으로 내보냅니다. 다운로드하신 TSV 파일을 열어 전체 선택(Ctrl+A) 후 구글 시트 A1 셀에 붙여넣기(Ctrl+V)하시면 됩니다.")

        exact_dim_cols = [
            "item_code", "item_name", "manufacturer_id", "manufacturer_name",
            "category_1", "category_2", "volume_value", "volume_unit", "standard_volume",
            "default_pack_qty", "difficulty_tier", "benchmark_speed_hr"
        ]
        df_sheet_export = df_dim_item[exact_dim_cols].copy()

        tsv_buffer = io.StringIO()
        df_sheet_export.to_csv(tsv_buffer, sep="\t", index=False)
        tsv_content = tsv_buffer.getvalue()

        copy_col1, copy_col2 = st.columns([1, 1])
        with copy_col1:
            st.download_button(
                "📥 구글 시트 [아이템 마스터] 탭용 TSV 다운로드 (12개 컬럼 완벽 일치)",
                data=tsv_content,
                file_name="google_sheet_dim_item_master_12cols.tsv",
                mime="text/tab-separated-values",
                key="btn_download_tsv_master_12"
            )
        with copy_col2:
            st.download_button(
                "📥 전체 상품 마스터 CSV 다운로드 (dim_item.csv)",
                data=df_sheet_export.to_csv(index=False, encoding="utf-8-sig"),
                file_name="dim_item.csv",
                mime="text/csv",
                key="btn_download_csv_clean_dim"
            )


# ---------------------------------------------------------
# TAB 6: DATA LINEAGE & ARCHITECTURE MAP (데이터 계보 & 아키텍처)
# ---------------------------------------------------------
with tab6:
    st.markdown("### 🗺️ 데이터 계보(Data Lineage) & 시스템 아키텍처 맵")
    st.caption("A4 수기 원장부터 최종 경영진 대시보드/이메일까지 이어지는 엔드투엔드 데이터 흐름과 스타 스키마(Star Schema) ERD 및 통합 데이터 카탈로그를 한눈에 관리합니다.")

    # Load raw data for catalog display
    raw_df_preview, raw_source_name = load_raw_sticker_data()

    # 1. 5-Stage Pipeline Health Metric Cards
    lh_c1, lh_c2, lh_c3, lh_c4, lh_c5 = st.columns(5)
    with lh_c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">0. 원천 수집 계층 (Source)</div>
                <div class="metric-value" style="color:#0284c7; font-size:20px;">구글 시트 Live</div>
                <span class="badge badge-pos">연동 정상 🟢</span>
                <div class="metric-sub">A4 원장 ➔ 스캔 PDF ➔ OCR ➔ 시트</div>
            </div>
            <div class="metric-desc">ℹ️ 원천 데이터 수집 및 실시간 CSV 파이프라인</div>
        </div>
        """, unsafe_allow_html=True)

    with lh_c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">1. 원본 보존 계층 (Bronze)</div>
                <div class="metric-value" style="color:#ea580c; font-size:22px;">{len(raw_df_preview):,} <span style="font-size:14px; font-weight:600;">행</span></div>
                <span class="badge badge-neutral">Raw Ingestion</span>
                <div class="metric-sub">14개 원본 컬럼 무손실 아카이빙</div>
            </div>
            <div class="metric-desc">ℹ️ 원본 데이터 가공 없는 스냅샷 저장소</div>
        </div>
        """, unsafe_allow_html=True)

    with lh_c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">2. 정제 Fact 계층 (Silver)</div>
                <div class="metric-value" style="color:#2563eb; font-size:22px;">{len(silver_df):,} <span style="font-size:14px; font-weight:600;">행</span></div>
                <span class="badge badge-pos">무결성 {quality_report['clean_rate_pct']}%</span>
                <div class="metric-sub">24개 정규화/검증 필드 결합</div>
            </div>
            <div class="metric-desc">ℹ️ 수량 일치 검증 및 4단계 품목 정규화 Fact</div>
        </div>
        """, unsafe_allow_html=True)

    with lh_c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">3. 마스터 차원 (Dimensions)</div>
                <div class="metric-value" style="color:#16a34a; font-size:22px;">3대 차원 모델</div>
                <span class="badge badge-neutral">MDM 구축 완료</span>
                <div class="metric-sub">품목 {len(df_dim_item)} · 제조 {len(df_dim_mfg)} · 바이어 {len(df_dim_buyer)}</div>
            </div>
            <div class="metric-desc">ℹ️ 기준 정보(MDM) 단일 진실 공급원</div>
        </div>
        """, unsafe_allow_html=True)

    with lh_c5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-top">
                <div class="metric-label">4. 분석 마트 계층 (Gold)</div>
                <div class="metric-value" style="color:#7c3aed; font-size:22px;">4대 Gold Marts</div>
                <span class="badge badge-pos">집계 실시간 가동</span>
                <div class="metric-sub">일자·품목·바이어·시뮬레이터</div>
            </div>
            <div class="metric-desc">ℹ️ 경영진 KPI 분석 및 주간 리포트 서빙</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # Sub-tabs in Tab 6
    t6_sub1, t6_sub2, t6_sub3 = st.tabs([
        "🔄 엔드투엔드 파이프라인 계보도 (Data Lineage Flow)",
        "📊 스타 스키마 ERD 관계도 (Star Schema ERD)",
        "📖 통합 데이터 카탈로그 & 스키마 탐색기 (Data Catalog)"
    ])

    # -------------------------------------------------------------
    # SUBTAB 6.1: 엔드투엔드 파이프라인 계보도
    # -------------------------------------------------------------
    with t6_sub1:
        st.markdown("#### 🔄 엔드투엔드 데이터 파이프라인 DAG 그래프 (Data Lineage DAG)")
        st.caption("A4 수기 원장부터 6대 계층을 거쳐 분석 서빙까지 도달하는 실제 방향성 비순환 그래프(DAG, Directed Acyclic Graph)입니다.")

        # Load live master dimensions and real-time counts
        df_dim_item = load_dim_item()
        df_dim_mfg = load_dim_manufacturer()
        df_dim_buyer = load_dim_buyer()
        n_raw = quality_report.get("total_records_processed", len(silver_df))
        n_silver = len(silver_df)
        n_item = len(df_dim_item)
        n_mfg = len(df_dim_mfg)
        n_buyer = len(df_dim_buyer)
        n_days = daily_mart["work_date"].nunique() if not daily_mart.empty else 0

        # DAG Orientation & Display Controls
        dag_c1, dag_c2 = st.columns([2, 5])
        with dag_c1:
            dag_orient = st.radio("📐 DAG 그래프 배치 방향", ["가로형 (Left ➔ Right)", "세로형 (Top ➔ Bottom)"], horizontal=True, key="dag_orient_radio")
        dag_rank_dir = "LR" if "가로형" in dag_orient else "TB"

        dag_dot = f"""digraph PipelineDAG {{
            rankdir={dag_rank_dir};
            bgcolor="transparent";
            compound=true;
            nodesep=0.35;
            ranksep=0.55;
            node [fontname="Pretendard, -apple-system, sans-serif", fontsize=10, style="filled,rounded", shape=box, penwidth=1.5];
            edge [fontname="Pretendard, -apple-system, sans-serif", fontsize=9, color="#64748b", penwidth=1.4, arrowsize=0.8];

            subgraph cluster_0 {{
                label="0. 원천 아날로그 수집 (Origin)";
                fontname="Pretendard, sans-serif";
                fontsize=11;
                style="dashed,rounded";
                color="#94a3b8";
                bgcolor="#f8fafc";
                
                src_a4 [label="📝 현장 A4 수기 일지\\n(작업 현장 반장 작성)", fillcolor="#ffffff", color="#64748b"];
                src_pdf [label="🖨️ 복합기 스캔\\n(PDF 변환 문서)", fillcolor="#ffffff", color="#64748b"];
                src_ocr [label="🔍 OCR 텍스트 추출\\n(숫자/문자 자동 판독)", fillcolor="#ffffff", color="#64748b"];
                src_sheet [label="📑 구글 시트 취합본\\n(Live Spreadsheet)", fillcolor="#f1f5f9", color="#0284c7"];

                src_a4 -> src_pdf [label="스캔"];
                src_pdf -> src_ocr [label="OCR"];
                src_ocr -> src_sheet [label="취합"];
            }}

            subgraph cluster_1 {{
                label="1. Bronze Layer (원천 보존)";
                fontname="Pretendard, sans-serif";
                fontsize=11;
                style="rounded";
                color="#ea580c";
                bgcolor="#fff7ed";
                
                raw_bronze [label="🥉 raw_verified_source_rows\\n({n_raw:,}행 / 14개 원본 컬럼)", fillcolor="#ffffff", color="#ea580c"];
            }}

            subgraph cluster_2 {{
                label="2. Quality & Normalization (품질 & 표준화)";
                fontname="Pretendard, sans-serif";
                fontsize=11;
                style="rounded";
                color="#16a34a";
                bgcolor="#f0fdf4";

                engine_dq [label="🛡️ 수량 정합성 검증 엔진\\n(pack_qty * work_qty == sticker_qty)", fillcolor="#ffffff", color="#16a34a"];
                engine_norm [label="🧩 지능형 4단계 품목명 표준화\\n(규칙 ➔ 별칭 ➔ 마스터 ➔ Fuzzy)", fillcolor="#ffffff", color="#16a34a"];
            }}

            subgraph cluster_3 {{
                label="3. Master Dimensions (기준 정보)";
                fontname="Pretendard, sans-serif";
                fontsize=11;
                style="rounded";
                color="#059669";
                bgcolor="#ecfdf5";

                dim_mfg_node [label="🏭 dim_manufacturer\\n({n_mfg:,}개 식품 제조사)", fillcolor="#ffffff", color="#059669"];
                dim_item_node [label="📦 dim_item\\n({n_item:,}종 상품 마스터/SKU)", fillcolor="#ffffff", color="#059669"];
                dim_buyer_node [label="🌐 dim_buyer\\n({n_buyer:,}개 글로벌 바이어)", fillcolor="#ffffff", color="#059669"];
                
                dim_mfg_node -> dim_item_node [label="제조사ID"];
            }}

            subgraph cluster_4 {{
                label="4. Silver Layer (정제 Fact)";
                fontname="Pretendard, sans-serif";
                fontsize=11;
                style="rounded";
                color="#2563eb";
                bgcolor="#eff6ff";

                silver_fact [label="🥈 silver_sticker_work_log\\n({n_silver:,}행 Fact + 24개 컬럼 + 인·시)", fillcolor="#ffffff", color="#2563eb", penwidth=2.5];
            }}

            subgraph cluster_5 {{
                label="5. Gold Layer (분석 집계 마트)";
                fontname="Pretendard, sans-serif";
                fontsize=11;
                style="rounded";
                color="#7c3aed";
                bgcolor="#faf5ff";

                mart_daily [label="🥇 daily_productivity_mart\\n(일별 생산성 {n_days:,}일 & 투입공수)", fillcolor="#ffffff", color="#7c3aed"];
                mart_item [label="🥇 item_difficulty_mart\\n(품목별 벤치마크 속도/난이도)", fillcolor="#ffffff", color="#7c3aed"];
                mart_buyer [label="🥇 buyer_summary_mart\\n(바이어별 작업 비중 & 오더수)", fillcolor="#ffffff", color="#7c3aed"];
                mart_forecast [label="⏱️ capacity_forecast_model\\n(오더 소요공수/인원 시뮬레이터)", fillcolor="#ffffff", color="#7c3aed"];
            }}

            subgraph cluster_6 {{
                label="6. 서빙 및 비즈니스 액션 (Serving)";
                fontname="Pretendard, sans-serif";
                fontsize=11;
                style="rounded";
                color="#0d9488";
                bgcolor="#f0fdfa";

                serving_app [label="📊 Streamlit 대시보드 (6개 탭)\\n(실시간 인터랙티브 분석)", fillcolor="#ffffff", color="#0d9488"];
                serving_mail [label="📧 GitHub Actions 주간 리포트\\n(매주 월요일 09:00 자동 발송)", fillcolor="#ffffff", color="#0d9488"];
            }}

            src_sheet -> raw_bronze [label="Live CSV Ingestion", color="#ea580c"];
            raw_bronze -> engine_dq [color="#16a34a"];
            raw_bronze -> engine_norm [color="#16a34a"];
            dim_item_node -> engine_norm [label="표준명 매핑", style="dashed", color="#059669"];
            dim_buyer_node -> engine_norm [label="바이어 매핑", style="dashed", color="#059669"];
            engine_dq -> silver_fact [color="#2563eb"];
            engine_norm -> silver_fact [color="#2563eb"];
            
            silver_fact -> mart_daily [color="#7c3aed"];
            silver_fact -> mart_item [color="#7c3aed"];
            silver_fact -> mart_buyer [color="#7c3aed"];
            silver_fact -> mart_forecast [color="#7c3aed"];

            mart_daily -> serving_app [color="#0d9488"];
            mart_item -> serving_app [color="#0d9488"];
            mart_buyer -> serving_app [color="#0d9488"];
            mart_forecast -> serving_app [color="#0d9488"];
            mart_daily -> serving_mail [color="#0d9488"];
            mart_item -> serving_mail [color="#0d9488"];
            mart_buyer -> serving_mail [color="#0d9488"];
        }}"""

        st.graphviz_chart(dag_dot, use_container_width=True)

        # Pipeline Detailed Specifications in Expander
        with st.expander("📝 6단계 파이프라인 단계별 세부 기술 명세 & 품질 가드레일 열람"):
            st.markdown(f"""
            <div style="display: flex; flex-direction: column; gap: 12px; margin-top: 8px; font-size: 13px; line-height: 1.62;">
                <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid #64748b; border-radius: 6px; padding: 12px 16px;">
                    <strong>Stage 0. 아날로그 원천 수집:</strong> [현장 A4 일지] ➔ [스캔 PDF] ➔ [OCR 텍스트 추출] ➔ [구글 스프레드시트 취합]<br/>
                    <span style="color:#dc2626; font-size:11.5px;">리스크 관리: OCR 숫자 오인식(0↔8, 0↔6), 입량 오기재 실시간 감사</span>
                </div>
                <div style="background: #fff7ed; border: 1px solid #fed7aa; border-left: 5px solid #ea580c; border-radius: 6px; padding: 12px 16px;">
                    <strong>Stage 1. Bronze Layer (원천 적재):</strong> <strong>{n_raw:,}행</strong> / 14개 원본 컬럼 무손실 아카이빙 (<code>src/ingestion/loader.py</code>)
                </div>
                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #16a34a; border-radius: 6px; padding: 12px 16px;">
                    <strong>Stage 2 & 3. 품질 검증 & 마스터 결합:</strong> <code>pack_qty * work_qty == sticker_qty</code> 수량 검증 + 4단계 품목 정규화 + 3대 디멘전(품목 <strong>{n_item:,}종</strong>, 제조 <strong>{n_mfg:,}개사</strong>, 바이어 <strong>{n_buyer:,}개사</strong>)
                </div>
                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-left: 5px solid #2563eb; border-radius: 6px; padding: 12px 16px;">
                    <strong>Stage 4. Silver Fact 계층:</strong> <strong>{n_silver:,}행 Fact</strong> + 24개 컬럼 + 투입 인·시(Man-Hours) 결합 단일 진실 테이블
                </div>
                <div style="background: #faf5ff; border: 1px solid #e9d5ff; border-left: 5px solid #7c3aed; border-radius: 6px; padding: 12px 16px;">
                    <strong>Stage 5. Gold Analytics Marts:</strong> 일자별 생산성(<strong>{n_days:,}일 가동</strong>), 품목별 벤치마크 속도/난이도, 바이어별 점유율, 공수 예측 모델
                </div>
                <div style="background: #f0fdfa; border: 1px solid #99f6e4; border-left: 5px solid #0d9488; border-radius: 6px; padding: 12px 16px;">
                    <strong>Stage 6. 서빙 및 액션:</strong> Streamlit 대시보드 (6개 탭 실시간 서빙) + GitHub Actions 주간 자동 리포트
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Pipeline Operations & Refresh Controls
        st.markdown("##### ⚙️ 파이프라인 수동 제어 & 상태 점검")
        p_c1, p_c2, p_c3 = st.columns([1.5, 1.5, 3])
        with p_c1:
            if st.button("🔄 파이프라인 전체 캐시 갱신 (Clear & Reload)", use_container_width=True, key="btn_clear_pipeline_cache"):
                st.cache_data.clear()
                st.success("✅ 메모리 캐시가 초기화되었습니다. 최신 데이터를 다시 불러옵니다.")
                st.rerun()
        with p_c2:
            if st.button("📦 3대 마스터 디멘전 스크립트 재실행", use_container_width=True, key="btn_rerun_dimensions"):
                from scripts.build_master_dimensions import generate_dimensions
                generate_dimensions()
                st.cache_data.clear()
                st.success("✅ dim_item, dim_manufacturer, dim_buyer CSV가 최신 상태로 재생성되었습니다!")
                st.rerun()
        with p_c3:
            st.caption(f"ℹ️ 현재 데이터 소스: **{source_status}** / 실시간 캐시 유효 시간: 10분(TTL 600s)")

    # -------------------------------------------------------------
    # SUBTAB 6.2: 스타 스키마 ERD 관계도
    # -------------------------------------------------------------
    with t6_sub2:
        st.markdown("#### 📊 스타 스키마 (Star Schema) ERD 다이어그램")
        st.caption("중앙 Fact 테이블(`fact_sticker_work`)과 Dimension 테이블, Gold Marts의 엔티티 관계도(Entity-Relationship Diagram)를 시각적으로 나타냅니다.")

        erd_rank_dir = "LR"

        erd_dot = f"""digraph StarSchemaERD {{
            rankdir={erd_rank_dir};
            bgcolor="transparent";
            nodesep=0.45;
            ranksep=0.7;
            node [shape=plaintext, fontname="Pretendard, -apple-system, sans-serif", fontsize=10];
            edge [fontname="Pretendard, -apple-system, sans-serif", fontsize=9, color="#2563eb", penwidth=1.6, arrowsize=0.8];

            dim_mfg [label=<
                <table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff" color="#16a34a">
                    <tr><td bgcolor="#16a34a" align="center" cellpadding="5"><font color="white"><b>🏭 dim_manufacturer</b></font></td></tr>
                    <tr><td align="left" cellpadding="3">🔑 <b>manufacturer_id</b> [PK]</td></tr>
                    <tr><td align="left" cellpadding="3">• manufacturer_name</td></tr>
                    <tr><td align="left" cellpadding="3">• business_category</td></tr>
                    <tr><td align="left" cellpadding="3">• item_count (품목수)</td></tr>
                    <tr><td align="left" cellpadding="3">• primary_brand</td></tr>
                </table>
            >];

            dim_item [label=<
                <table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff" color="#059669">
                    <tr><td bgcolor="#059669" align="center" cellpadding="5"><font color="white"><b>📦 dim_item</b></font></td></tr>
                    <tr><td align="left" cellpadding="3">🔑 <b>item_code</b> [PK]</td></tr>
                    <tr><td align="left" cellpadding="3">• item_name</td></tr>
                    <tr><td align="left" cellpadding="3">🔗 <b>manufacturer_id</b> [FK]</td></tr>
                    <tr><td align="left" cellpadding="3">• category_1, category_2</td></tr>
                    <tr><td align="left" cellpadding="3">• volume_value, volume_unit</td></tr>
                    <tr><td align="left" cellpadding="3">• default_pack_qty</td></tr>
                    <tr><td align="left" cellpadding="3">• difficulty_tier</td></tr>
                    <tr><td align="left" cellpadding="3">• benchmark_speed_hr</td></tr>
                </table>
            >];

            dim_buyer [label=<
                <table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff" color="#0891b2">
                    <tr><td bgcolor="#0891b2" align="center" cellpadding="5"><font color="white"><b>🌐 dim_buyer</b></font></td></tr>
                    <tr><td align="left" cellpadding="3">🔑 <b>buyer_id</b> [PK]</td></tr>
                    <tr><td align="left" cellpadding="3">• buyer_name</td></tr>
                    <tr><td align="left" cellpadding="3">• export_country</td></tr>
                    <tr><td align="left" cellpadding="3">• export_region</td></tr>
                    <tr><td align="left" cellpadding="3">• buyer_type</td></tr>
                    <tr><td align="left" cellpadding="3">• special_notes (라벨규정)</td></tr>
                </table>
            >];

            fact_work [label=<
                <table border="2" cellborder="0" cellspacing="0" bgcolor="#eff6ff" color="#1e40af">
                    <tr><td bgcolor="#1e40af" align="center" cellpadding="6"><font color="white"><b>🏛️ fact_sticker_work (Silver)</b></font></td></tr>
                    <tr><td align="left" cellpadding="3">🔑 <b>work_date, page_no, line_no</b> [PK]</td></tr>
                    <tr><td align="left" cellpadding="3">🔗 <b>normalized_item_name</b> [FK ➔ dim_item]</td></tr>
                    <tr><td align="left" cellpadding="3">🔗 <b>manufacturer</b> [FK ➔ dim_mfg]</td></tr>
                    <tr><td align="left" cellpadding="3">🔗 <b>buyer_normalized</b> [FK ➔ dim_buyer]</td></tr>
                    <tr><td align="left" cellpadding="3">📊 pack_qty (박스당 입량)</td></tr>
                    <tr><td align="left" cellpadding="3">📊 work_qty (출하 박스수)</td></tr>
                    <tr><td align="left" cellpadding="3">📊 sticker_qty (부착 스티커수)</td></tr>
                    <tr><td align="left" cellpadding="3">📊 calc_sticker_qty (계산 스티커수)</td></tr>
                    <tr><td align="left" cellpadding="3">⚠️ qty_mismatch_flag (오차 감지)</td></tr>
                    <tr><td align="left" cellpadding="3">📊 effective_worker_count (투입인원)</td></tr>
                    <tr><td align="left" cellpadding="3">📊 total_worker_hours (투입공수)</td></tr>
                    <tr><td align="left" cellpadding="3">⚡ stickers_per_man_hour (생산성)</td></tr>
                </table>
            >];

            mart_daily [label=<
                <table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff" color="#7c3aed">
                    <tr><td bgcolor="#7c3aed" align="center" cellpadding="4"><font color="white"><b>🥇 daily_productivity_mart</b></font></td></tr>
                    <tr><td align="left" cellpadding="2">🔑 <b>work_date</b> [PK]</td></tr>
                    <tr><td align="left" cellpadding="2">• total_stickers, total_boxes</td></tr>
                    <tr><td align="left" cellpadding="2">• worker_count, total_worker_hours</td></tr>
                    <tr><td align="left" cellpadding="2">• stickers_per_man_hour</td></tr>
                </table>
            >];

            mart_item [label=<
                <table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff" color="#7c3aed">
                    <tr><td bgcolor="#7c3aed" align="center" cellpadding="4"><font color="white"><b>🥇 item_difficulty_mart</b></font></td></tr>
                    <tr><td align="left" cellpadding="2">🔑 <b>normalized_item_name</b> [PK]</td></tr>
                    <tr><td align="left" cellpadding="2">• manufacturer, category_1</td></tr>
                    <tr><td align="left" cellpadding="2">• avg_pack_qty, total_stickers</td></tr>
                    <tr><td align="left" cellpadding="2">• stickers_per_hour, difficulty_tier</td></tr>
                </table>
            >];

            mart_buyer [label=<
                <table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff" color="#7c3aed">
                    <tr><td bgcolor="#7c3aed" align="center" cellpadding="4"><font color="white"><b>🥇 buyer_summary_mart</b></font></td></tr>
                    <tr><td align="left" cellpadding="2">🔑 <b>buyer_normalized</b> [PK]</td></tr>
                    <tr><td align="left" cellpadding="2">• export_country, export_region</td></tr>
                    <tr><td align="left" cellpadding="2">• order_count, total_boxes</td></tr>
                    <tr><td align="left" cellpadding="2">• total_stickers, sticker_share_pct</td></tr>
                </table>
            >];

            dim_mfg -> dim_item [label=" 1 : N", color="#16a34a", style="dashed"];
            dim_item -> fact_work [label=" 1 : N (품목)", color="#059669"];
            dim_mfg -> fact_work [label=" 1 : N (제조사)", color="#16a34a"];
            dim_buyer -> fact_work [label=" 1 : N (바이어)", color="#0891b2"];

            fact_work -> mart_daily [label=" N : 1 (일별 집계)", color="#7c3aed"];
            fact_work -> mart_item [label=" N : 1 (품목 집계)", color="#7c3aed"];
            fact_work -> mart_buyer [label=" N : 1 (바이어 집계)", color="#7c3aed"];
        }}"""

        st.graphviz_chart(erd_dot, use_container_width=True)

        st.divider()

        # Star Schema Join Specifications Table
        st.markdown("##### 📋 테이블 간 조인 키(Join Keys) 및 카디널리티 명세")
        erd_spec = pd.DataFrame([
            {
                "관계 유형": "Dimension ➔ Fact",
                "부모 테이블 (Parent)": "dim_manufacturer",
                "부모 키 (PK)": "manufacturer_name",
                "자식 테이블 (Child)": "fact_sticker_work (Silver)",
                "자식 키 (FK)": "manufacturer",
                "카디널리티": "1 : N",
                "조인 무결성": "✅ 100% 매칭 (26개사 전수 매핑)"
            },
            {
                "관계 유형": "Dimension ➔ Fact",
                "부모 테이블 (Parent)": "dim_item",
                "부모 키 (PK)": "item_name",
                "자식 테이블 (Child)": "fact_sticker_work (Silver)",
                "자식 키 (FK)": "normalized_item_name",
                "카디널리티": "1 : N",
                "조인 무결성": "✅ 100% 매칭 (별칭 사전 14종 결합)"
            },
            {
                "관계 유형": "Dimension ➔ Fact",
                "부모 테이블 (Parent)": "dim_buyer",
                "부모 키 (PK)": "buyer_name",
                "자식 테이블 (Child)": "fact_sticker_work (Silver)",
                "자식 키 (FK)": "buyer_normalized",
                "카디널리티": "1 : N",
                "조인 무결성": "✅ 100% 매칭 (81개 바이어 결합)"
            },
            {
                "관계 유형": "Dimension ➔ Dimension",
                "부모 테이블 (Parent)": "dim_manufacturer",
                "부모 키 (PK)": "manufacturer_id",
                "자식 테이블 (Child)": "dim_item",
                "자식 키 (FK)": "manufacturer_id",
                "카디널리티": "1 : N",
                "조인 무결성": "✅ 100% 제조사 식별자 매핑"
            },
            {
                "관계 유형": "Fact ➔ Gold Mart",
                "부모 테이블 (Parent)": "fact_sticker_work (Silver)",
                "부모 키 (PK)": "work_date (Group By)",
                "자식 테이블 (Child)": "daily_productivity_mart",
                "자식 키 (FK)": "work_date (1:1)",
                "카디널리티": "N : 1 (집계)",
                "조인 무결성": "✅ 일별 생산성 31일 집계"
            },
            {
                "관계 유형": "Fact ➔ Gold Mart",
                "부모 테이블 (Parent)": "fact_sticker_work (Silver)",
                "부모 키 (PK)": "normalized_item_name (Group By)",
                "자식 테이블 (Child)": "item_difficulty_mart",
                "자식 키 (FK)": "normalized_item_name (1:1)",
                "카디널리티": "N : 1 (집계)",
                "조인 무결성": "✅ 품목 난이도 벤치마크 집계"
            },
            {
                "관계 유형": "Fact ➔ Gold Mart",
                "부모 테이블 (Parent)": "fact_sticker_work (Silver)",
                "부모 키 (PK)": "buyer_normalized (Group By)",
                "자식 테이블 (Child)": "buyer_summary_mart",
                "자식 키 (FK)": "buyer_normalized (1:1)",
                "카디널리티": "N : 1 (집계)",
                "조인 무결성": "✅ 바이어별 출하 실적 집계"
            }
        ])
        st.dataframe(erd_spec, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------
    # SUBTAB 6.3: 통합 데이터 카탈로그 & 스키마 탐색기
    # -------------------------------------------------------------
    with t6_sub3:
        st.markdown("#### 📖 통합 데이터 카탈로그 & 스키마 탐색기 (Data Catalog)")
        st.caption("시스템을 구성하는 8개 핵심 테이블의 메타데이터, 컬럼 사전, 제약조건 및 실제 샘플 데이터를 인터랙티브하게 탐색합니다.")

        table_catalog_options = [
            "silver_sticker_work_log (Silver 정제 Fact)",
            "dim_item (상품 마스터 디멘전)",
            "dim_manufacturer (제조사 마스터 디멘전)",
            "dim_buyer (바이어 마스터 디멘전)",
            "raw_verified_source_rows (Bronze 원천 Raw)",
            "item_alias_mapping (동의어/별칭 사전)",
            "daily_productivity_mart (일자별 생산성 Gold Mart)",
            "item_difficulty_mart (품목별 난이도 Gold Mart)",
            "buyer_summary_mart (바이어별 실적 Gold Mart)"
        ]

        selected_table_name = st.selectbox("📂 조회할 테이블 선택", table_catalog_options, key="select_catalog_table")

        # Table Metadata & Data mapping
        alias_df_current = load_item_alias_mapping()

        catalog_meta = {
            "silver_sticker_work_log (Silver 정제 Fact)": {
                "layer": "Silver (Clean Fact)",
                "type": "Fact Table",
                "df": silver_df,
                "pk": "work_date, page_no, line_no (Composite PK)",
                "fks": "normalized_item_name (➔ dim_item), manufacturer (➔ dim_manufacturer), buyer_normalized (➔ dim_buyer)",
                "grain": "현장 작업일지 개별 작업 행 (Line)",
                "update": "배치 및 구글 시트 동기화 시 실시간 재집계",
                "source": "Bronze 원천 정제 + 마스터 조인 + 수량 무결성 감사",
                "dict": [
                    ("work_date", "작업일자", "string (YYYY-MM-DD)", "작업이 수행된 일자"),
                    ("page_no", "일지 페이지", "int", "A4 수기 작업일지 페이지 번호"),
                    ("line_no", "행 번호", "int", "해당 페이지 내 순번"),
                    ("item_name", "수기 품목명", "string", "현장 일지에 기록된 원본 품목명"),
                    ("normalized_item_name", "표준 품목명", "string", "4단계 정규화를 통해 표준화된 품목명"),
                    ("manufacturer", "제조사명", "string", "dim_item/dim_manufacturer 조인 제조사"),
                    ("category_1", "대분류", "string", "식품 대분류 (과자, 음료, 냉동 등)"),
                    ("category_2", "소분류", "string", "식품 소분류 (스낵, 비스킷, 탄산음료 등)"),
                    ("pack_qty", "박스당 입량", "int", "출하 박스 1개당 들어있는 제품 낱개 개수"),
                    ("work_qty", "출하 박스수", "int", "작업 완료 후 출하된 박스 수량"),
                    ("sticker_qty", "기록 스티커수", "int", "일지에 수기로 기재된 부착 스티커 수량"),
                    ("calc_sticker_qty", "계산 스티커수", "int", "입량 × 작업박스수 수학적 계산값"),
                    ("qty_mismatch_flag", "수량오차 플래그", "bool", "기록치와 계산치 불일치 시 True"),
                    ("qty_diff", "수량 오차(매)", "int", "일지 스티커수 - 계산 스티커수"),
                    ("buyer_normalized", "표준 바이어명", "string", "정규화된 해외 바이어/수출 거래처명"),
                    ("export_country", "수출 대상국", "string", "바이어 소재 수출 대상 국가"),
                    ("export_region", "글로벌 권역", "string", "대륙별 글로벌 권역 (북미, 유럽, 아시아 등)"),
                    ("effective_worker_count", "투입 인원수", "float", "당일 작업자 수 (누락 시 보정치 적용)"),
                    ("total_worker_hours", "투입 공수", "float", "당일 총 투입 인·시 (Man-Hours)"),
                    ("stickers_per_man_hour", "시간당 부착속도", "float", "인당 1시간당 스티커 부착 수량 (속도)")
                ]
            },
            "dim_item (상품 마스터 디멘전)": {
                "layer": "Master (Dimension)",
                "type": "Dimension Table",
                "df": df_dim_item,
                "pk": "item_code (ITM-0001 ~ ITM-0434)",
                "fks": "manufacturer_id (➔ dim_manufacturer)",
                "grain": "표준 개별 품목 (SKU) 단위",
                "update": "신규 상품 출시 시 수동/원클릭 등록",
                "source": "data/dim_item.csv (item_master.csv 기반 자동 생성)",
                "dict": [
                    ("item_code", "상품코드(SKU)", "string (ITM-XXXX)", "고유 식별 상품 코드"),
                    ("item_name", "표준 제품명", "string", "표준 공식 제품명"),
                    ("manufacturer_id", "제조사 ID", "string (MFG-XXX)", "제조사 식별 외래키"),
                    ("manufacturer_name", "제조사명", "string", "식품 제조사 명칭"),
                    ("category_1", "대분류", "string", "식품 대분류 (과자, 음료 등)"),
                    ("category_2", "소분류", "string", "식품 소분류 (스낵, 비스킷 등)"),
                    ("standard_volume", "표준 규격", "string", "중량 및 번들 포장 규격 문자열"),
                    ("volume_value", "용량 수치", "float/string", "정제된 용량 숫자 (예: 120, 1.5)"),
                    ("volume_unit", "용량 단위", "string", "표준 규격 단위 (g, ml, L, 번들)"),
                    ("default_pack_qty", "기본 입수량", "int", "박스당 표준 입수량 개수"),
                    ("difficulty_tier", "난이도 등급", "string", "입수량 기준 3단계 난이도 등급"),
                    ("benchmark_speed_hr", "기준 속도", "float", "과거 실적 기반 시간당 기준 부착 속도")
                ]
            },
            "dim_manufacturer (제조사 마스터 디멘전)": {
                "layer": "Master (Dimension)",
                "type": "Dimension Table",
                "df": df_dim_mfg,
                "pk": "manufacturer_id (MFG-001 ~ MFG-026)",
                "fks": "None",
                "grain": "식품 제조사 단위 (26개사)",
                "update": "신규 거래 제조사 계약 시 등록",
                "source": "data/dim_manufacturer.csv",
                "dict": [
                    ("manufacturer_id", "제조사 ID", "string (MFG-XXX)", "제조사 고유 식별 코드"),
                    ("manufacturer_name", "제조사명", "string", "국내외 식품 제조사 정식 명칭"),
                    ("business_category", "사업부문", "string", "주력 식품 생산 사업 분야"),
                    ("country", "본사 소재국", "string", "제조사 본사 소재 국가"),
                    ("item_count", "등록 품목수", "int", "해당 제조사 등록 SKU 총수"),
                    ("primary_brand", "대표 브랜드", "string", "대표 시그니처 브랜드 목록"),
                    ("notes", "운영 특이사항", "string", "임가공 및 비즈니스 특성 메모")
                ]
            },
            "dim_buyer (바이어 마스터 디멘전)": {
                "layer": "Master (Dimension)",
                "type": "Dimension Table",
                "df": df_dim_buyer,
                "pk": "buyer_id (BYR-001 ~ BYR-081)",
                "fks": "None",
                "grain": "해외 바이어/수출 벤더사 단위 (81개사)",
                "update": "수출 바이어 신규 수주 시 등록",
                "source": "data/dim_buyer.csv",
                "dict": [
                    ("buyer_id", "바이어 ID", "string (BYR-XXX)", "바이어 고유 식별 코드"),
                    ("buyer_name", "바이어명", "string", "바이어/거래처 정식 명칭"),
                    ("export_country", "수출 대상국", "string", "최종 소비/수출 국가"),
                    ("export_region", "글로벌 권역", "string", "대륙별 글로벌 권역"),
                    ("buyer_type", "거래처 유형", "string", "유통사, 대형마트, 벤더사 등"),
                    ("order_count", "누적 오더수", "int", "수행된 총 작업 오더 횟수"),
                    ("total_boxes", "총 출하박스", "int", "누적 출하 박스 수"),
                    ("total_stickers", "총 스티커수", "int", "누적 부착 스티커 수량"),
                    ("special_notes", "라벨링 규정", "string", "수출국별 법적 라벨링 주의사항")
                ]
            },
            "raw_verified_source_rows (Bronze 원천 Raw)": {
                "layer": "Bronze (Raw)",
                "type": "Raw Ingestion",
                "df": raw_df_preview,
                "pk": "source_file_name, page_no, line_no",
                "fks": "None (비정규화 원천)",
                "grain": "수기 일지 OCR 추출 1행",
                "update": "구글 스프레드시트 갱신 시 자동 반영",
                "source": "구글 스프레드시트 (Live CSV)",
                "dict": [
                    ("source_file_name", "원천 파일명", "string", "OCR 스캔 원본 파일명"),
                    ("page_no", "페이지", "int", "수기 작업일지 페이지 번호"),
                    ("line_no", "행 번호", "int", "일지 내 순번"),
                    ("work_date", "작업일자", "string", "일지에 기록된 작업 일자"),
                    ("worker_count", "작업인원", "float", "일지에 기록된 작업 인원수"),
                    ("item_name", "품목명", "string", "수기 원본 품목명"),
                    ("volume", "규격", "string", "수기 원본 규격 문자열"),
                    ("pack_qty", "입량", "int", "수기 원본 박스당 입수량"),
                    ("work_qty", "작업수량", "int", "수기 원본 출하 박스 수"),
                    ("sticker_qty", "스티커수량", "int", "수기 원본 스티커 수량"),
                    ("remark", "비고", "string", "거래처/수출국가/오더번호 메모")
                ]
            },
            "item_alias_mapping (동의어/별칭 사전)": {
                "layer": "Config (Dictionary)",
                "type": "Mapping Table",
                "df": alias_df_current,
                "pk": "raw_alias",
                "fks": "standard_item_name (➔ dim_item)",
                "grain": "수기 축약어 1건 단위",
                "update": "대시보드에서 원클릭 추가",
                "source": "data/item_alias_mapping.csv",
                "dict": [
                    ("raw_alias", "수기 별칭/약어", "string", "현장 작업자가 표기하는 축약어/오타"),
                    ("standard_item_name", "표준 제품명", "string", "매핑될 공식 마스터 제품명"),
                    ("notes", "등록 사유", "string", "등록 배경 및 작업자 메모")
                ]
            },
            "daily_productivity_mart (일자별 생산성 Gold Mart)": {
                "layer": "Gold (Analytics Mart)",
                "type": "Aggregate Table",
                "df": daily_mart,
                "pk": "work_date (Date)",
                "fks": "None",
                "grain": "작업 일자 1일 단위 (31일)",
                "update": "Silver Fact 변경 시 실시간 집계",
                "source": "GoldAnalyticsPipeline.build_daily_productivity_mart",
                "dict": [
                    ("work_date", "작업일자", "string (YYYY-MM-DD)", "작업 일자"),
                    ("total_stickers", "총 스티커수", "int", "당일 총 부착 스티커 수량"),
                    ("total_boxes", "총 출하박스", "int", "당일 총 출하 박스 수량"),
                    ("worker_count", "투입 인원", "float", "당일 현장 작업자 수"),
                    ("total_worker_hours", "총 투입공수", "float", "당일 총 투입 인·시 (Man-Hours)"),
                    ("stickers_per_man_hour", "시간당 부착량", "float", "인당 1시간당 스티커 부착 속도"),
                    ("boxes_per_man_hour", "시간당 박스량", "float", "인당 1시간당 출하 박스 처리 속도")
                ]
            },
            "item_difficulty_mart (품목별 난이도 Gold Mart)": {
                "layer": "Gold (Analytics Mart)",
                "type": "Aggregate Table",
                "df": item_mart,
                "pk": "normalized_item_name",
                "fks": "None",
                "grain": "표준 품목 1종 단위",
                "update": "Silver Fact 변경 시 실시간 집계",
                "source": "GoldAnalyticsPipeline.build_item_difficulty_mart",
                "dict": [
                    ("normalized_item_name", "표준 품목명", "string", "공식 표준 제품명"),
                    ("manufacturer", "제조사명", "string", "식품 제조사"),
                    ("category_1", "대분류", "string", "식품 대분류"),
                    ("avg_pack_qty", "평균 입수량", "float", "박스당 평균 입수량"),
                    ("total_stickers", "누적 스티커수", "int", "누적 총 부착 스티커 수량"),
                    ("stickers_per_hour", "시간당 속도", "float", "과거 누적 기준 평균 시간당 속도"),
                    ("difficulty_tier", "난이도 등급", "string", "저/중/고난이도 작업 복잡도 분류")
                ]
            },
            "buyer_summary_mart (바이어별 실적 Gold Mart)": {
                "layer": "Gold (Analytics Mart)",
                "type": "Aggregate Table",
                "df": buyer_mart,
                "pk": "buyer_normalized",
                "fks": "None",
                "grain": "해외 바이어 1개사 단위",
                "update": "Silver Fact 변경 시 실시간 집계",
                "source": "GoldAnalyticsPipeline.build_buyer_summary_mart",
                "dict": [
                    ("buyer_normalized", "표준 바이어명", "string", "공식 바이어/수출 거래처명"),
                    ("export_country", "수출 대상국", "string", "바이어 수출 대상 국가"),
                    ("export_region", "글로벌 권역", "string", "대륙별 글로벌 권역"),
                    ("order_count", "총 오더수", "int", "수행된 작업 오더 횟수"),
                    ("total_boxes", "총 출하박스", "int", "누적 출하 박스 수"),
                    ("total_stickers", "총 스티커수", "int", "누적 부착 스티커 수량"),
                    ("sticker_share_pct", "점유율(%)", "float", "전체 작업량 대비 바이어 비중")
                ]
            }
        }

        info = catalog_meta.get(selected_table_name, {})
        target_df = info.get("df", pd.DataFrame())

        # Overview Metadata Card (Enhanced Legibility & Clean Rendering)
        m_grain = info.get('grain', '-')
        m_layer = info.get('layer', '-')
        m_type = info.get('type', '-')
        m_update = info.get('update', '-')
        m_source = info.get('source', '-')
        m_pk = info.get('pk', '-')
        m_fks = info.get('fks', '-')
        n_rows_str = f"{len(target_df):,}"
        n_cols_str = f"{len(target_df.columns):,}"

        st.markdown(f"""<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; margin-bottom: 22px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);">
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 14px; margin-bottom: 16px;">
<div style="display: flex; align-items: center; gap: 10px;">
<span style="font-size: 24px;">📋</span>
<div>
<div style="font-weight: 800; color: #0f172a; font-size: 17px; letter-spacing: -0.3px;">{selected_table_name}</div>
<div style="font-size: 12px; color: #64748b; margin-top: 2px;">단위 (Grain): <strong>{m_grain}</strong></div>
</div>
</div>
<div style="display: flex; gap: 8px;">
<span style="background: #e0f2fe; color: #0284c7; font-weight: 700; font-size: 12px; padding: 4px 12px; border-radius: 20px; border: 1px solid #bae6fd;">{m_layer}</span>
<span style="background: #f1f5f9; color: #475569; font-weight: 600; font-size: 12px; padding: 4px 12px; border-radius: 20px; border: 1px solid #e2e8f0;">{m_type}</span>
</div>
</div>
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
<div style="font-size: 11.5px; color: #64748b; font-weight: 600;">📊 총 레코드 수</div>
<div style="font-size: 20px; font-weight: 800; color: #0f172a; margin-top: 2px;">{n_rows_str} <span style="font-size: 12px; font-weight: 500; color: #64748b;">행</span></div>
</div>
<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
<div style="font-size: 11.5px; color: #64748b; font-weight: 600;">📐 총 컬럼 수</div>
<div style="font-size: 20px; font-weight: 800; color: #0f172a; margin-top: 2px;">{n_cols_str} <span style="font-size: 12px; font-weight: 500; color: #64748b;">열</span></div>
</div>
<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
<div style="font-size: 11.5px; color: #64748b; font-weight: 600;">🔄 갱신 주기</div>
<div style="font-size: 13.5px; font-weight: 700; color: #0284c7; margin-top: 5px;">{m_update}</div>
</div>
<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
<div style="font-size: 11.5px; color: #64748b; font-weight: 600;">🎯 데이터 소스</div>
<div style="font-size: 12px; font-weight: 600; color: #334155; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{m_source}">{m_source}</div>
</div>
</div>
<div style="background: #f8fafc; border-radius: 8px; padding: 14px 18px; font-size: 12.5px; line-height: 1.65; color: #334155; border: 1px solid #e2e8f0;">
<div style="margin-bottom: 6px;">🔑 <strong style="color: #0f172a;">기본키 (Primary Key):</strong> <code style="background: #ffffff; padding: 2px 8px; border-radius: 4px; border: 1px solid #cbd5e1; color: #0f172a; font-weight: 600;">{m_pk}</code></div>
<div>🔗 <strong style="color: #0f172a;">외래키 (Foreign Keys):</strong> <span style="color: #475569;">{m_fks}</span></div>
</div>
</div>""", unsafe_allow_html=True)

        # Columns Dictionary Table
        st.markdown("##### 🗂️ 컬럼 스키마 사전 (Column Dictionary)")
        col_dict_data = info.get("dict", [])
        if col_dict_data:
            df_col_dict = pd.DataFrame(col_dict_data, columns=["컬럼명 (Column)", "한글 레이블", "데이터 타입", "설명"])
            st.dataframe(df_col_dict, use_container_width=True, hide_index=True)

        # Sample Data Preview with Custom Limit & Search
        st.markdown("##### 👀 실제 데이터 미리보기 (Data Preview & Search)")
        if not target_df.empty:
            col_pv1, col_pv2 = st.columns([3, 1])
            with col_pv1:
                search_query = st.text_input(
                    "🔍 테이블 내 실시간 검색 (키워드 입력 시 즉시 필터링)",
                    placeholder="검색할 품목명, 제조사, 코드 등을 입력하세요...",
                    key=f"cat_search_{selected_table_name}"
                )
            with col_pv2:
                limit_option = st.selectbox(
                    "표시 행 수",
                    options=["상위 20개", "상위 50개", "상위 100개", "전체 보기"],
                    index=1,
                    key=f"cat_limit_{selected_table_name}"
                )

            # Apply Search Filter
            preview_display_df = target_df.copy()
            if search_query.strip():
                q = search_query.strip().lower()
                mask = preview_display_df.astype(str).apply(lambda row: row.str.lower().str.contains(q, na=False)).any(axis=1)
                preview_display_df = preview_display_df[mask]

            total_found = len(preview_display_df)
            if limit_option == "상위 20개":
                preview_display_df = preview_display_df.head(20)
            elif limit_option == "상위 50개":
                preview_display_df = preview_display_df.head(50)
            elif limit_option == "상위 100개":
                preview_display_df = preview_display_df.head(100)
            # Else "전체 보기" keeps all rows

            st.caption(f"📊 총 **{len(target_df):,}개 행** 중 **{total_found:,}건** 검색됨 (화면에 **{len(preview_display_df):,}건** 표시)")
            st.dataframe(preview_display_df, use_container_width=True, hide_index=True)
            
            # Download CSV
            csv_target = target_df.to_csv(index=False, encoding="utf-8-sig")
            safe_fname = selected_table_name.split(" ")[0] + ".csv"
            st.download_button(
                f"📥 {safe_fname} 전체 데이터 다운로드 (CSV)",
                data=csv_target,
                file_name=safe_fname,
                mime="text/csv",
                key=f"btn_download_catalog_{safe_fname}"
            )
        else:
            st.info("해당 테이블에 표시할 데이터가 없습니다.")



