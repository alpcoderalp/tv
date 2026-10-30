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
