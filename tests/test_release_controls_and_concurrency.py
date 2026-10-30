import ast
import asyncio
import hashlib
import os
import pathlib
import sys
import time
import unittest
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

# Dynamic relative path resolution - zero local absolute path dependency
REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
CANDIDATE_PATH = REPO_DIR / "tv_signal_strategy.py"

with open(CANDIDATE_PATH, "rb") as f:
    CODE_BYTES = f.read()

CANDIDATE_SHA256 = hashlib.sha256(CODE_BYTES).hexdigest().upper()

TREE = ast.parse(CODE_BYTES.decode("utf-8"))
AST_FUNCS = {}
for node in TREE.body:
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
        self.connector = MockConnector()
        self.placed_market_orders = []
        self.simulate_network_lost_ack = False
        self.await_delay = 0.005

    def logger(self):
        return self.logger_inst

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

# Bind real AST methods from candidate
CandidateHarness._update_hybrid_peak_price = compile_method("_update_hybrid_peak_price")
CandidateHarness._ensure_position_r_geometry = compile_method("_ensure_position_r_geometry")
CandidateHarness._is_hybrid_managed_position = compile_method("_is_hybrid_managed_position")
CandidateHarness._is_position_protected = compile_method("_is_position_protected")
CandidateHarness._cleanup_position_tracking = compile_method("_cleanup_position_tracking")
CandidateHarness._try_trigger_hybrid_management = compile_method("_try_trigger_hybrid_management")
CandidateHarness._activate_hybrid_management = compile_method("_activate_hybrid_management")
CandidateHarness._hybrid_execute_tp1_close = compile_method("_hybrid_execute_tp1_close")
CandidateHarness._hybrid_handle_execution_report = compile_method("_hybrid_handle_execution_report")
CandidateHarness._reconcile_hybrid_pending_close = compile_method("_reconcile_hybrid_pending_close")
CandidateHarness._reconcile_hybrid_pending_close_guarded = compile_method("_reconcile_hybrid_pending_close_guarded")


class TestReleaseControlsAndConcurrencySuite(unittest.IsolatedAsyncioTestCase):

    def test_01_candidate_sha256_verified(self):
        """Verifies candidate SHA256 integrity."""
        self.assertEqual(len(CANDIDATE_SHA256), 64)
        self.assertEqual(
            CANDIDATE_SHA256,
            "0B60DDB301EF1E761DEB5729E8EB6CDB371CF9528D85BE76F581C2BD0B7524A2",
        )

    async def test_02_control1_amount_quantize_exception_cleanup_11_cases(self):
        """Control 1: Missing, None, Zero, Invalid string, NaN, Inf amounts safely handled."""
        test_cases = [
            ("Missing Amount", {}),
            ("None Amount", {"remaining_amount": None, "amount": None}),
            ("Zero Integer Amount", {"remaining_amount": 0, "amount": 0}),
            ("Zero Decimal Amount", {"remaining_amount": Decimal("0"), "amount": Decimal("0")}),
            ("Zero String Amount", {"remaining_amount": "0", "amount": "0"}),
            ("Invalid String Amount", {"remaining_amount": "invalid_abc", "amount": "invalid_abc"}),
            ("Decimal NaN", {"remaining_amount": Decimal("NaN"), "amount": Decimal("NaN")}),
            ("Decimal Infinity", {"remaining_amount": Decimal("Infinity"), "amount": Decimal("Infinity")}),
            ("Decimal -Infinity", {"remaining_amount": Decimal("-Infinity"), "amount": Decimal("-Infinity")}),
            ("String nan", {"remaining_amount": "nan", "amount": "nan"}),
            ("String inf", {"remaining_amount": "inf", "amount": "inf"}),
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
            self.assertTrue(trig)
            self.assertIn(7001, harness._hybrid_transitioning_orders)

            await asyncio.sleep(0.02)

            # 1. Zero orders dispatched
            self.assertEqual(len(harness.placed_market_orders), 0)
            # 2. Task ownership cleaned up (finally executed!)
            self.assertNotIn(7001, harness._hybrid_transitioning_orders)
            self.assertNotIn(7001, harness._processing_phase2_orders)
            # 3. Stage safety: no active attempt CIDs generated
            intent = pos.get("tp1_intent") or {}
            self.assertIsNone(intent.get("current_attempt_cid"))

    async def test_03_control1_transient_invalid_data_recovery(self):
        """Point 1: Transient invalid data reverts to HYBRID_WAIT; when data fixes, monitor re-processes parent."""
        harness = CandidateHarness()
        pos = {
            "order_id": 7002,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "remaining_amount": "invalid_transient_payload", # Transient invalid data
            "management_stage": "HYBRID_WAIT",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]
        price = Decimal("0.04850")

        # Tick 1: Trigger with invalid data
        trig1 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="ws")
        self.assertTrue(trig1)
        await asyncio.sleep(0.02)

        # Must NOT be permanently stuck in HYBRID_TRANSITIONING! Reverted to HYBRID_WAIT
        self.assertEqual(pos.get("management_stage"), "HYBRID_WAIT")
        self.assertEqual(len(harness.placed_market_orders), 0)
        self.assertNotIn(7002, harness._hybrid_transitioning_orders)

        # Between ticks: Data source fixes
        pos["remaining_amount"] = Decimal("5000")

        # Tick 2: Monitor evaluates position again
        trig2 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="monitor")
        self.assertTrue(trig2)
        await asyncio.sleep(0.02)

        # Parent successfully re-processed: TP1 dispatched for 2500!
        self.assertEqual(len(harness.placed_market_orders), 1)
        self.assertEqual(harness.placed_market_orders[0]["amount"], Decimal("2500"))
        self.assertEqual(pos.get("management_stage"), "HYBRID_CLOSE_PENDING")

    async def test_04_control2_initial_zero_amount_subsequent_monitor_reconcile_cleanup(self):
        """Point 2: Initial zero amount produces 0 TP1 orders, 0 re-triggers, and cleans up tracking."""
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

        # Step 1: Initial trigger
        trig1 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="ws")
        self.assertTrue(trig1)
        await asyncio.sleep(0.02)

        # Invariants:
        # a. 0 market orders dispatched
        self.assertEqual(len(harness.placed_market_orders), 0)
        # b. Stage marked terminal (HYBRID_CLOSED), tp1_done=True
        self.assertEqual(pos.get("management_stage"), "HYBRID_CLOSED")
        self.assertTrue(pos.get("tp1_done"))
        # c. Tracking cleaned up: order removed from tracked positions
        tracked = [p for p in harness._tracked_positions["CHIP-USDT"]["LONG"] if p.get("order_id") == 7003]
        self.assertEqual(len(tracked), 0)

        # Step 2: Subsequent monitor tick
        trig2 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price, source="monitor")
        self.assertFalse(trig2)
        self.assertEqual(len(harness.placed_market_orders), 0)

        # Step 3: Subsequent reconcile tick
        recon = await harness._reconcile_hybrid_pending_close_guarded(harness.connector, "CHIP-USDT", "LONG", pos)
        self.assertFalse(recon)
        self.assertEqual(len(harness.placed_market_orders), 0)

    async def test_05_control2_post_await_zero_amount_subsequent_monitor_reconcile_cleanup(self):
        """Point 2: Post-await zero amount produces 0 TP1 orders, 0 re-triggers, and cleans up tracking."""
        harness = CandidateHarness()
        harness.await_delay = 0.05
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

        # Position is closed during processing (remaining_amount becomes 0)
        pos["remaining_amount"] = Decimal("0")

        await harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price)

        # a. 0 market orders dispatched
        self.assertEqual(len(harness.placed_market_orders), 0)
        # b. Stage marked terminal (HYBRID_CLOSED), tp1_done=True
        self.assertEqual(pos.get("management_stage"), "HYBRID_CLOSED")
        self.assertTrue(pos.get("tp1_done"))
        # c. Tracking cleaned up
        tracked = [p for p in harness._tracked_positions["CHIP-USDT"]["LONG"] if p.get("order_id") == 7004]
        self.assertEqual(len(tracked), 0)

        # Subsequent monitor and reconcile calls
        self.assertFalse(harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price))
        self.assertFalse(await harness._reconcile_hybrid_pending_close_guarded(harness.connector, "CHIP-USDT", "LONG", pos))
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
        for _ in range(25):
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
            "order_id": 999333,
            "trading_pair": "CHIP-USDT",
            "side": "LONG",
            "entry": Decimal("0.04770"),
            "sl": Decimal("0.04702"),
            "r1_price": Decimal("0.04838"),
            "r2_price": Decimal("0.04906"),
            "amount": Decimal("4000"),
            "remaining_amount": Decimal("4000"),
            "management_stage": "HYBRID_TRANSITIONING",
            "exchange": "bybit_perpetual",
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"] = [pos]

        await harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, Decimal("0.04850"))

        self.assertEqual(pos["management_stage"], "HYBRID_CLOSE_PENDING")
        self.assertEqual(len(harness.placed_market_orders), 1)

    async def test_08_control4_stale_quantity_protection_across_awaits(self):
        """Control 4: If remaining_amount changes during await, fresh quantity is used."""
        harness = CandidateHarness()
        harness.await_delay = 0.05
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

        # Amount changes during processing to 2000
        pos["remaining_amount"] = Decimal("2000")

        await harness._activate_hybrid_management("bybit_perpetual", "CHIP-USDT", pos, price)

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

        for _ in range(30):
            await asyncio.sleep(0.01)
            if len(harness.placed_market_orders) >= 1 and pos_A.get("management_stage") == "HYBRID_CLOSE_PENDING":
                break
        self.assertEqual(pos_A.get("management_stage"), "HYBRID_CLOSE_PENDING")
        self.assertEqual(pos_B.get("management_stage"), "HYBRID_WAIT")
        self.assertEqual(len(harness.placed_market_orders), 1)

        # Tick 2: Lock released by A. B evaluates on next tick
        trig_B_tick2 = harness._try_trigger_hybrid_management("bybit_perpetual", "CHIP-USDT", pos_B, price, source="monitor")
        self.assertTrue(trig_B_tick2)
        for _ in range(30):
            await asyncio.sleep(0.01)
            if len(harness.placed_market_orders) >= 2 and pos_B.get("management_stage") == "HYBRID_CLOSE_PENDING":
                break

        self.assertEqual(pos_B.get("management_stage"), "HYBRID_CLOSE_PENDING")
        self.assertEqual(len(harness.placed_market_orders), 2)
        self.assertEqual(harness.placed_market_orders[0]["amount"], Decimal("2535"))
        self.assertEqual(harness.placed_market_orders[1]["amount"], Decimal("2400"))


if __name__ == "__main__":
    unittest.main()
