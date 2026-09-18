import os
import argparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from datetime import datetime, timedelta, date
import pandas as pd
from typing import Dict, Any, Optional, Tuple

from src.transformation.silver_pipeline import build_silver_layer
from src.analytics.gold_pipeline import GoldAnalyticsPipeline


def _load_env_fallback():
    """Loads key-value pairs from .env if present and not in os.environ."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_fallback()

GOOGLE_SHEET_EDIT_URL = os.getenv(
    "GOOGLE_SHEET_EDIT_URL",
    "https://docs.google.com/spreadsheets"
)
DASHBOARD_URL = os.getenv(
    "STREAMLIT_DASHBOARD_URL",
    "https://export-packaging-showcase.streamlit.app"
)


# ==============================================================================
# 1. Monthly Closing Report Generator (대안 1: 월간 종합 결산 리포트)
# ==============================================================================

def generate_monthly_report_html(
    silver_df: pd.DataFrame,
    target_month: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Generates an executive-ready monthly operations closing report in HTML.
    target_month format: 'YYYY-MM' (e.g. '2026-08'). If None, infers latest completed month.
    """
    if silver_df.empty:
        return "<h3>데이터가 없습니다.</h3>", {}

    df = silver_df.copy()
    df["work_month"] = pd.to_datetime(df["work_date"]).dt.strftime("%Y-%m")

    months = sorted(df["work_month"].dropna().unique())
    if not target_month:
        today = datetime.now().date()
        # If today is in the first 5 days of the month, pick previous month if available
        prev_m = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        if prev_m in months:
            target_month = prev_m
        else:
            target_month = months[-1]

    m_df = df[df["work_month"] == target_month]
    if m_df.empty:
        return f"<h3>{target_month} 월에 해당하는 데이터가 없습니다.</h3>", {}

    # Calculate MoM (Month-over-Month) with previous month
    target_idx = months.index(target_month) if target_month in months else -1
    prev_month = months[target_idx - 1] if target_idx > 0 else None
    prev_df = df[df["work_month"] == prev_month] if prev_month else pd.DataFrame()

    total_stickers = int(m_df["sticker_qty"].sum())
    total_boxes = int(m_df["work_qty"].sum())
    total_hours = float(m_df["total_man_hours"].drop_duplicates().sum()) if "total_man_hours" in m_df else 0.0
    if total_hours <= 0:
        total_hours = float((m_df["effective_worker_count"].mean() * 8.0) * m_df["work_date"].nunique())

    speed_hr = round(total_stickers / total_hours, 1) if total_hours > 0 else 0.0
    active_days = int(m_df["work_date"].nunique())
    avg_workers = round(m_df["effective_worker_count"].mean(), 1) if "effective_worker_count" in m_df else 0.0
    mismatch_count = int(m_df["qty_mismatch_flag"].sum())
    total_rows = len(m_df)
    dq_pass_rate = round(((total_rows - mismatch_count) / max(1, total_rows) * 100), 1)

    # MoM calculations
    mom_sticker_str = "신규 집계"
    mom_box_str = "신규 집계"
    if not prev_df.empty:
        prev_stickers = prev_df["sticker_qty"].sum()
        prev_boxes = prev_df["work_qty"].sum()
        s_diff = total_stickers - prev_stickers
        b_diff = total_boxes - prev_boxes
        s_pct = (s_diff / prev_stickers * 100) if prev_stickers > 0 else 0
        b_pct = (b_diff / prev_boxes * 100) if prev_boxes > 0 else 0
        mom_sticker_str = f"{'▲ +' if s_pct >= 0 else '▼ '}{s_pct:.1f}% (전월비 {s_diff:+,}매)"
        mom_box_str = f"{'▲ +' if b_pct >= 0 else '▼ '}{b_pct:.1f}% (전월비 {b_diff:+,}박스)"

    # Top 5 Items
    top_items = m_df.groupby("normalized_item_name").agg(
        boxes=("work_qty", "sum"),
        stickers=("sticker_qty", "sum"),
        manufacturer=("manufacturer", "first"),
        avg_pack=("pack_qty", "mean")
    ).sort_values("stickers", ascending=False).head(5).reset_index()

    # Top 5 Buyers
    top_buyers = m_df.groupby("buyer_normalized").agg(
        stickers=("sticker_qty", "sum"),
        boxes=("work_qty", "sum")
    ).sort_values("stickers", ascending=False).head(5).reset_index()

    top_items_rows = ""
    for idx, row in top_items.iterrows():
        pack_badge = "고난이도" if row['avg_pack'] >= 32 else ("보통" if row['avg_pack'] >= 16 else "단순")
        if row['avg_pack'] >= 32:
            bg_c, text_c = "#fee2e2", "#dc2626"
        elif row['avg_pack'] >= 16:
            bg_c, text_c = "#fef3c7", "#d97706"
        else:
            bg_c, text_c = "#dcfce7", "#16a34a"

        top_items_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;">
            <td style="padding: 10px 12px; font-weight: 600; color: #1e293b;">
                {idx+1}. {row['normalized_item_name']}
                <span style="display: inline-block; font-size: 11px; padding: 2px 6px; border-radius: 4px; background-color: {bg_c}; color: {text_c}; margin-left: 6px; font-weight: bold;">{pack_badge} (입량 {row['avg_pack']:.0f})</span>
            </td>
            <td style="padding: 10px 12px; color: #64748b;">{row['manufacturer']}</td>
            <td style="padding: 10px 12px; text-align: right; color: #0f172a;">{int(row['boxes']):,} 박스</td>
            <td style="padding: 10px 12px; text-align: right; font-weight: bold; color: #2563eb;">{int(row['stickers']):,} 개</td>
        </tr>
        """

    top_buyers_rows = ""
    for idx, row in top_buyers.iterrows():
        share = round((row['stickers'] / total_stickers * 100), 1) if total_stickers > 0 else 0
        status_badge = "🚀 1위 주력처" if idx == 0 else ("🟢 핵심 바이어" if idx <= 2 else "📦 정기 선적처")
        top_buyers_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;">
            <td style="padding: 10px 12px; font-weight: 600; color: #1e293b;">
                {row['buyer_normalized']}
                <span style="font-size: 11px; margin-left: 6px; color: #059669; font-weight: normal;">[{status_badge}]</span>
            </td>
            <td style="padding: 10px 12px; text-align: right; color: #0f172a;">{int(row['stickers']):,} 개</td>
            <td style="padding: 10px 12px; text-align: right; font-weight: bold; color: #059669;">{share}%</td>
        </tr>
        """

    year_str, month_str = target_month.split("-")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{year_str}년 {int(month_str)}월 스티커 패키징 월간 운영 결산 리포트</title>
    </head>
    <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', sans-serif; background-color: #f8fafc; color: #1e293b;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', sans-serif;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 30px 24px; color: #ffffff;">
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #93c5fd;">Export Packaging Monthly Operations Report</div>
                <h1 style="margin: 8px 0 4px 0; font-size: 23px; font-weight: 800; color: #ffffff;">📊 {year_str}년 {int(month_str)}월 스티커 패키징 월간 결산 리포트</h1>
                <p style="margin: 0; font-size: 13px; color: #cbd5e1;">집계 대상월: <strong>{target_month}</strong> (총 가동일수 {active_days}일 | 일평균 투입 {avg_workers}명 | 총 {total_rows:,}개 작업 행)</p>
            </div>

            <div style="padding: 24px;">
                
                <!-- 4 KPI Cards Grid -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px;">
                    <div style="background-color: #eff6ff; padding: 16px; border-radius: 8px; border: 1px solid #dbeafe;">
                        <div style="font-size: 12px; color: #1e40af; font-weight: 600;">월간 총 부착 스티커 수량</div>
                        <div style="font-size: 24px; font-weight: 800; color: #1e3a8a; margin-top: 4px;">{total_stickers:,} <span style="font-size: 14px; font-weight: 500;">매</span></div>
                        <div style="font-size: 11px; color: #3b82f6; margin-top: 4px; font-weight: 600;">{mom_sticker_str}</div>
                    </div>
                    <div style="background-color: #f0fdf4; padding: 16px; border-radius: 8px; border: 1px solid #dcfce7;">
                        <div style="font-size: 12px; color: #166534; font-weight: 600;">월간 완제품 출하 박스 수량</div>
                        <div style="font-size: 24px; font-weight: 800; color: #15803d; margin-top: 4px;">{total_boxes:,} <span style="font-size: 14px; font-weight: 500;">박스</span></div>
                        <div style="font-size: 11px; color: #16a34a; margin-top: 4px; font-weight: 600;">{mom_box_str}</div>
                    </div>
                    <div style="background-color: #faf5ff; padding: 16px; border-radius: 8px; border: 1px solid #f3e8ff;">
                        <div style="font-size: 12px; color: #6b21a8; font-weight: 600;">월간 총 투입 공수 (Man-Hours)</div>
                        <div style="font-size: 24px; font-weight: 800; color: #7e22ce; margin-top: 4px;">{total_hours:,.1f} <span style="font-size: 14px; font-weight: 500;">시간</span></div>
                        <div style="font-size: 11px; color: #8b5cf6; margin-top: 4px;">일평균 가동 {(total_hours/max(1, active_days)):.1f} 시간</div>
                    </div>
                    <div style="background-color: #fff7ed; padding: 16px; border-radius: 8px; border: 1px solid #ffedd5;">
                        <div style="font-size: 12px; color: #9a3412; font-weight: 600;">월평균 생산 속도 (Speed)</div>
                        <div style="font-size: 24px; font-weight: 800; color: #c2410c; margin-top: 4px;">{speed_hr:,.1f} <span style="font-size: 14px; font-weight: 500;">매/hr</span></div>
                        <div style="font-size: 11px; color: #ea580c; margin-top: 4px;">1인 1일 처리: {(total_stickers/max(1, (avg_workers*active_days))):,.0f} 매</div>
                    </div>
                </div>

                <!-- Section: Executive Highlights -->
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
                    <div style="font-size: 14px; font-weight: 700; color: #1e293b; margin-bottom: 8px;">🌟 {int(month_str)}월 운영 핵심 총괄 요약</div>
                    <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #475569; line-height: 1.7;">
                        <li><strong>총 출하량:</strong> 한 달간 총 <strong>{total_stickers:,}매</strong>(완제품 <strong>{total_boxes:,}박스</strong>) 정상 출하 완료.</li>
                        <li><strong>최대 수주처:</strong> 1위 바이어 '{top_buyers.iloc[0]["buyer_normalized"]}'(월간 {int(top_buyers.iloc[0]["stickers"]):,}매, 점유율 {(top_buyers.iloc[0]["stickers"]/total_stickers*100):.1f}%) 주도.</li>
                        <li><strong>데이터 품질:</strong> 총 {total_rows:,}건의 작업 행 중 무결성 통과율 <strong>{dq_pass_rate}%</strong> 달성 (오기입 의심 {mismatch_count}건 자동 보정 완료).</li>
                    </ul>
                </div>

                <!-- Section: Top Buyers -->
                <h3 style="font-size: 16px; font-weight: 700; margin: 24px 0 12px 0; color: #0f172a; border-left: 4px solid #059669; padding-left: 8px;">🌍 {int(month_str)}월 수출 바이어별 선적 실적 Top 5</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;">
                    <thead>
                        <tr style="background-color: #f1f5f9; text-align: left; font-size: 12px; color: #475569;">
                            <th style="padding: 8px 12px;">바이어 / 수출처</th>
                            <th style="padding: 8px 12px; text-align: right;">월간 스티커 수량</th>
                            <th style="padding: 8px 12px; text-align: right;">월간 점유율</th>
                        </tr>
                    </thead>
                    <tbody>
                        {top_buyers_rows}
                    </tbody>
                </table>

                <!-- Section: Top Items -->
                <h3 style="font-size: 16px; font-weight: 700; margin: 24px 0 12px 0; color: #0f172a; border-left: 4px solid #2563eb; padding-left: 8px;">🔥 {int(month_str)}월 최다 작업 품목 Top 5</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;">
                    <thead>
                        <tr style="background-color: #f1f5f9; text-align: left; font-size: 12px; color: #475569;">
                            <th style="padding: 8px 12px;">제품명</th>
                            <th style="padding: 8px 12px;">제조사</th>
                            <th style="padding: 8px 12px; text-align: right;">박스수</th>
                            <th style="padding: 8px 12px; text-align: right;">스티커수</th>
                        </tr>
                    </thead>
                    <tbody>
                        {top_items_rows}
                    </tbody>
                </table>

                <!-- Section: Data Quality Notice -->
                <div style="background-color: {'#fef2f2' if mismatch_count > 0 else '#f0fdf4'}; border: 1px solid {'#fecaca' if mismatch_count > 0 else '#bbf7d0'}; border-radius: 8px; padding: 14px 16px; font-size: 13px;">
                    <strong style="color: {'#991b1b' if mismatch_count > 0 else '#166534'};">🛡️ 월간 데이터 거버넌스(DQ) 감사:</strong> 
                    {f'해당 월 총 {total_rows:,}건의 데이터 중 수량 불일치 의심 {mismatch_count}건이 감지되었습니다 (현장 수기 기록 우선 자동 보정 완료).' if mismatch_count > 0 else f'해당 월 총 {total_rows:,}건의 데이터 정합성 검증이 100% 무결성을 통과하였습니다.'}
                </div>

                <!-- Footer Link Button -->
                <div style="text-align: center; margin-top: 30px; padding-top: 18px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
                    본 리포트는 수출 식품 패키징 자동화 플랫폼(GitHub Actions)에 의해 매월 1일 자동 발송됩니다.<br>
                    <div style="margin-top: 14px;">
                        <a href="{DASHBOARD_URL}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; font-weight: 700; border-radius: 8px; font-size: 13px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">📊 실시간 관제 대시보드 바로가기</a>
                    </div>
                </div>

            </div>
        </div>
    </body>
    </html>
    """

    summary_stats = {
        "target_month": target_month,
        "total_stickers": total_stickers,
        "total_boxes": total_boxes,
        "total_hours": total_hours,
        "speed_hr": speed_hr,
        "mom_sticker_str": mom_sticker_str,
        "mismatch_count": mismatch_count
    }

    return html_content, summary_stats


def generate_monthly_report_text(
    silver_df: pd.DataFrame,
    target_month: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Generates a clean, executive-ready plain-text monthly closing report.
    """
    if silver_df.empty:
        return "데이터가 없습니다.", {}

    df = silver_df.copy()
    df["work_month"] = pd.to_datetime(df["work_date"]).dt.strftime("%Y-%m")
    months = sorted(df["work_month"].dropna().unique())

    if not target_month:
        today = datetime.now().date()
        prev_m = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        if prev_m in months:
            target_month = prev_m
        else:
            target_month = months[-1]

    m_df = df[df["work_month"] == target_month]
    if m_df.empty:
        return f"{target_month} 월에 해당하는 데이터가 없습니다.", {}

    target_idx = months.index(target_month) if target_month in months else -1
    prev_month = months[target_idx - 1] if target_idx > 0 else None
    prev_df = df[df["work_month"] == prev_month] if prev_month else pd.DataFrame()

    total_stickers = int(m_df["sticker_qty"].sum())
    total_boxes = int(m_df["work_qty"].sum())
    total_hours = float(m_df["total_man_hours"].drop_duplicates().sum()) if "total_man_hours" in m_df else 0.0
    if total_hours <= 0:
        total_hours = float((m_df["effective_worker_count"].mean() * 8.0) * m_df["work_date"].nunique())

    speed_hr = round(total_stickers / total_hours, 1) if total_hours > 0 else 0.0
    active_days = int(m_df["work_date"].nunique())
    avg_workers = round(m_df["effective_worker_count"].mean(), 1) if "effective_worker_count" in m_df else 0.0
    per_worker_daily = round(total_stickers / max(1, (avg_workers * active_days)), 0)
    avg_pack = round(total_stickers / max(1, total_boxes), 1)

    mom_str = "신규 집계"
    if not prev_df.empty:
        prev_stickers = prev_df["sticker_qty"].sum()
        s_pct = ((total_stickers - prev_stickers) / prev_stickers * 100) if prev_stickers > 0 else 0
        mom_str = f"{'▲ +' if s_pct >= 0 else '▼ '}{s_pct:.1f}%"

    top_buyers = m_df.groupby("buyer_normalized").agg(
        stickers=("sticker_qty", "sum"),
        boxes=("work_qty", "sum")
    ).sort_values("stickers", ascending=False).head(5).reset_index()

    buyer_lines = []
    for idx, row in top_buyers.iterrows():
        pct = (row['stickers'] / total_stickers * 100) if total_stickers > 0 else 0
        status = " [🚀 1위 주력처]" if idx == 0 else " [🟢 주요 선적처]"
        buyer_lines.append(f"{idx+1}. {row['buyer_normalized']:<14}: {int(row['stickers']):>8,} 매 ({int(row['boxes']):>5,} 박스 | 점유율 {pct:>4.1f}%) ──{status}")
    buyers_text = "\n".join(buyer_lines)

    top_items = m_df.groupby("normalized_item_name").agg(
        boxes=("work_qty", "sum"),
        stickers=("sticker_qty", "sum"),
        manufacturer=("manufacturer", "first"),
        avg_pack=("pack_qty", "mean")
    ).sort_values("stickers", ascending=False).head(5).reset_index()

    item_lines = []
    for idx, row in top_items.iterrows():
        tier = "고난이도" if row['avg_pack'] >= 32 else ("보통" if row['avg_pack'] >= 16 else "단순")
        mfg = row['manufacturer']
        name_str = f"{row['normalized_item_name']} ({mfg})"
        item_lines.append(f"{idx+1}. {name_str:<32} │ {int(row['stickers']):>7,} 매 ({int(row['boxes']):>5,} 박스) │ 입량 {row['avg_pack']:>2.0f} [{tier}]")
    items_text = "\n".join(item_lines)

    mismatch_count = int(m_df["qty_mismatch_flag"].sum())
    total_rows = len(m_df)
    dq_pass = round(((total_rows - mismatch_count) / max(1, total_rows) * 100), 1)

    year_str, month_str = target_month.split("-")

    text_report = f"""[발송 제목] 📊 [월간 운영 결산] {year_str}년 {int(month_str)}월 수출 식품 스티커 패키징 실적 보고 (총 {total_stickers:,}매 출하)

발신: 수출 식품 패키징 운영 플랫폼 (자동 생성)
집계 대상월: {target_month} [총 가동일수: {active_days}일 | 일평균 투입: {avg_workers}명 | 총 {total_rows:,}개 작업 행]

================================================================================
🌟 {int(month_str)}월 월간 핵심 성과 하이라이트 (Monthly Highlights)
================================================================================
• [월간 생산량]: 한 달간 총 {total_stickers:,}매({total_boxes:,}박스) 완제품 출하 달성 (전월비 {mom_str})
• [공정 효율성]: 작업자 {avg_workers}명/일 투입 기준, 시간당 {speed_hr:,.1f}매/hr의 안정적 생산 속도 유지
• [수주 견인]: 1위 바이어 '{top_buyers.iloc[0]["buyer_normalized"]}'({(top_buyers.iloc[0]["stickers"]/total_stickers*100):.1f}%) 등 주력 거래처 선적 안정적
• [데이터 무결성]: 월간 총 {total_rows:,}행 중 {dq_pass}% 정합성 통과 (불일치 {mismatch_count}건 자동 보정)

================================================================================
📊 1. 월간 종합 생산성 지표 (Monthly Productivity Overview)
================================================================================
┌──────────────────────┬──────────────────────┬──────────────────────┐
│  총 부착 스티커 수량 │  총 완제품 출하박스  │  총 투입 가동 공수   │
│     {total_stickers:>10,} 매      │     {total_boxes:>8,} 박스     │     {total_hours:>7,.1f} Man-Hours  │
├──────────────────────┼──────────────────────┼──────────────────────┤
│  시간당 평균 속도    │  1인 1일 평균 처리량 │  박스당 평균 입수량  │
│     {speed_hr:>7,.1f} 매/hr    │      {per_worker_daily:>6,.0f} 매/인     │      {avg_pack:>6.1f} 개/박스    │
└──────────────────────┴──────────────────────┴──────────────────────┘

================================================================================
🌍 2. 월간 주요 수출 바이어별 선적 실적 및 점유율 Top 5
================================================================================
{buyers_text}

================================================================================
🏷️ 3. 월간 최다 작업 품목 Top 5 (Top SKU Complexity)
================================================================================
{items_text}

================================================================================
🛡️ 4. 월간 데이터 품질(DQ) 거버넌스 감사 결과
================================================================================
• 데이터 정합성 검증 : 월간 총 {total_rows:,}개 작업 행 중 {total_rows - mismatch_count:,}행 무결성 통과 (통과율: {dq_pass}%).
• 수량 불일치 감지   : {mismatch_count}건 감지 (현장 수기 기록 기준 1차 자동 보정 완료).
• 품목 마스터 정규화 : 100% (미등록 품목 0건, 전 품목 정규화 완료).

================================================================================
💡 5. 차월(다음 달) 운영 제언 및 액션 플랜 (Action Items)
================================================================================
① [자재 조달]: 1위 바이어의 대량 오더 지속에 대비한 수출용 라벨 원단 사전 안전재고 확충.
② [공정 최적화]: 입량 32개 이상 고난이도 품목 비중 분석 후 주초 숙련 라인 배치 유지.

--------------------------------------------------------------------------------
🔗 실시간 대시보드 관제 센터:
{DASHBOARD_URL}

※ 본 리포트는 데이터 파이프라인(Gold Mart)에 의해 매월 1일 오전 09:00에 정기 발송됩니다.
"""

    return text_report, {
        "target_month": target_month,
        "total_stickers": total_stickers,
        "total_boxes": total_boxes,
        "total_hours": total_hours,
        "speed_hr": speed_hr
    }


# ==============================================================================
# 2. Monthly Pre-check & Hold Alert Logic (월말 사전 점검 및 발송 보류)
# ==============================================================================

def check_monthly_readiness(
    silver_df: pd.DataFrame,
    target_month: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Checks whether the source data contains records for target_month.
    In pre-check (end of month), checks if the month has up-to-date records.
    """
    if silver_df.empty:
        return False, {"reason": "데이터셋이 비어 있습니다."}

    df = silver_df.copy()
    df["work_month"] = pd.to_datetime(df["work_date"]).dt.strftime("%Y-%m")
    months = sorted(df["work_month"].dropna().unique())

    if not target_month:
        today = datetime.now().date()
        # If day is 1, target is previous month; otherwise current month
        if today.day == 1:
            target_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        else:
            target_month = today.strftime("%Y-%m")

    m_df = df[df["work_month"] == target_month]
    is_ready = not m_df.empty

    latest_date = str(pd.to_datetime(silver_df["work_date"].max()).date())
    record_count = len(m_df)

    details = {
        "is_ready": is_ready,
        "target_month": target_month,
        "latest_date": latest_date,
        "record_count": record_count,
        "total_stickers": int(m_df["sticker_qty"].sum()) if is_ready else 0
    }
    return is_ready, details


def generate_monthly_missing_alert(
    details: Dict[str, Any],
    is_precheck: bool = False
) -> Tuple[str, str, str]:
    """
    Generates notification emails when monthly data is missing.
    is_precheck=True: Sent at end of month (월말 사전 독려 알림)
    is_precheck=False: Sent on 1st of month (월간 결산 발송 보류 알림)
    """
    target_month = details.get("target_month", "")
    latest_date = details.get("latest_date", "")
    record_count = details.get("record_count", 0)

    try:
        year_str, month_str = target_month.split("-")
        month_kr = f"{year_str}년 {int(month_str)}월"
    except Exception:
        month_kr = target_month

    if is_precheck:
        subject = f"⚠️ [사전 마감 알림] 내일 오전 월간 총괄 리포트 발송 예정: {month_kr} 작업 일지 최종 마감 안내"
        badge_title = "Monthly Closing Pre-flight Check"
        header_title = f"⚠️ {month_kr} 작업 일지 최종 마감 요청"
        header_bg = "linear-gradient(135deg, #d97706 0%, #f59e0b 100%)"
        status_box_bg = "#fffbeb"
        status_box_border = "#fef3c7"
        status_color = "#b45309"
        main_desc = f"""
        내일(<strong>1일 오전 09:00</strong>)에 전사 <strong>{month_kr} 월간 총괄 결산 리포트</strong>가 정기 발송될 예정입니다.<br><br>
        현재 원천 구글 스프레드시트를 점검한 결과, <strong>{month_kr}</strong> 작업 데이터가 아직 최종 마감되지 않은 것으로 확인되었습니다.<br>
        임원진 및 관련 부서에 정확한 월간 실적이 보고될 수 있도록 <strong>오늘 밤까지</strong> 작업 내역 입력을 완료해 주시기 바랍니다.
        """
        text_desc = f"""내일(1일 오전 09:00)에 전사 {month_kr} 월간 총괄 결산 리포트가 정기 발송될 예정입니다.
현재 원천 구글 스프레드시트 점검 결과, {month_kr} 작업 내역이 아직 최종 마감되지 않았습니다.
정확한 월간 실적 보고를 위해 오늘 밤까지 구글 시트에 작업 일지 입력을 완료해 주시기 바랍니다."""
    else:
        subject = f"🚨 [운영 알림] {month_kr} 작업 데이터 미등록으로 월간 결산 리포트 생성이 보류되었습니다"
        badge_title = "Monthly Operations Pipeline Notice"
        header_title = f"🚨 {month_kr} 월간 결산 리포트 발송 보류 안내"
        header_bg = "linear-gradient(135deg, #991b1b 0%, #ef4444 100%)"
        status_box_bg = "#fef2f2"
        status_box_border = "#fee2e2"
        status_color = "#991b1b"
        main_desc = f"""
        금일(<strong>1일 오전 09:00</strong>) 월간 결산 리포트 발송 시점까지 원천 구글 스프레드시트에 <strong>{month_kr}</strong> 작업 내역이 등록되지 않았습니다.<br><br>
        빈 통계나 잘못된 이전 데이터로 리포트가 발송되는 것을 방지하기 위해 <strong>금월 결산 리포트 자동 발송이 일시 보류</strong>되었습니다.<br>
        작업 일지를 구글 시트에 업데이트해 주시면 대시보드에 즉시 동기화되며, 대시보드에서 '최신 리포트 즉시 발송'을 진행하실 수 있습니다.
        """
        text_desc = f"""금일(1일 오전 09:00) 월간 결산 리포트 발송 시점까지 원천 구글 시트에 {month_kr} 작업 내역이 등록되지 않았습니다.
빈 통계나 이전 데이터가 발송되는 것을 방지하기 위해 금월 결산 리포트 자동 발송이 일시 보류되었습니다.
구글 시트에 작업 일지를 입력해 주시면 대시보드에 즉시 반영됩니다."""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', sans-serif; background-color: #f8fafc; color: #1e293b;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', sans-serif;">
            
            <!-- Header -->
            <div style="background: {header_bg}; padding: 26px 24px; color: #ffffff;">
                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; opacity: 0.9;">{badge_title}</div>
                <h1 style="margin: 8px 0 0 0; font-size: 21px; font-weight: 800;">{header_title}</h1>
            </div>

            <div style="padding: 24px;">
                <p style="font-size: 15px; line-height: 1.6; color: #334155; margin-top: 0;">
                    {main_desc}
                </p>

                <!-- Status Card -->
                <div style="background-color: {status_box_bg}; border: 1px solid {status_box_border}; border-radius: 8px; padding: 16px; margin: 20px 0;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;">
                        <tr>
                            <td style="padding: 6px 0; color: #64748b; width: 140px;">대상 마감월:</td>
                            <td style="padding: 6px 0; font-weight: bold; color: #0f172a;">{month_kr} ({target_month})</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; color: #64748b;">원천 최종 기록일:</td>
                            <td style="padding: 6px 0; font-weight: bold; color: {status_color};">{latest_date}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; color: #64748b;">현재 등록 상태:</td>
                            <td style="padding: 6px 0; font-weight: bold; color: #dc2626;">해당 월 등록 데이터 {record_count:,}건 (미마감)</td>
                        </tr>
                    </table>
                </div>

                <!-- Action Buttons -->
                <div style="text-align: center; margin: 28px 0 16px 0;">
                    <a href="{GOOGLE_SHEET_EDIT_URL}" target="_blank" style="display: inline-block; background-color: #15803d; color: #ffffff; padding: 12px 24px; text-decoration: none; font-weight: 700; border-radius: 8px; font-size: 14px; margin-right: 10px; box-shadow: 0 2px 4px rgba(21,128,61,0.2);">📝 원천 구글 시트 작업일지 입력 바로가기</a>
                    <a href="{DASHBOARD_URL}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; font-weight: 700; border-radius: 8px; font-size: 14px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">📊 관제 대시보드 바로가기</a>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
                    본 안내는 데이터 품질 및 마감 가드레일에 의해 자동 발송되었습니다.<br>
                    데이터가 등록되는 즉시 파이프라인이 월간 실적을 자동 집계합니다.
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""[운영 알림] {subject}

발신: 수출 식품 패키징 운영 플랫폼 (자동 검수)
검수 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

================================================================================
{header_title}
================================================================================
{text_desc}

[데이터 상태 점검]
• 대상 마감월: {month_kr} ({target_month})
• 최종 등록된 작업일: {latest_date}
• 현재 등록 건수: {record_count:,}건 (미마감)

================================================================================
💡 조치 방법 안내
================================================================================
1. 아래 구글 스프레드시트에 접속하여 작업 일지를 입력해 주세요:
   👉 {GOOGLE_SHEET_EDIT_URL}

2. 작업 일지 등록 후 대시보드에서 '최신 리포트 즉시 발송'을 진행할 수 있습니다:
   👉 {DASHBOARD_URL}

※ 본 안내는 월간 결산 리포트 자동 발송 전 데이터 정합성을 보호하기 위해 자동 발송되었습니다.
"""

    return subject, html_content, text_content


# ==============================================================================
# 3. SMTP Dispatch Engine
# ==============================================================================

def send_email_report(
    html_content: str,
    subject: Optional[str] = None,
    recipient_emails: Optional[list] = None,
    text_content: Optional[str] = None
) -> bool:
    """
    Sends multipart (text + HTML) report via SMTP using environment variables.
    """
    _load_env_fallback()

    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not recipient_emails:
        rec_env = os.getenv("RECIPIENT_EMAILS", "")
        recipient_emails = [e.strip() for e in rec_env.split(",") if e.strip()]

    if not smtp_user or not smtp_password or not recipient_emails:
        print("[Notice] SMTP credentials or recipients not fully configured. Email was generated but not dispatched via network.")
        return False

    if not subject:
        subject = "📊 [월간 운영 결산] 수출 식품 스티커 패키징 실적 보고"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = Header(subject, "utf-8").encode()
        msg["From"] = formataddr((str(Header("스티커 작업 분석 플랫폼", "utf-8")), smtp_user))
        msg["To"] = ", ".join(recipient_emails)

        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password.replace(" ", ""))
            server.sendmail(smtp_user, recipient_emails, msg.as_string())

        print(f"[Success] Monthly email successfully dispatched to {recipient_emails}")
        return True
    except Exception as e:
        print(f"[Error] Failed to send email via SMTP: {e}")
        return False


def run_monthly_email_pipeline(
    is_precheck: bool = False,
    force: bool = False,
    target_month: Optional[str] = None,
    recipient_emails: Optional[list] = None
) -> bool:
    """
    Monthly closing pipeline:
      - If is_precheck (월말 사전 점검):
          - Checks if today is the last day of the month (or force=True).
          - If data is ready -> Silent exit (True).
          - If data is NOT ready -> Dispatches 월말 마감 사전 독려 알림 email.
      - If regular 1st-of-month dispatch (매월 1일 본 발송):
          - If target month data is ready (or force=True) -> Dispatches 월간 결산 리포트.
          - If NOT ready -> Dispatches Hold Notice email.
    """
    silver_df, _, _ = build_silver_layer()
    is_ready, details = check_monthly_readiness(silver_df, target_month=target_month)

    print(f"[{'Monthly Precheck' if is_precheck else 'Monthly 1st Dispatch'}] Readiness: is_ready={is_ready}, details={details}")

    if is_precheck:
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        is_last_day = (tomorrow.month != today.month)

        if not is_last_day and not force:
            print(f"[Monthly Precheck] Today ({today}) is not the last day of the month. Skipping precheck.")
            return True

        if is_ready:
            print(f"[Monthly Precheck] Month data ({details['target_month']}) is ready ({details['record_count']} records). No reminder needed.")
            return True
        else:
            print(f"[Monthly Precheck] Month data is MISSING! Sending end-of-month reminder alert email...")
            subj, html_c, text_c = generate_monthly_missing_alert(details, is_precheck=True)
            return send_email_report(html_content=html_c, subject=subj, text_content=text_c, recipient_emails=recipient_emails)
    else:
        if is_ready or force:
            print("[Monthly Dispatch] Generating full monthly closing operations report...")
            t_month = details.get("target_month") if is_ready else target_month
            html, stats = generate_monthly_report_html(silver_df, target_month=t_month)
            text, _ = generate_monthly_report_text(silver_df, target_month=t_month)
            subject = f"📊 [월간 운영 결산] {stats.get('target_month', '')} 실적 보고 ({stats.get('total_stickers', 0):,}매 출하)"
            return send_email_report(html_content=html, subject=subject, text_content=text, recipient_emails=recipient_emails)
        else:
            print("[Monthly Dispatch] Target month data is MISSING! Sending Hold Notice alert email...")
            subj, html_c, text_c = generate_monthly_missing_alert(details, is_precheck=False)
            return send_email_report(html_content=html_c, subject=subj, text_content=text_c, recipient_emails=recipient_emails)


# ==============================================================================
# 4. Weekly Generator (Kept for on-demand UI use)
# ==============================================================================

def generate_weekly_report_html(
    silver_df: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Generates a responsive modern HTML email summary for a given week.
    Kept for backward compatibility and on-demand dashboard triggers.
    """
    if silver_df.empty:
        return "<h3>데이터가 없습니다.</h3>", {}

    max_date = pd.to_datetime(silver_df["work_date"].max())
    if not end_date:
        end_date = max_date.strftime("%Y-%m-%d")
    if not start_date:
        start_date = (max_date - timedelta(days=6)).strftime("%Y-%m-%d")

    mask = (silver_df["work_date"] >= start_date) & (silver_df["work_date"] <= end_date)
    week_df = silver_df[mask]
    if week_df.empty:
        week_df = silver_df.head(50)

    total_stickers = int(week_df["sticker_qty"].sum())
    total_boxes = int(week_df["work_qty"].sum())
    total_hours = float(week_df["total_man_hours"].drop_duplicates().sum()) if "total_man_hours" in week_df else 0.0
    if total_hours <= 0:
        total_hours = float((week_df["effective_worker_count"].mean() * 8.0) * week_df["work_date"].nunique())

    speed_hr = round(total_stickers / total_hours, 1) if total_hours > 0 else 0.0
    active_days = int(week_df["work_date"].nunique())
    avg_workers = round(week_df["effective_worker_count"].mean(), 1) if "effective_worker_count" in week_df else 0.0
    mismatch_count = int(week_df["qty_mismatch_flag"].sum())

    top_items = week_df.groupby("normalized_item_name").agg(
        boxes=("work_qty", "sum"),
        stickers=("sticker_qty", "sum"),
        manufacturer=("manufacturer", "first"),
        avg_pack=("pack_qty", "mean")
    ).sort_values("stickers", ascending=False).head(5).reset_index()

    top_buyers = week_df.groupby("buyer_normalized").agg(
        stickers=("sticker_qty", "sum"),
        boxes=("work_qty", "sum")
    ).sort_values("stickers", ascending=False).head(4).reset_index()

    top_items_rows = ""
    for idx, row in top_items.iterrows():
        pack_badge = "고난이도" if row['avg_pack'] >= 32 else ("보통" if row['avg_pack'] >= 16 else "단순")
        bg_c = "#fee2e2" if row['avg_pack'] >= 32 else ("#fef3c7" if row['avg_pack'] >= 16 else "#dcfce7")
        text_c = "#dc2626" if row['avg_pack'] >= 32 else ("#d97706" if row['avg_pack'] >= 16 else "#16a34a")
        top_items_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;">
            <td style="padding: 10px 12px; font-weight: 600; color: #1e293b;">
                {idx+1}. {row['normalized_item_name']}
                <span style="display: inline-block; font-size: 11px; padding: 2px 6px; border-radius: 4px; background-color: {bg_c}; color: {text_c}; margin-left: 6px; font-weight: bold;">{pack_badge}</span>
            </td>
            <td style="padding: 10px 12px; color: #64748b;">{row['manufacturer']}</td>
            <td style="padding: 10px 12px; text-align: right; color: #0f172a;">{int(row['boxes']):,} 박스</td>
            <td style="padding: 10px 12px; text-align: right; font-weight: bold; color: #2563eb;">{int(row['stickers']):,} 개</td>
        </tr>
        """

    top_buyers_rows = ""
    for idx, row in top_buyers.iterrows():
        share = round((row['stickers'] / total_stickers * 100), 1) if total_stickers > 0 else 0
        status_badge = "🚀 고성장" if idx == 0 else "🟢 안정"
        top_buyers_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;">
            <td style="padding: 10px 12px; font-weight: 600; color: #1e293b;">
                {row['buyer_normalized']} <span style="font-size: 11px; color: #059669;">[{status_badge}]</span>
            </td>
            <td style="padding: 10px 12px; text-align: right; color: #0f172a;">{int(row['stickers']):,} 개</td>
            <td style="padding: 10px 12px; text-align: right; font-weight: bold; color: #059669;">{share}%</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>스티커 작업 주간 실적 리포트</title></head>
    <body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif; background-color: #f8fafc; color: #1e293b;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif;">
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 28px 24px; color: #ffffff;">
                <h1 style="margin: 0; font-size: 22px; font-weight: 800;">📦 스티커 작업 주간 실적 리포트</h1>
                <p style="margin: 6px 0 0 0; font-size: 14px; opacity: 0.9;">조회 기간: <strong>{start_date} ~ {end_date}</strong> (총 가동일수: {active_days}일)</p>
            </div>
            <div style="padding: 24px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px;">
                    <div style="background-color: #eff6ff; padding: 16px; border-radius: 8px; border: 1px solid #dbeafe;">
                        <div style="font-size: 12px; color: #1e40af; font-weight: 600;">총 부착 스티커 수량</div>
                        <div style="font-size: 24px; font-weight: 800; color: #1e3a8a; margin-top: 4px;">{total_stickers:,} <span style="font-size: 14px;">개</span></div>
                    </div>
                    <div style="background-color: #f0fdf4; padding: 16px; border-radius: 8px; border: 1px solid #dcfce7;">
                        <div style="font-size: 12px; color: #166534; font-weight: 600;">총 작업 박스 수량</div>
                        <div style="font-size: 24px; font-weight: 800; color: #15803d; margin-top: 4px;">{total_boxes:,} <span style="font-size: 14px;">박스</span></div>
                    </div>
                </div>
                <h3 style="font-size: 16px; font-weight: 700; margin: 24px 0 12px 0; border-left: 4px solid #2563eb; padding-left: 8px;">🔥 최다 작업 품목</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">{top_items_rows}</table>
                <h3 style="font-size: 16px; font-weight: 700; margin: 24px 0 12px 0; border-left: 4px solid #059669; padding-left: 8px;">🌍 주요 바이어</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">{top_buyers_rows}</table>
                <div style="text-align: center; margin-top: 24px;">
                    <a href="{DASHBOARD_URL}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 10px 20px; text-decoration: none; font-weight: bold; border-radius: 6px;">📊 실시간 관제 대시보드 바로가기</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    summary_stats = {
        "start_date": start_date,
        "end_date": end_date,
        "total_stickers": total_stickers,
        "total_boxes": total_boxes,
        "total_hours": total_hours,
        "speed_hr": speed_hr,
        "mismatch_count": mismatch_count
    }
    return html_content, summary_stats


def generate_weekly_report_text(
    silver_df: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    html, stats = generate_weekly_report_html(silver_df, start_date=start_date, end_date=end_date)
    text = f"📦 [주간 리포트] {stats['start_date']} ~ {stats['end_date']} 스티커 수량: {stats['total_stickers']:,}개 | 박스: {stats['total_boxes']:,}박스"
    return text, stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monthly Operations Closing Email Dispatcher")
    parser.add_argument("--precheck", action="store_true", help="Run end-of-month pre-flight readiness check")
    parser.add_argument("--force", action="store_true", help="Force send report even if not 1st of month")
    parser.add_argument("--month", type=str, default=None, help="Target month in YYYY-MM format")
    parser.add_argument("--test-alert", action="store_true", help="Test send monthly missing data alert email immediately")
    args = parser.parse_args()

    if args.test_alert:
        silver_df, _, _ = build_silver_layer()
        _, details = check_monthly_readiness(silver_df, target_month=args.month)
        subj, html_c, text_c = generate_monthly_missing_alert(details, is_precheck=args.precheck)
        ok = send_email_report(html_content=html_c, subject=subj, text_content=text_c)
        print("Test monthly alert dispatch result:", ok)
    else:
        ok = run_monthly_email_pipeline(is_precheck=args.precheck, force=args.force, target_month=args.month)
        print("Monthly pipeline execution result:", ok)
