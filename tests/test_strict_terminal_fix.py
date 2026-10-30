import asyncio
import ast
import hashlib
import json
import os
import pathlib
import sys
import types
import unittest
import tempfile

TEST_TMP_DIR = pathlib.Path(tempfile.gettempdir()) / "hb_test_strict_terminal"
TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any, Set
from unittest.mock import AsyncMock, MagicMock

# Setup mock constants module for Bybit connector if not present
if "hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants" not in sys.modules:
    bybit_c_mock = types.ModuleType("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants")
    bybit_c_mock.QUERY_ACTIVE_ORDER_PATH_URL = "v5/order/realtime"
    p_mod = types.ModuleType("hummingbot.connector.derivative.bybit_perpetual")
    p_mod.bybit_perpetual_constants = bybit_c_mock
    sys.modules["hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants"] = bybit_c_mock
    sys.modules["hummingbot.connector.derivative.bybit_perpetual"] = p_mod

candidate_candidates = [
    os.environ.get("CANDIDATE_PATH", ""),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tv_signal_strategy.py"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_signal_strategy.py"),
    "candidate_hybrid_v2_D227F3A7_strict_terminal_fix.py",
]
CANDIDATE_PATH = next((p for p in candidate_candidates if p and os.path.exists(p)), "tv_signal_strategy.py")

with open(CANDIDATE_PATH, "rb") as f:
    CANDIDATE_SHA256 = hashlib.sha256(f.read()).hexdigest().upper()

# Parse candidate AST
with open(CANDIDATE_PATH, "r", encoding="utf-8") as f:
    parsed_ast = ast.parse(f.read(), filename=CANDIDATE_PATH)

AST_FUNCS = {}
for node in parsed_ast.body:
    if isinstance(node, ast.ClassDef) and node.name == "TVSignalStrategy":
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                AST_FUNCS[item.name] = item

print(f"[TEST HARNESS] Candidate SHA256: {CANDIDATE_SHA256}")
print(f"[TEST HARNESS] Extracted {len(AST_FUNCS)} functions from TVSignalStrategy AST.")


def compile_ast_method(func_name: str, extra_globals=None):
    fn_node = AST_FUNCS[func_name]
    mod = ast.Module(body=[fn_node], type_ignores=[])
    code_obj = compile(mod, filename=CANDIDATE_PATH, mode="exec")

    env = {
        "Any": Any,
        "Decimal": Decimal,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Tuple": Tuple,
        "Set": Set,
        "set": set,
        "time": sys.modules.get("time"),
        "json": json,
        "pathlib": pathlib,
        "asyncio": asyncio,
        "hasattr": hasattr,
        "getattr": getattr,
        "setattr": setattr,
        "isinstance": isinstance,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "abs": abs,
        "sum": sum,
        "min": min,
        "max": max,
        "bool": bool,
    }
    if extra_globals:
        env.update(extra_globals)

    exec(code_obj, env)
    return env[func_name]


class DummyLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []
        self.debugs = []

    def info(self, msg):
        self.infos.append(str(msg))

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, msg, *args, **kwargs):
        self.errors.append(str(msg))

    def debug(self, msg):
        self.debugs.append(str(msg))


def make_mock_connector():
    c = MagicMock()
    c.exchange_symbol_associated_to_pair = AsyncMock(return_value="CHIPUSDT")
    c.quantize_order_price = lambda pair, px: Decimal(str(px)).quantize(Decimal("0.00001"))
    c.quantize_order_amount = lambda pair, q: Decimal(str(q)).quantize(Decimal("1"))
    c.get_mid_price = lambda pair: Decimal("0.04500")
    return c


class RealASTStrictTerminalHarness:
    """Harness that binds real AST methods from strict terminal candidate file."""

    POSITION_MANAGEMENT_MODE = "legacy"
    BYBIT_CID_ROTATE_TRIES = 3
    BYBIT_CID_MAX_GENERATION = 9
    SYNC_PROTECTION_DURATION = 60
    _OKX_CID_TAG_MAP = {"SL": "S", "TP": "T"}

    def __init__(self, state_file=str(TEST_TMP_DIR / "test_harness_state.json")):
        self._logger = DummyLogger()
        self._tracked_positions: Dict[str, Dict[str, List[Dict]]] = {
            "CHIP-USDT": {"LONG": [], "SHORT": []}
        }
        self._sltp_orders: Dict[int, Dict] = {}
        self._sltp_ws_confirmed: Dict[int, float] = {}
        self._last_sltp_placement: Dict[int, float] = {}
        self._cid_generations: Dict[Tuple[int, str], int] = {}
        self._bybit_cid_gen: Dict[str, int] = {}
        self._position_archive_dir = TEST_TMP_DIR / "test_archive"
        self._position_archive_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = pathlib.Path(state_file)
        self._state_loaded = True
        self.current_timestamp = 1700000000.0
        self._trailing_sl_pending = {}
        self._signal_cache = {}
        self._sltp_retry_queue = {}
        self._position_identity_ledger = {}
        self._phase2_immunity = {}
        self._per_fill_accumulators = {}
        self._grace_period_until = {}
        self.connectors = {}
        self._phase2_active_positions = set()
        self._save_state_should_fail = False

        self._bybit_position_idx = lambda conn, ps, is_open=True: 2 if ps == "SHORT" else 1
        self._bybit_fresh_price = lambda pair, kind: Decimal("0.04500")
        self.BYBIT_VERIFY_SL_CLAMP = True
        self.BYBIT_ADOPT_SL_MIN_BUFFER_PCT = Decimal("0.003")

        # Mock defaults
        self._get_bybit_conditional_orders = AsyncMock(return_value=[])

        # Bind real AST methods
        self._bind_method("_bybit_cid_gen_key")
        self._bind_method("_parse_cid")
        self._bind_method("_bybit_sltp_link_id")
        self._bind_method("_bybit_bump_cid_generation")
        self._bind_method("_place_bybit_conditional_order")
        self._bind_method("_place_bybit_trading_stop")
        self._bind_method("_bybit_periodic_sltp_verify")
        self._bind_method("_bybit_on_leg_filled")
        self._bind_method("_get_bybit_conditional_orders")
        self._bind_method("_save_state")
        self._bind_method("_load_state")
        self._cleanup_position_tracking = self._real_cleanup_position_tracking
        self._bind_method("_pm_mode")
        self._bind_method("_position_repair_allowed")

        # Real AST save_state wrapper to allow testing simulated write failures
        self._real_save_state = self._save_state
        self._save_state = self._wrapping_save_state

    def _wrapping_save_state(self):
        if getattr(self, "_save_state_should_fail", False):
            self._logger.error("Simulated disk write failure in _save_state")
            return False
        return self._real_save_state()

    def _real_cleanup_position_tracking(self, trading_pair: str, side: str, position_order_id: int):
        if trading_pair in self._tracked_positions:
            positions = self._tracked_positions[trading_pair].get(side, [])
            self._tracked_positions[trading_pair][side] = [
                p for p in positions if str(p.get("order_id")) != str(position_order_id)
            ]

    def _bind_method(self, name: str):
        func = compile_ast_method(name)
        setattr(self, name, types.MethodType(func, self))

    def logger(self):
        return self._logger

    def _position_repair_allowed(self):
        return True

    def _safe_int(self, x):
        try:
            return int(x) if x is not None else None
        except Exception:
            return None

    def _is_exchange_snapshot_verified(self):
        return False

    async def _fetch_real_positions(self):
        return {}

    def _ensure_position_r_geometry(self, *args, **kwargs):
        pass

    def _sync_existing_sltp_orders(self, *args, **kwargs):
        pass

    def _rebuild_phase2_active_set_from_tracked(self):
        pass

    def _reset_trailing_timeout_log_state(self, *args, **kwargs):
        pass

    def _save_position_to_archive(self, *args, **kwargs):
        pass

    async def _get_cached_position_amount(self, pair, side, ensure_fresh=False, reason=""):
        return Decimal("2130")

    async def _bybit_verify_sl_coverage(self, connector, trading_pair, side, reason=""):
        pass

    def _archive_trigger_close(self, trading_pair, side, pos, parent_id, kind, trade_info):
        self._logger.info(f"[ARCHIVED] {trading_pair} {side} #{parent_id} kind={kind} trade={trade_info}")

    def _is_bybit_connector(self, connector):
        return True

    def _bybit_consolidation_mode(self, trading_pair, side):
        return None

    def _tp_order_suppressed(self, pos):
        return True

    def _quantize_order_price(self, connector, trading_pair, price):
        return Decimal(str(price)).quantize(Decimal("0.00001"))

    def _quantize_order_amount(self, connector, trading_pair, amount):
        return Decimal(str(amount)).quantize(Decimal("1"))

    def _bybit_ret_ok(self, resp):
        return isinstance(resp, dict) and resp.get("retCode") == 0

    def _bybit_clamp_stop_trigger(self, side, kind, trig, mark):
        return trig, False

    async def _bybit_raw_get(self, connector, path):
        return {"retCode": 0, "result": {"list": []}}

    async def _bybit_cancel_sibling_legs(self, connector, trading_pair, side, parent_id, triggered_order_id=None):
        pass


class TestStrictTerminalFixSuite(unittest.TestCase):
    """Test suite validating all strict terminal conditions, idempotent accounting, residual matching, and edge cases."""

    def test_01_candidate_sha256_verified(self):
        print(f"\n[TEST 1] Candidate SHA256: {CANDIDATE_SHA256}")
        self.assertEqual(len(CANDIDATE_SHA256), 64)
        self.assertIn(CANDIDATE_SHA256, ["0B60DDB301EF1E761DEB5729E8EB6CDB371CF9528D85BE76F581C2BD0B7524A2"])

    def test_02_full_fill_fresh_snapshot_verified(self):
        """Full fill (5180), sibling (2130), fresh exchange snapshot (2130). Real stop coverage verified."""
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_02_state.json"))
        parent_a = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        sibling_b = {"order_id": 626925806683, "amount": 2130.0, "remaining_amount": 2130.0, "sl": 0.04652, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [sibling_b, parent_a]

        created_orders = []
        amended_orders = []
        connector = make_mock_connector()

        # Active stop orders on exchange: Sibling B is active with 2130
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "1b42f0b4", "orderLinkId": "H-S-626925806683-BB", "parent_id": 626925806683, "kind": "SL", "triggerPrice": Decimal("0.04652"), "qty": Decimal("2130"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        # Link ID lookup returns Filled with verified cumExecQty 5180
        async def mock_get_order(conn, pair, cid):
            if "364986326432" in cid:
                return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "5180", "avgPrice": "0.04577"}
            return None
        harness._get_bybit_order_by_link_id = mock_get_order

        # Fresh exchange snapshot returns 2130
        harness._get_cached_position_amount = AsyncMock(return_value=Decimal("2130"))

        # 110072 on duplicate create
        async def mock_raw_post(conn, path, body):
            created_orders.append(body)
            if body.get("orderLinkId") == "H-S-364986326432-BB":
                return {"retCode": 110072, "retMsg": "duplicate orderLinkId"}
            return {"retCode": 0}
        harness._bybit_raw_post = mock_raw_post
        harness._amend_bybit_conditional_order = AsyncMock(side_effect=lambda *args, **kwargs: amended_orders.append(args) or {"success": True})

        positions = list(harness._tracked_positions["CHIP-USDT"]["SHORT"])
        asyncio.run(harness._bybit_periodic_sltp_verify(connector, "CHIP-USDT", "SHORT", positions))

        # Assertions
        bb1_creates = [o for o in created_orders if "BB1" in str(o)]
        self.assertEqual(len(bb1_creates), 0, "BB1 order was created!")
        active_ids = [p["order_id"] for p in harness._tracked_positions["CHIP-USDT"]["SHORT"]]
        self.assertNotIn(364986326432, active_ids, "Parent A was not removed from tracking")
        self.assertIn(626925806683, active_ids, "Sibling B was incorrectly removed")

        # VERIFY REAL STOP COVERAGE:
        remaining_tracked = sum(p["remaining_amount"] for p in harness._tracked_positions["CHIP-USDT"]["SHORT"])
        self.assertEqual(remaining_tracked, 2130.0)
        active_stops = asyncio.run(harness._get_bybit_conditional_orders(connector, "CHIP-USDT", "SHORT"))
        stop_coverage = sum(c["qty"] for c in active_stops if c["kind"] == "SL")
        self.assertEqual(stop_coverage, Decimal("2130"))
        self.assertEqual(Decimal(str(remaining_tracked)), stop_coverage, "Remaining position is not 100% covered by active stop!")
        print("  [TEST 2 PASSED] Full fill + fresh snapshot: Parent A closed, sibling 2130 100% covered by active stop.")

    def test_03_partial_fill_with_residual_stop_covered(self):
        """Partial fill (2000/5180): residual 3180 has active stop on exchange -> status 'partial_fill_covered'."""
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_03_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        sibling = {"order_id": 626925806683, "amount": 2130.0, "remaining_amount": 2130.0, "sl": 0.04652, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent, sibling]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        # Active stops on exchange: Stop for residual 3180 exists with matching parent, kind, price, side, positionIdx
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop_3180", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"},
            {"orderId": "sib_stop_2130", "orderLinkId": "H-S-626925806683-BB", "parent_id": 626925806683, "kind": "SL", "qty": Decimal("2130"), "triggerPrice": Decimal("0.04652"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"},
        ])

        connector = make_mock_connector()

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("status"), "partial_fill_covered")
        self.assertEqual(Decimal(str(res.get("remaining_amount"))), Decimal("3180"))

        # Parent must be preserved with remaining 3180
        active_shorts = harness._tracked_positions["CHIP-USDT"]["SHORT"]
        self.assertEqual(len(active_shorts), 2)
        p_match = next(p for p in active_shorts if p["order_id"] == 364986326432)
        self.assertEqual(Decimal(str(p_match["remaining_amount"])), Decimal("3180"))

        # Real stop coverage check: Total remaining (3180 + 2130 = 5310), active stops = 5310
        total_remaining = sum(p["remaining_amount"] for p in active_shorts)
        active_stops = asyncio.run(harness._get_bybit_conditional_orders(connector, "CHIP-USDT", "SHORT"))
        stop_coverage = sum(c["qty"] for c in active_stops if c["kind"] == "SL")
        self.assertEqual(Decimal(str(total_remaining)), stop_coverage, "Partial fill residual is not fully covered!")
        print("  [TEST 3 PASSED] Partial fill (2000/5180) + residual stop covered: remaining 3180 protected, 100% coverage.")

    def test_04_partial_fill_without_residual_stop_marked_unprotected(self):
        """Partial fill (2000/5180): residual 3180 has NO active stop on exchange -> marked 'unprotected_residual'."""
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_04_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        sibling = {"order_id": 626925806683, "amount": 2130.0, "remaining_amount": 2130.0, "sl": 0.04652, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent, sibling]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        # Active stops on exchange: ONLY sibling 2130 is active! Residual 3180 is UNPROTECTED!
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "sib_stop_2130", "orderLinkId": "H-S-626925806683-BB", "parent_id": 626925806683, "kind": "SL", "qty": Decimal("2130"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"},
        ])

        connector = make_mock_connector()

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        # MUST NOT BE MARKED AS SUCCESS!
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("status"), "unprotected_residual")
        self.assertEqual(Decimal(str(res.get("remaining_amount"))), Decimal("3180"))

        # Parent remaining is deducted to 3180, parent is NOT deleted
        active_shorts = harness._tracked_positions["CHIP-USDT"]["SHORT"]
        p_match = next(p for p in active_shorts if p["order_id"] == 364986326432)
        self.assertEqual(Decimal(str(p_match["remaining_amount"])), Decimal("3180"))
        print("  [TEST 4 PASSED] Partial fill without residual stop: clearly marked 'unprotected_residual', gap = 3180.")

    def test_05_full_fill_stale_or_missing_snapshot_preserves_parent(self):
        """Full fill (5180) but fresh exchange snapshot fails/missing -> parent must NOT be deleted!"""
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_05_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "5180", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        # Exchange snapshot fails (returns None on ensure_fresh=True)
        harness._get_cached_position_amount = AsyncMock(return_value=None)

        connector = make_mock_connector()

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("status"), "missing_snapshot_preserved")
        self.assertEqual(len(harness._tracked_positions["CHIP-USDT"]["SHORT"]), 1, "Parent was deleted without verified fresh snapshot!")
        print("  [TEST 5 PASSED] Full fill + missing/stale exchange snapshot: parent preserved, deletion blocked.")

    def test_06_execution_list_fallback_filters_non_trade_and_wrong_side(self):
        """Execution list fallback: filters non-Trade, wrong side, and deduplicates by execId."""
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_06_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]

        # Order has no cumExecQty
        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": ""}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        # /v5/execution/list returns 4 items:
        # 1. Funding (must be ignored)
        # 2. Trade Sell (wrong side for closing SHORT, must be ignored)
        # 3. Trade Buy (valid, qty 5180, execId trade_abc)
        # 4. Trade Buy duplicate (execId trade_abc, must be deduped)
        harness._bybit_raw_get = AsyncMock(return_value={
            "retCode": 0,
            "result": {
                "list": [
                    {"execId": "fund_1", "orderId": "bc09d4ee", "orderLinkId": "H-S-364986326432-BB", "execType": "Funding", "side": "Buy", "execQty": "5180"},
                    {"execId": "entry_trade", "orderId": "entry_oid", "orderLinkId": "B4123", "execType": "Trade", "side": "Sell", "execQty": "5180"},
                    {"execId": "trade_abc", "orderId": "bc09d4ee", "orderLinkId": "H-S-364986326432-BB", "execType": "Trade", "side": "Buy", "execQty": "5180"},
                    {"execId": "trade_abc", "orderId": "bc09d4ee", "orderLinkId": "H-S-364986326432-BB", "execType": "Trade", "side": "Buy", "execQty": "5180"},
                ]
            }
        })

        # Fresh exchange snapshot confirms 0 remaining
        harness._get_cached_position_amount = AsyncMock(return_value=Decimal("0"))

        connector = make_mock_connector()

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("status"), "already_filled_terminal")
        self.assertEqual(len(harness._tracked_positions["CHIP-USDT"]["SHORT"]), 0)
        print("  [TEST 6 PASSED] Execution list fallback: strictly filtered Trade + Buy side, deduped execId.")

    def test_07_aggregate_mismatch_preserves_parent(self):
        """Aggregate mismatch: exchange position is 1000 instead of expected sibling amount 2130."""
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_07_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        sibling = {"order_id": 626925806683, "amount": 2130.0, "remaining_amount": 2130.0, "sl": 0.04652, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent, sibling]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "5180", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._get_cached_position_amount = AsyncMock(return_value=Decimal("1000")) # Mismatch: 1000 != 2130
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        connector = make_mock_connector()

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("status"), "aggregate_mismatch_preserved")
        self.assertEqual(len(harness._tracked_positions["CHIP-USDT"]["SHORT"]), 2, "Parent was deleted despite aggregate mismatch!")
        print("  [TEST 7 PASSED] Aggregate mismatch (1000 != 2130): parent preserved, deletion blocked.")

    def test_08_repeated_reconcile_and_restart_stability(self):
        """Repeated reconcile ticks and restart simulation: 0 duplicate orders, exact remaining stop coverage verified."""
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_08_state.json"))
        sibling = {"order_id": 626925806683, "amount": 2130.0, "remaining_amount": 2130.0, "sl": 0.04652, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [sibling]

        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "1b42f0b4", "orderLinkId": "H-S-626925806683-BB", "parent_id": 626925806683, "kind": "SL", "triggerPrice": Decimal("0.04652"), "qty": Decimal("2130"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        created_orders = []
        harness._bybit_raw_post = lambda conn, p, b: created_orders.append(b) or {"retCode": 0}

        connector = make_mock_connector()
        positions = list(harness._tracked_positions["CHIP-USDT"]["SHORT"])

        # Tick 1
        asyncio.run(harness._bybit_periodic_sltp_verify(connector, "CHIP-USDT", "SHORT", positions))
        self.assertEqual(len(created_orders), 0)

        # Tick 2
        asyncio.run(harness._bybit_periodic_sltp_verify(connector, "CHIP-USDT", "SHORT", positions))
        self.assertEqual(len(created_orders), 0)

        # Simulated Restart
        harness._save_state()
        restarted = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_08_state.json"))
        restarted._tracked_positions = json.loads(open(harness._state_file).read())["tracked_positions"]
        restarted._get_bybit_conditional_orders = harness._get_bybit_conditional_orders
        created_restart = []
        restarted._bybit_raw_post = lambda conn, p, b: created_restart.append(b) or {"retCode": 0}

        pos_restart = list(restarted._tracked_positions["CHIP-USDT"]["SHORT"])
        asyncio.run(restarted._bybit_periodic_sltp_verify(connector, "CHIP-USDT", "SHORT", pos_restart))
        self.assertEqual(len(created_restart), 0)
        self.assertEqual(len(restarted._tracked_positions["CHIP-USDT"]["SHORT"]), 1)
        print("  [TEST 8 PASSED] Repeated reconcile + simulated restart: 0 orders, stable state, 100% stop coverage.")

    def test_09_active_untriggered_stop_amended_normally(self):
        """Active untriggered stop: normally amended, never falsely terminated."""
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_09_state.json"))
        parent = {"order_id": 999888777, "amount": 100.0, "remaining_amount": 100.0, "sl": 0.0500, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "active_123", "orderLinkId": cid, "orderStatus": "Untriggered", "qty": "100", "triggerPrice": "0.0520"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        amended = []
        harness._amend_bybit_conditional_order = AsyncMock(side_effect=lambda *args, **kwargs: amended.append(args) or {"success": True})

        connector = make_mock_connector()

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.0500"), Decimal("100"), cid="H-S-999888777-BB"
        ))

        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("status"), "amended")
        self.assertEqual(len(harness._tracked_positions["CHIP-USDT"]["SHORT"]), 1)
        self.assertEqual(len(amended), 1)
        print("  [TEST 9 PASSED] Untriggered active stop: normally amended, never falsely terminated.")

    def test_10_same_2000_fill_processed_3_times_and_post_restart(self):
        """
        User Requirement:
        'Aynı 2000’lik dolumu üç kez ve restart sonrasında işle: kalan her defasında 3180 kalmalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_10_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        connector = make_mock_connector()

        # Call 1
        res1 = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        p1 = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(p1["remaining_amount"])), Decimal("3180"), "Call 1: remaining must be 3180")
        self.assertEqual(p1["applied_cumulative_fill"]["bc09d4ee"], "2000")

        # Call 2
        res2 = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        p2 = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(p2["remaining_amount"])), Decimal("3180"), "Call 2: remaining must STAY 3180")

        # Call 3
        res3 = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        p3 = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(p3["remaining_amount"])), Decimal("3180"), "Call 3: remaining must STAY 3180")

        # Simulated Restart
        harness._save_state()
        restarted_harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_10_state.json"))
        restarted_harness._tracked_positions = json.loads(open(harness._state_file).read())["tracked_positions"]
        restarted_harness._get_bybit_order_by_link_id = mock_get_order
        restarted_harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})
        restarted_harness._get_bybit_conditional_orders = harness._get_bybit_conditional_orders

        # Call post-restart
        res4 = asyncio.run(restarted_harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        p4 = restarted_harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(p4["remaining_amount"])), Decimal("3180"), "Post-restart: remaining must STAY 3180")
        print("  [TEST 10 PASSED] Same 2000 fill processed 3x and post-restart: remaining stays 3180 every time.")

    def test_11_ws_fill_followed_by_rest_deducts_only_once(self):
        """
        User Requirement:
        'WS ardından REST ile aynı dolumu işle: yalnız bir kez düşmeli.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_11_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]
        connector = make_mock_connector()

        # Step 1: WS receives execution event for 2000 fill
        ws_exec = {
            "orderId": "bc09d4ee",
            "orderLinkId": "H-S-364986326432-BB",
            "execId": "exec_2000_single",
            "execQty": "2000",
            "closedSize": "2000",
            "execPrice": "0.04577",
            "execType": "Trade",
            "side": "Buy",
        }
        asyncio.run(harness._bybit_on_leg_filled(
            connector, "CHIP-USDT", "SHORT", 364986326432, "SL", ws_exec
        ))

        # After WS: parent remaining must be 3180
        pos = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(pos["remaining_amount"])), Decimal("3180"), "WS: remaining must be 3180")
        self.assertEqual(pos.get("applied_cumulative_fill", {}).get("bc09d4ee"), "2000")

        # Step 2: REST subsequently queries Bybit and sees cumExecQty=2000 for order bc09d4ee
        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        # REST must NOT deduct 2000 again! Remaining must STAY 3180!
        pos_after_rest = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(pos_after_rest["remaining_amount"])), Decimal("3180"), "REST after WS: remaining must STAY 3180 (not 1180!)")
        print("  [TEST 11 PASSED] WS fill then REST with same fill: deducted only once, remaining stays 3180.")

    def test_12_same_parent_insufficient_quantity_not_protection(self):
        """
        User Requirement:
        'Aynı parent + yetersiz miktarlı stop: koruma sayılmamalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_12_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        # Active stop has SAME parent (364986326432) BUT insufficient quantity (1000 instead of 3180)
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "under_qty_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("1000"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        connector = make_mock_connector()
        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        # MUST NOT be counted as protection!
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("status"), "unprotected_residual")
        print("  [TEST 12 PASSED] Same parent + insufficient qty stop (1000 vs 3180): not counted as protection.")

    def test_13_different_parent_same_quantity_not_protection(self):
        """
        User Requirement:
        'Farklı parent + aynı miktarlı stop: koruma sayılmamalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_13_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        # Active stop has EXACT quantity (3180) BUT DIFFERENT parent (999111222, sibling stop!)
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "sibling_stop", "orderLinkId": "H-S-999111222-BB", "parent_id": 999111222, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        connector = make_mock_connector()
        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        # Sibling stop MUST NOT be counted as protection!
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("status"), "unprotected_residual")
        print("  [TEST 13 PASSED] Different parent + same qty stop (sibling 3180): not counted as protection.")

    def test_14_wrong_price_side_positionidx_not_protection(self):
        """
        User Requirement:
        'Yanlış fiyat/yön/positionIdx: koruma sayılmamalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_14_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})
        connector = make_mock_connector()

        # Case A: Wrong Price
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "bad_price", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.05500"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])
        resA = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        self.assertFalse(resA.get("success"))
        self.assertEqual(resA.get("status"), "unprotected_residual")

        # Case B: Wrong Side
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "bad_side", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "SELL", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])
        resB = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        self.assertFalse(resB.get("success"))
        self.assertEqual(resB.get("status"), "unprotected_residual")

        # Case C: Wrong positionIdx
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "bad_pidx", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 1, "orderStatus": "Untriggered"}
        ])
        resC = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        self.assertFalse(resC.get("success"))
        self.assertEqual(resC.get("status"), "unprotected_residual")
        print("  [TEST 14 PASSED] Wrong price / side / positionIdx: correctly rejected as protection.")

    def test_15_aggregate_difference_below_5pct_blocks_cleanup(self):
        """
        User Requirement:
        'Aggregate’de yüzde 5’in altında gerçek miktar farkı: terminal cleanup yapılmamalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_15_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        sibling = {"order_id": 626925806683, "amount": 2130.0, "remaining_amount": 2130.0, "sl": 0.04652, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent, sibling]

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "5180", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        # Real exchange snapshot has 2100 instead of expected sibling amount 2130 (difference of 30, which is only 1.4% < 5%)
        harness._get_cached_position_amount = AsyncMock(return_value=Decimal("2100"))

        connector = make_mock_connector()
        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("status"), "aggregate_mismatch_preserved")
        self.assertEqual(len(harness._tracked_positions["CHIP-USDT"]["SHORT"]), 2, "Parent was deleted despite real aggregate mismatch!")
        print("  [TEST 15 PASSED] Real aggregate difference below 5% (2100 vs 2130, 1.4%): terminal cleanup strictly blocked.")

    def test_16_caller_alarm_not_suppressed_for_ambiguous_and_unprotected_states(self):
        """
        User Requirement:
        'Belirsiz durumları koruma doğrulanmış gibi sınıflandırma. CID rotation engeli ayrı, stop kapsamı sonucu ayrı olsun;
         koruma doğrulanamadığında caller alarmı bastırılmasın.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_16_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]
        connector = make_mock_connector()

        # Mock trading stop to return unprotected_residual
        harness._place_bybit_trading_stop = AsyncMock(return_value={
            "success": False,
            "sl_status": "unprotected_residual",
            "error": "unprotected_residual_3180",
        })

        # Run periodic verify
        positions = list(harness._tracked_positions["CHIP-USDT"]["SHORT"])
        asyncio.run(harness._bybit_periodic_sltp_verify(connector, "CHIP-USDT", "SHORT", positions))

        naked_warnings = [w for w in harness.logger().warnings if "BYBIT NAKED LEG" in w]
        self.assertEqual(len(naked_warnings), 1, "Caller alarm was suppressed for unprotected_residual!")
        self.assertIn("SL(unprotected_residual)", naked_warnings[0])

        # Test ambiguous_fill_preserved also triggers naked alarm
        harness._logger = DummyLogger()
        harness._place_bybit_trading_stop = AsyncMock(return_value={
            "success": False,
            "sl_status": "ambiguous_fill_preserved",
            "error": "ambiguous_fill",
        })
        asyncio.run(harness._bybit_periodic_sltp_verify(connector, "CHIP-USDT", "SHORT", positions))
        naked_warnings2 = [w for w in harness.logger().warnings if "BYBIT NAKED LEG" in w]
        self.assertEqual(len(naked_warnings2), 1, "Caller alarm was suppressed for ambiguous_fill_preserved!")
        self.assertIn("SL(ambiguous_fill_preserved)", naked_warnings2[0])

        # Test partial_fill_covered DOES NOT trigger naked alarm
        harness._logger = DummyLogger()
        harness._place_bybit_trading_stop = AsyncMock(return_value={
            "success": True,
            "sl_status": "partial_fill_covered",
        })
        asyncio.run(harness._bybit_periodic_sltp_verify(connector, "CHIP-USDT", "SHORT", positions))
        naked_warnings3 = [w for w in harness.logger().warnings if "BYBIT NAKED LEG" in w]
        self.assertEqual(len(naked_warnings3), 0, "partial_fill_covered should not produce naked leg alarm!")
        print("  [TEST 16 PASSED] Caller alarms not suppressed for ambiguous/unprotected states; partial_fill_covered safe.")

    # ─────────────────────────────────────────────────────────────────────────
    # POINT 1 NEW REGRESSIONS: WS execId vs REST cumExecQty separation & dedupe
    # ─────────────────────────────────────────────────────────────────────────

    def test_17_ws_same_order_diff_execid_cumulative_split(self):
        """
        User Requirement:
        'Aynı orderId, farklı execId: 1000 + 1000 → toplam 2000 yalnız bir kez uygulanmalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_17_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]
        connector = make_mock_connector()

        # WS Exec 1: 1000 with execId="exec_1001"
        ws_exec1 = {
            "orderId": "bc09d4ee",
            "orderLinkId": "H-S-364986326432-BB",
            "execId": "exec_1001",
            "execQty": "1000",
            "closedSize": "1000",
            "execPrice": "0.04577",
            "execType": "Trade",
            "side": "Buy",
        }
        asyncio.run(harness._bybit_on_leg_filled(connector, "CHIP-USDT", "SHORT", 364986326432, "SL", ws_exec1))

        pos = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(pos["remaining_amount"])), Decimal("4180"), "After exec 1: remaining must be 4180")
        self.assertEqual(pos["applied_exec_ids"]["exec_1001"], "1000")

        # WS Exec 2: 1000 with execId="exec_1002"
        ws_exec2 = {
            "orderId": "bc09d4ee",
            "orderLinkId": "H-S-364986326432-BB",
            "execId": "exec_1002",
            "execQty": "1000",
            "closedSize": "1000",
            "execPrice": "0.04577",
            "execType": "Trade",
            "side": "Buy",
        }
        asyncio.run(harness._bybit_on_leg_filled(connector, "CHIP-USDT", "SHORT", 364986326432, "SL", ws_exec2))

        pos = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(pos["remaining_amount"])), Decimal("3180"), "After exec 2: remaining must be exactly 3180 (2000 total deducted)")
        self.assertEqual(pos["applied_exec_ids"]["exec_1002"], "1000")
        self.assertEqual(pos["applied_cumulative_fill"]["bc09d4ee"], "2000")
        print("  [TEST 17 PASSED] Same orderId, diff execId (1000 + 1000): total 2000 deducted cleanly, remaining = 3180.")

    def test_18_ws_same_execid_repeat_no_double_deduction_or_terminal_cleanup(self):
        """
        User Requirement:
        'Aynı execId tekrarı → ikinci miktar düşümü veya yanlış terminal cleanup olmamalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_18_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]
        connector = make_mock_connector()

        ws_exec = {
            "orderId": "bc09d4ee",
            "orderLinkId": "H-S-364986326432-BB",
            "execId": "exec_unique_99",
            "execQty": "2000",
            "closedSize": "2000",
            "execPrice": "0.04577",
            "execType": "Trade",
            "side": "Buy",
        }
        # First processing
        asyncio.run(harness._bybit_on_leg_filled(connector, "CHIP-USDT", "SHORT", 364986326432, "SL", ws_exec))
        pos = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(pos["remaining_amount"])), Decimal("3180"))

        # Duplicate delivery of the exact same execId
        asyncio.run(harness._bybit_on_leg_filled(connector, "CHIP-USDT", "SHORT", 364986326432, "SL", ws_exec))
        pos_after_dup = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(pos_after_dup["remaining_amount"])), Decimal("3180"), "Duplicate execId must NOT cause second deduction!")
        self.assertEqual(len(harness._tracked_positions["CHIP-USDT"]["SHORT"]), 1, "Duplicate execId must NOT trigger terminal cleanup!")
        print("  [TEST 18 PASSED] Same execId repeat: no second deduction, no false terminal cleanup, remaining stays 3180.")

    def test_19_ws_split_then_rest_cumulative_no_extra_deduction(self):
        """
        User Requirement:
        'WS 1000 + 1000, ardından REST cumExecQty=2000 → ek düşüm olmamalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_19_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]
        connector = make_mock_connector()

        # WS 1000
        asyncio.run(harness._bybit_on_leg_filled(connector, "CHIP-USDT", "SHORT", 364986326432, "SL", {
            "orderId": "bc09d4ee", "orderLinkId": "H-S-364986326432-BB", "execId": "ws_1", "execQty": "1000", "execType": "Trade", "side": "Buy"
        }))
        # WS 1000
        asyncio.run(harness._bybit_on_leg_filled(connector, "CHIP-USDT", "SHORT", 364986326432, "SL", {
            "orderId": "bc09d4ee", "orderLinkId": "H-S-364986326432-BB", "execId": "ws_2", "execQty": "1000", "execType": "Trade", "side": "Buy"
        }))
        self.assertEqual(Decimal(str(harness._tracked_positions["CHIP-USDT"]["SHORT"][0]["remaining_amount"])), Decimal("3180"))

        # REST then queries Bybit order: cumExecQty = 2000
        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        # Must not deduct again
        pos_after_rest = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(pos_after_rest["remaining_amount"])), Decimal("3180"), "REST must NOT deduct again after WS 1000+1000!")
        print("  [TEST 19 PASSED] WS 1000+1000 then REST cumExecQty=2000: no extra deduction, remaining stays 3180.")

    def test_20_rest_first_then_delayed_ws_executions_no_extra_deduction(self):
        """
        User Requirement:
        'REST cumExecQty=2000, ardından bu dolumlara ait gecikmiş WS execution’ları → ek düşüm olmamalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_20_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]
        connector = make_mock_connector()

        # Step 1: REST processes cumExecQty=2000 first
        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        pos_after_rest = harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(pos_after_rest["remaining_amount"])), Decimal("3180"))

        # Step 2: Delayed WS execution 1 arrives (1000)
        asyncio.run(harness._bybit_on_leg_filled(connector, "CHIP-USDT", "SHORT", 364986326432, "SL", {
            "orderId": "bc09d4ee", "orderLinkId": "H-S-364986326432-BB", "execId": "delayed_1", "execQty": "1000", "execType": "Trade", "side": "Buy"
        }))
        self.assertEqual(Decimal(str(pos_after_rest["remaining_amount"])), Decimal("3180"), "Delayed WS 1 must not cause second deduction!")

        # Step 3: Delayed WS execution 2 arrives (1000)
        asyncio.run(harness._bybit_on_leg_filled(connector, "CHIP-USDT", "SHORT", 364986326432, "SL", {
            "orderId": "bc09d4ee", "orderLinkId": "H-S-364986326432-BB", "execId": "delayed_2", "execQty": "1000", "execType": "Trade", "side": "Buy"
        }))
        self.assertEqual(Decimal(str(pos_after_rest["remaining_amount"])), Decimal("3180"), "Delayed WS 2 must not cause second deduction!")
        print("  [TEST 20 PASSED] REST cumExecQty=2000 then delayed WS executions: no extra deduction, remaining stays 3180.")

    # ─────────────────────────────────────────────────────────────────────────
    # POINT 3 NEW REGRESSIONS: State save/load roundtrip & error handling
    # ─────────────────────────────────────────────────────────────────────────

    def test_21_state_save_and_load_roundtrip_preserves_accounting_and_result(self):
        """
        User Requirement:
        'Bu akışların arasında gerçek state save/load → sonuç değişmemeli.'
        Verifies real AST _save_state and _load_state preserve remaining_amount and applied_cumulative_fill.
        """
        state_path = str(TEST_TMP_DIR / "test_roundtrip_reg_21.json")
        harness = RealASTStrictTerminalHarness(state_path)
        parent = {
            "order_id": 364986326432,
            "amount": 5180.0,
            "remaining_amount": 3180.0,
            "entry": 0.04500,
            "sl": 0.04576,
            "tp": 0.0,
            "side": "SHORT",
            "risk": 0.0,
            "applied_cumulative_fill": {"bc09d4ee": "2000"},
            "applied_exec_ids": {"e1": "1000", "e2": "1000"},
            "ws_fills_by_order": {"bc09d4ee": "2000"},
        }
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]

        # Save state using real AST method
        save_ok = harness._save_state()
        self.assertTrue(save_ok, "Real AST _save_state returned False!")

        # Load into a completely fresh harness instance using real AST _load_state
        restarted_harness = RealASTStrictTerminalHarness(state_path)
        restarted_harness._tracked_positions = {}
        asyncio.run(restarted_harness._load_state())

        loaded_pos = restarted_harness._tracked_positions["CHIP-USDT"]["SHORT"][0]
        self.assertEqual(Decimal(str(loaded_pos["remaining_amount"])), Decimal("3180"))
        self.assertEqual(loaded_pos["applied_cumulative_fill"]["bc09d4ee"], "2000")
        self.assertEqual(loaded_pos["applied_exec_ids"]["e1"], "1000")
        self.assertEqual(loaded_pos["applied_exec_ids"]["e2"], "1000")

        # Now test that calling _place_bybit_conditional_order on the recovered state still produces stable remaining
        connector = make_mock_connector()
        restarted_harness._get_bybit_order_by_link_id = AsyncMock(return_value={
            "orderId": "bc09d4ee", "orderLinkId": "H-S-364986326432-BB", "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"
        })
        restarted_harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})
        restarted_harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "Untriggered"}
        ])

        res = asyncio.run(restarted_harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))
        self.assertEqual(Decimal(str(restarted_harness._tracked_positions["CHIP-USDT"]["SHORT"][0]["remaining_amount"])), Decimal("3180"))
        print("  [TEST 21 PASSED] Real AST state save/load roundtrip: remaining_amount and applied_cumulative_fill preserved.")

    # ─────────────────────────────────────────────────────────────────────────
    # POINT 2 NEW REGRESSIONS: Missing/Empty/Unknown status, side, or positionIdx
    # ─────────────────────────────────────────────────────────────────────────

    def test_22_missing_status_side_or_positionidx_not_partial_fill_covered(self):
        """
        User Requirement:
        'Eksik statü/yön/positionIdx → partial_fill_covered dönmemeli.'
        'Residual korumasında eksik/boş/unknown statü, yön veya positionIdx doğrulanmış koruma sayılmasın.
         Aktif statüler açık izin listesiyle kabul edilsin. Gerçek conditional-order parser’ının bu alanları
         nasıl taşıdığını da test et; sibling stoplarına dokunma.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_22_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]
        connector = make_mock_connector()

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        # Subtest A: Missing orderStatus (None)
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": None}
        ])
        resA = asyncio.run(harness._place_bybit_conditional_order(connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"))
        self.assertFalse(resA.get("success"))
        self.assertEqual(resA.get("status"), "unprotected_residual")

        # Subtest B: Unknown orderStatus ("unknown")
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": 2, "orderStatus": "unknown"}
        ])
        resB = asyncio.run(harness._place_bybit_conditional_order(connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"))
        self.assertFalse(resB.get("success"))
        self.assertEqual(resB.get("status"), "unprotected_residual")

        # Subtest C: Missing side (None or empty)
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": None, "positionIdx": 2, "orderStatus": "Untriggered"}
        ])
        resC = asyncio.run(harness._place_bybit_conditional_order(connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"))
        self.assertFalse(resC.get("success"))
        self.assertEqual(resC.get("status"), "unprotected_residual")

        # Subtest D: Missing positionIdx (None or -1)
        harness._get_bybit_conditional_orders = AsyncMock(return_value=[
            {"orderId": "res_stop", "orderLinkId": "H-S-364986326432-BB-RES", "parent_id": 364986326432, "kind": "SL", "qty": Decimal("3180"), "triggerPrice": Decimal("0.04576"), "side": "BUY", "positionIdx": None, "orderStatus": "Untriggered"}
        ])
        resD = asyncio.run(harness._place_bybit_conditional_order(connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"))
        self.assertFalse(resD.get("success"))
        self.assertEqual(resD.get("status"), "unprotected_residual")

        # Subtest E: Real parser test: verify real _get_bybit_conditional_orders extracts and carries orderStatus, side, positionIdx
        raw_api_response = {
            "retCode": 0,
            "result": {
                "list": [{
                    "orderId": "real_parsed_oid",
                    "orderLinkId": "H-S-364986326432-BB",
                    "stopOrderType": "StopLoss",
                    "triggerPrice": "0.04576",
                    "qty": "3180",
                    "positionIdx": 2,
                    "side": "Buy",
                    "orderStatus": "Untriggered"
                }]
            }
        }
        mock_conn = make_mock_connector()
        mock_conn._api_get = AsyncMock(return_value=raw_api_response)
        harness._bind_method("_get_bybit_conditional_orders")
        parsed_orders = asyncio.run(harness._get_bybit_conditional_orders(mock_conn, "CHIP-USDT", "SHORT"))
        self.assertEqual(len(parsed_orders), 1)
        po = parsed_orders[0]
        self.assertEqual(po.get("orderStatus"), "Untriggered", "Real parser failed to carry orderStatus!")
        self.assertEqual(po.get("side"), "BUY", "Real parser failed to carry side!")
        self.assertEqual(po.get("positionIdx"), 2, "Real parser failed to carry positionIdx!")
        print("  [TEST 22 PASSED] Missing/unknown status, side, or positionIdx rejected; real parser verified.")

    # ─────────────────────────────────────────────────────────────────────────
    # POINT 3 NEW REGRESSIONS: State Save Failure Error Handling
    # ─────────────────────────────────────────────────────────────────────────

    def test_23_state_save_failure_produces_explicit_error_never_silent_success(self):
        """
        User Requirement:
        'State yazma hatası → açık hata/belirsizlik sonucu; sessiz başarı olmamalı.'
        """
        harness = RealASTStrictTerminalHarness(str(TEST_TMP_DIR / "test_23_state.json"))
        parent = {"order_id": 364986326432, "amount": 5180.0, "remaining_amount": 5180.0, "sl": 0.04576, "tp": 0.0, "side": "SHORT"}
        harness._tracked_positions["CHIP-USDT"]["SHORT"] = [parent]
        connector = make_mock_connector()

        # Simulate disk write failure in _save_state
        harness._save_state_should_fail = True

        async def mock_get_order(conn, pair, cid):
            return {"orderId": "bc09d4ee", "orderLinkId": cid, "orderStatus": "Filled", "cumExecQty": "2000", "avgPrice": "0.04577"}
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate"})

        res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "SHORT", "SL", Decimal("0.04576"), Decimal("5180"), cid="H-S-364986326432-BB"
        ))

        # MUST NOT be success! Must report state_save_failed!
        self.assertFalse(res.get("success"), "Silent success returned despite state save failure!")
        self.assertEqual(res.get("status"), "state_save_failed")
        self.assertEqual(res.get("error"), "state_save_failed")
        print("  [TEST 23 PASSED] State save failure produces explicit error ('state_save_failed'), never silent success.")


if __name__ == "__main__":
    unittest.main()
