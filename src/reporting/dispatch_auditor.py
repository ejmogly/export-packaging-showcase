"""
Dispatch Auditor Agent (발송 거버넌스 감사 에이전트)
================================================================================
역할 및 비즈니스 정책:
1. 멱등성(Idempotency) 보장:
   - data/dispatch_history.json 원장을 관리하여, 동일 대상월(Target Month)에 대한
     중복 발송(Duplicate Dispatches)을 원천 차단합니다.
2. 단계별 전략 로드맵(Phased Roadmap) 준수:
   - Phase 1 (현행): 월별 종합 결산 리포트 선제 도입 및 100% 무장애 안정화.
   - Phase 2 (예정): 월별 발송 안정화 검증 후 주별(Weekly) 운영 리포트 순차 도입.
   - 주간 리포트 템플릿과 생성 로직은 보존하되, Phase 1 기간 중 불시 주간 발송은 사전 차단(Pending)합니다.
3. 일정 감사 (Date Audit):
   - 월간 결산 본 발송은 매월 1일에만 승인됩니다 (--force 오버라이드 지원).
================================================================================
"""

import os
import json
from datetime import datetime, date
from typing import Dict, Any, Tuple, Optional, List


# 로드맵 단계 선언
PHASE_1_MONTHLY_STABILIZATION = "PHASE_1_MONTHLY_STABILIZATION"
PHASE_2_WEEKLY_EXPANSION = "PHASE_2_WEEKLY_EXPANSION"

CURRENT_REPORTING_PHASE = PHASE_1_MONTHLY_STABILIZATION


class DispatchAuditor:
    """
    이메일 발송 전 비즈니스 룰 및 중복 여부를 독립적으로 감사하는 에이전트
    """
    def __init__(self, ledger_path: Optional[str] = None):
        if not ledger_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.ledger_path = os.path.join(base_dir, "data", "dispatch_history.json")
        else:
            self.ledger_path = ledger_path

    # --------------------------------------------------------------------------
    # 1. Ledger (발송 원장) I/O
    # --------------------------------------------------------------------------
    def load_ledger(self) -> Dict[str, Any]:
        """Loads persistent dispatch ledger from disk."""
        if not os.path.exists(self.ledger_path):
            return {
                "schema_version": "1.0",
                "current_phase": CURRENT_REPORTING_PHASE,
                "dispatches": []
            }
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[DispatchAuditor Warning] Failed to read ledger ({e}). Starting fresh ledger.")
            return {
                "schema_version": "1.0",
                "current_phase": CURRENT_REPORTING_PHASE,
                "dispatches": []
            }

    def save_ledger(self, ledger: Dict[str, Any]) -> bool:
        """Saves dispatch ledger to disk."""
        try:
            os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                json.dump(ledger, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[DispatchAuditor Error] Failed to write ledger: {e}")
            return False

    def has_successfully_dispatched(self, target_month: str, report_type: str = "monthly") -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Checks whether target_month has already been successfully dispatched.
        """
        ledger = self.load_ledger()
        for record in ledger.get("dispatches", []):
            if (
                record.get("report_type") == report_type and
                record.get("target_month") == target_month and
                record.get("status") == "SUCCESS"
            ):
                return True, record
        return False, None

    def record_dispatch(
        self,
        target_month: str,
        report_type: str = "monthly",
        recipients: Optional[List[str]] = None,
        kpi_summary: Optional[Dict[str, Any]] = None,
        status: str = "SUCCESS",
        note: str = ""
    ) -> bool:
        """
        Records a dispatch event in the audit ledger.
        """
        ledger = self.load_ledger()
        ledger["current_phase"] = CURRENT_REPORTING_PHASE
        
        record = {
            "dispatch_id": f"{report_type}_{target_month}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "report_type": report_type,
            "target_month": target_month,
            "dispatched_at": datetime.now().isoformat(),
            "recipients": recipients or [],
            "status": status,
            "kpi_summary": kpi_summary or {},
            "note": note
        }
        ledger.setdefault("dispatches", []).append(record)
        return self.save_ledger(ledger)

    # --------------------------------------------------------------------------
    # 2. Pre-Flight Audit Gates (발송 전 사전 심사 게이트)
    # --------------------------------------------------------------------------
    def audit_monthly_dispatch(
        self,
        target_month: str,
        today: Optional[date] = None,
        force: bool = False
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Audits monthly closing dispatch request.
        Returns: (is_approved, audit_reason, audit_metadata)
        """
        if today is None:
            today = datetime.now().date()

        meta = {
            "target_month": target_month,
            "audit_date": str(today),
            "force_flag": force,
            "current_phase": CURRENT_REPORTING_PHASE
        }

        # Gate 1: 멱등성 검사 (Idempotency Audit)
        is_already_sent, prev_record = self.has_successfully_dispatched(target_month, report_type="monthly")
        if is_already_sent and not force:
            sent_at = prev_record.get("dispatched_at", "이전 일시")
            reason = (
                f"🚨 [AUDIT REJECTED - 멱등성 보호] {target_month} 월간 결산 리포트는 이미 "
                f"정상 발송되었습니다 (발송일시: {sent_at}). 중복 발송을 원천 차단합니다."
            )
            meta["rejection_code"] = "DUPLICATE_DISPATCH_BLOCKED"
            meta["previous_record"] = prev_record
            return False, reason, meta

        # Gate 2: 날짜 검사 (Date Audit - 매월 1일 엄수)
        if today.day != 1 and not force:
            reason = (
                f"🚨 [AUDIT REJECTED - 일정 정책 위반] 오늘은 {today.day}일입니다. "
                f"월간 결산 리포트는 매월 1일에만 발송이 승인됩니다. (수동 강제 시 --force 사용)"
            )
            meta["rejection_code"] = "INVALID_DISPATCH_DAY"
            return False, reason, meta

        # Gate 3: 승인
        approval_msg = (
            f"✅ [AUDIT APPROVED] {target_month} 월간 결산 리포트 발송 심사를 최종 승인하였습니다. "
            f"(강제 여부: {force})"
        )
        meta["audit_status"] = "APPROVED"
        return True, approval_msg, meta

    def audit_weekly_dispatch(
        self,
        start_date: str,
        end_date: str,
        force: bool = False
    ) -> Tuple[bool, str]:
        """
        Audits weekly dispatch request with respect to strategic roadmap.
        In Phase 1, weekly reports are kept pending until monthly stabilizes.
        """
        if CURRENT_REPORTING_PHASE == PHASE_1_MONTHLY_STABILIZATION and not force:
            reason = (
                "ℹ️ [AUDIT HOLD - 로드맵 대기] 주별 발송은 'Phase 1: 월별 결산 선제 안정화' "
                "달성 후 2단계(Phase 2)로 순차 오픈될 예정입니다. (강제 발송 시 --force 사용)"
            )
            return False, reason

        return True, f"✅ [AUDIT APPROVED] 주간 리포트 발송 승인 ({start_date} ~ {end_date})"
