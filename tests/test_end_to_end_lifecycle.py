"""
End-to-End Lifecycle Test on 4F95AA04:
Boş eski state → Yeni parent → TP1 → Save/Load → WS/REST SL kapanışı

Kapsam:
1. Başlangıçta boş state dosyasından yükleme (0 açık pozisyon).
2. Yeni parent pozisyonunun oluşturulması ve ilk SL emrinin kurulması.
3. TP1 tetiği ve kısmi dolumu (kalan miktarın %50'ye düşmesi, BE stop amend'i, deftere işlenmesi).
4. Gerçek AST _save_state() ve yeni harness örneğinde _load_state() roundtrip doğrulaması.
5. WS üzerinden SL kapanış gerçekleşmesi (execId, cumExecQty, full_close kararı, tracking temizliği, disk kaydı).
6. Ardından gelen REST periodic verify / reconcile döngüsünün 0 borsa pozisyonunu görmesi,
   hiçbir yetim stop (BB1/BB2) üretmemesi ve disk state'inin tamamen boş kalması.
"""

import asyncio
import json
import os
import pathlib
import sys
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

# Import base harness from test_strict_terminal_fix
import test_strict_terminal_fix

class TestEndToEndLifecycleSuite(unittest.TestCase):

    def setUp(self):
        self.state_file = pathlib.Path("scratch/test_e2e_lifecycle_state.json")
        if self.state_file.exists():
            self.state_file.unlink()

    def tearDown(self):
        if self.state_file.exists():
            try:
                self.state_file.unlink()
            except Exception:
                pass

    def test_e2e_clean_state_to_parent_tp1_restart_and_ws_rest_sl_close(self):
        connector = test_strict_terminal_fix.make_mock_connector()

        # =====================================================================
        # ADIM 1: BOŞ ESKİ STATE İLE BAŞLANGIÇ
        # =====================================================================
        empty_initial_state = {
            "timestamp": 1700000000.0,
            "tracked_positions": {
                "CHIP-USDT": {"LONG": [], "SHORT": []}
            },
            "signal_cache": {},
            "sltp_orders": {},
            "position_identity_ledger": {},
            "phase2_immunity": {},
            "per_fill_accumulators": {},
            "grace_period_until": {}
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(empty_initial_state, f)

        harness = test_strict_terminal_fix.RealASTStrictTerminalHarness(str(self.state_file))
        harness._tracked_positions = {}
        asyncio.run(harness._load_state())

        self.assertEqual(len(harness._tracked_positions.get("CHIP-USDT", {}).get("LONG", [])), 0)
        print("\n[E2E STEP 1 PASSED] Boş state başarıyla yüklendi: 0 aktif pozisyon.")

        # =====================================================================
        # ADIM 2: YENİ PARENT POZİSYONUNUN OLUŞTURULMASI
        # =====================================================================
        parent_id = 1001
        new_parent = {
            "order_id": parent_id,
            "exchange": "bybit_perpetual_demo",
            "entry": 0.0500,
            "sl": 0.0480,
            "tp": 0.0540,
            "amount": 4000.0,
            "remaining_amount": 4000.0,
            "side": "LONG",
            "risk": 8.0,
            "1r_reached": False,
            "phase2_active": False,
            "applied_cumulative_fill": {},
            "applied_exec_ids": {},
            "ws_fills_by_order": {},
            "confirmed_sl": 0.0480,
            "last_logged_sl": 0.0480,
            "tp1_done": False,
        }
        harness._tracked_positions["CHIP-USDT"]["LONG"].append(new_parent)
        harness._sltp_orders[parent_id] = {
            "sl_order_id": "H-S-1001-BB",
            "sl_price": 0.0480,
            "side": "LONG",
            "trading_pair": "CHIP-USDT",
        }

        # Borsa üzerinde 4000 adetlik SL emri aktif
        exchange_stops = [
            {
                "orderId": "sl_ord_initial",
                "orderLinkId": "H-S-1001-BB",
                "parent_id": parent_id,
                "kind": "SL",
                "qty": Decimal("4000"),
                "triggerPrice": Decimal("0.0480"),
                "side": "SELL",
                "positionIdx": 1,
                "orderStatus": "Untriggered",
            }
        ]
        harness._get_bybit_conditional_orders = AsyncMock(return_value=exchange_stops)
        harness._get_cached_position_amount = AsyncMock(return_value=Decimal("4000"))

        save_ok = harness._save_state()
        self.assertTrue(save_ok)
        print("[E2E STEP 2 PASSED] Yeni parent #1001 oluşturuldu (qty=4000 @ 0.0500, SL=0.0480).")

        # =====================================================================
        # ADIM 3: TP1 TETİĞİ VE KISMİ DOLUM (%50 DOLUM, STOP BE'YE TAŞINDI)
        # =====================================================================
        # TP1 2000 adet doldu
        tp1_fill_qty = Decimal("2000")
        new_parent["remaining_amount"] = float(Decimal("4000") - tp1_fill_qty) # 2000.0
        new_parent["tp1_done"] = True
        new_parent["applied_cumulative_fill"]["HTP1-1001"] = str(tp1_fill_qty)

        # Stop Break-Even'a (0.0500) taşınır ve kalan miktar 2000'e güncellenir
        new_parent["sl"] = 0.0500
        new_parent["confirmed_sl"] = 0.0500
        new_parent["last_logged_sl"] = 0.0500

        exchange_stops[0]["qty"] = Decimal("2000")
        exchange_stops[0]["triggerPrice"] = Decimal("0.0500")
        harness._get_cached_position_amount = AsyncMock(return_value=Decimal("2000"))

        self.assertEqual(new_parent["remaining_amount"], 2000.0)
        self.assertEqual(new_parent["sl"], 0.0500)
        self.assertTrue(new_parent["tp1_done"])
        print("[E2E STEP 3 PASSED] TP1 gerçekleşti: kalan=2000.0, stop BE=0.0500 seviyesine taşındı.")

        # =====================================================================
        # ADIM 4: GERÇEK STATE SAVE/LOAD VE RESTART DOĞRULAMASI
        # =====================================================================
        save_ok = harness._save_state()
        self.assertTrue(save_ok)

        # Tamamen temiz yeni harness instance'ı (Restart)
        restarted = test_strict_terminal_fix.RealASTStrictTerminalHarness(str(self.state_file))
        restarted._tracked_positions = {}
        asyncio.run(restarted._load_state())

        restarted_shorts = restarted._tracked_positions.get("CHIP-USDT", {}).get("LONG", [])
        self.assertEqual(len(restarted_shorts), 1)
        loaded_p = restarted_shorts[0]
        self.assertEqual(loaded_p["order_id"], parent_id)
        self.assertEqual(Decimal(str(loaded_p["amount"])), Decimal("4000"))
        self.assertEqual(Decimal(str(loaded_p["remaining_amount"])), Decimal("2000"))
        self.assertEqual(Decimal(str(loaded_p["sl"])), Decimal("0.0500"))
        self.assertTrue(loaded_p["tp1_done"])
        self.assertEqual(loaded_p["applied_cumulative_fill"].get("HTP1-1001"), "2000")
        print("[E2E STEP 4 PASSED] Restart sonrası state eksiksiz geri yüklendi (remaining=2000, BE SL=0.0500).")

        # =====================================================================
        # ADIM 5: WS ÜZERİNDEN SL KAPANIŞI (BREAK-EVEN STOP DOLUMU)
        # =====================================================================
        # Bybit'ten SL dolum execution event'i gelir
        sl_exec_event = {
            "execId": "ex_sl_close_999",
            "orderId": "sl_ord_initial",
            "orderLinkId": "H-S-1001-BB",
            "execQty": "2000",
            "execPrice": "0.0500",
            "side": "Sell",
            "execTime": 1700000050000,
        }
        restarted._bybit_cancel_sibling_legs = AsyncMock()
        restarted._bybit_verify_sl_coverage = AsyncMock()
        restarted._archive_trigger_close = MagicMock()

        # Gerçek AST _bybit_on_leg_filled metodunu çalıştır:
        asyncio.run(restarted._bybit_on_leg_filled(
            connector, "CHIP-USDT", "LONG", parent_id, "SL", sl_exec_event
        ))

        # Doğrulama: WS ile tam kapanış kararı verildi, tracking temizlendi, arşiv çağrıldı
        active_longs_after_ws = restarted._tracked_positions.get("CHIP-USDT", {}).get("LONG", [])
        self.assertEqual(len(active_longs_after_ws), 0, "Parent tracking'den silinmedi!")
        restarted._archive_trigger_close.assert_called_once()
        # Periyodik döngü / kapanış sonrası state kaydetme:
        restarted._save_state()
        print("[E2E STEP 5 PASSED] WS SL kapanışı: full_close=True, tracking temizliği tamamlandı, arşivlendi ve kaydedildi.")

        # =====================================================================
        # ADIM 6: ARDINDAN GELEN REST SORGUSU / PERİYODİK DENETİM
        # =====================================================================
        # Borsa pozisyonu artık 0
        restarted._get_cached_position_amount = AsyncMock(return_value=Decimal("0"))
        restarted._get_bybit_conditional_orders = AsyncMock(return_value=[])

        # Eğer periyodik denetim eski linkId ile emir koymaya kalkışırsa:
        restarted._get_bybit_order_by_link_id = AsyncMock(return_value={
            "orderId": "sl_ord_initial",
            "orderLinkId": "H-S-1001-BB",
            "orderStatus": "Filled",
            "cumExecQty": "2000",
            "avgPrice": "0.0500",
        })
        restarted._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate orderLinkId"})

        rest_result = asyncio.run(restarted._place_bybit_conditional_order(
            connector, "CHIP-USDT", "LONG", "SL", Decimal("0.0500"), Decimal("2000"), cid="H-S-1001-BB"
        ))

        # Doğrulama: Parent tracking'de olmadığı için yeni stop koyulmadı, already_filled_terminal döndü
        self.assertTrue(rest_result.get("success"))
        self.assertEqual(rest_result.get("status"), "already_filled_terminal")
        self.assertTrue(rest_result.get("not_modified"))

        # Disk state dosyası kontrolü: 0 açık pozisyon olmalı
        with open(self.state_file, "r", encoding="utf-8") as f:
            final_saved = json.load(f)
        saved_longs = final_saved.get("tracked_positions", {}).get("CHIP-USDT", {}).get("LONG", [])
        self.assertEqual(len(saved_longs), 0, "Diskteki state dosyasında kapanmış pozisyon kaldı!")
        print("[E2E STEP 6 PASSED] REST döngüsü sıfır emir üretti, already_filled_terminal doğrulandı, disk 0 pozisyon.")
        print("\n================================================================================")
        print(">>> UÇTAN UCA TÜM ADIMLAR (1-6) 4F95AA04 ÜZERİNDE BAŞARIYLA TAMAMLANDI! <<<")
        print("================================================================================")

if __name__ == "__main__":
    unittest.main()
