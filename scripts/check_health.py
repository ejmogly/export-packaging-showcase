"""
System Health & Integrity Audit Script
================================================================================
실제로 점검한 결과만 출력합니다. 점검할 수 없는 항목은 '확인 불가(SKIP)'로
명시하며, 하드코딩된 "정상" 문구를 출력하지 않습니다.

판정 기준:
    PASS  - 실제 점검 결과 정상
    WARN  - 동작은 하지만 주의가 필요
    FAIL  - 비정상 (종료 코드 1)
    SKIP  - 이 환경에서 점검 불가 (사유 함께 표시)
    INFO  - 판정 없이 참고 정보만 표시

Usage:
    python scripts/check_health.py              # 전체 점검
    python scripts/check_health.py --skip-tests # 단위 테스트 생략 (빠른 점검)

Optional:
    GITHUB_TOKEN (또는 GH_TOKEN) 환경변수를 설정하면 비공개 저장소의
    GitHub Actions 최근 실행 결과까지 조회합니다.
================================================================================
"""

import io
import json
import os
import re
import subprocess
import sys
import unittest
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from src.ingestion.loader import get_configured_sheet_url  # noqa: E402
from src.transformation.silver_pipeline import build_silver_layer  # noqa: E402

ICONS = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌", "SKIP": "⏭️ ", "INFO": "ℹ️ "}
RESULTS = []  # (section, level, label, detail)

# Workflow expectations: file -> list of expected cron expressions
EXPECTED_WORKFLOWS = {
    "daily_pipeline.yml": ["0 0 * * *"],
    "monthly_report.yml": ["50 11 28-31 * *", "0 0 1 * *"],
}
REQUIRED_EMAIL_SECRETS = ["SMTP_USER", "SMTP_PASSWORD", "RECIPIENT_EMAILS"]


def record(section, level, label, detail=""):
    RESULTS.append((section, level, label, detail))
    line = f"  {ICONS[level]} [{level}] {label}"
    if detail:
        line += f"\n         └ {detail}"
    print(line)


# ------------------------------------------------------------------------------
# 1. Data pipeline
# ------------------------------------------------------------------------------
def check_data_pipeline(today):
    sec = "데이터"
    print("\n[1/4] 📊 데이터 파이프라인")
    showcase_mode = get_configured_sheet_url() is None

    try:
        df, dq, source = build_silver_layer()
    except Exception as e:  # pragma: no cover - surfaced to user
        record(sec, "FAIL", "Silver 레이어 생성 실패", repr(e))
        return

    # 1-1. Data source (live vs fallback)
    if showcase_mode:
        record(sec, "INFO", "데이터 소스: 쇼케이스 모드(익명화 로컬 데이터)", source)
    elif str(source).startswith("Live Google Sheet"):
        record(sec, "PASS", "구글 시트 실시간 연동", source)
    else:
        record(sec, "WARN", "구글 시트 연동 실패 → 로컬 캐시로 대체됨", source)

    # 1-2. Freshness (business-day gap, Korean public holidays not considered)
    dates = df["work_date"].dropna().astype(str)
    min_d, max_d = dates.min(), dates.max()
    latest = datetime.strptime(max_d[:10], "%Y-%m-%d").date()
    gap = int(np.busday_count(np.datetime64(latest) + np.timedelta64(1, "D"), np.datetime64(today))) if latest < today else 0
    detail = f"최신 작업일 {max_d[:10]} / 그 이후 경과 평일 {gap}일 (공휴일 미반영)"
    if showcase_mode:
        record(sec, "INFO", "데이터 최신성: 쇼케이스는 고정 데이터라 판정 생략", detail)
    elif gap <= 2:
        record(sec, "PASS", "데이터 최신성", detail)
    elif gap <= 5:
        record(sec, "WARN", "데이터 최신성: 최근 입력이 다소 밀림", detail)
    else:
        record(sec, "FAIL", "데이터 최신성: 1주 이상 신규 입력 없음", detail)

    # 1-3. Volume summary
    record(
        sec, "INFO", "누적 규모",
        f"{len(df):,}행 ({min_d[:10]} ~ {max_d[:10]}) | 스티커 {int(df['sticker_qty'].sum()):,}매 | "
        f"박스 {int(df['work_qty'].sum()):,} | 바이어 {df['buyer_normalized'].nunique()} | "
        f"제조사 {df['manufacturer'].nunique()} | 표준품목 {df['normalized_item_name'].nunique()}",
    )

    # 1-4. Data quality breakdown (from validator report, not a pass/fail gate)
    if isinstance(dq, dict):
        record(
            sec, "INFO", f"데이터 품질: 이슈 없는 행 {dq.get('clean_rate_pct', 0):.1f}%",
            f"인원수 누락 {dq.get('worker_missing_count', 0):,}행 | 수량 불일치 {dq.get('qty_mismatch_count', 0):,}행 | "
            f"품목 미매칭 {dq.get('unmatched_item_count', 0):,}행 (품목 매칭률 {dq.get('item_match_rate_pct', 0):.2f}%)",
        )


# ------------------------------------------------------------------------------
# 2. Unit tests
# ------------------------------------------------------------------------------
def _flatten(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from _flatten(t)
        else:
            yield t


def check_unit_tests():
    sec = "테스트"
    print("\n[2/4] 🧪 자동 단위 테스트")
    suite = unittest.TestLoader().discover(str(PROJECT_ROOT / "tests"))
    all_ids = [t.id() for t in _flatten(suite)]
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    bad = {t.id(): "FAIL" for t, _ in result.failures}
    bad.update({t.id(): "ERROR" for t, _ in result.errors})

    by_file = {}
    for tid in all_ids:
        mod = tid.split(".")[0]
        by_file.setdefault(mod, []).append(tid)
    for mod, ids in by_file.items():
        n_bad = sum(1 for i in ids if i in bad)
        print(f"     - {mod}.py: {len(ids) - n_bad}/{len(ids)} 통과")

    if not bad and result.testsRun == len(all_ids):
        record(sec, "PASS", f"단위 테스트 {result.testsRun}/{len(all_ids)} 통과")
    else:
        names = ", ".join(f"{k.split('.')[-1]}({v})" for k, v in bad.items())
        record(sec, "FAIL", f"단위 테스트 실패 {len(bad)}건 / 전체 {len(all_ids)}건", names)


# ------------------------------------------------------------------------------
# 3. Static configuration (files in this repository)
# ------------------------------------------------------------------------------
def check_configuration():
    sec = "설정"
    print("\n[3/4] ⚙️  저장소 설정 (코드/설정 파일 정적 점검)")
    wf_dir = PROJECT_ROOT / ".github" / "workflows"

    for fname, expected_crons in EXPECTED_WORKFLOWS.items():
        path = wf_dir / fname
        if not path.exists():
            record(sec, "FAIL", f"워크플로 파일 없음: {fname}")
            continue
        text = path.read_text(encoding="utf-8")
        crons = re.findall(r"cron:\s*['\"]([^'\"]+)['\"]", text)
        missing = [c for c in expected_crons if c not in crons]
        manual = "workflow_dispatch" in text
        if missing:
            record(sec, "FAIL", f"{fname}: 예상 스케줄 누락", f"누락 {missing} / 발견 {crons}")
        else:
            record(sec, "PASS", f"{fname}: 스케줄 {crons}" + (" + 수동 실행" if manual else ""))

        if fname == "monthly_report.yml":
            refs = re.findall(r"secrets\.([A-Z_]+)", text)
            miss = [s for s in REQUIRED_EMAIL_SECRETS if s not in refs]
            if miss:
                record(sec, "FAIL", "monthly_report.yml: 메일 발송용 시크릿 참조 누락", str(miss))
            else:
                record(
                    sec, "PASS", "monthly_report.yml: 메일 시크릿 참조 확인 " + ", ".join(REQUIRED_EMAIL_SECRETS),
                    "참조 여부만 확인 — GitHub에 실제 값이 등록됐는지는 저장소 Settings > Secrets에서 확인 필요",
                )

    # Microsoft Clarity: defined AND invoked in app.py
    app_py = PROJECT_ROOT / "app" / "app.py"
    if app_py.exists():
        src = app_py.read_text(encoding="utf-8")
        defined = "def inject_microsoft_clarity" in src
        invoked = re.search(r"^inject_microsoft_clarity\(\)", src, re.M) is not None
        m = re.search(r'CLARITY_PROJECT_ID",\s*"([a-z0-9]+)"', src)
        pid = m.group(1) if m else None
        if defined and invoked and pid:
            record(
                sec, "PASS", f"Clarity 삽입 코드 존재 및 호출됨 (프로젝트 {pid})",
                "코드 존재만 확인 — 실제 세션 수집 여부는 Clarity 대시보드에서 확인 필요",
            )
        else:
            record(sec, "FAIL", "Clarity 삽입 코드 이상", f"정의={defined}, 호출={invoked}, ID={pid}")
    else:
        record(sec, "FAIL", "app/app.py 없음")

    # Local SMTP settings (only matter for manual local sending)
    import src.reporting.email_reporter as er  # loads .env fallback into os.environ

    present = [k for k in REQUIRED_EMAIL_SECRETS if os.getenv(k)]
    record(
        sec, "INFO", f"로컬 메일 설정(.env): {len(present)}/{len(REQUIRED_EMAIL_SECRETS)}개 존재",
        "로컬 수동 발송에만 사용 (자동 발송은 GitHub Secrets 사용). 값은 출력하지 않음",
    )
    return er.DASHBOARD_URL


# ------------------------------------------------------------------------------
# 4. External services (network)
# ------------------------------------------------------------------------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def check_external(dashboard_url):
    sec = "외부"
    print("\n[4/4] 🌐 외부 서비스 (네트워크)")

    # 4-1. Streamlit app
    try:
        opener = urllib.request.build_opener(_NoRedirect)
        req = urllib.request.Request(dashboard_url, headers={"User-Agent": "health-check"})
        resp = opener.open(req, timeout=15)
        record(sec, "PASS", f"Streamlit 앱 응답 HTTP {resp.status}", dashboard_url)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "") if e.headers else ""
        if e.code in (301, 302, 303, 307, 308) and "auth" in loc:
            record(
                sec, "SKIP", "Streamlit 앱: 로그인 필요(비공개 앱)라 자동 확인 불가",
                f"{dashboard_url} — 브라우저에서 직접 확인 필요",
            )
        elif e.code in (301, 302, 303, 307, 308):
            record(sec, "WARN", f"Streamlit 앱: 예상치 못한 리다이렉트 HTTP {e.code}", loc)
        else:
            record(sec, "FAIL", f"Streamlit 앱 오류 HTTP {e.code}", dashboard_url)
    except Exception as e:
        record(sec, "FAIL", "Streamlit 앱 접속 실패", repr(e))

    # 4-2. GitHub Actions latest runs (needs token for private repos)
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    try:
        remote = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", remote)
        repo = f"{m.group(1)}/{m.group(2)}" if m else None
    except Exception:
        repo = None

    if not repo:
        record(sec, "SKIP", "GitHub Actions: 원격 저장소 정보를 찾지 못함")
        return
    if not token:
        record(
            sec, "SKIP", f"GitHub Actions 실행 기록: 토큰 없음 ({repo})",
            "비공개 저장소라 GITHUB_TOKEN 환경변수가 필요. 없으면 GitHub > Actions 탭에서 직접 확인",
        )
        return

    for fname in EXPECTED_WORKFLOWS:
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{fname}/runs?per_page=1"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "health-check",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                runs = json.loads(r.read().decode("utf-8")).get("workflow_runs", [])
        except Exception as e:
            record(sec, "WARN", f"GitHub Actions 조회 실패: {fname}", repr(e))
            continue
        if not runs:
            record(sec, "WARN", f"{fname}: 실행 기록 없음")
            continue
        run = runs[0]
        when = run.get("created_at", "")[:16].replace("T", " ") + " UTC"
        concl = run.get("conclusion") or run.get("status")
        level = "PASS" if concl == "success" else ("INFO" if concl in ("in_progress", "queued") else "FAIL")
        record(sec, level, f"{fname}: 최근 실행 {concl}", f"{when} ({run.get('event')}) {run.get('html_url', '')}")


# ------------------------------------------------------------------------------
def main():
    skip_tests = "--skip-tests" in sys.argv
    today = date.today()
    print("=" * 70)
    print(f"🩺 SYSTEM HEALTH CHECK — {PROJECT_ROOT.name}")
    print(f"   실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    check_data_pipeline(today)
    if skip_tests:
        print("\n[2/4] 🧪 자동 단위 테스트")
        record("테스트", "SKIP", "--skip-tests 옵션으로 생략")
    else:
        check_unit_tests()
    dashboard_url = check_configuration()
    check_external(dashboard_url)

    counts = {k: sum(1 for r in RESULTS if r[1] == k) for k in ICONS}
    print("\n" + "=" * 70)
    print("📋 요약: " + " | ".join(f"{k} {v}" for k, v in counts.items()))
    if counts["FAIL"]:
        print("❌ 비정상 항목이 있습니다. 위 FAIL 항목을 확인하세요.")
    elif counts["WARN"]:
        print("⚠️  치명적 문제는 없지만 주의 항목이 있습니다.")
    else:
        print("✅ 점검 가능한 항목은 모두 정상입니다.")
    if counts["SKIP"]:
        print(f"⏭️  {counts['SKIP']}개 항목은 이 환경에서 확인할 수 없어 직접 확인이 필요합니다.")
    print("=" * 70)
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
