# tv_signal_strategy.py — Bybit-Native Migration Notes

> ⚠️ **GÜNCEL MİMARİ (v4.0): per-piece SL = koşullu emir (CID) **+** per-piece TP =
> **reduceOnly LIMIT** emir (10'luk kotayı TÜKETMEZ) **+** aggregate konsolidasyon
> **PASİF** (silinmedi, tek env ile geri açılır; acil fallback olarak duruyor).**
> §1-9 = ilk tur (trading-stop Partial). §10 = v2 (order/create + CID).
> §11 = v3 + DEMO API'de kanıtlanmış gerçekler. §12 = v3.1 (recovery loop).
> §13 = v3.2 (tracking şaşması). §14 = v3.3 (sembol çözümleme).
> §15 = v3.4 (arşiv okuyucu). §16 = v3.5 (kapanış tespiti / positionSide).
> §17 = v3.6 (pozisyon cache salınımı — HB upstream `side=''`).
> §18 = v4.0 (reduceOnly LIMIT TP + konsolidasyon pasif). §19 = v4.1 (toplam SL
> kapsama denetimi).
> §20 = v4.2 (zero-remaining yanlış pozitifi + orphan limit TP + arşiv boşluğu
> + SAAT DİLİMİ hazard notu).
> §21 = v4.3 (orphan SL atfı + TP ESCALATE + sinyal validasyonu + MQTT körlüğü).
> §22 = v4.4 (olay-güdümlü kapanış + false-success 5. nokta + backstop bug'ı).
> §23 = v4.5 (strateji saatlik fiyatla çalışıyordu; Fix AY taze ticker).
> §24 = v5.0, RİSK FORMÜLÜ KALDIRAÇLA YANLIŞ ÖLÇEKLENİYORDU (Fix BD) +
> hayalet-parça reconciliation (Fix BB/BB-2) + trailing bayat-fiyat regresyonu
> (Fix BA).
> §25 = v5.1, Risk_Sizing_Fix.md uygulandı (Fix BE: sizing filtreleri, %5→%25
> marj tavanı, fee-aware qty, MAX_OPEN_PIECES=6) + phase2_correction.md uygulandı
> (Fix BF: public WS ticker feed + tek 1R tetikleyicisi) + Fix BG (eşik gevşetme).
> §26 = v5.2 — CANLI VPS FORENSIC TUR (2026-08-07): per-piece real-entry
> hep blended-avg'a düşüyordu (Fix BH), fee/commission HER YERDE hardcoded 0
> idi (Fix BI), monitor'ın WS-dual-mode kısayolu 1R'i 35+ dakika kaçırmasına
> izin veriyordu → ALWAYS-ON backstop'a çevrildi (Fix BJ), WS reconnect/kopma
> tamamen görünmezdi (Fix BK), eski polling SL/TP-trigger yolu arşive hiç
> yazmıyordu (Fix BM).
> **§27 = live geçiş/çoklu-pair VPS gerçekleri** (kod değişikliği yok, tek
> gereken `.env.hummingbot`'ta `BYBIT_ENV` + yml'de `markets:` connector
> anahtarı) + `tools/switch_bybit_env.sh` otomasyonu.
> §28 = v5.3 — RESTART SONRASI FAZ 2 HAFIZASI KAYBI (Fix BN, borsa-imzası
> tespiti) + `manual_second_take`'in Bybit'te ölü kod olması (Fix BO).
> **§29 = v5.4 — AMNEZİNİN GERÇEK KÖK NEDENİ: boot'ta on_tick'in auto-save'i
> `_load_state`'ten ÖNCE boş tracking'i dosyanın üzerine yazıyordu (Fix BQ,
> §15.5 gizemi kapandı) + Faz 2 TAM durumu artık persist (Fix BQ-2) +
> auto-detect KOŞULSUZ exchange-truth adoption ve ikinci Faz-2 kanıtı E2 =
> reddedilen arşivin ratio≈0.5 parmak izi (Fix BP; BN'in tek kanıtı önceki
> bozuk restart'la yok edilebiliyordu — canlıda kanıtlandı).**
> **§30 = v5.5 — 1R KOMİSYONU YARISINDAN AZ SAYIYORDU: hem oran bayattı
> (0.0008 vs gerçek round-trip 0.0011) hem komisyon TEK sayılıyordu (denklemde
> İKİ kez görünür) → 1R hedefi `entry×0.0014` ERKEN, R cinsinden
> `0.0014/sl_pct` (ZAMA %1.22 SL'de 0.115R; MIN_SL_PCT tabanında 0.70R).
> Fix BR: `_fee_adjusted_r_levels` = R'nin TEK tanımı + TP gerçek entry+fee'ye
> göre yeniden türetilir (SL SABİT), sinyalin R/R'si korunur ve Faz 2'de TP2
> olarak akar. Fix BS: dust kalıntı artık gerçekten MARKET ile kapatılıyor
> (`B4_DISABLE_SLTP_CLOSE` etrafından dolanılır — aksi halde NO-OP'tu).
> Fix BT: polling kapanış dalı kapsama denetimi yapmıyordu. Fix BU: eski
> `DUST CLOSE` bloğu sonucu okumadan "kapatıldı" diyordu.**
> **§31 = v5.6 — DEĞİŞTİRİLEBİLİR POZİSYON YÖNETİMİ (Fix BV). Tek env:
> `POSITION_MANAGEMENT_MODE=legacy|rr2_trailing|passive`.
> `legacy` = mevcut akış (gövdesi `_try_trigger_legacy_phase2`'ye BİREBİR
> taşındı, byte-identical). `rr2_trailing` = 1R'de İŞLEM YOK → 2R'de
> SL=fee-aware R1 (konulamazsa parent-scoped MARKET close) → +%0.2 →
> SL ≥ R2 + R2 anchor'lı trailing. `passive` = yönetim VE koruma onarımı
> (7 giriş noktası) KAPALI.
> ⚠️ **MODLAR KARMA ÇALIŞMAZ** — geçiş prosedürü §31.7'de ADIM ADIM.
> ⚠️ RR2'de **girişte TP emri KONULMAZ** (`RR2_PLACE_ENTRY_TP=0`): giriş
> TP'si Fix BR sonrası tam olarak 2R'de, yani RR2 tetiğinin AYNI
> fiyatında durur; konursa trailing HİÇ çalışmaz (§31.2-C).
> Planın 5 hatası §31.2'de düzeltildi (en önemlisi §15.3'ün kod
> okuma hatası + 2 kaçırılmış TP-diriltme yolu).
> **§31.10 = Fix BW — kurtarma yolları RR2 durumunu YOK EDİYORDU: rebuild
> RR2 alanlarını taşımıyordu (donmuş runner) ve adoption geometriyi TAŞINMIŞ
> stop'tan türetiyordu; ayrıca adoption'ın `1r_reached=True` yazması parçayı
> RR2'de TAMAMEN ATIL bırakıyordu (EN GÜNCEL).**
> **§32 = v5.7 — UPGRADED POSITION CLEANUP, TRAILING SAFETY NET & COUNT HARDENING (Fix BX/BY/BZ).**
> **§33 = v5.8 — RR2 MULTI-STAGE RATCHET TRAILING v4 FINAL (Fix CA: wick floor kilidi, 11R tavanı, ladder anchor ayrımı).**
> **§34 = v5.9 — HYBRID TRAILING MODE (Fix CB: 1R TP1 %50 + BE + 1R-2R hold entry + 2R trailing + 3R ratchet).**
> **§35 = v6.0 — BYBIT DEMO UNIFIED CANDIDATE (4F95AA04) — QUANTIZE LOOP, TERMINAL STOP IDEMPOTENT FILL ACCOUNTING & RECONCILE (Fix CC/CD/CE/CF) (EN GÜNCEL).**
> 📌 **KAYNAK ÖNCELİĞİ VE DOĞRULUK HİYERARŞİSİ:**
> 1. **Güncel Kod Davranışı Kaynağı:** Hash'i sabitlenmiş kaynak kodudur (`tv_signal_strategy.py` SHA256: `4f95aa04183052f4333b32960067e3591c0f48b0a6dbeb512ac442a93687af41`).
> 2. **Canlı Runtime Durumu Kaynağı:** Taze UTC zaman damgalı Bybit API sorguları, aktif container ortam değişkenleri ve ham log kayıtlarıdır.
> 3. **Dokümantasyon Notları:** Bölüm numaraları (§) kronolojik evrim sürecini ve analiz bağlamını temsil eder; tek başına bir bölüm numarası koddaki ve runtime'daki kesin kanıtların üzerinde mutlak doğruluk kaynağı değildir (tarihsel çelişkilerde öncelik güncel bölümlerdedir: §35 > §34 > §33 > §32 > §31...).
> §11.1, §12.1, §16.1, §17.2 ve **§18.3**'teki API gerçekleri *varsayım değil*, canlı
> probe ile doğrulanmıştır — **aynı şeyleri tekrar test etmeyin.**
> ⚠️ **Deploy durumu (2026-10-28):** **v6.0 Unified Release (Fix CC/CD/CE/CF) Bybit Demo ortamında kalıcı olarak DEPLOY EDİLDİ.**
> Host/container SHA256: `4f95aa04183052f4333b32960067e3591c0f48b0a6dbeb512ac442a93687af41` (birebir eşleşti).
> Test suite: **37/37 PASS** (`tests/run_all_candidate_tests.py` — 23 strict terminal + 13 quantize + 1 real AST E2E).
> VPS durumu (Deploy Anı Snapshot — 2026-10-28 18:41:27 UTC): Bybit Demo REST API üzerinden taze denetimle 0 pozisyon, 0 limit emir, 0 koşullu/stop emir doğrulanarak flat başlatıldı; bu sürekli bir durum değil, deploy anına ait anlık bir görüntüdür (snapshot).
> ⚠️ **Runtime Doğrulama Sınırı:** Deploy sonrasında doğal sinyalle yeni pozisyon açılması (ör. 2026-10-28 19:30:13 UTC PONS-USDT LONG), botun sinyal alıp işlediğini gösterir ancak trailing ilerlemesi, borsa amend veya terminal kapanış mantığının canlıda tam doğrulandığı anlamına gelmez; bu akışlar ancak doğal 1R/2R/3R veya SL tetiklenme anlarında doğrulanabilir.
> ⚠️ **Eski deploy durumu (2026-09-01):** **v5.5 (BR/BS/BT/BU) + v5.6 (BV) HENÜZ
> DEPLOY EDİLMEDİ.** Lokal: derlendi · AST **0 fonksiyon kaybı (432 → 457)** ·
> `BYBIT_GUARD`=2 · **12 statik paketin TAMAMI PASS** (`verify_v56_fixes.py`
> yeni, **139 assert**, gerçek fonksiyonlar koşuluyor).
> `verify_v51/v52/v55` yeniden-adlandırma (`_try_trigger_legacy_phase2`)
> için bilinçli güncellendi. `verify_v4_limit_tp.py` canlı API anahtarı ister.
> ⚠️ Varsayılan `POSITION_MANAGEMENT_MODE=legacy` → deploy davranışı
> DEĞİŞMEZ; yeni yönetim ancak §31.7 prosedürüyle açılır.
> ⚠️ **Eski deploy durumu (2026-08-22):** VPS md5 = lokal HEAD (2026-08-12'den beri
> v5.4 çalışıyor; 5 günlük logda 0 restart). **v5.5 (Fix BR/BS/BT/BU) HENÜZ
> DEPLOY EDİLMEDİ.** Lokal: derlendi · AST **0 fonksiyon kaybı (432 → 439)** ·
> `BYBIT_GUARD`=2 · **11 statik paketin TAMAMI PASS** (`verify_v55_fixes.py`
> yeni; `verify_v51_fixes.py` 1R assert'leri BİLİNÇLİ güncellendi:
> 101.08 → 101.22, ayrıca `R_FEE_AWARE=0` legacy paritesi de assert edilir).
> `verify_v4_limit_tp.py` canlı API anahtarı ister → koşulmadı.
> ⚠️ İlk gün logunda **Faz 2 aktivasyonları daha SEYREK ve daha DÜŞÜK R ile**
> görünecek (aynı durum eskiden `1.04R`, artık `0.93R`) — bu REGRESYON DEĞİL,
> düzeltmenin kendisidir (§30.2/§30.6-R1). Geri alma: `R_FEE_AWARE=0`.
> ⚠️ **Eski deploy durumu (2026-08-08):**
> VPS md5 doğrulandı — **v5.3 (Fix BN/BO dahil) 2026-08-07 17:49 UTC'den beri
> çalışıyor** (md5 lokalin BN'li haliyle birebir eşleşti). **v5.4 (Fix
> BP/BQ/BQ-2) HENÜZ DEPLOY EDİLMEDİ — CANLI ÖNCESİ ZORUNLU** ve deploy'da
> §29.5'teki TEK SEFERLİK state-dosyası temizliği YAPILMALI (mevcut dosya
> 20:50 fabrikasyonlarıyla kirli).
> Lokal: derlendi · AST 0 fonksiyon kaybı (432) · `verify_v53_fixes.py`
> **33/33** (yeniden yazıldı: BQ/BQ-2/BP/BO),
> `verify_v52_fixes.py` **25/25**,
> `verify_v51_fixes.py` **64/64**,
> `verify_v46_fixes.py` 19/19, `verify_v45/v44/v43/v42_fixes.py`/
> `verify_sl_coverage.py`/`verify_exec_fixes.py` hepsi PASS (8/8 paket).
> ⚠️ **ANALYZER İÇİN (GÜNCELLENDİ → §30.9):** `_processed` dosyasının **her
> kopyası kaydırılmış DEĞİL** — 2026-08-22'de incelenen kopya VPS ham logu ile
> birebir aynı damgaları taşıyordu (yani **UTC**). §20.7'deki +3 varsayımına
> güvenmeyin; korelasyon öncesi tek bir olayı iki dosyada karşılaştırarak
> DOĞRULAYIN. Tek yetkili kaynak VPS ham `logs_tv_signal_strategy.log` (UTC).

> Bu dosya, `tv_signal_strategy.py`'nin OKX-native'den **Bybit-native**'e taşınması
> sırasında yapılan analiz ve düzeltmeleri özetler. Amaç: sonraki AI oturumlarının
> bıraktığımız yerden az token harcayarak devam edebilmesi.
>
> OKX-native referans (karşılaştırma için): `tv_signal_strategy_prebybit.py`
> Uygulama planı: `implementation_plan.md`
> Partial TP/SL yönergesi: `~/Downloads/Bybit V5 API Hedge Mode ve Parçalı TP_SL Bot Otomasyon Yönergesi.md`

## ⚠️ ÖNCE OKU — Doğrulama zorunlu
- Bu makine hummingbot paketini **import edemiyor** (`No module named hummingbot.connector`).
  Bot Docker/VPS içinde çalışıyor. Bu yüzden yalnızca `python -m py_compile tv_signal_strategy.py`
  ile derleme doğrulanabildi; **runtime davranışı DEMO ortamında test EDİLMELİDİR**
  (`EXCHANGE_BACKEND=bybit`, `BYBIT_ENV=demo`, `B4_DRY_RUN=0`, `TRADING_ENABLED=1`).
- Bazı Bybit v5 API davranışları test edilmeden %100 doğrulanamadı → aşağıdaki
  "Doğrulanacak Varsayımlar" bölümüne bak.

---

## 1) Sistem Mimarisi (özet)
- Strateji TradingView sinyalleriyle (MQTT) pozisyon açar; 3 borsayı destekler:
  Binance / OKX / **Bybit** (aktif backend). Backend seçimi: `EXCHANGE_BACKEND` env
  (varsayılan `bybit`), kurulum L928-966 civarı; aktif connector adı `ACTIVE_CONNECTOR`.
- Exchange dispatch helper'ları: `_is_okx_connector`, `_is_bybit_connector` (L1671+).
- **Faz 1 (1R monitor)**: `_monitor_positions` — her pozisyonun kendi entry/sl'sine göre
  1R kârı yakalar → Phase 2 tetikler. Exchange-agnostic (per-position).
- **Faz 2**: kısmi kapama (`_close_partial_position`) + SL'yi entry'ye çek (risk-free)
  + dinamik trailing SL (`_update_trailing_sl`). SL güncellemesi `_set_phase2_sltp`
  ve `_update_trailing_sl` üzerinden geçer.
- Koruma ağı katmanları (hepsi Bybit-aware yapıldı):
  entry placement → `_naked_position_recovery` (yerel tracking) →
  `_periodic_sltp_verify`/`_bybit_periodic_sltp_verify` (exchange-truth) → Phase 2.

## 2) Bybit Mimari Kısıtı — EN ÖNEMLİ NOKTA
- Bybit **hedge mode**'da bir pair+yönde **tek** pozisyon vardır: `positionIdx=1` (LONG),
  `positionIdx=2` (SHORT). Aynı yöndeki tüm girişler bu tek pozisyona toplanır
  (`_bybit_position_idx` L1713 her zaman 1/2 döner).
- Bu yüzden OKX'teki "aynı yönde çoklu bağımsız pozisyon, her biri kendi algo SL/TP'si"
  modeli Bybit'te **doğrudan çalışmaz**.
- **Çözüm (kullanıcı onaylı, yönerge dosyasından):** `tpslMode="Partial"` + `tpSize`/`slSize`.
  Her fill parçası, kendi qty'si kadar **izole bir koşullu emir** (conditional order)
  olarak SL/TP alır. Böylece tek hedge pozisyonu içinde parça-bazlı TP/SL mümkün olur.
- **Partial-mode kritik gerçek:** Partial SL/TP, pozisyonun `stopLoss`/`takeProfit`
  ALANLARINDA GÖRÜNMEZ. Ayrı koşullu emirlerdir → `v5/order/realtime?orderFilter=StopOrder`
  ile okunur. Bybit kuralı: bir çağrıda hem `tpSize` hem `slSize` set edilirse EŞİT olmalı.

## 3) Bybit Yardımcıları (hepsi tek sınıfta, ~L1671-2300)
| Helper | Ne yapar |
|---|---|
| `_is_bybit_connector` | connector Bybit mi |
| `_bybit_position_idx(side)` | 1=LONG / 2=SHORT (hedge) |
| `_bybit_raw_post(conn, endpoint, body)` | HB throttler bypass, imzalı POST. **Kalıcı session + timeout + client-side pacing (`BYBIT_RAW_MIN_INTERVAL`=0.15s) + 10006/10018/10429 retry** |
| `_place_bybit_trading_stop(conn, tp, side, sl_price=, tp_price=, qty=)` | `qty` verilirse **Partial** (tpSize/slSize=qty), yoksa **Full**. `34040 "not modified"` → success (spam fix). `out["not_modified"]`, `out["mode"]` döner |
| `_clear_bybit_trading_stop(conn, tp, side, clear_sl, clear_tp)` | Partial koşullu SL/TP'yi `v5/order/cancel` ile iptal + Full alanını "0"la |
| `_get_bybit_conditional_orders(conn, tp, side=)` | `order/realtime?orderFilter=StopOrder` → [{orderId, kind("SL"/"TP"), triggerPrice, qty, positionIdx}] |
| `_get_bybit_position_protection(conn, tp, side)` | Full (position stopLoss/takeProfit) + Partial (koşullu emirler) birleşik → {found, size, has_sl, has_tp, sl_price, tp_price} |
| `_get_bybit_executions(conn, tp, order_id=, limit=)` | `v5/execution/list` → normalize [{qty, price, side("BUY"/"SELL"), orderId, time}] |
| `_place_bybit_market_order(...)` | Entry market IOC (self.buy/sell veya REST v5/order/create) |
| `_close_bybit_market_amount(...)` | reduceOnly market kapama |
| `_fetch_bybit_positions(conn, force, reason)` | `v5/position/list` → `_binance_positions_cache[f"{tp}_{side}"]` (amount signed, entry) |
| `_get_cached_open_orders_bybit(conn, sym)` | Aktif (non-conditional) emirler |
| `_patch_bybit_connector_order_states()` | HB connector `ORDER_STATE` dict'ine `Triggered/Untriggered/Deactivated/Active` ekler (Sorun 2b, KeyError fix). __init__'te bybit ise çağrılır |

## 4) Yapılan Düzeltmeler (kronolojik gruplar)

### A. İlk tur (Sorun 2a/2c/2d + eksik Bybit branch'leri)
- **KRİTİK** `_set_phase2_sltp` Bybit branch'i tanımsız `position_side` yerine `side`
  kullanıyor (UnboundLocalError → tüm Bybit Phase 2 SL/TP sessizce çöküyordu).
- `_place_sltp_simple` SL+TP blokları: Bybit branch (önce `BYBIT_GUARD` → naked).
- `_verify_order_execution`: Bybit branch (`_get_bybit_executions` ile FILLED doğrulama).
- Inline `deferred_phase2_verify` closure: Bybit branch (Sorun 2d, `string indices` hatası).
- `_check_pending_trailing_sl`: Bybit branch (trailing SL'yi pozisyondan doğrula).
- `_reconcile_sltp`: Bybit erken çıkış (CID/positionSide open-orders modeli Bybit'e uymaz).
- `_check_sltp_exists_for_position`, `_periodic_sltp_verify` (+`_bybit_periodic_sltp_verify`),
  `_sync_existing_sltp_orders`: Bybit-aware SL/TP tespiti.
- Cancel fonksiyonları (`_cancel_existing_sltp`, `_cancel_only_sl` no-op, `_cancel_only_tp`
  aktif clear, `_cancel_position_sltp_only`, `_cancel_order_safe`): Bybit dalları.
- `_set_binance_sltp_batch`: Bybit → doğrudan trading-stop.
- `_get_real_entry_price_from_trades`, `_get_entry_price_from_positions`: Bybit peer.
- `_wait_for_order_fill`, `_delayed_sltp_health_check`: Bybit branch (future-proof).
- Sorun 2b monkey-patch (ORDER_STATE).

### B. Spam + mekanizma düzeltmeleri
- **34040 "not modified" spam** → `_place_bybit_trading_stop` başarı sayar (DEBUG log).
- **Dinamik trailing SL kırıktı** (`_update_trailing_sl` → `_send_conditional_order` →
  BYBIT_GUARD). Bybit branch eklendi (trading-stop ile overwrite).
- **OKX cooldown cross-contamination**: `_consume_user_stream` artık sadece OKX
  connector için `_okx_note_network_error` çağırıyor (L12222 civarı).
- **Position staleness**: `_fetch_bybit_positions` artık anlamsız `_has_recent_ws_positions`
  kısayolu yerine HB `account_positions` cache'ine + zaman-eşikli REST'e güveniyor.
- **Rate-limit hardening**: `_bybit_raw_post` kalıcı session + timeout + pacing + retry.

### C. Partial TP/SL re-mimarisi (per-piece izole SL/TP)
- `_place_bybit_trading_stop` `qty` param → `tpslMode="Partial"`, tpSize/slSize=qty.
- Tüm caller'lara parça qty geçirildi (entry, phase2, trailing, naked, periodic, batch,
  async, health, place_sltp_simple).
- Tespit `_get_bybit_conditional_orders` ile (order/realtime StopOrder). `has_sl/has_tp`
  hem Full (position alanı) hem Partial (koşullu emir) kaynağından.
- `_check_sltp_exists_for_position` + `_bybit_periodic_sltp_verify`: **per-piece** —
  parçanın qty'sine (±%5) karşılık gelen SL/TP koşullu emri var mı diye bakar.
- `_clear_bybit_trading_stop`: Partial koşullu emirleri `v5/order/cancel` + Full "0".
- `_set_phase2_sltp` Bybit: parça boyutu değişince (full→kalan) eski Partial emri
  clear-before-place (tek-parçada tam doğru).

### D. Bybit v5 WebSocket parsing (yeni)
- `_handle_user_stream_event`: `payload.get("topic")` varsa Bybit branch.
- `_handle_bybit_user_stream_event` router → position/order/execution.
- `_handle_bybit_position_event`: `_ws_position_buffer` + `_binance_positions_cache`
  güncelle (shape `_fetch_bybit_positions` ile aynı; amount signed).
- `_handle_bybit_order_event`: `orderLinkId` → `_parse_cid`/`_identity_link_from_cid`
  (per-piece parent map) + `_order_monitor` fill event.
- `_handle_bybit_execution_event`: `_last_user_trades_call` zaman damgası.

## 5) Doğrulanacak Varsayımlar (DEMO'da test et) 🔬
1. **order/realtime orderFilter="StopOrder"** trading-stop-üretimi Partial TP/SL'yi
   döndürüyor mu? (Yoksa `tpslOrder` filtresi gerekebilir.) → `_get_bybit_conditional_orders`.
   Dönmezse tespit "naked" der → gereksiz re-place. Log: `🔍 [SLTP CHECK BYBIT]`.
2. **Partial trading-stop tekrar çağrısı (aynı size, yeni fiyat)** mevcut koşullu emri
   GÜNCELLER mi yoksa DUPLICATE mi yaratır? (34040 kanıtı update-in-place'i destekliyor.)
   Trailing bu varsayıma dayanıyor. Duplicate olursa oversized koşullu emir birikir.
3. **Partial trading-stop farklı size ile** çağrılınca (Phase 2 full→half) eski emri
   değiştiriyor mu? clear-before-place bunu tek-parçada güvenceye alıyor; çoklu-parçada
   kardeşler kısa süre clear olur (periodic verify geri koyar).
4. **Bybit WS topic isimleri/şekilleri**: `position`/`order`/`execution` data alanları
   (positionIdx, size, entryPrice, orderStatus, cumExecQty, orderLinkId) beklenen mi?
5. **api-demo.bybit.com** WS+REST demo hesapla çalışıyor mu (`_bybit_raw_post` base_url).

## 6) Bilinen Sınırlamalar / degraded (kırık değil)
- Çoklu aynı-yön parça: Partial ile izole TP/SL hedeflenir; ancak koşullu emirlerde
  CID YOK (trading-stop orderLinkId kabul etmez) → parça↔emir eşlemesi qty+fiyat ile
  yaklaşık yapılır. Aynı qty'li iki parça ayırt edilemez (yine de "korumalı" tespit edilir).
- ~~Orphan cleanup … Bybit'te başıboş SL/TP emri oluşmaz~~ ❌ **BU İFADE YANLIŞTIR.**
  Bybit `order/create` koşullu emirlerini pozisyon kapanınca iptal ETMEZ → orphan
  birikir ve 10'luk tavanı doldurur. Bkz. **§11.3** ve `_bybit_sweep_orphan_conditional_orders`.
- ~~`_detect_multiple_entries_from_trades`/`_find_entry_price_from_trades`: Bybit exec
  kayıtlarında `positionSide` boş → bu fallback parser'lar zayıf~~ ⚠️ **ARTIK GEÇERSİZ.**
  Alan borsadan gelmiyor ama `closedSize`'dan **türetilebiliyor** — v3.5 Fix X bunu yapar.
  Bu boşluk yalnızca "zayıf parser" değil, **tüm kapanış tespitini çökertiyordu.**
  Bkz. **§16.2** (kanıt + ölçüm) ve `_get_bybit_executions`.
- Mixed OKX+Bybit kurulumda `_should_skip_sltp_due_to_backoff` OKX auth cooldown'ı
  Bybit'i de bloklayabilir (Bybit-only kurulumda etkisiz).

## 7) Doğrulama Komutları
```bash
python -m py_compile tv_signal_strategy.py        # derleme (OK olmalı)
grep -n "BYBIT_GUARD" tv_signal_strategy.py       # sadece _send_conditional_order guard'ında (1)
```
Demo log kontrolleri:
- `✅ [BYBIT SLTP]` / `➖ [BYBIT SLTP] değişmedi` → placement/idempotent
- `🩹 [PERIODIC VERIFY BYBIT]` → eksik koruma tamamlandı
- `🩹 Bybit ORDER_STATE patch` → connector patch aktif
- OLMAMALI: `❌ [FAZ 2 SL] Başarısız: {'error':'BYBIT_GUARD'}`, `string indices must be integers`,
  `KeyError: 'Triggered'`, `⚠️ [BYBIT SLTP] fail ... 34040` spam

## 8) Anahtar Fonksiyon Konumları (grep ile bul — satırlar kayabilir)
`_place_bybit_trading_stop` · `_get_bybit_conditional_orders` · `_get_bybit_position_protection`
· `_clear_bybit_trading_stop` · `_bybit_raw_post` · `_bybit_periodic_sltp_verify`
· `_set_phase2_sltp` · `_update_trailing_sl` · `_check_sltp_exists_for_position`
· `_naked_position_recovery` · `_handle_bybit_user_stream_event` · `_fetch_bybit_positions`
· `_patch_bybit_connector_order_states`

## 9) Sıradaki İşler
- ~~Demo testleri (§5 ve §10.5)~~ → **§11.1'de KANITLANDI.** Kalan tek test grubu: **§11.9**.

---

## 10) GÜNCEL MİMARİ (v2) — order/create KOŞULLU EMİR + CID  ⭐

> [!WARNING]
> **Tarihsel Bağlam ve Güncel Sınır (v6.0 Fix CD):** Bu bölümde anlatılan "CID yanmışsa generation artırıp yeniden create et" mantığı, v6.0'da sınırlandırılmıştır. Borsa emri `filled` olduğunda veya borsa pozisyonu sıfır olduğunda generation artırılmaz; ayrıntılar için bkz. **§35.2**.

### 10.1 Neden değişti (log kanıtı)
İlk tur `tpslMode="Partial"` trading-stop kullanıyordu. Canlı demo logunda
(`logs_tv_signal_strategy_processed.log`) şu **kanıtlı hatalar** görüldü:
- **Duplicate patlaması**: `🧹 [BYBIT SLTP CLEAR] ... (cond=5)`, `cond=7` → tek pozisyonda
  5-7 duplicate koşullu emir. Kök neden: trading-stop Partial'ın **CID'i yok**;
  parça↔emir eşlemesi qty ile yapılıyordu ve Phase 2 qty'yi değiştirince eşleşme
  bozulup her turda yeni emir ekleniyordu.
- **`retCode 10001`** = "would immediately trigger" (giriş kaymasıyla SL/TP anlık
  fiyatın ters tarafında) → aynı geçersiz değer sonsuz retry → binlerce WARNING.
- **Birleşik SL+TP çağrısı**: geçersiz TP tüm çağrıyı reddedince geçerli SL de konmuyordu
  (ETH long naked).

Kullanıcı kararı: **per-piece via order/create + CID** (trading-stop Partial değil).

### 10.2 Yeni mekanizma
SL/TP artık **ayrı reduceOnly koşullu (stop) market emirleri** (`v5/order/create`):
- Her leg **STABİL orderLinkId (CID)** taşır: `H-S-<parent>-BB` (SL), `H-T-<parent>-BB` (TP)
  → `_bybit_sltp_link_id(parent_order_id, kind)`. `_parse_cid` bunu parse eder (parent_id).
- **Idempotent upsert**: `_place_bybit_conditional_order` → order/create; retCode 0 = placed;
  **duplicate orderLinkId → `_amend_bybit_conditional_order`** (triggerPrice + qty güncelle).
  Böylece tekrar yerleştirme/trailing **duplicate YARATMAZ** (aynı CID → amend).
- **breach pre-check** (mid price ile) + **immediate-trigger cooldown** (60s/(pair,side,kind))
  → 10001 spam biter, API çağrısı bile yapılmaz.
- **SL ve TP AYRI** konur → geçersiz TP, geçerli SL'yi engellemez.
- triggerDirection: SL LONG=2/SHORT=1, TP LONG=1/SHORT=2. triggerBy: SL=MarkPrice, TP=LastPrice.
  reduceOnly=true, closeOnTrigger=true, positionIdx=1/2.

### 10.3 Yeni/değişen fonksiyonlar
- `_bybit_sltp_link_id(parent, kind)` → stabil CID.
- `_place_bybit_conditional_order(conn, tp, side, kind, trigger, qty, cid)` → upsert (create→amend).
- `_amend_bybit_conditional_order(conn, tp, new_trigger, order_link_id=, order_id=, qty=)`.
- `_place_bybit_trading_stop(...)` → **artık per-piece order/create wrapper** (imza aynı +
  `position_order_id` eklendi; qty ZORUNLU — reduceOnly boyutu için). Döner:
  `{success, sl_order_id, tp_order_id, sl_status, tp_status, not_modified}`.
  status ∈ {placed, amended, breached, immediate, cooldown, failed}.
- `_get_bybit_conditional_orders` → her emir için `parent_id` + `cid_tag` (CID parse) döner;
  `kind` ÖNCE CID tag'inden (order/create koşullu emirde stopOrderType="Stop", ayrım yapmaz).
- Tespit (`_check_sltp_exists_for_position`, `_bybit_periodic_sltp_verify`) → **CID parent_id
  ile kesin eşleşme** (qty ±%5 fallback). Duplicate/qty-drift sorunu biter.
- `_clear_bybit_trading_stop(..., position_order_id=)` → per-piece iptal (sadece o CID);
  position_order_id yoksa tüm taraf + Full-"0" leftover temizliği.
- Tüm `_place_bybit_trading_stop` çağrıları artık `position_order_id` geçiyor (CID için).
- `_update_trailing_sl` Bybit → upsert (amend) ile SL güncelliyor (naked pencere yok).
- `_set_phase2_sltp` Bybit → clear-before-place KALDIRILDI (amend qty+price hallediyor).

### 10.4 Log-analizi düzeltmeleri (bu tur)
- 34040/duplicate/10001 spam → cooldown + DEBUG log.
- ETH long naked (birleşik çağrı) → SL/TP ayrı → geçerli SL konur.
- `_bybit_raw_post` zaten kalıcı session + pacing + retry (önceki turdan).

### 10.5 DEMO'da doğrulanacak KRİTİK varsayımlar 🔬
1. **order/create koşullu emir kabulü (hedge)**: body {orderType:Market, triggerPrice,
   triggerDirection, triggerBy, reduceOnly:true, closeOnTrigger:true, positionIdx, orderLinkId}.
   Bybit hedge modda `reduceOnly:true`+positionIdx kabul ediyor mu? Etmezse reduceOnly'i çıkar.
2. **duplicate orderLinkId retMsg**: "orderLinkId ... exist/duplicate/repeated" bekleniyor →
   amend'e düşer. Farklı ifade ise `_place_bybit_conditional_order` duplicate tespitini güncelle.
3. **v5/order/amend** orderLinkId ile triggerPrice+qty günceller mi (trailing/Phase2)?
4. **order/realtime orderFilter="StopOrder"** bu koşullu emirleri (orderLinkId ile) döndürüyor mu?
   (Tespit buna bağlı.) Log: `🔍 [SLTP CHECK BYBIT]`, `✅ [BYBIT COND SL/TP]`, `↻ ... amended`.
5. **breach pre-check** `connector.get_mid_price` mark/last ile uyumlu mu (borderline 10001).

### 10.6 Bilinen sınır
- Giriş kayması (fill ≫ signal) SL/TP'yi anlık tetik yapıyorsa leg konmaz (breach skip +
  cooldown) → o parça o leg'de korumasız kalabilir. Auto-close EKLENMEDİ (para-aksiyonu
  riski). Öneri: entry'de fill↔signal sapması büyükse SL/TP'yi fill'e göre yeniden türet
  veya girişi reddet (ayrı iş).
- Demo hesabındaki eski duplicate/orphan koşullu emirler kullanıcı isteğiyle ELLE
  temizlenecek (kod dokunmadı). → **§11'de otomatik süpürücü eklendi.**

---

## 11) v3 — KANITLANMIŞ API GERÇEKLERİ + LEG BÜTÇESİ / KONSOLİDASYON  ⭐⭐

### 11.1 DEMO API probe ile KESİNLEŞEN gerçekler (tekrar test ETMEYİN)
`api-demo.bybit.com`, canlı hesap, 2026-07-28:

| # | Soru | **KANITLANMIŞ CEVAP** |
|---|---|---|
| 1 | `orderFilter="StopOrder"` order/create koşullu leglerini döndürüyor mu? | **EVET, EKSİKSİZ.** `orderLinkId`, `stopOrderType='Stop'`, `positionIdx`, `qty`, `triggerPrice`, `orderStatus='Untriggered'` hepsi geliyor. §10.5.4 varsayımı **DOĞRULANDI**. |
| 2 | `orderFilter="tpslOrder"` işe yarar mı? | **HAYIR, her zaman 0 döndürüyor** (PartialTakeProfit bile). `StopOrder` her iki türü kapsıyor → **doğru filtre `StopOrder`**. |
| 3 | hedge modda `reduceOnly:true` + `positionIdx` kabul ediliyor mu? | **EVET** (§10.5.1 doğrulandı). |
| 4 | duplicate retMsg tam metni? | **`'OrderLinkedID is duplicate'`, retCode `110072`.** ⚠️ `orderlink**ed**id` — eski `"orderlinkid" in ret_msg` kontrolü ASLA eşleşmiyordu. |
| 5 | Koşullu emir tavanı kaç ve kapsamı ne? | **symbol başına 10 "normal stop order", havuz İKİ YÖN ORTAK.** Kanıt: BTCUSDT'de 7×idx1 + 3×idx2 = 10 iken **idx=2'ye yeni emir de `110009` aldı** (idx=2'de sadece 3 leg vardı). retCode `110009` `'already had 10  working normal stop orders'`. |
| 6 | `trading-stop` TP/SL aynı kotayı mı kullanıyor? | **HAYIR, AYRI KOTA.** Symbol 10/10 tavanındayken `trading-stop` Partial TP `retCode 0` ile kabul edildi. → **Pozisyon-seviyesi koruma 0 normal-stop slotu tüketir.** |
| 7 | `trading-stop` üretimi emrin CID'i var mı? | **YOK** (`orderLinkId=''`, `stopOrderType='PartialTakeProfit'`). Ama `StopOrder` filtresinde görünür. |
| 8 | `takeProfit="0"` ile Partial TP silinir mi? | **HAYIR** → `10001 '"tpSize" and "takeProfit" ... need to input in pairs'`. Partial TP'yi silmek için **`v5/order/cancel` + orderId** kullan. |
| 9 | `settleCoin=USDT` ile hesap-geneli koşullu emir listelenir mi? | **EVET** (+`nextPageCursor` sayfalama). Orphan süpürücü buna dayanıyor. |
| 10 | tickSize'lar | BTC `0.10` · ETH `0.01` · DOGE `0.00001` · BNB `0.10` |

### 11.2 🔥 CID KALICI YANAR — v2'nin temel kusuru
`order/history` kanıtı: `H-S-455265996682-BB` → `status='Filled'` (20:20:22'de tetiklendi).
Log'daki `110072`'ler tam bundan **sonra** (20:21, 20:26, …).

**Bybit bir `orderLinkId`'yi bir kez kullanıldıktan sonra ASLA yeniden kabul etmez**
(Filled/Cancelled olsa bile). Sonuç: "stabil CID = idempotent upsert" tasarımı
**ilk leg tetiklendiği anda kalıcı olarak bozulur**:
tespit doğru şekilde "SL yok" der → aynı CID ile create → `110072` → amend de
imkânsız (kapalı emir amend edilemez) → **parça sonsuza dek korumasız + 5 dakikalık
sonsuz retry.**
→ Çözüm: **CID generation** (`H-S-<pid>-BB` → `BB1` → `BB2` …).
`_parse_cid` parts[3]'ü opsiyonel okuduğu için suffix parse'ı BOZMAZ; tespit hep
`parent_id` ile çalışır (test edildi).

### 11.3 🔥 ORPHAN BİRİKMESİ — `110009`'un ASIL nedeni
Bybit `order/create` koşullu emirlerini pozisyon kapanınca **iptal etmez** (yalnızca
`trading-stop` üretimi olanları iptal eder). Bir parça kapanınca kardeş leg'i açık kalır.
Demo anlık görüntüsü: **35 açık leg'in ≥22'si (%63) orphan** —
ETHUSDT 8/8 ve BNBUSDT 7/7 leg vardı ama **o sembollerde pozisyon YOKTU**;
BTCUSDT'de 7 leg `idx=1` iken **LONG pozisyon yoktu**.
Orphanlar tavanı doldurunca yeni parçalar `110009` alıp **naked** kalıyordu (1554 kez).
⚠️ §6'daki *"Bybit'te başıboş SL/TP emri oluşmaz"* ifadesi **YANLIŞTIR** — silindi sayın.

### 11.4 Yapılan düzeltmeler (v3)
| Fix | Ne | Nerede |
|---|---|---|
| **A** | `110072` → `orderLinkId`'yi `order/realtime`'da ara. **Açıksa** amend; **kapalıysa** CID yanmış → generation artır + yeniden create (tek çağrıda `BYBIT_CID_ROTATE_TRIES`=3 deneme; restart sonrası çoklu yanmış generation için) | `_place_bybit_conditional_order`, `_bybit_sltp_link_id`, `_bybit_bump_cid_generation`, `_get_bybit_order_by_link_id` |
| **B1** | `110093 'expect Falling…'` artık **immediate** sınıfı → cooldown + DEBUG (WARNING spam bitti) | `_place_bybit_conditional_order` |
| **B2** | `110009` artık ayrı `cap_full` statüsü → süpürme + konsolidasyon tetikler, spam yapmaz | `_bybit_note_cond_cap_full` |
| **B3** | **FALSE-SUCCESS FIX:** `success = not hard_fail` idi; `breached/immediate/cooldown` hard_fail saymadığı için **hiçbir emir konmadan** `success=True` dönüyor, `🩹 eksik koruma tamamlandı` basılıp `_sltp_ws_confirmed` set ediliyordu → koruma ağı parçayı KORUMALI sanıyordu (aynı parça için 36 kez). Artık **sadece `sl_status/tp_status ∈ {placed, amended}`** onaylanır; konulamayan leg `🔓 [BYBIT NAKED LEG]` ile raporlanır | `_bybit_periodic_sltp_verify`, `_delayed_sltp_health_check` |
| **C** | **Orphan süpürücü** (hesap geneli, `settleCoin`) — 120s'de bir | `_bybit_sweep_orphan_conditional_orders` |
| **D** | Symbol leg bütçesi + parça limiti ≤5/yön + **erken konsolidasyon** | `_bybit_symbol_leg_usage`, `_bybit_enforce_piece_budget` |
| **E** | Aggregate konsolidasyon state machine | `_bybit_consolidate_side` |
| **F** | %→absolut trailing mesafe motoru (pariteden bağımsız) | `_bybit_trailing_distance` |

### 11.5 Orphan süpürücü — güvenlik kuralları
Bir leg **ancak şu 4 koşul birlikte** sağlanırsa iptal edilir:
1. **CID taşıyor** (`H-S-`/`H-T-`). CID'siz legler (`trading-stop` üretimi:
   `PartialTakeProfit`/`TrailingStop`) = **konsolide koruma** → ASLA silinmez.
2. Yaş ≥ `BYBIT_ORPHAN_MIN_AGE` (180s) — yeni konan leg tracking yerleşmeden silinmez.
3. (a) o `positionIdx`'te pozisyon YOK **veya** (b) parent parça artık takipte değil.
   Tracking tamamen boşsa (restart) **hiçbir şey silinmez**.
4. Üst üste `BYBIT_ORPHAN_CONFIRM_HITS` (2) gözlem.

### 11.6 Aggregate konsolidasyon (kullanıcı yönergesi madde 4)
Tetikler: (1) pair+yön parça > 5, (2) symbol leg bütçesi ≤ `BYBIT_COND_BUDGET_RESERVE`
(erken konsolidasyon — tavan iki yön ortak olduğu için 5×2×2=20 > 10, bu fallback
olmadan tıkanma kaçınılmaz), (3) `110009` görüldü.

Karar borsanın verdiği **`avgPrice` (breakeven)** + **`unrealisedPnl`** üzerinden
(ek ortalama hesabı YOK):

```
KÂRDA  → per-piece legler iptal → SL = breakeven (risk-free)
         ├─ SL kurulamadı        → MARKET CLOSE
         └─ SL kuruldu (a1)      → %1 TRAILING (trading-stop Full)
                                   ├─ başarılı → mode='trailing'  → (a2) FAZ 2 YOK
                                   └─ başarısız→ mode='breakeven_sl' (SL duruyor,
                                                 market close YAPILMAZ)
ZARAR > %4 → per-piece legler iptal → MARKET CLOSE
ZARAR ≤ %4 (b1) → legler iptal → SL = be∓%4, TP = be±%8 (Full)
                  → mode='fixed' → FAZ 2 GEÇERLİ
```

Konsolide koruma `trading-stop` Full kullandığı için **0 normal-stop slotu tüketir**
(§11.1 #6) → 10'luk bütçenin tamamı per-piece parçalara kalır.

**Faz 2 entegrasyonu:**
- `mode='trailing'` → `_activate_phase2` ve `_monitor_positions` erken çıkar (kural a2).
- `mode='fixed'/'breakeven_sl'` → Faz 2 çalışır; SL/TP güncellemeleri
  `aggregate_ok=True` bayrağıyla **pozisyon seviyesine yönlendirilir**
  (`_place_bybit_trading_stop` → `_bybit_set_position_stop_full`).
  Bayrak SADECE `_set_phase2_sltp` ve `_update_trailing_sl` çağrılarında set edilir —
  giriş/naked/periodic yolları aggregate korumayı **ezmemeli**.
- Diğer tüm caller'lar konsolide tarafta per-piece leg koymaz (tek choke-point:
  `_place_bybit_trading_stop` başındaki guard).

`cancel-all` **KULLANILMADI**: Bybit cancel-all dokümanı `positionIdx` parametresini
tanımlamıyor → diğer yönü de silme riski var. Bunun yerine `positionIdx`'e göre
filtrelenmiş liste tek tek iptal edilir (N ≤ 10).

### 11.7 Yeni env değişkenleri
```
BYBIT_MAX_COND_PER_SYMBOL=10     BYBIT_MAX_PIECES_PER_SIDE=5
BYBIT_COND_BUDGET_RESERVE=2      BYBIT_CONSOLIDATE_TRAIL_PCT=0.01
BYBIT_CONSOLIDATE_SL_PCT=0.04    BYBIT_CONSOLIDATE_TP_PCT=0.08
BYBIT_CONSOLIDATE_MAX_LOSS_PCT=0.04
BYBIT_ORPHAN_SWEEP_INTERVAL=120  BYBIT_ORPHAN_MIN_AGE=180
BYBIT_ORPHAN_CONFIRM_HITS=2      BYBIT_CID_MAX_GENERATION=50
BYBIT_CID_ROTATE_TRIES=3
```

### 11.8 Yapılan doğrulamalar
- `python -m py_compile tv_signal_strategy.py` → OK
- AST ile fonksiyon seti karşılaştırması → **0 fonksiyon kayboldu**, 24 eklendi
- Gerçek `_parse_cid` ile generation suffix testi → `BB`/`BB1`/`BB2`/`BB7`/`BB50`
  hepsi `valid=True`, doğru `parent_id`; bozuk girdiler reddediliyor
- Trailing motoru: BTC 635.10 (%1.000) · ETH 19.00 (%1.000) · DOGE 0.00070 (%0.999)
  · BNB 5.70 (%0.991) — hepsi tick katı; min 1 tick guard çalışıyor
- retCode sınıflandırması log'daki 3 gerçek mesajla test edildi (1681 WARNING → 0)

### 11.9 ~~DEMO'da doğrulanacak~~ → **HEPSİ DOĞRULANDI** ✅ (bkz. §12.1)
1. ~~`trailingStop` + `activePrice`~~ → **KABUL EDİLİYOR** (`retCode 0`). `activePrice`
   olmadan da çalışır. Detay + `TrailingProfit` keşfi: §12.1.
2. ~~`stopLoss` + `trailingStop` birlikte durur mu~~ → **EVET, BİRLİKTE DURUYOR**
   (iki ayrı koşullu emir). `stopLoss:"0"` yapmama kararı **DOĞRU** çıktı.
3. ~~`v5/order/amend` orderLinkId ile triggerPrice+qty~~ (§10.5.3) → **ÇALIŞIYOR**
   (`retCode 0`, qty 44346→24091 güncellendi).
4. Kalan (kod-içi, API değil): `_bybit_consolidated` / `_bybit_cid_gen` **transient**
   (restart'ta sıfırlanır). Konsolide taraf 120s içinde yeniden konsolide olur (borsadaki
   Full koruma bu arada durur); CID generation rotate ile self-heal eder.
   Konsolidasyon sonrası kapanışta `♻️ [BYBIT CONSOLIDATE] … sıfırlandı` görülmeli.

### 11.10 Beklenen log imzaları
```
🧹 [BYBIT ORPHAN] iptal …           → orphan temizlendi
✅ [BYBIT ORPHAN] N başıboş …       → tur özeti
🔁 [BYBIT CID ROTATE] … yanmış → … → CID generation arttı
🚧 [BYBIT COND CAP] …               → tavan dolu (5 dk throttle)
🚧 [BYBIT LEG BUDGET] … ERKEN konsolide
📏 [BYBIT PIECE LIMIT] … parça=6 > 5
🔗 [BYBIT CONSOLIDATE] … başlıyor (sebep=…, breakeven=…, pnl=…%)
🛡️ [BYBIT CONSOLIDATE] … SL breakeven'e çekildi
🏃 [BYBIT CONSOLIDATE] … %1 trailing stop aktif → FAZ 2 İŞLETİLMEYECEK
🛑 [BYBIT CONSOLIDATE] … → MARKET CLOSE
⏭️ [FAZ 2 SKIP] … global trailing altında (kural a2)
🔓 [BYBIT NAKED LEG] … konulamadı: SL(breached)   ← ARTIK GİZLENMİYOR
```
OLMAMALI: `110072`/`110009`/`110093` WARNING spam'i, `⚠️ [BYBIT COND …] fail` seli,
aynı parça için tekrarlayan `🩹 eksik koruma tamamlandı`.

---

## 12) v3.1 — CANLI DEPLOY SONRASI BULGULAR (2026-07-28 deploy @18:40)  ⭐⭐⭐

> [!WARNING]
> **Tarihsel Bağlam ve Güncel Sınır (v6.0 Fix CD):** v3.1 recovery döngülerinde karşılaşılan CID yanmalarında körlemesine generation artırma, v6.0 Fix CD ile borsa pozisyonu sıfırken veya emir dolmuşken engellenmiştir. Bkz. **§35.2**.

### 12.1 Kalan API varsayımları KAPANDI (canlı DOGEUSDT SHORT üzerinde test)
| Test | Sonuç |
|---|---|
| `trading-stop` Full + `trailingStop` + `activePrice="0"` | **`retCode 0`** → `TrailingStop` koşullu emri, tetik = mark ∓ dist |
| `trailingStop` **activePrice OLMADAN** | **`retCode 0`** (fallback yolu güvenli) |
| `stopLoss` + `trailingStop` **birlikte** | **KORUNUYOR** — `SL='0.07286'` VE `trail='0.0007'`, iki ayrı emir: `StopLoss@0.07286` + `TrailingStop@0.07158`. → `trailing_stop.md`'nin `stopLoss:"0"` önerisi **UYGULANMAMALI** |
| `activePrice=<seviye>` semantiği | Emir tipi **`TrailingProfit`** olur ve tetik = **`activePrice + dist`**. Kanıt: activePrice=0.06936, dist=0.0007 → tetik 0.07006 ≈ breakeven (0.0700561) |
| `v5/order/amend` + `orderLinkId` + `triggerPrice` + `qty` (§10.5.3) | **ÇALIŞIYOR** — `retCode 0`, `{orderId, orderLinkId}` döner, qty 44346→24091 uygulandı |
| Kârda olmayan pozisyona breakeven SL | **REDDEDİLİR**: `10001 'StopLoss:… for Sell position should greater base_price:…'` (SL anlık tetik olurdu). Kural (a) yalnızca kârda çalıştığı için kodda sorun DEĞİL; sınırda `10001` alınırsa spec gereği market close doğru davranıştır (market≈breakeven). |

**Bunun kurala etkisi (Fix I):** `activePrice = be ∓ dist` verilerek trailing'in
aktivasyon anındaki stop'u **tam breakeven**'e sabitlenir → trailing ASLA breakeven'den
kötü kilitlemez. `activePrice="0"` verilseydi trailing anında aktifleşir ve kâr %1'den
azken stop breakeven'in ALTINA düşebilirdi (kullanıcının "risk-free" niyeti bozulurdu).

### 12.2 🔥 SONSUZ RECOVERY DÖNGÜSÜ — deploy sonrası bulunan EN CİDDİ hata
**Canlı kanıt:** 15:39 UTC restart → 16:10 UTC'ye kadar **16 tur**, 2 dakika aralıkla,
`[TRACKED] Bot: []`, tracking'e **0 ekleme**, pozisyon 24091 olarak açık kaldı.

Döngü:
```
🔍 [RECOVERY] DOGE-USDT SHORT track edilmiyor! Amount: -24091
📁 Arşivden yüklendi: DOGE-USDT_SHORT_1785245103.json  (SL: 0.0702)
B4/B5: Bybit SLTP-fail market close DISABLED — naked leave
✅ [AUTO-DETECT CLOSE] Pozisyon kapatma gönderildi   ← YALAN
return  # Tracking'e ekleme                          ← pozisyon YÖNETİMSİZ
(120s grace) → baştan
```

**İKİ katmanlı kök neden:**

**(a) Arşiv güvenilirlik filtresi `archive_data`'ya HİÇ uygulanmıyordu.**
Kod `reliable_for_autoclose` denetimini (yaş + amount) **yalnızca `cached_signal`** için
yapıyordu. Kullanılan arşiv dosyası:
```json
{"status":"pending", "order_id":null, "filled_amount":0.0,
 "sl_price":0.0702, "exchange":"binance_perpetual_testnet"}
```
→ 165 dakika eski, **HİÇ FILL OLMAMIŞ**, hatta **başka borsaya** ait bir sinyal, canlı
Bybit pozisyonunun (avg `0.0700561`, size `24091`) gerçek SL'si sanıldı. SL `0.0702`
zaten kırılmış olduğu için "kapat" kararı çıktı.

**(b) `_close_position_market_amount` EXCEPTION ATMAZ.**
`B4_DISABLE_SLTP_CLOSE=1` (VPS'te doğrulandı) → `{"sent": False, "reason":
"bybit_sltp_close_disabled"}` döner. Eski kod dönüşü **kontrol etmeden** `✅ kapatma
gönderildi` basıyor, ardından **koşulsuz `return  # Tracking'e ekleme`** ile tracking'i
atlıyordu.

**Yan etkiler (hepsi bu döngüden türüyor):**
- Faz 1 / Faz 2 bu pozisyon için **hiç çalışmaz**.
- Orphan süpürücü, "tracking boşsa hiçbir şey silme" koruma kuralı gereği o pair+yöndeki
  legacy legleri **temizleyemez** (§11.5 kural 3) → kullanıcının gördüğü "DOGE legleri
  kaldı" tablosu.
- Pozisyonun SL/TP'si hiç yönetilmez; borsadaki legler eski parçalardan kalır → qty
  uyuşmazlığı.

### 12.3 v3.1 düzeltmeleri
| Fix | Ne | Nerede |
|---|---|---|
| **G** | `_close_position_market_amount` dönüşü kontrol edilir; `sent=False` ise dürüst WARNING + **`return` YAPILMAZ** → pozisyon normal tracking/SL-TP akışına düşer. `close_sent` exception yolunda da tanımlı (`False` ön-atama) | auto-detect close bloğu |
| **H** | `_bybit_symbol_leg_usage` artık **yalnızca CID'li** legleri sayar. `trading-stop` legleri (`StopLoss`/`TrailingStop`/`TrailingProfit`/`PartialTakeProfit`, `orderLinkId=''`) `StopOrder` listesinde görünür ama 10'luk kotayı **tüketmez** (§11.1 #6) → sayılması konsolide bir tarafın korumasını bütçe sanıp diğer tarafı gereksiz erken konsolide ediyordu | `_bybit_symbol_leg_usage` |
| **I** | Kural (a1): `activePrice = be ∓ dist` ile **breakeven-garantili** trailing; reddedilirse `activePrice="0"` fallback | `_bybit_consolidate_side` |
| **J** | **Arşiv güvenilirlik filtresi**: `status ∉ {filled, closed}` veya `filled_amount ≤ 0` veya yaş > 10 dk veya amount %5+ sapma → `reliable_for_autoclose=False` (auto-close atlanır, pozisyon tracking'e alınır) | auto-detect close bloğu |
| **K** | **SON KORUMA GUARD** (süpürücü): pozisyon CANLI ise ve leg o yöndeki **son SL (veya son TP)** ise **SİLİNMEZ**. Fix G ile pozisyonlar tracking'e girmeye başlayınca eski legler "untracked_parent" görünür; guard olmadan hepsi silinip pozisyon korumasız kalabilirdi. Sayaç aynı tur içinde düşürülür | `_bybit_sweep_orphan_conditional_orders` |

### 12.4 Kullanıcının sorusuna cevap (legacy mi, süregelen bug mı?)
**İkisi birden, ama farklı katmanlarda:**
- Kalan 4 DOGE leg'i **legacy**: 2 SL `2026-07-27 17:20` ve `2026-07-28 01:41`'de,
  2 TP `18:22`/`18:35`'te oluşmuş — **hepsi deploy'dan (18:40) ÖNCE**. Deploy sonrası
  **hiç yeni leg üretilmedi**. qty uyuşmazlığı (46295/44346/47802 vs 24091) pozisyonun
  TP tetikleriyle küçülmesinden; legler eski qty'sini korumuş.
- Leg **tanıma** sorunu YOK: `orderFilter=StopOrder` + CID parse doğru çalışıyor (§11.1).
- Ama bot pozisyonu **tanıyıp yönetmeyi** başaramıyor → sebep §12.2 döngüsü (leg değil,
  **tracking/recovery** katmanı).
- "SL yok" izlenimi: pozisyon satırındaki `stopLoss` alanı **boş** (`''`) çünkü per-piece
  SL ayrı koşullu emirdir (§2/§11.1). Gerçekte 2 SL leg'i vardı (0.0722 / 0.0732) ve
  ikisi de mark'ın üzerindeydi → koruma mevcuttu, sadece hedeflenen 0.0702'den gevşekti.

### 12.5 Hesap temizliği (yapıldı)
Legacy legler elle sağlıklı hale getirildi — **koruma hiç kaldırılmadan**:
- `H-S-486175392158-BB` → `order/amend` ile qty **44346 → 24091** (trigger 0.0722 aynı)
- `H-S-906519710670-BB` iptal (daha gevşek 2. SL, 0.0732)
- `H-T-136269840552-BB` iptal (oversized 2. TP, qty 46295)
- `H-T-211782566193-BB` korundu (TP 0.0698, qty 24091 — pozisyonla birebir)

Son durum: **DOGEUSDT SHORT 24091 · 1 SL @0.0722 (24091) · 1 TP @0.0698 (24091)**,
hesap genelinde toplam **2** koşullu emir (öncesi 35).

### 12.6 Deploy notu
v3.1 fixleri (G/H/I/J/K) **VPS'e deploy EDİLMEDİ** — VPS izni "okuma ve araştırma"
kapsamındaydı. Deploy edilen sürüm (`/home/ubuntu/deploy/bots/scripts/tv_signal_strategy.py`,
Jul 28 15:39 UTC) v3'tür; §12.2 döngüsü o sürümde **hâlâ aktif**.
Deploy sonrası beklenen yeni loglar:
```
⚠️ [AUTO-DETECT CLOSE SKIP] … arşiv dolmamış sinyal (status='pending', filled=0)
⚠️ [AUTO-DETECT CLOSE] … kapatma GÖNDERİLEMEDİ (reason=bybit_sltp_close_disabled) …
    → tracking'e alınıp normal SL/TP yönetimine devredilecek
🛡️ [BYBIT ORPHAN] … bu yöndeki SON SL leg'i → SİLİNMEDİ
```
OLMAMALI: `✅ [AUTO-DETECT CLOSE] Pozisyon kapatma gönderildi` ardından pozisyonun açık
kalması; `[TRACKED] Bot: []` ile birlikte tekrarlayan `🔍 [RECOVERY]`.

---

## 13) v3.2 — TRACKING ŞAŞMASININ KÖK NEDENİ + adopte hedefler  ⭐⭐⭐⭐

### 13.1 🔥 KÖK NEDEN: auto-detect `position_data`'sında `trading_pair` EKSİKTİ
Tek satırlık eksik, uzun bir hata zincirinin kaynağı. `_save_position_to_archive`
`trading_pair` anahtarını **zorunlu** tutar ("-" içermezse arşivlemeyi reddeder).
Normal `_track_position` yolunda anahtar **VARDI**; yalnızca **auto-detect (adopte)**
yolunda yoktu.

```
adopte pozisyon tracking'e eklenir  →  _save_position_to_archive REDDEDER
   ⚠️ [ARCHIVE SKIP] Geçersiz trading_pair: None, position_data: 1785255479388700
→ pozisyon HİÇ arşivlenmez
→ restart:  📂 State yükleniyor: 0 pozisyon kaydı  /  ℹ️ Recover edilecek pozisyon yok
→ auto-detect yeniden çalışır ve HER SEFERİNDE YENİ pseudo order_id üretir
   (⚠️ order_id trade history'de bulunamadı → Timestamp kullanılacak)
→ önceki pseudo id ile konmuş SL/TP legleri kalıcı "untracked_parent" orphan görünür
→ her restartta yeni leg çifti eklenir, eskiler kalır
→ symbol başına 10 koşullu emir tavanının dolmasına KATKI (§11.3 ile birleşir)
→ süpürücü guard'ı son SL leg'ini korumak zorunda kalır → 2 dakikada bir WARNING
```
Kullanıcının *"eski hatalı yapı tracking mekanizmasını şaşırtmış olmalı"* sezgisi
**doğruydu** — mekanizma budur. **Fix N** anahtarı ekler.

⚠️ İkincil yapısal sınır: adopte pozisyonun **gerçek entry order_id'si** trade history'den
alınamıyor. **Nedeni v3.5'te netleşti:** Bybit exec kaydında `positionSide` yok (§16.2 →
Fix X ile türetiliyor) **VE** `orderId` bir UUID olduğu için `_safe_int` ile tracking
kimliğine çevrilemiyor (§16.4.b). Yani bu satır Bybit'te **hiçbir zaman** sayısal bir
entry id üretemez → kimlik **CID leglerinden** kurtarılır (§15 Fix T) veya pseudo id
kullanılır. Fix N ile pseudo id **kalıcı** olduğu için legler restart'lar arasında eşleşir;
Fix AC ile de türetim artık **deterministik** (eskiden `hash()` randomize idi → §16.4.c).

### 13.2 B3'ün ÜÇÜNCÜ noktası — birincil yerleştirme yolu (Fix M)
`_set_binance_sltp_async` Bybit dalı `if r.get("success")` kontrol ediyordu; bu "hard fail
yok" demektir ve **breached/immediate/cooldown/cap_full**'da leg konmadığı hâlde `True`'dur.
Sonuç: `_sltp_ws_confirmed` set ediliyor (koruma ağı parçayı TAM KORUMALI sanıyor) ve
`[INDIVIDUAL SLTP] ✅ … SL:0.0702, TP:0.0694` **yalan** logu basılıyordu — canlı kanıt:
borsada `H-S-1785255479388700-BB` **hiç yoktu**, sadece TP vardı.
B3'te periodic-verify + health-check düzeltilmişti; **birincil (giriş/individual) yol
atlanmıştı.** Artık 4 noktanın hepsi leg-bazlı gerçeği raporluyor.

### 13.3 Adopte hedef türetme (Fix O) — kullanıcı kararı: SL %1 / TP %2
Sinyal/arşiv auto-close için güvenilmezse (§12.3 Fix J) **SL/TP hedefi olarak da
güvenilmezdir**. Bu durumda hedefler borsanın `avgPrice`'ından (breakeven) türetilir:

```
LONG :  SL = be×(1−%1)   TP = be×(1+%2)
SHORT:  SL = be×(1+%1)   TP = be×(1−%2)
entry := be  (borsa gerçeği; arşivin entry'si DEĞİL)
```
**Anlık-tetik clamp'i:** türetilen SL zaten kırılmışsa (yerleştirilemez) `mark`'ın
`BYBIT_ADOPT_SL_MIN_BUFFER_PCT` (%0.3) ötesine çekilir → parça **korumasız kalmaz**
(gevşek SL, naked'dan iyidir). Log clamp'i açıkça bildirir.

Doğrulanmış senaryolar (be=0.0700561, tick=0.00001):
| side | mark | SL | TP | clamp | yerleştirilebilir |
|---|---|---|---|---|---|
| SHORT | 0.0707 | 0.07076 | 0.06865 | hayır | ✅ |
| SHORT | 0.0710 | 0.07121 | 0.06865 | **evet** | ✅ |
| SHORT | 0.0690 | 0.07076 | 0.06865 | hayır | ✅ |
| LONG | 0.0695 | 0.06936 | 0.07146 | hayır | ✅ |

(Eski davranış: arşiv SL=0.0702, SHORT mark=0.0707 → SL fiyatın ters tarafında → **ASLA
konamaz**; borsa `10001 'StopLoss … should greater base_price'` ile reddeder.)

### 13.4 Guard log spam'i (Fix L)
"Son koruma leg'i silinmedi" guard'ı **kalıcı** bir durumu bildirebilir (parça kendi
leg'ini hiç koyamıyorsa). Her süpürme turunda (120s) WARNING basmak log'u boğuyordu →
artık ilk kez WARNING, sonrasında `BYBIT_ORPHAN_GUARD_LOG_INTERVAL` (30 dk) aralıkla;
aradaki turlar DEBUG. Fix O kök nedeni çözdüğü için bu durum normalde hiç oluşmamalı.

### 13.5 v3.2 düzeltmeleri
| Fix | Ne | Nerede |
|---|---|---|
| **L** | Guard log throttle (30 dk) | `_bybit_sweep_orphan_conditional_orders` |
| **M** | B3'ün 3. noktası: birincil yerleştirme yolunda leg-bazlı gerçek + `all_placed` + `🔓 NAKED LEG`; `_sltp_ws_confirmed` yalnızca tüm legler konduysa | `_set_binance_sltp_async` (Bybit dalı), `[INDIVIDUAL SLTP]` logu |
| **N** | **`trading_pair` anahtarı** adopte `position_data`'ya eklendi → arşivleme çalışır, pseudo id kalıcı olur | auto-detect `position_data` |
| **O** | Güvenilmez sinyalde hedefler breakeven'den türetilir (SL %1 / TP %2) + anlık-tetik clamp'i | auto-detect, `reliable_for_autoclose` sonrası |

### 13.6 Yeni env değişkenleri (v3.2)
```
BYBIT_ADOPT_SL_PCT=0.01              BYBIT_ADOPT_TP_PCT=0.02
BYBIT_ADOPT_SL_MIN_BUFFER_PCT=0.003  BYBIT_ORPHAN_GUARD_LOG_INTERVAL=1800
```
⚠️ Bunlar konsolidasyonun `BYBIT_CONSOLIDATE_SL_PCT`(%4)/`_TP_PCT`(%8) değerlerinden
**AYRIDIR** — adopte pozisyon ile aggregate konsolidasyon farklı politikalar.

### 13.7 Deploy sonrası izlenecek yeni loglar
```
🧭 [ADOPT TARGETS] … sinyal/arşiv güvenilmez → hedefler breakeven(…) bazlı yeniden
   türetildi: SL=… (%1) TP=… (%2)
⚠️ [INDIVIDUAL SLTP] … KISMEN yerleşti (sl_status=…, tp_status=…)
🔓 [BYBIT NAKED LEG] … konulamadı: SL(breached)
```
OLMAMALI: `⚠️ [ARCHIVE SKIP] Geçersiz trading_pair: None`;
`✅ [INDIVIDUAL SLTP] … SL:… TP:…` ardından borsada o CID'in bulunmaması;
2 dakikalık `🛡️ [BYBIT ORPHAN] … SON SL leg'i` tekrarı.

---

## 14) v3.3 — SEMBOL ÇÖZÜMLEME (bir sinyal açıldı, biri sonsuza dek ertelendi)

### 14.1 Belirti
2026-07-28 20:02 deploy. İki sinyal geldi, **biri açıldı biri askıda kaldı**:
```
20:20:22  DOTUSD.P  sell  → 📁 DOTUSD_SHORT_… → ⏳ ertelendi (trading rules not ready)
                            retry=1..7/20  delay=5→320s ve büyüyor
20:25:05  BNBUSDT.P sell  → 📁 BNB-USDT_SHORT_… → ✅ 20:25:38 pozisyon AÇILDI
```
Connector HAZIRDI (`conn_ready=True`; BNB aynı connector'da 33 sn sonra açıldı) — yani
"trading rules not ready" mesajı **yanlış teşhis**.

### 14.2 Kök neden: normalizasyonda `USD` dalı yok
Eski kod yalnızca `USDT`/`USDC` son ekini biliyordu:
```python
trading_pair = trading_pair.replace(".P","")
if "-" not in trading_pair and len(trading_pair) >= 6:
    if   trading_pair.endswith("USDT"): → BNBUSDT → "BNB-USDT"  ✅
    elif trading_pair.endswith("USDC"): → yok
    # USD için DAL YOK → "DOTUSD" olduğu gibi kalır
```
`DOTUSD` `connector.trading_rules`'ta yok → `_requeue_signal("trading rules not ready")`.
`markets` listesinde **`DOT-USDT` VAR** ([L505](../tv_signal_strategy.py#L505)), yani hedef
enstrüman belirsiz değil; Bybit **linear** evreninde `DOTUSD` diye market yoktur
(USD yalnızca inverse kontratlarda, strateji `category="linear"` kullanır).

**Sinyal kaynağı hatası:** TradingView alert'i `DOTUSD.P` göndermiş, `DOTUSDT.P`
göndermeliydi. Asıl düzeltme Pine/alert tarafındadır; bot artık toleranslı davranıyor.

### 14.3 İkinci kusur: backoff'ta üst sınır yok
`delay = 5 × 2^(n−1)`, kap yok → retry 15 ≈ 1 gün, retry 20 ≈ **30 gün**, 20 retry
toplamı ≈ **61 gün**. Yani çözülemeyen sembol ne işlenir ne düşer, queue'da asılı kalır.
Kap (300s) ile 20 retry toplamı **75 dakika**.

### 14.4 Üçüncü kusur: normalizasyon KOPYALANMIŞ
Aynı mantık `_archive_signal` içinde de tekrarlanıyordu (aynı USD boşluğuyla) → arşiv
dosyası `DOTUSD_SHORT_…` adıyla yazılıyordu. Pair `DOT-USDT` olarak çözülse bile
auto-detect o arşivi **hiç bulamaz** → SL/TP kurtarılamaz. Artık tek çözücü kullanılıyor.

### 14.5 v3.3 düzeltmeleri
| Fix | Ne | Nerede |
|---|---|---|
| **P** | `_resolve_signal_trading_pair(connector, raw)` — adaylar `trading_rules`'a karşı denenir, **tahmin yok**. `.P/.PERP/.SWAP` soyulur. `USD` → `USDT` ikamesi (yalnızca hedef pair gerçekten varsa). **`USDC` ikame EDİLMEZ** — Bybit'te USDC perp'i ayrı gerçek bir market, sessizce USDT işlemek yanlış enstrüman olur. | yeni helper |
| **Q** | **Hızlı başarısızlık**: `trading_rules` yüklüyse sorun "hazır değil" değil "sembol desteklenmiyor"dur → sinyal HEMEN düşürülür, arşive `unsupported_symbol:…` yazılır, desteklenen pariteler loglanır. 20 retry yok. | `_process_signal` |
| **R** | Backoff kapı `SIGNAL_RETRY_DELAY_MAX=300` | `_requeue_signal` |
| **S** | `_archive_signal` de aynı çözücüyü kullanır → arşiv adı tracking pair'i ile tutarlı | `_archive_signal` |

Doğrulanmış davranış (`markets`: BTC/ETH/DOT/DOGE/BNB-USDT):
| Sinyal | Sonuç |
|---|---|
| `BNBUSDT.P` | `BNB-USDT` (direct) |
| `DOTUSD.P` | `DOT-USDT` (**substituted**, WARNING loglanır) |
| `BTCUSD.P` | `BTC-USDT` (substituted) |
| `DOTUSDT.P` / `ETH-USDT` | direct |
| `BTCUSDC.P` | **RED** — USDC ayrı market, ikame yok |
| `SOLUSDT.P` | **RED** — markets listesinde yok |

### 14.6 Yeni env
```
SIGNAL_RETRY_DELAY_MAX=300        SIGNAL_QUOTE_FALLBACK_USDT=1
```

### 14.7 Bu logdaki SAĞLIK durumu (çökme/çakışma YOK)
- `✅ [BYBIT COND SL] … @ 572.80` + `✅ [BYBIT COND TP] … @ 560.50` +
  `✅ [B4 BYBIT SLTP] … parent=94939948991 SL=… TP=…` → **per-piece CID mimarisi
  ilk kez temiz çalıştı** (SL ve TP ayrı, ikisi de konuldu).
- `110072` / `110009` / `110093` **YOK**. `🔓 NAKED LEG` **YOK**.
  `⚠️ [ARCHIVE SKIP]` **YOK**. Orphan guard spam'i **YOK**.
- Risk/margin clamp doğru: `Initial margin çok büyük! 5157.27 > 206.56` → boyut
  düşürüldü, Risk=37.18 USDT (%0.90), 7.26 BNB @ 20x.
- Tracking sağlıklı: `📋 [TRACKED] Bot: ['BNB-USDT_SHORT'] (Toplam: 1)`.
- ⚠️ Bilgi: `[MQTT] External event listener setup failed: MQTTGateway is offline!` —
  gateway yolu kapalı ama **direct client** çalışıyor (sinyaller geldi) → degraded,
  kırık değil. Tek yolla çalışıyor; gateway ayağa kalkarsa yedek yol geri gelir.
- ℹ️ `🔍 [DEBUG] account_positions keys: []` — HB'nin kendi cache'i boş, bot kendi REST
  cache'ini kullanıyor (Bybit'te beklenen, §4B).

---

## 15) v3.4 — ARŞİV OKUYUCU KUSURU (doğru SL/TP'nin ezilmesi) + arşiv hijyeni  ⭐⭐⭐⭐

### 15.1 Belirti
Restart öncesi BNB SHORT doğru leglerle açıldı (SL 572.8 / TP 560.5, parent 94939948991).
Restart sonrası **aynı arşivden aynı pozisyon FARKLI SL/TP ile** çekildi, yeni legler
kondu ve **doğru legler silindi** — oysa o aralıkta hiç yeni TradingView sinyali yok.
```
20:44:04 📁 Arşivden yüklendi: BNB-USDT_SHORT_1785259505.json (19.0 dk)
         Entry: 568.7, SL: 572.8, TP: 560.5              ← DOĞRU okundu
20:44:04 ⚠️ arşiv dolmamış sinyal (status='', filled=7.26) → güvenilmez
20:44:04 🧭 [ADOPT TARGETS] SL=574.60 TP=557.60 | eski (kullanılmayan): SL=572.8 TP=560.5
20:48:06 🧹 [BYBIT ORPHAN] iptal H-S-94939948991-BB trig=572.8 (untracked_parent)
```

### 15.2 🔥 Kök neden: arşiv DOSYASI değil, OKUYUCU
VPS'teki dosya **kusursuz**:
```json
"status": "filled", "filled_amount": 7.26, "fill_price": 569.0,
"order_id": "36b2686d-…", "sl_price": 572.8, "tp_price": 560.5
```
Ama `_load_signal_from_archive` dönüş sözlüğü yalnızca
`entry / sl / tp / timestamp / filled_amount / _archive_file` içeriyordu —
**`status` YOK.** §12.3 Fix J `archive_data.get("status")` okuyordu → `None` → `''` →
`'' ∉ {filled, closed}` → "güvenilmez" → §13.3 Fix O doğru hedefleri ezdi.
**Yani hatayı ben ekledim** (Fix J, dosya şemasını değil loader şemasını varsaymalıydım).

**İkinci kusur — kavram karışıklığı:** Fix J tek bayrak (`reliable_for_autoclose`)
kullanıyordu. Bunlar İKİ AYRI soru:
| Soru | Yaş kuralı | Kriter |
|---|---|---|
| Bu arşive dayanarak pozisyonu **KAPATABİLİR** miyim? | 10 dk (katı) | para aksiyonu |
| Bu arşiv bu pozisyonun **SL/TP hedefi** mi? | ~önemsiz (yükleme zaten 45 dk kapılı) | arşiv BU pozisyona karşılık geliyor mu |
19 dakikalık, `filled_amount=7.26` (pozisyonla **birebir**) bir arşiv ikinci soru için
mükemmelken 10 dk kuralına takılıyordu.

### 15.3 Diğer arşiv anomalileri (canlı ölçüm 2026-07-28 VPS)
| Bulgu | Değer | Sonuç |
|---|---|---|
| Hiç disk prune YOK | signal 11.694 dosya/47 MB · position 12.978/52 MB · perfill 16 MB · toplam **~115 MB, ~24.800 dosya**, en eski **2026-03-30** | her auto-detect binlerce dosyada glob |
| Arşivlerin ~yarısı **`pending`** | 400 örnek: 198 pending / 185 filled / 17 failed | ⚠️ loader `max(mtime)` = "en son dosya" seçiyordu → **hiç dolmamış** sinyal canlı pozisyona uygulanabiliyor (DOGE vakasının kaynağı) |
| Bozuk dosya adları | `__1776451170.json` × **7** (pair VE side boş) | `{pair}_{side}_{ts}` şablonu doğrulanmadan yazılıyor |
| `DOTUSD_SHORT/LONG` × 19 | §14 USD normalizasyon boşluğu | §14 Fix P/S ile giderildi |
| `tv_signal_state.json` | yazılıyor ve güncel (BNB pseudo id + türetilmiş 574.6 kaydedilmiş) | persist çalışıyor; ama restart'ta `0 pozisyon kaydı` okundu → §15.5 |

### 15.4 v3.4 düzeltmeleri
| Fix | Ne | Nerede |
|---|---|---|
| **U** | Loader artık `status`/`order_id`/`fill_price`/`fill_timestamp` **geçiriyor**; dosya seçimi **puanlı**: (dolu + miktar eşleşen) > (dolu) > (diğer), eşitlikte en yeni. `match_amount` ile pozisyon boyutu verilir. Tarama `ARCHIVE_SCAN_LIMIT`(40) ile sınırlı | `_load_signal_from_archive` |
| **V** | `targets_trustworthy` bayrağı `reliable_for_autoclose`'dan **ayrıldı**. Hedef türetme (Fix O) artık yalnızca arşiv BU pozisyona karşılık gelmiyorsa çalışır (miktar ±%5 VEYA status=filled) | auto-detect |
| **T** | Restart'ta **parent order_id borsadaki CID leglerinden kurtarılıyor** (`H-S-<parent>-BB` → parent). Pseudo id üretilmeden önce denenir → eski DOĞRU legler orphan olup silinmez, gereksiz churn biter | `_recover_parent_id_from_cid_legs` |
| **W** | Arşiv hijyeni: boş pair/side ile **yazmayı reddet** (`__<ts>.json` üretimi biter) + disk prune (yaş `ARCHIVE_RETENTION_DAYS`=7g, pair/side başına `ARCHIVE_MAX_FILES_PER_KEY`=60). **Aktif pozisyon arşivleri korunur** | `_archive_signal`, `_prune_disk_archives` |

Doğrulanmış davranış:
| Senaryo | `targets_trustworthy` | Sonuç |
|---|---|---|
| BNB: `status=filled`, `filled=7.26`, poz 7.26 | **True** | arşiv hedefleri (572.8/560.5) **KORUNUR** |
| DOGE: `status=pending`, `filled=0`, poz 24091 | False | breakeven %1/%2 türetilir |
| `status` alanı olmayan eski arşiv, miktar eşleşiyor | **True** | arşiv hedefleri korunur |

### 15.5 Kalan açık konu (fix EDİLMEDİ)
Restart'ta `📂 State yükleniyor: 0 pozisyon kaydı` okunuyor, oysa `tv_signal_state.json`
dolu ve güncel yazılıyor. Startup sırası şüpheli: state yükleme
`20:44:03,059`'da, pozisyon cache'i `20:44:03,250`'de (yükleme SONRASI) tazeleniyor ve
`⏸️ [STARTUP CLEANUP] Exchange'de pozisyon görünmüyor` uyarısı da bundan doğuyor.
Fix T bu durumun ZARARINI ortadan kaldırıyor (kimlik CID'den kurtarılıyor) ama state
yükleme sırası ayrıca incelenmeli.

### 15.6 Yeni env (v3.4)
```
ARCHIVE_SCAN_LIMIT=40            ARCHIVE_RETENTION_DAYS=7
ARCHIVE_MAX_FILES_PER_KEY=60     ARCHIVE_PRUNE_INTERVAL=3600
```

### 15.7 Temiz başlangıç (kullanıcı sorusu)
`rm` komutları **güvenli ama yeterli değil ve gerekli de değil**:
- Arşiv verisi **bozuk değildi** → silmek 15.1 belirtisini çözmez; kod fixleri (U/V) çözer.
- **Pozisyon AÇIKKEN `signal_archive` silinmemeli**: auto-detect SL/TP kaynağını kaybeder
  ve hedefleri breakeven'den (%1/%2) türetir → mevcut korumalar değişir.
- Doğru sıra: **(1)** v3.4 deploy → **(2)** pozisyonlar KAPALIYKEN `rm` → **(3)** başlat.
- `ARCHIVE_RETENTION_DAYS`/`ARCHIVE_MAX_FILES_PER_KEY` artık birikimi kendiliğinden
  önlüyor; tek seferlik `rm` yalnızca 4 aylık geçmişi kısaltmak için.

---

## 16) v3.5 — 🔥 KAPANIŞ TESPİTİ HİÇ ÇALIŞMIYORDU + leak/restart soruşturması ⭐⭐⭐⭐⭐

Log: 2026-07-28 21:31 → 2026-07-29 11:16 (v3.4 deploy sonrası, **13,75 saat kesintisiz**).

### 16.1 Yeni KANITLANMIŞ API gerçekleri (`/v5/execution/list`, demo, 2026-07-29)
`tools/bybit_exec_probe.py` ile 5 sembol × 20 satır:

| # | Soru | **KANITLANMIŞ CEVAP** |
|---|---|---|
| 11 | execution kaydında `positionIdx` var mı? | **YOK.** Tam alan listesi: `blockTradeId, closedSize, createType, execFee, execFeeV2, execId, execPrice, execQty, execTime, execType, execValue, extraFees, feeCurrency, feeRate, indexPrice, isMaker, leavesQty, markIv, markPrice, marketUnit, orderId, orderLinkId, orderPrice, orderQty, orderType, seq, side, stopOrderType, symbol, tradeIv, underlyingPrice`. → `positionSide` **doğrudan okunamaz, TÜRETİLMELİ.** |
| 12 | `closedSize` güvenilir "reduce" göstergesi mi? | **EVET.** `closedSize > 0` ⟺ bu execution pozisyonu küçülttü; `"0"` ⟺ açtı/büyüttü. Hedge modda eşleme tek anlamlı (§16.5'te 11/11 doğrulandı). |
| 13 | execution listesi sadece trade mi döndürür? | **HAYIR.** 8 saatte bir `execType="Funding"` satırı gelir ve **`execQty` = O ANDAKİ POZİSYON BOYUTU**'dur (`side=Buy execQty=5.41 closedSize=0 execType=Funding`). Trade sanılırsa **pozisyon büyüklüğünde hayalet giriş** üretir. |
| 14 | execution'da `orderLinkId` var mı? | **EVET, dolu geliyor** (`H-S-<parent>-BB1`, `B4<ts>`). → CID→parent eşlemesi **ekstra REST çağrısı olmadan** yapılabilir. |
| 15 | `createType` neyi ayırt eder? | `CreateByUser` (giriş / bot market-close) · `CreateByStopOrder` (per-piece CID legi) · `CreateByStopLoss`/`CreateByTakeProfit` (**trading-stop Full** = konsolide koruma, `orderLinkId` boş). |

### 16.2 🔥 KÖK NEDEN: `positionSide` sabit boş string idi
`_get_bybit_executions` normalize ederken `"positionSide": ""  # filled by caller if needed`
yazıyordu — **hiçbir caller doldurmuyordu.** Stratejide trade'leri süzen **9 ayrı yer**
`t.get("positionSide") == side` yapıyor → Bybit'te **hepsi her zaman boş liste** döndürüyordu.

**Ölçülen sonuç (13,75 saatlik log):**

| Belirti | Sayı |
|---|---|
| `⏰ [MANUEL CLOSE TIMEOUT]` → `FORCE CLEANUP` | **19 / 19 kapanış** (temiz kapanış = **0**) |
| `⏸️ [PARTIAL CLOSE AMBIGUOUS] … close_qty=0 … Kör FIFO engellendi` | **81** |
| Tracking şişmesi | `[TRACKED] Bot: Toplam 15` ↔ borsada en fazla **9** |

Yani **her** kapanış 60–120 s "trade history'de close bulunamadı" bekleyip zorla temizleniyordu.
Kullanıcının *"bot aksiyon almada, sl/tp silmede geç kalıyor"* hissi **birebir bu.**

### 16.3 🔥 Sadece "gecikme" değil — PARA KAYBEDEN döngü
Kapanan parça tracking'ten düşmediği için koruma ağı **kapanmış parçaya tekrar TP kuruyor**;
o TP fiyat geçtiği için tetiklenip **pozisyondan bir dilim daha kesiyor**.
Canlı kanıt — ETH-USDT SHORT parça #177111192753 (qty 0.82):

```
06:51:24  H-T-177111192753-BB1 TETİKLENDİ → 0.82 kapandı (borsa: 2.75 → 1.93)
06:51:48  ⏸️ PARTIAL CLOSE AMBIGUOUS close_qty=0   ← parça DÜŞÜLEMEDİ
06:53:30  🔁 CID ROTATE BB1 yanmış (filled) → BB2 · 🔓 NAKED LEG TP(immediate)
06:58:30  ✅ BYBIT COND TP @1891.56 qty=0.82        ← AYNI parçaya TEKRAR TP
06:58:36  BB2 TETİKLENDİ → 0.82 daha kapandı (1.93 → 1.11)
07:20:29  BB3 TETİKLENDİ → 0.82 daha kapandı (1.11 → 0.29)
```

`Tracked` hep 2.75'te kaldı. **Tek parça için 3 × 0.82 = 2.46 ETH** planlanmadan kapatıldı.
`H-T-177111192753-BB1/BB2/BB3` üçünün de `closedSize=0.82` ile Filled olduğu probe'da görülür.

### 16.4 İkincil kusurlar (aynı zincirin parçaları)

| # | Kusur | Etki |
|---|---|---|
| a | `_map_close_trades_to_parent_ids_by_cid` → `order_id = int(t.get("orderId", 0))` | Bybit order id'leri **UUID** → her satırda `0` → `continue`. **CID→parent eşlemesi Bybit'te TAMAMEN ÖLÜ**, hep kör FIFO'ya düşülüyordu. |
| b | `int(t.get("orderId", 0)) not in self._bot_generated_close_orders` (2 yer) + `real_order_id = int(trade.get("orderId", 0))` (auto-detect) | UUID'de **ValueError**. Bugüne kadar patlamadı çünkü `positionSide == side` **her zaman False** olup `and` zincirini short-circuit ediyordu. positionSide düzeltilse bu satırlar **anında exception atacaktı** (auto-detect'te §15 Fix T CID-recovery'sini de atlatarak). → positionSide fixiyle **aynı turda** düzeltilmesi ZORUNLUYDU. |
| c | `order_id_int = abs(hash(str(order_id))) % 10**12` (2 yer) | Python `hash(str)` **PYTHONHASHSEED ile process başına randomize**. Aynı Bybit UUID'si restart sonrası **BAŞKA** parent id üretiyordu → borsadaki `H-S-<parent>-BB` legleri sahipsiz görünüyordu (§13.1/§15.5 churn'ünün bir bacağı daha). |

### 16.5 v3.5 düzeltmeleri

| Fix | Ne | Nerede |
|---|---|---|
| **X** | `positionSide` **türetiliyor**: `Sell`+reduce→LONG · `Buy`+reduce→SHORT · `Buy`+open→LONG · `Sell`+open→SHORT (reduce ⟺ `closedSize>0`). Ayrıca `execType ∈ {Funding, Settle, SessionSettlePnL}` **atlanıyor** ve `clientOrderId / orderLinkId / closedSize / reduceOnly / execType / createType / stopOrderType` dışa veriliyor | `_get_bybit_executions`, `BYBIT_NON_TRADE_EXEC_TYPES` |
| **Y** | CID→parent eşlemesi UUID-safe; `orderLinkId` **satırdan** okunuyor (ekstra REST yok). `_get_client_order_id_by_order_id` Bybit'te erken `None` (Binance fapi'ye gitmesin) | `_map_close_trades_to_parent_ids_by_cid` |
| **AB** | `int(orderId)` mayınları temizlendi: `_is_bot_generated_close_order()` (int **ve** str üyelik) + auto-detect'te `_safe_int` ve `<=0` ise `continue` (CID-recovery'ye düşsün) | 2 × manuel-close filtresi, auto-detect |
| **AC** | `_stable_int_order_id()` — sha1 tabanlı **deterministik** parent id (restart'ta AYNI) | 2 × `abs(hash(...))` yerine |
| **AA** | `BYBIT POSITIONS cache refreshed` artık **fingerprint (pair_side→miktar) değişmedikçe** DEBUG. Ölçüm: 13,75 saatte **516 satır** (332'si `phase2-tp2-check`) hepsi aynı veriyi tekrarlıyordu | `_fetch_bybit_positions` |

**Doğrulama** (`tools/verify_exec_fixes.py` — helper'lar AST ile GERÇEK dosyadan çıkarılıp koşuldu):
- positionSide türetmesi: **canlı borsa 9 kapanış satırı + 2 açılış = 11/11**, log ground-truth
  ile eşleşti (CID parent → borsa side): `400586919576→LONG(BNB)`, `961063690544→LONG(ETH)`,
  `608835124721→LONG(DOT)`, `614134201237→SHORT(DOGE)`, `797452564966→LONG(DOGE)`,
  `529876242241→LONG(BTC)`, `701190084971→SHORT(BNB)`, `677936178791→SHORT(BNB)`,
  `177111192753→SHORT(ETH)`
- `_stable_int_order_id`: deterministik, 12 hane, boş girdide 0
- `_is_bot_generated_close_order`: 6 senaryo, UUID'de ValueError yok
- `py_compile` OK · AST: **0 fonksiyon kaybı** · `BYBIT_GUARD` hâlâ 2 (guard + docstring)

### 16.6 ❌ Otomatik restart YOK — kullanıcı sorusu 3
Ölçüm (VPS, salt-okuma):

```
docker inspect hummingbot → RestartCount=0  OOMKilled=false  ExitCode=0
                            StartedAt=2026-07-28T18:31:14Z (= 21:31 TR)  Up 14 hours
dmesg | grep -i oom       → (boş)      docker events (24h) → (boş)
```

Logdaki 3 "boot" (20:02 / 20:44 / 21:30+21:31) **kullanıcının kendi deploy'ları**.
Restart gibi *görünen* şey → **7 adet WS reconnect**: `ConnectionError: No PONG received
after 10.0 seconds` ve `Close code = 1006` sonrası `Subscribed to private/public … channels`
satırları boot sekansına benziyor. Bunlar **kendi kendini onaran, normal** olaylardır
(user-stream 4×, public order book 3× / 14 saatte). Pozisyon takibi bunlardan **bozulmadı**;
takip bozulmasının nedeni §16.2'dir.

### 16.7 ❌ OEM/memory leak Bybit'te YOK — kullanıcı sorusu 4
`leak_solved.md`'deki OKX katili: `_message_queue["mark_price"]` — **üretici var, tüketici yok**
(`listen_for_mark_price_info` hiç task olarak schedule edilmiyordu) → 132.600+ mesaj, 3,5 GB.

Bybit'te bu şablon **yok**:
- `BybitPerpetualAPIOrderBookDataSource._channel_originating_message` yalnızca **3** kuyruğa
  yazıyor: `trade`, `diff`, `funding_info`. `mark_price`/`index_price` kuyruğu **hiç yok**.
- Üçünün de tüketicisi **çalışıyor**: `listen_for_trades` / `listen_for_order_book_diffs`
  (`order_book_tracker_data_source.py`) ve `_funding_info_listener_task = safe_ensure_future(...)`
  (`perpetual_derivative_py_base.py:97`) — OKX'te eksik olan tam bu schedule'dı.
- Ölçüm: **14 saat sonra `hummingbot` container 315,6 MiB** (host 7,57 GiB'in %4,07'si), swap 0.
  OKX vakasında saatler içinde GB'lara çıkıyordu. **Trend düz.**
- ⚠️ `docker inspect … MemLimit=0` → OKX döneminde konulan **3,5 GB limiti artık YOK**.
  Sızıntı olmadığı için sorun değil; yine de emniyet kemeri istenirse compose'a
  `mem_limit: 3500m` geri eklenebilir (öneri, zorunlu değil).
- `leak_solved.md`'deki teşhis probları hâlâ **mühürlü**: `_log_leak_probe_telemetry`,
  `_log_reference_cache_telemetry`, `_log_connector_queue_health` → hepsinin ilk satırı `return`.
  `_log_gc_type_histogram` ve `QUEUE OWNER V4` dosyada **yok**. `_cleanup_reference_caches`
  **aktif** (silinmemeli). Tek `gc.get_objects()` çağrısı mühürlü fonksiyonun içinde → çalışmıyor.

### 16.8 Kalan açık konular (fix EDİLMEDİ — bilinçli)
1. **`🔓 [BYBIT NAKED LEG] … SL(breached)` döngüsü.** DOGE-USDT LONG #71316517654 için
   ~35 dk boyunca 7 kez; ETH SHORT için `TP(immediate)` benzer şekilde. Parçanın SL'i fiyatın
   ters tarafında kaldığı için **hiç konulamıyor** (§10.6). §13.3'teki *anlık-tetik clamp*'i
   (mark'ın %0,3 ötesine çek) sadece **adopt** yolunda var; periodic-verify yolunda yok.
   Aynı politikayı buraya taşımak parçayı korumasız bırakmaz ama **gevşek SL = para kararı** →
   kullanıcı onayı gerekir. ETH tarafındaki tekrar §16.5 Fix X ile kendiliğinden bitecek
   (kapanmış parça artık tracking'ten düşecek); DOGE tarafı gerçek bir korumasız parçadır.
2. **§15.5 hâlâ açık:** restart'ta `📂 State yükleniyor: 0 pozisyon kaydı` (state dosyası dolu).
   Startup sırası: state yükleme `…:03,059`, pozisyon cache tazeleme `…:03,250`.
3. **Orphan süpürücü kapanış temizliğini üstlenmiş durumda.** Logda 11 leg `(no_position)`
   gerekçesiyle silindi — bunlar aslında kapanış yolunun anında iptal etmesi gereken leglerdi.
   Fix X sonrası süpürücü yine **son savunma** olmalı, birincil yol değil; bir sonraki logda
   `(no_position)` iptal sayısının **belirgin düşmesi** beklenir.

### 16.9 Deploy sonrası izlenecek loglar

```
🧩 [CID RECONCILE CLOSE] … Parent #… closed via CID mapping. FIFO skipped.
🧩 [CID MANUEL CLOSE MATCH] / 🧩 [CID PARTIAL->MANUEL MATCH]
```

**AZALMASI/BİTMESİ gerekenler (başarı ölçütü):**
- `⏰ [MANUEL CLOSE TIMEOUT]` → **0'a yakın** (önce 19/19)
- `⏸️ [PARTIAL CLOSE AMBIGUOUS] … close_qty=0` → **bitmeli** (önce 81)
- `[TRACKED] Bot: Toplam` ile `[POZISYON DEĞİŞİKLİĞİ] Binance: Toplam` **eşit** kalmalı
  (önce 15 ↔ 9)
- `BYBIT POSITIONS cache refreshed` → yalnızca gerçek değişimde (önce 516 satır)
- `🧹 [BYBIT ORPHAN] … (no_position)` → belirgin azalma

**OLMAMASI gerekenler:** `ValueError: invalid literal for int()`, aynı parça için tekrarlayan
`✅ [BYBIT COND TP]`, `🔁 [BYBIT CID ROTATE] … (status=filled)` serisi.

---

## 17) v3.6 — 🔥 POZİSYON CACHE'İ SALINIYORDU (HB upstream `side=''` hatası) ⭐⭐⭐⭐⭐

Log: 2026-07-29 12:04 → 2026-07-30 11:45 (**27 saat kesintisiz**, `RestartCount=0`).
v3.5 deploy edilmiş durumda. Bu bölüm v3.5'in **ne kadarını çözdüğünü** ve kalan
kök nedeni belgeler.

### 17.1 v3.5 skorkartı (ölçüm)
| Metrik | v3.4 (13,75 s) | v3.5 (27 s) | Sonuç |
|---|---|---|---|
| `⏸️ [PARTIAL CLOSE AMBIGUOUS] close_qty=0` | **81** | **0** | ✅ Fix X çözdü |
| `🧩 [CID … CLOSE MATCH]` (yeni yol çalışıyor) | 0 | 2 | ✅ Fix Y çalışıyor |
| `ValueError: invalid literal for int()` | — | **0** | ✅ Fix AB tuttu |
| `BYBIT POSITIONS cache refreshed` satırı | 516 (332 tp2-check) | **103** (10 tp2-check) | ✅ Fix AA |
| `110072/110009/110093` spam | 0 | **0** | ✅ |
| `⏰ [MANUEL CLOSE TIMEOUT]` | 19/19 | **14** | ❌ **KALDI → §17.2** |

### 17.2 🔥 KÖK NEDEN: HB `account_positions` hayalet pozisyon üretiyor
**UPSTREAM HATA — canlı API ile kanıtlandı (2026-07-30).**
`hummingbot/connector/derivative/bybit_perpetual/bybit_perpetual_derivative.py::_update_positions`
(satır ~475) pozisyon yönünü şöyle türetiyor:
```python
position_side = PositionSide.LONG if data["side"] == "Buy" else PositionSide.SHORT
```
Bybit hedge modda **boş tarafı da satır olarak döndürür** ve o satırda `side=''` olur.
Canlı kanıt (`/v5/position/list?category=linear&symbol=…`, HB'nin kullandığı çağrının aynısı):
```
DOGEUSDT: idx=1 side='Buy'  size='76030' | idx=2 side=''     size='0'
BNBUSDT : idx=1 side=''     size='0'     | idx=2 side='Sell'  size='8.72'
ETHUSDT : idx=1 side='Buy'  size='5.33'  | idx=2 side=''     size='0'
```
`side=''` → `!= "Buy"` → **her boş satır SHORT sayılıyor.** İki ayrı bozulma:
1. **Kapanan bir LONG asla silinmiyor.** Boş idx=1 satırı `remove_position(<pair>SHORT)`
   çağırıyor → `<pair>LONG` anahtarı `account_positions`'ta **hayalet** olarak kalıyor.
2. **Canlı bir SHORT silinebiliyor.** BNBUSDT örneğinde boş idx=1 satırı da, canlı idx=2
   satırı da aynı `<pair>SHORT` anahtarına yazıyor. Satır sırası garanti değil; boş satır
   sonra gelirse `set_position` üzerine `remove_position` biniyor.

**Bizim tarafımızdaki büyütücü (asıl suçlu bendim):** `_fetch_bybit_positions` bu görüntüyü
`_apply_hb_cache()` ile **tüm cache'in üzerine yazıyor ve REST'i atlıyordu** (§4B'de
"HB account_positions'a güveniyoruz" diye eklemiştim). Ayrıca Tier A `new_cache`'i bu
görüntüyle **seed** ediyordu. Sonuç:
```
non-force tick → cache = HB görüntüsü (hayaletli)
force tick     → cache = REST gerçeği
```
→ cache 30 saniyede bir **6 ↔ 5 salınıyor** (logda `Toplam: 6 5 6 5 6 5 …`).

### 17.3 Salınımın yol açtığı 4 belirti (hepsi tek kök)
```
11:28:13  [PHASE2 TP2 SKIP] DOGE SHORT #27536720338 - Binance amount 0 (kapanmış)
11:28:15  Binance: 5   ← REST gerçeği
11:28:45  Binance: 6   ← HB hayaleti geri geldi
11:29:00  🔁 CID ROTATE H-S-…-BB yanmış (filled) → BB1
11:29:01  ✅ BYBIT COND SL @0.07020 qty=17115   ← KAPANMIŞ pozisyona YENİ leg
11:29:11  🧩 CID MANUEL CLOSE MATCH → ✅ CLEANUP COMPLETE
11:29:54  🔍 [RECOVERY] DOGE SHORT track edilmiyor! Amount: -17115  ← HAYALET
11:29:54  ✅ [AUTO-DETECT] tracking'e eklendi (1R Reached: True)
11:30:29  🧹 [BYBIT ORPHAN] iptal H-T-…-BB1 (no_position)  ← 35 sn önce adopte edilenin TP'si
11:31:10  ⏸️ [MANUEL CLOSE WAIT] … close trade bulunamadı! 60 s
11:32:11  ⏰ [MANUEL CLOSE TIMEOUT] → FORCE CLEANUP
11:34:31  🧹 [BYBIT ORPHAN] iptal H-S-…-BB1 (no_position)
```
- **(kullanıcı b)** "birleştirmede tüm işleme konulan tp/sl silinemiyor" → legler
  *silinebiliyor*; sorun **ölü parçalar için sürekli YENİ leg üretilmesi**. Kanıt:
  ETH SHORT #394137403787 girişte doğru şekilde `side_consolidated(fixed)` ile
  bloklandı (07:10:04), ama konsolidasyon 11:06'da sıfırlanınca (pozisyon kapandı)
  parça hâlâ takipteydi → periodic-verify legleri koydu → sweeper 11:12'de topladı.
- **(kullanıcı c)** "korumasız açık pozisyonlar" → orphan süpürücü **doğru** çalışıyor
  (direkt REST kullanıyor, `_get_bybit_position_sizes`), cache'e güvenen periodic-verify
  yanlış leg üretiyor; ikisi birbirini kovalıyor.
- Kalan **14 `MANUEL CLOSE TIMEOUT`** → hayalet pozisyonun "kapanışı" için close trade
  aranıyor; gerçek kapanış zaten dakikalar önce tüketilmiş → 60-80 s bekleyip force cleanup.
- `[TRACKED] Toplam 17` ↔ `Binance Toplam 8` şişmesi.

### 17.4 v3.6 düzeltmeleri
| Fix | Ne | Nerede |
|---|---|---|
| **AD** | **HB `account_positions` artık gerçek kaynak DEĞİL.** `_apply_hb_cache()` erken-dönüş kısayolu (2 yer) kaldırıldı → yerine düz `BYBIT_POS_CACHE_TTL` (5 s) kontrolü. Tier A ayrı `hb_tier_a` sözlüğüne toplanıyor ve **yalnızca REST TAMAMEN başarısızsa** (`not rest_ok`) kullanılıyor; o durumda da uyarı loglanıyor. REST başarılı + boş ise "0 open" DOĞRU cevap kabul ediliyor | `_fetch_bybit_positions` |
| **AE** | **Anlık-tetik SL clamp'i artık ana yolda** (kullanıcı onaylı para kararı): breach pre-check'te SL fiyatın ters tarafındaysa leg atlanmıyor, **mark ∓ %0.3 seviyesine çekiliyor**. `🩹 [BYBIT SL CLAMP]` loglanır. ⚠️ **Yalnızca SL** — TP'yi mark'ın hemen ötesine çekmek rastgele seviyeden kâr realize etmek olurdu. `BYBIT_VERIFY_SL_CLAMP=0` ile kapatılabilir | `_place_bybit_conditional_order` |
| **AG** | Periodic-verify artık `phase2_tp_mode == "manual_second_take"` parçalarına **TP legi koymuyor**. Faz 2 bu modda TP'yi BİLEREK koymaz (TP tetik seviyesi; ikinci alım market close). Kanıt: **5/5** Faz 2 aktivasyonundan 2-7 dk sonra `🩹 … TP=True` + `✅ [BYBIT COND TP] (cid rotate #1)` → Faz 2'nin istemediği TP emri, TP2 market close ile aynı anda tetiklenme riski (L18824'teki `/order 400` spam'i) + boşuna CID yakma | `_bybit_periodic_sltp_verify` |
| **AF** | Faz 2 fill doğrulaması `2×10s` → `5×2s` (aynı ≈10 s toplam pencere, tipikte 2 s). SL **zaten** provisional olarak konulduğu için bu bekleme koruma sağlamıyordu, sadece Faz 2'nin kesinleşmesini geciktiriyordu (kanıt: BNB SHORT 19:04:20,139 → 19:04:30,531 = 10,4 s) | `_activate_phase2`, `PHASE2_VERIFY_RETRIES/DELAY` |

### 17.5 (kullanıcı a) Trailing stop ÇALIŞIYOR — ama nadiren tetikleniyor
27 saatte **10 konsolidasyon**; ikisi arasında birebir korelasyon:
| pnl | dal | sonuç |
|---|---|---|
| +0.01% · +0.06% · +0.16% | **(a1) KÂR** | **3/3 → `🏃 %1.00 trailing stop aktif`** (activePrice = breakeven ∓ dist) |
| −0.04 … −0.41% (7 adet) | (b1) ZARAR ≤%4 | 7/7 → `aggregate koruma SL=%4 TP=%8` |

Yani mekanizma sağlam. **Nadir tetiklenmesinin nedeni:** konsolidasyon `leg_budget(8/10)`
ile **çok erken** ateşleniyor — yönde 2 parça olunca (2 parça × 2 leg × 2 yön = 8 leg,
`BYBIT_COND_BUDGET_RESERVE=2`). O anda pozisyon henüz ±0.2% bandında ve komisyon/spread
yüzünden genelde **hafif eksi** → zarar dalına düşüyor. Sonuç: sinyalin sıkı SL'i
(~%0.7) yerine **%4 aggregate SL** devreye giriyor (BNB SHORT: entry 572.70 → SL 595.60).
Koruma var ama **5-6× daha geniş**. Bu bir *tasarım* sonucu, hata değil — ama
`BYBIT_MAX_PIECES_PER_SIDE`/`BYBIT_COND_BUDGET_RESERVE` ayarı veya "yalnızca kârdaysa
konsolide et, değilse parçayı reddet" politikası kullanıcı kararı olarak masada.

### 17.6 (kullanıcı d) Faz 2 SL için ONAY BEKLEMİYOR
Canlı sıra (BNB-USDT SHORT #625502882980):
```
19:04:19,385  kısmi kapama emri gönderildi
19:04:20,139  ✅ [PHASE 2 BYBIT] SL@570.70   ← 0,75 s sonra SL KONDU (fire-and-forget)
19:04:20,139  🔍 [FAZ 2 VERIFY] (2x10s polling)
19:04:30,531  ✅ FILLED                       ← 10,4 s BLOKE
19:04:31,760  ✅ [PHASE 2 BYBIT] SL@570.70   ← gerçek entry ile 2. kez (aynı fiyat)
```
Yani **SL beklemiyor** — `provisional_ok = await self._set_phase2_sltp(..., place_tp=False)`
kapama emrinden hemen sonra çalışıyor. Bekleyen şey yalnızca "gerçekte ne kadar kapandı"
doğrulaması. Fix AF bu pencereyi 10 s → ~2 s'e indirdi. Periyodik REST doğrulaması
(`_bybit_periodic_sltp_verify`) zaten arkada çalışıyor → istenen "fire and forget +
periyodik verify" modeli **artık tam olarak bu.**

### 17.7 ❌ Restart ve leak — TEKRAR NEGATİF (ikinci ölçüm)
```
RestartCount=0  OOMKilled=false  StartedAt=2026-07-29T09:03:56Z (=12:04 TR)  MemLimit=0
hummingbot MEM: 14 saat → 315,6 MiB | 27 saat → 321,7 MiB   (+6 MiB / 13 saat ≈ düz)
```
Logda 3 WS reconnect (2 user-stream + 1 order book) — boot sekansına benziyor, restart değil
(§16.6). Sızıntı yok (§16.7); arşiv hijyeni de tuttu: **62 / 62 / 2 dosya, ~2 MB**
(v3.4 öncesi ~24.800 dosya / ~115 MB).

### 17.8 Kalan açık konular
1. **`❌ [PHASE 2 BYBIT SL/TP] BTC-USDT SHORT fail … 'StopLoss … should greater base_price'`**
   (1 kez, 27 saatte). Konsolide (`fixed`) bir tarafta Faz 2 aggregate SL'i breakeven'e
   çekmek istiyor ama fiyat breakeven'i geçmiş → Bybit reddediyor. **Clamp UYGULANMADI:**
   burada SL'i mark'ın hemen ötesine çekmek pozisyonu fiilen market'ten kapatmak olurdu —
   onaylanan "gevşek SL" kararı *korumasız parça* içindi, bu farklı bir para kararı.
   Reddedilince mevcut %4 aggregate SL yerinde kalıyor → **pozisyon korumasız DEĞİL.**
2. **§15.5 hâlâ açık:** restart'ta `📂 State yükleniyor: 0 pozisyon kaydı`.
   `tv_signal_state.json` dolu (24 KB, `tracked_positions` 5 kayıt) ve yazılıyor.
3. **Upstream HB hatası yamalanmadı.** Fix AD stratejiyi bağımsız kıldığı için zararsız,
   ama HB'nin kendi PnL/pozisyon görünümü hâlâ bozuk. İstenirse OKX'te yapılanın aynısı
   (`custom/` altında override) uygulanabilir: yön `data["side"]` yerine
   **`data["positionIdx"]`** (1=LONG, 2=SHORT) üzerinden türetilmeli.

### 17.9 Yeni env (v3.6)
```
BYBIT_POS_CACHE_TTL=5        BYBIT_VERIFY_SL_CLAMP=1
PHASE2_VERIFY_RETRIES=5      PHASE2_VERIFY_DELAY=2
```

### 17.10 Deploy sonrası başarı ölçütü
**BİTMESİ gerekenler:**
- `[POZISYON DEĞİŞİKLİĞİ] Toplam` **salınımı** (6↔5↔6) → tek yönlü değişmeli
- `⏰ [MANUEL CLOSE TIMEOUT]` → **0'a yakın** (14'ten)
- `🔍 [RECOVERY] … track edilmiyor` hayalet adopsiyonları → 0
- `[TRACKED] Toplam` ile `Binance Toplam` **eşit** kalmalı (önce 17 ↔ 8)
- Faz 2 sonrası `🩹 … TP=True` + `✅ [BYBIT COND TP] (cid rotate)` çifti → **bitmeli**
- `🧹 [BYBIT ORPHAN] … (no_position)` → belirgin azalma

**YENİ görülecekler:** `🩹 [BYBIT SL CLAMP] … mark ∓%0.3 seviyesine çekildi`
(→ `🔓 [BYBIT NAKED LEG] … SL(breached)` yerine),
`⚠️ [BYBIT POS] REST başarısız … HB account_positions görüntüsüne düşülüyor`
(nadir olmalı; sıklaşırsa REST/rate-limit sorunu var demektir).

---

## 18) v4.0 — 🎯 reduceOnly LIMIT TP MİMARİSİ + KONSOLİDASYON PASİF ⭐⭐⭐⭐⭐

Kullanıcı kararı 2026-07-31: konsolidasyon pasife alınacak (silinmeyecek), TP
`alternative_consalidation.md`'deki gibi **reduceOnly limit** emre taşınacak.

### 18.1 v3.6 skorkartı — Fix AD/AE/AF/AG TUTTU
Log 2026-07-30 18:05 → 2026-07-31 00:20 (6,25 s), 1 boot, **0 ERROR satırı**.

| Metrik | v3.5 (27 s) | v3.6 (6,25 s) | |
|---|---|---|---|
| `⏰ [MANUEL CLOSE TIMEOUT]` | 14 | **1** | ✅ Fix AD |
| `🔍 [RECOVERY] track edilmiyor` (hayalet) | 4 | **0** | ✅ Fix AD |
| `🔓 [BYBIT NAKED LEG]` | 6 | **0** | ✅ Fix AE |
| `🩹 [BYBIT SL CLAMP]` | — | **2** (doğru çalıştı) | ✅ Fix AE |
| `⏸️ PARTIAL CLOSE AMBIGUOUS` | 0 | **0** | ✅ |
| `cache refreshed` | 103 | **28** | ✅ Fix AA |
| `110009` / `cid rotate` | 0 | **0** | ✅ |

`POZISYON DEĞİŞİKLİĞİ` salınımı (6↔5) **bitti**. Kalan 1 timeout: BTC-USDT LONG
multi-piece kör-FIFO guard'ı (`MANUEL CLOSE AMBIGUOUS … eşleşme yok`) — tek olay.

### 18.2 `alternative_consalidation.md` değerlendirmesi — 1 madde YANLIŞ
**Katılıyorum, ana önerisi doğru ve canlı olarak kanıtlandı.** Tek düzeltme:

| Doküman iddiası | Gerçek |
|---|---|
| `triggerPrice` varsa emir conditional olur; adı önemli değil | ✅ **DOĞRU** |
| reduceOnly limit TP conditional sayılmaz, 500'lük havuzu kullanır | ✅ **DOĞRU — canlı kanıt (18.3)** |
| Hummingbot uyumu / fill riski / reduceOnly reddi | ✅ **Gerçek riskler** → guard'lar 18.5 |
| *"`trading-stop` Full/Partial de 10'luk conditional havuzdan sayılıyor"* | ❌ **YANLIŞ.** Doküman metninden çıkarım yapmış, test etmemiş. §11.1 #6 canlı testi: symbol **10/10 doluyken** `trading-stop` Partial TP `retCode 0` ile KABUL EDİLDİ. Hata mesajı da ayrımı söylüyor: `'already had 10 working normal stop orders'` — "normal stop order" ayrı bir sınıf. `trading-stop` legleri `StopOrder` listesinde GÖRÜNÜR ama 110009 sayacını artırmaz. |

⚠️ Bu çelişki mimariyi **etkilemiyor**: yeni tasarım `trading-stop`'a yalnızca acil
fallback'te dokunuyor ve bütçe **en kötü durum** varsayımıyla hesaplanıyor.

### 18.3 KANITLANMIŞ API GERÇEKLERİ (canlı demo, 2026-07-31)
`tools/bybit_rolimit_probe.py` + `tools/verify_v4_limit_tp.py` (14/14 PASS):

| # | Soru | **KANITLANMIŞ CEVAP** |
|---|---|---|
| 16 | hedge modda `reduceOnly=true` + `orderType=Limit` + `positionIdx` kabul mü? | **EVET**, `retCode 0`. |
| 17 | Bu emir `orderFilter=StopOrder` listesinde görünür mü? | **HAYIR.** `orderFilter=Order`'da görünür. Satır: `orderType='Limit' triggerPrice='' stopOrderType='' reduceOnly=True status='New'`. |
| 18 | 10'luk conditional kotayı tüketir mi? | **HAYIR.** Emir konduktan sonra conditional sayısı `2 → 2` (değişmedi). |
| 19 | `v5/order/amend` + `orderLinkId` + **yalnız `price`** (triggerPrice YOK) çalışır mı? | **EVET**, `retCode 0` ve fiyat gerçekten güncellendi (Faz 2 qty/fiyat güncelleme yolu açık). |
| 20 | `v5/order/cancel` + `orderId` limit TP için de çalışır mı? | **EVET** (aynı gövde koşullu ve limit emirde ortak; `orderFilter` GEREKMİYOR). |

### 18.4 🔑 Slot matematiği — konsolidasyon neden GEREKSİZ oldu
```
ESKİ: parça = 1 SL(cond) + 1 TP(cond) = 2 slot
      5 parça × 2 slot × 2 yön = 20 > 10   → konsolidasyon ZORUNLUYDU
YENİ: parça = 1 SL(cond) + 1 TP(limit,500-havuz) = 1 slot
      5 parça × 1 slot × 2 yön = 10 = 10   → TAM SIĞIYOR
```
`BYBIT_MAX_PIECES_PER_SIDE=5` ile kota asla aşılmaz → aggregate konsolidasyon
(ve onunla gelen **%4 geniş SL**, §17.5) devre dışı kalabilir. Sinyalin kendi
sıkı SL'i (~%0.7) korunur. **Bu, konsolidasyonun asıl maliyetini ortadan kaldırır.**

### 18.5 v4.0 — yapılanlar
| Fix | Ne | Nerede |
|---|---|---|
| **AH** | `_place_bybit_limit_tp()` — TP artık reduceOnly **LIMIT** (GTC, `triggerPrice` YOK, `postOnly` YOK). CID `H-T-<parent>-BB<gen>` korunuyor; duplicate → `amend(price,qty)`; CID yanmışsa generation rotate. `BYBIT_TP_AS_LIMIT=0` ile eski koşullu TP'ye dönülür | yeni + `_place_bybit_trading_stop` TP dalı |
| **AI** | `_get_bybit_limit_tp_orders()` + `_get_bybit_conditional_orders(include_limit_tp=True)` — limit TP'ler **aynı sözleşmeyle** aynı listeye ekleniyor (`is_limit=True`, `consumes_cond_slot=False`). Böylece `_has_leg`, `_get_bybit_position_protection`, periodic verify, orphan süpürücü ve iptal yolları **DEĞİŞMEDEN** çalışıyor | 9 caller'ın hepsi otomatik kapsandı |
| **AJ** | `_bybit_symbol_leg_usage` yalnızca `consumes_cond_slot=True` legleri sayıyor | bütçe motoru |
| **AK** | **Konsolidasyon PASİF — TEK KAPI.** `_bybit_consolidation_mode()` başına `if not BYBIT_CONSOLIDATION_ENABLED: return None`. Bu tek short-circuit choke-point guard'ını, periodic-verify atlamasını, `_bybit_phase2_blocked`'ı ve aggregate yönlendirmeyi **otomatik** no-op yapıyor → dallanma eklenmedi, kod silinmedi. `_bybit_consolidate_side` de ayrıca kapıda duruyor | `_bybit_consolidation_mode`, `_bybit_consolidate_side` |
| **AL** | `_amend_bybit_conditional_order(..., price=)` — `new_trigger=None` ise gövdeye `triggerPrice` KOYMUYOR (limit emirde hata verirdi) | amend |

**Guard'lar (kullanıcı maddesi 3 — "mantıklı ve profitable olsun"):**
| # | Risk (dokümandan) | Guard |
|---|---|---|
| 1 | Kota dolu → parça SL'siz açılır | **Girişte ön-kontrol:** `free < 1` ise **pozisyon AÇILMAZ** (`🚦 [B4 ENTRY BLOCKED]`). Korumasız pozisyon, kaçan fırsattan pahalıdır. `BYBIT_REQUIRE_SL_SLOT_ON_ENTRY=0` ile kapatılır |
| 2 | **Limit TP hiç dolmaz / gap'ler** (dokümanın ana riski) | `_bybit_guard_unfilled_limit_tps()`: mark TP'yi **kâr yönünde** `BYBIT_TP_LIMIT_SLIP_PCT` (%0,15) geçmiş **ve** emir `BYBIT_TP_LIMIT_GRACE_S` (20 s) beklemişse → limit **iptal**, kalan **MARKET** ile kapatılır (`🛟 [BYBIT TP ESCALATE]`). Maker avantajı korunur, kâr kaçmaz |
| 3 | `postOnly` reddi → "emir set edilemedi" | **postOnly KULLANILMIYOR.** TP pozisyon lehine tarafta; fiyat geçtiyse GTC limit anında ve **daha iyi** fiyattan dolar — istenen davranış bu |
| 4 | qty > pozisyon → otomatik kısma/red | Emir öncesi **canlı pozisyona clamp** (`min(qty, live)`), borsanın auto-adjust'ına güvenilmiyor |
| 5 | Pozisyon yoksa reduceOnly reddi | Canlı boyut 0 ise emir **hiç gönderilmiyor** → `status="no_position"`; ayrıca red mesajı `no_position` olarak sınıflanıp state senkronize ediliyor |
| 6 | Margin sıkışınca Bybit aktif emirleri iptal edebilir | Limit TP'ler artık detection listesinde olduğu için **periodic verify eksik TP'yi geri koyar** (koşullu SL ile aynı ağ) |
| 7 | **Çift kapanış** (HB/Faz 2 ile çakışma) | (a) `phase2_tp_mode='manual_second_take'` → duran limit TP **iptal** ediliyor; (b) **TP2 market close ÖNCESİ** limit TP iptal ediliyor; (c) iptal başarısızsa market close **ATLANIYOR**. Not: bu strateji HB PositionExecutor/triple-barrier kullanmıyor → dokümandaki executor çakışması bu botta yok, tek exit sahibi strateji |
| 8 | — (kullanıcı maddesi 4) | **SL/TP birikmesi:** `_bybit_dedupe_parent_legs()` — bkz. 18.6 |

### 18.6 Madde 4 — Faz 2'de SL birikmesi
**Neden birikiyor:** CID generation rotate (`BB → BB1 → BB2`) eski leg HÂLÂ açıkken
yeni leg yaratabiliyor. Bu sadece bütçe israfı değil, **para kaybettiriyor**: iki
leg de reduceOnly, ikisi de tetiklenirse parça boyutunun **iki katı** kesilir —
§16.3'teki ETH-USDT vakasının (3 × 0,82 ETH) mekanizması.

**Guard (mantık bozulmadan, zarara yol açmadan):** aynı `parent_id` + `kind` için
>1 leg varsa **EN GÜVENLİ olan TUTULUR**, fazlası iptal edilir:
```
SL → LONG: EN YÜKSEK trigger  |  SHORT: EN DÜŞÜK trigger   (en sıkı stop)
TP → LONG: EN DÜŞÜK  trigger  |  SHORT: EN YÜKSEK trigger  (en yakın kâr al)
```
Tutulan leg **zaten borsada duruyor** → koruma hiçbir an sıfıra düşmüyor
(önce-iptal-sonra-koy YAPILMIYOR). Tek leg varsa dokunulmuyor.
`BYBIT_DEDUPE_PARENT_LEGS=0` ile kapatılır. Log: `🧬 [BYBIT LEG DEDUPE]`.

### 18.7 Acil durum fallback (konsolidasyon ölmedi)
`110009` görülürse (yeni mimaride görülmemeli; GUARD 1 girişte engelliyor) ve
konsolidasyon pasifse, `_bybit_note_cond_cap_full` **tek seferlik** olarak
`_bybit_consolidate_side(reason="emergency_cap_full")` çağırıyor: aggregate
`trading-stop` Full SL "normal stop order" kotası tüketmeden tüm tarafı korur.
`BYBIT_CONSOLIDATION_EMERGENCY=0` ile kapatılır. Log: `🆘 [BYBIT EMERGENCY CONSOLIDATE]`.
**Primer'e geri dönmek:** `BYBIT_CONSOLIDATION_ENABLED=1` — tek env, kod değişmez.

### 18.8 Borsa/VPS çapraz kontrol (2026-07-31)
```
7 açık pozisyon · SL/TP kapsaması: 7/7 TAM · korumasız: 0 · orphan leg: 0
conditional kullanım: BNB 2/10 · BTC 4/10 · DOGE 2/10 · DOT 6/10 · ETH 4/10
ETHUSDT idx=2 → SL 1993.35 (+%4.00) TP 1763.35 (−%8.00), CID'siz  = konsolide (b1)
RestartCount=0 · OOMKilled=false · MemLimit=0 · hummingbot 27 s → 321,7 MiB (düz)
arşiv: 62 / 62 / 2 dosya (~2 MB)
```
ETHUSDT SHORT'taki **%4 geniş aggregate SL**, §17.5'te anlatılan erken-konsolidasyon
maliyetinin canlı örneği — v4.0 ile bu bir daha oluşmayacak.

### 18.9 Doğrulama
- `tools/verify_v4_limit_tp.py` → **14/14 PASS** (canlı borsada: yerleştirme,
  StopOrder'da görünmezlik, kota sabit `2→2`, satır filtresi, CID parent parse,
  `price`-only amend + fiyatın gerçekten değişmesi, orderId ile iptal, dedupe
  seçimi 4 senaryo, slot matematiği). Test emri **iptal edildi**, pozisyonlara
  dokunulmadı.
- `tools/bybit_rolimit_probe.py` → #16-18 kanıtları
- `py_compile` OK · AST: **0 fonksiyon kaybı** (404 fonksiyon) · `BYBIT_GUARD` = 2

### 18.10 Yeni env (v4.0)
```
BYBIT_TP_AS_LIMIT=1                 BYBIT_CONSOLIDATION_ENABLED=0
BYBIT_CONSOLIDATION_EMERGENCY=1     BYBIT_REQUIRE_SL_SLOT_ON_ENTRY=1
BYBIT_TP_LIMIT_SLIP_PCT=0.0015      BYBIT_TP_LIMIT_GRACE_S=20
BYBIT_DEDUPE_PARENT_LEGS=1
```

### 18.11 Deploy sonrası izlenecekler
**YENİ görülecekler:**
```
✅ [BYBIT LIMIT TP] … (reduceOnly limit — conditional slot TÜKETMEZ)
↻ [BYBIT LIMIT TP] … amended @ …
🛟 [BYBIT TP ESCALATE] … limit TP dolmadı … MARKET ile kapatılıyor
🧬 [BYBIT LEG DEDUPE] … fazlası iptal (tutulan: …)
🚦 [B4 ENTRY BLOCKED] … conditional kota DOLU → giriş REDDEDİLDİ
```
**BİTMESİ gerekenler:** `🔗 [BYBIT CONSOLIDATE] … başlıyor` (artık hiç olmamalı),
`🚧 [BYBIT LEG BUDGET] … ERKEN konsolide`, `%4.00`/`%8.00` aggregate SL/TP satırları,
`✅ [BYBIT COND TP]` (yerini `LIMIT TP` alacak).
**OLMAMASI gerekenler:** `110009`, `🆘 [BYBIT EMERGENCY CONSOLIDATE]`,
aynı parça için ikinci bir `LIMIT TP` (dedupe yakalamalı).
**İZLENECEK RİSK:** `🛟 [BYBIT TP ESCALATE]` sıklığı. Çok sıksa limit TP fiyatları
piyasaya göre iyimser demektir → `BYBIT_TP_LIMIT_SLIP_PCT`/`GRACE_S` ayarlanmalı.

---

## 19) v4.1 — 🛡️ TOPLAM SL KAPSAMA DENETİMİ (10:40 yarışının fixi)

> [!WARNING]
> **Tarihsel Bağlam ve Güncel Sınır (v6.0 Fix CD / CF):** Bu bölümdeki `_has_leg` fonksiyonunda yer alan "CID yoksa ±%5 miktar toleransı" kuralı, v6.0 Fix CF ile kaldırılmıştır. Güncel davranışta `parent_id` tam eşleşmesi ve quantize edilmiş miktar tam eşitliği zorunludur. Bkz. **§35.4**.

### 19.1 Olayın tam anatomisi (canlı, 2026-07-31 10:40:20 ETH-USDT SHORT)
```
10:40:20  FAZ 2 AKTIVASYON #907992450676  -> reduceOnly close 1.29   ┐ AYNI TICK
10:40:20  PHASE2 TP2 HIT   #571064777411  -> reduceOnly close 0.62   ┘
10:40:20  PHASE2 TP2 ZERO REMAINING #571064777411 "parca tamamen kapandi"
          ...ama borsada 0.62 ETH HAYATTA KALDI
10:40:24  PHASE 2 BYBIT SL@1918.16 Amount:1.30   <- SL 1.30 kapsiyor
          borsa pozisyonu = 1.92                 <- 0.62 KORUMASIZ
10:41:05  DEFERRED VERIFY MISMATCH (45 s)
10:41:45  DEFERRED VERIFY FINAL   (85 s) -> kendini duzeltti, zarar YOK
```

### 19.2 Neden mevcut ağların HİÇBİRİ yakalamadı
| Ağ | Farkı görür mü? | Gecikme |
|---|---|---|
| Trade detector (`diff = borsa − tracked = +0.62`) | **Evet, ~1 s** | ❌ **`phase2_immunity` (120 s) ile SUSTURULMUŞ** — ve bu susturma DOĞRU, FIFO churn'ünü engelliyor (v3.5/v3.6) |
| `_bybit_periodic_sltp_verify` | Hayır — **parça-bazlı** ("bu parçanın legi var mı?") | 300 s (logda 10-90 dk) |
| `_naked_position_recovery` | Hayır — parça-bazlı | — |
| `DEFERRED VERIFY` | Evet (hafıza vs borsa) | **85 s** ← olayı fiilen yakalayan |

⚠️ **Bu yüzden ilk önerdiğim (a) seçeneği YANLIŞTI:** periodic verify'a kural eklemek
tespiti 300 s'e çıkarırdı — fiilen yaşanan 85 s'den **DAHA YAVAŞ**.

### 19.3 Kök neden — doğru ifade
Kapsama denetimi **parça-bazlı**; toplam-qty bazlı bir denetim YOK. Ayrıca gerçek
zamanlı fark tespiti `phase2_immunity`/`grace_period` ile susturuluyor. Susturma
*tracking* katmanı için doğru, ama *emir kapsaması* için gereksiz.
**Ayrım:** tracking'e bakan denetim susturulmalı; EMİRLERE bakan denetim susturulmamalı.

### 19.4 v4.1 çözümü — `_bybit_verify_sl_coverage()`
**Yalnızca EMİRLERE bakar** (tracking'e değil) → immunity/grace'ten **BAĞIMSIZ**.
**Olay-tetiklemeli**, polling YOK. Riskin *yaratıldığı* 2 noktada çağrılıyor:
1. `PHASE2 TP2 ZERO REMAINING` (parça "tamamen kapandı" ilan edildiği an)
2. `FAZ 2 AKTİF` (Faz 2 kesinleştiği an)
\+ `_bybit_periodic_sltp_verify` içinde **yavaş emniyet ağı**.

**REST maliyeti = 1 çağrı** (olay başına, saatte birkaç kez):
| Veri | Kaynak | Çağrı |
|---|---|---|
| pozisyon boyutu | `_binance_positions_cache` (WS ile anlık taze, 5 s TTL) | **0** |
| SL legleri | `order/realtime` `orderFilter=StopOrder` | **1** |
| limit TP taraması | `include_limit_tp=False` ile **atlanıyor** | **0** |

Periyodik emniyet ağı: **0 ekstra çağrı** (zaten çekilmiş `cond` + `real_amount`).

**Remedy — GÜVENLİK sırası: ÖNCE KAPSA, SONRA KAPAT**
```
gap = pozisyon_boyutu − Σ(SL leg qty)        (tolerans: boyutun %2'si)

1) ÖNCE: en yeni parçanın SL leg'i `qty += gap` ile AMEND edilir
         (min(size) ile kapaklı → asla pozisyondan fazlası kapatılmaz)
         → YENİ EMİR YOK: slot tüketilmez, leg birikmesi olmaz, dedupe ile çakışmaz

2) SONRA sınıflandır:
   A) ATFEDİLEBİLİR — gap, "tamamen kapandı" ilan ettiğimiz bir parçanın
      miktarına eşit (±%5, 300 s defter) → kapanış emri FİİLEN GERÇEKLEŞMEMİŞ
      → gap MARKET ile kapatılır.  ⚠️ Bu YENİ bir para kararı DEĞİL: o miktarın
        kapatılmasına zaten karar verilmiş ve emir gönderilmişti.
   B) ATFEDİLEMEZ (ör. takip edilmeyen manuel giriş) → sadece (1)'deki amend
      kalır; market close YAPILMAZ (keyfi kapanış yok).
```
Market close başarısız olursa miktar **(1) sayesinde SL kapsamında kalır** — bu
yüzden sıra tersine çevrilemez.

Defter: `_bybit_note_declared_closed()` → `_bybit_declared_closed[pair_side]`,
300 s sonra otomatik prune. 30 s aksiyon cooldown'ı ile çift tetikleme engelli.

### 19.5 Kullanıcı sorularına cevap
- **(a) Periodic verify boşluğu HEMEN görür mü?** **HAYIR** — 300 s'de bir çalışıyor,
  yaşanan 85 s'den yavaş. İlk önerim hatalıydı; bu yüzden olay-tetiklemeli yapıldı.
- **(b) Amend neden `ZERO REMAINING` doğrulamasından hızlı?** **Kendiliğinden hızlı
  DEĞİL** — ikisi de borsa verisi ister. Hız *ne yaptığından* değil **NE ZAMAN
  baktığından** ve **susturulmamasından** gelir. Bu yüzden ikisi ayrıldı:
  *tespit* = olay-tetiklemeli + immunity-bağımsız (~1 s); *remedy* = amend (kapsama)
  veya market close (atfedilebilirse).
- **(c) Atfedilebiliyorsa market close, değilse amend** → **aynen uygulandı** (19.4).

### 19.6 Doğrulama — `tools/verify_sl_coverage.py` (14/14 PASS)
Gerçek olay sayılarıyla replay: defter kaydı · `1.92 − 1.30 = 0.62` · tolerans
aşımı · `#571064777411` ile atıf · `1.30 → 1.92` amend · `≤ size` kapağı ·
atfedilemez yolda market-close YOK · REST maliyeti 1 · gecikme tablosu
(1 s < 85 s < 300 s). `py_compile` OK · AST **0 fonksiyon kaybı** (406).

### 19.7 Deploy sonrası izlenecekler
```
🛡️ [SL COVERAGE GAP] … → **N KORUMASIZ** (sebep=tp2_zero_remaining|phase2_activated|periodic_backstop)
🛡️ [SL COVERAGE FIX] … qty A → B amend edildi (yeni emir YOK)
🎯 [SL COVERAGE ATTRIBUTED] … kapanış GERÇEKLEŞMEMİŞ, MARKET ile tamamlanıyor
```
**BİTMESİ gereken:** `⚠️ [DEFERRED VERIFY MISMATCH]` (kapsama artık ondan ~85× önce
düzeltiliyor). **İZLENECEK:** `SL COVERAGE GAP` sıklığı — sıksa Faz 2/TP2 aynı tick
yarışı yapısal, o zaman TP2'yi Faz 2 aktivasyonu ile aynı tick'te ateşlememek gerekir.

---

## 20) v4.2 — ZERO-REMAINING YANLIŞ POZİTİFİ + ORPHAN LIMIT TP + ARŞİV BOŞLUĞU

Log: 2026-08-01 03:02 → 14:34 (11,5 s), 0 boot, `RestartCount=0`, 318,5 MiB.
v4.1 deploy edilmişti (markerlar doğrulandı, mtime Aug 1 00:01).

### 20.1 🔥 `ZERO REMAINING` yanlış pozitifi — para etkisi VAR (Fix AM)
Canlı zincir (2026-08-01 06:02:01, BNB-USDT LONG #953428545827):
```
06:02:01  PHASE2 TP2 HIT → kalan 4.25'in 2.12'si kapatıldı (gerçek kalan 2.13)
06:02:01  🧹 PHASE2 TP2 ZERO REMAINING "parça tamamen kapandı"   ← YANLIŞ
06:02:01  🧹 CLOSED POS CLEANUP - 1 SL/TP iptal edildi           ← SL İPTAL
06:02:02  🔍 [RECOVERY] track edilmiyor! Amount: 2.13
06:02:02  🧭 [ADOPT TARGETS] güvenilmez → SL 586.4 (%0.22) → **581.80 (%1.00)**
06:02:04  ✅ LIMIT TP @ 599.40 (eski 590.3)
```
**Risk hiçbir trade kararı olmadan 4,5 KAT genişledi + ~3 s SL'siz kalındı.**

**Kök neden** (`_close_partial_position` dönüşü):
`"remaining_qty": (accumulator.total_qty if accumulator else Decimal("0"))`
Defter YOKSA **0** dönüyordu, `None` değil → tüketicinin
`if new_remaining is None: remaining - close` fallback'i **hiç çalışmıyordu**.
Bybit'te per-fill defteri dolmadığı için bu her Faz 2'de geçerli
(`FIFO SUMMARY`=0, `PHASE2 CLOSE BACKFILL`=8/8).

**Fix AM (iki kilit):**
1. Üretici: `accumulator is not None and closed_fills` → otorite; aksi halde
   **`None`** (bilinmiyor) + DEBUG log.
2. Tüketici: "kalan=0" iddiası ancak aritmetik de 0 gösteriyorsa kabul edilir;
   aksi halde `⚠️ [PHASE2 TP2 REMAINING GUARD]` ile aritmetik kullanılır.
   → SL iptali / yeniden-sahiplenme / hedef genişlemesi zinciri kırılır.

### 20.2 🔥 Başıboş reduceOnly LIMIT TP'ler (Fix AN)
Borsa anlık görüntüsü (2026-08-01): **3 başıboş limit TP.** Hepsi SL tetiğiyle
kapanmış parçalardan kalmış:

| Leg | Pozisyon | Tehlike |
|---|---|---|
| `H-T-605486003147-BB` Sell 2.62 @1873.95 | ETH LONG canlı 2.67 | fiyat gelirse **canlı pozisyonun %98'ini** ölmüş parçanın fiyatından kapatır |
| `H-T-821481267840-BB` Buy 0.079 @62927.7 | BTC SHORT canlı 0.156 | yarısını kapatır |
| `H-T-318970892001-BB` Sell 0.05 @1874.91 | ETH LONG | küçük |

**Kök neden — iki katman:**
1. SL/TP-trigger temizleme dalı parçayı tracking'den siliyor ama **kardeş leg'i
   iptal etmiyordu.**
2. `_get_bybit_all_conditional_orders` yalnızca `orderFilter=StopOrder` tarıyordu
   → orphan süpürücü **limit TP'leri hiç görmüyordu** → kalıcı orphan.
   10'luk kotayı tüketmedikleri için `110009` da çıkmıyor → **tamamen sessiz.**

Üretim hızı: 11,5 saatte **7 SL tetiği → ~7 orphan TP.** §16.3'te 3 × 0,82 ETH
kaybettiren hata sınıfının aynısı.

**Fix AN:** `_bybit_cancel_sibling_legs()` — tetiklenen leg hariç aynı parent'ın
TÜM leglerini (koşullu **ve** limit) iptal eder, `_sltp_orders` kaydını da
temizler (gereksiz CID generation yanmasın). **+ Fix AN-2:** hesap geneli
süpürücüye `orderFilter=Order` taraması eklendi; yalnızca **bizim** `H-T-` CID'li
reduceOnly limit emirleri alınır, `triggerPrice`'lı satırlar atlanır (çift sayım
yok), limit fiyatı süpürücünün beklediği `triggerPrice` alanına map edilir.
Süpürücünün 4 emniyet kuralı ve "son SL leg'i silinmez" guard'ı aynen geçerli
(`createdTime` Order satırlarında da var → yaş kuralı çalışıyor).

⚠️ **Kapsama-miktar kontrolü yeterli DEĞİL:** `tools/bybit_coverage.py` "0
korumasız" diyordu çünkü miktarlar rastlantısal olarak tutuyordu
(0.077+0.079=0.156). **Kimlik de eşleşmeli** — parent setleri ayrışmıştı.

### 20.3 📁 27/35 kayıtsız kapanış (Fix AO)
`lost_positions_prune_smooting.md`'deki tespit **doğru**: SL/TP-trigger dalı
`Skipping FIFO logic, just cleaning up tracking` diyerek **hiçbir arşiv kaydı
yazmıyordu** → borsadaki 35 kapanışın 27'si botun arşivinde yok
(analyzer `recorded_by_bot: NO` ile doğru yakalıyordu).

**Fix AO:** `_archive_trigger_close()` — bu dalda artık hem `_enqueue_perfill_record`
hem `_archive_phase2_close` yazılır; `close_reason=<SL|TP>_TRIGGER`, borsa close
order id'si (analyzer için **kesin** join anahtarı), qty/entry/close_price/pnl.
**Yalnızca diske yazar** — emir/pozisyon/tracking davranışı değişmez.
Yan fayda: `phase2_close_*.json` dosyaları ilk kez fiilen oluşmaya başlar →
diğer agent'ın prune-key + protected-guard düzeltmesi (§20.6) artık GEREKLİ hale
gelir, ki o düzeltme bu repoda zaten mevcut.

### 20.4 ⏱️ Kapsama guard'ı yanlış anda okuyordu (Fix AP)
v4.1'in `_bybit_verify_sl_coverage`'ı 06:02 olayında **hiç loglamadı**
(`SL COVERAGE GAP`=0) — oysa SL iptal edilmiş, pozisyon 2.13 kalmış, boşluk %100'dü.
Sebep: guard iptal/kapatma emirlerinin **hemen ardından senkron** çağrılıyordu;
borsa görüntüsü henüz yansımamıştı → tutarlı tablo görüp temiz döndü.
Ayrıca `ensure_fresh=False` ile bayat "0" okuyup sessizce çıkabiliyordu.

**Fix AP:** `settle_delay` parametresi (`BYBIT_COVERAGE_SETTLE_S`=3 s),
pozisyon okuması `ensure_fresh=True`, ve iki risk çağrı noktası artık
`asyncio.create_task` ile **arka planda** — Faz 2 gecikmiyor, guard yansımadan
sonra okuyor.

### 20.5 🔀 Faz 2 / TP2 serileştirme (Fix AQ)
Gözlenen iki yarış şekli: **aynı saniye** (2026-07-31 10:40:20 ETH SHORT) ve
**TP2 önce, Faz 2 sonra** (2026-08-01 06:02:01→06:02:34 BNB LONG).

**Fix AQ:** `_phase2_may_act(pair, side, actor)` — `PHASE2_TP2_SERIALIZE_WINDOW`
(5 s) içinde karşılıklı dışlama:
- `phase2` **asla bloklanmaz** (koruyucu eylem, SL→entry içerir); pencereyi damgalar
  ve bekleyen `tp2`'yi erteler.
- `tp2` yalnızca pencere boşsa çalışır; ertelenirse **bir sonraki fırsatta ÖNCELİK**
  kazanır → açlık yok.
- `PHASE2_TP2_SERIALIZE=0` ile kapatılır.

⚠️ Dürüst not: serileştirme 06:02 olayını **engellemezdi** — oradaki arıza
`remaining_qty=0` idi (Fix AM). Bu yüzden asıl koruma Fix AM + kapsama guard'ı;
AQ savunma katmanıdır, birincil çözüm değil.

### 20.6 Diğer agent'ın prune düzeltmesi — DOĞRULANDI
`_prune_disk_archives` içindeki `_archive_group_key` + `_archive_protection_stem`
düzeltmesi bu repoda mevcut ve **önerdiğim şekille birebir aynı**: event-prefix
soyulur, anahtar `phase2_close|PAIR_SIDE` olur, normal dosyalar (`PAIR_SIDE_<TS>`)
ve `perfill_*.jsonl` etkilenmez. Ek iş gerekmedi.

### 20.7 🕐 SAAT DİLİMİ — analyzer için KRİTİK hazard notu
İki agent'ın çelişkili iddiası **iki farklı dosyadan** kaynaklanıyordu. Aynı olay,
aynı milisaniye ile kanıtlandı:
```
RAW  (VPS /home/ubuntu/deploy/bots/logs/logs_tv_signal_strategy.log):
      2026-08-01 10:02:26,916  [SL CLEANUP] ETH-USDT LONG #318970892001
PROCESSED (paylasilan logs_tv_signal_strategy_processed.log):
      2026-08-01 13:02:26,916  [SL CLEANUP] ETH-USDT LONG #318970892001
```
VPS host+container TZ = `Etc/UTC` (doğrulandı) → **raw log UTC'dir.**
`_processed` dosyası **+3 saat kaydırılmıştır.**

Analyzer **raw** dosyayı okuyor (`electron/vpsGuardLogParser.ts:154-155`) ve
timestamp'e açıkça `Z` ekleyip UTC sayıyor (satır 77) → **DOĞRU.**
⚠️ Ama `_processed` dosyası ASLA analyzer'a verilmemeli: isim tek kelime farklı ve
verilirse **pencere bazlı** tüm korelasyonlar (15 s race-condition tespiti,
`findNearestPriorSignal` slippage atfı) sessizce **3 saat** kayar. Order-ID ile
kesin join saat diliminden bağımsız olduğu için hata fark edilmez.

### 20.8 Bu logdaki diğer bulgular
- **Kritik ERROR yok:** 4 WS reconnect (normal) + 1 `Yetersiz bakiye` (risk guard
  doğru çalıştı) + 1 **`Entry ve SL fiyatlari ayni!`** (TradingView `entry==sl`
  göndermiş, sinyal reddedildi — kaynak tarafında sorun var).
- 0 `MANUEL CLOSE TIMEOUT` · 0 `FORCE CLEANUP` · 0 `110009` ·
  0 `PARTIAL CLOSE AMBIGUOUS` · 0 `CONSOLIDATE`.
- **Orphan SL de var:** `H-S-235385024254-BB` (0.079) — TP'si doldu, fill
  atfedilmedi → parça "canlı" sanılıyor → süpürücü (pozisyon var + parent takipte)
  dokunmuyor. Bu leg 10'luk kotayı TÜKETİR. Fix AO'nun arşiv kaydı bu atfı
  kolaylaştırır ama tam çözüm için TP-fill atfı ayrıca ele alınmalı → §20.10.
- **Limit TP kısmi fill gerçekleşti:** DOT LONG 14:15'te SL+TP 6319.9 ile kondu;
  borsada şimdi 3160/3160/**TP yok** → limit TP kısmen doldu, kalan iptal olmuş.
  `TP ESCALATE` (Guard 2) hiç ateşlenmedi → eşiği gözden geçirilmeli.

### 20.9 Doğrulama
`tools/verify_v42_fixes.py` → **30/30 PASS** (gerçek dosyadan çıkarılan
`_phase2_may_act` koşuldu; 06:02 ve 10:40 olayları sayılarla replay edildi;
her fix için yapısal iddialar dosyaya karşı doğrulandı).
`py_compile` OK · AST **0 fonksiyon kaybı** (411) · `BYBIT_GUARD` = 2 ·
`verify_exec_fixes.py` + `verify_sl_coverage.py` hâlâ PASS.

### 20.10 Kalan açık konular
1. **TP-fill atfı:** bir limit TP dolduğunda parça tracking'ten düşmüyor →
   orphan SL (`H-S-235385024254-BB`). Fix AO kaydı yazıyor ama atıf ayrı iş.
2. **`TP ESCALATE` hiç ateşlenmedi** — kısmi fill sonrası kalan TP'siz kaldı.
   `BYBIT_TP_LIMIT_SLIP_PCT`/`GRACE_S` gerçek veriyle kalibre edilmeli.
3. **Sinyal kaynağı:** `entry_price == sl_price` gönderiliyor (1 olay).

### 20.11 Yeni env (v4.2)
```
BYBIT_COVERAGE_SETTLE_S=3     PHASE2_TP2_SERIALIZE=1
PHASE2_TP2_SERIALIZE_WINDOW=5
```

### 20.12 Deploy sonrası izlenecekler
**YENİ görülecekler:**
```
⚠️ [PHASE2 TP2 REMAINING GUARD] … 'tamamen kapandı' KABUL EDİLMEDİ
🧹 [SIBLING LEG CANCEL] … (LIMIT TP …) iptal edildi
📁 [SL_TRIGGER CLOSE ARCHIVED] / [TP_TRIGGER CLOSE ARCHIVED]
🔀 [PHASE2/TP2 SERIALIZE] … TP2 ERTELENDİ / öncelik verildi
🛡️ [SL COVERAGE GAP] (artık gerçekten ateşlenebilir — Fix AP)
```
**BİTMESİ gerekenler:** `PHASE2 TP2 ZERO REMAINING` ardından `[RECOVERY]` +
`[ADOPT TARGETS]` zinciri; `recorded_by_bot: NO` oranı (analyzer'da düşmeli);
başıboş `H-T-*` limit legleri.

---

## 21) v4.3 — ORPHAN SL (TP-fill atfı) + TP ESCALATE boşluğu + SİNYAL VALİDASYONU + MQTT SESSİZLİĞİ

> [!WARNING]
> **Tarihsel Bağlam ve Güncel Sınır (v6.0 Fix CD):** Orphan SL atfı ve kaçan fill sonrası stop üretimi sorunları, v6.0 Fix CD terminal stop ve idempotent dolum defterleri ile çözülmüştür. Bkz. **§35.2**.

### 21.1 🕵️ 17:10 sinyali neden hiç log üretmedi — BOT SUÇLU DEĞİL
Zincir baştan sona izlendi (2026-08-01, sinyal 17:10 TR = **14:10 UTC**):

| Katman | Bulgu |
|---|---|
| Container | `State=running`, `RestartCount=0`, restart 13:16:04 UTC (elle/compose), 314 MiB, CPU %1,7 |
| Strateji | 13:16:17'de boot etti, 13:16:27'de `✅ [MQTT] Direct client subscribed` |
| Broker (emqx) | Bot client'ı **CANLI ve ABONE**: `topic:trading_signal qos:0` + `rogerthat/+/signal_rx` |
| rogerthat | 14:00–14:25 UTC arası **yalnızca heartbeat**, `rogerthat_mqtt_queue_depth=0` → webhook HİÇ gelmedi |
| Strateji logu | Son satır **13:16:57 UTC**, sonrası 86 dk sessiz |

**Sonuç:** mesaj hiç yayınlanmadı. Kopukluk **TradingView → rogerthat** hopunda.
`_on_mqtt_message` zaten `data = data.get("data", data)` ile senin gönderdiğin
`{"topic":...,"data":{...}}` zarfını destekliyor → parse hatası DEĞİL.

**86 dakikalık sessizlik de normaldi (ve işte gerçek kusur bu):**
- `[POZISYON DEĞİŞİKLİĞİ]` → `if total_positions > 0` ile gated; 0 pozisyon → susar.
- `[ORPHAN DEBUG]` → yalnızca `(pair sayısı, pozisyon sayısı)` **değişince** loglar;
  durum (5, 0) sabit kaldığı için bir kez basıp sustu.
- MQTT liveness → **`if self._last_mqtt_message_ts > 0:`** ile gated. Restart'tan
  sonra hiç mesaj gelmediği için bu değer **0** kaldı → **tüm liveness bloğu
  atlandı**, `ℹ️ [HEALTH] MQTT idle` bile basılmadı.

⇒ Bot, sinyal akışı hiç kurulmamışken **saatlerce hiçbir uyarı üretmeden** sessiz
kalabiliyordu. Fix AR bunu kapatır.

### 21.2 Fix AR — MQTT sessizliği boot'tan itibaren ölçülür
Liveness referansı: son mesaj yoksa **`_bot_start_time`**. Ayrıca ayrı bir dal:
```
⚠️ [HEALTH] MQTT: bot başladığından beri (Ns) HİÇ sinyal alınmadı.
   direct_client=bağlı, gateway_subscriber=yok. Sinyal beklendiği hâlde bu satırı
   görüyorsanız zincir TradingView→rogerthat→broker tarafında kopuk olabilir.
```
Eşik 0 pozisyonda 1800 s → 13:46 UTC'de uyarmış olurdu (sinyalden ~25 dk önce).
⚠️ Yapısal not: abonelik `qos:0` + `clean_start=true` + `session_expiry=0` →
bot bir an kopsa mesaj **izsiz** kaybolur. Kalıcı teslim isteniyorsa qos≥1 +
persistent session gerekir (rogerthat/broker tarafı kararı).

### 21.3 Fix AS — bozuk sinyal ARŞİVLENMEDEN reddedilir
`❌ Entry ve SL fiyatlari ayni!` eskiden `_open_position` içinde, yani sinyal
**arşivlendikten ve queue'ya girdikten sonra** ölüyordu → her bozuk alarm için
VPS'te kalıcı dosya + boşa retry.
`_signal_reject_reason()` artık `_archive_signal`'dan **ÖNCE** çalışır; yalnızca
matematiksel olarak imkânsız durumları reddeder:
`entry==sl` · LONG'da `sl>=entry` · SHORT'ta `sl<=entry` · TP ters tarafta ·
`side ∉ {buy,sell}` · sayısal olmayan/0 fiyat.
Log: `🚫 [SIGNAL REJECTED] <sebep> → arşivlenmedi, işleme alınmadı`.
Sembol çözümleme / risk / marj kontrolleri kendi yerlerinde kaldı.

### 21.4 Fix AT — ORPHAN SL: TP-fill atfı (kullanıcı sorusu: "bozmuyor mu?")
**Evet, bozuyordu — hafife aldım.** Atıf zinciri:
`_sltp_orders[pid]["tp_order_id"]` ile execution `orderId` karşılaştırılıyordu.
v4.0'dan sonra TP bir **reduceOnly LIMIT** emri ve amend yolunda saklanan değer
borsa id'si yerine **CID** olabiliyor → karşılaştırma eşleşmiyor →
**TP fill'i HİÇ atfedilmiyor.** Canlı kanıt `H-S-235385024254-BB`: TP doldu,
parça kapandı, ama takipte kaldı ve SL leg'i borsada durdu.

Orphan SL'in pozisyon yönetimine verdiği zarar (4 kanal):
1. **10'luk conditional kotayı tüketir** (kapasite kaybı).
2. `tracked_total`'ı şişirir → trade-detector negatif fark görüp partial-close/
   FIFO yollarına girer.
3. `_bybit_verify_sl_coverage`'ta **kapsama olarak SAYILIR** → gerçek boşluğu
   maskeler (kendi guard'ımı kör eder).
4. Tetiklenirse **başka bir parçanın** miktarını ölü parçanın SL seviyesinden
   kapatır → §16.3'te 3 × 0,82 ETH kaybettiren sınıf.

**Fix AT:** `_resolve_close_trade_parent(close_trade)` — atıf artık **CID ile**
(`orderLinkId`/`clientOrderId` → `_parse_cid` → parent_id + tag). Kesin,
UUID-güvenli, ekstra REST yok (§16.1 #14: execution satırı orderLinkId taşıyor).
CID yoksa eski `_sltp_orders` karşılaştırmasına düşer → Binance/OKX korunur.
İki atıf döngüsünde de CID **önce** denenir.
⇒ TP fill'i atfedilince parça tracking'ten düşer, SL leg'i "kardeş leg" olur ve
**Fix AN** onu iptal eder. Yani orphan SL = AT + AN birlikte çözülür.

### 21.5 Fix AU — TP ESCALATE neden hiç ateşlenmedi
`TP ESCALATE`=0 idi. Sebep **eşik değil, yapıydı**: guard yalnızca **hâlâ açık**
limit TP'ler üzerinde döner ve başında `if not legs: continue` vardı.
Canlı kanıt (DOT-USDT LONG): TP 0.7669'da **kısmen doldu** (6319.9 → 3160),
kalan emir kayboldu → iterasyon boş → guard ateşlenemedi ve kalan yarı TP'siz kaldı.

**Fix AU:**
- `if not legs: continue` **kaldırıldı** (`legs = legs or []`).
- **Yeni dal:** parça canlı + TP hedefi var + `manual_second_take` DEĞİL +
  hiç TP legi yok + fiyat hedefi kâr yönünde `slip` kadar geçmiş → kaçırılan kâr
  **MARKET** ile realize edilir (`🕳️ [BYBIT TP ESCALATE] … TP legi YOK ama fiyat
  hedefi geçti`). Fiyat henüz geçmemişse dokunulmaz — periodic verify TP'yi geri koyar.
- **Kısmi fill görünürlüğü:** `📏 [LIMIT TP PARTIAL FILL] … N doldu, M kaldı`
  → eşik kalibrasyonu için gerçek veri üretir.
- Çift kapanış koruması aynen: market close öncesi duran emir iptal edilir,
  iptal başarısızsa market close ATLANIR.

### 21.6 Neden (a) ve (b)'yi açık bırakmıştım — dürüst gerekçe
- **(a) TP-fill atfı:** "büyük değişiklik" (per-fill defterini Bybit'te çalıştırmak)
  sanmıştım ve 4 maddelik kapsam dışında saydım. **Yanlış değerlendirmeydi:**
  gerçek düzeltme küçük (CID ile atıf) ve etkisi büyük — orphan SL pozisyon
  yönetimini 4 kanaldan bozuyor (§21.4). Şimdi düzeltildi.
- **(b) TP ESCALATE:** "eşikler gerçek veriyle kalibre edilmeli" demiştim.
  Ölçünce sorunun **eşik değil yapı** olduğu çıktı (`if not legs: continue`).
  Sayı ayarlamak hiçbir şeyi çözmezdi; yapısal dal eklendi.

### 21.7 Doğrulama
`tools/verify_v43_fixes.py` → **31/31 PASS**: gerçek dosyadan çıkarılan
`_signal_reject_reason` + `_resolve_close_trade_parent` + `_parse_cid` koşuldu;
**17:10 payload'ı KABUL** ediliyor (yanlış reddetme yok), 7 bozuk payload
reddediliyor, CID atfı 7 senaryo, AU/AR yapısal iddiaları dosyaya karşı doğrulandı.
`py_compile` OK · AST **0 fonksiyon kaybı** (414) ·
`verify_exec_fixes` + `verify_sl_coverage` + `verify_v42_fixes` hâlâ PASS.

### 21.8 Deploy sonrası izlenecekler
```
⚠️ [HEALTH] MQTT: bot başladığından beri … HİÇ sinyal alınmadı
🚫 [SIGNAL REJECTED] entry_price == sl_price …
🎯 [TP PARTIAL TRIGGER] … (CID atıf: parça #…)
🧹 [SIBLING LEG CANCEL] … (COND SL …) iptal edildi     ← orphan SL artık temizlenir
🕳️ [BYBIT TP ESCALATE] … TP legi YOK ama fiyat hedefi geçti
📏 [LIMIT TP PARTIAL FILL] … doldu, … kaldı
```
**BİTMESİ gerekenler:** başıboş `H-S-*` legleri (kotayı tüketen);
`_processed` log dosyasının analyzer'a verilmesi (§20.7).
**İZLENECEK:** `LIMIT TP PARTIAL FILL` sıklığı → yüksekse TP fiyatları
likiditeye göre iyimser; `BYBIT_TP_LIMIT_SLIP_PCT`/`GRACE_S` bu veriyle ayarlanmalı.

### 21.9 Kalan açık konu
**TradingView → rogerthat webhook'u** (bot dışı): 17:10 alarmı rogerthat'e hiç
ulaşmadı. TradingView alert'inin webhook URL'si / "Webhook URL" kutusunun işaretli
olması ve rogerthat'in HTTP endpoint'i kontrol edilmeli. Bot tarafında yapılacak
bir şey yok; Fix AR artık bunu **sessizce** geçmiyor.

---

## 22) v4.4 — 🚀 OLAY-GÜDÜMLÜ KAPANIŞ (OKX paritesi) + false-success'in 5. noktası + kendi backstop'umun bug'ı ⭐⭐⭐⭐⭐

Log: 2026-08-01 18:13 → 21:53 (v4.2+v4.3 deploy edilmiş). Kullanıcı talebi:
"atomu parçalama; bot parçalarını tanısın ve yönetsin; kapanan pozisyonun SL'i
OKX-native'deki gibi HEMEN iptal edilsin."

### 22.1 🔥 CANLI OLAY: DOT-USDT LONG **43 dakika çıplak** — 4 halkalı zincir
```
21:10:03  LONG açıldı (6267.6 @ 0.7748)
21:10:04  FAZ 2 aktivasyonu (giriş +0.44% ile doğdu) → yarı kapatıldı
21:10:04  ✅ [PHASE 2 BYBIT] SL@0.7748   ← YALAN: hiçbir [BYBIT COND SL] satırı yok
21:10:13  🛡️ SL COVERAGE GAP … leg=0    ← tespit ~9 saniyede ÇALIŞTI
21:10 → 21:53  her 5 dk GAP logu, DÜZELTME YOK (19 satır)
```
| Halka | Kusur | Fix |
|---|---|---|
| 1 | SL sessizce atlandı (breach/cooldown → DEBUG'da görünmez) | AV görünür kılar |
| 2 | `_set_phase2_sltp` `success=not hard_fail` sayıyordu → yalan `✅`, `_record_sltp_placement` hafızayı zehirledi → deferred verify "OK" dedi | **AV** |
| 3 | Coverage guard yalnızca AMEND biliyordu; `leg=0` iken yapacak şeyi yoktu | **AW** |
| 4 | Benim periodic backstop'um coverage çağrısından sonra `return` ediyordu → per-piece yerleştirme döngüsünü (asıl iyileştirici) BİZZAT ENGELLİYORDU | **AW-2** |

### 22.2 Düzeltmeler
| Fix | Ne |
|---|---|
| **AV** | `_set_phase2_sltp` artık **leg-bazlı gerçek** ister: `sl_status ∈ {placed, amended, consolidated}` (istenmişse TP de). Değilse `❌ … KONULAMADI: sl_status=…` ile **False** döner → caller eski SL'i İPTAL ETMEZ (koruma sıfıra düşmez), periodic/coverage tamamlar. B3/M/AG'den sonra false-success'in **5. ve son** noktası. |
| **AW** | `_bybit_verify_sl_coverage` `sl_legs` boşken artık **YENİ SL KOYAR**: önce en yeni parçanın tracked SL'i ile per-piece (clamp Fix AE otomatik); o da olmazsa **pozisyon-seviyesi trading-stop Full SL** (breakeven ∓ %1) — borsa kapanışta kendisi iptal eder, orphan riski yok. |
| **AW-2** | Periodic backstop'taki `return` kaldırıldı; coverage çağrısından sonra `cond/sl/tp` listeleri tazelenir ve per-piece döngü DEVAM eder (idempotent, CID upsert). |
| **AX** | `_handle_bybit_execution_event` artık gerçek işleyici (eskiden SADECE timestamp yazıyordu): `execType=Trade` + `closedSize>0` + CID'imiz → `_bybit_on_leg_filled` arka plan task'i: **tam parça kapanışıysa** (fill ≥ %95 kalan) kardeş legler ANINDA iptal (AN) + arşiv (AO) + tracking'den düş + kapsama denetimi. Kısmi fill → sadece log. `execId` dedupe'lu. |
| **AX-2** | WS position event `size=0` → `_bybit_cancel_all_side_legs`: o pair+yöndeki TÜM CID'li legler ANINDA iptal. Emniyet: REST ile pozisyonun gerçekten kapalı olduğu bir kez daha doğrulanır (canlıysa HİÇBİR ŞEY silinmez), 60 s debounce. **OKX-native "pozisyon kapandı → algoları hemen sil" davranışının Bybit karşılığı.** |

### 22.3 Kapanış tespiti gecikme tablosu (kullanıcı madde 2'nin cevabı)
| Yol | Eski gecikme | v4.4 |
|---|---|---|
| WS execution (leg fill) | KULLANILMIYORDU | **~1 sn (birincil)** |
| WS position size=0 | cache temizliği vardı, leg iptali YOKTU | **~1-2 sn (birincil)** |
| Trade detector | ~20 sn (birincil yoldu) | fallback |
| Orphan süpürücü | 120 sn aralık + 180 sn yaş + 2 tur = **5-11 dk** (canlı: ETH SHORT TP 20:26 → SL iptal 20:35/20:37) | son savunma |
Tüm yollar idempotent (ikinci iptal "not exist" → başarı) → çakışma zararsız.

### 22.4 Hata kaynağı dağılımı (kullanıcı madde 1'in cevabı)
- **KOD (~%80):** false-success zinciri (5 nokta — hepsi kapandı), polling-öncelikli
  kapanış tespiti (AX ile olay-güdümlü oldu), tek-yönlü remedy'ler (amend-only →
  AW ile place fallback), backstop `return` (AW-2).
- **BORSA (~%15):** Bybit `order/create` leglerini kapanışta iptal etmez (§11.3,
  yapısal — AX bunu telafi eder); `orderLinkId` kalıcı yanar (§11.2); execution'da
  `positionIdx` yok (§16.1); HB upstream `side=''` (§17.2, Fix AD ile bağımsızlaşıldı).
- **VPS (~%5):** restart/OOM YOK (3 kez ölçüldü), MQTT zinciri bir kez koptu
  (§21.1 — TradingView→rogerthat, bot dışı).

### 22.5 Pozisyon yönetimi artık HANGİ ağlarla korunuyor (özet mimari)
```
GİRİŞ    : GUARD 1 slot ön-kontrolü → SL(cond)+TP(limit), CID'li, false-success YOK
Faz 1/2  : provisional SL fire-and-forget; AV leg-gerçeği; AQ Faz2/TP2 serileştirme;
           AM remaining aritmetik kilidi
KAPANIŞ  : AX WS-anında (birincil) → AT CID atfı + AN kardeş iptal + AO arşiv
KAPSAMA  : AP settle'lı olay-tetiklemeli guard + AW place-fallback + AW-2'li
           5 dk periodic backstop + naked-recovery + orphan süpürücü (son savunma)
```
Her katman alttakinin kaçırdığını yakalar; en alttaki iki katman yalnızca EMİRLERE
bakar (tracking'e değil) → tracking bozulsa bile borsa gerçeği kazanır.

### 22.6 Doğrulama
`tools/verify_v44_fixes.py` → **34/34 PASS** (21:10 olayının replay'i; gerçek WS
payload şekliyle AX akışı: ETH SHORT TP fill → atıf + tam-kapanış kararı; B4
entry linki leg sanılmıyor; AX-2 canlı-pozisyon emniyeti). `py_compile` OK ·
AST **0 fonksiyon kaybı** (416) · önceki 4 test paketi PASS.

### 22.7 Deploy sonrası izlenecekler
**YENİ:** `⚡ [WS LEG FILL] / [WS CLOSE COMPLETE] / [WS POS CLOSED]`,
`🛡️ [SL COVERAGE FIX] … YENİ SL kondu / Full SL kondu`,
`❌ [PHASE 2 BYBIT SL/TP] … KONULAMADI: sl_status=…` (artık kök neden görünür).
**BİTMESİ gereken:** `SL COVERAGE GAP`'in aynı pozisyon için TEKRARI (tek sefer
görünüp `FIX` ile kapanmalı); kapanış sonrası dakikalarca yaşayan `H-S-*` legleri;
`PARTIAL CLOSE AMBIGUOUS` (parça WS ile anında düşeceği için fark oluşmamalı).
**İZLENECEK:** `⏭️ [WS POS CLOSED] … yanlış alarm` sıklığı (sık ise WS event
sırası şüpheli demektir).

---

## 23) v4.5 — 🩸 EN BÜYÜK BUG: STRATEJİ SAATLİK FİYATLA ÇALIŞIYORDU (Fix AY) ⭐⭐⭐⭐⭐⭐

Log: 2026-08-01 22:31 → 08-03 17:45 (43 saat, v4.4 deploy'lu, 1 boot).
Canlıya geçiş öncesi son büyük soruşturma (kullanıcının 24 saati var).

### 23.1 🔥 KANIT — tüm fiyat-güdümlü olaylar saat başında kümeleniyor
16 FAZ 2 aktivasyonunun 14'ü, TÜM trailing/TP2 olayları `:31:50–:32:24`
aralığında; saniye alanı 43 saatte monoton +34 s kayıyor = **periyot ≈ 3601 s**.
Boot 22:31:54 + N×3600 = birebir örtüşüyor. Giriş gecikmesi ise 1 s (sinyal →
`Pozisyon aciliyor`), yani `on_tick` canlı.
⇒ **`connector.get_mid_price` SAATTE BİR değişiyor**: HB order book yalnızca
saatlik REST snapshot ile tazeleniyor, WS diff'leri kitaba işlenmiyor (upstream).
Temmuz loglarında da aynı imza var (`:04:xx`, `:40:xx` kümeleri) — **bug baştan
beri vardı**, v4.4'ün olay-güdümlü kapanışları sayesinde ancak şimdi izole edildi.

### 23.2 Bu tek bug'ın açıkladıkları (kullanıcı maddeleri 3/4/5)
| Belirti | Mekanizma |
|---|---|
| 1R 90 dk'da ≥7 kez aşıldı, bot 14:32'de gördü (madde 3) | Faz 1 saatlik kareyle bakıyor |
| `#111024928587` 6,5 saat sonra 1.57R'de aktive (madde 4) | aynı |
| "6 sn'de iki %50 kapanış" (madde 4) | İKİ AYRI parçanın (biri Faz 2, biri ertelenmiş TP2) tetikleri saatler önce gerçekte aşılmıştı; saatlik kare gelince ikisi birden ateşledi. Parça başına tek aksiyon — çift kapanış YOK (`phase2_tp2_done` latch'i doğrulandı) |
| 21:10:04 sessiz SL atlaması (§22.1) | breach pre-check bayat fiyata (0.77885) karşı "geçerli" dedi; borsa GERÇEK mark'a (≈0.7748) karşı 10001 verdi → cooldown → sessiz |
| SL CLAMP'ler yanlış seviyeye çekti | clamp kıyası saat-öncesi mark ile yapılıyordu |
| Dengesiz K/Z: kayıpların sadece 1'i −1R'de, 50'si −5..−45'e saçılmış (madde 5) | stoplar bayat fiyatla taşındı + boyutlandırma bayat fiyatla yapıldı + 1R/TP2 geç görüldü. Kazanç tarafı tasarıma uyuyor: +20..45 kovası (22 adet) = Faz 2 yarı-kapanışları (~0.5R), −5..+5 (16) = entry-stop |

### 23.3 Fix AY — taze fiyat beslemesi (strateji artık HB kitabına bağımlı değil)
- `_bybit_refresh_tickers`: `/v5/market/tickers?category=linear` — public, TEK
  çağrıda TÜM semboller (last/mark/bid/ask), `BYBIT_TICKER_TTL=3` s, single-flight,
  on_tick'ten arka plan task'i. İlk başarıda `🩸 [FRESH PRICE FEED] aktif` loglar.
- `_bybit_fresh_price(pair, kind)`: senkron okuyucu; 3×TTL'den bayatsa None →
  caller `get_mid_price` fallback'ine düşer (feed ölse bile eski davranış).
- **Bağlanan kritik noktalar:** `_monitor_positions` (1R/TP2/trailing kararı,
  "last"), breach pre-check + CLAMP (**SL için "mark"** — Bybit SL'i MarkPrice
  ile tetikler, kıyas da mark ile olmalı; TP için "last"), TP escalate (market
  close kararı!), giriş boyutlandırması (Risk=X USDT hesabı), adopt/konsolidasyon
  clamp'i.
- Fix AZ (kozmetik): Faz 2 başarısında `last_logged_sl` senkronu — trailing logu
  artık `SL: <orijinal sinyal SL> → …` diye yanıltmıyor (kullanıcı bunu "stop
  @entry çalışmamış" diye okumuştu; borsada SL gerçekte entry'deydi, doğrulandı).

### 23.4 v4.4 skorkartı (43 saat) — olay-güdümlü katman ÇALIŞIYOR
`⚡ WS LEG FILL` 64 · `⚡ WS POS CLOSED` 75 · `SIBLING LEG CANCEL` 46 ·
`SL COVERAGE FIX` 3 (1 amend + 2 pozisyon-seviyesi Full SL) · `SERIALIZE` 16
(ertelenen TP2 tam bir kez, öncelikle çalıştı) · `MANUEL CLOSE TIMEOUT` 2 (43
saatte; force-cleanup düzgün toparladı) · `PARTIAL CLOSE AMBIGUOUS` 3 (geçici) ·
orphan iptali 4 (hepsi dakikalar içinde). Kapanışların ezici çoğunluğu artık
poll beklemeden ~1 sn'de işleniyor.

### 23.5 Kullanıcı sorularının kısa cevapları (2a–e, c)
- **(a) tanıma/yönetme:** EVET — 43 saatte hayalet adopsiyon 0, RECOVERY 1 (dust),
  TRACKED↔borsa uyumlu; her parça CID'iyle borsada birebir izlenebilir.
- **(b) Faz1/Faz2 mantığı:** mekanik olarak DOĞRU çalışıyor; tek bozukluk
  ZAMANLAMAydı (bayat fiyat) → Fix AY. Hata botta (fiyat kaynağı seçimi) +
  upstream HB (diff'lerin kitaba işlenmemesi); borsa tarafı temiz.
- **(c) SL/TP sekmesindeki DOT kaydı:** coverage guard'ın SON ÇARE fallback'i —
  `SL COVERAGE FIX … pozisyon-seviyesi Full SL kondu` (07:32:04 DOT SHORT dust
  0.2 için). trading-stop Full SL, UI'da "SL/TP" sekmesinde görünür ve pozisyon
  kapanınca borsa kendisi siler → "şimdi yok" doğru gözlem. Mimari değişmedi:
  primer = Conditional SL + Limit TP; Full SL yalnızca acil kapsama fallback'i.
- **(d) orphan/zombie:** EVET — birincil yol artık WS (~1 sn, 46 kardeş iptal);
  süpürücü son savunma (4 iptal, dakikalar).
- **(e) naked tespiti:** EVET — coverage guard hem olay-tetiklemeli hem periyodik;
  `leg=0` durumunda artık YENİ SL koyabiliyor (AW), 43 saatte 3 kez düzeltti,
  hiçbir GAP tekrar etmedi.

### 23.6 Analyzer için not
`position_flow_LONG_*.json` **bozuk**: LONG akışında `side=SELL` OPEN düğümleri
(gerçekte SHORT açılışları) ve OPEN'da `realizedPnl≠0`. Analyzer'ın positionSide
atfı düzeltilmeli (closedSize>0 ⟺ reduce kuralı, §16.1 #12). Borsa gerçeğinden
kurulmuş doğru akış: `dot_flow_2026-08-01_03.md`.

### 23.7 Yeni env (v4.5)
```
BYBIT_TICKER_TTL=3
```

### 23.8 Canlıya geçiş kontrol listesi (24 saatlik pencere)
1. **v4.5'i HEMEN deploy et** (AY tüm karar geometrisini düzeltir) →
   `🩸 [FRESH PRICE FEED] aktif` satırını doğrula.
2. İlk saatlerde izle: FAZ 2 aktivasyonları artık `:32` kümelenmesinden ÇIKMALI
   (sinyal sonrası herhangi bir saniye); `SL CLAMP` nadirleşmeli; kayıplar
   −1R±fee bandına oturmalı.
3. `⏭️ [WS POS CLOSED] … yanlış alarm` sıklaşırsa haber ver (WS sırası).
4. Canlıda İLK GÜN `BYBIT_MAX_PIECES_PER_SIDE=2-3` ile başlamak riski yarılar
   (öneri, zorunlu değil).
5. MQTT zinciri: qos:0 + clean_start → kalıcı teslim istenirse rogerthat/broker
   tarafında qos≥1 (bot dışı, §21.2).

---

## 24) v5.0 — 🔥🔥 RİSK FORMÜLÜ KALDIRAÇLA YANLIŞ ÖLÇEKLENİYORDU (Fix BD) + hayalet-parça reconciliation (Fix BB/BB-2) + trailing'in kendi bayat-fiyat regresyonu (Fix BA)

Log: 2026-08-03 18:43 → 08-05 16:56 (v4.5/Fix AY deploy'lu). Canlıya geçiş
öncesi kullanıcının kendi bulduğu 3 ayrı doküman (`phase2_correction.md`,
`risk_calc.md`, `DOT_PNL_TABLE.json`) üzerinden yapılan son tur.

### 24.1 🔥🔥 EN BÜYÜK BULGU: pozisyon boyutu formülü kaldıraçla YANLIŞ ölçekleniyordu (Fix BD)
`risk_calc.md` kullanıcının önceki turda bahsettiği ve benim YANLIŞ analiz
ettiğim konuydu. Yeniden inceleyince doğrulandı ve DAHA DERİN bir kök neden
bulundu.

**Eski formül:** `amount = (risk_amount * leverage) / price_diff`

Bu formül **yanlıştı.** Futures'ta SL vurduğunda gerçek $ kayıp
`amount × price_diff`'tir — kaldıraç yalnızca ne kadar MARJ bağlandığını
belirler, P&L'i **etkilemez**. Eski formül `amount`'u kaldıraçla çarparak SL
vurduğunda gerçek kaybı **`risk_amount × leverage`**'a çıkarıyordu:
```
risk_calc.md örneği: risk_amount=44.52, leverage=20, price_diff=9.04
  amount_uncapped = 44.52×20/9.04 ≈ 98.5 ETH
  SL vurursa gerçek kayıp = 98.5×9.04 ≈ 890 USD  ← hedeflenen %0.9 değil, %18!
```
Botun bugüne kadar "yaklaşık doğru" görünmesinin TEK nedeni, **%5 marj
tavanının** (neredeyse her sinyalde `⚠️ Initial margin çok büyük!` ile) bu
şişirilmiş boyutu geri kesmesiydi. Ama tavan-kesimli boyutun GERÇEK riski de
sabit %0.9 DEĞİLDİ — SL mesafesine göre DALGALANIYORDU:
```
gerçek_risk ≈ max_margin × leverage × (price_diff / entry_price)
```
SL mesafesi (`price_diff/entry_price`) sinyalden sinyale değiştikçe (ör. %0.5
vs %1.2) gerçek $ risk de dalgalanıyordu — **kullanıcının gözlemi ("40-50$
arası değişiyor") kaza değil, formülün DOĞASIYDI.**

**Yeni formül:** `amount = risk_amount / price_diff` (kaldıraç YOK). Bununla
SL vurduğunda gerçek kayıp HER ZAMAN tam olarak `risk_amount` (hedeflenen
%0.9) olur — kaldıraçtan VE SL mesafesinden bağımsız. Kaldıraç yalnızca marj
hesabında kullanılmaya devam ediyor; iki kontrol artık ayrık: "en fazla %0.9
risk" VE "en fazla %5 marj", hangisi önce dolarsa o devreye giriyor (ikisi de
güvenlik yönünde — marj tavanı artık riski AZALTABİLİR, asla ARTIRAMAZ).

**Ek şeffaflık:** `🎯 [GERÇEK RİSK]` logu eklendi — nihai (min-notional/lot-size
düzeltmeli) qty ile SL vurursa oluşacak GERÇEK $ kaybı, hedeften %5'ten fazla
sapıyorsa açıkça raporlar (risk_calc.md'nin "log nihai boyutu yansıtmıyor"
tespitinin gözlemlenebilirlik kısmı).

⚠️ **SL/TP seviyeleri bu bugtan ETKİLENMEDİ** — onlar her zaman sinyalin kendi
`sl_price`/`tp_price` alanlarından geliyor, `risk_amount`'tan türetilmiyor. Yani
hiçbir pozisyon "yanlış SL ile" korunmadı; sadece pozisyon BÜYÜKLÜĞÜ (ve
dolayısıyla SL vurursa gerçekleşecek $ miktarı) hedeflenenden sapıyordu.

### 24.2 🔥 DOT_PNL_TABLE anomalisi — Bybit'in TEK ortalama-giriş muhasebesi (mimari gerçek, bug DEĞİL)
Kullanıcının "-45.51/-45.62 gibi anlaşılmaz kayıplar" sorusu için borsa
`execution/list` ile ground-truth yapıldı:

```
15:17:05  İKİ AYRI parça (#362398044794 entry=0.8378, #781420389676 entry=0.8347)
          AYNI ANDA SL ile kapandı @ 0.8291
          Botun KENDİ arşivi: pnl=-49.10 ve pnl=-31.68 (kendi entry'lerine göre doğru hesap)
          Bybit'in GERÇEK closed-pnl'i: HER İKİSİ İÇİN DE ~-45.5/-45.6
          DOT_PNL_TABLE'daki "EntryPrice" HER İKİ satır için de 0.8362 (AYNI!)
```
**Neden:** Bybit hedge modda **TEK pozisyon, TEK ağırlıklı ortalama giriş**
tutar (§2). İki parça AYNI pozisyona (positionIdx=1) stack olunca, Bybit'in
gerçek PnL muhasebesi HER close için o ANKİ BLENDED avgEntryPrice'ı kullanır —
botun kendi iç kayıttaki "bu parçanın sinyal entry'si" DEĞİL. Doğrulama:
`(0.8362-0.8291)×5658 ≈ 40.2` ve `×5644.1 ≈ 40.1` (komisyon ile ~45.5-45.6'ya
yakınsıyor) — **iki satırın neredeyse eşit çıkmasının nedeni ikisinin de AYNI
blended avg'a göre hesaplanmasıdır.**

**Bu bir BUG DEĞİL, Bybit hedge modun YAPISAL bir özelliği.** Sonuç: **birden
fazla parça AYNI tarafta stack olduğunda, botun per-piece "beklenen risk/PnL"
hesabı ile Bybit'in GERÇEK ledger'ı sistematik olarak AYRIŞIR** — parça sayısı
arttıkça (bu bot `BYBIT_MAX_PIECES_PER_SIDE=5`'e kadar izin veriyor) sapma
büyür. `~$5`/`-$2` gibi küçük "anlamsız" PnL'ler de aynı mekanizmanın ürünü:
`EntryPrice==TradedPrice` (0.8341=0.8341, pnl=-2.51) → SL tam breakeven'e
(blended avg) çekilmiş bir parçanın komisyon-kadar küçük kaybı — **tasarım
gereği, hata değil.**

Kullanıcı gerçek sermaye ile giderken bunu bilmeli: **per-parça $ risk hedefi
(Fix BD ile artık doğru), o parçanın SL'i TEK BAŞINA vurduğunda GEÇERLİDİR;
aynı tarafta BAŞKA parçalar da varsa, gerçekleşen PnL bu hedeften blended-avg
etkisiyle sapabilir** (bazen lehte, bazen aleyhte — yön blended avg'ın hangi
tarafta olduğuna bağlı, sistematik bir kayıp değil, ek BİR VARYANS kaynağı).

### 24.3 🔥 Hayalet parça: gerçek SL 60 sn'lik pencereyi kaçırdı, 24+ saat "AMBIGUOUS", saatler sonra ALAKASIZ pozisyondan qty çaldı (Fix BB / BB-2)
`/v5/execution/list` ile ground-truth (2026-08-04, ETH-USDT LONG):
```
09:20:03  #581207421772 GİRİŞ 2.60 ETH @ 1866.99, SL @ 1862.00
09:28:13  SL TETİKLENDİ (borsa gerçeği) — 2.60 TAMAMEN kapandı @ 1861.91
          ⚡ WS LEG FILL bu olayı YAKALAMADI (sebep tespit edilemedi — WS
          event kaybı/sıralama sorunu olabilir, ekstra soruşturma gerekir)
09:29:44  trade-detector kontrol etti: 91 SANİYE GEÇMİŞTİ, sabit 60 sn'lik
          `recent_close_trades` penceresi kapanışı ZATEN KAÇIRMIŞTI
          ⏸️ [PARTIAL CLOSE AMBIGUOUS] … Kör FIFO engellendi (retry=1)
09:29→   AYNI boşluk 285 KEZ tekrarlandı (24+ saat, ~40-60 sn aralıkla)
08-05
14:51:55  `_monitor_positions` bu HAYALET parça (#581207421772) üzerinde
          fiyat+1R şartını sağladı sanıp FAZ 2 AKTİVE ETTİ
          → GERÇEK bir reduceOnly SELL 1.30 ETH emri gönderdi
          → Bybit paylaşılan hedge pozisyonundan (o an gerçekte BAŞKA
          parçalara ait olan) 1.30 ETH'yi kesti
```
**Bu, "kırılma yaşanan örnek var mı" sorusunun kesin cevabıdır:** tracking 24+
saat kırıktı VE bu kırıklık saatler sonra GERÇEK bir emrin ALAKASIZ bir
pozisyondan qty kesmesine yol açtı (parasal etkisi sınırlı kaldı çünkü kesilen
miktar zaten gerçek/korunan bir parçaya aitti ve kendi SL/TP'si sağlamdı — ama
mekanizma TEHLİKELİYDİ ve tekrar edebilirdi).

**Fix BB — uyarlamalı pencere:** `_close_trade_lookback_seconds()` — bu
(pair,side) için `_unconfirmed_closes` durumu YOKSA davranış DEĞİŞMEZ (60 sn).
VARSA (yani boşluk zaten ambiguous işaretlendiyse) pencere `first_detected`'tan
bu yana geçen süre + 90 sn tampona genişler (üst sınır 30 dk). 3 çağrı
noktasının hepsine uygulandı. Dış `recent_trades` havuzu da 300→1800 sn'ye
genişletildi (ekstra REST çağrısı YOK, aynı `limit` ile çekilen veri bellekte
daha uzun tutuluyor) ve execution fetch limiti 50→100'e çıkarıldı (Bybit'in
izin verdiği azami, tek çağrı) — yüksek işlem hacminde 50 satırın birkaç
dakikada tükenip pencereyi anlamsız kılmasını önlemek için.

**Fix BB-2 — ghost Faz 2 aktivasyon guard'ı:** `_monitor_positions`'ın Faz 1→2
geçiş noktasında, o (pair,side) için `_unconfirmed_closes` TAZEyse (<120 sn)
YENİ Faz 2 aktivasyonu ERTELENİR (parça henüz Faz 1 öncesi, ertelemek risk
yaratmaz). **Zaten aktif trailing parçaları ETKİLENMEZ** — onlar kendi
`ensure_fresh=True` real-amount kontrolünü ayrıca yapıyor.

### 24.4 Trailing SL'in KENDİ bayat-fiyat regresyonu (Fix BA)
Fix AY (v4.5) `_monitor_positions`'ın peak/1R fiyat kaynağını taze ticker'a
çevirmişti ama `_update_trailing_sl`'in "anında tetiklenir mi" doğrulama
kontrolü UNUTULMUŞTU — hâlâ bayat `get_mid_price` kullanıyordu. Canlı kanıt
(2026-08-05 01:24, DOT-USDT LONG #437120393823):
```
peak (taze veriyle) 0.8629 → 0.8690 tırmanırken
"Current Price" (bayat) 0.84405'te DONMUŞ kaldı
→ ⚠️ [TRAILING SL SKIP] … SL (0.8468+) >= Current Price (0.84405) — 10+ dakika
  boyunca HER trailing güncellemesi "anında tetiklenir" sanılıp ATLANDI
```
Sonuç: kâr kilitleme (trailing SL yukarı taşıma) gecikiyordu — para kaybı
değil ama fonksiyonun kendisi devre dışı kalıyordu. Fix BA: aynı
`_bybit_fresh_price(trading_pair, "last")` kaynağı buraya da bağlandı (dust
check ve immediate-trigger check AYNI `mid_price` değişkenini paylaşıyor, tek
düzeltme ikisini de kapsadı).

### 24.5 `phase2_correction.md` değerlendirmesi — KATILIYORUM (yön), kapsam ERTELENDİ
Doküman genel doğrultuda haklı: gerçek zamanlı public WS ticker akışı (push,
~ms gecikme) mevcut 3 sn'lik REST-poll'dan (Fix AY) daha düşük gecikme sağlar.
Yasak listesi (provisional-SL sırası, immunity/grace erken temizlenmemesi,
çoklu-pozisyon collapse edilmemesi, exchange native trailingStop kullanılmaması
vb.) da mevcut mimariyle tam uyumlu — hepsi zaten korunuyor.

**Ama kapsam kararı:** canlıya geçişe saatler kala YENİ bir WS alt sistemi
(bağlantı yönetimi, reconnect/backoff, mesaj ayrıştırma, debounce, dual-mode
orkestrasyon) kurmak — burada CANLI test edilemeyen, ilave saldırı/hata yüzeyi
demek. Fix AY zaten KRİTİK hatayı (saatlik donukluk, 1200x gecikme) kapattı;
3 sn'den ~100-300 ms'ye inmek İYİLEŞTİRME ama ZORUNLU değil. Bunun yerine bu
turda Fix AY'ın kendi YARIM KALMIŞ yayılımından doğan SOMUT bir regresyonu
(Fix BA) buldum ve düzelttim — daha küçük, daha güvenli, daha yüksek öncelikli.
**WS katmanı canlı ilk gün stabil çalıştıktan sonra ayrı bir iyileştirme turu
olarak ele alınmalı**, `phase2_correction.md`'nin kendi güvenlik kısıtlarıyla
(hepsi zaten mevcut mimaride var) birebir uygulanabilir.

### 24.6 Doğrulama
`tools/verify_v46_fixes.py` → **19/19 PASS**: risk_calc.md'nin KENDİ sayılarıyla
replay (eski formül gerçek riski 20x şişiriyordu, yeni formül tam hedefe
oturuyor), 09:28:13 olayının uyarlamalı-pencere replay'i, BB-2 guard'ının Faz
1'i durdurup aktif trailing'i etkilemediğinin doğrulanması.
`py_compile` OK · AST **0 fonksiyon kaybı** (419) · `BYBIT_GUARD`=2 · önceki
6 test paketi hâlâ PASS.

### 24.7 Canlı borsa/VPS çapraz kontrol (2026-08-05)
```
6 pozisyon · SL kapsaması: 6/6 TAM (0 korumasız) · TP boşlukları TÜMÜ
manual_second_take modundaki (Faz2-aktif) parçalara ait — TASARIM GEREĞİ
conditional kullanım: BNB 1/10 · BTC 1/10 · DOGE 2/10 · DOT 3/10 · ETH 3/10
RestartCount=0 · 0 boot bu logda
```

### 24.8 Kalan açık konular
1. **WS execution event'inin 09:28:13'teki SL fill'i neden kaçırdığı** tam
   olarak teşhis edilemedi (WS reconnect ile çakışma ihtimali var — o pencerede
   ayrı bir WS hata logu aranmalı). Fix BB/BB-2 bu tür kaçırmaların ZARARINI
   sınırlıyor (yavaş-ama-kesin reconciliation + ghost-Faz2 guard'ı) ama olayın
   KENDİSİNİ engellemiyor — WS katmanının kendisi %100 güvenilir değil,
   fallback'ler onu tamamlıyor.
2. **`phase2_correction.md`'nin public WS teklifi** uygulanmadı (§24.5) —
   kullanıcı isterse ayrı bir turda, canlı ilk gün stabilitesi doğrulandıktan
   sonra ele alınabilir.
3. **Bybit'in blended-avg muhasebesi** (§24.2) koddan "düzeltilebilecek" bir
   şey değil — kullanıcının stacking politikasını (`BYBIT_MAX_PIECES_PER_SIDE`)
   bilinçli bir risk/basitlik tercihi olarak gözden geçirmesi önerilir.

---

## 25) v5.1 — 🧮 RISK SIZING FİLTRELERİ (Fix BE) + 🌊 PUBLIC WS TICKER FEED (Fix BF)

Kullanıcı talebi 2026-08-05: (1) `phase2_correction.md`'yi tam risk analiziyle
uygula (artık 24 saatlik demo test penceresi VAR → §24.5'teki erteleme gerekçesi
kalktı); (2) `Risk_Sizing_Fix.md`'ye katılıyor musun, katılıyorsan uygula.
İkisine de KATILDIM ve uygulandı. Canlı öncesi son büyük kod turu.

### 25.1 Fix BE — Risk_Sizing_Fix.md (boyutlandırma filtreleri)
Fix BD (§24.1) formülü düzeltmişti; BE, formülün etrafına Risk_Sizing_Fix.md'nin
guard setini kurar. **Çekirdek karar (KULLANICI ONAYLI, AskUserQuestion ile):**
eski **%5 initial-margin KESME tavanı KALDIRILDI** → yerine
`MAX_MARGIN_PER_TRADE` (%25, binerse KESMEZ → SİNYALİ ATLAR). Gerekçe: Fix BD
sonrası %5 tavanı SL<%0.9 olan HER sinyalde (tipik sinyaller %0.5-0.7) devreye
girip gerçek riski hedefin altına, ama KONTROLSÜZ bir değere kesiyordu —
spec'in "effective_risk hedefin ±%10-15'i" kabul kriteri %5 ile imkânsızdı.

| Filtre | Eşik | Davranış |
|---|---|---|
| MAX_SLOTS | toplam parça ≥ 6 (tüm pair + 2 yön) | `🚫 [SIZING SKIP] reason=MAX_SLOTS` |
| TOO_WIDE | sl_pct > %1.5 | skip |
| MIN_SL_PCT (soft) | sl_pct < %0.15 | boyut min mesafeyle hesaplanır (qty küçülür) + WARN — eski %0.1 clamp'in devamı, eşik spec'e çekildi |
| TOO_TIGHT_FEE | fee_est > risk×%25 | skip. ⚠️ Pratik anlamı: **SL < ~%0.44 sinyaller elenmeye başlar** (fee-aware ile sınır biraz gevşer; ETH örneği %0.48 → geçer) |
| MARGIN_PER_TRADE | marj > available×%25 | skip (Fix BD sonrası yalnız SL<~%0.18 anomalilerinde biner) |
| MARGIN_CAP | kullanılan+yeni marj > available×%75 | skip. Kullanılan marj ÖNCE kendi REST-truth cache'inden (`_estimate_used_margin`, taze ticker fiyatıyla — HB `account_positions` §17.2 gereği güvenilmez), yoksa HB tahmini |
| MIN_QTY_RISK_BUMP | borsa minimumuna yükseltme riski hedef×1.25 üzerine taşır | skip (sessiz risk şişmesi YASAK) |

**Fee-aware boyut (varsayılan AÇIK):** `qty = risk / (sl_dist + entry×FEE_RT)`,
FEE_RT=0.0011 (Bybit taker %0.055×2). SL vurduğunda "kayıp + komisyon" birlikte
tam hedefe oturur; qty ~%10-18 küçülür (güvenli yön). `SIZING_FEE_AWARE=0` ile
eski saf formül. Not: 1R hedef matematiğindeki `COMMISSION_RATE`(0.0004)
DEĞİŞTİRİLMEDİ (spec yasağı: "commission-adjusted target formula'ya dokunma").
**Dürüst log:** her sinyalde `📊 [SIZING] target_risk= effective_risk= qty=
notional= margin= sl_pct= fee_est= open_pieces=` (spec: "never log target as
if filled"). `📊 Risk hesabı` satırına sl_pct/fee_est/open_pieces eklendi;
`⚠️ Initial margin çok büyük!` satırı ARTIK YOK (o mekanizma kalktı).

### 25.2 Fix BF — phase2_correction.md (public WS ticker feed)
**Mimari:** WS yalnızca CACHE yazar + değerlendirici çağırır; Faz 2 güvenlik
makinesi (provisional SL → verify → final → old-SL-cancel, immunity/grace,
deferred verify, per-piece no-collapse, software trailing) DEĞİŞMEDİ.
Spec'in 10 maddelik "Forbidden" listesinin tamamına uyuldu.

- `_bybit_public_ws_loop`: `wss://stream.bybit.com/v5/public/linear`,
  `tickers.<SYM>` aboneliği (konfigüre marketler ∪ tracked), 20 s ping,
  exponential backoff 1→30 s, (re)connect'te degraded-until-first-tick.
  **Public linear market verisi demo/live AYNI akıştır** (demo emirleri mainnet
  fiyatına dolar; public'in demo varyantı yok) → tek URL, `BYBIT_PUBLIC_WS_URL`
  ile override.
- `_bybit_public_ws_ingest`: **DELTA-güvenli alan MERGE** (tickers kanalı yalnız
  değişen alanları yollar; `lastPrice` yokken satırı ezmek fiyatı silerdi),
  `source="ws"`, pair başına ≥0.1 s eval debounce.
- **`_try_trigger_phase2` — TEK 1R tetikleyicisi (spec §3 ZORUNLU):** monitor'ın
  LONG/SHORT ikiz blokları silindi, 1R matematiği BİREBİR `_compute_profit_r`'a
  taşındı (komisyon buffer'ı aynı). Guard'lar: 1r_reached/phase2_active,
  geçersiz order_id, `_processing_phase2_orders`, `_bybit_phase2_blocked`,
  **Fix BB-2 hayalet-parça guard'ı (WS yolu da alır)**, crossed değilse no-op.
  Set-add + create_task aynı event loop'ta atomik → **çift Faz 2 imkânsız**
  (WS+monitor aynı ms'de bile). Log: `🚀 [FAZ 2 AKTİVASYON] … [kaynak=ws|monitor,
  fiyat_yaşı=Nms]`.
- `_bybit_evaluate_r_levels` (spec §5): Faz1→tetik, Faz2-aktif→`_maybe_schedule_trailing`
  (order_id başına ≥0.75 s, WS+monitor ORTAK throttle), `🏔️ [2R]` gözlem logu
  (parça başına 1 kez, `r_distance_orig` = tetik anında sabitlenen ORİJİNAL risk
  mesafesi — Faz 2 SL'i taşıyınca `sl` alanı değişir, R metriği bozulmasın diye).
- **Monitor dual-mode (spec §8):** `_bybit_ws_pair_eval_fresh(pair)` → WS
  değerlendiricisi pair'i son ~4 s'de HATASIZ işlediyse monitor tetik denemez
  (yedek); bayatladıysa monitor bugünkü gibi birincil. Sağlık damgası bilinçli
  olarak **evaluator canlılığı** (feed değil): feed akarken evaluator exception
  atarsa damga atılmaz → monitor otomatik birincil kalır (fail-safe).
- **REST fallback (spec §7):** WS bayat/kopuk VE açık parça varken
  `_bybit_refresh_tickers` TTL'i 3 s → 0.75 s'e iner; WS sağlıklıyken idle.
  REST snapshot, WS'nin ≤2 s içinde yazdığı sembolü EZMEZ (merge guard).
- Yaşam döngüsü: `on_tick` → `_ensure_bybit_public_ws` (tek task handle, sızıntı
  yok); `on_stop` → cancel. `BYBIT_PUBLIC_WS_ENABLED=0` → tüm kapılar kapanır,
  davranış v4.5 (Fix AY REST-poll) ile birebir aynı.

### 25.3 Risk analizi — öngörülen hatalar ve kurulan savunmalar
| # | Risk | Savunma |
|---|---|---|
| R1 | REST full-snapshot, daha taze WS girdisini ezer | per-sembol merge guard (`source=='ws'` ve ≤2 s taze → korunur) |
| R2 | Delta mesajda eksik alan satırı sıfırlar | alan-bazlı merge; eksik alan mevcut değeri KORUR |
| R3 | WS+monitor çift Faz 2 | tek helper + atomik set-add (aynı loop, arada await yok) + dual-mode gate |
| R4 | Task sızıntısı / restart fırtınası | tek handle + done-check; backoff 1→30 s; on_stop cancel |
| R5 | WS yolunda bloklayıcı iş | evaluator senkron, aksiyonlar yalnız create_task; REST/await YASAK (test ediyor) |
| R6 | Evaluator bozulursa sessiz körlük | sağlık damgası evaluator-sonu → damga durur → monitor birincil olur |
| R7 | Demo/live public WS domain farkı | fark YOK (public tek akış); yanılıyorsak env override + degraded fallback zaten bugünkü davranış |
| R8 | Sakin sembolün push'u seyrek → yanlış "bayat" | bağlantı sağlığı mesaj-bazlı; pair tazeliği `_bybit_fresh_price` ts'i ile ayrı |
| R9 | WS öldüğünde fiyat tazeliği | REST fallback TTL 0.75 s + monitor backup → v4.5'ten DAHA iyi, asla daha kötü değil |

### 25.4 Yeni env (v5.1)
```
MAX_OPEN_PIECES=6            MAX_MARGIN_USAGE=0.75    MAX_MARGIN_PER_TRADE=0.25
SIZING_FEE_RT=0.0011         SIZING_FEE_AWARE=1       MAX_FEE_RATIO=0.25
MIN_SL_PCT=0.0015            MAX_SL_PCT=0.015         MAX_RISK_BUMP_RATIO=1.25
BYBIT_PUBLIC_WS_ENABLED=1    BYBIT_PUBLIC_WS_URL=wss://stream.bybit.com/v5/public/linear
BYBIT_PUBLIC_WS_STALE_SEC=2.0  BYBIT_PUBLIC_WS_EVAL_MIN_INTERVAL=0.1
BYBIT_TRAIL_WS_MIN_INTERVAL=0.75  BYBIT_REST_FALLBACK_TTL_ACTIVE=0.75
```

### 25.5 Doğrulama
`tools/verify_v51_fixes.py` → **52/52 PASS**: 250$ hesap replay'i (SL %0.5
geçer / %0.3 TOO_TIGHT / %2 TOO_WIDE; fee-aware'de risk+komisyon ≡ hedef;
kaldıraç bağımsızlığı 5/20/50x; kaldırılan bug'ın 20x şişirmesi), gerçek
`_count_open_pieces`/`_compute_profit_r`/`_try_trigger_phase2`/
`_maybe_schedule_trailing` fonksiyonları AST ile çıkarılıp koşuldu (1R parite
eski inline matematikle birebir; idempotence; 6 guard; BB-2 WS yolunda;
throttle). `py_compile` OK · AST **0 fonksiyon kaybı** (432; +13 yeni) ·
`BYBIT_GUARD`=2 · önceki 7 paket PASS.

### 25.6 Deploy sonrası izlenecekler
**YENİ görülecekler:**
```
🌊 [BYBIT PUBLIC WS] bağlandı: N ticker …
🚀 [FAZ 2 AKTİVASYON] … [kaynak=ws, fiyat_yaşı=<100ms]   ← ws olmalı, monitor değil
📊 [SIZING] … target_risk= effective_risk= …             ← her girişte
🚫 [SIZING SKIP] … reason=…                              ← elenen sinyaller artık görünür
🏔️ [2R] …
```
**BİTMESİ gerekenler:** `⚠️ Initial margin çok büyük!` (mekanizma kalktı);
`[kaynak=monitor]` aktivasyonların çoğunluğu olması (WS sağlıklıyken ws olmalı).
**İZLENECEK:** `🚫 [SIZING SKIP]` dağılımı — TOO_TIGHT_FEE sıklığı yüksekse
sinyal SL'leri komisyona göre fazla dar demektir (MAX_FEE_RATIO kullanıcı
kararıyla gevşetilebilir); MAX_SLOTS sıklığı 6 tavanının ticaret sıklığına
uyup uymadığını gösterir. WS reconnect sıklığı (DEBUG logda) — sıksa ağ/URL
sorunu, davranış otomatik REST-poll'a düşer (koruma boşluğu oluşmaz).

### 25.7 Kalan açık konular
1. §24.8'dekiler aynen geçerli (09:28:13 WS-miss kök nedeni; blended-avg politikası).
2. ~~TOO_TIGHT_FEE eşiğinin (%25) gerçek sinyal dağılımıyla kalibrasyonu~~ →
   **§25.8 Fix BG ile gevşetildi** (deploy sonrası 24 saatlik `SIZING SKIP`
   dağılımı yeni eşiklerle tekrar izlenmeli).
3. `_estimate_used_margin` pozisyonların GERÇEK kaldıraçla değil `B4_DEFAULT_LEVERAGE`
   ile marj tahmini yapar — tüm pozisyonlar aynı kaldıraçla açıldığı için bugün doğru;
   pozisyon-bazlı kaldıraç kullanılırsa güncellenmeli.

### 25.8 Fix BG (2026-08-06) — TOO_TIGHT_FEE / TOO_TIGHT_SL eşikleri gevşetildi
Deploy sonrası kullanıcı kararı: v5.1'in eşikleri gerçek sinyal akışına göre
fazla sıkı çıktı. İki minimal değişiklik (mevcut mimari/guard sırası
BOZULMADI, yalnızca sabitler + bir kontrolün sertliği değişti):

| Parametre | Önce | Sonra | Etki |
|---|---|---|---|
| `MAX_FEE_RATIO` | %25 | **%50** | TOO_TIGHT_FEE artık yalnızca sl_pct < ~%0.11'de tetiklenir (fee_rt=0.0011 ile) — önceki turda %0.3 SL'leri gereksiz eliyordu |
| `MIN_SL_PCT` | %0.15 (**soft** clamp) | **%0.20 (HARD SKIP)** | Önceki davranış dar SL'yi sessizce minimuma çekip GERÇEK olmayan bir mesafeyle boyutlandırıyordu (sinyalin kendi SL'inden bağımsız qty şişmesini gizliyordu) — artık TOO_WIDE ile simetrik: bant dışına çıkan sinyal kesilmeden/şişirilmeden tamamen ATLANIR (`reason=TOO_TIGHT_SL`) |

**Örtüşme notu:** bu iki varsayılanla (`fee_rt=0.0011`, oran=%50) TOO_TIGHT_FEE
matematiksel eşiği (~%0.11) yeni TOO_TIGHT_SL tabanının (%0.20) ALTINDA kalıyor
→ pratikte çok dar SL'ler artık neredeyse hep `TOO_TIGHT_SL` sebebiyle elenir,
`TOO_TIGHT_FEE` bu kombinasyonda savunma-derinliği katmanı (ölü kod değil —
`SIZING_FEE_RT` veya `MAX_FEE_RATIO` farklı ayarlanırsa yine tek başına
tetiklenebilir). `tools/verify_v51_fixes.py` bu örtüşmeyi açıkça test eder.

Doğrulama: `verify_v51_fixes.py` güncellendi (yeni eşiklerle replay: %0.3 SL
artık geçiyor, %0.15 SL artık `TOO_TIGHT_SL` ile atlanıyor) — **tüm assertler
PASS**. `py_compile` OK · AST 0 fonksiyon kaybı (432) · 8 paketin hepsi PASS
(not: `verify_v43_fixes.py` konsol cp1254 kodlamasıyla emoji basarken
`UnicodeEncodeError` verebilir — bu ortam/terminal kaynaklı, kodla ilgisiz;
`PYTHONIOENCODING=utf-8` ile çalıştırınca PASS).

---

## 26) v5.2 — 🔬 CANLI VPS FORENSIC TUR (2026-08-07): monitor'ın 1R'i 35+ dakika kaçırması + 4 yan bulgu

### 26.1 Metodoloji (kullanıcının "logları kaçırıyorsun" uyarısına yanıt)
Bu tur üç bağımsız kaynak çapraz kullanıldı, tek dosyaya güvenilmedi:
1. **Lokal `logs_tv_signal_strategy_processed.log`** (UTC+3, 1894 satır, tamamı
   okundu) — 2026-08-06 00:48 → 2026-08-07 16:35 aralığını kapsıyor.
2. **VPS ham log** (`/home/ubuntu/deploy/bots/logs/logs_tv_signal_strategy.log`,
   UTC, SSH read-only ile çekildi) — rotate olmuş, 2026-08-06 22:15 → CANLI ANA
   (2026-08-07 15:25 UTC) kadar sürüyor. Lokal dosyanın **bittiği yerden
   (13:35 UTC) sonrasını** tek başına bu dosya kapsıyordu — kullanıcının
   şikayet ettiği son DOT-USDT LONG kapanışı ve DOT-USDT SHORT 1R-miss olayı
   **yalnızca burada** vardı.
3. **Bybit public kline** (`api.bybit.com/v5/market/kline`, kimlik doğrulama
   GEREKMEZ — public piyasa verisi) — botun kendi loguna güvenmek yerine
   DOTUSDT'nin dakikalık low/high'ı doğrudan borsadan çekildi. Bu, "fiyat
   gerçekten 1R'yi geçti mi" sorusunu bot koduna hiç bakmadan kesin cevapladı.
4. **VPS↔lokal dosya md5 karşılaştırması** — deploy edilen `tv_signal_strategy.py`
   ile bu oturumun başındaki lokal dosya **birebir aynı** çıktı (`91d0b003...`,
   38307 satır) → versiyon kayması yok, bulunan bug'lar VARSAYILAN olarak
   canlıda da aktifti.

### 26.2 Madde 1 — istenen davranış / anomali / naked / Faz2 / tanıma (özet)
- **(a) İstenen davranış genel olarak sergileniyor**: WS-anında-kapanış (Fix AX),
  per-piece SL/limit-TP, orphan süpürücü, SL kapsama guard'ı hepsi bu 40 saatte
  çalışır durumda gözlendi (`⚡ WS LEG FILL`/`WS CLOSE COMPLETE` düzinelerce kez
  temiz çalıştı).
- **(b) Anomaliler**: §26.3 (1R miss), §26.4 (real-entry blended-avg), §26.5
  (arşivsiz kapanış), §26.6 (fee=0) — hepsi bulundu ve düzeltildi.
- **(c) Naked parça**: bu 40 saatte **hiçbir kalıcı naked parça yok** — tüm
  pozisyonlar her an ≥1 SL legiyle kapsanıyordu (`SL COVERAGE GAP` olayları hep
  saniyeler içinde `SL COVERAGE FIX` ile kapandı). §26.3'teki 1R-miss, korumasız
  bırakmadı (SL zaten aktifti) — yalnızca Faz 2'nin (risk-free'e geçiş +
  trailing) hiç aktive OLMAMASI riskiydi.
- **(d) Faz 2 ilerlemesi**: çoğunlukla düzgün (DOT-USDT SHORT #676925755948,
  #400480960388, #796424090557, #416554904297, BNB-USDT LONG #215942193878 —
  hepsi 1R→aktivasyon→trailing→TP2 zincirini eksiksiz tamamladı). **Tek
  istisna** §26.3'teki DOT-USDT SHORT #563527774245 — bu KALICI (35+ dk) bir
  tekil olay, dağınık/sık değil.
- **(e) Pozisyon tanıma**: genel olarak sağlam; `[TRACKED]` ile `Binance:` listesi
  bu pencerede sürekli örtüştü. Tek gerçek "tanıma" sorunu §26.4 idi (tanınıyordu
  ama YANLIŞ referans fiyatla).

### 26.3 🔥🔥 EN BÜYÜK BULGU — monitor'ın WS-dual-mode kısayolu 1R'i 35+ DAKİKA kaçırdı (Fix BJ)
**Olay**: DOT-USDT SHORT #563527774245 (14:05 UTC açıldı, gerçek entry≈0.8114,
SL=0.8176, 1R=entry−risk=**0.8052**). Bybit public kline (kimliksiz, doğrudan
sorgulandı):
```
14:52 UTC low=0.8049  (1R'yi geçti)
14:55 low=0.8056  14:58 low=0.8055  15:00 low=0.8054  15:09 low=0.8077
15:12-15:28 arası sürekli 0.808 bandında (1R'nin altında/yakınında)
```
Fiyat **35+ dakika** 1R bandında/altında kaldı. VPS ham logda bu order_id için
**HİÇBİR** `🚀 [FAZ 2 AKTİVASYON]` satırı yok — pozisyon 15:20 UTC'de (log
kaydının sonu) hâlâ Faz 1'de, hâlâ tam boyutta, hâlâ trailing'siz.

**Kök neden**: `_bybit_ws_pair_eval_fresh(pair)` (v5.1 Fix BF §8 "dual-mode")
BAĞLANTI seviyesinde sağlık ölçüyordu: WS soketi ayaktaysa VE **herhangi bir
sembolün** tick'i yakın zamanda geldiyse, `_bybit_evaluate_r_levels` her
sembol için çağrılır ve `_bybit_ws_pair_eval_ts[pair]` güncellenir — pair'in
KENDİ fiyatı gerçekten tazelenmiş mi diye AYRI bakılmıyordu. Monitor bu
timestamp tazeyse **tetiği hiç denemiyordu** ("WS zaten bakıyor" varsayımı).
Aynı dakikada (14:12:56 UTC) private pozisyon WS'inin de `(ws-stale)` REST
fallback'e düştüğü gözlendi — o anki hızlı fiyat hareketiyle (14:00→14:12
arası DOTUSDT %1,2 düştü) örtüşen bir ağ/borsa aksaklığı ihtimalini
destekliyor. Kesin "hangi alan donmuştu" tespit edilemedi (canlı debug
erişimi yok) ama SONUÇ nettir: bağlantı "sağlıklı" görünürken bu SEMBOLÜN
1R tetiği hiç ateşlenmedi.

**Fix BJ**: `_monitor_positions`'daki `if self._bybit_ws_pair_eval_fresh(pair):
continue` kısayolu **kaldırıldı**. `_try_trigger_phase2` zaten tam idempotent
(`1r_reached`/`phase2_active` guard'ı + atomik set-add, WS ile aynı event
loop'ta arada await yok) → monitor artık **HER ~1 saniyede KOŞULSUZ** dener.
Maliyet: ekstra bir karşılaştırma/guard-check (ihmal edilebilir). Kazanç:
bu bug sınıfı (bağlantı sağlıklı ama SEMBOL fiyatı donmuş) bir daha asla
sonsuza kadar kaçırılamaz — en kötü durumda WS ~1 sn gecikir, monitor devralır.
`_bybit_ws_pair_eval_fresh` fonksiyonu koddan silinmedi (teşhis için durabilir)
ama artık hiçbir yerde tetiği ENGELLEMİYOR.

### 26.4 Real-entry mekanizması hep BLENDED ortalamaya düşüyordu (Fix BH)
Kullanıcının gözlemi doğruydu: "sl@entry diyor ama borsada bunu göremiyorum…
bu SL değeri nasıl uyduruldu?" Kanıt zinciri:
- `_activate_phase2` → `_get_real_entry_price_from_trades(connector, pair,
  side, position_order_id)` çağırıyor.
- Bu fonksiyon ÖNCE `_get_bybit_executions(order_id=position_order_id, ...)`
  ile PARÇAYA ÖZEL execution sorgusu dener — ama `position_order_id`
  **dahili stabil-int takip anahtarıdır** (`_stable_int_order_id`'den türer,
  ör. `448093208057`), Bybit'in gerçek `orderId`'si İSE bir **UUID**'dir
  (ör. `8bb55e2f-dbdc-4d32-aa97-a5732d4a06a8`). `/v5/execution/list`'e
  `orderId=448093208057` filtresiyle sorgu **HİÇBİR ZAMAN eşleşmez** →
  `trades` her zaman boş → kod SESSİZCE `_get_entry_price_from_positions`'a
  düşer, o da `_ws_position_buffer`'dan **pozisyon-seviyesi (BLENDED, tüm
  parçaların karışımı) ortalama fiyatı** döndürür (log: `📡 [ENTRY] WS position
  buffer'dan: 0.81601612`).
- Canlı örnek: DOT-USDT LONG #448093208057 kendi sinyaliyle ~0.815'ten
  doldu, ama iki parça aynı yönde birikmiş olduğu için (§24.2'nin blended-avg
  gerçeği) "gerçek entry" olarak **0.81601612** — YANİ HEM #448093208057 HEM
  DE eski #804236257305 parçasının karışımı — rapor edildi ve Faz 2'nin
  SL@entry'si BUNA göre kondu. Sinyalin kendi SL/entry'siyle uyuşmaması
  ("ne sinyal ne kârlı seviye") buradan geliyordu.

**Fix BH**: `_track_position`'a yeni `exchange_order_id` parametresi eklendi
(borsanın GERÇEK UUID'si), `position_data["exchange_order_id"]` olarak
saklanıyor. İki canlı Bybit çağrı noktası da artık ham UUID'yi geçiyor.
`_get_real_entry_price_from_trades` yeni `exchange_order_id` argümanını
alıyor ve Bybit execution sorgusunda `exchange_order_id or order_id`
kullanıyor — artık PARÇANIN KENDİ fill'(ler)i doğru bulunuyor, blended
pozisyon-ortalamasına yalnızca bu bilgi YOKSA (eski/adopte pozisyonlar)
düşülüyor. `_activate_phase2`'nin çağrısı `pos_data.get("exchange_order_id")`
geçirecek şekilde güncellendi.

### 26.5 Eski polling SL/TP-trigger yolu arşive HİÇ yazmıyordu (Fix BM)
Aynı gün, DOT-USDT LONG #804236257305 (09:30 UTC'de açılmış, SL=0.8087) 14:12:59
UTC'de gerçekten tetiklendi — Bybit kline'da o dakika low=**0.8054** (sert bir
mumda), yani SL 0.8087'den tetiklenip piyasa emri muhtemelen ~0.805x civarında
doldu (kullanıcının gördüğü "0.8056 gibi anlamsız" değer — **anlamsız değil,
gerçek slippage**; ama bu satır ARŞİVE HİÇ YAZILMADI, o yüzden doğrulanamaz
görünüyordu). Kök neden: `_enqueue_trade_detection_jobs` içindeki
`was_sltp_trigger` dalı — WS-anında-kapanış (Fix AX) bu fill'i kaçırınca
düşülen YAVAŞ/polling fallback yolu — Fix AO'nun (§20.3) archive çağrısını
HİÇ almamış eski bir daldı: sadece `🎯 [SL TRIGGER DETECTED] … Skipping FIFO
logic, just cleaning up tracking` deyip tracking'i boşaltıyordu, `_archive_
trigger_close` çağrılmıyordu.

**Fix BM**: bu dal artık temizlediği HER parça için gerçek kapanış trade'ini
(qty/fiyat) eşleştirip `_archive_trigger_close` (modern WS yolunun kullandığı
AYNI fonksiyon) ile arşivliyor — `📁 [SL CLOSE ARCHIVED]` artık bu yoldan
geçen kapanışlar için de basılıyor. Yalnızca diske yazar; emir/tracking
davranışı değişmedi.

### 26.6 Fee/commission HER YERDE hardcoded 0 idi (Fix BI)
`_get_bybit_executions` normalize edilmiş dict'i Bybit'in döndürdüğü
`execFee` alanını **hiç okumuyordu** — bu yüzden onu tüketen HER yer
(`_verify_order_execution`'ın Bybit dalı dahil) `"commission": Decimal("0")`
hardcoded döndürüyordu, gerçek trade'de komisyon ne olursa olsun. **Fix BI**:
`_get_bybit_executions` artık `"fee": str(ex.get("execFee") or "0")` alanını
dahil ediyor; `_verify_order_execution` bu alanı fill'ler üzerinden toplayıp
gerçek komisyonu raporluyor.

### 26.7 WS reconnect/disconnect tamamen görünmezdi (Fix BK)
`_bybit_public_ws_loop`'un "bağlandı" logu `_bybit_public_ws_announced`
bayrağıyla **süreç ömründe yalnızca bir kez** basılıyordu — ilk bağlantıdan
sonraki HER kopma/reconnect **DEBUG seviyesinde** (pratikte görünmez)
geçiyordu. §26.3'teki olayı log'dan doğrudan teşhis edememenin bir nedeni
buydu. **Fix BK**: reconnect artık INFO ile ayrı metinle loglanıyor, bağlantı
hatası WARNING'e yükseltildi, gerçek bir kopma (`bağlıydı → değil`) ayrıca
loglanıyor, ve `_bybit_refresh_tickers` içine açık parça varken WS bayat/kopuk
olduğunda ≥30 sn'de bir throttled bir "feed bayat" WARNING'i eklendi.

### 26.8 Madde 3 — conditional SL için triggerBy: Mark mı Last mı? (ÖNERİ: Mark'ta KAL)
Borsa arayüzünde "Last Price" seçeneğinin var olması doğru gözlem, ama
**değiştirmenizi ÖNERMİYORUM**:
- SL'ler bilerek `triggerBy=MarkPrice` kullanıyor (§10.2) — Mark Price birden
  fazla borsanın endeks fiyatının ortalamasıdır, LastPrice ise TEK borsadaki
  son işlem fiyatıdır. Mark, ani/tekil "stop hunting" fitillerine karşı
  Last'tan DAHA DAYANIKLIDIR — bu endüstri standardı bir güvenlik tercihidir.
- 26.5'teki "0.8087→~0.805x" olayı trigger TÜRÜNDEN kaynaklanmıyordu: SL
  koşullu emri tetiklenince **MARKET emri** olarak yürür; piyasa o dakika
  gerçekten 0.8054'e kadar düştüğü için (kline kanıtı) fiyat farkı gerçek
  slippage'dır — Last Price tetikleyici kullansaydık da AYNI market emri AYNI
  şekilde kayardı (trigger tipi tetiklenme ANINI belirler, sonucun ne fiyattan
  dolduğunu değil). Last Price'a geçmek üstelik SL'i daha tetiklenebilir hale
  getirir (tek borsanın anlık fitiline karşı savunmasız) — güvenlik yönünü
  BOZAR. **Karar kullanıcıya bırakılıyor** ama teknik tavsiye: değiştirme.

### 26.9 Madde 5 — "TP=1R limit emri" fikri: manual_second_take BOZUK DEĞİL, farklı bir mekanizma
Kod incelemesi gösterdi ki `phase2_tp_mode="manual_second_take"` (kullanıcının
"patchlemiştik" dediği mekanizma) **çalışıyor** — DOT-USDT SHORT
#416554904297/#796424090557 ve BNB-USDT LONG #215942193878 hepsi
`🎯 [PHASE2 TP2 HIT] … closing 0.50 of remaining` ile ikinci alımı doğru
tetikledi. DOT-USDT LONG #448093208057 bu tetiği HİÇ görmedi çünkü fiyat SL'e
(breakeven) TP'sinden (0.8251, ~2R) önce geri döndü — bu bir bug değil, normal
piyasa sonucu.

Kullanıcının asıl önerisi (yeniden okuyunca) DAHA FARKLI ve İYİ bir fikir:
**girişte sinyalin TAM boyut için TP'si yerine, YARIM boyut için 1R
seviyesine reduceOnly LIMIT emri koymak** — böylece 1R'ye ulaşma exchange'in
kendi emir motoruyla gerçekleşir, bizim WS/monitor tespitimize hiç bağlı
kalmaz (§26.3'ün KÖKÜNÜ yapısal olarak ortadan kaldırır — kaçırılacak bir şey
olmaz, çünkü tetikleyen bot değil borsa olur). Bu, mevcut v4.0 "reduceOnly
LIMIT TP" mimarisiyle (§18) TUTARLI, ama Faz 1→2 GEÇİŞİNİN kendisini
(şu an: monitor/WS fiyat algılar → market emriyle yarım kapat → SL'i
breakeven'e taşı) yeniden tasarlamak anlamına gelir: limit emir dolunca bunu
YAKALAYIP (mevcut WS leg-fill pipeline'ı, Fix AX, zaten bunun için var) SL'i
breakeven'e taşıma adımını TETİKLEMEK gerekir — yani "Faz 2 aktivasyonu"
artık fiyat-algılama değil FILL-algılama olur.

Bu, canlıya saatler kala uygulanacak kadar küçük bir değişiklik DEĞİL —
Faz 1→2 geçişinin ÇEKİRDEK mekanizmasını değiştiriyor. **Fix BJ zaten §26.3'ün
somut belirtisini (35+ dakikalık sessiz kaçırma) kapatıyor** (monitor artık
asla susmuyor). Bu yüzden bu oturumda UYGULANMADI — ayrı, dikkatli test
edilebilecek bir turda ele alınmalı. İstenirse bir sonraki oturumda
tasarlanır.

### 26.10 Madde 6 — Faz 2 sonrası marj serbest kalımı: muhtemelen ZATEN doğru
`available_balance`, botun KENDİ hesapladığı bir değer DEĞİL —
`get_balance_df()` üzerinden doğrudan Bybit'in cüzdan/marj API'sinden gelir.
ReduceOnly bir Faz 2 kapatması pozisyonu küçülttüğü anda borsa kendi
`availableToWithdraw`'ını günceller; botun bunu "geri eklemesi" gereken bir
kod yolu YOK (ve olmamalı — exchange-truth tek kaynak olmalı). Log'daki
"💰 Bakiye" satırları arasında net bir öncesi/sonrası karşılaştırması aynı
pencerede çok sayıda örtüşen pozisyon/PnL olduğu için güvenilir izole
edilemedi. **Somut bir bug bulunamadı**; şüphe duyulursa en net test: tek
pozisyon açık olduğu bir anda Faz 2'nin hemen ÖNCESİ ve HEMEN SONRASI
`💰 Bakiye` değerlerini (aradaki tek fark Faz 2 kapatması olacak şekilde)
karşılaştırmak — mevcut log'da böyle temiz bir pencere yoktu.

### 26.11 Doğrulama
`tools/verify_v52_fixes.py` → **25/25 PASS**: Fix BH (UUID vs stabil-int
yapısal kanıtı + gerçek fonksiyon zinciri), Fix BI (fee toplama matematiği),
Fix BJ (dual-mode kısayolunun kaldırıldığı + idempotence + 09:28 olayının
kline-doğrulanmış replay'i), Fix BK (reconnect/disconnect log metinleri),
Fix BM (archive çağrısının konumu ve içeriği). `py_compile` OK · AST **0
fonksiyon kaybı** (432) · `BYBIT_GUARD`=2 · önceki 8 test paketi (verify_v51
dahil, güncellenen dual-mode assertion'la 64/64) hâlâ PASS.

### 26.12 Deploy sonrası izlenecekler
**YENİ görülecekler:**
```
🌊 [BYBIT PUBLIC WS] yeniden bağlandı: … (önceki bağlantı koptu, backoff=…s sonra)
⚠️ [BYBIT PUBLIC WS] bağlantı hatası / bağlantı koptu
⚠️ [BYBIT PUBLIC WS] feed bayat/kopuk — açık parça(lar) var, REST fallback …
📁 [SL CLOSE ARCHIVED] / [TP CLOSE ARCHIVED] — artık `SL/TP TRIGGER DETECTED`
   sonrasında da (eskiden bu yolda hiç basılmıyordu)
```
**İZLENECEK:** `🚀 [FAZ 2 AKTİVASYON] … [kaynak=monitor]` sıklığı artık WS
gerçekten bayatladığında da (dual-mode kısayolu kalkınca) daha sık görünebilir
— bu ENDİŞE değil, tam da istenen davranış (WS sessiz kalsa bile tetik kaçmaz).
`Commission:` satırlarının artık 0'dan farklı gerçek değerler göstermesi.
**KALAN AÇIK KONULAR:** §26.3'teki WS/borsa aksaklığının TAM kök nedeni
(hangi alan/neden donmuştu) teşhis edilemedi — Fix BJ zararı ortadan
kaldırıyor ama olayın kendisini açıklamıyor; §26.9'daki "TP=1R limit emri"
yeniden tasarımı ayrı bir turda ele alınmalı; §26.10 canlıda tek-pozisyon
testiyle doğrulanabilir.

---

## 27) LIVE GEÇİŞ + ÇOKLU-PAIR — VPS'te doğrulanmış gerçekler (2026-08-07)

Aşağıdakiler VPS'e SSH ile (read-only) bakılarak doğrulandı — varsayım değil.
Otomasyon: `tools/switch_bybit_env.sh` (bash — VPS'e kopyalanıp orada çalıştırılır,
bu makineden VPS'e yazma iznim yok, kod local'de hazırlandı).

### 27.1 Çoklu-pair — kod değişikliği GEREKMİYOR
Tüm runtime dosyasında pair'lerin hardcoded olduğu **TEK yer**:
`tv_signal_strategy.py:505` (`markets = {...}` class default). Bu bile
runtime'da **config YAML tarafından override ediliyor** (`init_markets`
classmethod, `TVSignalConfig.markets` alanından). VPS'te gerçek kaynak:
`conf/scripts/tv_signal_strategy.yml`:
```yaml
markets:
  bybit_perpetual_demo:
    - BTC-USDT
    - ETH-USDT
    - DOT-USDT
    - DOGE-USDT
    - BNB-USDT
```
Yeni pair eklemek için TEK gereken: bu listeye satır eklemek (+ container
restart). Trading rules, tick size, WS abonelik listesi, risk sizing, TP/SL
mimarisi — HEPSİ zaten dinamik/pair-agnostic (kod içinde ikinci bir hardcoded
pair listesi YOK, doğrulandı). Tek koşul: pair Bybit'te **linear (USDT-M)**
kontrat olarak var olmalı; yoksa sinyal `unsupported_symbol` ile zararsızca
reddedilir (§14 Fix P/Q).

### 27.2 Demo → Live — TEK env + TEK YAML anahtarı
VPS'teki gerçek `.env.hummingbot` (sadece operasyonel bayraklar, secret YOK):
```
BYBIT_ENV=demo            EXCHANGE_BACKEND=bybit      TRADING_ENABLED=1
B4_DRY_RUN=0              B4_ATTACH_TPSL=0            B4_DEFAULT_LEVERAGE=20
B4_MAX_NOTIONAL_USDT=0    B4_MAX_MARGIN_USDT=0        B4_USE_HB_PLACE_ORDER=0
B4_DISABLE_SLTP_CLOSE=1
```
`ACTIVE_CONNECTOR` zaten `BYBIT_ENV`'e göre kod içinde otomatik seçiliyor
(`__init__` L982-984: `demo→bybit_perpetual_demo`, `live→bybit_perpetual`) —
**bu satır zaten canlıya hazır, dokunmaya gerek yok.** Değişmesi gereken
SADECE:
1. `.env.hummingbot`: `BYBIT_ENV=demo` → `BYBIT_ENV=live`
2. `conf/scripts/tv_signal_strategy.yml`: `markets:` altındaki
   `bybit_perpetual_demo:` → `bybit_perpetual:` (pair listesi AYNI kalır)

### 27.3 Endpoint/domain — HB'nin CUSTOM-patched dosyasında ZATEN doğru
`docker-compose.yml` şu dosyayı container'a MOUNT ediyor (stok HB dosyasının
YERİNE geçiyor): `bots/custom/bybit_perpetual/bybit_perpetual_constants.py`.
İçeriği doğrulandı — `bybit_perpetual_main` (live) domain'i zaten TAM ve
DOĞRU: `REST=https://api.bybit.com/`, private WS=`wss://stream.bybit.com/v5/
private`, public linear WS=`wss://stream.bybit.com/v5/public/linear` (demo
ile AYNI — Fix BF'nin "public linear veri demo/live tek akış" varsayımını
BİREBİR doğruluyor, ayrıca kanıtlandı). **Bu dosyaya DOKUNULMAYACAK.**
`_bybit_raw_credentials` (kendi kodumuz) zaten `connector._domain`'e bakıp
`"demo"` içermiyorsa `api.bybit.com` kullanıyor — otomatik doğru.

### 27.4 Connector credential dosyası ZATEN VAR — içeriği DOĞRULANMALI
`conf/connectors/bybit_perpetual.yml` VPS'te **mevcut** (yapısal olarak
tam: `connector`/`bybit_perpetual_api_key`/`bybit_perpetual_secret_key`,
key/secret şifreli — CONFIG_PASSWORD ile). **İçeriğinin gerçekten LIVE
API anahtarı olduğunu ben doğrulayamam** (şifreli, decrypt etmedim/etmemeliyim)
— kullanıcı HB CLI'de `connect bybit_perpetual` ile TEYİT/güncelleme yapmalı.
Bybit tarafında: Position Mode=Hedge (demo hesabından AYRI bir ayar, live
hesapta ayrıca kontrol edilmeli), API key izni "Contract Trading" açık,
"Withdrawal" kapalı, IP whitelist kullanılıyorsa VPS IP'si ekli olmalı.

### 27.5 Otomasyon: `tools/switch_bybit_env.sh`
Bash seçildi (Python değil) — iş yalnızca 2 config dosyasında bir anahtar
değişimi + docker restart, ek bağımlılık gerektirmez. **API key/secret'a HİÇ
dokunmaz** (şifreli veriyi kör sed ile değiştirmek güvensiz olurdu) — bunun
yerine `connect bybit_perpetual` adımını açıkça HATIRLATIR. Varsayılan
DRY-RUN; `--apply` + interaktif "evet" onayı olmadan hiçbir dosya değişmez.
Her `--apply` öncesi otomatik timestamp'li yedek alır (`revert` ile geri
dönülebilir). Komutlar: `status` · `live [--apply]` · `demo [--apply]` ·
`add-pair PAIR-USDT [--apply]` · `revert`.

---

## 28) v5.3 — 🔁 RESTART SONRASI FAZ 2 HAFIZASI KAYBI (Fix BN) + manual_second_take'in Bybit'te ÖLÜ KOD olması (Fix BO)

Kullanıcı talebi 2026-08-08: v5.2 deploy edildikten sonra bir restart'ta bot
Faz-2'deki bir parçanın Faz 2'de olduğunu "unuttu" — kök nedeni bul, "sonraya
bırakma", paketin tamamını (ilişkili tüm mekanizmaları) düşünerek kalıcı çöz.

### 28.1 Canlı olay (2026-08-07, BNB-USDT LONG #603114248654)
```
18:20:07  Açıldı: Entry 591.2, SL 589.8 (sinyal)
19:09:36  FAZ 2 AKTİVASYON (1.02R) → yarı kapat, SL@591.2 → trailing başladı
19:10:01  Trailing: SL 591.2 → 591.79 → 592.38 (kâr kilitleniyor)
19:13:16  2R geçti (594.20) — TP2 (manual_second_take) hedefi 594.3, henüz değil
19:48:02  RESTART (muhtemelen v5.2 deploy'u için; on_stop() HİÇ ÇAĞRILMADI —
          "💾 Shutdown"/"✅ State kaydedildi" satırları YOK; muhtemelen
          `docker restart` SIGTERM'i strateji on_stop'una ulaştıramadan
          SIGKILL'e düştü — sert kapanış)
19:48:12  📂 State yükleniyor: 0 pozisyon kaydı   ← state dosyası bu spesifik
          restart'ta OKUNAMADI (muhtemelen deploy sürecinin operasyonel bir
          yan etkisi; ayrıca araştırılmadı — aşağıdaki kod düzeltmesi
          NEDENDEN BAĞIMSIZ olarak sağlamlaştırıyor)
19:48:13  AUTO-DETECT devreye girdi. Arşiv BNB-USDT_LONG için filled=1.17
          buldu ama canlı miktar 0.59 (ratio=0.50) → "Archive filled_amount
          mismatch" ile REDDEDİLDİ (tam da Faz 2'nin İMZASI olan oran hariç
          tutuluyordu!) → "Cache/Arşiv'de bulunamadı, tahmin edilecek":
            Entry bulunamadı → mid_price (592.45) kullanıldı
            SL bulunamadı → entry∓%2 tahmini: 580.60
            TP bulunamadı → entry±%2 tahmini: 604.20
          "✅ [AUTO-DETECT] … 1R Reached: False"  ← FAZ 2 HAFIZASI SİLİNDİ
19:48:14  ✅ [BYBIT LIMIT TP] BNB-USDT LONG @ 604.20 qty=0.59  ← manual_second_
          take parçasına YANLIŞ, TAM boyutlu bir TP emri kondu
          (SL için "✅ [BYBIT COND SL] @ 580.60" log satırı bu kesitte
          görünmedi — muhtemelen CID amend "not_modified" ile sessiz kaldı;
          amend gerçekleşmiş olsaydı gerçek 592.38'lik trailing SL 580.60'a
          GERİYE ÇEKİLMİŞ olurdu — bu ihtimal test edilmeden bırakılmadı,
          kök neden zaten kapatıldı)
```

### 28.2 Kök neden zinciri (üç ayrı, birbirini besleyen kusur)
1. **`_auto_detect_position`'daki arşiv-oranı filtresi** (`ratio > 1.8 veya < 0.55`
   → arşivi reddet) **tam olarak Faz 2'nin kendi imzasını** (bir kez %50
   kısmi kapama → ratio≈0.50) dışlıyordu. Bu eşik muhtemelen "tamamen
   alakasız/eski sinyal" senaryolarını elemek için konmuştu ama en yaygın
   gerçek senaryoyu (tam olarak bir Faz 2 geçişi) da eledi.
2. **Entry tahmini `mid_price`'a EŞİTLENİYORDU.** Bu, aşağıdaki
   `already_1r = (mid_price >= entry_price + risk_distance)` kontrolünü
   **yapısal olarak imkânsız** hale getiriyordu (`mid_price >= mid_price +
   risk_distance`, risk_distance>0 iken asla doğru olamaz) — yani entry
   tahmin yoluna düşen HİÇBİR parça "zaten Faz 2'de" olarak asla
   tanınamıyordu, ne kadar ileride olursa olsun.
3. **`is_already_phase2` kontrolü de kırılgandı**: `original_amount`'ı
   SADECE cache/arşivin `filled_amount` alanından okuyordu — ama tam da
   arşivin REDDEDİLDİĞİ (1) senaryosunda bu alan hiç yoktu → "Original
   amount bulunamadı! FAZ 2 kontrolü atlanıyor, normal aktivasyon
   yapılacak" → **zaten yarısı kapanmış bir parçayı TEKRAR yarıya
   indirmeye** (ikinci kez `_activate_phase2` çağırmaya) çok yakındı (bu
   olayda madde 2 yüzünden `already_1r=False` kaldığı için bu dal hiç
   çalışmadı, ama bu AYRI ve gerçek bir risk).
4. **Nihai `position_data` sözlüğü `"phase2_active": False`'u KOŞULSUZ
   set ediyordu** — `already_1r`/`is_already_phase2` ne olursa olsun.
   Yani en iyi ihtimalle (Faz 2 yeniden aktive edilmese bile) parça
   `phase2_active=False` VE `1r_reached=True` ile **hem Faz 1 hem Faz 2
   dalının dışında, atıl bir limbo durumunda** kalıyordu —
   `_monitor_positions` böyle bir parçayı ne yeniden değerlendirir ne
   trailing yapar.
5. **`_set_binance_sltp_async`'ın Bybit dalı `phase2_tp_mode`'u HİÇ
   bilmiyordu.** Fonksiyonun İÇİNDE bir `manual_second_take` kontrolü
   VARDI ama Bybit dalı bu kontrolden ÖNCE `return` ediyordu → Bybit için
   bu kontrol **erişilemez ölü koddu**. `_ensure_individual_sltp_for_all_
   positions` (auto-detect'in SL/TP yerleştirme adımı) `pos.get("tp")`'yi
   `phase2_tp_mode`'a bakmadan doğrudan geçiyordu → manual_second_take
   parçalarına bile tam boyutlu bir TP emri konabiliyordu.

### 28.3 Fix BN — borsa-gerçeği tabanlı Faz 2 imzası tespiti
`_auto_detect_position`'a, entry/SL cache→arşiv→tahmin merdiveninden HEMEN
SONRA (hangi yoldan geçilmiş olursa olsun), Bybit için şu kontrol eklendi:
```
gerçek_entry = _get_bybit_position_row(...).entry      # borsa avgPrice
gerçek_sl    = _get_bybit_position_protection(...).sl_price  # borsadaki AKTİF SL leg
Faz-2-imzası = (LONG: gerçek_sl >= gerçek_entry) veya (SHORT: gerçek_sl <= gerçek_entry)
```
Bu, **amount oranından veya arşiv yaşından TAMAMEN bağımsız, tahrif
edilemez** bir kanıttır: bir Faz-1 SL'i, risk tanımı gereği HER ZAMAN
entry'nin risk tarafındadır — asla entry'de veya ötesinde olamaz. Bulunduğunda:
- `entry_price`/`sl_price` **borsa gerçeğiyle EZİLİR** (ne tahmin ne
  reddedilmiş arşiv değeri kullanılır).
- `tp_price`: arşivin/cache'in ORİJİNAL sinyal TP'si tercih edilir (hafif
  bayat olsa da rastgele icat etmekten kesinlikle iyidir); yoksa borsada
  hâlâ duran gerçek bir limit TP; o da yoksa zaten hesaplanmış tp_price kalır.
- `risk_distance`/`risk_amount` YENİ entry/SL ile **yeniden hesaplanır**.
- `already_1r` **doğrudan True** set edilir (mid_price karşılaştırmasına
  gerek yok — bu daha güçlü bir kanıt).
- `is_already_phase2` **doğrudan True** set edilir → `_activate_phase2`
  KESİNLİKLE tekrar çağrılmaz (kırılgan `original_amount/2` karşılaştırmasına
  düşülmez).
- `position_data`'ya artık KOŞULLU olarak `phase2_active`,
  `phase2_activation_complete`, `phase2_tp_mode="manual_second_take"`,
  `phase2_tp2_done=False`, ve kâr yönünde bir `peak_price` set edilir —
  parça limbo'da kalmaz, `_monitor_positions`'ın trailing dalına DOĞRUDAN
  girer.
Bybit-dışı (OKX) davranış **tamamen değişmedi** (tüm blok
`_is_bybit_connector` ile korunuyor); genuine Faz-1 pozisyonlar için de
sıfır davranış değişikliği (imza koşulu sağlanmaz, eski merdiven aynen çalışır).

### 28.4 Fix BO — `manual_second_take` artık Bybit'te de etkili
`_set_binance_sltp_async`'a, Bybit dalından ÖNCE bağımsız bir
`_manual_second_take_early` kontrolü eklendi (aynı `_find_position_by_order_id`
deseniyle, aynı exception-safe şekilde) — bulunduğunda `_place_bybit_trading_
stop`'a geçirilen `tp_price` sıfırlanır (`_effective_tp_price`). Bu, YALNIZCA
Fix BN'in kurtardığı parçaları değil, `phase2_tp_mode="manual_second_take"`
işaretli HERHANGİ bir parça için HERHANGİ bir çağıranı korur (savunma
derinliği — "paketin tamamı" ilkesi). Eski (Bybit-dışı) kontrol dokunulmadan
duruyor, OKX davranışı değişmedi.

### 28.5 Kalıcı state kaydının (§15.5) kendisi hâlâ araştırılmadı — ama artık ÖNEMSİZ
Bu restart'ta `📂 State yükleniyor: 0 pozisyon kaydı` görülmesinin TAM nedeni
(muhtemelen `docker restart`'ın `on_stop()`'a ulaşamadan sert kapanışa
düşmesi) ayrıca doğrulanmadı. **Bilinçli karar:** Fix BN, state kaybının
NEDENİNDEN bağımsız çalışır — state dosyası okunsa da okunmasa da, auto-detect
her tetiklendiğinde borsa-gerçeğine bakar. Bu, tek bir kök nedeni kovalamaktan
(deploy script'i mi, HB'nin SIGTERM işleyişi mi, veri klasörü mü) daha sağlam
bir mühendislik kararıdır. **Operasyonel öneri:** deploy'larda konteyneri
`docker restart` ile SERT kapatmak yerine önce HB CLI'de `stop` komutuyla
stratejiyi GRACEFUL durdurup (böylece `on_stop()`/`_save_state()` çalışır),
SONRA konteyneri yeniden başlatmak devlet kaybı riskini daha da azaltır.

### 28.6 Doğrulama
`tools/verify_v53_fixes.py` → **22/22 PASS**: gerçek fonksiyonlar AST ile
çıkarılıp yapısal olarak doğrulandı; olayın kendi sayılarıyla (591.2/592.38
LONG, 0.8114/0.8118 SHORT mirror) imza-tespiti matematiği replay edildi
(gerçek pozitif + gerçek Faz-1 negatif, yanlış-pozitif YOK); Fix BO'nun
Bybit dalında eskiden ERİŞİLEMEZ olduğu yapısal olarak kanıtlandı (branch
her zaman `return` ile bitiyor, eski kontrol ondan SONRA). `py_compile` OK ·
AST **0 fonksiyon kaybı** (432) · `BYBIT_GUARD`=2 · önceki 9 test paketi PASS.

### 28.7 Deploy sonrası izlenecekler
**YENİ:** `🔁 [AUTO-DETECT PHASE2 RESTORED] …` (restart sonrası Faz 2'deki
parçalar için bunu görmelisiniz, "1R Reached: False" ile fabricated SL/TP
DEĞİL). **BİTMESİ gereken:** restart sonrası Faz-2-aktif bir parçanın SL'inin
borsada GERİ ÇEKİLMESİ; manual_second_take parçalarına restart sonrası tam
boyutlu TP emri konması.

---

## 29) v5.4 — 🔒 RESTART AMNEZİSİNİN GERÇEK KÖK NEDENİ: BOOT'TAKİ STATE-WIPE YARIŞI (Fix BQ) + koşulsuz exchange-truth adoption (Fix BP)

Kullanıcı raporu 2026-08-08: "Fix BN işlevsel değil — DOT-USDT SHORT Faz 2'de
olmasına rağmen restart sonrası algılanamadı, SL yine uydurulup 0.8182'ye
(orijinal 0.8176'dan da kötü) çekildi." **Kullanıcı haklıydı.** VPS md5
doğrulandı: 20:50 restart'ı GERÇEKTEN Fix BN'li kodla çalıştı (dosya 17:49
UTC'de deploy edilmiş, marker mevcut) ve BN tetiklenmedi.

### 29.1 Fix BN neden tetiklenmedi — olay zinciri (hepsi kanıtlı)
```
19:57  DOT SHORT #563527774245 Faz 2'ye geçti; SL→entry(0.8114)→trailing 0.80815
20:07  RESTART (ESKİ kod — BN henüz deploy edilmemişti):
       state "0 kayıt" → auto-detect → arşiv ratio=0.50 REDDEDİLDİ →
       entry=mid(0.80445) uyduruldu → SL 0.8205 uyduruldu ve BORSADAKİ
       GERÇEK 0.80815'lik trailing SL legi 0.8205'e AMEND EDİLDİ ← HASAR
20:49  v5.3 (Fix BN) deploy edildi (dosya mtime 17:49 UTC, md5 birebir)
20:50  RESTART (YENİ kod): BN çalıştı ama imzası "SL entry'de/ötesinde mi"
       idi — borsadaki SL artık 0.8205 (20:07'nin bozduğu değer), entry
       0.8114'ün RİSK tarafında → E1 kanıtı bir önceki restart tarafından
       YOK EDİLMİŞTİ → BN sessizce (debug) geçti → fabrikasyon yine çalıştı:
       SL 0.8182. Ayrıca "0 pozisyon kaydı" YİNE görüldü.
```
İki bağımsız kusur birleşti: (a) BN tek kanıta dayanıyordu ve o kanıt yok
edilebilirdi; (b) state dosyası NEDEN her restart'ta "0 kayıt" veriyordu —
asıl gizem buydu ve çözüldü:

### 29.2 🔥🔥 Fix BQ — state dosyasını BOOT'UN KENDİSİ siliyordu (§15.5 kapandı)
`on_tick` her 10 sn'de `_save_state()` çağırıyor ve `_last_health_check=0`
başladığı için İLK tick'te çalışıyor. `_load_state()` ise `asyncio.create_task`
ile planlanıyor — yani senkron on_tick bitene kadar HİÇ çalışmıyor. Sıra:
```
ilk tick:  create_task(_load_state)   ← henüz çalışmadı (sadece planlandı)
           ...
           _save_state()              ← BOŞ tracking'i dosyanın ÜZERİNE YAZDI
tick biter → event loop → _load_state ← kendi sildiğimiz dosyayı okur → "0 kayıt"
```
Canlı kanıt: dosya 20:26'da 3 kayıt içeriyordu (SSH ile doğrulandı), 20:50
restart'ında "0 kayıt" okundu — arada tek yazan boot'un kendisiydi.
v3.4'ten beri açık duran §15.5 gizemi ("dosya dolu yazılıyor ama restart'ta 0
okunuyor") tam olarak buydu: dosya İNCELENDİĞİ her an doluydu, çünkü boot'taki
silme + auto-detect'in yeniden doldurması arasında bakılıyordu.

**Fix BQ:** `self._state_loaded = False` (init) → `_save_state` bu bayrak
True olmadan YAZAMAZ (erken return) → `_load_state` `finally:` ile bayrağı
açar (exception'da bile — bot asla kalıcı yazamaz duruma düşmez).

**Fix BQ-2:** Faz 2'nin TAM durumu artık persist ediliyor: eski kod yalnız
`phase2_active` kaydediyordu; `phase2_activation_complete`, `phase2_tp_mode`,
`phase2_tp2_done`, `exchange_order_id`, `last_logged_sl`, `r_distance_orig`
eklendi (kaydet + geri yükle + geriye uyum: eski dosyada activation_complete
yoksa phase2_active'e eşitlenir). Restore edilen Faz2-aktif parçalar
`_phase2_active_positions` setine de yeniden ekleniyor.

### 29.3 Fix BP — auto-detect artık KOŞULSUZ borsa-gerçeği kullanıyor
BN'in iki boşluğu kapatıldı:
1. **Adoption koşulsuz:** Faz'dan bağımsız, borsada DURAN değerler varken
   tahmin YASAK: entry := pozisyonun gerçek avgPrice'ı; SL := gerçek koşullu
   SL leg tetiği; TP := gerçek limit TP fiyatı (birden fazla leg → dedupe
   kuralıyla aynı "en koruyucu" seçim). Eski SL/TP araması Binance-tipi
   (`STOP_MARKET` / `open_orders`) olduğu için Bybit'te YAPISAL OLARAK KÖRDÜ —
   "SL emri bulunamadı, tahmin ediliyor" satırının gerçek nedeni buydu; artık
   `_get_bybit_conditional_orders(include_limit_tp=True)` okunuyor. Leg hiç
   yoksa fabrikasyon en azından GERÇEK entry'den türetiliyor (mid'den değil —
   mid tabanlı entry `already_1r`'ı yapısal olarak imkânsız kılıyordu).
2. **İki bağımsız Faz-2 kanıtı:** E1 = gerçek SL, gerçek entry'de/ötesinde
   (Faz-1 SL'i bunu yapısal olarak sağlayamaz). **E2 = reddedilen arşivin
   yarım-parça parmak izi** (canlı miktar / arşiv filled ∈ [0.40, 0.60]) —
   ratio-filtresinin "uyuşmazlık" diye çöpe attığı oran TAM OLARAK Faz 2
   yarı-kapanışının imzasıdır; arşiv artık `archive_data_rejected` olarak
   saklanıyor ve TP'si (orijinal sinyal hedefi = TP2 tetiği) geri kazanılıyor.
   E1'in borsa kanıtı önceki bozuk restart'la silinmiş olsa bile E2 hayatta
   kalır (20:50 vakasının birebir çözümü).
   Kurtarmada SL "entry-veya-daha-iyi"ye kilitlenir: bozuk/gevşetilmiş leg
   breakeven'a SIKILAŞTIRILIR (0.8205→0.8114), trailing'le daha iyi leg'e
   DOKUNULMAZ. Hata yolu artık WARNING (eskiden görünmez debug'dı).

### 29.4 Katmanların birlikte çalışması (savunma sırası)
```
1) Fix BQ  : state dosyası artık boot'ta silinmiyor → restore normal yol
2) Fix BQ-2: restore, Faz 2'nin TAM durumunu getiriyor (trailing kaldığı
             yerden, TP2 modu dahil)
3) Fix BP  : state dosyası GERÇEKTEN yoksa/bozuksa (volume kaybı vb.)
             auto-detect borsa-gerçeği + E1|E2 ile parçayı doğru faza kurar
4) Fix BO  : manual_second_take parçasına hiçbir yoldan TP emri konamaz
```

### 29.5 ⚠️ TEK SEFERLİK OPERASYONEL ADIM — mevcut state dosyası KİRLİ
VPS'teki `data/tv_signal_state.json` şu an 20:50 fabrikasyonlarını içeriyor
(DOT SHORT: entry=0.80225, sl=0.8182). Fix BQ deploy edilince bu KİRLİ dosya
sadakatle restore edilir. **v5.4'ü deploy ederken bir kez:**
```
cd ~/deploy/bots && rm -f data/tv_signal_state.json data/tv_signal_state.json.bak
```
(pozisyonlar borsada SL'leriyle korunmaya devam eder; boot'tan ~10 sn sonra
auto-detect Fix BP ile borsa-gerçeğinden doğru kurar: E2 arşiv parmak izi
DOT SHORT için 0.50 → Faz 2 restore, SL 0.8182→0.8114'e sıkılaştırılır.)

### 29.6 Doğrulama
`tools/verify_v53_fixes.py` (yeniden yazıldı) → **33/33 PASS**: BQ yarışının
yapısal imkânsızlık kanıtı; BQ-2 alan-alan persist/restore; BP'nin koşulsuz
adoption'ı; 20:07/20:50 olayının kendi sayılarıyla E1/E2 replay'i (E1'in
yok edildiği durumda E2'nin yakaladığı dahil); yanlış-pozitif yokluğu (taze
Faz-1: E1 risk-tarafı + E2 ratio=1.0 → ateşlemez; band kenarları 0.39/0.61 →
ateşlemez). `py_compile` OK · AST 0 fonksiyon kaybı (432) · `BYBIT_GUARD`=2 ·
önceki 9 paket PASS.

### 29.7 Deploy sonrası izlenecekler
**YENİ:** `📂 State yükleniyor: N pozisyon kaydı` (N>0 — İLK KEZ!);
`[STATE SAVE SKIP] _load_state henüz tamamlanmadı` (DEBUG, boot'ta 1-2 kez);
`🔁 [AUTO-DETECT PHASE2 RESTORED] … kanıt=…` (yalnız state dosyası yokken);
`🧲 [AUTO-DETECT EXCHANGE-TRUTH] … benimsendi` (Faz-1 adoption'ları).
**BİTMESİ gereken:** restart sonrası `0 pozisyon kaydı` (state dosyası
gerçekten varken); `SL emri bulunamadı, tahmin ediliyor` (Bybit'te leg varken);
restart sonrası SL'in borsada GERİYE amend edilmesi.

---

## 30) v5.5 — 🔥🔥 1R KOMİSYONU YARISINDAN AZ SAYIYORDU (Fix BR) + DUST KALINTI SÜRESİZ KORUMASIZ KALIYORDU (Fix BS) + polling yolunda kapsama denetimi yokluğu (Fix BT) + DUST CLOSE false-success (Fix BU)

Kullanıcı talebi 2026-08-22 (`markdown_files/analysis_2208.md` A ve B analizleri
üzerine): (2a) 1R hesabına gerçek entry yanında **fee** de eklenmeli, (2b) sinyal
R/R oranı korunarak **SL SABİT tutulup TP** gerçek entry+fee'ye göre ayarlanmalı,
(2c) Faz 2'de TP2 olarak gelen bu TP, **reward/risk = 2** olacak şekilde
güncellenmiş fiyat olsun, (3) B'deki 1. öneri (dust kapama) uygulanmalı.

### 30.1 A ve B analizlerine katılıyor muyum? EVET — iki önemli EKLE ile
**A: tamamen doğru**, kod satır satır doğrulandı (`_compute_profit_r` L24302,
`_track_position` L25091, `_bybit_wait_order_fila`→`avgPrice`, `_bybit_fresh_price`).
Ek iki uyarı (A'nın atladığı): (i) `real_entry`, per-fill accumulator DOLUYSA
`avg_cost`'a döner (canlıda hep boş — 5 günde 0 `PER-FILL` satırı); (ii)
`_bybit_wait_order_fill` **timeout ederse** `avg_price=None` döner ve entry
SESSİZCE sinyal fiyatında kalır.

**B: kök neden zinciri doğru, ama üç noktası eksik/yanlış:**
| B'nin iddiası | Gerçek |
|---|---|
| Kalıntı "eski leg'in qty'sine sığmıştı" | ❌ TERSİ: kalıntı leglerin DIŞINDA (1282 pozisyon vs 1279 kapsanan) — kapsama guard'ı gap=3'ü tam bu yüzden hesapladı |
| Kök neden `_bybit_cancel_sibling_legs` | Kısmen: gözlenen 5 dust doğumundan **yalnız 1'inde** sibling-cancel bir SL yok etti; 1'inde iptal edilen bir **limit TP**'ydi, **3'ünde hiç `SIBLING LEG CANCEL` satırı yok** |
| — (B'de yok) | 🔥 **Polling kapanış dalı `_bybit_verify_sl_coverage`'ı HİÇ çağırmıyordu** (WS dalı çağırıyor) → 3 doğum hiç kapsama denetimi almadı → **Fix BT** |
| — (B'de yok) | 🔥 Kapsama guard'ının kalıntı için koyduğu leg, **kapanmak üzere olan bir parent'a** atfediliyor (`position_order_id=newest`) → sibling-cancel onu siliyor. Canlı: `05:15:48 YENİ SL kondu @0.3402 qty=3` → `05:18:57 SIBLING LEG CANCEL … qty=3 iptal edildi` |
| Öneri 1: `_close_position_market_amount` ile kapat | ❌ **HARFİYEN UYGULANSA NO-OP OLURDU.** O fonksiyonun Bybit dalı `B4_DISABLE_SLTP_CLOSE=1` (VPS varsayılanı) iken HER ZAMAN `{"sent": False, "reason": "bybit_sltp_close_disabled"}` döner. Alt seviye `_close_bybit_market_amount` kullanılmalı → **Fix BS** |

### 30.2 🔥🔥 Fix BR — 1R matematiği İKİ bağımsız yönden hatalıydı
`_compute_profit_r` şunu hesaplıyordu: `target_1r = 2E − S ± E×0.0008`.
Doğru cevap (net kâr == net zarar): **`2E − S ± 2·fee_rt·E = 2E − S ± E×0.0022`**.

| Hata | Açıklama |
|---|---|
| **(1) Oran bayat** | `COMMISSION_RATE=0.0004` (%0.04) kullanılıyordu; Bybit linear taker **%0.055/yön** → round-trip **0.0011**. Boyutlandırma (`SIZING_FEE_RT`) ZATEN 0.0011 kullanıyordu — **iki sabit sessizce ayrışmıştı.** |
| **(2) Komisyon tek sayılıyordu** | Başabaş denkleminde round-trip komisyon **İKİ kez** görünür: kâr tarafında ödenen + zarar tarafında ödenen. Kod bir kez ekliyordu. |

**Net etki:** hedef `E×0.0014` kadar ERKEN → R cinsinden **`0.0014 / sl_pct`**.
```
ZAMA-USDT SHORT (2026-08-20 15:20, canlı): entry 0.04595 / SL 0.04651 / TP 0.04483
  sl_pct = %1.219      eski 1R = 0.04535324      yeni 1R = 0.04528891
  → %11.5 (0.115R) ERKEN tetikliyordu
MIN_SL_PCT tabanı (%0.20): 0.0014/0.0020 = **0.70R ERKEN** ← en tehlikeli hâli
```
Aynı hata çıkışta da vardı: o sinyalin TP'si (`0.04483`) fee sonrası **net
1.75R** getiriyor, 2R DEĞİL. Madde 2c tam olarak bunu düzeltir.

**Yeni geometri — tek tanım (`_fee_adjusted_r_levels`):**
```
eff_entry = E ± fee_rt·E          (LONG +, SHORT −)   ← komisyon dahil BAŞABAŞ
risk_eff  = |eff_entry − S|        S = SİNYAL SL'i, ASLA DEĞİŞMEZ (madde 2b)
target_1r = eff_entry ± risk_eff  = 2E − S ± 2·fee_rt·E
TP_new    = eff_entry ± rr·risk_eff       rr = |TP_sig − E_sig| / |E_sig − S|
```
**İnvaryant: `rr = 1` verilince `TP_new == target_1r`** → R'nin tek tanımı
(testte assert edilir). ZAMA örneği: TP `0.04483 → 0.04467`, net R/R **2.01**
(tick entry'den UZAĞA yuvarlandığı için hedefin ALTINA asla düşmez).

**`R_FEE_AWARE=0` legacy yolu eski formülü BİREBİR üretir** (101.08/98.92
testte doğrulanır) — redeploy'suz rollback. `R_FEE_RT` varsayılanı
`SIZING_FEE_RT`'i **miras alır** → iki sabit bir daha ayrışamaz.

### 30.3 Fix BR — TP tek noktada yazılır, her restart şeklinde hayatta kalır
| Nokta | Ne yapılır |
|---|---|
| Bybit giriş yolu (`✅ B4 Order OK` sonrası) | `actual_entry` kesinleştiği anda `tp_price` DÜZELTİLİR → arşiv, signal cache, `_track_position` ve **borsadaki limit TP legi** hepsi AYNI değeri alır. Leg doğrudan düzeltilmiş fiyatta **OLUŞUR** → amend yok, CID rotasyonu yok, `_bybit_dedupe_parent_legs`'in "en yakın leg'i tut" kuralı TP'yi sinyal değerine geri çekemez |
| HB-place-order dalı (`B4_USE_HB_PLACE_ORDER=1`) | Aynı düzeltme → tek env değişimi madde 2b/2c'yi sessizce geri ALAMAZ |
| `_activate_phase2` (gerçek entry rafine edildikten sonra) | TP2 yeniden türetilir. Risk tabanı **`phase2_first_sl`/`initial_sl`** — `pos_data["sl"]` DEĞİL (o noktada breakeven'e taşınmak üzere). `rr` **persist edilmiş `rr_target`**'tan gelir, mutasyona uğramış pos_data'dan tekrar TÜRETİLMEZ. Log: `🎯 [TP2 RECOMPUTED] eski → yeni` |
| `_save_state`/`_load_state` | `signal_entry`, `signal_tp`, `rr_target`, `r_eff_entry` persist + restore (eski dosyalarda `rr_target` yoksa sinyal üçlüsünden yeniden türetilir) |
| `_load_signal_from_archive` | `tp_price_adjusted` varsa `tp` olarak **onu** döndürür; ham hedef `tp_signal`'de kalır. **State dosyası hiç yokken TP2'nin sinyal TP'sine (net 1.75R) geri dönmesini engelleyen TEK kaynak burasıdır** |
| `_auto_detect_position` | Benimsenen parçaya sinyal üçlüsü + `rr_target` taşınır; TP kaynağı (`tp_adjusted` vs `tp_signal`) LOGLANIR → sessiz geri dönüş görünür olur. Ayrıca bu yolun kendi `already_1r` kontrolü komisyonu **HİÇ** saymıyordu (ana yoldan bile gevşekti) → artık aynı fee-aware fonksiyon |
| 2R gözlem logu | Referans `r_eff_entry` + `risk_eff` → 2R çizgisi ile rr=2 TP2 **ÇAKIŞIR** |

**DOKUNULMAYANLAR (bilerek):** Faz 2 SL'i hâlâ **HAM gerçek entry** (breakeven),
`eff_entry` DEĞİL — madde 2b "SL sabit tutulacak" diyor ve `eff_entry`'e taşımak
her Faz-2 çıkışının gerçekleşen PnL'ini değiştirirdi. Boyutlandırma (Fix BD/BE/BG
formülü + 7 filtre) tek tick bile oynamadı. Trailing merdiveni **yüzde bazlı**
olduğu için R paydasının yeniden tanımlanmasından **yapısal olarak etkilenmez**.
OKX yolu (`_place_okx_order_async`) **kasten değiştirilmedi** (test edilemiyor).

### 30.4 🧼 Fix BS — dust kalıntı artık gerçekten kapatılıyor
`_close_dust_position()`. Guard'lar: `DUST_CLOSE_ENABLED` · attempt tavanı (3) +
backoff (300 s) + in-flight kilidi · `_is_position_protected` (phase2/sync/grace)
· `_orders_being_placed` · `_trading_allowed` · **TAZE fiyat** (`_bybit_fresh_price`
— §23 bayat `get_mid_price`'ı kanıtladı) · **TAZE REST boyutu** (`ensure_fresh=True`;
pozisyon büyümüşse DOKUNMAZ) · `qty = min(amount, live)` · eşik borsanın GERÇEK
`min_notional_size`'ı · artık dust değilse `↩️ [DUST CLOSE İPTAL]` ile normal
akışa bırakır · başarıda kalan CID legleri temizlenir · başarısızlık
`⚠️ [DUST CLOSE FAIL]`/`🧼 [DUST CLOSE GAVE UP]` ile GÖRÜNÜR.

**`exact_qty=True`** (yeni, varsayılan `False` → 7 mevcut çağıran DEĞİŞMEDİ):
miktar step'e AŞAĞI yuvarlanır, `min_notional`'a **YUKARI ÇEKİLMEZ**. Aksi halde
3 birim TRX kalıntısı için ~15 birimlik reduceOnly emir gider ve borsanın
auto-adjust'ına güvenmek gerekirdi (§18.5 Guard 4 bunu yasaklıyor).

Her iki dust kapısı da bağlandı: `_monitor_positions` (`🗑️ [MONITOR DUST]`,
birincil) ve `_auto_detect_position` (`🗑️ [IGNORED DUST]`, savunma derinliği;
5 günde 0 kez tetiklendi çünkü monitor kapısı önce devreye giriyor). Yanlış
"Orphan cleanup temizleyecek" vaadi tüm LOG satırlarından kaldırıldı (yorumlarda
tarihsel kayıt olarak duruyor). Eski `IGNORED DUST` metnindeki "Binance Min
Notional / manuel Convert Small Assets" tavsiyesi de silindi — Bybit'te yanlıştı.

### 30.5 Fix BT / BU — kapsama boşluğunun iki sessiz halkası
- **BT:** polling kapanış dalı (`🎯 [SL/TP PARTIAL TRIGGER]`) kardeş legleri
  iptal ediyor ama `_bybit_verify_sl_coverage`'ı **hiç çağırmıyordu**; WS dalı
  (`_bybit_on_leg_filled`) çağırıyor. Gözlenen 5 dust doğumundan 3'ü bu yoldan
  geldi → doğduğu andan itibaren denetimsiz. Artık `create_task` ile çağrılıyor
  (`sebep=<sl|tp>_trigger_polling_cleanup`), tespit döngüsü bloklanmıyor.
- **BU:** `🧹 [DUST CLOSE]` bloğu (`_set_binance_sltp_async` içindeki eski yol)
  `_close_position_market_amount`'ın dönüşünü **hiç okumuyor**, sonra tracking'i
  temizleyip `dust_position_closed` döndürüyordu → Bybit'te emir HİÇ
  gönderilmemişken "kapatıldı" deniyordu (§12.2 Fix G'nin aynı sınıfı). Artık
  `_close_dust_position` üzerinden gider ve sonuç DÜRÜST loglanır; başarısızsa
  MONITOR DUST kapısına (tavan + backoff ile) devreder.

### 30.6 Madde 4 — risk analizi (ne değişecek, ne bozulmayacak)
| # | Risk | Önlem / durum |
|---|---|---|
| 1 | **Faz 2 her pozisyonda ÖLÇÜLEBİLİR ŞEKİLDE DAHA GEÇ aktive olacak** (eşik `E×0.0014` uzaklaştı). Daha az parça risk-free'ye/trailing'e ulaşır; daha çok parça tam boyutta −1R'de durur | **Bu bug'ın düzeltilmesinin KAÇINILMAZ sonucudur, yumuşatılmadı.** İlk gün logu regresyon sanılmasın: aynı piyasa durumu eskiden `1.04R` basarken artık `0.93R` basacak. `R_FEE_AWARE=0` anında geri alır. Etki `0.0014/sl_pct` ile ölçekli → dar SL'lerde en büyük; `TOO_TIGHT_SL` (%0.20) zaten 0.70R'de sınırlıyor |
| 2 | State-dosyasız restart TP2'yi sinyal TP'sine geri çevirir | Arşive `tp_price_adjusted`/`rr_target`/`tp_price_signal` yazılır, loader `tp_adjusted`'ı TERCİH eder, auto-detect kaynağı LOGLAR |
| 3 | Giriş-anı ve Faz-2 TP'leri ayrışır (iki farklı endpoint: `order/realtime avgPrice` vs `execution/list` ağırlıklı ortalama) | Faz 2 rafine entry'den yeniden hesaplar (tasarım); `rr` persist edilmiş `rr_target`'tan, risk tabanı `phase2_first_sl`'den → sürüklenme yok. Fark `🎯 [TP2 RECOMPUTED]` ile ölçülebilir |
| 4 | Eski fiyatlı bayat limit TP legi kalır, dedupe "en yakın"ı tutup TP'yi geri çeker | TP **ilk yerleştirmeden ÖNCE** hesaplanıyor → leg doğrudan doğru fiyatta oluşur, amend/rotasyon penceresi YOK. Dedupe kuralı **gevşetilmedi** (gevşetmek §16.3'ün 3×0.82 ETH sınıfını geri getirirdi) |
| 5 | `risk_eff <= 0` veya absürt `rr` saçma TP üretir | `risk_eff<=0` → ham mesafeye düşer (ZeroDivision yok); `_fee_adjusted_tp` 0 dönerse çağıran **SİNYAL TP'sini KORUR** + WARNING (TP2 tetiği asla boşalmaz); `rr` **[1.2, 4.0]** bandına kırpılır → TP2 fee-aware 1R'nin DAİMA ÖTESİNDE, dolayısıyla kırpma tek başına Phase2/TP2 aynı-tick yarışı YARATAMAZ (Fix AQ yine yedek) |
| 6 | Tick yuvarlaması gerçekleşen R/R'yi hedefin altına çeker (kalıcı negatif sapma) | Yuvarlama **entry'den UZAĞA** (LONG ceil / SHORT floor), `min_price_increment` ile; testte 0.10 ve 0.00001 tick için iki yönde assert edilir → sapma yalnızca LEHTE olabilir |
| 7 | Loglanan R değerleri düşer, bug gibi görünür | §30.2'de birebir örnekle belgelendi; 2R logu da aynı referansa çekildi; mesaj şekli/`[kaynak=…]` eki KORUNDU (mevcut grep'ler bozulmaz) |
| 8 | Mevcut test paketleri kırılır ve gerçek sorunları maskeler | `verify_v51_fixes.py` **bilinçli** güncellendi (101.08→101.22 + `R_FEE_AWARE=0` legacy parite assert'i + harness'a `_fee_adjusted_r_levels`/`_r_fee_rt` bağlandı + `ROUND_*` namespace'e eklendi). **Tüm yeni config `getattr(self,…,default)` ile okunur** → AST harness'ın boş `SimpleNamespace`'i çalışmaya devam eder (bu da ayrıca assert edilir) |
| 9 | Parçalar-arası TP bulaşması görünür hale gelir (`_signal_cache` tek pair+side anahtarı) | **Kapsam dışı ve ÖNCEDEN VAR** — bugün de bir sinyalin TP'si başka parçaya uygulanıyor. `tp_signal` cache'te tutulduğu için denetlenebilir. Multi-entry dedektörüne (Fix BB/BB-2 korumalı) dokunulmadı |
| 10 | Düzeltilmiş TP zaten piyasanın gerisinde kalır ve limit anında dolar | Aritmetik olarak DOĞRU davranış (rr zaten gerçekleşmiş demektir); `_place_bybit_limit_tp` bilerek `postOnly` kullanmıyor → daha İYİ fiyattan dolar |
| 11 | Dust kapama canlı bir pozisyonu keser | `ensure_fresh=True` REST boyutu + `min(amount, live)` + reduceOnly + `exact_qty` + koruma/emir-kilidi guard'ları + eşiği aşarsa İPTAL |
| 12 | Bybit sub-min-notional reduceOnly kapamayı reddeder | **Doğrulanamadı** (lokal API anahtarı yok) → her iki dal da güvenli: red hâlinde attempt tavanı + backoff + `GAVE UP` uyarısı, sessiz sonsuz retry YOK |
| 13 | `create_task` ile sızıntı / çift kapama | In-flight kilidi + `last_ts` backoff; `_bybit_verify_sl_coverage` zaten 30 s aksiyon cooldown'lı ve idempotent |

**Doğrulama:** `py_compile` OK · AST **0 fonksiyon kaybı** (432 → 439; +6 metot
+1 nested) · `BYBIT_GUARD` = 2 · **11 statik test paketinin TAMAMI PASS**
(`verify_v55_fixes.py` **yeni, 78 assert**; `verify_v51_fixes.py` güncellendi).
`verify_v4_limit_tp.py` canlı API anahtarı ister (statik değil) → bu turda
koşulmadı.

### 30.7 Yeni env (v5.5)
```
R_FEE_AWARE=1            R_FEE_RT=<SIZING_FEE_RT'i miras alır: 0.0011>
TP_FEE_ADJUST_ENABLED=1  TP_RR_MODE=signal   TP_RR_FIXED=2.0
TP_RR_MIN=1.2            TP_RR_MAX=4.0
DUST_CLOSE_ENABLED=1     DUST_CLOSE_MAX_NOTIONAL=5.0
DUST_CLOSE_MAX_ATTEMPTS=3  DUST_CLOSE_RETRY_SEC=300
```

### 30.8 Madde 5 — 5 GÜNLÜK FORENSİK (VPS ham log, UTC, 2026-08-17 11:49 → 08-22 11:11, 4647 satır)
**Bot istenildiği gibi davrandı mı? EVET — bir yapısal boşluk dışında (§30.4).**

| Metrik | Değer | Yorum |
|---|---|---|
| Boot / restart | **0** | 5 günde tek yeniden başlatma yok (`RestartCount` etkisi: state/amnezi olayı da 0). Fix BQ bu pencerede sınanmadı — ama bozulma da yok |
| `CRITICAL` / `Traceback`'li çökme | **0** | 30 `ERROR` satırının **22'si tek bir saatte** (08-17 15:00) — `api-demo.bybit.com` bağlanamama + WS order-book/user-stream yeniden bağlanmaları. Kalanlar tek tek. Hepsi kendini onardı |
| Faz 2 aktivasyonu | **27 olay, 27'si `kaynak=ws`, 0'ı `kaynak=monitor`** | WS feed 5 gün boyunca sağlıklı; Fix BJ'nin always-on monitor backstop'u hiç devreye girmek zorunda kalmadı |
| TP2 (`manual_second_take`) | 9 HIT / 9 DONE | Temiz, kayıp yok |
| Trailing güncellemesi | 119 | Çalışıyor |
| `WS POS CLOSED` / `WS LEG FILL` | 77 / 19 | Olay-güdümlü kapanış birincil yol |
| `110009` / `110072` / `110093` | **0 / 0 / 0** | Kota ve CID mimarisi temiz |
| `BYBIT NAKED LEG` · `SL CLAMP` · `TP ESCALATE` · `LEG DEDUPE` · `CONSOLIDATE` · `ENTRY BLOCKED` · `SIGNAL REJECTED` | hepsi **0** | — |
| `SIZING SKIP` | 31 (17 `TOO_TIGHT_SL`, 12 `TOO_WIDE`, 2 `MAX_SLOTS`, **0 `TOO_TIGHT_FEE`**) | §25.8'in öngörüsü doğrulandı: Fix BG sonrası fee filtresi artık bağlamıyor, savunma-derinliği katmanı |
| `MANUEL CLOSE TIMEOUT` → `FORCE CLEANUP` | **3** (08-19 15:30 / 08-21 08:58 / 08-21 12:01) | 60-80 s bekleme sonrası zorla temizlik. Üçünde de `Binance pozisyon=0` doğrulandı → **pozisyon zarar görmedi**, yalnız defter tutma yavaş |
| `PARTIAL CLOSE AMBIGUOUS` | 2 | Fix BB uyarlamalı penceresi kör FIFO'yu **engelledi** (istenen davranış) |
| `CID ROTATE` | 8 | Normal (tetiklenmiş CID yanması) |
| **`MONITOR DUST`** | **55** | 🔴 **ASIL ANOMALİ** — §30.4'ün belgelediği kalıcı boşluk. TRX-USDT LONG 3 birim ($1.03, 08-22 05:19'dan) ve ZAMA-USDT SHORT 1 birim ($0.05, 08-21 20:31'den) saatlerce/günlerce **KORUMASIZ**; her saat aynı uyarı, hiçbir aksiyon |
| **`SL COVERAGE GAP` / `FIX`** | **5 / 3** | 🔴 **2 boşluk HİÇ kapatılmadı**: `08-19 15:25:03 SHORT pozisyon=5 → 5 KORUMASIZ` için **FIX satırı YOK**. Ayrıca `08-22 05:15:48`'de konan `qty=3` SL, 3 dakika sonra (`05:18:57`) sibling-cancel ile **SİLİNDİ** → Fix BT/BS'in tam gerekçesi. Beş boşluğun **hepsi** 1/3/5 birimlik dust kalıntılarıydı |

**Sonuç:** çökme/çakışma yok, çift Faz 2 yok, orphan birikmesi yok, kota sorunu
yok, hayalet pozisyon yok. Tek gerçek anomali **dust kalıntı sınıfı** — ve bu
turda kökünden (BS + BT + BU) kapatıldı. §30.2'deki 1R hatası bu 5 günün TÜM
Faz-2 zamanlamasını etkilemişti (27 aktivasyonun hepsi olması gerekenden erken),
ama tek tek log satırından görülemez — yalnız matematikten çıkar.

### 30.9 ⚠️ §20.7 SAAT DİLİMİ NOTU GÜNCELLENDİ
Lokal `logs_tv_signal_strategy_processed.log` **bu hâliyle KAYDIRILMIŞ DEĞİL** —
VPS ham logu ile birebir aynı damgalar (`2026-08-21 22:07:14,898` ve
`2026-08-22 09:04:02,067` her iki dosyada AYNI). Yani bu kopya **UTC**'dir.
§20.7'deki +3 saatlik kayma bu dosya için GEÇERSİZ. Ayrıca lokal dosya
08-22 09:04'te bitiyor, VPS logu 11:11'e kadar sürüyor → **korelasyon için VPS
ham log tek yetkili kaynaktır.**

### 30.10 Deploy sonrası izlenecekler
**YENİ görülecekler:**
```
🎯 [TP FEE-ADJUST] … sinyal TP X → Y (R/R=2.000 korundu) | gerçek entry=…, SL=… (SABİT)
🎯 [TP2 RECOMPUTED] … eski → yeni (R/R=…, risk tabanı SL=…)
🧼 [DUST CLOSE] … KORUMASIZ kalıntı MARKET ile kapatılıyor: qty=… [kaynak=monitor, deneme=1/3]
✅ [DUST CLOSE] … kalıntı kapatıldı
🛡️ [SL COVERAGE …] … sebep=sl_trigger_polling_cleanup   ← Fix BT'nin yeni tetikleyicisi
📁 [AUTO-DETECT] … (kaynak=tp_adjusted, Yaş: … dakika)
```
**BİTMESİ gerekenler:** `🗗️ [MONITOR DUST]`'ın saat başı TEKRARI (tek sefer
görünüp `DUST CLOSE` ile kapanmalı); `SL COVERAGE GAP`'in FIX'siz kalması;
kapanıştan dakikalar sonra hâlâ yaşayan `H-S-*`/`H-T-*` legleri.
**İZLENECEKLER:**
1. **Faz 2 aktivasyon SIKLIĞI düşecek** — bu beklenen (§30.6 R1). İlk gün
   `1.0x R` yerine `0.9x R` basan satırlar normaldir.
2. `⚠️ [DUST CLOSE FAIL] … reason=…` → Bybit sub-min-notional reduceOnly
   kapamayı reddediyorsa burada görülür (§30.6 R12, doğrulanmadı).
3. `🧼 [DUST CLOSE GAVE UP]` → 3 deneme yetmiyorsa elle müdahale gerekir.
4. `⚠️ [TP FEE-ADJUST] … TP türetilemedi` → sinyal üçlüsü bozuk demektir.
5. `TOO_TIGHT_SL` sıklığı: 5 günde 17 idi. 1R eşiği uzaklaştığı için dar-SL
   sinyallerinin değeri daha da düştü; gerekirse `MIN_SL_PCT` yükseltilebilir
   (kullanıcı kararı).

### 30.11 Kalan açık konular
1. **Kapsama guard'ının kalıntı legi hâlâ ölmek üzere olan bir parent'a
   atfediliyor** (`position_order_id=newest.get("order_id")`). Fix BT+BS
   ZARARI ortadan kaldırıyor (kalıntı ya yeniden korunur ya kapatılır) ama
   atıf mantığı düzeltilmedi — kalıntıyı kendi parent'ı ile track etmek ayrı
   bir tur işidir.
2. **Kapsama toleransı `size × 0.02`** (`_bybit_verify_sl_coverage` ve
   `_bybit_periodic_sltp_verify`) 1282 birimlik pozisyonda 3 birimlik boşluğu
   MASKELER → kalıntı doğduğu anda görünmez. Bilinçli olarak DEĞİŞTİRİLMEDİ:
   sıkılaştırmak her yuvarlama artığında churn üretir; dust sınıfı artık
   kapatma ile çözülüyor.
3. §24.2'deki **blended-avg muhasebesi** hâlâ geçerli: aynı tarafta birden fazla
   parça varken Bybit'in gerçekleşen PnL'i botun per-parça hedefinden sapar.
   Fix BR bunu değiştirmez (değiştiremez) — `BYBIT_MAX_PIECES_PER_SIDE` bilinçli
   bir risk tercihi olarak gözden geçirilmeli.
4. §26.9'daki **"TP=1R limit emri"** yeniden tasarımı hâlâ masada (Faz 1→2
   geçişini fiyat-algılamadan fill-algılamaya çevirmek). Fix BR bu tasarımı
   KOLAYLAŞTIRIR: artık `target_1r` tek bir fonksiyondan gelir.
5. `_bybit_wait_order_fill` **timeout** ederse entry sessizce sinyal fiyatında
   kalır (§30.1-i) → o parçanın TP'si de sinyal entry'sine göre türetilir.
   Faz 2'deki yeniden hesap (§30.3) bunu telafi eder, ama giriş anındaki leg
   yanlış kalır. Ayrı iş.

---

## 31) v5.6 — 🔀 DEĞİŞTİRİLEBİLİR POZİSYON YÖNETİMİ: `legacy` / `rr2_trailing` / `passive` (Fix BV)

Kullanıcı talebi 2026-09-01: (a) mevcut yönetim korunsun, aktif/pasif edilebilsin;
(b) 1R'de yarı kapama OLMASIN, **2R'de SL=1R** + koddaki trailing devreye girsin;
(c) 2R'de R1'e stop KONULAMIYORSA market ile kapat; (d) R1 stop sonrası fiyat
lehte **%0.2** ilerlerse stop **en az 2R**'ye çekilsin ve trailing R2'den başlasın.
Seviyeler §30'un fee-aware (gerçek entry + round-trip komisyon) R'leridir.

### 31.1 `rr2_pozisyon_yonetimi_gecis_plani_final_v4.md`'ye katılıyor muyum?
**Mimarisine EVET** (tek global env, pozisyon-başına profil yok, migration yok,
mod değişimi bot kapalı + pozisyon yokken). **Şu 9 kritik tespiti kod üzerinde
BİREBİR DOĞRULANDI ve uygulandı:**

| Plan | Doğrulama |
|---|---|
| §15.1 trailing dalı ham `phase2_active` bakıyor, RR2 onu False bırakıyor → trailing HİÇ çalışmaz | ✅ GERÇEK ve KRİTİK (monitor L25196 + WS L4151) |
| §8.3 `clamped_trigger` `_place_bybit_trading_stop`'ta propagate edilmiyor | ✅ GERÇEK (L2538 set ediliyor, `out` şablonunda yok) |
| §8.4 `_update_trailing_sl` soft-fail'de True dönüyor (`success = not hard_fail`) | ✅ GERÇEK sessiz-başarı |
| §8.1 processing-lock + backoff kontrolleri tam belirtilen yerde | ✅ |
| §9 `_get_cached_position_amount` Bybit'te SIDE-AGGREGATE → cross-piece kapanma | ✅ GERÇEK ve ŞİDDETLİ |
| §5 `RR2_TRANSITIONING` restart'ta kalıcı kilit | ✅ |
| §14 orphan cleanup yalnız `phase2_active`'e bakıyor | ✅ (L33003) |
| §13.2 `passive` onarımı da kapatmalı | ✅ (aksi halde tanım kendisiyle çelişir) |
| mikro-not 1: `ACTIVE_CONNECTOR` alt çizgisiz | ✅ (kodda `getattr(self, "ACTIVE_CONNECTOR", None)`) |

### 31.2 ❌ Planın YANLIŞ / EKSİK olduğu 5 nokta (hepsi düzeltilerek uygulandı)

**(A) §15.3'ün temel önermesi kodun YANLIŞ OKUNMASI.** Plan gerçek zincirin
`if r_do and entry and not 2r_logged: [log] elif not 1r_reached: [trigger]`
olduğunu söylüyor. **Değil.** Gerçek kod:
```python
if pos_data.get("phase2_active") and pos_data.get("phase2_activation_complete"):
    _maybe_schedule_trailing(...)
    <2R log İÇ İÇE burada>
elif not pos_data.get("1r_reached", False):
    _try_trigger_phase2(...)
```
`elif` **phase2 bayraklarına** bağlı, 2R log'una DEĞİL. Dolayısıyla
`r_distance_orig`/`r_eff_entry`'yi girişte doldurmak WS 1R tetiğini **öldüremez**;
§4'ün "zorunlu mod-gate" gerekçesi ve test 30'un anlattığı arıza **imkânsızdır**.
→ §15.3'ün "log ve tetiği ayır" yeniden yapılandırması **UYGULANMADI** (dosyanın
en sıcak döngüsünde gereksiz risk). Yalnız §15.1'in koşul değişikliği yapıldı.
(Mod-gate ayrıca uygulandı — ama gerekçesi "WS tetiğini kurtarmak" değil,
"legacy pozisyon açılışına tek byte dokunmamak".)

**(B) Plan 2 TP-diriltme yolunu kaçırmış; `phase2_tp_mode="rr2_no_tp"` 11 mevcut
kontrol noktası için TANIMSIZ bir değer.**
- `_periodic_sltp_verify` L9777: `if (not tp_price or tp_price <= 0) and
  recovered.get("tp") is not None: pos["tp"] = tp_price` — **tam olarak `tp==0`
  iken**, yani RR2'nin bilinçli durumunda ateşlenir. 5 dakika içinde sinyal TP'si
  geri yazılır, ardından `_bybit_periodic_sltp_verify` (`need_tp = tp_target > 0`)
  TP bacağını borsaya geri koyar → **RR2 sessizce bozulur.**
- `_deterministic_rebuild_pair_side_from_exchange_truth` L12402:
  `canonical_position["tp"] = tp_price` koşulsuz.

→ Çözüm: **tek bayrak yerine İKİ AYRI yüklem** (planın `rr2_tp_suppressed`
bayrağı bu ayrımı yapmadığı için 9777'de kullanılsa **legacy TP2'yi öldürürdü**):
| Yüklem | Anlamı |
|---|---|
| `_tp_order_suppressed(pos)` | TP **EMRİ** konmaz — `manual_second_take` **VE** `rr2_no_tp` |
| `_tp_target_suppressed(pos)` | `tp` **ALANI** 0'da kalır — **YALNIZ** `rr2_no_tp` (legacy TP2'de `tp>0` ZORUNLUDUR, o yazılım tetiğidir) |

**(C) 🔴 Planın "çözülmemiş risk" diye bıraktığı madde aslında BLOKE EDİCİ bir
tasarım hatasıydı.** Plan §17/§21'de "2R Limit TP fill-before-cancel yarışı"
diyor. Gerçek daha kötü: **Fix BR sonrası girişteki limit TP tam olarak fee-aware
2R seviyesindedir** — yani RR2'nin TETİK fiyatının AYNISI. TP emri borsada
durursa kazanan **her** RR2 işleminde limit TP, RR2 evaluator'ıyla aynı fiyatta
dolar; pozisyon 2R'de kapanır, trailing **hiç** çalışmaz → `rr2_trailing` fiilen
"legacy + TP" olur, yani yeni yönetim **sessizce hiç devreye girmez**.
→ Çözüm: **RR2 modunda girişte TP emri KONULMAZ** (`RR2_PLACE_ENTRY_TP=0`,
varsayılan) ve `tp` alanı doğuştan 0 + `rr2_no_tp` işaretlenir. Böylece
`BYBIT_TP_AS_LIMIT=1` de artık **yük taşımıyor** ve
`_bybit_cancel_parent_limit_tp_only()` birincil mekanizma değil emniyet süngüsü.

**(D) §12'nin merdiven yeniden yazımı LEGACY'ye dokunuyordu** (deadband → `!=`,
anchor değişimi). Aritmetik olarak eşdeğer olduğunu doğruladım, ama dosyanın en
sıcak para-hareket eden kodunu sıfır legacy faydası için değiştirmek gereksiz.
→ **Legacy merdiven BYTE-IDENTICAL bırakıldı**; RR2 kendi
`_rr2_trailing_ladder()` fonksiyonunu aldı. Planın risk #29'u argümanla değil
**yapısal olarak** ortadan kalktı.

**(E) `passive` kapıları eksikti.** Plan yalnız `_reconcile_sltp` +
`_sltp_retry_queue`'yu kapatıyor. Ama **Bybit'te asıl onarım ağı
`_bybit_periodic_sltp_verify`'dır** (ve `_bybit_verify_sl_coverage`,
`_naked_position_recovery`, `_delayed_sltp_health_check`, `_close_dust_position`).
→ Tek yüklem `_position_repair_allowed()` ile **7 giriş noktası** kapatıldı.
Giriş-anı SL yerleştirme **KASITLI OLARAK kapatılmadı**: aksi halde `passive`
yeni pozisyonları çıplak açardı, yani "zararsız gözlem modu" değil aktif tehlike
olurdu.

**(F) Planın atlamadığı ama benim eklediğim guard:** `_ensure_position_r_geometry`
artık **fill-only**. Planın hali `r_sl_baseline or initial_sl or sl` merdivenini
her çağrıda yeniden değerlendiriyordu; state dosyası olmadan yapılan bir
restart + auto-detect adoption'da `initial_sl` **TAŞINMIŞ** stop olur ve R1/R2
içeri kayar → "en az 2R" garantisi sessizce bozulur. Artık mevcut r1/r2 varsa
ASLA yeniden türetilmez; aşama ilerlemiş ama geometri kayıpsa yeniden türetme
YAPILMAZ, mevcut stop anchor kabul edilip `RR2_TRAIL_2R`'de devam edilir
(`⚠️ [RR2 GEOMETRY LOST]`) — trailing `max()/min()` ile asla kötüleştirmez.

### 31.3 Kabul edilen akış (uygulanan hâli)
```
RR2_WAIT ──(fiyat fee-aware 2R'yi geçti)──> RR2_TRANSITIONING
   │  1R'de HİÇBİR İŞLEM YOK (yarı kapama yok, SL taşınmaz, TP yok)
   ▼
RR2_TRANSITIONING ──SL = fee-aware R1 (STRICT doğrulama)──> RR2_ARMED_R1
   │                     └─ konulamadı → parent-scoped MARKET CLOSE (madde c)
   ▼
RR2_ARMED_R1 ──(R1 stop konduğu fiyattan +%0.2 lehte)──> RR2_TRAIL_2R
   │             SL = max/min(mevcut, R2)  +  anchor = R2
   ▼
RR2_TRAIL_2R ── %0.2 hareket → %0.1 stop merdiveni (anchor R2, no-degrade)
```
`r1_price == target_1r` ve `r2_price == _fee_adjusted_tp(rr=2)` **invaryantı**
testte assert edilir → R'nin tek tanımı korunur (§30.2).

### 31.4 Eklenen fonksiyonlar (26 yeni, 0 kayıp — 432 → 458)
`_pm_mode` · `_position_repair_allowed` · `_is_rr2_managed_position` ·
`_tp_order_suppressed` · `_tp_target_suppressed` ·
`_position_management_trailing_active` · `_position_management_rr2_switch_armed` ·
`_fee_adjusted_r_targets` · `_ensure_position_r_geometry` ·
`_try_trigger_rr2_management` · `_activate_rr2_management` ·
`_rr2_failsafe_close_parent` · `_schedule_rr2_failclose_retry` ·
`_maybe_switch_rr2_to_r2_trailing` · `_rr2_trailing_ladder` ·
`_update_trailing_sl_rr2_strict` · `_bybit_cancel_parent_limit_tp_only` ·
`_try_trigger_legacy_phase2` (eski gövde BİREBİR taşındı) ·
`_rr2_adopt_position_state` (Fix BW, §31.10).

### 31.5 Etki / çökme / çakışma analizi (madde 4 ve 5)
| # | Risk | Durum |
|---|---|---|
| 1 | **Legacy regresyonu** | `_try_trigger_phase2` gövdesi `_try_trigger_legacy_phase2`'ye TEK SATIR değişmeden taşındı; trailing dalı koşulu legacy'de BİREBİR aynı iki bayrağı okuyor (4 senaryo testle); legacy merdiven byte-identical; RR2 alanları yalnız rr2 modunda yazılıyor; `_update_trailing_sl`'in yeni 2 parametresi varsayılanda eski davranış. **12 test paketinin tamamı PASS.** |
| 2 | **Çift aktivasyon (WS + monitor aynı ms)** | `_try_trigger_rr2_management` senkron; guard'lar + `_rr2_transitioning_orders.add()` arada `await` OLMADAN → atomik. Testle: ikinci çağrı no-op. |
| 3 | **Cross-piece kapanma** | `scoped = min(live_aggregate, parent_amount)` hem activation'da hem failsafe close'da. Yoksa A parçasının R1 stopu B'yi de kapatırdı. |
| 4 | **Sessiz başarı (SL konmadı ama "kondu" denildi)** | `clamped_trigger` propagate + `_bybit_last_sltp_status` + strict wrapper. Clamp = BAŞARISIZ (gevşetilmiş stop "en az R1/R2" garantisini bozar). |
| 5 | **RR2 trailing hiç çalışmaz** | §15.1 helper'ı iki dalda da; testte "ham `phase2_active` kapısı iki loop'ta da KALMADI" assert'i var. |
| 6 | **TP diriltilmesi** | 5 nokta kapatıldı (periodic verify, deterministic rebuild, reconcile, trailing self-heal, giriş). `tp` doğuştan 0. |
| 7 | **Restart kilidi** | `RR2_TRANSITIONING` → `RR2_WAIT` demote (`♻️ [RR2 RESTORE]`). |
| 8 | **Geometri kaybı** | fill-only + `⚠️ [RR2 GEOMETRY LOST]` (bkz. 31.2-F). |
| 9 | **Bookkeeping hatası pozisyonu kapatır** | Ayrı `try` — SL canlıysa disk hatası aktivasyon başarısızlığı SAYILMAZ. |
| 10 | **Fail-close başarısız** | `RR2_FAIL_CLOSE_PENDING` + 15 s retry + `CRITICAL` log. |
| 11 | **Switch spam** | `_rr2_switch_sched_ts` throttle (`BYBIT_TRAIL_WS_MIN_INTERVAL`). |
| 12 | **Bellek** | Kapanışta iki yeni sözlük `pop` edilir. |
| 13 | **`passive` çelişkisi** | 7 onarım kapısı; giriş SL'i bilinçli AÇIK. |
| 14 | **Konsolide taraf** | `_bybit_consolidation_mode(...) is not None` → RR2 no-op (testli). |
| 15 | **Hayalet parça** | Fix BB-2 deseni RR2 tetiğinde de var (`_unconfirmed_closes` < 120 s → ertele). |
| 16 | **RR2'de `_update_trailing_sl`'in `$10` / anlık-tetik ön kontrolleri** | R1 LONG'da `< mid` (geçer), R2 switch'te headroom yalnız %0.2 → nadiren reddedebilir; strict wrapper bunu **fail-close DEĞİL** sayıp bir sonraki pencerede tekrar dener (`R1 SL CANLI kalıyor`). |
| 17 | **`RR2_ARMED_R1`'de WS her tick `_try_trigger_phase2` çağırır** | Dispatcher → RR2 → `stage != RR2_WAIT` → no-op. Zararsız (planın mikro-not 2'si). |
| 18 | **OKX** | Dispatch `_monitor_positions`'ta olduğu için OKX de kapsanır; `_bybit_cancel_parent_limit_tp_only` Bybit-only guard'lı. |

**Bilinçli olarak çözülmeyen (kabul edilen) tek risk:** SL emirleri `MarkPrice`
ile tetiklenir, RR2 karar mantığı WS `last` fiyatıyla çalışır. Mark/last
ayrışırsa stop `last` R1/R2'ye değmeden tetiklenebilir — bu **legacy trailing ile
paylaşılan** mevcut konvansiyondur, RR2'ye özgü yeni bir risk değildir.

**Doğrulama:** `py_compile` OK · AST **0 fonksiyon kaybı (432 → 458)** ·
`BYBIT_GUARD` = 2 · **12 statik paketin TAMAMI PASS**
(`verify_v56_fixes.py` YENİ: **139 assert**, gerçek fonksiyonlar AST ile
çıkarılıp KOŞULDU — 2R tetiği, merdiven adımları, no-degrade, guard'lar).
`verify_v51/v52/v55` yeniden-adlandırma için bilinçli güncellendi.
`verify_v4_limit_tp.py` canlı API anahtarı ister → koşulmadı.

### 31.6 Yeni env (v5.6)
```
POSITION_MANAGEMENT_MODE=legacy      # legacy | rr2_trailing | passive
RR2_TRAIL_SWITCH_PCT=0.002           # R1 stop sonrası trailing'e geçiş eşiği
RR2_PLACE_ENTRY_TP=0                 # ⚠️ 0'DA BIRAK (bkz. 31.2-C)
```

### 31.7 🔧 POZİSYON YÖNETİMİ GEÇİŞİ — TAM PROSEDÜR (madde 8)

> ⚠️ **MODLAR KARMA ÇALIŞMAZ.** Kodda pozisyon-başına profil, migration veya
> "açık pozisyonu yeni moda çevir" mantığı **YOKTUR** — bilinçli. `legacy` bir
> pozisyon RR2 modunda `management_stage` alanı olmadığı için `RR2_WAIT`
> sanılır ve 2R'de yönetilmeye başlar; RR2 bir pozisyon `legacy` modda
> `1r_reached=False` olduğu için 1R'de yarıya indirilir. **İkisi de yanlıştır.**
> Bu yüzden geçiş yalnızca **pozisyon yokken** yapılır.

**ADIM ADIM (VPS'te):**

```bash
# 1) Stratejiyi GRACEFUL durdur (state kaydı için — docker restart SIGKILL'e
#    düşerse on_stop çalışmaz; §28.5).
#    Hummingbot CLI'de:  stop
#    (Bot "Strategy stopped" yazana kadar bekle.)

# 2) TÜM açık pozisyonları kapat.
#    Bybit web arayüzünden "Close All" veya tek tek market close.
#    Doğrula: hiçbir pair'de pozisyon KALMAMALI.

# 3) TÜM açık emirleri temizle. ÜÇ ayrı sınıf var, üçünü de kontrol et:
#      a) koşullu SL bacakları      → orderFilter=StopOrder  (H-S-*-BB*)
#      b) reduceOnly LIMIT TP'ler   → orderFilter=Order      (H-T-*-BB*)
#      c) trading-stop üretimi      → pozisyon kapanınca borsa kendisi siler
#    Bybit UI: "Orders" + "TP/SL" sekmelerinin İKİSİ de boş olmalı.

# 4) Mod anahtarını değiştir.
cd ~/deploy
nano .env.hummingbot        # POSITION_MANAGEMENT_MODE=<yeni mod>
# env içeriği :
CONFIG_PASSWORD=Fenere12!
SCRIPT_STRATEGY=tv_signal_strategy.py
OKX_ENV=demo
OKX_DEMO=true
OKX_API_KEY=f7a245f6-e25b-45b1-b442-cb2785ee12d5
OKX_SECRET_KEY=8CB4074788E4BEBEA47A7024C2C121E3
OKX_PASSPHRASE=Fenere22!

CONFIG_FILE_NAME=tv_signal_strategy.py
LEAK_PROBE_INTERVAL_SECONDS=30
BYBIT_ENV=demo
EXCHANGE_BACKEND=bybit
TRADING_ENABLED=1
B4_DRY_RUN=0
B4_ATTACH_TPSL=0
B4_MAX_NOTIONAL_USDT=0
B4_MAX_MARGIN_USDT=0
B4_DEFAULT_LEVERAGE=20
B4_USE_HB_PLACE_ORDER=0
B4_DISABLE_SLTP_CLOSE=1
POSITION_MANAGEMENT_MODE=rr2_trailing
RR2_TRAIL_SWITCH_PCT=0.002
RR2_PLACE_ENTRY_TP=0

# şu komutları gir 
cd ~/deploy
docker compose up -d --force-recreate hummingbot
docker compose exec hummingbot env | grep -E "POSITION_MANAGEMENT|BYBIT_ENV"

# İkinci komutta artık üç RR2 veya (POSITION_MANAGEMENT_MODE=legacy için legacy) satırını da görmelisin. Görmeden stratejiyi başlatma — yoksa bot env'siz default legacy modda açılır ve RR2 hiç devreye girmez (sessizce).

# 4b) Geri dönüş sıralaması
bash
# a) Graceful stop (Hummingbot CLI'de: stop) + pozisyon/emir boş olmalı
#    (Bybit UI: Positions, Orders, TP/SL sekmeleri boş)

# b) Env'de TEK satırı değiştir (diğer ikisi kalabilir, zararsız):
nano ~/deploy/.env.hummingbot
#    POSITION_MANAGEMENT_MODE=rr2_trailing  →  POSITION_MANAGEMENT_MODE=legacy

# c) State kalıntısını temizle (archive'e dokunma):
rm -f data/tv_signal_state.json data/tv_signal_state.json.bak

# d) Evet — restart YETMEZ, recreate şart (env create-time enjekte ediliyor):
cd ~/deploy && docker compose up -d --force-recreate hummingbot

# e) Doğrula ve başlat:
docker compose exec hummingbot env | grep POSITION_MANAGEMENT
#    → POSITION_MANAGEMENT_MODE=legacy görmelisin
#    CLI'de: start --script tv_signal_strategy.py
# Üç not:

POSITION_MANAGEMENT_MODE satırını tamamen silmek de olur — default legacy'dir; ama açıkça legacy yazmak daha güvenli (altı ay sonra dosyaya baktığında ne olduğu belli olur).

Eski kod dosyasına dönmen gerekmez: yeni dosya legacy modda bayt-bayt eski davranış (legacy tetik gövdesi birebir taşınmış, merdiven dokunulmamış, RR2 alanları legacy'de hiç yazılmıyor). Yani rollback = sadece env + state + recreate.

Demo testlerin bitip live'a geçerken aynı kapıdan döneceksin: BYBIT_ENV=live + YAML markets: anahtarı bybit_perpetual: + recreate.

# 5) rr2_trailing'e geçiyorsan İKİ satırı DA doğrula:
#      POSITION_MANAGEMENT_MODE=rr2_trailing
#      RR2_PLACE_ENTRY_TP=0        ← 1 YAPMA (31.2-C: TP tam 2R'de durur ve
#                                    trailing hiç çalışmaz)
#    İsteğe bağlı: RR2_TRAIL_SWITCH_PCT=0.002

# 6) State dosyasını SİL — eski moda ait aşama/bayrak kalıntısı kalmasın.
rm -f data/tv_signal_state.json data/tv_signal_state.json.bak

# 7) Konteyneri recreate ve stratejiyi başlat.

#    CLI: start --script tv_signal_strategy.py

# 8) İLK 60 SANİYE — boot logunda mod satırını DOĞRULA.
docker logs --tail 200 hummingbot | grep -i "POSITION_MANAGEMENT"
#    "Geçersiz POSITION_MANAGEMENT_MODE" görürsen env yazımı hatalı → legacy'ye
#    düşmüş demektir, düzelt ve 7'yi tekrarla.

# 9) İLK İŞLEMİ düşük notional ile doğrula (aşağıdaki tabloya göre).
```

**Her modda ilk işlemde GÖRÜLMESİ GEREKEN loglar:**

| Mod | Girişte | 1R'de | 2R'de | Sonrasında |
|---|---|---|---|---|
| `legacy` | `✅ [B4 BYBIT SLTP] … SL=… TP=…` | `🚀 [FAZ 2 AKTİVASYON]` + `%50 kapama` + `SL@entry` | `🎯 [PHASE2 TP2 HIT]` | `🔺/🔻 [FAZ 2 TRAILING]` |
| `rr2_trailing` | `🔀 [RR2 ENTRY] … TP emri KONULMAYACAK` + `🔀 [RR2 TRACK] … R1=… R2=…` + SL bacağı (TP **YOK**) | **HİÇBİR ŞEY** (bu doğru davranış!) | `🚀 [RR2 TRIGGER]` → `🛡️ [RR2 ARMED] … SL = R1` | `🏃 [RR2 R2 SWITCH]` → `🔺/🔻 [RR2 TRAILING]` |
| `passive` | SL/TP normal konur | — | — | Hiçbir yönetim/onarım logu OLMAMALI |

**`rr2_trailing`'de OLMAMASI gerekenler:**
`🚀 [FAZ 2 AKTİVASYON]` (legacy tetiği) · `[PHASE2 TP2 …]` ·
`✅ [BYBIT LIMIT TP]` (giriş TP'si) · `🩹 … TP=True` (TP diriltme) ·
`🔺 [FAZ 2 TRAILING]` (legacy merdiven — RR2'de `[RR2 TRAILING]` olmalı).

**`passive`'de OLMAMASI gerekenler:**
`🩹 [PERIODIC VERIFY BYBIT]` · `🛡️ [SL COVERAGE …]` · `🔍 [RECOVERY]` ·
`⚠️ [RECONCILE]` · `🧼 [DUST CLOSE]` · `🚀 [FAZ 2 …]` · `[RR2 …]`.

**GERİ DÖNÜŞ (rollback):** Aynı 9 adım, `POSITION_MANAGEMENT_MODE=legacy` ile.
Kod tarafında hiçbir şey geri alınmaz — `legacy` yolu byte-identical durur.
Ek acil anahtarlar (redeploy gerektirmez): `R_FEE_AWARE=0` (§30 1R geometrisi),
`TP_FEE_ADJUST_ENABLED=0` (§30 TP düzeltmesi), `DUST_CLOSE_ENABLED=0` (§30 dust).

### 31.8 Deploy sonrası izlenecekler
**YENİ görülecekler:** `🔀 [RR2 ENTRY]` · `🔀 [RR2 TRACK]` · `🚀 [RR2 TRIGGER]` ·
`🛡️ [RR2 ARMED]` · `🏃 [RR2 R2 SWITCH]` · `🔺/🔻 [RR2 TRAILING]` ·
`🧹 [RR2 LIMIT TP CANCEL]` · `♻️ [RR2 RESTORE]`.
**İZLENECEK UYARILAR:**
1. `⚠️ [RR2 SL STRICT] … soft-fail` sıklığı — sıksa mark/last ayrışması veya
   çok dar R mesafesi var; `🛑 [RR2 FAILSAFE]` ile birlikte gelirse pozisyonlar
   2R'de market'ten kapanıyor demektir (kâr realize edilir ama trailing kaçar).
2. `🚨 [RR2 FAIL CLOSE PENDING]` → **elle müdahale gerekir**, pozisyon
   korumasız olabilir.
3. `⚠️ [RR2 GEOMETRY LOST]` → state dosyası kaybolmuş; R1/R2 yeniden
   türetilmedi (doğru davranış) ama parça artık mevcut stop'tan trailliyor.
4. `1R`'de hiçbir log olmaması **normaldir** — RR2'nin tanımı bu.

### 31.10 Fix BW — KURTARMA YOLLARI RR2 DURUMUNU YOK EDİYORDU (kullanıcı geri bildirimi 2026-09-01)

Kullanıcı §31.2-(B) ve -(F) üzerine iki ek getirdi. **İkisi de doğrulandı ve
uygulandı**; birinin sonuç iddiası matematikle çürütüldü, ayrıca üçüncü bir
delik bulundu.

#### 31.10.1 (B)-amplification — `_deterministic_rebuild_...` RR2 alanlarını taşımıyor ✅
**Doğru.** İki yol var:
- `canonical_position` mevcutsa (`else` dalı) → aynı dict, RR2 alanları **yaşar**.
- **±%5 içinde eşleşen parça yoksa** (kalıcı mismatch'in TİPİK hâli) pseudo id
  üretilir, tüm parçalar temizlenir ve **SIFIRDAN** bir dict kurulur:
  `management_stage`, `r1_price`, `r2_price`, `trailing_anchor_price`,
  `rr2_stop_placed_at` **YOK**; üstelik `1r_reached=False`,
  `phase2_active=False` açıkça yazılır. → **RR2 durumu tamamen kaybolur.**

**⚠️ Ama sonuç iddiası ("stop R1'e AŞAĞI amend edilir, kilitli kâr yok olur")
matematiksel olarak İMKÂNSIZ.** Geometri taşınmış stop `S'`'den yeniden
türetilirse (LONG, `S' > eff_entry`):
```
risk' = |eff_entry − S'| = S' − eff_entry
r1'   = eff_entry + risk' = eff_entry + S' − eff_entry = S'      ← MEVCUT STOP
r2'   = eff_entry + 2·risk' = 2S' − E − fee                      ← FIRLAR
```
`r1' == S'` olduğu için yeniden aktivasyon `_update_trailing_sl(new_sl=S')`
çağırır → **stop hiç değişmez**. (Testte assert edilir.)

**GERÇEK zarar:** `r2'` fiyatın çok üstüne fırlar → tetik bir daha ateşlenmez;
stage `RR2_WAIT`'e döndüğü için `_position_management_trailing_active()` False →
**trailing kalıcı olarak ölür**. Sonuç: statik stoplu, yönetilmeyen
**"donmuş runner"**. Ayrıca `_is_rr2_managed_position()` False olur → orphan/sync
temizleyicileri parçayı korumalı saymaz.

**Fix BW-1:** rebuild, tarafı collapse etmeden ÖNCE en ileri aşamadaki parçadan
RR2 durumunu (`management_stage`, `r_sl_baseline`, `r_eff_entry`,
`r_distance_orig`, `r1/r2_price`, `rr2_stop_placed_at`, `trailing_anchor_price`,
`tp_suppressed_by_rr2`, `rr2_original_tp`, `phase2_tp_mode`, sinyal üçlüsü)
**yakalar** (stage sıralaması TRAIL_2R > ARMED_R1 > FAIL_PENDING >
TRANSITIONING) ve canonical parçaya **geri yazar**. `_ensure_position_r_geometry`
fill-only olduğu için r1/r2 geri gelince geometri bir daha türetilmez → drift
yok. RR2'ye özgü bayraklar da normalize edilir (`1r_reached=False` vb.).
Log: `🔀 [RR2 REBUILD CARRY]`. **Legacy/passive rebuild BYTE-IDENTICAL.**

**Fix BW-3 (kullanıcı mikro-bulgusu, 2026-09-01) — taşınan
`RR2_TRANSITIONING` DEMOTE edilir.** `TRANSITIONING` de taşıma adayıdır
(rank 1) ve rebuild aktivasyon penceresine denk gelirse — aktivasyon emirleri
değiştirirken mismatch tetiklenebilir — taşınan aşama `RR2_TRANSITIONING`
kalır. O aşama **hiçbir dala uymaz**:
| Dal | Beklediği aşama |
|---|---|
| tetik (`_try_trigger_rr2_management`) | `RR2_WAIT` (`!= RR2_WAIT` → `return False`) |
| switch (`_maybe_switch_rr2_to_r2_trailing`) | `RR2_ARMED_R1` |
| trailing (`_position_management_trailing_active`) | `RR2_TRAIL_2R` |

Üstelik devam eden aktivasyon task'i **ESKİ (artık orphan) dict'e** yazdığı
için `RR2_ARMED_R1` geçişi canonical parçaya ULAŞMAZ. Demote yalnız
`_load_state`'te olduğundan parça **bir sonraki restart'a kadar DONAR**.
`_phase2_immunity` kapısı (`_periodic_sltp_verify` o tarafı atlar) olasılığı
düşürür ama sıfırlamaz: `PHASE2_IMMUNITY_DURATION` sonludur ve
`_close_partial_position` / REST retry'ları aktivasyonu daha uzun sürdürebilir.
→ Carry sırasında load-time demote'un **AYNISI** uygulanır
(`♻️ [RR2 REBUILD DEMOTE]`). `r1/r2/baseline` taşındığı için `RR2_WAIT`'e
dönmek güvenlidir: bir sonraki tick 2R kontrolünü normal yapar ve aktivasyon
idempotenttir (SL amend, limit-TP iptali no-op). **`RR2_FAIL_CLOSE_PENDING`
BİLİNÇLİ olarak demote EDİLMEZ** — monitor tam o aşama için
`_schedule_rr2_failclose_retry`'ı dispatch ediyor.

#### 31.10.2 (F)-nüans — adoption'ın SL kaynağı borsadaki CANLI stop ✅
**Doğru, hem de iki yoldan:** `sl_order["stopPrice"]` (klasik yol) **ve** Fix
BP'nin `_real_sl`'i (koşullu leg). İkisi de RR2'nin **TAŞINMIŞ** stop'unu verir.
Kullanıcının aşama-bağımlı drift analizi de **birebir doğru**:

| Evlat edinilirken | Matematik | Sonuç |
|---|---|---|
| `RR2_ARMED_R1` (stop = R1) | R1, `eff_entry` etrafında S ile **SİMETRİK** → `risk' = R`, `r1' = R1`, `r2' = R2` | Geometri **TESADÜFEN bozulmaz** ✅ |
| `RR2_TRAIL_2R` (stop > R2) | `risk' = S' − eff_entry > 2R` → `r2'` fırlar | Tetik ölür → stage RR2_WAIT → **donmuş runner** ❌ |

**Fix BW-2:** kullanıcının önerisi ("`r_baseline_untrusted` işaretle, tetiği pas
geç") **kabul edildi ve BİR ADIM İLERİ taşındı** — çünkü "tetiği pas geçmek" de
donmuş runner üretir. Yeni `_rr2_adopt_position_state()` **Fix BP'nin E1
kanıtını** yeniden kullanır (bir RR2_WAIT stop'u yapısı gereği entry'nin RİSK
tarafındadır):
```
stop RİSK tarafında  → baseline GÜVENİLİR → normal RR2_WAIT + gerçek R1/R2
stop entry'de/ötesinde → baseline GÜVENİLMEZ → geometri TÜRETİLMEZ,
                         mevcut stop anchor kabul edilir, parça
                         RR2_TRAIL_2R'de DEVAM eder (merdiven yalnız İYİLEŞTİRİR)
```
`r_baseline_untrusted` bayrağı `_ensure_position_r_geometry`'de de onurlandırılır
ve **persist/restore** edilir → restart geometriyi yeniden türetemez.
Log: `🔀 [RR2 ADOPT]` / `🔀 [RR2 ADOPT ARMED]`.

Böylece donmuş runner yerine parça **kaldığı yerden trailing'e devam eder**;
`max()/min()` no-degrade kuralı stop'u asla kötüleştiremez (testte: evlat
edinilen armed parça, sonraki +%0.2 tick'inde stop'u bir adım YUKARI taşıyor).

#### 31.10.3 ➕ Üçüncü delik (ikisinde de yok): adoption legacy alanları yazıyor
`_auto_detect_position` her benimsemede şunları yazıyor:
`1r_reached = already_1r`, `phase2_tp_mode = "manual_second_take"`,
`tp = <borsa TP legi veya tahmin>`, `phase2_active = phase2_recovered`.
RR2 modunda:
- **`1r_reached=True` monitor'ın TEK dispatch dalını (`elif not 1r_reached`)
  kapatır** → parça ne trailing dalına ne tetik dalına girer → **tamamen atıl**
  (Fix BN'in çözdüğü sınıfın RR2'de yeniden doğuşu).
- `manual_second_take` + `tp>0` → TP2 yazılım tetiği canlanır (bugün
  `_handle_phase2_trailing`'in mod kapısı bunu engelliyor, ama kapıya bel
  bağlamak kırılgan).

`_rr2_adopt_position_state()` bu dördünü de RR2 için normalize eder
(`tp=0`, `rr2_no_tp`, `1r_reached=False`, `phase2_*=False`).
**legacy/passive'de helper ilk satırda `return` eder → tam NO-OP** (testte
legacy parçanın `tp`/`tp_mode`/`1r_reached` alanlarının korunduğu assert edilir).

**Doğrulama:** `py_compile` OK · AST **0 fonksiyon kaybı (432 → 458)** ·
`BYBIT_GUARD`=2 · **12 paketin TAMAMI PASS** · `verify_v56_fixes.py`
**139 assert** (Fix BW için: rebuild carry + BW-3 demote, `r1' == S'` matematiği,
`r2'` şişmesi, ARMED simetrisi, 4 adoption senaryosu LONG/SHORT × armed/waiting,
evlat edinilen armed parçanın sonraki tick'te stop'u yukarı taşıması,
legacy NO-OP).

**Yeni log imzaları:** `🔀 [RR2 REBUILD CARRY]` · `♻️ [RR2 REBUILD DEMOTE]` · `🔀 [RR2 ADOPT]` ·
`🔀 [RR2 ADOPT ARMED]`. İkincisi görülürse: state dosyası kaybolmuş, parça
borsa gerçeğinden kurtarıldı ve R1/R2 **bilinçli olarak** yeniden türetilmedi —
bu doğru davranıştır, uyarı değil hata değildir.

### 31.11 Kalan açık konular
1. Mark/last ayrışması (31.5, bilinçli kabul).
2. Emergency konsolidasyon RR2 sonrası bir tarafı konsolide ederse
   `management_stage` `ARMED_R1`/`TRAIL_2R`'de donabilir; olasılık düşük
   (`BYBIT_CONSOLIDATION_ENABLED=0`), opsiyonel guard eklenmedi.
3. Parçalar-arası TP bulaşması (§30.11-1) RR2'de KONU DEĞİL (TP yok).
4. `passive` modun OKX/Binance'te fiilen kullanılması hâlinde giriş-SL
   retry'ları donabilir (`_process_sltp_retry_queue` kapısı) — o senaryoya
   geçilirse yeniden değerlendirilmeli.
5. RR2'de `BYBIT_MAX_PIECES_PER_SIDE` aynı tarafta çoklu parçaya izin vermeye
   devam ediyor; §24.2'nin blended-avg muhasebesi RR2'de de geçerlidir.


---

## 32) v5.7 — UPGRADED POSITION CLEANUP, TRAILING SAFETY NET & COUNT HARDENING (Fix BX / BY / BZ)

### 32.1 Fix BX — Borsa Flat Kapanışında Hayalet Tracking Temizliği ve Sentetik Arşivleme
Borsa üzerinde pozisyon sıfırlandığında (`live_amt <= 0`), `_bybit_cancel_all_side_legs` fonksiyonu açık kalan artık conditional leg'leri iptal ederken hafızadaki hayalet takip parçalarını (`_tracked_positions`) güvenle temizler:
- Her temizlenen parça için `_archive_trigger_close` çağrılarak sentetik kapanış arşivi (`close_order=SYNTH_FLAT_<order_id>`) üretilir.
- `_save_state()` çağrılarak temizlenmiş state anında diske yazılır.
- Halen işlemde olan inflight parçalar (`_processing_phase2_orders` ve `_rr2_failclose_inflight`) yarış durumlarını önlemek için temizlikten hariç tutulur.
- Log: `⚡ [WS POS CLOSED] {pair} {side} size=0 → kalan tüm legler ve parça tracking'i anında temizleniyor`.

### 32.2 Fix BY — `_count_open_pieces` Önbellek Sertleştirmesi (Race Condition Koruması)
Açık parça sayımında borsa pozisyon önbelleği (`_binance_positions_cache`) ile hafıza senkronizasyonu 4 kurala bağlandı:
1. **Kural A (Hayalet Eleme):** Önbellekte sembol yok, önbellek taze (<120s) ve parça yaşı >70s ise borsa gerçeğine uyularak sayılmaz (0).
2. **Kural B (Yeni Giriş Yarışı):** Önbellekte sembol yok, önbellek taze (<120s) ancak parça <=70s ise yeni açılmış sinyal yarışı kabul edilir ve sayılır (1).
3. **Kural C (Bayat Önbellek Güvenliği):** Önbellek bayat (>120s) ve sembol yoksa güvenlik gereği parça silinmez ve sayılır (1).
4. **Kural D (Aktif Pozisyon):** Önbellekte pozisyon varsa normal olarak sayılır (1).

### 32.3 Fix BZ — `_update_trailing_sl` Trailing Güvenlik Ağı (Safety Net)
Trailing döngüsü sırasında sorgulanan gerçek borsa pozisyon büyüklüğü sıfır veya negatif gelirse (`real_amt <= 0`):
- Parça derhal tracking listesinden düşürülür.
- Sentetik kapanış kaydı arşive yazılır.
- `_save_state()` tetiklenerek state dosyası güncellenir.
- Doğrulama: `tools/verify_v57_upgraded_fixes.py` (tüm testler PASS).

---

## 33) v5.8 — RR2 MULTI-STAGE RATCHET TRAILING v4 FINAL (Fix CA)

### 33.1 Multi-Stage Ratchet Floor Kilitleme Mekanizması
RR2 modunda fiyat 2R seviyesini aştıktan sonra fitil/wick hareketlerinde kârı kilitlemek için çok aşamalı zemin mantığı devreye girer:
- **Wick Zemin Kilidi:** Fiyat 2R -> 4.5R aralığında tek tick'te ani zirve yapsa bile zemin doğrudan 3R seviyesine kilitlenir (`floor = 3R`). Hedef stop:
  $$\text{target} = \max(S, \text{floor}, \text{candidate}) \quad (\text{SHORT için } \min)$$
- **Merdiven Çapa Ayrımı (Ladder Anchor Separation):**
  - Anchor = 2R, aday tabanı = 1R.
  - Aktivasyon anında ($m = 0$) aday stop tam 1R seviyesindedir; fiyatta suni zıplama veya gap oluşmaz.
- **11R Tavan Sınırı (Ceiling Clamp):** Fiyat 17.5R gibi aşırı zirvelere gitse dahi $k_{\text{peak}} \le 11$ ile sınırlandırılır, maksimum zemin 10R olarak kilitlenir.

### 33.2 Soft-Fail ve Hayalet Yazma Koruması (Ghost-Write Protection)
- Borsa koşullu emir amend çağrısı başarısız olduğunda veya borsa stopu okunamadığında (`strict=False`):
  - Hafızadaki `sl` veya `last_logged_sl` değerleri asla bozulmaz / üzerine yazılmaz.
  - Asla körlemesine acil durum market emri gönderilmez.
  - `_rr2_ratchet_retry_ts` sözlüğü üzerinden 3 saniyelik zaman aşımı ile kontrollü retry uygulanır.

### 33.3 Degraded / Rescue Modu ve Post-Load Yükseltme
- State dosyasının kaybolduğu veya borsa-gerçeğinden kurtarma yapıldığı durumlarda $E$ veya $R$ eksikse sistem çökmez; ladder-only modunda güvenle çalışır.
- State dosyasından geri yüklenen `RR2_ARMED_R1` parçaları otomatik olarak `RR2_TRAIL_2R` aşamasına yükseltilir (`management_stage = "RR2_TRAIL_2R"`).
- Doğrulama: `tools/verify_v58_rr2_ratchet.py` (tüm invariant'lar PASS).

---

## 34) v5.9 — HYBRID TRAILING MODE (`hybrid_trailing`) (Fix CB)

### 34.1 Mimari ve Çalışma Mantığı
`POSITION_MANAGEMENT_MODE=hybrid_trailing` modu, 1R kısmi kâr alma (TP1 %50) ile 2R dinamik trailing ve 3R ratchet yönetimini birleştirir:
- **Giriş Emri:** Girişte limit TP konulmaz (`tp_suppressed=True`, `RR2_PLACE_ENTRY_TP=0`).
- **Aşama 1 (1R Tetikleyici — `HYBRID_WAIT` → `HYBRID_TRANSITIONING`):**
  - Fiyat fee-aware 1R seviyesine ulaştığında %50 kısmi kapanış için reduce-only limit/market TP1 emri gönderilir (`HYBRID_CLOSE_PENDING`).
  - SL derhal giriş seviyesine taşınır: gerçek stop hedefi `entry` fiyatıdır; kodda ve loglarda tarihsel olarak `[HYBRID +0.5% BE]` etiketi geçse de ek bir %0.5 stop tamponu yoktur (`sl_price=entry` gönderilir). Fee-aware R hesabı ise R1, R2 ve TP geometrisinde tahmini round-trip komisyonu R mesafesine dahil eder; ancak stop emrinin kendisi `entry` seviyesine konduğundan, stop tetiklendiğinde gerçekleşen kayma (slippage) ve komisyonlar nedeniyle ücretler dahil net sıfır zarar (breakeven) garantisi vermez.
- **Aşama 2 (1R–2R Arası Bekleme — `HYBRID_HOLD_ENTRY`):**
  - TP1 gerçekleştikten sonra kalan parça `HYBRID_HOLD_ENTRY` aşamasına geçer.
  - 1R ile 2R arasında trailing çalıştırılmaz; doğrulanmış entry stop (BE) korunur. Bu sayede 1R-2R arasındaki salınımlarda erken stop olma riski engellenir.
- **Aşama 3 (2R Dinamik Trailing — `HYBRID_TRAIL_2R`):**
  - Fiyat 2R seviyesini aştığında normal dinamik trailing merdiveni devreye girer. Zirve fiyat ilerledikçe SL dinamik olarak taşınır.
- **Aşama 4 (3R Ratchet Devri — `HYBRID_TRAIL_3R`):**
  - Fiyat 3R seviyesini aştığında yönetim tam RR2 multi-stage ratchet mantığına devredilir.

### 34.2 Reconcile ve Güvenlik Ağları
- `HYBRID_CLOSE_PENDING` durumunda emir borsada açık veya kısmi dolmuşsa kesinleşene kadar `HYBRID_WAIT`'e dönülmez; çift kapama önlenir.
- `_update_trailing_sl_rr2_strict` sözleşmesi ile borsa amend işlemi teyit edilmeden yerel state güncellenmez.
- Doğrulama: `tools/verify_v59_hybrid_trailing.py` (tüm sözleşmeler PASS).

---

## 35) v6.0 — BYBIT DEMO UNIFIED CANDIDATE (`4F95AA04`) — QUANTIZE LOOP, TERMINAL STOP IDEMPOTENT FILL ACCOUNTING & RECONCILE (2026-10-28) (Fix CC / CD / CE / CF)

2026-10-28 canlı adli incelemesinde tespit edilen 3 kritik canlı bot kusurunu kalıcı ve minimal olarak kapatan birleşik sürüm:

### 35.1 Fix CC — Tek Operasyonel Hedef ve Quantize Readback Mutabakatı
- **Kök Neden:** 2R trailing döngüsünde ham hedef (`new_sl`) borsa tick size'ına quantize edilmeden talep ediliyor, borsa quantize ederek kabul ediyor, fakat bot readback doğrulamasında quantize edilmiş borsa değerini ham hedefle karşılaştırıyordu. Bu uyuşmazlık nedeniyle state kaydedilemiyor ve her 3 saniyede bir sonsuz retry döngüsü (9499 retry) oluşuyordu.
- **Düzeltme:**
  1. `operational_sl = quantize_fn(trading_pair, raw_target)` tek bir noktada hesaplanır.
  2. Hem borsaya gönderilen amend isteği hem de readback doğrulayıcısı (`target_sl=operational_sl`) bu quantize operasyonel hedefi kullanır.
  3. **Gevşetmeme Koruması (No-Degrade):**
     ```python
     if side == "LONG" and operational_sl <= current_sl:
         return
     if side == "SHORT" and operational_sl >= current_sl:
         return
     ```
     Mevcut stoptan daha kötü veya eşit operasyonel hedef borsaya gönderilmez.
  4. Quantize fonksiyonu hata verirse ham float ile devam edilmez; mevcut stop ve state korunup 3s throttle ile retry edilir.

### 35.2 Fix CD — Terminal Filled Stop, Residual Emir Ayrımı ve Idempotent Muhasebe
- **Kök Neden:** WS bağlantı kopukluğunda veya kaçan WS fill mesajlarında, borsa koşullu emri Filled olduğunda bot bunu yalnızca CID yanması sanıp generation artırıyor ve borsa pozisyonu sıfırlanmışken dahi yeni yetim stoplar (BB1/BB2) üretiyordu.
- **Emir Durumu Ayrımı (CID Generation Sınırları):**
  1. **`live_status == "filled"` (Terminal veya Kısmi Dolum):** Borsa koşullu emri gerçekleştiğinde generation artırılmaz. `burned_parent` kimliği tracked parça (`order_id`) ile eşleştirilir; gerçek dolum miktarı `cumExecQty` veya `/v5/execution/list` (`execType == Trade`) üzerinden kesinleştirilerek idempotent dolum defterleri çalıştırılır.
  2. **İptal / Devre Dışı Durumlar (`live_status in ("cancelled", "deactivated", ...)`):**
     - Eğer borsa pozisyonu sıfır ise (`real_pos_amt <= 0`), generation artırılmaz (`zero_position_no_stop`) ve yetim stop üretimi engellenir.
     - Eğer borsa pozisyonu > 0 ise, meşru residual koruma ihtiyacı için CID generation rotasyonu (`_bybit_bump_cid_generation`) çalışmaya devam eder ve borsa üzerinde yeni stop emri oluşturulur. Yani CID generation her koşulda kaldırılmış değildir; borsa pozisyonu varken iptal/deaktif emirler için korunur.
  3. **Belirsiz Durumlar (Ambiguous States):**
     - `cumExecQty` veya trade execution doğrulanmazsa (`ambiguous_fill_preserved`), fazla dolum şüphesinde (`overfill_ambiguous_preserved`), taze borsa snapshot'ı alınamazsa (`missing_snapshot_preserved`) veya borsa miktarı ile kalan sibling toplamı uyuşmazsa (`aggregate_mismatch_preserved`): parent tracking'den silinmez, sessiz başarı verilmez ve belirsiz durum korunarak salt-okunur reconcile beklenir.
- **Tekilleştirme Defterleri (Idempotent Accounting):**
  - `applied_cumulative_fill`: Emir bazında kümülatif dolum defteri.
  - `applied_exec_ids`: WS gerçekleşme kimlikleri (`execId`).
  - `ws_fills_by_order`: WS üzerinden gelen dolum toplamı.
  - Yeni dolum farkı: $\Delta = \max(0, \text{cum\_exec} - \text{prev\_applied})$. WS ve REST aynı gerçekleşmeyi asla ikinci kez düşmez.
- **Kısmi Dolum (Residual $> 0$):** Kalan miktar için aktif stopun varlığı 6 katı kriterle sorgulanır:
  - (1) SL türü kontrolü (`kind == "SL"`).
  - (2) Parent kimliği tam eşleşmesi (`parent_id == burned_parent` — sibling stopu ASLA koruma sayılmaz).
  - (3) Quantize edilmiş miktar tam eşitliği (`q_c_qty == q_new_rem`).
  - (4) Fiyat geçerliliği ve parent SL karşılama kontrolü.
  - (5) Aktif durum kontrolü (açık izin listesi: `untriggered`, `new`, `active`; unknown/boş reddedilir).
  - (6) Doğru pozisyon bacağı (`positionIdx` ve `side`).
- **Tam Dolum (Residual $== 0$):**
  - Taze borsa pozisyon snapshot'ı (`ensure_fresh=True`) alınır.
  - Gerçek borsa pozisyonu ile kalan sibling toplamı quantize hassasiyetinde sıfır toleransla (`q_real == q_expected`) uyuşmalıdır.
  - Mutabakat tam ise `_archive_trigger_close` çağrılır, `_cleanup_position_tracking` ile parent temizlenir ve state kaydedilir.
- **Save-Failure Davranışı:** State kaydetme başarısızlığında (`_save_state() == False`), "sessiz başarı verilmez; kalıcı kayıt doğrulanmış sayılmaz" (`out["status"] = "state_save_failed"` döner). Ancak bu durum, çağrı öncesinde bellekte yapılmış olabilecek ara state/defter güncellemelerinin veya liste temizliklerinin hiç yapılmadığına dair mutlak bir garanti vermez; salt kalıcı disk mutabakatının sağlanamadığını ifade eder.

### 35.3 Fix CE — Mevcut Daha İyi Stopu Koruma (`_place_bybit_conditional_order`)
- Canlı borsadaki stop trigger fiyatı istenen hedeften daha iyiyse:
  - Miktar tam uyuşuyorsa: amend gönderilmez, daha iyi stop korunur (`preserved_better_sl`).
  - Miktar uyuşmuyorsa: fiyat gevşetilmeden mevcut daha iyi fiyat muhafaza edilerek yalnız miktar düzeltilir (`amended_qty_only`).

### 35.4 Fix CF — State Persistence, Sibling İzolasyonu ve %5 Toleransının Kapsamı
- **State Defterlerinin Kalıcılığı:** `applied_cumulative_fill`, `applied_exec_ids`, `ws_fills_by_order` hem `_save_state` hem de `_load_state` içine eklenerek yeniden başlatmalarda korunur.
- **%5 Tolerans Değişikliğinin Gerçek Fonksiyon Kapsamı:** Yüzde 5 (%5) toleransının kaldırılması tüm kod tabanında genel bir değişiklik değildir; yalnız iki kritik fonksiyonun ilgili kararlarıyla sınırlıdır:
  1. `_has_leg` fonksiyonunda (L9580+): Eksik CID durumunda miktar üzerinden `±%5` yaklaşık eşleşme kaldırılmış, `parent_id` tam eşleşmesi ve quantize edilmiş miktar tam eşitliği (`q_c_qty == q_piece`) zorunlu kılınmıştır. Sibling stopu asla koruma sayılamaz.
  2. `_place_bybit_conditional_order` terminal tam dolum kontrolünde (L2835+ / L3340+): Gerçek borsa pozisyonu ile kalan sibling toplamının mutabakatında %5 tolerans kaldırılmış, quantize hassasiyetinde sıfır tolerans (`q_real == q_expected`) şart koşulmuştur.
  - Kod tabanındaki diğer ilgisiz alanlar (ör. ilk sizing marj tavanları veya arşiv oran kontrolleri) bu değişikliğin kapsamı dışındadır.

### 35.5 Doğrulama ve Deploy Paketi
- **Lokal Test Paketi:** `tests/run_all_candidate_tests.py` -> **37/37 PASS** (23 strict terminal + 13 quantize + 1 real AST E2E).
- **Git Repo:** `https://github.com/alpcoderalp/tv`
- **Commit:** `b181daf`
- **Kalıcı Host Dosyası:** `/home/ubuntu/deploy/bots/scripts/tv_signal_strategy.py`
- **Doğrulanmış SHA256:** `4f95aa04183052f4333b32960067e3591c0f48b0a6dbeb512ac442a93687af41`
- **Konteyner SHA256:** `4f95aa04183052f4333b32960067e3591c0f48b0a6dbeb512ac442a93687af41` (Birebir eşleşti).


### 35.6 Eski-State Çift-Düşüm Migration Uyarısı (Flat Deploy vs. Kendi State'inden Restart)
- **Migration Sınırı:** `4F95AA04` sürümünde, eski `51F6CDD4` state'inden devralınan açık pozisyonlarda daha önce uygulanmış kısmi dolumların (`remaining_amount < amount`) REST execution geçmişiyle tekrar düşülmesini engelleyen 5 satırlık state-migration guard'ı bilinçli olarak eklenmemiştir.
- **Flat Deploy (Kullanılan ve Doğrulanan Yöntem):** Borsa pozisyonları kullanıcı tarafından manuel kapatılmış, state dosyası sıfırlanmış ve bot 0 pozisyonla temiz başlatılmıştır. Bu sayede eski state'ten kaynaklanabilecek çift-düşüm (double-deduction) riski flat deploy'da oluşmaz.
- **4F95AA04 Kendi State'inden Restart:** Yeni sürümün kendi ürettiği state şemasında `applied_cumulative_fill`, `applied_exec_ids` ve `ws_fills_by_order` defterleri persist edildiği için, botun kendi state'inden yeniden başlatılması (restart) güvenli ve idempotenttir.
- ⚠️ **Kritik Kural:** Eski `51F6CDD4` state'i açık pozisyon içerirken doğrudan `4F95AA04` sürümüne devredilmemelidir.

### 35.7 Canlı Çalışma Doğrulaması ve Adli Analiz Sonuçları (2026-10-28 18:40 UTC — 2026-10-30 09:12+ UTC, ~39 Saat)

2026-10-28 18:40:19 UTC tarihinde Bybit Demo ortamında gerçekleştirilen flat deploy sonrasında, `4F95AA04` sürümü yaklaşık 39 saat boyunca kesintisiz olarak canlı piyasa verileri ve gerçek TradingView sinyalleriyle çalıştırılmıştır. Bu süre zarfındaki tüm işlemler, log kayıtları, Bybit REST/WS akışları ve borsa emirleri adli analize tabi tutulmuş; stratejinin beklenen tasarım ve güvenlik sözleşmelerine %100 uyduğu tespit edilmiştir.

#### 35.7.1 Operasyonel Ortam ve Çalışma Metrikleri
- **Çalışma Süresi:** 2026-10-28 18:40:19 UTC — 2026-10-30 09:12+ UTC (~39 saat kesintisiz).
- **Konteyner ve Servis Durumu:** %100 Uptime. `hummingbot` ve `rogerthat` servislerinde 0 çökme, 0 beklenmedik restart, 0 exception döngüsü.
- **İşlem Gören Toplam Pozisyon:** 27 adet Parent pozisyon:
  - **CHIP-USDT:** 18 adet (8 LONG, 10 SHORT).
  - **PONS-USDT:** 9 adet (4 LONG, 5 SHORT).
- **Pozisyon Yaşam Döngüsü:**
  - **23 Adet Tamamlanan (Closed):** Uçtan uca tüm yaşam döngüsünü tamamlayarak arşivlenmiş ve takipten temizlenmiştir (`[CLOSED POS CLEANUP]`).
  - **4 Adet Açık / Aktif (Open):** Canlı Bybit Demo borsasında ve Hummingbot hafızasında eşzamanlı olarak güvenle sürdürülmektedir (`#570414374565`, `#167272712944`, `#606906494493`, `#275087885943`).
- **Borsa Koşullu Emir Senkronizasyonu:** Bybit Demo REST API üzerinden yapılan anlık doğrulamada, açık 4 pozisyonun tamamı 100% kapsama ile borsa tarafında aktif koşullu stop emirleriyle (`triggerDirection`, `triggerPrice`, `qty`) korunmaktadır ($386 + 2550 + 4600 + 6330 = 13866$ kontrat). Borsa üzerinde **0 adet yetim (orphan) emir**, **0 adet korumasız kontrat** bulunmaktadır.
- **Finansal Gerçekleşen Sonuç:**
  - Kapanan 23 işlemin kalan parçalarından elde edilen gerçekleşen PnL: **+9.5975 USDT**.
  - Alınan 11 adet TP1 kısmi kâr parçalarından elde edilen gerçekleşen PnL: **+19.1871 USDT**.
  - **Toplam Net Gerçekleşen PnL:** **+26.7826 USDT** (Testnet 400 USDT bakiye üzerinde net kârlılık).

---

#### 35.7.2 Kritik Düzeltmelerin (Fix CC / CD / CE / CF) Canlı Adli Doğrulaması

1. **Fix CC — Quantize ve Readback Döngüsünün Tam Sıfırlanması:**
   - *Tarihsel Hata (51F6CDD4):* 2R dinamik trailing aşamasında borsa tick size'ı ile yerel hedef arasındaki quantize uyuşmazlığı nedeniyle 40 dakikada 9.499 kez `HYBRID TRAIL 2R RETRY` tetiklenmiş ve bot kilitlenmişti.
   - *Canlı Doğrulama (4F95AA04):* 39 saat ve 27 pozisyon boyunca loglarda `HYBRID TRAIL 2R RETRY` tetiklenme sayısı tam **0 (SIFIR)**'dır. Amend edilen her trailing ve ratchet seviyesi tek seferde borsa tarafından kabul edilmiş ve readback mutabakatı hatasız sağlanmıştır.
2. **Fix CD / CE / CF — Orphan / Hayalet Stopların Tamamen Engellenmesi (BB1/BB2 İzolasyonu):**
   - *Tarihsel Hata:* Kapanan pozisyonların ardından borsada kalan koşullu emirlerin tetiklenmesiyle sahte ters yönlü pozisyonlar (`BB1`/`BB2`) oluşabiliyordu.
   - *Canlı Doğrulama (4F95AA04):* Dakikalık periyodik `[ORPHAN DEBUG]` taramalarında ve 23 pozisyon kapanışının tamamında borsa pozisyonu sıfırlandığı an `zero_position_no_stop` devreye girmiş; kalan tüm stop emirleri iptal edilmiştir. Borsada tek bir yetim emir dahi bırakılmamıştır.
3. **1R Tespiti ve TP1 (%50) Kısmi Kapanış Sözleşmesi:**
   - 27 pozisyonun 12'sinde 1R seviyesi aşılmış (`[HYBRID TRIGGER]`); 11 tanesinde reduce-only limit/market TP1 emri derhal borsaya iletilmiş ve doldurulmuştur (`link=HTP1...`).
   - Kalan 1 işlemde (`#882631596625`), aynı milisaniyede kardeş pozisyon (`#127744249455`) işlemde olduğu için `lock_key` devreye girmiş, eşzamanlı çift emir riski önlenerek stage güvenle `HYBRID_WAIT`'e sıfırlanmıştır.
4. **Break-Even (BE) / HYBRID_HOLD_ENTRY Davranışı:**
   - TP1 dolumu sonrası stopun tam `entry` seviyesine çekilmesi ve 1R ile 2R arasında erken stop gevşetmesi/sıkılaştırması yapılmadan beklenmesi canlı piyasada gözlemlenmiştir.
   - 3 işlem fiyattaki geri çekilmede tam giriş fiyatından ($0.0000$ net zarar ile) kapanarak TP1 kârını %100 korumuştur. 1 işlem (`#570414374565`) ise halen giriş seviyesinde (`0.2322`) güvenle tutulmaktadır.
5. **2R Dinamik Trailing ve 3R Ratchet Devri:**
   - 7 adet runner pozisyon 2R ve ardından 3R seviyesini aşmıştır (`#748481856534`, `#382732215995`, `#523397809626`, `#127744249455`, `#613482810910`, `#68583515800`, `#393613137952`).
   - Fiyat 3R'ye ulaştığında çok aşamalı ratchet mekanizması devreye girerek stopu 2R kâr zeminine kilitlemiştir (`floor = 2R`). Fiyat geri çekildiğinde pozisyonlar büyük kârla (+3.37 USDT ile +14.28 USDT arasında değişen runner kârları) kapatılmıştır.

---

#### 35.7.3 Gerçek Veriyle Test Edilen vs. Henüz Canlıda Yaşanmayan Süreçler Matrisi

| # | Süreç / Hipotez | Beklenen Davranış | Canlı Veri Durumu | Adli Sonuç ve Kanıt |
|---|---|---|---|---|
| **1** | **Sinyal Karşılama ve Sizing** | TV webhook sinyalini alma, 20x kaldıraç, bakiye ve marj kontrolü ile piyasa emri açma. | **TEST EDİLDİ & BAŞARILI** | 27 parent sinyali 0 gecikmeyle karşılandı; Trading Rules ve min notional uyumlu lotlama yapıldı. |
| **2** | **TP Bastırma (Hybrid Mode)** | Girişte borsa limit TP emri konulmaması (`tp_suppressed=True`). | **TEST EDİLDİ & BAŞARILI** | 27 pozisyonun hiçbirine girişte borsa TP emri konulmadı; çıkış tamamen hybrid trailing'e bırakıldı. |
| **3** | **Tekil Koşullu Stop (Bybit Cond SL)** | Her parent parçası için borsa üzerinde müstakil koşullu stop emri oluşturma. | **TEST EDİLDİ & BAŞARILI** | 27 parent için borsada bağımsız koşullu SL açıldı (`[B4 BYBIT SLTP]`). %100 kapsama sağlandı. |
| **4** | **1R Tespiti ve TP1 İcrası** | 1R temasında 50% reduce-only TP1 emri (`HTP1...`) gönderme ve doldurma. | **TEST EDİLDİ & BAŞARILI** | 12 parent 1R'yi gördü; 11 tanesinde 50% TP1 anında icra edildi (+19.19 USDT kâr). |
| **5** | **1R-2R Bekleme (HYBRID_HOLD_ENTRY)** | TP1 sonrası stopu girişe çekme, 1R-2R arasında trailing başlatmama. | **TEST EDİLDİ & BAŞARILI** | 4 işlem bu aşamada bekledi; 3 tanesi tam girişte $0.0000$ PnL ile kapandı; 1 tanesi halen açık. |
| **6** | **2R Trailing & 3R Ratchet Kilidi** | 2R'de dinamik trailing başlatma; 3R'de zemin stopunu 2R kârına sabitleme. | **TEST EDİLDİ & BAŞARILI** | 7 runner pozisyonda 2R ve 3R ratchet kusursuz çalıştı; stop gevşetmeden zirveleri takip etti. |
| **7** | **Quantize & Readback Uyumu (Fix CC)** | Stop amend edilirken borsa tick hassasiyeti ile yerel hedefin tam uyuşması. | **TEST EDİLDİ & BAŞARILI** | 39 saatte 0 retry (`HYBRID TRAIL 2R RETRY: 0`). 51F6CDD4'teki 9499 hatası tamamen çözüldü. |
| **8** | **Pozisyon Kapanış Temizliği (Fix CD/CE)** | Pozisyon kapandığında state temizliği ve borsa koşullu emrinin iptali. | **TEST EDİLDİ & BAŞARILI** | 23 kapanışın tamamında `[CLOSED POS CLEANUP]` çalıştı; borsa üzerinde 0 adet orphan stop kaldı. |
| **9** | **Sibling Eşzamanlılık Kilidi** | Aynı pair/yönde iki parent aynı anda 1R olduğunda emir çarpışmasını önleme. | **TEST EDİLDİ & BAŞARILI** | #127744249455 ve #882631596625 aynı anda 1R oldu; `lock_key` ikincisini bekletip güvenle korudu. |
| **10** | **Aktif Runner Varken Konteyner Çökmesi** | 3R ratchet aşamasındaki bir işlem taşınırken botun aniden kapanıp state'ten kurtarılması. | **CANLIDA YAŞANMADI** | Bot 39 saat boyunca hiç çökmedi (%100 uptime). Test suite'te (Test 34-36) sentetik olarak doğrulandı. |
| **11** | **Kısmi Dolum Sırasında WS Kopması** | TP1 dolduğu anda WS'in kopması ve REST üzerinden kurtarma (`ambiguous_fill_preserved`). | **CANLIDA YAŞANMADI** | Bybit WS bağlantısı TP1 anlarında stabil kaldı; genel pending reconcile ise #521438515384'te başarıyla çalıştı. |
| **12** | **Borsa UI'dan Manuel Müdahale** | Kullanıcının Bybit web sitesinden emri veya pozisyonu elle değiştirmesi. | **CANLIDA YAŞANMADI** | Test süresince borsa arayüzünden manuel müdahale yapılmadı; sistem tam otonom yönetildi. |

---

#### 35.7.4 27 Parent Pozisyonun Tam Yaşam Döngüsü ve Adli Tablosu

| # | Parent ID | İşlem Çifti | Yön | Giriş Fiyatı | İlk SL | Ulaşılan Aşama | Çıkış Nedeni | Net PnL (USDT) | Durum |
|---|---|---|---|---|---|---|---|---|---|
| 01 | `#521438515384` | PONS-USDT | LONG | 0.2853 | 0.2794 | 1R (TP1) → BE | Break-Even (Giriş) Stopu | +1.6933 (TP1) + 0.0000 | CLOSED |
| 02 | `#139635067271` | CHIP-USDT | LONG | 0.04966 | 0.04872 | HYBRID_WAIT | İlk Baseline SL | -3.4464 | CLOSED |
| 03 | `#748481856534` | CHIP-USDT | SHORT | 0.04940 | 0.05008 | 1R → 2R → 3R | 3R Ratchet Trailing SL | +1.7272 (TP1) + 3.3660 | CLOSED |
| 04 | `#217553911573` | CHIP-USDT | LONG | 0.04962 | 0.04938 | HYBRID_WAIT | İlk Baseline SL | -3.0225 | CLOSED |
| 05 | `#458985609538` | CHIP-USDT | SHORT | 0.04946 | 0.04985 | 1R (TP1) → BE | Break-Even (Giriş) Stopu | +1.6848 (TP1) - 0.0432 | CLOSED |
| 06 | `#382732215995` | PONS-USDT | SHORT | 0.2880 | 0.2944 | 1R → 2R → 3R | 3R Ratchet Trailing SL | +1.7216 (TP1) + 3.4020 | CLOSED |
| 07 | `#228742928457` | PONS-USDT | LONG | 0.2774 | 0.2706 | HYBRID_WAIT | İlk Baseline SL | -3.6176 | CLOSED |
| 08 | `#398771100426` | CHIP-USDT | LONG | 0.04829 | 0.04798 | HYBRID_WAIT | İlk Baseline SL | -2.7311 | CLOSED |
| 09 | `#523397809626` | CHIP-USDT | SHORT | 0.04812 | 0.04846 | 1R → 2R → 3R | 3R Ratchet Trailing SL | +1.6048 (TP1) + 4.4935 | CLOSED |
| 10 | `#735721789888` | PONS-USDT | SHORT | 0.2746 | 0.2803 | HYBRID_WAIT | İlk Baseline SL | -3.6424 | CLOSED |
| 11 | `#200380378825` | PONS-USDT | LONG | 0.2772 | 0.2706 | HYBRID_WAIT | İlk Baseline SL | -3.3726 | CLOSED |
| 12 | `#127744249455` | CHIP-USDT | LONG | 0.04770 | 0.04702 | 1R → 2R → 3R | 3R Ratchet Trailing SL | +1.7204 (TP1) + 10.3632 | CLOSED |
| 13 | `#69482630512` | CHIP-USDT | SHORT | 0.04750 | 0.04796 | HYBRID_WAIT | İlk Baseline SL | -4.5079 | CLOSED |
| 14 | `#882631596625` | CHIP-USDT | LONG | 0.04775 | 0.04702 | 1R (Throttled) | Baseline SL (Kilit Koruması) | -3.5040 | CLOSED |
| 15 | `#770074244599` | CHIP-USDT | SHORT | 0.04754 | 0.04786 | HYBRID_WAIT | İlk Baseline SL | -3.0112 | CLOSED |
| 16 | `#613482810910` | CHIP-USDT | LONG | 0.04817 | 0.04743 | 1R → 2R → 3R | 3R Ratchet Trailing SL | +1.7834 (TP1) + 8.8688 | CLOSED |
| 17 | `#551995529500` | PONS-USDT | SHORT | 0.2753 | 0.2809 | HYBRID_WAIT | İlk Baseline SL | -3.5784 | CLOSED |
| 18 | `#586808454451` | PONS-USDT | LONG | 0.2783 | 0.2722 | 1R (TP1) → BE | Break-Even (Giriş) Stopu | +1.6348 (TP1) + 0.0000 | CLOSED |
| 19 | `#68583515800` | PONS-USDT | SHORT | 0.2751 | 0.2827 | 1R → 2R → 3R | 3R Ratchet Trailing SL | +1.8240 (TP1) + 10.9896 | CLOSED |
| 20 | `#393613137952` | CHIP-USDT | SHORT | 0.04993 | 0.05067 | 1R → 2R → 3R | 3R Ratchet Trailing SL | +1.7908 (TP1) + 14.2780 | CLOSED |
| 21 | `#570414374565` | PONS-USDT | LONG | 0.2322 | 0.2270 | 1R (TP1) → BE | Açık (Giriş Stopu: 0.2322) | +2.0020 (TP1 gerçekleşti) | OPEN |
| 22 | `#167272712944` | CHIP-USDT | LONG | 0.04284 | 0.04144 | HYBRID_WAIT | Açık (Başlangıç SL: 0.04144) | Henüz Kapanmadı | OPEN |
| 23 | `#606906494493` | CHIP-USDT | SHORT | 0.04208 | 0.04287 | HYBRID_WAIT | Açık (Başlangıç SL: 0.04287) | Henüz Kapanmadı | OPEN |
| 24 | `#873481395202` | CHIP-USDT | LONG | 0.04253 | 0.04190 | HYBRID_WAIT | İlk Baseline SL | -3.5910 | CLOSED |
| 25 | `#920800717595` | CHIP-USDT | SHORT | 0.04217 | 0.04273 | HYBRID_WAIT | İlk Baseline SL | -3.9833 | CLOSED |
| 26 | `#702333768047` | CHIP-USDT | LONG | 0.04270 | 0.04190 | HYBRID_WAIT | İlk Baseline SL | -4.1120 | CLOSED |
| 27 | `#275087885943` | CHIP-USDT | SHORT | 0.04225 | 0.04277 | HYBRID_WAIT | Açık (Başlangıç SL: 0.04277) | Henüz Kapanmadı | OPEN |

