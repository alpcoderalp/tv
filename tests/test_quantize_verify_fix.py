"""
Comprehensive Test Suite: Real Candidate AST Method Execution
(candidate_hybrid_v2_51F6CDD4_candidate.py)

Kapsam (12/12 Test):
1. test_01_candidate_sha256_hash_verified: Aday dosyanın SHA256 hash'i dinamik doğrulanır ve yazdırılır (D227F3A7...).
2. test_02_long_counter_example_better_existing_stop_not_lowered: LONG mevcut stop=0.2713, qty=336; ham hedef 0.2689740 (op: 0.2689) -> daha iyi stopu düşüren amend gönderilmez.
3. test_03_short_symmetry_better_stop_not_loosened: SHORT mevcut stop=0.2713, ham hedef 0.2740 (daha gevşek) -> amend gönderilmez.
4. test_04_short_symmetry_normal_progression_advances: SHORT normal kâr ilerlemesinde stop 0.2750 -> 0.2700 taşınır.
5. test_05_better_price_wrong_quantity_separated_and_unverified_readback_blocks_state:
   - Daha iyi fiyat (0.2713) korunarak sadece miktar (336) amend edilir.
   - Borsa readback'i doğrulanmadan state başarıya ilerlemez, last_logged_sl korunur.
   - Miktar amend hatasında cancel/replace yapılmaz.
6. test_06_rr2_ratchet_trailing_real_body_long_3r_floor_strictly_enforced:
   - Gerçek _rr2_ratchet_trailing gövdesi çalıştırılır (doğrulayıcıya doğrudan değer verilmez).
   - 3R Peak=0.2798, entry=0.26375, R=0.00535 -> Ham floor 0.27445.
   - 0.2744 Bybit emri varken state yazılmaz, last_logged_sl korunur, 3s throttle kurulur.
   - 0.2745 Bybit emri varken floor sağlanır ve state ilerletilir.
7. test_07_rr2_ratchet_trailing_real_body_short_3r_floor_strictly_enforced:
   - SHORT simetrisinde gerçek _rr2_ratchet_trailing gövdesi çalıştırılır.
   - Gevşek stop reddedilir, floor'u sağlayan stop kabul edilir.
8. test_08_quantize_exception_preserves_stop_and_sets_retry:
   - quantize_order_price istisna fırlatırsa ham hedefle devam edilmez, stop/state korunur, 3s retry kurulur.
9. test_09_quantize_returns_none_preserves_stop_and_sets_retry:
   - quantize None dönerse stop/state korunur, retry kurulur.
10. test_10_quantize_returns_nan_preserves_stop_and_sets_retry:
   - quantize NaN dönerse stop/state korunur, retry kurulur.
11. test_11_stale_quantity_readback_rejected_and_state_not_advanced:
   - Borsada fiyat doğru (0.2689) ancak miktar eski (672 vs 336) kaldığında doğrulayıcı None döner, state ilerletilmez.
12. test_12_retry_throttle_prevents_premature_dispatch:
   - 3 saniyelik retry throttle penceresi içinde ikinci bir çağrı hiçbir emir göndermez.
"""

import ast
import asyncio
import hashlib
import os
import pathlib
import time
import types
import unittest
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from unittest.mock import AsyncMock, MagicMock

# ─────────────────────────────────────────────────────────────────────────────
# CANDIDATE AST METOT ÇIKARMA VE DERLEME
# ─────────────────────────────────────────────────────────────────────────────

candidate_candidates = [
    os.environ.get("CANDIDATE_PATH", ""),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tv_signal_strategy.py"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_signal_strategy.py"),
    "candidate_hybrid_v2_D227F3A7_strict_terminal_fix.py",
]
CANDIDATE_PATH = next((p for p in candidate_candidates if p and os.path.exists(p)), "tv_signal_strategy.py")

with open(CANDIDATE_PATH, "rb") as f:
    CANDIDATE_BYTES = f.read()

CANDIDATE_SHA256 = hashlib.sha256(CANDIDATE_BYTES).hexdigest().upper()
_candidate_source = CANDIDATE_BYTES.decode("utf-8")

_tree = ast.parse(_candidate_source)
_strat_node = next(
    n for n in _tree.body if isinstance(n, ast.ClassDef) and n.name == "TVSignalStrategy"
)

TARGET_METHODS = [
    "_handle_phase2_trailing",
    "_update_trailing_sl_rr2_strict",
    "_update_trailing_sl",
    "_place_bybit_conditional_order",
    "_place_bybit_trading_stop",
    "_hybrid_verify_bybit_sl_order",
    "_rr2_ratchet_trailing",
    "_hybrid_retry_break_even_sl",
]

_funcs = [m for m in _strat_node.body if getattr(m, "name", None) in TARGET_METHODS]
_candidate_ns = {
    "Decimal": Decimal,
    "time": time,
    "asyncio": asyncio,
    "getattr": getattr,
    "hasattr": hasattr,
    "setattr": setattr,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "min": min,
    "max": max,
    "abs": abs,
    "isinstance": isinstance,
    "dict": dict,
    "list": list,
    "Optional": Optional,
    "Dict": Dict,
    "List": List,
    "Set": Set,
    "Tuple": Tuple,
    "Any": Any,
}

_compiled = compile(ast.Module(body=_funcs, type_ignores=[]), "<candidate_ast>", "exec")
exec(_compiled, _candidate_ns)


# ─────────────────────────────────────────────────────────────────────────────
# GERÇEK GÖVDE TEST HARNESS
# ─────────────────────────────────────────────────────────────────────────────

class RealCandidateHarness:
    """
    Candidate dosyasından çıkarılan GERÇEK metotları bağlayan test ortamı.
    Model veya kopya değil; candidate AST'sindeki birebir fonksiyonlar çalışır.
    """

    def __init__(self, tick_size: Decimal = Decimal("0.0001")):
        self.tick_size = tick_size
        self._logger = MagicMock()
        self._processing_phase2_orders = set()
        self._hybrid_trail_retry_ts = {}
        self._rr2_ratchet_retry_ts = {}
        self.POSITION_MANAGEMENT_MODE = "hybrid_trailing"
        self._bybit_last_sltp_status = {}
        self._RR2_SOFT_FAIL_STATUSES = ("breached", "immediate", "cooldown")
        self._sltp_orders = {}
        self._last_sltp_placement = {}
        self._sltp_ws_confirmed = {}
        self._trailing_sl_pending = {}
        self._bybit_cond_immediate_until = {}
        self.BYBIT_VERIFY_SL_CLAMP = False
        self._tracked_positions = {}
        self.amend_calls = []
        self.raw_post_calls = []

        # Connector stub
        self.connector = MagicMock()
        self.connector.quantize_order_price = self._quantize_order_price
        self.connector.quantize_order_amount = lambda pair, amt: Decimal(str(amt))
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="PONSUSDT")
        self.connector.trading_rules = {}

        self.connectors = {"bybit_perpetual_demo": self.connector}

        # Mock order responses
        self._mock_live_order = None
        self._mock_conditional_orders = []

        # Gerçek candidate metotlarını instance'a bağla
        for name in TARGET_METHODS:
            setattr(self, name, types.MethodType(_candidate_ns[name], self))

    def _quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        p = Decimal(str(price))
        return (p // self.tick_size) * self.tick_size

    def logger(self):
        return self._logger

    def _pm_mode(self):
        return "hybrid_trailing"

    def _is_bybit_connector(self, connector):
        return True

    def _get_connector(self, exchange):
        return self.connector

    async def _phase2_second_take_if_tp_hit(self, **kwargs):
        return False

    def _should_skip_sltp_due_to_backoff(self, *args, **kwargs):
        return False

    def _bybit_consolidation_mode(self, *args, **kwargs):
        return None

    def _bybit_sltp_link_id(self, position_order_id, kind):
        return f"H-S-{position_order_id}-BB"

    def _bybit_position_idx(self, connector, ps, is_open=True):
        return 1

    def _bybit_fresh_price(self, *args, **kwargs):
        return getattr(self, "_mock_current_price", Decimal("0.2720"))

    def _bybit_ret_ok(self, resp):
        return (resp or {}).get("retCode") == 0

    async def _bybit_raw_post(self, connector, path, body):
        self.raw_post_calls.append({"path": path, "body": body})
        return {"retCode": 110072, "retMsg": "OrderLinkedID is duplicate"}

    async def _get_bybit_order_by_link_id(self, connector, trading_pair, cid):
        return self._mock_live_order

    async def _amend_bybit_conditional_order(
        self, connector, trading_pair, trigger_price, order_link_id=None, qty=None
    ):
        call_info = {
            "trigger_price": trigger_price,
            "order_link_id": order_link_id,
            "qty": qty,
        }
        self.amend_calls.append(call_info)
        return {"success": True}

    async def _get_bybit_conditional_orders(self, connector, trading_pair, side_u):
        return self._mock_conditional_orders

    async def _get_cached_position_amount(self, trading_pair, side, **kwargs):
        for sd in self._tracked_positions.get(trading_pair, {}).values():
            for p in sd:
                return p.get("remaining_amount", p.get("amount", Decimal("0")))
        return Decimal("336")

    def _save_state(self):
        pass

    def _maybe_schedule_trailing(self, *args, **kwargs):
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 12 ADET KAPSAMLI GERÇEK GÖVDE TESTİ
# ─────────────────────────────────────────────────────────────────────────────

class TestRealCandidateBody(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 80)
        print(f"  TESTED CANDIDATE FILE : {os.path.basename(CANDIDATE_PATH)}")
        print(f"  CANDIDATE FULL SHA256 : {CANDIDATE_SHA256}")
        print("=" * 80)

    def setUp(self):
        self.harness = RealCandidateHarness(tick_size=Decimal("0.0001"))

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 1: ADAY DOSYANIN SHA256 HASH DOĞRULAMASI
    # ─────────────────────────────────────────────────────────────────────────
    def test_01_candidate_sha256_hash_verified(self):
        """Aday dosyanın SHA256 hash'inin tam olarak FBB70BAF... ile eşleştiği doğrulanır."""
        expected_hash = "4F95AA04183052F4333B32960067E3591C0F48B0A6DBEB512AC442A93687AF41"
        self.assertEqual(
            CANDIDATE_SHA256,
            expected_hash,
            f"Aday dosya SHA256 eşleşmedi! Beklenen={expected_hash}, Bulunan={CANDIDATE_SHA256}",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 2: LONG KARŞI ÖRNEK (DAHA İYİ STOPU DÜŞÜRMEME)
    # ─────────────────────────────────────────────────────────────────────────
    def test_02_long_counter_example_better_existing_stop_not_lowered(self):
        """
        KULLANICI TALEBİ:
        LONG mevcut stop = 0.2713, qty = 336; ham hedef 0.2689740, tick 0.0001
        Gerçek candidate _handle_phase2_trailing gövdesiyle çalıştırılır.
        Daha iyi stopu (0.2713) düşüren hiçbir amend gönderilmemelidir.
        """
        pos_order_id = 53829041518
        pos_data = {
            "order_id": pos_order_id,
            "side": "LONG",
            "entry": Decimal("0.2637"),
            "sl": Decimal("0.2713"),          # MEVCUT STOP 0.2713
            "confirmed_sl": Decimal("0.2713"),# MEVCUT STOP 0.2713
            "last_logged_sl": Decimal("0.2713"),
            "amount": Decimal("336"),
            "remaining_amount": Decimal("336"),
            "management_stage": "HYBRID_TRAIL_2R",
            "peak_price": Decimal("0.2743"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"LONG": [pos_data]}}
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2713",
            "qty": "336",
            "orderId": "mock-sl-order-1",
        }
        self.harness._mock_conditional_orders = [{
            "parent_id": pos_order_id,
            "kind": "SL",
            "triggerPrice": "0.2713",
            "qty": "336",
        }]

        # Gerçek _handle_phase2_trailing gövdesini çalıştır:
        asyncio.run(
            self.harness._handle_phase2_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                current_price=Decimal("0.2743"),
                pos_data=pos_data,
            )
        )

        # KANIT: Stopu 0.2713'ten 0.2689'a düşüren hiçbir amend gönderilmemiştir!
        for call in self.harness.amend_calls:
            self.assertNotEqual(
                call["trigger_price"],
                Decimal("0.2689"),
                "HATA: Gerçek gövde daha iyi stopu (0.2713) düşüren amend (0.2689) gönderdi!",
            )
        self.assertEqual(pos_data["sl"], Decimal("0.2713"))
        self.assertEqual(pos_data["confirmed_sl"], Decimal("0.2713"))

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 3: SHORT SİMETRİSİ (DAHA İYİ STOPU GEVŞETMEME)
    # ─────────────────────────────────────────────────────────────────────────
    def test_03_short_symmetry_better_stop_not_loosened(self):
        """
        SHORT'ta mevcut stop=0.2713 daha iyiyken, hesaplanan hedef 0.2740 (daha gevşek) ise
        stopu yükselten/gevşeten amend gönderilmez.
        """
        pos_order_id = 942973113463
        pos_data = {
            "order_id": pos_order_id,
            "side": "SHORT",
            "entry": Decimal("0.2714"),
            "sl": Decimal("0.2713"),
            "confirmed_sl": Decimal("0.2713"),
            "last_logged_sl": Decimal("0.2713"),
            "amount": Decimal("232"),
            "remaining_amount": Decimal("232"),
            "management_stage": "HYBRID_TRAIL_2R",
            "peak_price": Decimal("0.2714"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"SHORT": [pos_data]}}
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2713",
            "qty": "232",
            "orderId": "mock-short-sl",
        }

        asyncio.run(
            self.harness._handle_phase2_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                current_price=Decimal("0.2714"),
                pos_data=pos_data,
            )
        )

        for call in self.harness.amend_calls:
            if call["trigger_price"] is not None:
                self.assertLessEqual(
                    call["trigger_price"],
                    Decimal("0.2713"),
                    "HATA: SHORT stop gevşetildi!",
                )

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 4: SHORT NORMAL İLERLEME
    # ─────────────────────────────────────────────────────────────────────────
    def test_04_short_symmetry_normal_progression_advances(self):
        """SHORT'ta kâr ilerledikçe stop daha sıkı fiyata başarıyla taşınır."""
        pos_order_id = 942973113463
        pos_data = {
            "order_id": pos_order_id,
            "side": "SHORT",
            "entry": Decimal("0.2750"),
            "sl": Decimal("0.2750"),
            "confirmed_sl": Decimal("0.2750"),
            "last_logged_sl": Decimal("0.2750"),
            "amount": Decimal("232"),
            "remaining_amount": Decimal("232"),
            "management_stage": "HYBRID_TRAIL_2R",
            "peak_price": Decimal("0.2750"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"SHORT": [pos_data]}}
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2750",
            "qty": "232",
            "orderId": "mock-short-sl",
        }
        self.harness._mock_conditional_orders = [{
            "parent_id": pos_order_id,
            "kind": "SL",
            "triggerPrice": "0.2700",
            "qty": "232",
        }]

        self.harness._mock_current_price = Decimal("0.2650")
        asyncio.run(
            self.harness._handle_phase2_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                current_price=Decimal("0.2650"),
                pos_data=pos_data,
            )
        )

        self.assertEqual(pos_data["confirmed_sl"], Decimal("0.2700"))

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 5: DAHA İYİ FİYAT, YANLIŞ MİKTAR VE BORSA READBACK DOĞRULAMA KİLİDİ
    # ─────────────────────────────────────────────────────────────────────────
    def test_05_better_price_wrong_quantity_separated_and_unverified_readback_blocks_state(self):
        """
        KULLANICI TALEBİ:
        1) Daha iyi mevcut fiyat (0.2713) ve yanlış miktar (672 vs 336) ayrılır.
           Stop fiyatını (0.2713) gevşetmeden sadece miktar (336) düzeltilir (amended_qty_only).
        2) Bu miktar düzeltmesi borsa readback'iyle doğrulanmadan state'in başarıya ilerlemediği
           gerçek aday gövdesiyle kanıtlanır.
        3) Miktar düzeltmesi başarısız olursa genel cancel/replace yapılmaz ve işlem başarısız döner.
        """
        # Adım 1: Borsa live emri 0.2713 ve 672 (yanlış miktar)
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2713",
            "qty": "672",
            "orderId": "order-wrong-qty",
        }

        res = asyncio.run(
            self.harness._place_bybit_conditional_order(
                connector=self.harness.connector,
                trading_pair="PONS-USDT",
                position_side="LONG",
                kind="SL",
                trigger_price=Decimal("0.2689"),  # İstenen hedef daha gevşek
                qty=Decimal("336"),              # İstenen doğru miktar
                cid="H-S-53829041518-BB",
            )
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "amended_qty_only")
        self.assertEqual(len(self.harness.amend_calls), 1)
        # Amend'e giden fiyat daha iyi olan 0.2713 olmalı, gevşek 0.2689 OLMAMALIDIR!
        self.assertEqual(self.harness.amend_calls[0]["trigger_price"], Decimal("0.2713"))
        self.assertEqual(self.harness.amend_calls[0]["qty"], Decimal("336"))

        # Adım 2: Readback doğrulanmadan state başarıya ilerlemez:
        # Borsa readback'inde hala eski miktar 672 varsa doğrulayıcı None döner:
        self.harness._mock_conditional_orders = [{
            "parent_id": 53829041518,
            "kind": "SL",
            "triggerPrice": "0.2713",
            "qty": "672",
        }]

        verified_sl = asyncio.run(
            self.harness._hybrid_verify_bybit_sl_order(
                connector=self.harness.connector,
                trading_pair="PONS-USDT",
                side="LONG",
                position_order_id=53829041518,
                target_sl=Decimal("0.2713"),
                expected_qty=Decimal("336"),
            )
        )
        self.assertIsNone(verified_sl, "HATA: Stale miktar doğrulandı!")

        # Borsa readback'i doğru miktarla (336) güncellendiğinde doğrulanır:
        self.harness._mock_conditional_orders = [{
            "parent_id": 53829041518,
            "kind": "SL",
            "triggerPrice": "0.2713",
            "qty": "336",
        }]
        verified_sl_ok = asyncio.run(
            self.harness._hybrid_verify_bybit_sl_order(
                connector=self.harness.connector,
                trading_pair="PONS-USDT",
                side="LONG",
                position_order_id=53829041518,
                target_sl=Decimal("0.2713"),
                expected_qty=Decimal("336"),
            )
        )
        self.assertEqual(verified_sl_ok, Decimal("0.2713"))

        # Adım 3: Güvenli miktar amend'i başarısız olursa cancel/replace yapılmaz:
        self.harness.amend_calls.clear()
        self.harness._amend_bybit_conditional_order = AsyncMock(
            return_value={"success": False, "error": "rate_limit"}
        )
        res_fail = asyncio.run(
            self.harness._place_bybit_conditional_order(
                connector=self.harness.connector,
                trading_pair="PONS-USDT",
                position_side="LONG",
                kind="SL",
                trigger_price=Decimal("0.2689"),
                qty=Decimal("336"),
                cid="H-S-53829041518-BB",
            )
        )
        self.assertFalse(res_fail["success"])
        self.assertEqual(res_fail["status"], "failed")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 6: GERÇEK _rr2_ratchet_trailing GÖVDESİ LONG 3R FLOOR SINAMASI
    # ─────────────────────────────────────────────────────────────────────────
    def test_06_rr2_ratchet_trailing_real_body_long_3r_floor_strictly_enforced(self):
        """
        KULLANICI TALEBİ:
        RR2 floor testinin gerçek _rr2_ratchet_trailing yolunu çalıştırdığını,
        yalnız ortak doğrulayıcıya doğrudan değer vermediğini göster.
        Giriş: 0.26375, ilk SL: 0.2584, 1R: 0.00535, 3R Peak: 0.2798 -> Ham Floor: 0.27445.
        Gerçek _rr2_ratchet_trailing gövdesi çalıştırılır.
        Bybit'te 0.2744 varken state yazılmaz, last_logged_sl korunur, 3s throttle kurulur.
        Bybit'te 0.2745 varken floor sağlanır ve kabul edilir.
        """
        pos_order_id = 777001
        entry = Decimal("0.26375")
        r_orig = Decimal("0.00535")
        initial_sl = Decimal("0.26375")
        pos_data = {
            "order_id": pos_order_id,
            "side": "LONG",
            "r_eff_entry": entry,
            "r_distance_orig": r_orig,
            "r1_price": Decimal("0.2691"),
            "trailing_anchor_price": Decimal("0.2691"),
            "sl": initial_sl,
            "confirmed_sl": initial_sl,
            "last_logged_sl": initial_sl,
            "amount": Decimal("500"),
            "remaining_amount": Decimal("500"),
            "peak_price": Decimal("0.2798"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"LONG": [pos_data]}}
        self.harness._mock_current_price = Decimal("0.2798")

        # Senaryo A: Borsa emri 0.2744 (0.2744 < 0.27445 - 1e-6)
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2744",
            "qty": "500",
            "orderId": "order-777001",
        }
        self.harness._mock_conditional_orders = [{
            "parent_id": pos_order_id,
            "kind": "SL",
            "triggerPrice": "0.2744",
            "qty": "500",
        }]

        # GERÇEK _rr2_ratchet_trailing YOLU ÇALIŞTIRILIR
        asyncio.run(
            self.harness._rr2_ratchet_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                side="LONG",
                pos_data=pos_data,
                current_price=Decimal("0.2798"),
                position_order_id=pos_order_id,
            )
        )

        # KANIT: 0.2744 floor'u sağlamadığı için reddedilir, state korunur, 3s throttle kurulur
        self.assertEqual(pos_data["sl"], initial_sl)
        self.assertEqual(pos_data["last_logged_sl"], initial_sl)
        self.assertEqual(pos_data["confirmed_sl"], initial_sl)
        self.assertIn(pos_order_id, self.harness._rr2_ratchet_retry_ts)

        # Senaryo B: Borsa emri 0.2745 (0.2745 >= 0.27445 floor'unu sağlar)
        self.harness._rr2_ratchet_retry_ts.clear()
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2745",
            "qty": "500",
            "orderId": "order-777001",
        }
        self.harness._mock_conditional_orders = [{
            "parent_id": pos_order_id,
            "kind": "SL",
            "triggerPrice": "0.2745",
            "qty": "500",
        }]

        asyncio.run(
            self.harness._rr2_ratchet_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                side="LONG",
                pos_data=pos_data,
                current_price=Decimal("0.2798"),
                position_order_id=pos_order_id,
            )
        )

        # KANIT: 0.2745 floor'u sağladığı için kabul edilir ve state güncellenir
        self.assertEqual(pos_data["sl"], Decimal("0.2745"))
        self.assertEqual(pos_data["confirmed_sl"], Decimal("0.2745"))
        self.assertEqual(pos_data["last_logged_sl"], Decimal("0.2745"))
        self.assertNotIn(pos_order_id, self.harness._rr2_ratchet_retry_ts)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 7: GERÇEK _rr2_ratchet_trailing GÖVDESİ SHORT 3R FLOOR SINAMASI
    # ─────────────────────────────────────────────────────────────────────────
    def test_07_rr2_ratchet_trailing_real_body_short_3r_floor_strictly_enforced(self):
        """SHORT simetrisinde gerçek _rr2_ratchet_trailing yolu floor'u gevşetmez."""
        pos_order_id = 777002
        entry = Decimal("0.2798")
        r_orig = Decimal("0.00535")
        initial_sl = Decimal("0.2798")
        # 3R Peak: 0.26375 -> SHORT Floor: 0.2798 - 2 * 0.00535 = 0.26910
        pos_data = {
            "order_id": pos_order_id,
            "side": "SHORT",
            "r_eff_entry": entry,
            "r_distance_orig": r_orig,
            "r1_price": Decimal("0.2744"),
            "trailing_anchor_price": Decimal("0.2744"),
            "sl": initial_sl,
            "confirmed_sl": initial_sl,
            "last_logged_sl": initial_sl,
            "amount": Decimal("500"),
            "remaining_amount": Decimal("500"),
            "peak_price": Decimal("0.26375"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"SHORT": [pos_data]}}
        self.harness._mock_current_price = Decimal("0.26375")

        # Borsa emri 0.2692 (SHORT'ta 0.2692 > 0.26910 daha gevşektir -> REDDEDİLİR):
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2692",
            "qty": "500",
            "orderId": "order-777002",
        }
        self.harness._mock_conditional_orders = [{
            "parent_id": pos_order_id,
            "kind": "SL",
            "triggerPrice": "0.2692",
            "qty": "500",
        }]

        asyncio.run(
            self.harness._rr2_ratchet_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                side="SHORT",
                pos_data=pos_data,
                current_price=Decimal("0.26375"),
                position_order_id=pos_order_id,
            )
        )

        self.assertEqual(pos_data["sl"], initial_sl)
        self.assertIn(pos_order_id, self.harness._rr2_ratchet_retry_ts)

        # Borsa emri 0.2691 (SHORT floor'u sağlar -> KABUL):
        self.harness._rr2_ratchet_retry_ts.clear()
        self.harness._mock_live_order["triggerPrice"] = "0.2691"
        self.harness._mock_conditional_orders[0]["triggerPrice"] = "0.2691"

        asyncio.run(
            self.harness._rr2_ratchet_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                side="SHORT",
                pos_data=pos_data,
                current_price=Decimal("0.26375"),
                position_order_id=pos_order_id,
            )
        )

        self.assertEqual(pos_data["sl"], Decimal("0.2691"))
        self.assertNotIn(pos_order_id, self.harness._rr2_ratchet_retry_ts)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 8: QUANTIZE EXCEPTION TESTİ
    # ─────────────────────────────────────────────────────────────────────────
    def test_08_quantize_exception_preserves_stop_and_sets_retry(self):
        """quantize_order_price hata fırlatırsa ham hedefle devam edilmez, retry kurulur."""
        pos_order_id = 53829041518
        initial_sl = Decimal("0.2637")
        pos_data = {
            "order_id": pos_order_id,
            "side": "LONG",
            "entry": initial_sl,
            "sl": initial_sl,
            "confirmed_sl": initial_sl,
            "last_logged_sl": initial_sl,
            "amount": Decimal("336"),
            "remaining_amount": Decimal("336"),
            "management_stage": "HYBRID_TRAIL_2R",
            "peak_price": Decimal("0.2637"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"LONG": [pos_data]}}
        self.harness.connector.quantize_order_price = MagicMock(
            side_effect=RuntimeError("Connector trading rules unavailable")
        )

        asyncio.run(
            self.harness._handle_phase2_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                current_price=Decimal("0.2743"),
                pos_data=pos_data,
            )
        )

        self.assertEqual(len(self.harness.amend_calls), 0)
        self.assertEqual(pos_data["sl"], initial_sl)
        self.assertEqual(pos_data["last_logged_sl"], initial_sl)
        self.assertIn(pos_order_id, self.harness._hybrid_trail_retry_ts)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 9: QUANTIZE NONE TESTİ
    # ─────────────────────────────────────────────────────────────────────────
    def test_09_quantize_returns_none_preserves_stop_and_sets_retry(self):
        """quantize_order_price None döndürürse stop ve state korunur, retry kurulur."""
        pos_order_id = 53829041518
        initial_sl = Decimal("0.2637")
        pos_data = {
            "order_id": pos_order_id,
            "side": "LONG",
            "entry": initial_sl,
            "sl": initial_sl,
            "confirmed_sl": initial_sl,
            "last_logged_sl": initial_sl,
            "amount": Decimal("336"),
            "remaining_amount": Decimal("336"),
            "management_stage": "HYBRID_TRAIL_2R",
            "peak_price": Decimal("0.2637"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"LONG": [pos_data]}}
        self.harness.connector.quantize_order_price = MagicMock(return_value=None)

        asyncio.run(
            self.harness._handle_phase2_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                current_price=Decimal("0.2743"),
                pos_data=pos_data,
            )
        )

        self.assertEqual(len(self.harness.amend_calls), 0)
        self.assertEqual(pos_data["sl"], initial_sl)
        self.assertIn(pos_order_id, self.harness._hybrid_trail_retry_ts)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 10: QUANTIZE NAN TESTİ
    # ─────────────────────────────────────────────────────────────────────────
    def test_10_quantize_returns_nan_preserves_stop_and_sets_retry(self):
        """quantize_order_price NaN döndürürse stop ve state korunur, retry kurulur."""
        pos_order_id = 53829041518
        initial_sl = Decimal("0.2637")
        pos_data = {
            "order_id": pos_order_id,
            "side": "LONG",
            "entry": initial_sl,
            "sl": initial_sl,
            "confirmed_sl": initial_sl,
            "last_logged_sl": initial_sl,
            "amount": Decimal("336"),
            "remaining_amount": Decimal("336"),
            "management_stage": "HYBRID_TRAIL_2R",
            "peak_price": Decimal("0.2637"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"LONG": [pos_data]}}
        self.harness.connector.quantize_order_price = MagicMock(return_value=Decimal("NaN"))

        asyncio.run(
            self.harness._handle_phase2_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                current_price=Decimal("0.2743"),
                pos_data=pos_data,
            )
        )

        self.assertEqual(len(self.harness.amend_calls), 0)
        self.assertEqual(pos_data["sl"], initial_sl)
        self.assertIn(pos_order_id, self.harness._hybrid_trail_retry_ts)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 11: STALE MİKTAR READBACK TESTİ
    # ─────────────────────────────────────────────────────────────────────────
    def test_11_stale_quantity_readback_rejected_and_state_not_advanced(self):
        """
        Borsada fiyat doğru (0.2689) ancak miktar stale (672 vs beklenen 336) kaldığında:
        Doğrulayıcı None döner, state ilerletilmez, retry kurulur.
        """
        pos_order_id = 53829041518
        initial_sl = Decimal("0.2637")
        pos_data = {
            "order_id": pos_order_id,
            "side": "LONG",
            "entry": initial_sl,
            "sl": initial_sl,
            "confirmed_sl": initial_sl,
            "last_logged_sl": initial_sl,
            "amount": Decimal("336"),
            "remaining_amount": Decimal("336"),
            "management_stage": "HYBRID_TRAIL_2R",
            "peak_price": Decimal("0.2637"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"LONG": [pos_data]}}
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2689",
            "qty": "672",
            "orderId": "stale-qty-order-1",
        }
        self.harness._mock_conditional_orders = [{
            "parent_id": pos_order_id,
            "kind": "SL",
            "triggerPrice": "0.2689",
            "qty": "672",
        }]

        asyncio.run(
            self.harness._handle_phase2_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                current_price=Decimal("0.2743"),
                pos_data=pos_data,
            )
        )

        self.assertEqual(pos_data["sl"], initial_sl)
        self.assertNotEqual(pos_data.get("confirmed_sl"), Decimal("0.2689"))
        self.assertIn(pos_order_id, self.harness._hybrid_trail_retry_ts)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 12: RETRY THROTTLE KORUMASI
    # ─────────────────────────────────────────────────────────────────────────
    def test_12_retry_throttle_prevents_premature_dispatch(self):
        """3 saniyelik retry throttle penceresi içinde ikinci bir çağrı hiçbir emir göndermez."""
        pos_order_id = 53829041518
        initial_sl = Decimal("0.2637")
        pos_data = {
            "order_id": pos_order_id,
            "side": "LONG",
            "entry": initial_sl,
            "sl": initial_sl,
            "confirmed_sl": initial_sl,
            "last_logged_sl": initial_sl,
            "amount": Decimal("336"),
            "remaining_amount": Decimal("336"),
            "management_stage": "HYBRID_TRAIL_2R",
            "peak_price": Decimal("0.2637"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"LONG": [pos_data]}}
        # 1 saniye önce kurulmuş retry (< 3.0s throttle):
        self.harness._hybrid_trail_retry_ts[pos_order_id] = time.time() - 1.0

        asyncio.run(
            self.harness._handle_phase2_trailing(
                exchange="bybit_perpetual_demo",
                trading_pair="PONS-USDT",
                current_price=Decimal("0.2743"),
                pos_data=pos_data,
            )
        )

        # Throttle nedeniyle hiçbir işlem yapılmamalıdır
        self.assertEqual(len(self.harness.amend_calls), 0)
        self.assertEqual(pos_data["sl"], initial_sl)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 13: GERÇEK _hybrid_retry_break_even_sl GÖVDESİ İLE READBACK KİLİDİ
    # ─────────────────────────────────────────────────────────────────────────
    def test_13_hybrid_retry_break_even_sl_better_price_wrong_qty_readback_sequence(self):
        """
        KULLANICI TALEBİ:
        Gerçek _hybrid_retry_break_even_sl gövdesini kullanarak:
        - Daha iyi fiyat (0.2713) + yanlış miktar (672 vs beklenen 336)
        - Amend ACK başarılı (live_trig 0.2713 korunarak sadece miktar 336 olarak amend edilir)
        - İlk readback stale (borsa hala 672 gösteriyor) -> pending/state KORUNUR, False döner
        - Sonraki readback doğru (borsa 0.2713 ve 336 gösteriyor) -> ancak o zaman aşama ilerler
        - Gerçek market stopu/exchange yok; I/O mock'lu.
        """
        pos_order_id = 53829041518
        pos_data = {
            "order_id": pos_order_id,
            "side": "LONG",
            "entry": Decimal("0.2637"),
            "sl": Decimal("0.2584"),
            "amount": Decimal("336"),
            "remaining_amount": Decimal("336"),
            "pending_target_sl": Decimal("0.2637"),
            "management_stage": "HYBRID_TP1_FILLED_SL_PENDING",
            "peak_price": Decimal("0.2743"),
            "r2_price": Decimal("0.2744"),
        }
        self.harness._tracked_positions = {"PONS-USDT": {"LONG": [pos_data]}}
        self.harness._mock_current_price = Decimal("0.2743")

        # Canlı borsa emri: Fiyat daha iyi (0.2713 > entry 0.2637), miktar YANLIŞ (672 vs 336)
        self.harness._mock_live_order = {
            "orderStatus": "Untriggered",
            "triggerPrice": "0.2713",
            "qty": "672",
            "orderId": "order-53829041518",
        }
        # Borsa ilk readback listesi: hala stale (672)
        self.harness._mock_conditional_orders = [{
            "parent_id": pos_order_id,
            "kind": "SL",
            "triggerPrice": "0.2713",
            "qty": "672",
        }]

        # 1. ÇAĞRI: Amend ACK başarılı olur fakat ilk readback stale'dir:
        res1 = asyncio.run(
            self.harness._hybrid_retry_break_even_sl(
                connector=self.harness.connector,
                trading_pair="PONS-USDT",
                side="LONG",
                pos_data=pos_data,
            )
        )

        # KANIT 1: İlk readback stale olduğu için _hybrid_retry_break_even_sl False dönmeli
        self.assertFalse(res1, "HATA: Stale readback ile işlem başarılı sayıldı!")
        # KANIT 2: Amend çağrısında daha iyi fiyat (0.2713) korunmalı ve sadece miktar (336) gönderilmeli
        self.assertEqual(len(self.harness.amend_calls), 1)
        self.assertEqual(self.harness.amend_calls[0]["trigger_price"], Decimal("0.2713"))
        self.assertEqual(self.harness.amend_calls[0]["qty"], Decimal("336"))
        # KANIT 3: Pending state ve aşama KORUNMALI, ilerlememeli
        self.assertEqual(pos_data["pending_target_sl"], Decimal("0.2637"))
        self.assertEqual(pos_data["management_stage"], "HYBRID_TP1_FILLED_SL_PENDING")
        self.assertEqual(pos_data["sl"], Decimal("0.2584"))

        # 2. ÇAĞRI: Sonraki readback doğru (borsa güncellendi: 0.2713 ve 336)
        self.harness._mock_live_order["qty"] = "336"
        self.harness._mock_conditional_orders = [{
            "parent_id": pos_order_id,
            "kind": "SL",
            "triggerPrice": "0.2713",
            "qty": "336",
        }]
        self.harness.amend_calls.clear()

        res2 = asyncio.run(
            self.harness._hybrid_retry_break_even_sl(
                connector=self.harness.connector,
                trading_pair="PONS-USDT",
                side="LONG",
                pos_data=pos_data,
            )
        )

        # KANIT 4: Doğru readback ile işlem True dönmeli
        self.assertTrue(res2, "HATA: Doğru readback ile işlem başarısız oldu!")
        # KANIT 5: Artık yeni bir amend gönderilmesine gerek kalmamalı (mevcut emir eşleşti)
        self.assertEqual(len(self.harness.amend_calls), 0)
        # KANIT 6: pending_target_sl TEMİZLENMELİ
        self.assertNotIn("pending_target_sl", pos_data)
        # KANIT 7: confirmed_sl ve sl 0.2713 olarak kaydedilmeli
        self.assertEqual(pos_data["confirmed_sl"], Decimal("0.2713"))
        self.assertEqual(pos_data["sl"], Decimal("0.2713"))
        # KANIT 8: management_stage ilerlemeli (HYBRID_TP1_FILLED_SL_PENDING'den çıkıp aşama ilerlemeli)
        self.assertNotEqual(pos_data["management_stage"], "HYBRID_TP1_FILLED_SL_PENDING")
        self.assertIn(pos_data["management_stage"], ("HYBRID_HOLD_ENTRY", "HYBRID_TRAIL_2R"))


if __name__ == "__main__":
    unittest.main()
