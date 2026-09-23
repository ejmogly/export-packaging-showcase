"""
Interactive Lineage & Flow Studio Engine
Provides executive-grade visual flow diagrams, interactive HTML5/SVG canvases,
and enhanced multi-stage Sankey diagrams for Data Lineage & Supply Chain Value Chain.
"""

import json
import pandas as pd
import plotly.graph_objects as go


def determine_consolidation_reason(raw: str, norm: str, match_type: str = "") -> str:
    """Classifies the data normalization rule applied to raw handwritten text."""
    if raw == norm:
        return "표준 일치 (Exact)"
    elif raw.lower() == norm.lower():
        return "대소문자 통일 (Case Normalization)"
    elif raw.replace(" ", "") == norm.replace(" ", ""):
        return "띄어쓰기 정규화 (Whitespace Trim)"
    elif any(t in raw for t in [
        "화이트화임", "연얀갱", "쿠쿠다스", "톰", "탕콩", "카드타드",
        "엔젤큐러슈", "뻬빼로", "뺴빼로", "초모", "소프크콘", "칸초칩",
        "칸쵸집", "구운나초", "후렌차파이"
    ]):
        return "수기/OCR 오타 교정 (Typo Correction)"
    elif any(k in raw for k in ["6봉", "12봉", "4P", "6P", "8P", "12P", "2P", "번들", "환"]):
        return "규격/수식어 통합 (Spec Consolidation)"
    elif raw in ["홈", "롯"]:
        return "파편 단어 복원 (Fragment Recovery)"
    elif "캐)" in raw:
        return "접두사 정규화 (Prefix Strip)"
    else:
        return "별칭 사전 매핑 (Alias Mapped)"


def build_lineage_dataset(silver_df: pd.DataFrame, dim_item_df: pd.DataFrame):
    """
    Builds the structured lineage dataframe and JSON-ready multi-variant items catalog.
    """
    lineage_df = silver_df.groupby(["item_name", "normalized_item_name"]).agg(
        row_count=("work_date", "count"),
        total_stickers=("sticker_qty", "sum"),
        min_date=("work_date", "min"),
        max_date=("work_date", "max"),
        match_type=("match_type", "first")
    ).reset_index()

    lineage_df["consolidation_reason"] = lineage_df.apply(
        lambda r: determine_consolidation_reason(r["item_name"], r["normalized_item_name"], str(r.get("match_type", ""))),
        axis=1
    )

    variant_counts = lineage_df.groupby("normalized_item_name")["item_name"].nunique()
    multi_variant_items = variant_counts[variant_counts > 1].sort_values(ascending=False)

    items_catalog = []
    dim_lookup = dim_item_df.set_index("item_name").to_dict("index") if not dim_item_df.empty else {}

    for canon_name in multi_variant_items.index:
        sub = lineage_df[lineage_df["normalized_item_name"] == canon_name]
        m_info = dim_lookup.get(canon_name, {})
        sku = m_info.get("item_code", "-")
        mfg = m_info.get("manufacturer_name", "-")
        cat1 = m_info.get("category_1", "-")
        cat2 = m_info.get("category_2", "-")
        cat_full = f"{cat1} > {cat2}" if cat1 != "-" else "-"
        std_vol = m_info.get("standard_volume", "-")

        raw_list = []
        for _, r in sub.iterrows():
            raw_list.append({
                "raw_name": str(r["item_name"]),
                "row_count": int(r["row_count"]),
                "total_stickers": float(r["total_stickers"]),
                "reason": str(r["consolidation_reason"]),
                "min_date": str(r["min_date"]),
                "max_date": str(r["max_date"])
            })

        # Sort raw list: exact match first, then by stickers descending
        raw_list.sort(key=lambda x: (0 if "표준 일치" in x["reason"] else 1, -x["total_stickers"]))

        tot_stk = float(sub["total_stickers"].sum())
        tot_rows = int(sub["row_count"].sum())
        has_typo = any("오타" in x["reason"] for x in raw_list)
        has_space = any("띄어쓰기" in x["reason"] for x in raw_list)

        items_catalog.append({
            "canon_name": str(canon_name),
            "sku_code": str(sku),
            "mfg": str(mfg),
            "category": str(cat_full),
            "std_vol": str(std_vol),
            "total_stickers": tot_stk,
            "total_rows": tot_rows,
            "variants_count": len(raw_list),
            "has_typo": has_typo,
            "has_space": has_space,
            "raw_variants": raw_list
        })

    return lineage_df, multi_variant_items, items_catalog


def render_interactive_lineage_studio_html(items_catalog: list, initial_focus: str = "The빠새") -> str:
    """
    Renders an executive-grade, client-side interactive HTML5/SVG Flow Studio.
    Provides instant click-to-highlight lineage tracing, animated bezier ribbons,
    filter pills, and real-time search.
    """
    catalog_json = json.dumps(items_catalog, ensure_ascii=False)
    initial_focus_json = json.dumps(initial_focus, ensure_ascii=False)

    html_code = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #090d16;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Segoe UI", Roboto, sans-serif;
    padding: 12px 14px;
    user-select: none;
    overflow-x: hidden;
  }}

  /* Top HUD Banner */
  .hud-banner {{
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
    border: 1px solid rgba(56, 189, 248, 0.35);
    border-radius: 12px;
    padding: 12px 18px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    min-height: 52px;
  }}
  .hud-left {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13px;
    color: #94a3b8;
  }}
  .hud-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 10px #10b981;
    animation: pulseGlow 2s infinite;
  }}
  @keyframes pulseGlow {{
    0% {{ box-shadow: 0 0 4px #10b981; }}
    50% {{ box-shadow: 0 0 14px #10b981; }}
    100% {{ box-shadow: 0 0 4px #10b981; }}
  }}
  .hud-item-title {{
    font-size: 16px;
    font-weight: 800;
    color: #38bdf8;
    margin-right: 6px;
  }}
  .hud-badge {{
    background: rgba(56, 189, 248, 0.15);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.4);
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 14px;
  }}
  .hud-right {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .hud-stats {{
    display: flex;
    gap: 14px;
    font-size: 13px;
    color: #cbd5e1;
  }}
  .hud-reset-btn {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #f8fafc;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .hud-reset-btn:hover {{
    background: #38bdf8;
    color: #090d16;
    border-color: #38bdf8;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
  }}

  /* Filter & Search Bar */
  .control-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    gap: 10px;
  }}
  .filter-pills {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }}
  .filter-pill {{
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #94a3b8;
    font-size: 11px;
    font-weight: 600;
    padding: 5px 12px;
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .filter-pill:hover, .filter-pill.active {{
    background: rgba(56, 189, 248, 0.2);
    border-color: #38bdf8;
    color: #38bdf8;
    box-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
  }}
  .search-box {{
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    color: #f8fafc;
    padding: 6px 12px;
    font-size: 12px;
    width: 220px;
    outline: none;
    transition: border 0.2s;
  }}
  .search-box:focus {{
    border-color: #38bdf8;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
  }}

  /* Main Canvas Container */
  .canvas-wrap {{
    position: relative;
    background: #0b1120;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 16px;
    min-height: 540px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  }}
  .stage-headers {{
    display: grid;
    grid-template-columns: 1.15fr 0.75fr 1.15fr;
    gap: 24px;
    margin-bottom: 12px;
    position: relative;
    z-index: 2;
  }}
  .stage-hdr {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .columns-grid {{
    display: grid;
    grid-template-columns: 1.15fr 0.75fr 1.15fr;
    gap: 24px;
    position: relative;
    z-index: 2;
  }}
  .flow-col {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 480px;
    overflow-y: auto;
    padding-right: 4px;
  }}
  .flow-col::-webkit-scrollbar {{
    width: 4px;
  }}
  .flow-col::-webkit-scrollbar-thumb {{
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
  }}

  /* Cards Styling */
  .node-card {{
    background: rgba(30, 41, 59, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 9px 12px;
    cursor: pointer;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
  }}
  .node-card:hover {{
    background: rgba(30, 41, 59, 0.95);
    border-color: rgba(255, 255, 255, 0.25);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }}
  .node-card.active {{
    background: rgba(15, 23, 42, 0.95) !important;
    border-color: #38bdf8 !important;
    box-shadow: 0 0 16px rgba(56, 189, 248, 0.55) !important;
    transform: translateY(-2px);
  }}
  .node-card.dimmed {{
    opacity: 0.08 !important;
    filter: grayscale(85%);
  }}

  .raw-name {{
    font-size: 13px;
    font-weight: 700;
    color: #f8fafc;
    font-family: monospace;
    margin-bottom: 3px;
  }}
  .raw-meta {{
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: #94a3b8;
  }}
  .rule-tag {{
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 8px;
    display: inline-block;
  }}

  /* Rule Cards */
  .rule-node {{
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 10px 12px;
    cursor: pointer;
    transition: all 0.25s;
  }}
  .rule-node:hover {{
    border-color: rgba(255, 255, 255, 0.3);
  }}
  .rule-node.active {{
    box-shadow: 0 0 16px rgba(129, 140, 248, 0.5) !important;
    border-color: #818cf8 !important;
  }}
  .rule-node.dimmed {{
    opacity: 0.08 !important;
  }}
  .rule-title {{
    font-size: 12px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 2px;
  }}
  .rule-sub {{
    font-size: 10px;
    color: #64748b;
  }}

  /* Canonical Cards */
  .canon-node {{
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
    border: 1px solid rgba(99, 102, 241, 0.35);
    border-radius: 8px;
    padding: 10px 12px;
    cursor: pointer;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .canon-node:hover {{
    border-color: #818cf8;
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.3);
  }}
  .canon-node.active {{
    border-color: #38bdf8 !important;
    box-shadow: 0 0 20px rgba(56, 189, 248, 0.6) !important;
    background: linear-gradient(135deg, rgba(30, 58, 138, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
  }}
  .canon-node.dimmed {{
    opacity: 0.08 !important;
    filter: grayscale(85%);
  }}
  .canon-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 3px;
  }}
  .canon-sku {{
    font-size: 11px;
    color: #a5b4fc;
    font-family: monospace;
    font-weight: 700;
  }}
  .canon-name {{
    font-size: 14px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 3px;
  }}
  .canon-meta {{
    font-size: 11px;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
  }}

  /* SVG Links */
  #flow-svg {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 1;
  }}
  .flow-path {{
    fill: none;
    transition: stroke-opacity 0.25s, stroke-width 0.25s;
  }}
  .flow-path.active {{
    stroke-opacity: 0.95 !important;
    stroke-dasharray: 6 3;
    animation: flowDash 1.2s linear infinite;
    filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.8));
  }}
  .flow-path.dimmed {{
    stroke-opacity: 0.02 !important;
  }}
  @keyframes flowDash {{
    from {{ stroke-dashoffset: 24; }}
    to {{ stroke-dashoffset: 0; }}
  }}
</style>
</head>
<body>

<!-- HUD Banner -->
<div class="hud-banner" id="hudBanner">
  <div class="hud-left">
    <div class="hud-dot"></div>
    <div id="hudMsg">원하는 <strong>대표 표준 품목</strong> 또는 <strong>수기 기입명</strong>을 클릭하면 연결된 모든 데이터 계보가 네온 하이라이트됩니다.</div>
  </div>
  <div class="hud-right">
    <div class="hud-stats" id="hudStats"></div>
    <button class="hud-reset-btn" onclick="resetHighlight()">전체 보기 (Reset)</button>
  </div>
</div>

<!-- Controls -->
<div class="control-bar">
  <div class="filter-pills">
    <div class="filter-pill active" onclick="setFilter('top15', this)">🔥 3종 이상 분열군 (17개)</div>
    <div class="filter-pill" onclick="setFilter('typo', this)">🚨 수기 오타 교정군 (10개)</div>
    <div class="filter-pill" onclick="setFilter('space', this)">⚠️ 띄어쓰기 편차군 (150개)</div>
    <div class="filter-pill" onclick="setFilter('highvol', this)">💎 고물량 상위 TOP 20</div>
    <div class="filter-pill" onclick="setFilter('all', this)">🌐 전체 다중 표기군 (187개)</div>
  </div>
  <input type="text" class="search-box" id="searchBox" placeholder="🔎 품목명 실시간 검색..." oninput="handleSearch(this.value)">
</div>

<!-- Main Canvas -->
<div class="canvas-wrap" id="canvasWrap">
  <svg id="flow-svg"></svg>
  
  <div class="stage-headers">
    <div class="stage-hdr">
      <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#38bdf8;box-shadow:0 0 8px #38bdf8;"></span>
      <span>1. 원천 수기 기입 원장 (Raw Variants)</span>
    </div>
    <div class="stage-hdr">
      <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#818cf8;box-shadow:0 0 8px #818cf8;"></span>
      <span>2. 5-Layer AI 방어 엔진 (Rules)</span>
    </div>
    <div class="stage-hdr">
      <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981;"></span>
      <span>3. 공식 표준 마스터 골든 레코드 (Golden)</span>
    </div>
  </div>

  <div class="columns-grid">
    <div class="flow-col" id="rawCol"></div>
    <div class="flow-col" id="ruleCol"></div>
    <div class="flow-col" id="canonCol"></div>
  </div>
</div>

<script>
const ALL_ITEMS = {catalog_json};
const INITIAL_FOCUS = {initial_focus_json};

let currentFilter = 'top15';
let activeCanon = null;
let visibleItems = [];

function getRuleStyle(reason) {{
  if (reason.includes("오타")) return {{ color: "#f43f5e", bg: "rgba(244, 63, 94, 0.15)", border: "#f43f5e" }};
  if (reason.includes("띄어쓰기")) return {{ color: "#f59e0b", bg: "rgba(245, 158, 11, 0.15)", border: "#f59e0b" }};
  if (reason.includes("대소문자")) return {{ color: "#38bdf8", bg: "rgba(56, 189, 248, 0.15)", border: "#38bdf8" }};
  if (reason.includes("표준 일치")) return {{ color: "#10b981", bg: "rgba(16, 185, 129, 0.15)", border: "#10b981" }};
  return {{ color: "#a855f7", bg: "rgba(168, 85, 247, 0.15)", border: "#a855f7" }};
}}

function getFilteredItems() {{
  if (currentFilter === 'top15') {{
    return ALL_ITEMS.filter(x => x.variants_count >= 3);
  }} else if (currentFilter === 'typo') {{
    return ALL_ITEMS.filter(x => x.has_typo);
  }} else if (currentFilter === 'space') {{
    return ALL_ITEMS.filter(x => x.has_space);
  }} else if (currentFilter === 'highvol') {{
    return [...ALL_ITEMS].sort((a,b) => b.total_stickers - a.total_stickers).slice(0, 20);
  }} else {{
    return ALL_ITEMS;
  }}
}}

function setFilter(filt, btn) {{
  currentFilter = filt;
  document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('searchBox').value = '';
  renderCanvas();
}}

function renderCanvas() {{
  visibleItems = getFilteredItems();

  const rawCol = document.getElementById("rawCol");
  const ruleCol = document.getElementById("ruleCol");
  const canonCol = document.getElementById("canonCol");
  
  rawCol.innerHTML = "";
  ruleCol.innerHTML = "";
  canonCol.innerHTML = "";

  const rulesSet = new Set();
  visibleItems.forEach(it => {{
    it.raw_variants.forEach(rv => rulesSet.add(rv.reason));
  }});

  // Render Rules
  Array.from(rulesSet).forEach(rule => {{
    const st = getRuleStyle(rule);
    const div = document.createElement("div");
    div.className = "rule-node";
    div.id = `rule-${{rule.replace(/[^a-zA-Z0-9가-힣]/g, '_')}}`;
    div.innerHTML = `
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">
        <span style="width:7px;height:7px;border-radius:50%;background:${{st.color}};box-shadow:0 0 6px ${{st.color}};"></span>
        <div class="rule-title" style="color:${{st.color}};">${{rule.split('(')[0]}}</div>
      </div>
      <div class="rule-sub">${{rule}}</div>
    `;
    div.onclick = () => selectRule(rule);
    ruleCol.appendChild(div);
  }});

  // Render Items
  visibleItems.forEach(it => {{
    // Canon card
    const cDiv = document.createElement("div");
    cDiv.className = "canon-node";
    cDiv.id = `canon-${{it.canon_name}}`;
    cDiv.innerHTML = `
      <div class="canon-header">
        <span class="canon-sku">${{it.sku_code}}</span>
        <span style="background:rgba(16,185,129,0.15);color:#10b981;font-size:10px;font-weight:700;padding:1px 6px;border-radius:10px;">${{it.raw_variants.length}}종 수렴</span>
      </div>
      <div class="canon-name">${{it.canon_name}}</div>
      <div class="canon-meta">
        <span>${{it.mfg}}</span>
        <strong style="color:#38bdf8;">${{it.total_stickers.toLocaleString()}}매</strong>
      </div>
    `;
    cDiv.onclick = () => selectCanon(it.canon_name);
    canonCol.appendChild(cDiv);

    // Raw cards
    it.raw_variants.forEach(rv => {{
      const rDiv = document.createElement("div");
      rDiv.className = "node-card";
      rDiv.id = `raw-${{it.canon_name}}-${{rv.raw_name.replace(/[^a-zA-Z0-9가-힣]/g, '_')}}`;
      const rSt = getRuleStyle(rv.reason);
      rDiv.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
          <div class="raw-name">'${{rv.raw_name}}'</div>
          <span class="rule-tag" style="background:${{rSt.bg}};color:${{rSt.color}};border:1px solid ${{rSt.border}};">${{rv.reason.split('(')[0]}}</span>
        </div>
        <div class="raw-meta">
          <span>기록: <strong>${{rv.row_count}}건</strong></span>
          <span style="color:#cbd5e1;">작업량: <strong>${{rv.total_stickers.toLocaleString()}}매</strong></span>
        </div>
      `;
      rDiv.onclick = () => selectRaw(it.canon_name, rv.raw_name);
      rawCol.appendChild(rDiv);
    }});
  }});

  setTimeout(drawLinks, 60);

  // If initial focus item exists in visible items, focus it
  if (activeCanon && visibleItems.some(x => x.canon_name === activeCanon)) {{
    setTimeout(() => selectCanon(activeCanon), 100);
  }} else if (visibleItems.some(x => x.canon_name === INITIAL_FOCUS)) {{
    setTimeout(() => selectCanon(INITIAL_FOCUS), 100);
  }} else if (visibleItems.length > 0) {{
    setTimeout(() => selectCanon(visibleItems[0].canon_name), 100);
  }}
}}

function drawLinks() {{
  const svg = document.getElementById("flow-svg");
  const container = document.getElementById("canvasWrap");
  const cRect = container.getBoundingClientRect();

  svg.setAttribute("width", cRect.width);
  svg.setAttribute("height", cRect.height);
  svg.innerHTML = "";

  visibleItems.forEach(it => {{
    const cEl = document.getElementById(`canon-${{it.canon_name}}`);
    if (!cEl) return;
    const cRectEl = cEl.getBoundingClientRect();
    const cx = cRectEl.left - cRect.left;
    const cy = cRectEl.top - cRect.top + cRectEl.height / 2;

    it.raw_variants.forEach(rv => {{
      const rId = `raw-${{it.canon_name}}-${{rv.raw_name.replace(/[^a-zA-Z0-9가-힣]/g, '_')}}`;
      const rEl = document.getElementById(rId);
      const ruleId = `rule-${{rv.reason.replace(/[^a-zA-Z0-9가-힣]/g, '_')}}`;
      const ruleEl = document.getElementById(ruleId);
      if (!rEl || !ruleEl) return;

      const rRect = rEl.getBoundingClientRect();
      const rx = rRect.right - cRect.left;
      const ry = rRect.top - cRect.top + rRect.height / 2;

      const ruleRect = ruleEl.getBoundingClientRect();
      const ruLx = ruleRect.left - cRect.left;
      const ruRx = ruleRect.right - cRect.left;
      const ruy = ruleRect.top - cRect.top + ruleRect.height / 2;

      const st = getRuleStyle(rv.reason);

      // Path 1: Raw -> Rule
      const p1 = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const d1 = `M ${{rx}} ${{ry}} C ${{rx + 35}} ${{ry}}, ${{ruLx - 35}} ${{ruy}}, ${{ruLx}} ${{ruy}}`;
      p1.setAttribute("d", d1);
      p1.setAttribute("class", "flow-path");
      p1.setAttribute("data-canon", it.canon_name);
      p1.setAttribute("data-raw", rv.raw_name);
      p1.setAttribute("data-rule", rv.reason);
      p1.setAttribute("stroke", st.color);
      p1.setAttribute("stroke-width", "2");
      p1.setAttribute("stroke-opacity", "0.3");
      svg.appendChild(p1);

      // Path 2: Rule -> Canon
      const p2 = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const d2 = `M ${{ruRx}} ${{ruy}} C ${{ruRx + 35}} ${{ruy}}, ${{cx - 35}} ${{cy}}, ${{cx}} ${{cy}}`;
      p2.setAttribute("d", d2);
      p2.setAttribute("class", "flow-path");
      p2.setAttribute("data-canon", it.canon_name);
      p2.setAttribute("data-raw", rv.raw_name);
      p2.setAttribute("data-rule", rv.reason);
      p2.setAttribute("stroke", "#38bdf8");
      p2.setAttribute("stroke-width", "2.5");
      p2.setAttribute("stroke-opacity", "0.35");
      svg.appendChild(p2);
    }});
  }});
}}

function selectCanon(name) {{
  activeCanon = name;
  const it = ALL_ITEMS.find(x => x.canon_name === name);
  if (!it) return;

  // Update HUD
  document.getElementById("hudMsg").innerHTML = `
    👑 <span class="hud-item-title">[${{it.canon_name}}]</span>
    <span class="hud-badge">${{it.sku_code}}</span>
    수기 변형 <strong>${{it.raw_variants.length}}종</strong> ➔ 100% 무결 통합 골든 마스터
  `;
  document.getElementById("hudStats").innerHTML = `
    <span>총 수량: <strong style="color:#38bdf8;">${{it.total_stickers.toLocaleString()}}매</strong></span>
    <span>실적: <strong style="color:#10b981;">${{it.total_rows}}건</strong></span>
    <span>제조: <strong style="color:#cbd5e1;">${{it.mfg}}</strong></span>
  `;

  // Highlight elements
  document.querySelectorAll(".canon-node").forEach(el => {{
    el.classList.toggle("active", el.id === `canon-${{name}}`);
    el.classList.toggle("dimmed", el.id !== `canon-${{name}}`);
  }});

  const connectedRules = new Set(it.raw_variants.map(r => r.reason));
  document.querySelectorAll(".rule-node").forEach(el => {{
    const isConn = Array.from(connectedRules).some(r => el.id === `rule-${{r.replace(/[^a-zA-Z0-9가-힣]/g, '_')}}`);
    el.classList.toggle("active", isConn);
    el.classList.toggle("dimmed", !isConn);
  }});

  document.querySelectorAll(".node-card").forEach(el => {{
    const isConn = el.id.startsWith(`raw-${{name}}-`);
    el.classList.toggle("active", isConn);
    el.classList.toggle("dimmed", !isConn);
    if (isConn) {{
      el.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
    }}
  }});

  document.querySelectorAll(".flow-path").forEach(p => {{
    const isConn = p.getAttribute("data-canon") === name;
    p.classList.toggle("active", isConn);
    p.classList.toggle("dimmed", !isConn);
  }});
}}

function selectRaw(canonName, rawName) {{
  selectCanon(canonName);
}}

function selectRule(rule) {{
  document.getElementById("hudMsg").innerHTML = `
    ⚡ <span class="hud-item-title">[${{rule}}]</span> 엔진 규칙 적용 흐름 추적
  `;
  document.getElementById("hudStats").innerHTML = "";

  document.querySelectorAll(".rule-node").forEach(el => {{
    const isMatch = el.id === `rule-${{rule.replace(/[^a-zA-Z0-9가-힣]/g, '_')}}`;
    el.classList.toggle("active", isMatch);
    el.classList.toggle("dimmed", !isMatch);
  }});

  document.querySelectorAll(".flow-path").forEach(p => {{
    const isConn = p.getAttribute("data-rule") === rule;
    p.classList.toggle("active", isConn);
    p.classList.toggle("dimmed", !isConn);
  }});

  document.querySelectorAll(".canon-node, .node-card").forEach(el => {{
    el.classList.remove("active");
    el.classList.add("dimmed");
  }});

  document.querySelectorAll(`.flow-path[data-rule="${{rule}}"]`).forEach(p => {{
    const cName = p.getAttribute("data-canon");
    const cEl = document.getElementById(`canon-${{cName}}`);
    if (cEl) {{ cEl.classList.remove("dimmed"); cEl.classList.add("active"); }}

    const rName = p.getAttribute("data-raw");
    const rEl = document.getElementById(`raw-${{cName}}-${{rName.replace(/[^a-zA-Z0-9가-힣]/g, '_')}}`);
    if (rEl) {{ rEl.classList.remove("dimmed"); rEl.classList.add("active"); }}
  }});
}}

function resetHighlight() {{
  activeCanon = null;
  document.getElementById("hudMsg").innerHTML = `원하는 <strong>대표 표준 품목</strong> 또는 <strong>수기 기입명</strong>을 클릭하면 연결된 모든 데이터 계보가 네온 하이라이트됩니다.`;
  document.getElementById("hudStats").innerHTML = "";

  document.querySelectorAll(".canon-node, .rule-node, .node-card").forEach(el => {{
    el.classList.remove("active");
    el.classList.remove("dimmed");
  }});
  document.querySelectorAll(".flow-path").forEach(p => {{
    p.classList.remove("active");
    p.classList.remove("dimmed");
  }});
}}

function handleSearch(q) {{
  if (!q.trim()) {{
    resetHighlight();
    return;
  }}
  const term = q.toLowerCase();
  const match = ALL_ITEMS.find(it => 
    it.canon_name.toLowerCase().includes(term) ||
    it.raw_variants.some(r => r.raw_name.toLowerCase().includes(term))
  );
  if (match) {{
    // If not visible in current filter, add it
    if (!visibleItems.some(x => x.canon_name === match.canon_name)) {{
      visibleItems.unshift(match);
      renderCanvas();
    }}
    selectCanon(match.canon_name);
  }}
}}

window.addEventListener("resize", drawLinks);
window.onload = () => {{
  renderCanvas();
}};
</script>
</body>
</html>
"""
    return html_code


def build_value_chain_sankey(base_sc_df: pd.DataFrame, focus_buyer: str = None, isolate_buyer: bool = False):
    """
    Builds an executive-grade 3-stage Supply Chain Value Chain Sankey diagram (Buyer -> Mfg -> Category).
    Includes distinct signature brand colors per buyer and interactive focus highlighting.
    """
    top_s_buyers = base_sc_df.groupby("buyer_normalized")["sticker_qty"].sum().nlargest(7).index.tolist()
    top_s_mfgs = base_sc_df.groupby("manufacturer")["sticker_qty"].sum().nlargest(6).index.tolist()
    top_s_cats = base_sc_df.groupby("category_2")["sticker_qty"].sum().nlargest(5).index.tolist()

    df_sankey = base_sc_df.copy()
    if isolate_buyer and focus_buyer and focus_buyer != "전체 공급망 종합 흐름 (Overview)":
        df_sankey = df_sankey[df_sankey["buyer_normalized"] == focus_buyer].copy()

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

    # Distinct curated brand colors for buyers
    buyer_color_map = {
        "신세계푸드": ("#2563eb", "rgba(37, 99, 235, 0.6)"),
        "오리온베트남": ("#059669", "rgba(5, 150, 105, 0.6)"),
        "롯데상사": ("#d97706", "rgba(217, 119, 6, 0.6)"),
        "CJ제일제당": ("#e11d48", "rgba(225, 29, 72, 0.6)"),
        "이마트": ("#7c3aed", "rgba(124, 58, 237, 0.6)"),
        "농협하나로": ("#0891b2", "rgba(8, 145, 178, 0.6)"),
        "기타": ("#64748b", "rgba(100, 116, 139, 0.35)")
    }

    node_colors = []
    for n in all_nodes:
        if n.startswith("바이어:"):
            b_name = n.replace("바이어: ", "")
            c_found = None
            for k, (solid, _) in buyer_color_map.items():
                if k in b_name:
                    c_found = solid
                    break
            node_colors.append(c_found or "#3b82f6")
        elif n.startswith("제조:"):
            node_colors.append("#10b981")
        else:
            node_colors.append("#8b5cf6")

    link_sources = [node_map[s] for s in flow1["source"]] + [node_map[s] for s in flow2["source"]]
    link_targets = [node_map[t] for t in flow1["target"]] + [node_map[t] for t in flow2["target"]]
    link_values = flow1["value"].tolist() + flow2["value"].tolist()

    link_colors = []
    # Flow 1 link colors (Buyer -> Mfg)
    for _, r in flow1.iterrows():
        b_name = r["source"].replace("바이어: ", "")
        rgba = "rgba(148, 163, 184, 0.3)"
        for k, (_, c_rgba) in buyer_color_map.items():
            if k in b_name:
                rgba = c_rgba
                break
        
        # If focus buyer is active and not matching, dim it
        if focus_buyer and focus_buyer != "전체 공급망 종합 흐름 (Overview)":
            if focus_buyer not in b_name:
                rgba = "rgba(148, 163, 184, 0.08)"
            else:
                rgba = rgba.replace("0.6", "0.9")
        link_colors.append(rgba)

    # Flow 2 link colors (Mfg -> Category)
    for _, r in flow2.iterrows():
        if focus_buyer and focus_buyer != "전체 공급망 종합 흐름 (Overview)":
            link_colors.append("rgba(139, 92, 246, 0.55)")
        else:
            link_colors.append("rgba(148, 163, 184, 0.25)")

    sankey_fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=24,
            thickness=24,
            line=dict(color="#334155", width=1),
            label=all_nodes,
            color=node_colors,
            hovertemplate="<b>%{label}</b><br>총 물량: <b>%{value:,.0f} 매</b><extra></extra>"
        ),
        link=dict(
            source=link_sources,
            target=link_targets,
            value=link_values,
            color=link_colors,
            hovertemplate="<b>%{source.label}</b> ➔ <b>%{target.label}</b><br>작업량: <b>%{value:,.0f} 매</b><extra></extra>"
        )
    )])

    sankey_fig.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        dragmode=False,
        height=480,
        margin=dict(l=15, r=15, t=25, b=25),
        font=dict(family="Pretendard, -apple-system, sans-serif", size=12, color="#f8fafc")
    )

    return sankey_fig
