

Verilen açık onay doğrultusunda, `D080D6BA…` strateji adayı ve test paketi izole release dalına (`release/candidate_0B60DDB3`) commit edilmiş ve GitHub'a push edilmiştir. `main` dalına merge **edilmemiştir**; canlı VPS, Demo botu, çalışan container'lar, state ve borsa emirlerine kesinlikle dokunulmamıştır.

---

### 1. Commit Bilgileri ve SHA256 Doğrulaması

- **GitHub Release Dalı:** [`release/candidate_0B60DDB3`](https://github.com/alpcoderalp/tv/tree/release/candidate_0B60DDB3)
- **Commit 1 (Kod Adayı ve 46 Testin Tamamı):**
  - **Commit Hash:** [`b94c1d1de32f48f553ac4d667320ca9a3891ff80`](https://github.com/alpcoderalp/tv/commit/b94c1d1de32f48f553ac4d667320ca9a3891ff80)
  - **Mesaj:** `fix(hybrid): separate invalid/negative amounts, delegate zero close to verified cleanup, and enforce save_state`
  - **Kapsam:** [`tv_signal_strategy.py`](file:///c:/Users/bu_da/tv_repo/tv_signal_strategy.py), [`tests/test_release_controls_and_concurrency.py`](file:///c:/Users/bu_da/tv_repo/tests/test_release_controls_and_concurrency.py), [`tests/test_strict_terminal_fix.py`](file:///c:/Users/bu_da/tv_repo/tests/test_strict_terminal_fix.py), [`tests/test_quantize_verify_fix.py`](file:///c:/Users/bu_da/tv_repo/tests/test_quantize_verify_fix.py).
- **Commit 2 (Dokümantasyon Kaydı):**
  - **Commit Hash:** [`57f6fdb162de29d6698f3bcd9476f09424894129`](https://github.com/alpcoderalp/tv/commit/57f6fdb162de29d6698f3bcd9476f09424894129)
  - **Mesaj:** `docs: record candidate D080D6BA as locally tested and not deployed`
  - **Kapsam:** [`CLAUDE.md`](file:///c:/Users/bu_da/tv_repo/CLAUDE.md) ve [`.claude/CLAUDE.md`](file:///c:/Users/bu_da/tv_repo/.claude/CLAUDE.md) (BB1 yalnız generation eki olarak tanımlanmış, aday "deploy edilmedi" olarak kaydedilmiştir).

#### SHA256 Birebir Doğrulama:
- **Commit Öncesi SHA256:** `D080D6BA896795857E12BBCC9FA1B1BCFAF8DBA1F3DA0B6EDEF3CAD23B5F64E5`
- **Commit Sonrası SHA256:** `D080D6BA896795857E12BBCC9FA1B1BCFAF8DBA1F3DA0B6EDEF3CAD23B5F64E5`
- **Doğrulama Sonucu:** Byte-birebir eşleşme teyit edilmiştir (0 fark).

---

### 2. `4F95AA04` Tabanına Göre Nihai Strateji Diff'i

```diff
diff --git a/tv_signal_strategy.py b/tv_signal_strategy.py
index 4b8f2e2..b36e8fa 100644
--- a/tv_signal_strategy.py
+++ b/tv_signal_strategy.py
@@ -27024,10 +27024,49 @@ class TVSignalStrategy(ScriptStrategyBase):
     ) -> None:
         order_id = int(pos_data.get("order_id") or 0)
         side = str(pos_data.get("side") or "").upper()
+        close_amount = Decimal("0")
         try:
             if order_id <= 0 or side not in ("LONG", "SHORT"):
                 return
 
+            try:
+                if "remaining_amount" in pos_data and pos_data["remaining_amount"] is not None:
+                    raw_amt = pos_data["remaining_amount"]
+                else:
+                    raw_amt = pos_data.get("amount", "0")
+                if raw_amt is None:
+                    raise ValueError("None amount")
+                total_amount = Decimal(str(raw_amt))
+                if not total_amount.is_finite() or total_amount.is_nan():
+                    raise ValueError("Non-finite amount")
+            except Exception:
+                # Geçersiz / parse edilemeyen veri: transient hata olabilir.
+                # Sessiz HYBRID_TRANSITIONING kalıcılığını önlemek için WAIT'e dönülür.
+                if pos_data.get("management_stage") == "HYBRID_TRANSITIONING":
+                    pos_data["management_stage"] = "HYBRID_WAIT"
+                return
+
+            if total_amount < Decimal("0"):
+                # Negatif miktar: veri tutarsızlığı / hatası.
+                # Emir gönderilmez, parent tracking silinmez, tp1_done yazılmaz.
+                if pos_data.get("management_stage") == "HYBRID_TRANSITIONING":
+                    pos_data["management_stage"] = "HYBRID_WAIT"
+                return
+
+            if total_amount == Decimal("0"):
+                # Açıkça sıfır kalan pozisyon: TP1 engellenir (emir gönderilmez).
+                # Kapanış ve temizlik mevcut doğrulanmış cleanup/reconciliation akışına devredilir;
+                # TP1 aktivasyon fonksiyonuna yalnız miktar varsayımıyla yeni terminal silme yetkisi eklenmez.
+                if pos_data.get("management_stage") == "HYBRID_TRANSITIONING":
+                    pos_data["management_stage"] = "HYBRID_WAIT"
+                return
+
+            close_amount = (total_amount / Decimal("2")).quantize(Decimal("0.00000001"))
+            if not close_amount.is_finite() or close_amount <= Decimal("0"):
+                if pos_data.get("management_stage") == "HYBRID_TRANSITIONING":
+                    pos_data["management_stage"] = "HYBRID_WAIT"
+                return
+
             if current_price is not None and current_price > Decimal("0"):
                 self._update_hybrid_peak_price(pos_data, current_price)
 
@@ -27047,11 +27086,6 @@ class TVSignalStrategy(ScriptStrategyBase):
             if connector is None:
                 raise RuntimeError(f"connector bulunamadı: {exchange}")
 
-            total_amount = Decimal(str(pos_data.get("remaining_amount") or pos_data.get("amount") or "0"))
-            close_amount = (total_amount / Decimal("2")).quantize(Decimal("0.00000001"))
-            if close_amount <= 0:
-                return
-
             executed = await self._hybrid_execute_tp1_close(
                 connector, exchange, trading_pair, pos_data, close_amount, current_price
             )
@@ -27064,6 +27098,15 @@ class TVSignalStrategy(ScriptStrategyBase):
         finally:
             self._hybrid_transitioning_orders.discard(order_id)
             self._processing_phase2_orders.discard(order_id)
+            # 🎯 DAR DÜZELTME: Yalnızca bu çağrının emir gönderimine ulaşmadığı ve
+            # hiçbir aktif/belirsiz attempt CID taşımadığı kanıtlanan çıkışlarda stage HYBRID_WAIT'e iade edilir.
+            if pos_data.get("management_stage") == "HYBRID_TRANSITIONING":
+                intent = pos_data.get("tp1_intent") or {}
+                cids = set(intent.get("attempt_cids") or [])
+                if intent.get("current_attempt_cid"):
+                    cids.add(intent.get("current_attempt_cid"))
+                if not cids and not pos_data.get("tp1_done"):
+                    pos_data["management_stage"] = "HYBRID_WAIT"
 
     async def _hybrid_execute_tp1_close(
         self,
@@ -27138,7 +27181,37 @@ class TVSignalStrategy(ScriptStrategyBase):
                 pos_data["management_stage"] = "HYBRID_WAIT"
             return False
 
-        close_amount = (close_amount // step) * step
+        # Fresh amount verification right before order intent creation:
+        try:
+            if "remaining_amount" in pos_data and pos_data["remaining_amount"] is not None:
+                fresh_raw = pos_data["remaining_amount"]
+            else:
+                fresh_raw = pos_data.get("amount", "0")
+            if fresh_raw is None:
+                raise ValueError("None amount")
+            fresh_total = Decimal(str(fresh_raw))
+            if not fresh_total.is_finite() or fresh_total.is_nan():
+                raise ValueError("Non-finite amount")
+        except Exception:
+            if pos_data.get("management_stage") == "HYBRID_TRANSITIONING":
+                pos_data["management_stage"] = "HYBRID_WAIT"
+            return False
+
+        if fresh_total < Decimal("0"):
+            # Negatif miktar: emir gönderilmez, tracking silinmez, tp1_done yazılmaz.
+            if pos_data.get("management_stage") == "HYBRID_TRANSITIONING":
+                pos_data["management_stage"] = "HYBRID_WAIT"
+            return False
+
+        if fresh_total == Decimal("0"):
+            # Açıkça sıfır kalanda TP1 engellenir; terminal silme yapılmaz.
+            # Kapanış mevcut doğrulanmış cleanup/reconciliation akışına devredilir.
+            if pos_data.get("management_stage") == "HYBRID_TRANSITIONING":
+                pos_data["management_stage"] = "HYBRID_WAIT"
+            return False
+
+        fresh_close_amount = (fresh_total / Decimal("2")).quantize(Decimal("0.00000001"))
+        close_amount = (fresh_close_amount // step) * step
         if close_amount <= Decimal("0"):
             self.logger().warning(
                 f"⚠️ [HYBRID TP1 ABORT] #{order_id} {trading_pair}: close_amount zero after step normalization (step={step})"
@@ -27188,11 +27261,19 @@ class TVSignalStrategy(ScriptStrategyBase):
         )
         if not (isinstance(res, dict) and res.get("success")):
             intent_record["status"] = "SUBMIT_FAILED"
-            pos_data["management_stage"] = "HYBRID_WAIT"
-            self._save_state()
+            # 🎯 DAR DÜZELTME: Borsa isteği kabul etmiş fakat yanıt ağda kaybolmuş olabilir.
+            # Körleme HYBRID_WAIT'e dönülmez; aşama HYBRID_CLOSE_PENDING kalır ve
+            # attempt_cid uzlaştırma (reconciliation) mekanizmasına devredilir.
+            if not self._save_state():
+                self.logger().error(
+                    f"❌ [HYBRID] State persist failed for SUBMIT_FAILED intent #{order_id}"
+                )
             return False
 
-        self._save_state()
+        if not self._save_state():
+            self.logger().error(
+                f"❌ [HYBRID] State persist failed after order placement #{order_id}"
+            )
         return True
 
     def _hybrid_handle_execution_report(self, pos_data: dict, reports: list) -> bool:
```

---

### 3. Ham 46 Test Koşum Çıktısı (Aynı Commit Üzerinde)

```text
test_01_candidate_sha256_verified (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_01_candidate_sha256_verified) ... ok
test_02_full_fill_fresh_snapshot_verified (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_02_full_fill_fresh_snapshot_verified) ... ok
test_03_partial_fill_with_residual_stop_covered (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_03_partial_fill_with_residual_stop_covered) ... ok
test_04_partial_fill_without_residual_stop_marked_unprotected (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_04_partial_fill_without_residual_stop_marked_unprotected) ... ok
test_05_full_fill_stale_or_missing_snapshot_preserves_parent (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_05_full_fill_stale_or_missing_snapshot_preserves_parent) ... ok
test_06_execution_list_fallback_filters_non_trade_and_wrong_side (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_06_execution_list_fallback_filters_non_trade_and_wrong_side) ... ok
test_07_aggregate_mismatch_preserves_parent (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_07_aggregate_mismatch_preserves_parent) ... ok
test_08_repeated_reconcile_and_restart_stability (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_08_repeated_reconcile_and_restart_stability) ... ok
test_09_active_untriggered_stop_amended_normally (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_09_active_untriggered_stop_amended_normally) ... ok
test_10_same_2000_fill_processed_3_times_and_post_restart (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_10_same_2000_fill_processed_3_times_and_post_restart) ... ok
test_11_ws_fill_followed_by_rest_deducts_only_once (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_11_ws_fill_followed_by_rest_deducts_only_once) ... ok
test_12_same_parent_insufficient_quantity_not_protection (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_12_same_parent_insufficient_quantity_not_protection) ... ok
test_13_different_parent_same_quantity_not_protection (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_13_different_parent_same_quantity_not_protection) ... ok
test_14_wrong_price_side_positionidx_not_protection (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_14_wrong_price_side_positionidx_not_protection) ... ok
test_15_aggregate_difference_below_5pct_blocks_cleanup (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_15_aggregate_difference_below_5pct_blocks_cleanup) ... ok
test_16_caller_alarm_not_suppressed_for_ambiguous_and_unprotected_states (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_16_caller_alarm_not_suppressed_for_ambiguous_and_unprotected_states) ... ok
test_17_ws_same_order_diff_execid_cumulative_split (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_17_ws_same_order_diff_execid_cumulative_split) ... ok
test_18_ws_same_execid_repeat_no_double_deduction_or_terminal_cleanup (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_18_ws_same_execid_repeat_no_double_deduction_or_terminal_cleanup) ... ok
test_19_ws_split_then_rest_cumulative_no_extra_deduction (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_19_ws_split_then_rest_cumulative_no_extra_deduction) ... ok
test_20_rest_first_then_delayed_ws_executions_no_extra_deduction (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_20_rest_first_then_delayed_ws_executions_no_extra_deduction) ... ok
test_21_state_save_and_load_roundtrip_preserves_accounting_and_result (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_21_state_save_and_load_roundtrip_preserves_accounting_and_result) ... ok
test_22_missing_status_side_or_positionidx_not_partial_fill_covered (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_22_missing_status_side_or_positionidx_not_partial_fill_covered) ... ok
test_23_state_save_failure_produces_explicit_error_never_silent_success (test_strict_terminal_fix.TestStrictTerminalFixSuite.test_23_state_save_failure_produces_explicit_error_never_silent_success) ... ok
test_01_candidate_sha256_verified (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_01_candidate_sha256_verified) ... ok
test_02_dynamic_tick_quantize_never_retries_on_exact_boundary (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_02_dynamic_tick_quantize_never_retries_on_exact_boundary) ... ok
test_03_readback_guard_prevents_retry_when_rounded_to_same_tick (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_03_readback_guard_prevents_retry_when_rounded_to_same_tick) ... ok
test_04_unquantized_amend_target_rejected_before_network_call (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_04_unquantized_amend_target_rejected_before_network_call) ... ok
test_05_hold_entry_stage_suppresses_trailing_between_1r_and_2r (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_05_hold_entry_stage_suppresses_trailing_between_1r_and_2r) ... ok
test_06_trail_2r_triggers_trailing_and_saves_state (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_06_trail_2r_triggers_trailing_and_saves_state) ... ok
test_07_trail_3r_ratchet_locks_stop_at_2r_profit_floor (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_07_trail_3r_ratchet_locks_stop_at_2r_profit_floor) ... ok
test_08_ratchet_floor_monotonic_increasing_on_pullback (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_08_ratchet_floor_monotonic_increasing_on_pullback) ... ok
test_09_state_save_roundtrip_preserves_new_fields (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_09_state_save_roundtrip_preserves_new_fields) ... ok
test_10_missing_new_fields_in_legacy_state_load_safe_defaults (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_10_missing_new_fields_in_legacy_state_load_safe_defaults) ... ok
test_11_zero_position_no_stop_guard_blocks_stray_stop_generation (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_11_zero_position_no_stop_guard_blocks_stray_stop_generation) ... ok
test_12_non_finite_inputs_raise_or_quantize_safely (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_12_non_finite_inputs_raise_or_quantize_safely) ... ok
test_13_full_flow_1r_to_2r_to_3r_transition_and_amend_sequence (test_quantize_verify_fix.TestCandidateQuantizeVerifySuite.test_13_full_flow_1r_to_2r_to_3r_transition_and_amend_sequence) ... ok
test_01_full_lifecycle_e2e (test_end_to_end_lifecycle.TestEndToEndLifecycleSuite.test_01_full_lifecycle_e2e) ... ok
test_01_candidate_sha256_verified (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_01_candidate_sha256_verified) ... ok
test_02_missing_invalid_negative_amounts_preserve_parent_and_block_tp1 (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_02_missing_invalid_negative_amounts_preserve_parent_and_block_tp1) ... ok
test_03_transient_invalid_data_recovery (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_03_transient_invalid_data_recovery) ... ok
test_04_initial_zero_amount_blocks_tp1_and_delegates_to_cleanup (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_04_initial_zero_amount_blocks_tp1_and_delegates_to_cleanup) ... ok
test_05_zero_amount_on_async_suspension_blocks_tp1_and_delegates_to_cleanup (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_05_zero_amount_on_async_suspension_blocks_tp1_and_delegates_to_cleanup) ... ok
test_06_control2_real_pending_reconcile_on_lost_ack (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_06_control2_real_pending_reconcile_on_lost_ack) ... ok
test_07_control3_stage_transitions_audit_caller_callee (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_07_control3_stage_transitions_audit_caller_callee) ... ok
test_08_fresh_quantity_recheck_on_async_suspension (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_08_fresh_quantity_recheck_on_async_suspension) ... ok
test_09_concurrency_sibling_lock_resolution_127744249455_and_882631596625 (test_release_controls_and_concurrency.TestReleaseControlsAndConcurrencySuite.test_09_concurrency_sibling_lock_resolution_127744249455_and_882631596625) ... ok

----------------------------------------------------------------------
Ran 46 tests in 2.020s

OK

================================================================================
CANDIDATE TEST SUMMARY: Ran 46 tests.
Errors: 0, Failures: 0
ALL TESTS PASSED SUCCESSFULLY! (100% PASS)
```

---

### 4. Güncellenmiş Dokuz Release & Concurrency Testinin Tam Kaynakları

#### Üretim Await Analizi ve Deterministik Test Senkronizasyon Noktası:
- **Üretim Yolu Await Noktaları:** `tv_signal_strategy.py` içerisinde `_activate_hybrid_management` başlatıldığında, miktar okunmasından emir gönderimine kadar olan hat senkron ilerler; iç kolda tek await `await self._place_bybit_market_order(...)` (L27250) ve üst çağrıcıda `await self._hybrid_execute_tp1_close(...)` (L27088) mevcuttur.
- **Deterministik Event Mekanizması:** Test 5 ve Test 8'de yapay bekleme (`sleep`) yerine `asyncio.Event` kullanılmıştır:
  1. `harness.pre_close_hook_event.set()` çağrısı, coroutine'in emir öncesi kontrol noktasına ulaştığını test döngüsüne deterministik olarak bildirir.
  2. `await harness.resume_event.wait()` ile coroutine tam bu eşikte bekletilir.
  3. Test döngüsü miktarı (0 veya yeni bakiye) günceller ve `resume_event.set()` ile devam ettirir.
  4. Böylece yarış durumu (race condition) flakiness olmadan %100 deterministik test edilir.

```python
# Dosya: tests/test_release_controls_and_concurrency.py (TAM KAYNAK)

import asyncio
import ast
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import time
import types
import unittest
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any, Set
from unittest.mock import AsyncMock, MagicMock

# Base candidate path
CANDIDATE_PATH = pathlib.Path(__file__).resolve().parent.parent / "tv_signal_strategy.py"

# Parse AST from candidate
with open(CANDIDATE_PATH, "r", encoding="utf-8") as f:
    CANDIDATE_CODE = f.read()
    CANDIDATE_AST = ast.parse(CANDIDATE_CODE, filename=str(CANDIDATE_PATH))

AST_FUNCS = {}
for node in CANDIDATE_AST.body:
    if isinstance(node, ast.ClassDef) and node.name == "TVSignalStrategy":
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                AST_FUNCS[item.name] = item

def compile_method(func_name: str, extra_globals=None):
    fn_node = AST_FUNCS[func_name]
    mod = ast.Module(body=[fn_node], type_ignores=[])
    code_obj = compile(mod, filename=str(CANDIDATE_PATH), mode="exec")
    env = {
        "Any": Any, "Decimal": Decimal, "Dict": Dict, "List": List,
        "Optional": Optional, "Tuple": Tuple, "Set": Set, "set": set,
        "time": time, "asyncio": asyncio, "hasattr": hasattr,
        "getattr": getattr, "setattr": setattr, "isinstance": isinstance,
        "len": len, "str": str, "int": int, "float": float,
        "abs": abs, "sum": sum, "min": min, "max": max, "bool": bool,
        "ValueError": ValueError, "RuntimeError": RuntimeError,
    }
    if extra_globals:
        env.update(extra_globals)
    exec(code_obj, env)
    return env[func_name]

class DummyLogger:
    def __init__(self):
        self.logs = []
    def info(self, msg): self.logs.append(("INFO", str(msg)))
    def warning(self, msg): self.logs.append(("WARN", str(msg)))
    def error(self, msg, exc_info=None): self.logs.append(("ERROR", str(msg)))
    def debug(self, msg): self.logs.append(("DEBUG", str(msg)))

class MockTradingRule:
    def __init__(self, min_base_amount_increment=Decimal("1")):
        self.min_base_amount_increment = min_base_amount_increment

class MockConnector:
    def __init__(self):
        self.trading_rules = {
            "CHIP-USDT": MockTradingRule(Decimal("1")),
            "PONS-USDT": MockTradingRule(Decimal("1")),
        }
        self.mock_executions = []
        self.mock_orders = {}

class CandidateHarness:
    def __init__(self):
        self.logger_inst = DummyLogger()
        self._tracked_positions = {"CHIP-USDT": {"LONG": [], "SHORT": []}, "PONS-USDT": {"LONG": [], "SHORT": []}}
        self._sltp_orders = {}
        self._sltp_retry_queue = {}
        self._phase2_active_positions = set()
        self._last_sltp_placement = {}
        self._sltp_ws_confirmed = {}
        self._orders_being_placed = set()
        self._processing_phase2_orders = set()
        self._hybrid_transitioning_orders = set()
        self._unconfirmed_closes = {}
        self._phase2_immunity = {}
        self._sync_protection = {}
        self._grace_period_until = {}
        self._signal_cache = {}
        self._trailing_sl_stale_guard = {}
        self._sltp_placement_active = set()
        self._phase2_fail_close_guard = {}
        self._per_fill_accumulators = {}
        self._close_position_locks = {}
        self._trailing_sl_pending = {}
        self.connector = MockConnector()
        self.placed_market_orders = []
        self.simulate_network_lost_ack = False
        self.await_delay = 0.005
        self.pre_close_hook_event: Optional[asyncio.Event] = None
        self.resume_event: Optional[asyncio.Event] = None

    def logger(self):
        return self.logger_inst

    def _should_log_info(self, key, msg):
        return True

    def _identity_log_event(self, **kwargs):
        pass

    def _safe_int(self, val):
        try:
            return int(val) if val else 0
        except Exception:
            return 0

    def _reset_trailing_timeout_log_state(self, val):
        pass

    def _cancel_sltp_health_task(self, val):
        pass

    def _cleanup_closed_position_sltp(self, *args, **kwargs):
        pass

    def _pm_mode(self):
        return "hybrid_trailing"

    def _trading_allowed(self, context=""):
        return True

    def _get_connector(self, ex):
        return self.connector

    def _is_bybit_connector(self, conn):
        return True

    def _bybit_consolidation_mode(self, pair, side):
        return None

    def _save_state(self):
        return True

    def _is_rr2_managed_position(self, pos):
        return False

    async def _place_bybit_market_order(self, **kwargs):
        pair = kwargs.get("trading_pair")
        side = kwargs.get("position_side")
        lock_key = f"{pair}_{side}"
        self._orders_being_placed.add(lock_key)
        await asyncio.sleep(self.await_delay)
        self.placed_market_orders.append(kwargs)
        self._orders_being_placed.discard(lock_key)

        if self.simulate_network_lost_ack:
            return {"success": False, "error": "network_timeout_lost_ack"}

        return {"success": True, "order_id": f"ORD_{len(self.placed_market_orders)}"}

    async def _get_bybit_executions(self, connector, trading_pair):
        return getattr(connector, "mock_executions", [])

    async def _get_bybit_order_by_link_id(self, connector, trading_pair, cid):
        return getattr(connector, "mock_orders", {}).get(cid)

    async def _hybrid_execute_tp1_close(self, connector, exchange, trading_pair, pos_data, close_amount, current_price):
        if getattr(self, "pre_close_hook_event", None) is not None:
            self.pre_close_hook_event.set()
            if getattr(self, "resume_event", None) is not None:
                await self.resume_event.wait()
        return await self._orig_hybrid_execute_tp1_close(connector, exchange, trading_pair, pos_data, close_amount, current_price)

# Bind real AST methods from candidate
CandidateHarness._update_hybrid_peak_price = compile_method("_update_hybrid_peak_price")
CandidateHarness._ensure_position_r_geometry = compile_method("_ensure_position_r_geometry")
CandidateHarness._is_hybrid_managed_position = compile_method("_is_hybrid_managed_position")
CandidateHarness._is_position_protected = compile_method("_is_position_protected")
CandidateHarness._cleanup_position_tracking = compile_method("_cleanup_position_tracking")
CandidateHarness._prune_stale_tracked_positions = compile_method("_prune_stale_tracked_positions")
CandidateHarness._try_trigger_hybrid_management = compile_method("_try_trigger_hybrid_management")
CandidateHarness._activate_hybrid_management = compile_method("_activate_hybrid_management")
CandidateHarness._orig_hybrid_execute_tp1_close = compile_method("_hybrid_execute_tp1_close")
CandidateHarness._hybrid_handle_execution_report = compile_method("_hybrid_handle_execution_report")
CandidateHarness._reconcile_hybrid_pending_close = compile_method("_reconcile_hybrid_pending_close")
CandidateHarness._reconcile_hybrid_pending_close_guarded = compile_method("_reconcile_hybrid_pending_close_guarded")


class TestReleaseControlsAndConcurrencySuite(unittest.IsolatedAsyncioTestCase):

    def test_01_candidate_sha256_verified(self):
        """Verify candidate file SHA256 integrity."""
        h = hashlib.sha256()
        with open(CANDIDATE_PATH, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        expected_sha = "D080D6BA896795857E12BBCC9FA1B1BCFAF8DBA1F3DA0B6EDEF3CAD23B5F64E5"
        self.assertEqual(
            h.hexdigest().upper(),
            expected_sha,
            f"Candidate SHA256 mismatch! Found {h.hexdigest().upper()}, expected {expected_sha}"
        )

    async def test_02_missing_invalid_negative_amounts_preserve_parent_and_block_tp1(self):
        """Points 1 & 5: Missing, None, invalid strings, NaN, Infinity, and negative amounts:
        - 0 TP1 orders dispatched.
        - Parent tracking is strictly preserved (NOT deleted).
        - tp1_done is NOT set to True.
        - Stage safely reverts to HYBRID_WAIT for future evaluation.
        """
        test_cases = [
            ("Missing Amount", {}),
            ("None Amount", {"remaining_amount": None, "amount": None}),
            ("Invalid String Amount", {"remaining_amount": "invalid_abc", "amount": "invalid_abc"}),
            ("Decimal NaN", {"remaining_amount": Decimal("NaN"), "amount": Decimal("NaN")}),
            ("Decimal Infinity", {"remaining_amount": Decimal("Infinity"), "amount": Decimal("Infinity")}),
            ("Decimal -Infinity", {"remaining_amount": Decimal("-Infinity"), "amount": Decimal("-Infinity")}),
            ("Negative Decimal Amount", {"remaining_amount": Decimal("-5000"), "amount": Decimal("-5000")}),
            ("Negative Integer Amount", {"remaining_amount": -1000, "amount": -1000}),
            ("Negative String Amount", {"remaining_amount": "-250", "amount": "-250"}),
        ]

        for label, amt_fields in test_cases:
            harness = CandidateHarness()
            pos = {
                "order_id": 7001,
                "trading_pair": "CHIP-USDT",
                "side": "LONG",
                "entry": Decimal("0.04770"),
                "sl": Decimal("0.04702"),
                "r1_price": Decimal("0.04838"),
                "r2_price": Decimal("0.04906"),
                "management_stage": "HYBRID_WAIT",
                "exchange": "bybit_perpetual",
            }
            pos.update(amt_fields)
            harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]
            price = Decimal("0.04850")

            trig = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="ws")
            self.assertTrue(trig, f"Failed trigger for {label}")

            # Await processing task
            await asyncio.sleep(0.02)

            # Assert 1: Zero orders dispatched
            self.assertEqual(len(harness.placed_market_orders), 0, f"Orders placed for {label}")
            # Assert 2: Task ownership cleaned up (finally executed)
            self.assertNotIn(7001, harness._hybrid_transitioning_orders, f"Lock leaked for {label}")
            self.assertNotIn(7001, harness._processing_phase2_orders, f"Phase2 lock leaked for {label}")
            # Assert 3: tp1_done is NOT True
            self.assertFalse(pos.get("tp1_done", False), f"tp1_done incorrectly set True for {label}")
            # Assert 4: Stage safely restored to HYBRID_WAIT
            self.assertEqual(pos.get("management_stage"), "HYBRID_WAIT", f"Stage not HYBRID_WAIT for {label}")
            # Assert 5: Parent tracking preserved (NOT deleted)
            tracked = [p for p in harness._tracked_positions["CHIP-USDT"]["LONG"] if p.get("order_id") == 7001]
            self.assertEqual(len(tracked), 1, f"Parent tracking deleted for {label}")

    async def test_03_transient_invalid_data_recovery(self):
        """Transient invalid data reverts to HYBRID_WAIT; when data fixes, monitor re-processes parent."""
        harness = CandidateHarness()
        pos = {
            "order_id": 7002,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "remaining_amount": "invalid_transient_payload",
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]
        price = Decimal("0.04850")

        # Tick 1: Trigger with transient invalid data
        trig1 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="ws")
        self.assertTrue(trig1)
        await asyncio.sleep(0.02)

        # Reverted to HYBRID_WAIT, 0 orders, parent preserved
        self.assertEqual(pos.get("management_stage"), "HYBRID_WAIT")
        self.assertEqual(len(harness.placed_market_orders), 0)
        self.assertFalse(pos.get("tp1_done", False))
        self.assertEqual(len(harness._tracked_positions["CHIP-USDT"]["LONG"]), 1)
        self.assertNotIn(7002, harness._hybrid_transitioning_orders)

        # Between ticks: Data source fixes
        pos["remaining_amount"] = Decimal("5000")

        # Tick 2: Monitor evaluates position again
        trig2 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="monitor")
        self.assertTrue(trig2)
        await asyncio.sleep(0.02)

        # Parent successfully re-processed: TP1 dispatched for 2500
        self.assertEqual(len(harness.placed_market_orders), 1)
        self.assertEqual(harness.placed_market_orders[0]["amount"], Decimal("2500"))
        self.assertEqual(pos.get("management_stage"), "HYBRID_CLOSE_PENDING")

    async def test_04_initial_zero_amount_blocks_tp1_and_delegates_to_cleanup(self):
        """Points 2 & 5: When remaining_amount is explicitly zero:
        - TP1 activation blocks order placement (0 orders).
        - Activation function does NOT unilaterally delete parent or force HYBRID_CLOSED.
        - Existing verified cleanup flow (_prune_stale_tracked_positions) cleanly reclaims the position.
        """
        harness = CandidateHarness()
        pos = {
            "order_id": 7003,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "remaining_amount": Decimal("0"), # Explicit zero amount
            "amount": Decimal("5000"),
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]
        price = Decimal("0.04850")

        # Step 1: Initial activation attempt
        await harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price)

        # Invariants:
        # a. 0 market orders dispatched
        self.assertEqual(len(harness.placed_market_orders), 0)
        # b. Activation function does not mark tp1_done
        self.assertFalse(pos.get("tp1_done", False))
        # c. Stage safely restored to HYBRID_WAIT
        self.assertEqual(pos.get("management_stage"), "HYBRID_WAIT")
        # d. Parent tracking NOT deleted by activation function
        tracked = [p for p in harness._tracked_positions["CHIP-USDT"]["LONG"] if p.get("order_id") == 7003]
        self.assertEqual(len(tracked), 1)

        # Step 2: Real verified cleanup path runs (_prune_stale_tracked_positions)
        pruned = harness._prune_stale_tracked_positions()
        self.assertEqual(pruned, 1)

        # Now parent tracking is cleanly pruned by existing verified flow
        tracked_after = [p for p in harness._tracked_positions["CHIP-USDT"]["LONG"] if p.get("order_id") == 7003]
        self.assertEqual(len(tracked_after), 0)

        # Step 3: Direct activation on pruned position produces 0 orders
        await harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price)
        self.assertEqual(len(harness.placed_market_orders), 0)

    async def test_05_zero_amount_on_async_suspension_blocks_tp1_and_delegates_to_cleanup(self):
        """Points 2, 4 & 5: Deterministic task synchronization with asyncio.Event:
        Simulate an asynchronous task switch before intent creation where remaining_amount becomes 0:
        - TP1 order placement is blocked (0 orders).
        - Activation function does NOT unilaterally delete parent or force terminal stage.
        - Existing verified cleanup flow cleanly prunes tracking.
        Production note: In the production codebase, _activate_hybrid_management -> _hybrid_execute_tp1_close
        executes synchronously up to market order placement. This test deterministically simulates an asynchronous
        task suspension using asyncio.Event to prove that if remaining_amount changes while suspended before intent
        generation, fresh amount is strictly re-read and enforced.
        """
        harness = CandidateHarness()
        harness.pre_close_hook_event = asyncio.Event()
        harness.resume_event = asyncio.Event()

        pos = {
            "order_id": 7004,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "remaining_amount": Decimal("5000"),
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]
        price = Decimal("0.04850")

        # Start task
        task = asyncio.create_task(harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price))

        # Deterministically wait until suspended at pre-order hook
        await harness.pre_close_hook_event.wait()

        # Concurrent event while suspended: position closed on exchange (remaining_amount becomes 0)
        pos["remaining_amount"] = Decimal("0")

        # Resume task
        harness.resume_event.set()
        await task

        # Invariants:
        # a. 0 market orders dispatched
        self.assertEqual(len(harness.placed_market_orders), 0)
        # b. Activation function did not mark tp1_done
        self.assertFalse(pos.get("tp1_done", False))
        # c. Stage safely restored to HYBRID_WAIT
        self.assertEqual(pos.get("management_stage"), "HYBRID_WAIT")
        # d. Parent tracking NOT deleted by activation function
        tracked = [p for p in harness._tracked_positions["CHIP-USDT"]["LONG"] if p.get("order_id") == 7004]
        self.assertEqual(len(tracked), 1)

        # Step 2: Real verified cleanup path runs (_prune_stale_tracked_positions)
        pruned = harness._prune_stale_tracked_positions()
        self.assertEqual(pruned, 1)

        # Tracking is now cleanly pruned
        tracked_after = [p for p in harness._tracked_positions["CHIP-USDT"]["LONG"] if p.get("order_id") == 7004]
        self.assertEqual(len(tracked_after), 0)

        # Step 3: Direct activation produces 0 orders
        await harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price)
        self.assertEqual(len(harness.placed_market_orders), 0)

    async def test_06_control2_real_pending_reconcile_on_lost_ack(self):
        """Control 2: Real pending reconcile path queries exchange, applies 1x deduction, 0 duplicates."""
        harness = CandidateHarness()
        harness.simulate_network_lost_ack = True

        pos = {
            "order_id": 888222333,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "amount": Decimal("5000"),
            "remaining_amount": Decimal("5000"),
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]
        price = Decimal("0.04850")

        # Step 1: Dispatch with lost ACK
        trig1 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="ws")
        self.assertTrue(trig1)
        for _ in range(50):
            await asyncio.sleep(0.01)
            if pos.get("tp1_intent", {}).get("status") == "SUBMIT_FAILED":
                break

        self.assertEqual(pos.get("management_stage"), "HYBRID_CLOSE_PENDING")
        self.assertEqual(pos.get("tp1_intent", {}).get("status"), "SUBMIT_FAILED")
        attempt_cid = pos["tp1_intent"]["current_attempt_cid"]
        self.assertIsNotNone(attempt_cid)
        self.assertEqual(len(harness.placed_market_orders), 1)

        # Step 2: Ambiguous tick while in HYBRID_CLOSE_PENDING -> Must NOT submit second order
        trig2 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="monitor")
        self.assertFalse(trig2)
        self.assertEqual(len(harness.placed_market_orders), 1)

        # Step 3: Run the REAL reconcile path with mock execution fill
        harness.connector.mock_executions = [
            {
                "orderLinkId": attempt_cid,
                "execId": "EXEC_RECON_001",
                "execQty": "2500",
                "closedSize": "2500",
                "execPrice": "0.04852",
            }
        ]

        reconcile_res = await harness._reconcile_hybrid_pending_close_guarded(
            harness.connector, "CHIP-USDT", "LONG", pos
        )
        self.assertTrue(reconcile_res)

        # Step 4: Verify exactly-once accounting
        self.assertTrue(pos.get("tp1_done"))
        self.assertEqual(pos.get("remaining_amount"), Decimal("2500"))
        self.assertEqual(pos.get("management_stage"), "HYBRID_TP1_FILLED_SL_PENDING")
        self.assertEqual(pos.get("tp1_intent", {}).get("status"), "FILL_VERIFIED")
        self.assertEqual(len(harness.placed_market_orders), 1)

    async def test_07_control3_stage_transitions_audit_caller_callee(self):
        """Control 3: HYBRID_CLOSE_PENDING set by callee is never reverted to HYBRID_WAIT by caller."""
        harness = CandidateHarness()
        pos = {
            "order_id": 999111222,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "amount": Decimal("5000"),
            "remaining_amount": Decimal("5000"),
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]
        price = Decimal("0.04850")

        # Simulate submit failure in place_market_order
        harness.simulate_network_lost_ack = True
        await harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price)

        # Callee sets HYBRID_CLOSE_PENDING; caller must NOT overwrite it with HYBRID_WAIT!
        self.assertEqual(pos.get("management_stage"), "HYBRID_CLOSE_PENDING")

    async def test_08_fresh_quantity_recheck_on_async_suspension(self):
        """Points 4 & 5: Deterministic task synchronization with asyncio.Event:
        Simulate an asynchronous task switch before intent creation where remaining_amount changes:
        - Fresh quantity is re-verified and used for sizing instead of stale value.
        Production note: In the production codebase, _activate_hybrid_management -> _hybrid_execute_tp1_close
        executes synchronously up to market order placement. This test deterministically simulates an asynchronous
        task suspension using asyncio.Event to prove that if remaining_amount changes while suspended before intent
        generation, fresh amount is strictly re-read and enforced.
        """
        harness = CandidateHarness()
        harness.pre_close_hook_event = asyncio.Event()
        harness.resume_event = asyncio.Event()

        pos = {
            "order_id": 555666777,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "amount": Decimal("10000"),
            "remaining_amount": Decimal("10000"),
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]
        price = Decimal("0.04850")

        # Start task
        task = asyncio.create_task(harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price))

        # Deterministically wait until suspended at pre-order hook
        await harness.pre_close_hook_event.wait()

        # Amount changes while suspended from 10000 to 2000
        pos["remaining_amount"] = Decimal("2000")

        # Resume task
        harness.resume_event.set()
        await task

        # Fresh quantity (2000 / 2 = 1000) used instead of initial (10000 / 2 = 5000)
        self.assertEqual(len(harness.placed_market_orders), 1)
        self.assertEqual(harness.placed_market_orders[0]["amount"], Decimal("1000"))

    async def test_09_concurrency_sibling_lock_resolution_127744249455_and_882631596625(self):
        """Concurrency Defect: #127744249455 and #882631596625 both trigger 1R; lock contention cleanly resolved."""
        harness = CandidateHarness()
        pos_A = {
            "order_id": 127744249455,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "amount": Decimal("5070"),
            "remaining_amount": Decimal("5070"),
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        pos_B = {
            "order_id": 882631596625,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04775"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04848"),
            "r2_price": Decimal("0.04921"),
            "amount": Decimal("4800"),
            "remaining_amount": Decimal("4800"),
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos_A, pos_B]
        price = Decimal("0.04857")

        trig_A = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos_A, price, source="ws")
        trig_B = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos_B, price, source="ws")
        self.assertTrue(trig_A and trig_B)

        for _ in range(50):
            await asyncio.sleep(0.01)
            if len(harness.placed_market_orders) >= 1 and pos_A.get("management_stage") == "HYBRID_CLOSE_PENDING":
                break
        self.assertEqual(pos_A.get("management_stage"), "HYBRID_CLOSE_PENDING")
        self.assertEqual(pos_B.get("management_stage"), "HYBRID_WAIT")
        self.assertEqual(len(harness.placed_market_orders), 1)

        # Tick 2: Lock released by A. B evaluates on next tick
        trig_B_tick2 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos_B, price, source="monitor")
        self.assertTrue(trig_B_tick2)
        for _ in range(50):
            await asyncio.sleep(0.01)
            if len(harness.placed_market_orders) >= 2 and pos_B.get("management_stage") == "HYBRID_CLOSE_PENDING":
                break

        self.assertEqual(pos_B.get("management_stage"), "HYBRID_CLOSE_PENDING")
        self.assertEqual(len(harness.placed_market_orders), 2)
        self.assertEqual(harness.placed_market_orders[0]["amount"], Decimal("2535"))
        self.assertEqual(harness.placed_market_orders[1]["amount"], Decimal("2400"))


if __name__ == "__main__":
    unittest.main()
```

---

### 5. Açık Pozisyonlar Varken State Uyumluluğu Değerlendirmesi ve Kontrollü Dağıtım Planı

Mevcut çalışan sistemde 4 adet aktif pozisyon bulunmaktadır (`#570414374565`, `#167272712944`, `#606906494493`, `#275087885943`).

#### A. State Şeması ve Geriye Dönük Uyumluluk (State Compatibility)
1. **Şema Değişikliği Yoktur:**
   - Yeni aday `D080D6BA…`, disk üzerindeki JSON state dosyasının yapısını, alan adlarını veya tiplerini değiştirmemektedir.
   - Mevcut state alanları (`remaining_amount`, `management_stage`, `applied_cumulative_fill`, `applied_exec_ids`, `ws_fills_by_order`, `confirmed_sl`) olduğu gibi korunur.
2. **Aktif Pozisyonların Durumu:**
   - `#570414374565` (PONS-USDT LONG): Zaten TP1 dolumunu tamamlamış, `HYBRID_HOLD_ENTRY` aşamasında BE stopu ile korunmaktadır. Adayın getirdiği TP1 kilitlenme düzeltmesi bu pozisyonu etkilemez; BE koruması ve 2R/3R ratchet mekanizmaları aynen işlemeye devam eder.
   - `#167272712944`, `#606906494493`, `#275087885943`: `HYBRID_WAIT` aşamasında 1R temasını beklemektedir. Yeni sürüm devreye girdiğinde bu pozisyonlar için kilitlenme riski tamamen ortadan kalkar; aynı pair üzerinde eşzamanlı 1R görseler dahi kilit serbest kaldığında sırayla güvenle TP1 icra edilir.
3. **Miktar Güvenliği (Zero / Negative Amount):**
   - Pozisyonlardan biri restart sırasında borsada kapanmış ve hafızaya 0 bakiye ile dönmüşse, eski sürümün aksine yeni sürüm körleme `HYBRID_TRANSITIONING` kilitlenmesine girmeyecek; TP1 emri gönderilmeyecek ve pozisyon mevcut `_prune_stale_tracked_positions` temizliği ile güvenle arşivlenecektir.

#### B. Kontrollü Dağıtım Planı (Canlıya Geçiş İçin Önerilen Adımlar)

> [!NOTE]
> Aşağıdaki adımlar gelecekteki olası bir deploy için taslak prosedürdür. Şu an **hiçbir deploy yapılmamıştır**.

1. **Ön Dağıtım Kontrolü (Pre-Flight Check):**
   - VPS üzerindeki `state_tv_signal_strategy.json` yedeği alınır (`cp state_tv_signal_strategy.json state_tv_signal_strategy.json.bak_4F95`).
   - Bybit REST API üzerinden açık 4 pozisyonun aktif borsa koşullu stopları doğrulanır.
2. **Dosya Güncellemesi (File Swap):**
   - Docker container içinde `/workspace/hummingbot/strategy/tv_signal_strategy.py` dosyası `D080D6BA…` sürümüyle güncellenir.
   - SHA256 container içinde doğrulanır (`sha256sum tv_signal_strategy.py`).
3. **Graceful Restart:**
   - Bot durdurulur (`stop` komutu ile state'in diske flush edilmesi sağlanır).
   - Docker container yeniden başlatılır (`docker compose restart hummingbot`).
4. **Post-Deploy Doğrulama:**
   - Boot loglarında `[STATE LOAD]` ile açık 4 pozisyonun eksiksiz yüklendiği ve `_state_loaded=True` olduğu doğrulanır.
   - `order_status` komutu ile borsa stop emirlerinin eksiksiz bağlandığı teyit edilir.

---

> [!IMPORTANT]
> Bu işlem yalnızca yerel release dalına commit ve push ile sınırlandırılmıştır. Canlı VPS, Demo botu ve borsa emirleri hiçbir şekilde değiştirilmemiştir. Canlıya deploy veya restart için açık talimatınız beklenmektedir.
