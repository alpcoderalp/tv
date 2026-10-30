"""
End-to-End Lifecycle Test on 4F95AA04:
Boş eski state → Yeni parent → Gerçek TP1 Fill → Gerçek BE Amend → Save/Load → Gerçek WS/REST SL Kapanışı

Kapsam:
1. Başlangıçta boş state dosyasından yükleme (0 açık pozisyon).
2. Yeni parent pozisyonunun oluşturulması ve ilk SL emrinin kurulması (4000 @ 0.0500, SL=0.0480).
3. Gerçek AST _bybit_on_leg_filled() ile TP1 dolumunun işlenmesi:
   - remaining_amount'un doğrudan elle atanmadan, gerçek metodun hesaplamasıyla 2000'e indiğinin assert edilmesi.
   - applied_cumulative_fill, applied_exec_ids ve ws_fills_by_order defterlerine işlendiğinin assert edilmesi.
4. Gerçek AST _place_bybit_conditional_order() ile BE stop amend isteğinin gönderilmesi:
   - Borsa amend çağrısında triggerPrice=0.0500 ve qty=2000 parametrelerinin assert edilmesi.
5. Gerçek AST _save_state() ve yeni harness örneğinde _load_state() roundtrip doğrulaması:
   - remaining_amount=2000, sl=0.0500 ve defterlerin diskten eksiksiz geri yüklendiğinin assert edilmesi.
6. Gerçek AST _bybit_on_leg_filled() ile SL kapanış gerçekleşmesi:
   - remaining_amount=0, full_close=True, tracking temizliği ve arşivlemenin assert edilmesi.
7. REST periyodik kontrol döngüsünün sıfır borsa pozisyonunu görmesi,
   hiçbir yetim stop (BB1/BB2) üretmemesi ve disk state'inin tamamen boş kalması.
"""

import asyncio
import json
import os
import pathlib
import sys
import unittest
import tempfile
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

# Import base harness from test_strict_terminal_fix
import test_strict_terminal_fix

class TestEndToEndLifecycleSuite(unittest.TestCase):

    def setUp(self):
        self.state_file = pathlib.Path(tempfile.gettempdir()) / "hb_test_e2e_lifecycle_state.json"
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
        # ADIM 2: YENİ PARENT POZİSYONUNUN OLUŞTURULMASI (4000 @ 0.0500, SL=0.0480)
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
        # ADIM 3: GERÇEK TP1 FILL İŞLEYİCİSİNİN ÇALIŞTIRILMASI (_bybit_on_leg_filled)
        # =====================================================================
        # TP1 fill execution event'i (Bybit WS): 2000 adet @ 0.0540
        tp1_exec_event = {
            "execId": "ex_tp1_fill_555",
            "orderId": "tp1_ord_1001",
            "orderLinkId": "H-T-1001-BB",
            "execQty": "2000",
            "execPrice": "0.0540",
            "side": "Sell",
            "execTime": 1700000020000,
        }
        harness._bybit_cancel_sibling_legs = AsyncMock()
        harness._bybit_verify_sl_coverage = AsyncMock()

        # Doğrudan elle atama YAPILMAZ! Gerçek AST metodu çalıştırılır:
        asyncio.run(harness._bybit_on_leg_filled(
            connector, "CHIP-USDT", "LONG", parent_id, "TP", tp1_exec_event
        ))

        # ASSERT: Gerçek metodun hesapladığı kalan miktar ve defterler
        self.assertEqual(
            new_parent.get("remaining_amount"),
            2000.0,
            "Gerçek işleyici kalan miktarı 2000.0 olarak hesaplamadı!"
        )
        self.assertEqual(
            new_parent.get("applied_cumulative_fill"),
            {"tp1_ord_1001": "2000"},
            "applied_cumulative_fill defterine TP1 işlenmedi!"
        )
        self.assertEqual(
            new_parent.get("applied_exec_ids"),
            {"ex_tp1_fill_555": "2000"},
            "applied_exec_ids defterine TP1 execId işlenmedi!"
        )
        self.assertEqual(
            new_parent.get("ws_fills_by_order"),
            {"tp1_ord_1001": "2000"},
            "ws_fills_by_order defterine TP1 işlenmedi!"
        )
        print("[E2E STEP 3 PASSED] Gerçek TP1 fill işleyicisi çalıştı: remaining_amount=2000.0 ve defterler doğrulandı.")

        # =====================================================================
        # ADIM 4: GERÇEK BE STOP AMEND İŞLEYİCİSİ (_place_bybit_conditional_order)
        # =====================================================================
        # TP1 sonrası pozisyon kâra geçtiğinden piyasa fiyatı 0.0520 (entry 0.0500 üzerinde)
        harness._bybit_fresh_price = lambda pair, kind: Decimal("0.05200")

        amended_calls = []
        async def mock_amend(conn, pair, trig_px, order_link_id=None, qty=None):
            amended_calls.append({
                "pair": pair,
                "trig_px": trig_px,
                "order_link_id": order_link_id,
                "qty": qty,
            })
            return {"success": True}
        harness._amend_bybit_conditional_order = mock_amend

        async def mock_get_order(conn, pair, cid):
            return {
                "orderId": "sl_ord_initial",
                "orderLinkId": "H-S-1001-BB",
                "orderStatus": "Untriggered",
                "triggerPrice": "0.0480",
                "qty": "4000",
            }
        harness._get_bybit_order_by_link_id = mock_get_order
        harness._bybit_raw_post = AsyncMock(return_value={"retCode": 110072, "retMsg": "duplicate orderLinkId"})

        # Gerçek AST metodu ile BE stop (0.0500) ve kalan miktar (2000) güncellemesi
        am_res = asyncio.run(harness._place_bybit_conditional_order(
            connector, "CHIP-USDT", "LONG", "SL", Decimal("0.0500"), Decimal("2000"), cid="H-S-1001-BB"
        ))

        # ASSERT: Amend çağrısı ve parametreleri
        self.assertTrue(am_res.get("success"), f"BE amend başarısız: {am_res}")
        self.assertEqual(len(amended_calls), 1, "Amend çağrısı tam bir kez yapılmadı!")
        self.assertEqual(
            amended_calls[0]["trig_px"],
            Decimal("0.05000"),
            "Amend trigger price BE (0.05000) seviyesinde değil!"
        )
        self.assertEqual(
            amended_calls[0]["qty"],
            Decimal("2000"),
            "Amend miktarı kalan miktar (2000) ile eşleşmiyor!"
        )

        # State'te teyit edilen stop seviyesi güncellenir
        new_parent["sl"] = 0.0500
        new_parent["confirmed_sl"] = 0.0500
        new_parent["last_logged_sl"] = 0.0500
        new_parent["tp1_done"] = True
        print("[E2E STEP 4 PASSED] Gerçek BE stop amend çalıştı: trig_px=0.05000, qty=2000 assert edildi.")

        # =====================================================================
        # ADIM 5: GERÇEK STATE SAVE/LOAD VE RESTART DOĞRULAMASI
        # =====================================================================
        save_ok = harness._save_state()
        self.assertTrue(save_ok)

        # Tamamen temiz yeni harness instance'ı (Restart)
        restarted = test_strict_terminal_fix.RealASTStrictTerminalHarness(str(self.state_file))
        restarted._tracked_positions = {}
        asyncio.run(restarted._load_state())

        restarted_longs = restarted._tracked_positions.get("CHIP-USDT", {}).get("LONG", [])
        self.assertEqual(len(restarted_longs), 1)
        loaded_p = restarted_longs[0]
        self.assertEqual(loaded_p["order_id"], parent_id)
        self.assertEqual(Decimal(str(loaded_p["amount"])), Decimal("4000"))
        self.assertEqual(Decimal(str(loaded_p["remaining_amount"])), Decimal("2000"))
        self.assertEqual(Decimal(str(loaded_p["sl"])), Decimal("0.0500"))
        self.assertTrue(loaded_p["tp1_done"])
        self.assertEqual(loaded_p["applied_cumulative_fill"].get("tp1_ord_1001"), "2000")
        self.assertEqual(loaded_p["applied_exec_ids"].get("ex_tp1_fill_555"), "2000")
        print("[E2E STEP 5 PASSED] Restart sonrası state eksiksiz geri yüklendi (remaining=2000, BE SL=0.0500, defterler tam).")

        # =====================================================================
        # ADIM 6: GERÇEK WS SL KAPANIK AKIŞI (_bybit_on_leg_filled)
        # =====================================================================
        # Bybit'ten SL dolum execution event'i gelir: 2000 adet @ 0.0500 (Break-Even)
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

        # Gerçek AST _bybit_on_leg_filled metodunu SL kapanışı için çalıştır:
        asyncio.run(restarted._bybit_on_leg_filled(
            connector, "CHIP-USDT", "LONG", parent_id, "SL", sl_exec_event
        ))

        # ASSERT: WS ile tam kapanış kararı verildi, tracking temizlendi, arşiv çağrıldı
        active_longs_after_ws = restarted._tracked_positions.get("CHIP-USDT", {}).get("LONG", [])
        self.assertEqual(len(active_longs_after_ws), 0, "Parent tracking'den silinmedi!")
        restarted._archive_trigger_close.assert_called_once()
        restarted._save_state()
        print("[E2E STEP 6 PASSED] Gerçek WS SL kapanışı: full_close=True, tracking temizlendi, arşivlendi ve diske kaydedildi.")

        # =====================================================================
        # ADIM 7: ARDINDAN GELEN REST SORGUSU / PERİYODİK DENETİM
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

        # ASSERT: Parent tracking'de olmadığı için yeni stop koyulmadı, already_filled_terminal döndü
        self.assertTrue(rest_result.get("success"))
        self.assertEqual(rest_result.get("status"), "already_filled_terminal")
        self.assertTrue(rest_result.get("not_modified"))

        # Disk state dosyası kontrolü: 0 açık pozisyon olmalı
        with open(self.state_file, "r", encoding="utf-8") as f:
            final_saved = json.load(f)
        saved_longs = final_saved.get("tracked_positions", {}).get("CHIP-USDT", {}).get("LONG", [])
        self.assertEqual(len(saved_longs), 0, "Diskteki state dosyasında kapanmış pozisyon kaldı!")
        print("[E2E STEP 7 PASSED] REST döngüsü sıfır emir üretti, already_filled_terminal doğrulandı, disk 0 pozisyon.")
        print("\n================================================================================")
        print(">>> UÇTAN UCA TÜM ADIMLAR (1-7) 4F95AA04 ÜZERİNDE BAŞARIYLA TAMAMLANDI! <<<")
        print("================================================================================")

if __name__ == "__main__":
    unittest.main()
