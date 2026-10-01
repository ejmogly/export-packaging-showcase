"""
Unit Tests for DispatchAuditor Agent
================================================================================
Tests idempotency ledger, date gates, and phased roadmap enforcement.
================================================================================
"""

import unittest
import os
import shutil
import tempfile
from datetime import date
from src.reporting.dispatch_auditor import DispatchAuditor, PHASE_1_MONTHLY_STABILIZATION


class TestDispatchAuditor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ledger_file = os.path.join(self.test_dir, "test_dispatch_history.json")
        self.auditor = DispatchAuditor(ledger_path=self.ledger_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_initial_ledger_empty(self):
        """Initial ledger should be empty."""
        ledger = self.auditor.load_ledger()
        self.assertEqual(ledger["current_phase"], PHASE_1_MONTHLY_STABILIZATION)
        self.assertEqual(len(ledger["dispatches"]), 0)

    def test_02_audit_monthly_approval_on_day_1(self):
        """Monthly dispatch should be approved on day 1 for new month."""
        day1 = date(2026, 10, 1)
        is_approved, msg, meta = self.auditor.audit_monthly_dispatch("2026-09", today=day1, force=False)
        self.assertTrue(is_approved)
        self.assertIn("AUDIT APPROVED", msg)

    def test_03_audit_monthly_rejected_on_day_other_than_1(self):
        """Monthly dispatch should be rejected on day 29 or 30."""
        day29 = date(2026, 9, 29)
        is_approved, msg, meta = self.auditor.audit_monthly_dispatch("2026-09", today=day29, force=False)
        self.assertFalse(is_approved)
        self.assertEqual(meta.get("rejection_code"), "INVALID_DISPATCH_DAY")

        # But allowed with force=True
        is_appr_force, msg_force, _ = self.auditor.audit_monthly_dispatch("2026-09", today=day29, force=True)
        self.assertTrue(is_appr_force)

    def test_04_idempotency_prevents_duplicate_dispatches(self):
        """Once dispatched, subsequent dispatch requests for same target month must be blocked."""
        day1 = date(2026, 10, 1)

        # 1st attempt: Approved
        is_appr, _, _ = self.auditor.audit_monthly_dispatch("2026-09", today=day1, force=False)
        self.assertTrue(is_appr)

        # Record success
        rec_ok = self.auditor.record_dispatch(
            target_month="2026-09",
            report_type="monthly",
            recipients=["manager@factory.com"],
            kpi_summary={"total_stickers": 773578}
        )
        self.assertTrue(rec_ok)

        # 2nd attempt: Must be BLOCKED due to idempotency!
        is_appr2, msg2, meta2 = self.auditor.audit_monthly_dispatch("2026-09", today=day1, force=False)
        self.assertFalse(is_appr2)
        self.assertEqual(meta2.get("rejection_code"), "DUPLICATE_DISPATCH_BLOCKED")
        self.assertIn("멱등성 보호", msg2)

        # But force=True can override
        is_appr_override, _, _ = self.auditor.audit_monthly_dispatch("2026-09", today=day1, force=True)
        self.assertTrue(is_appr_override)

    def test_05_weekly_dispatch_hold_in_phase_1(self):
        """Weekly dispatch should be held pending in Phase 1 until monthly stabilizes."""
        is_appr, msg = self.auditor.audit_weekly_dispatch("2026-09-01", "2026-09-07", force=False)
        self.assertFalse(is_appr)
        self.assertIn("Phase 1: 월별 결산 선제 안정화", msg)

        # Allowed with force
        is_appr_force, msg_force = self.auditor.audit_weekly_dispatch("2026-09-01", "2026-09-07", force=True)
        self.assertTrue(is_appr_force)


if __name__ == "__main__":
    unittest.main()
