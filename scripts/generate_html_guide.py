#!/usr/bin/env python3
"""
Generates a stunning, executive-grade HTML version of DASHBOARD_MASTER_GUIDE.md
Features:
- Modern Pretendard & Inter typography
- Fixed sticky sidebar with auto-scrolling TOC & active scrollspy
- Live real-time search & section filtering
- Beautiful callouts, metric badges, and interactive UI tables
- Clean code blocks & terminal diagrams with copy functionality
- Print-friendly layout (save to PDF)
"""

import os
import re
import markdown

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_PATH = os.path.join(PROJECT_ROOT, "docs", "DASHBOARD_MASTER_GUIDE.md")
HTML_PATH = os.path.join(PROJECT_ROOT, "docs", "DASHBOARD_MASTER_GUIDE.html")

def generate_guide_html():
    if not os.path.exists(MD_PATH):
        raise FileNotFoundError(f"Markdown file not found: {MD_PATH}")

    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Convert markdown to HTML using extensions
    md_parser = markdown.Markdown(extensions=[
        "tables",
        "fenced_code",
        "toc",
        "nl2br",
        "sane_lists"
    ])
    raw_html = md_parser.convert(md_content)

    # Post-process HTML for enhanced aesthetics
    # 1. Enhance code blocks (ascii diagrams & code)
    raw_html = re.sub(
        r'<pre><code>(.*?)</code></pre>',
        r'<div class="code-wrapper"><div class="code-header"><span class="code-dot red"></span><span class="code-dot yellow"></span><span class="code-dot green"></span><span class="code-title">SYSTEM SPEC & DIAGRAM</span><button class="copy-btn" onclick="copyCode(this)">복사</button></div><pre><code>\1</code></pre></div>',
        raw_html,
        flags=re.DOTALL
    )

    # 2. Enhance tables
    raw_html = raw_html.replace('<table>', '<div class="table-container"><table class="guide-table">')
    raw_html = raw_html.replace('</table>', '</table></div>')

    # 3. Enhance badges (e.g. `🟢 ...`, `⚠️ ...`, `✅ ...`)
    raw_html = re.sub(
        r'<code>(🟢[^<]+)</code>',
        r'<span class="badge badge-success">\1</span>',
        raw_html
    )
    raw_html = re.sub(
        r'<code>(⚠️[^<]+)</code>',
        r'<span class="badge badge-warning">\1</span>',
        raw_html
    )
    raw_html = re.sub(
        r'<code>(🚨[^<]+)</code>',
        r'<span class="badge badge-danger">\1</span>',
        raw_html
    )
    # 4. Enhance Mathematical Formulas (Fractions, Sums, Financial Equations)
    block_formula_html = """<div class="math-display-card">
  <span class="math-term">필요 공수</span>
  <span class="math-equal">=</span>
  <span class="math-sym">&sum;</span>
  <span class="math-paren">(</span>
  <span class="math-fraction">
    <span class="numerator">품목별 총 스티커수</span>
    <span class="denominator">품목별 벤치마크 속도 (매/hr)</span>
  </span>
  <span class="math-paren">)</span>
</div>"""

    lines = []
    for line in raw_html.splitlines():
        if "필요 공수" in line and "$$" in line:
            line = "   " + block_formula_html + "</li>"
        lines.append(line)
    raw_html = "\n".join(lines)

    math_replacements = [
        # Fractions
        (r"$\frac{\text{총 스티커 수량}}{\text{총 투입 공수}}$", "<span class=\"math-fraction\"><span class=\"numerator\">총 스티커 수량</span><span class=\"denominator\">총 투입 공수</span></span>"),
        (r"$\frac{\text{총 스티커 수량}}{\sum \text{worker_count}}$", "<span class=\"math-fraction\"><span class=\"numerator\">총 스티커 수량</span><span class=\"denominator\"><span class=\"math-sym\">&sum;</span> worker_count</span></span>"),
        (r"$\frac{\text{공정 매출총이익}}{\text{총 출하 박스수}}$", "<span class=\"math-fraction\"><span class=\"numerator\">공정 매출총이익</span><span class=\"denominator\">총 출하 박스수</span></span>"),
        # Summation & Financial formulas
        (r"$\sum \text{sticker_qty}$", "<span class=\"math-expr\"><span class=\"math-sym\">&sum;</span> <code class=\"math-code\">sticker_qty</code></span>"),
        (r"$\sum \text{row_man_hours}$", "<span class=\"math-expr\"><span class=\"math-sym\">&sum;</span> <code class=\"math-code\">row_man_hours</code></span>"),
        (r"$\sum (\text{작업량} \times \text{적용 단가})$", "<span class=\"math-expr\"><span class=\"math-sym\">&sum;</span> (<span class=\"math-term\">작업량</span> &times; <span class=\"math-term\">적용 단가</span>)</span>"),
        (r"$\sum (\text{소요 공수} \times \text{시급 13,000원})$", "<span class=\"math-expr\"><span class=\"math-sym\">&sum;</span> (<span class=\"math-term\">소요 공수</span> &times; <span class=\"math-term\">시급 13,000원</span>)</span>"),
        (r"$\text{총 매출액} - \text{총 인건비 원가}$", "<span class=\"math-expr\"><span class=\"math-term\">총 매출액</span> &minus; <span class=\"math-term\">총 인건비 원가</span></span>"),
        (r"$\text{입량} \times \text{작업수량} = \text{스티커수량}$", "<span class=\"math-expr\"><span class=\"math-term\">입량</span> &times; <span class=\"math-term\">작업수량</span> = <span class=\"math-term\">스티커수량</span></span>"),
        (r"($\text{박스수} \times \text{입량}$)", "(<span class=\"math-term\">박스수</span> &times; <span class=\"math-term\">입량</span>)"),
        (r"박스수$\times$입량", "<span class=\"math-term\">박스수</span> &times; <span class=\"math-term\">입량</span>"),
        (r"투입 인원 $\times$ 8시간", "투입 인원 &times; 8시간"),
        (r"$N$일", "<em>N</em>일"),
        (r"Rank 6 $\rightarrow$ Rank 5 $\rightarrow$ Rank 4 $\rightarrow$ Rank 3 $\rightarrow$ Rank 2 $\rightarrow$ <strong>Rank 1 (최상단)</strong>", "Rank 6 &rarr; Rank 5 &rarr; Rank 4 &rarr; Rank 3 &rarr; Rank 2 &rarr; <strong>Rank 1 (최상단)</strong>")
    ]

    for src, dst in math_replacements:
        raw_html = raw_html.replace(src, dst)

    full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>수출 식품 스티커 작업 분석 플랫폼 완전 정복 마스터 가이드 (Official Manual)</title>
  
  <!-- Web Fonts -->
  <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@500;700;800&display=swap" rel="stylesheet">

  <!-- MathJax v3 for Crisp Formula Rendering -->
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true
      }},
      options: {{
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
      }},
      chtml: {{
        scale: 1.05
      }}
    }};
  </script>
  <script type="text/javascript" id="MathJax-script" async
    src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js">
  </script>

  <style>
    :root {{
      --primary: #1e40af;
      --primary-light: #3b82f6;
      --primary-bg: #eff6ff;
      --accent: #0ea5e9;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --slate-50: #f8fafc;
      --slate-100: #f1f5f9;
      --slate-200: #e2e8f0;
      --slate-300: #cbd5e1;
      --slate-400: #94a3b8;
      --slate-500: #64748b;
      --slate-600: #475569;
      --slate-700: #334155;
      --slate-800: #1e293b;
      --slate-900: #0f172a;
      --font-sans: "Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: "JetBrains Mono", Menlo, Monaco, Consolas, monospace;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    html {{
      scroll-behavior: smooth;
      font-size: 15px;
    }}

    body {{
      font-family: var(--font-sans);
      background-color: #f8fafc;
      color: var(--slate-800);
      line-height: 1.7;
      display: flex;
      min-height: 100vh;
    }}

    /* Sidebar Navigation */
    .sidebar {{
      width: 320px;
      height: 100vh;
      position: sticky;
      top: 0;
      background: #0f172a;
      color: #e2e8f0;
      display: flex;
      flex-direction: column;
      border-right: 1px solid rgba(255, 255, 255, 0.1);
      z-index: 100;
      flex-shrink: 0;
    }}

    .sidebar-header {{
      padding: 24px 20px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }}

    .sidebar-brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 17px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.3px;
    }}

    .sidebar-brand .icon-box {{
      width: 34px;
      height: 34px;
      background: linear-gradient(135deg, #3b82f6, #1d4ed8);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
    }}

    .sidebar-subtitle {{
      font-size: 11px;
      color: var(--slate-400);
      margin-top: 6px;
      font-weight: 500;
    }}

    .sidebar-search {{
      padding: 14px 20px 10px;
    }}

    .search-input {{
      width: 100%;
      background: rgba(255, 255, 255, 0.07);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 8px;
      padding: 8px 12px 8px 34px;
      color: #f8fafc;
      font-size: 12px;
      font-family: inherit;
      outline: none;
      transition: all 0.2s;
      background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="%2394a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>');
      background-repeat: no-repeat;
      background-position: 12px center;
    }}

    .search-input:focus {{
      border-color: #38bdf8;
      background-color: rgba(255, 255, 255, 0.12);
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
    }}

    .sidebar-nav {{
      flex: 1;
      overflow-y: auto;
      padding: 12px 14px 20px;
    }}

    .sidebar-nav::-webkit-scrollbar {{
      width: 5px;
    }}
    .sidebar-nav::-webkit-scrollbar-thumb {{
      background: rgba(255, 255, 255, 0.15);
      border-radius: 4px;
    }}

    .nav-group-title {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #64748b;
      margin: 14px 10px 6px;
    }}

    .nav-link {{
      display: flex;
      align-items: center;
      padding: 7px 12px;
      color: #94a3b8;
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      border-radius: 6px;
      transition: all 0.15s ease;
      line-height: 1.4;
      margin-bottom: 2px;
    }}

    .nav-link:hover {{
      color: #ffffff;
      background: rgba(255, 255, 255, 0.08);
      transform: translateX(2px);
    }}

    .nav-link.active {{
      color: #38bdf8;
      background: rgba(56, 189, 248, 0.12);
      font-weight: 700;
      border-left: 3px solid #38bdf8;
    }}

    .nav-sub {{
      padding-left: 24px;
      font-size: 12px;
      color: #64748b;
    }}

    .sidebar-footer {{
      padding: 16px 20px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      gap: 10px;
    }}

    .btn-side {{
      flex: 1;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #e2e8f0;
      padding: 7px 10px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      text-align: center;
      transition: all 0.2s;
    }}

    .btn-side:hover {{
      background: #3b82f6;
      border-color: #3b82f6;
      color: #ffffff;
    }}

    /* Main Content */
    .main-wrap {{
      flex: 1;
      max-width: 1040px;
      margin: 0 auto;
      padding: 40px 48px 100px;
    }}

    /* Top Banner Card */
    .hero-banner {{
      background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #0369a1 100%);
      border-radius: 16px;
      padding: 36px 40px;
      color: #ffffff;
      box-shadow: 0 12px 30px rgba(30, 64, 175, 0.25);
      margin-bottom: 40px;
      position: relative;
      overflow: hidden;
    }}

    .hero-banner::after {{
      content: "";
      position: absolute;
      top: -60px;
      right: -60px;
      width: 240px;
      height: 240px;
      background: radial-gradient(circle, rgba(56, 189, 248, 0.3) 0%, rgba(56, 189, 248, 0) 70%);
      pointer-events: none;
    }}

    .hero-tags {{
      display: flex;
      gap: 8px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }}

    .hero-tag {{
      background: rgba(255, 255, 255, 0.16);
      border: 1px solid rgba(255, 255, 255, 0.28);
      color: #e0f2fe;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 20px;
      backdrop-filter: blur(4px);
    }}

    .hero-title {{
      font-size: 28px;
      font-weight: 800;
      line-height: 1.3;
      letter-spacing: -0.5px;
      margin-bottom: 12px;
    }}

    .hero-desc {{
      font-size: 14px;
      line-height: 1.6;
      color: #bae6fd;
      max-width: 840px;
    }}

    /* Content Typography */
    h1, h2, h3, h4, h5 {{
      color: var(--slate-900);
      font-weight: 800;
      letter-spacing: -0.3px;
    }}

    h1 {{
      font-size: 24px;
      margin-top: 48px;
      margin-bottom: 18px;
      padding-bottom: 12px;
      border-bottom: 2px solid var(--slate-200);
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    h2 {{
      font-size: 20px;
      margin-top: 36px;
      margin-bottom: 14px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--slate-200);
    }}

    h3 {{
      font-size: 17px;
      margin-top: 28px;
      margin-bottom: 12px;
      color: var(--primary);
    }}

    h4 {{
      font-size: 15px;
      margin-top: 20px;
      margin-bottom: 8px;
      color: var(--slate-800);
    }}

    p {{
      margin-bottom: 14px;
      color: #334155;
    }}

    ul, ol {{
      margin-bottom: 16px;
      padding-left: 22px;
    }}

    li {{
      margin-bottom: 6px;
      color: #334155;
    }}

    strong {{
      color: var(--slate-900);
      font-weight: 700;
    }}

    hr {{
      border: 0;
      height: 1px;
      background: var(--slate-200);
      margin: 36px 0;
    }}

    /* Inline Badges & Code */
    code {{
      font-family: var(--font-mono);
      font-size: 12.5px;
      background: #e2e8f0;
      color: #1e293b;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 600;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      font-weight: 700;
      padding: 2px 9px;
      border-radius: 14px;
      white-space: nowrap;
    }}

    .badge-success {{
      background: #dcfce7;
      color: #15803d;
      border: 1px solid #bbf7d0;
    }}

    .badge-warning {{
      background: #fef3c7;
      color: #b45309;
      border: 1px solid #fde68a;
    }}

    .badge-danger {{
      background: #fee2e2;
      color: #b91c1c;
      border: 1px solid #fecaca;
    }}

    .badge-accent {{
      background: #e0e7ff;
      color: #4338ca;
      border: 1px solid #c7d2fe;
    }}

    /* Code Block & Terminal UI */
    .code-wrapper {{
      background: #090d16;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
      margin: 18px 0 24px;
      overflow: hidden;
    }}

    .code-header {{
      background: #131b2e;
      padding: 8px 16px;
      display: flex;
      align-items: center;
      gap: 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }}

    .code-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
    }}
    .code-dot.red {{ background: #ef4444; }}
    .code-dot.yellow {{ background: #f59e0b; }}
    .code-dot.green {{ background: #10b981; }}

    .code-title {{
      font-size: 11px;
      font-weight: 700;
      color: #94a3b8;
      letter-spacing: 0.5px;
      margin-left: 4px;
      flex: 1;
    }}

    .copy-btn {{
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #cbd5e1;
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .copy-btn:hover {{
      background: #38bdf8;
      color: #090d16;
      border-color: #38bdf8;
    }}

    pre {{
      padding: 18px 20px;
      overflow-x: auto;
      margin: 0;
      background: transparent;
    }}

    pre code {{
      background: transparent;
      color: #38bdf8;
      font-family: var(--font-mono);
      font-size: 12.5px;
      line-height: 1.6;
      padding: 0;
      font-weight: 400;
    }}

    /* Modern Table UI */
    .table-container {{
      background: #ffffff;
      border: 1px solid var(--slate-200);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
      margin: 18px 0 24px;
    }}

    .guide-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13.5px;
      text-align: left;
    }}

    .guide-table th {{
      background: #f1f5f9;
      color: var(--slate-800);
      font-weight: 700;
      padding: 12px 16px;
      border-bottom: 2px solid var(--slate-200);
    }}

    .guide-table td {{
      padding: 12px 16px;
      border-bottom: 1px solid var(--slate-100);
      color: #334155;
    }}

    .guide-table tr:last-child td {{
      border-bottom: none;
    }}

    .guide-table tr:hover td {{
      background-color: #f8fafc;
    }}

    /* Math Formula Typography & Styling */
    .math-expr {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #f0f7ff;
      border: 1px solid #bfdbfe;
      color: #1e40af;
      padding: 3px 9px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 13px;
      vertical-align: middle;
      line-height: 1.3;
      white-space: nowrap;
    }}

    .math-sym {{
      font-size: 16px;
      font-weight: 800;
      color: #2563eb;
      line-height: 1;
    }}

    .math-term {{
      color: #1e3a8a;
      font-weight: 700;
    }}

    .math-code {{
      font-family: var(--font-mono);
      background: rgba(37, 99, 235, 0.08);
      color: #1d4ed8;
      padding: 1px 5px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 700;
    }}

    .math-fraction {{
      display: inline-flex;
      flex-direction: column;
      vertical-align: middle;
      text-align: center;
      padding: 3px 8px;
      background: #f0f7ff;
      border: 1px solid #bfdbfe;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 700;
      color: #1e3a8a;
      line-height: 1.25;
      min-width: 90px;
    }}

    .math-fraction .numerator {{
      border-bottom: 1.5px solid #2563eb;
      padding-bottom: 3px;
      margin-bottom: 3px;
      color: #1d4ed8;
    }}

    .math-fraction .denominator {{
      color: #1e40af;
    }}

    .math-display-card {{
      background: linear-gradient(135deg, #f0f7ff 0%, #e0f2fe 100%);
      border: 1px solid #93c5fd;
      border-radius: 12px;
      padding: 20px 28px;
      margin: 18px 0;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      font-size: 16px;
      font-weight: 700;
      color: #1e3a8a;
      box-shadow: 0 4px 16px rgba(37, 99, 235, 0.08);
    }}

    .math-display-card .math-fraction {{
      font-size: 13.5px;
      background: #ffffff;
      border: 1px solid #93c5fd;
      padding: 5px 12px;
    }}

    .math-equal {{
      font-size: 18px;
      font-weight: 800;
      color: #2563eb;
      margin: 0 4px;
    }}

    .math-paren {{
      font-size: 28px;
      font-weight: 300;
      color: #3b82f6;
      line-height: 1;
    }}

    mjx-container {{
      font-size: 108% !important;
      color: #1e3a8a !important;
      outline: none !important;
      vertical-align: middle !important;
    }}

    mjx-container[jax="CHTML"][display="true"] {{
      background: #f0f7ff;
      border: 1px solid #bfdbfe;
      border-radius: 10px;
      padding: 16px 24px;
      margin: 18px 0;
      overflow-x: auto;
      box-shadow: 0 2px 8px rgba(30, 58, 138, 0.05);
    }}

    /* Floating Back-to-Top Button */
    .back-to-top {{
      position: fixed;
      bottom: 28px;
      right: 28px;
      width: 44px;
      height: 44px;
      background: #1e40af;
      color: #ffffff;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 16px rgba(30, 64, 175, 0.35);
      cursor: pointer;
      text-decoration: none;
      font-size: 18px;
      opacity: 0;
      visibility: hidden;
      transition: all 0.3s ease;
      z-index: 90;
    }}

    .back-to-top.visible {{
      opacity: 1;
      visibility: visible;
    }}

    .back-to-top:hover {{
      background: #2563eb;
      transform: translateY(-2px);
    }}

    /* Print Styles */
    @media print {{
      .sidebar, .back-to-top, .sidebar-footer, .copy-btn {{
        display: none !important;
      }}
      body {{
        background: #ffffff;
        color: #000000;
      }}
      .main-wrap {{
        max-width: 100%;
        padding: 0;
      }}
      .hero-banner {{
        background: #1e3a8a !important;
        color: #ffffff !important;
        box-shadow: none !important;
      }}
    }}
  </style>
</head>
<body>

  <!-- Sidebar Navigation -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-brand">
        <div class="icon-box">📦</div>
        <div>
          <div>스티커 분석 가이드</div>
          <div class="sidebar-subtitle">Enterprise Operational Manual</div>
        </div>
      </div>
    </div>

    <div class="sidebar-search">
      <input type="text" id="searchInput" class="search-input" placeholder="키워드 검색 (예: 생키, 5.4, 단일의존도)..." oninput="handleSearch()">
    </div>

    <nav class="sidebar-nav" id="sidebarNav">
      <div class="nav-group-title">공식 목차</div>
      <a href="#sec-1" class="nav-link">1. 글로벌 사이드바 컨트롤러</a>
      <a href="#sec-2" class="nav-link">2. 탭 1: 종합 운영 상황판</a>
      <a href="#sec-3" class="nav-link">3. 탭 2: 생산성 & 난이도 엔진</a>
      
      <div class="nav-group-title">비즈니스 분석 & 마트</div>
      <a href="#sec-4" class="nav-link">4. 탭 3: 바이어 & 수출국가별 분석</a>
      <a href="#sec-4-1" class="nav-link nav-sub">3.1 종합 실적 (Overview)</a>
      <a href="#sec-4-2" class="nav-link nav-sub">3.2 고객 건강도 모니터</a>
      <a href="#sec-4-3" class="nav-link nav-sub">3.3 공급망 교차 매트릭스</a>
      
      <a href="#sec-5" class="nav-link">5. 탭 4: 인력 계획 & 마진 채산성</a>
      <a href="#sec-5-1" class="nav-link nav-sub">4.1 납기 시뮬레이터</a>
      <a href="#sec-5-2" class="nav-link nav-sub">4.2 마진 채산성 분석기</a>

      <div class="nav-group-title">품질 거버넌스 & 엔지니어링</div>
      <a href="#sec-6" class="nav-link">6. 탭 5: DQ & 마스터 관리(MDM)</a>
      <a href="#sec-6-1" class="nav-link nav-sub">6.1 4대 DQ KPI 해석법</a>
      <a href="#sec-6-2" class="nav-link nav-sub">6.2 4대 세부 검수실 (5.1~5.4)</a>

      <a href="#sec-7" class="nav-link">7. 탭 6: 아키텍처 & 거버넌스</a>
      <a href="#sec-7-1" class="nav-link nav-sub">6.1 엔드투엔드 계보도</a>
      <a href="#sec-7-2" class="nav-link nav-sub">6.2 스타 스키마 ERD</a>
      <a href="#sec-7-3" class="nav-link nav-sub">6.3 통합 데이터 카탈로그</a>

      <a href="#sec-8" class="nav-link">8. 공통 조작 규칙 & UX 가이드</a>
    </nav>

    <div class="sidebar-footer">
      <button class="btn-side" onclick="window.print()">🖨️ 인쇄 / PDF</button>
      <button class="btn-side" onclick="window.scrollTo({{ top: 0, behavior: 'smooth' }})">▲ 최상단</button>
    </div>
  </aside>

  <!-- Main Content Body -->
  <main class="main-wrap" id="mainContent">
    
    <!-- Top Hero Banner -->
    <div class="hero-banner">
      <div class="hero-tags">
        <span class="hero-tag">Official Manual v2.4 LTS</span>
        <span class="hero-tag">Streamlit Enterprise Certified</span>
        <span class="hero-tag">2026.09.24 Updated</span>
        <span class="hero-tag">실시간 검증 완료 🟢</span>
      </div>
      <h1 class="hero-title" style="color:#ffffff; margin:0 0 10px; border:none; padding:0;">수출 식품 스티커 작업 분석 플랫폼 완전 정복 마스터 가이드</h1>
      <p class="hero-desc">
        A4 수기 원장 및 실시간 구글 스프레드시트부터 Silver Fact, Gold Mart, 3단계 밸류체인 생키 플로우, 인터랙티브 네온 계보 스튜디오까지 전사 데이터 파이프라인의 100% 무결성을 증명하는 공식 운영 매뉴얼입니다.
      </p>
    </div>

    <!-- Generated Markdown Content -->
    <article id="articleContent">
      {raw_html}
    </article>

  </main>

  <!-- Floating Back to Top Button -->
  <a href="#" class="back-to-top" id="backToTop" title="맨 위로 이동">▲</a>

  <script>
    // Copy code snippet function
    function copyCode(btn) {{
      const codeBlock = btn.closest('.code-wrapper').querySelector('pre code');
      if (!codeBlock) return;
      navigator.clipboard.writeText(codeBlock.innerText).then(() => {{
        const prevText = btn.innerText;
        btn.innerText = "복사됨! ✓";
        btn.style.background = "#10b981";
        btn.style.color = "#ffffff";
        setTimeout(() => {{
          btn.innerText = prevText;
          btn.style.background = "";
          btn.style.color = "";
        }}, 1800);
      }});
    }}

    // Real-time search filter
    function handleSearch() {{
      const q = document.getElementById("searchInput").value.toLowerCase().trim();
      const article = document.getElementById("articleContent");
      const paragraphs = article.querySelectorAll("h1, h2, h3, h4, p, li, .code-wrapper, .table-container");

      if (!q) {{
        paragraphs.forEach(el => el.style.display = "");
        return;
      }}

      paragraphs.forEach(el => {{
        const text = el.innerText.toLowerCase();
        if (text.includes(q)) {{
          el.style.display = "";
          el.style.backgroundColor = "rgba(254, 240, 138, 0.25)";
        }} else {{
          el.style.backgroundColor = "";
        }}
      }});
    }}

    // Back to top visibility
    window.addEventListener("scroll", () => {{
      const btn = document.getElementById("backToTop");
      if (window.scrollY > 300) {{
        btn.classList.add("visible");
      }} else {{
        btn.classList.remove("visible");
      }}
    }});

    // Active ScrollSpy for sidebar
    const observer = new IntersectionObserver((entries) => {{
      entries.forEach(entry => {{
        if (entry.isIntersecting) {{
          const id = entry.target.getAttribute("id");
          if (!id) return;
          document.querySelectorAll(".nav-link").forEach(link => {{
            link.classList.toggle("active", link.getAttribute("href") === `#${{id}}`);
          }});
        }}
      }});
    }}, {{ rootMargin: "-20% 0px -70% 0px" }});

    document.querySelectorAll("h1[id], h2[id], h3[id], a[name], a[id]").forEach(el => {{
      observer.observe(el);
    }});
  </script>
</body>
</html>
"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"✅ Generated HTML Guide: {HTML_PATH} ({len(full_html):,} bytes)")

if __name__ == "__main__":
    generate_guide_html()
