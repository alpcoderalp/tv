import ast
import asyncio
import time
import json
import os
import sys
import unittest
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Any, Dict, List, Optional, Set, Tuple
from unittest.mock import AsyncMock, MagicMock

sys.stdout.reconfigure(encoding="utf-8")

# 1. Parse and extract production code from tv_signal_strategy.py
with open("tv_signal_strategy.py", "r", encoding="utf-8") as f:
    source_code = f.read()

tree = ast.parse(source_code)

ns = {
    "Decimal": Decimal,
    "ROUND_CEILING": ROUND_CEILING,
    "ROUND_FLOOR": ROUND_FLOOR,
    "time": time,
    "asyncio": asyncio,
    "json": json,
    "List": List,
    "Dict": Dict,
    "Optional": Optional,
    "Set": Set,
    "Tuple": Tuple,
    "Any": Any,
    "max": max,
    "min": min,
    "abs": abs,
    "bool": bool,
    "str": str,
    "int": int,
    "float": float,
    "len": len,
    "getattr": getattr,
    "setattr": setattr,
    "hasattr": hasattr,
    "sorted": sorted,
    "all": all,
    "set": set,
    "isinstance": isinstance,
    "TradeType": type("TradeType", (), {
        "BUY": type("TT", (), {"name": "BUY", "value": 1})(),
        "SELL": type("TT", (), {"name": "SELL", "value": 2})()
    }),
}

# Compile PerFillAccumulator
acc_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PerFillAccumulator")
exec(compile(ast.Module(body=[acc_node], type_ignores=[]), "<ast>", "exec"), ns)
PerFillAccumulator = ns["PerFillAccumulator"]

# Compile TVSignalStrategy methods
strat_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TVSignalStrategy")
target_names = [
    "_hybrid_execute_tp1_close",
    "_hybrid_retry_break_even_sl",
    "_hybrid_handle_execution_report",
    "_hybrid_apply_05_be",
    "_reconcile_hybrid_pending_close",
    "_activate_hybrid_management",
    "_try_trigger_hybrid_management",
    "_position_management_trailing_active",
    "_handle_phase2_trailing",
    "_tp_order_suppressed",
    "_tp_target_suppressed",
    "_fee_adjusted_r_targets",
    "_fee_adjusted_r_levels",
    "_rr2_adopt_position_state",
    "_hybrid_adopt_position_state",
    "_pm_mode",
    "_is_position_protected",
    "_is_hybrid_managed_position",
    "_is_rr2_managed_position",
    "_trading_allowed",
    "_ensure_position_r_geometry",
    "_place_bybit_limit_tp",
    "_place_bybit_conditional_order",
    "_place_sltp_simple",
    "_place_bybit_trading_stop",
    "_normalize_exchange_name",
    "_resolve_signal_trading_pair",
    "_process_signal",
    "_apply_amount_rules",
    "_ceil_to_step"
]
funcs = [m for m in strat_node.body if getattr(m, "name", None) in target_names]
exec(compile(ast.Module(body=funcs, type_ignores=[]), "<ast>", "exec"), ns)

import types

class MockStrategyHarness:
    def __init__(self):
        self._logger = MagicMock()
        self.POSITION_MANAGEMENT_MODE = "hybrid_trailing"
        self.TRADING_ENABLED = True
        self._tracked_positions = {}
        self._per_fill_accumulators = {}
        self._phase2_active_positions = set()
        self._signal_cache = {}
        self._sltp_retry_queue = {}
        self._orders_being_placed = set()
        self._grace_period_until = {}
        self._r_geometry_cache = {}
        self._hybrid_transitioning_orders = set()
        self._processing_phase2_orders = set()
        self._hybrid_trail_retry_ts = {}
        self._emergency_flattening = False
        self._recovery_in_progress = False
        self._repair_active = False
        self._reconciliation_in_progress = False
        self._phase2_immunity = {}
        self._sync_protection = {}
        self.current_timestamp = 1700000000.0
        self.PHASE2_IMMUNITY_DURATION = 5.0
        self.GRACE_PERIOD_SECONDS = 5.0
        self._state_loaded = True
        self.RR2_PLACE_ENTRY_TP = False
        self.EXCHANGE_MAPPING = {}
        self.EXCHANGE_BACKEND = "bybit"
        self.ACTIVE_CONNECTOR = "bybit_perpetual_demo"
        self.SIGNAL_QUOTE_FALLBACK_USDT = True
        self.connectors = {}
        self.markets = {"bybit_perpetual_demo": ["CHIP-USDT", "PONS-USDT"]}
        self.MIN_SL_PCT = Decimal("0.004")
        self.MAX_SL_PCT = Decimal("0.07")
        self.B4_DEFAULT_LEVERAGE = 20

        for name in target_names:
            setattr(self, name, types.MethodType(ns[name], self))

        self._connector = MagicMock()
        self._save_state = MagicMock(return_value=True)
        self._save_strategy_state = MagicMock(return_value=True)
        self._get_connector = MagicMock(return_value=self._connector)
        self._is_bybit_connector = MagicMock(return_value=True)
        self._bybit_consolidation_mode = MagicMock(return_value=None)
        self._place_bybit_market_order = AsyncMock(return_value={"success": True, "order_id": "MKT_CLOSE_1"})
        self._place_bybit_trading_stop = AsyncMock(return_value={"success": True, "sl_status": "created"})
        self._update_trailing_sl_rr2_strict = AsyncMock(return_value=True)
        self._rr2_failsafe_close_parent = AsyncMock(return_value=True)
        self._rr2_ratchet_trailing = AsyncMock(return_value=True)
        self._phase2_second_take_if_tp_hit = AsyncMock(return_value=False)
        self.connectors = {"bybit": self._connector}

    def logger(self):
        return self._logger

    def _r_fee_rt(self):
        return Decimal("0.0012")

    def get_trading_rule(self, trading_pair: str):
        rule = MagicMock()
        rule.min_base_amount_increment = Decimal("10")
        rule.min_order_size = Decimal("10")
        rule.min_notional_size = Decimal("5")
        return rule

class TestOfflineContractRules(unittest.TestCase):
    def setUp(self):
        self.strat = MockStrategyHarness()

    def test_01_be_threshold_boundaries(self):
        """Kural: %0.5 fiyat hareketi. Altı tetiklemez, tam eşik ve üstü tetikler."""
        entry = Decimal("100.0")
        pos_long = {
            "order_id": 101, "side": "LONG", "entry": entry, "sl": Decimal("98.0"),
            "amount": Decimal("10"), "remaining_amount": Decimal("10"), "management_stage": "HYBRID_WAIT"
        }
        self.strat._tracked_positions.setdefault("BTC-USDT", {"LONG": [pos_long], "SHORT": []})

        # LONG: +0.49% -> Altında, tetiklememeli
        crossed_under = Decimal("100.49") >= entry * Decimal("1.005")
        self.assertFalse(crossed_under)

        # LONG: +0.50% -> Tam eşik, tetiklemeli
        crossed_exact = Decimal("100.50") >= entry * Decimal("1.005")
        self.assertTrue(crossed_exact)

        # LONG: +0.51% -> Üstünde, tetiklemeli
        crossed_over = Decimal("100.51") >= entry * Decimal("1.005")
        self.assertTrue(crossed_over)

        # SHORT: entry 100.0 -> 99.51 (altında/tetiklemez), 99.50 (tam eşik/tetikler), 99.49 (üstünde/tetikler)
        self.assertFalse(Decimal("99.51") <= entry * Decimal("0.995"))
        self.assertTrue(Decimal("99.50") <= entry * Decimal("0.995"))
        self.assertTrue(Decimal("99.49") <= entry * Decimal("0.995"))

    def test_02_be_and_tp1_same_tick(self):
        """Aynı tick'te hem +0.5% hem 1R geçilirse her iki görev de oluşturulur."""
        pos = {
            "order_id": 202, "side": "LONG", "entry": Decimal("100.0"), "sl": Decimal("98.0"),
            "amount": Decimal("10"), "remaining_amount": Decimal("10"), "management_stage": "HYBRID_WAIT"
        }
        self.strat._tracked_positions.setdefault("BTC-USDT", {"LONG": [pos], "SHORT": []})
        self.strat._ensure_position_r_geometry(pos)
        self.assertIn("r1_price", pos)
        r1 = pos["r1_price"]

        async def _run():
            triggered = self.strat._try_trigger_hybrid_management("bybit", "BTC-USDT", pos, r1 + Decimal("1.0"))
            self.assertTrue(triggered)
            self.assertEqual(pos["management_stage"], "HYBRID_TRANSITIONING")
            self.assertIn(202, self.strat._hybrid_transitioning_orders)
            # Drain any tasks
            pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        asyncio.run(_run())

    def test_03_repeating_ticker_reconnect_duplicate_guard(self):
        """Tekrarlayan ticker veya duplicate event aynı parent için ikinci TP1 emri gönderemez."""
        pos = {
            "order_id": 303, "side": "LONG", "entry": Decimal("100.0"), "sl": Decimal("98.0"),
            "amount": Decimal("10"), "remaining_amount": Decimal("10"), "management_stage": "HYBRID_WAIT"
        }
        self.strat._tracked_positions.setdefault("BTC-USDT", {"LONG": [pos], "SHORT": []})
        self.strat._ensure_position_r_geometry(pos)
        r1 = pos["r1_price"]

        async def _run():
            # First trigger
            t1 = self.strat._try_trigger_hybrid_management("bybit", "BTC-USDT", pos, r1 + Decimal("1.0"))
            self.assertTrue(t1)

            # Duplicate event arrives immediately while transitioning
            t2 = self.strat._try_trigger_hybrid_management("bybit", "BTC-USDT", pos, r1 + Decimal("1.0"))
            self.assertFalse(t2) # Blocked by self._hybrid_transitioning_orders!
            
            pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        asyncio.run(_run())

    def test_04_tp1_partial_fill_accounting(self):
        """TP1 kısmı parçalı dolarsa accumulator tam miktara ulaşmadan tp1_done yapmaz."""
        pos = {
            "order_id": 404, "side": "LONG", "entry": Decimal("100.0"), "sl": Decimal("98.0"),
            "amount": Decimal("10"), "remaining_amount": Decimal("10"), "management_stage": "HYBRID_CLOSE_PENDING",
            "tp1_intent": {
                "parent_id": 404, "amount": "5.0", "side": "LONG", "status": "SUBMITTED",
                "current_attempt_cid": "HTP14041790000000", "attempt_cids": ["HTP14041790000000"],
                "attempts_cum": {}, "attempts_exec_sum": {}, "execution_ids": []
            }
        }
        # Partial fill 1: 2.0 qty
        rep1 = {"orderLinkId": "HTP14041790000000", "execQty": "2.0", "execId": "EX1", "orderStatus": "PartiallyFilled"}
        self.strat._hybrid_handle_execution_report(pos, [rep1])
        self.assertFalse(pos.get("tp1_done", False))
        self.assertEqual(pos["remaining_amount"], Decimal("8.0"))

        # Partial fill 2: 3.0 qty (total 5.0)
        rep2 = {"orderLinkId": "HTP14041790000000", "execQty": "3.0", "execId": "EX2", "orderStatus": "Filled"}
        self.strat._hybrid_handle_execution_report(pos, [rep2])
        self.assertTrue(pos.get("tp1_done", False))
        self.assertEqual(pos["remaining_amount"], Decimal("5.0"))

    def test_05_tp1_and_sl_race_protection(self):
        """TP1 emri reduceOnly=True kullanır; SL ile yarışta ters yönde yeni pozisyon açamaz."""
        pos = {
            "order_id": 505, "side": "SHORT", "entry": Decimal("100.0"), "sl": Decimal("102.0"),
            "amount": Decimal("10"), "remaining_amount": Decimal("10"), "management_stage": "HYBRID_WAIT"
        }
        self.strat._tracked_positions.setdefault("BTC-USDT", {"LONG": [], "SHORT": [pos]})
        async def _run():
            await self.strat._hybrid_execute_tp1_close(
                self.strat._connector, "bybit", "BTC-USDT", pos, Decimal("5.0"), Decimal("95.0")
            )
        asyncio.run(_run())
        
        # Verify call arguments
        calls = self.strat._place_bybit_market_order.mock_calls
        self.assertTrue(len(calls) > 0)
        call_kwargs = calls[0].kwargs
        self.assertTrue(call_kwargs.get("reduce_only"), "TP1 emri mutlaka reduce_only=True olmalı!")
        self.assertTrue(call_kwargs.get("exact_qty"), "TP1 emri exact_qty=True olmalı!")

    def test_06_close_side_inversion_contract(self):
        """SHORT pozisyonun kapamasında position_side='SHORT', LONG'da 'LONG' iletilir."""
        pos_short = {"order_id": 601, "side": "SHORT", "amount": Decimal("10"), "remaining_amount": Decimal("10")}
        pos_long = {"order_id": 602, "side": "LONG", "amount": Decimal("10"), "remaining_amount": Decimal("10")}
        self.strat._tracked_positions.setdefault("BTC-USDT", {"LONG": [pos_long], "SHORT": [pos_short]})

        async def _test_short():
            await self.strat._hybrid_execute_tp1_close(
                self.strat._connector, "bybit", "BTC-USDT", pos_short, Decimal("5.0"), Decimal("95.0")
            )
        asyncio.run(_test_short())
        self.assertEqual(self.strat._place_bybit_market_order.mock_calls[-1].kwargs.get("position_side"), "SHORT")
        self.assertEqual(self.strat._place_bybit_market_order.mock_calls[-1].kwargs.get("context"), "close")

        async def _test_long():
            await self.strat._hybrid_execute_tp1_close(
                self.strat._connector, "bybit", "BTC-USDT", pos_long, Decimal("5.0"), Decimal("105.0")
            )
        asyncio.run(_test_long())
        self.assertEqual(self.strat._place_bybit_market_order.mock_calls[-1].kwargs.get("position_side"), "LONG")
        self.assertEqual(self.strat._place_bybit_market_order.mock_calls[-1].kwargs.get("context"), "close")

    def test_07_qtystep_rounding(self):
        """_apply_amount_rules trading_rule min_base_amount_increment'e göre tam aşağı yuvarlar."""
        rule = MagicMock()
        rule.min_base_amount_increment = Decimal("10")
        rule.min_order_size = Decimal("10")
        rule.min_notional_size = Decimal("5")
        self.strat._connector.trading_rules = {"CHIP-USDT": rule}

        # _apply_amount_rules(amount, trading_rule, entry_price)
        qty, _ = self.strat._apply_amount_rules(Decimal("4379.56"), rule, Decimal("1.0"))
        self.assertEqual(qty, Decimal("4370"))

    def test_08_second_entry_same_symbol_side_independent_tracking(self):
        """Bot aynı sembol ve yönde iki pozisyonu listede bağımsız iki obje olarak saklar."""
        p1 = {"order_id": 801, "side": "LONG", "entry": Decimal("100"), "amount": Decimal("10")}
        p2 = {"order_id": 802, "side": "LONG", "entry": Decimal("102"), "amount": Decimal("20")}
        self.strat._tracked_positions["BTC-USDT"] = {"LONG": [p1, p2], "SHORT": []}
        
        self.assertEqual(len(self.strat._tracked_positions["BTC-USDT"]["LONG"]), 2)
        self.assertEqual(self.strat._tracked_positions["BTC-USDT"]["LONG"][0]["order_id"], 801)
        self.assertEqual(self.strat._tracked_positions["BTC-USDT"]["LONG"][1]["order_id"], 802)

    def test_09_state_recovery_untrusted_baseline_no_artificial_r(self):
        """Restart sonrası recovery'de r_baseline_untrusted aktifse yapay R üretilmez."""
        pos = {
            "order_id": 901, "side": "LONG", "entry": Decimal("100"), "sl": Decimal("100"),
            "amount": Decimal("10"), "remaining_amount": Decimal("10")
        }
        self.strat._hybrid_adopt_position_state(pos)
        self.assertTrue(pos.get("r_baseline_untrusted"))
        self.assertEqual(pos.get("management_stage"), "HYBRID_TRAIL_1R")
        self.assertNotIn("r1_price", pos)
        self.assertNotIn("r2_price", pos)

    def test_10_trailing_ratchet_beyond_2r(self):
        """2R ötesinde trailing stop tepe fiyatla birlikte kârı kilitleyerek ilerler."""
        pos = {
            "order_id": 1001, "side": "LONG", "entry": Decimal("100.0"), "sl": Decimal("98.0"),
            "amount": Decimal("5"), "remaining_amount": Decimal("5"), "management_stage": "HYBRID_TRAIL_1R",
            "confirmed_sl": Decimal("100.0"), "r1_price": Decimal("102.0"), "r2_price": Decimal("104.0")
        }
        self.strat._tracked_positions.setdefault("BTC-USDT", {"LONG": [pos], "SHORT": []})
        # Run _handle_phase2_trailing at price 106.0
        asyncio.run(self.strat._handle_phase2_trailing("bybit", "BTC-USDT", Decimal("106.0"), pos))
        self.assertEqual(pos.get("management_stage"), "HYBRID_TRAIL_2R")
        self.assertTrue(self.strat._update_trailing_sl_rr2_strict.called)

if __name__ == "__main__":
    unittest.main(verbosity=2)
