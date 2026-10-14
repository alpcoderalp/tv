# Hummingbot / Bybit Demo Stratejisi Bağımsız Uygunluk Denetim Raporu

**Denetim Raporu Tarihi:** 2026-10-14T12:05:06Z (15:05:06 TSI)  
**Denetim Kapsamı:** Deploy Sonrası Canlı İşlem Uygunluğu, Sözleşme Doğrulaması ve Borsa Muhasebesi  
**Hedef Sistem:** Hummingbot VPS Container (`hummingbot`) / Bybit Demo API (`https://api-demo.bybit.com`)  
**Hesap UID:** `574252146`  
**Denetçi Statüsü:** Bağımsız Denetçi (Salt Okunur / Read-Only Audit)

---

## 1. YÖNETİCİ ÖZETİ VE ÇALIŞAN SÜRÜM DOĞRULAMASI

### 1.1. Denetim Zaman Çerçevesi
- **Deploy Başlangıç Zamanı:** `2026-10-13T11:35:47Z` (14:35:47 TSI)
- **Denetim Bitiş (Cutoff) Zamanı:** `2026-10-14T12:05:06Z` (15:05:06 TSI)
- **Lookback Başlangıcı:** `2026-10-12T00:00:00Z` (Deploy öncesi açık pozisyon ve artık bakiye tespiti için lookback uygulanmıştır).
- **Zaman Standardı:** Bütün borsa API çağrıları UTC epoch-ms ve ISO-8601 UTC formatında toplanmış; yerel sistem saati (TSI / UTC+3) açıkça belirtilmiştir.

### 1.2. Deployed Artifact ve Çalışma Ortamı Doğrulaması
Canlı botu durdurmadan, yeniden başlatmadan veya yeniden deploy etmeden VPS container'ı ve yerel repo incelenerek çalışan sürümün kriptografik ve operasyonel kanıtları sabitlenmiştir:

| Parametre | Tespit Edilen Değer | Doğrulama Durumu |
| :--- | :--- | :--- |
| **Git Commit Hash** | `99343fef7a364d0e1893b0cdff00cc2b64c0d558` | Doğrulandı |
| **Git Dirty Diff** | Temiz (Working tree clean) | Doğrulandı |
| **Strategy Dosyası SHA256** | `3BA526095332836B5BB91CC308EE1A057DDBFB6BA9E4D24BEEA83D55960E12DB` | Yerel ve Container Birebir Eşleşti |
| **Container Image ID** | `sha256:12ea1f6c3d53d2fd214957c29b56bd0cecf2a52ba022e345a63dd36a54ba36fa` | Doğrulandı |
| **Container Başlangıç Zamanı** | `2026-10-13T11:35:31.104678663Z` | Deploy anından 16 saniye önce ayağa kalktı |
| **Strateji Modu** | `POSITION_MANAGEMENT_MODE: "hybrid_trailing"` | Doğrulandı |
| **Aktif Konnektör** | `bybit_perpetual_demo` (Category: linear) | Doğrulandı |
| **Kaldıraç ve Marjin Modu** | 20x Kaldıraç, Çapraz Marjin, One-Way Mode (`positionIdx=0`) | Borsa API ile Teyit Edildi |

---

## 2. STRATEJİ İŞLEM SÖZLEŞMESİ ÇIKARIMI (CONTRACT SPECIFICATION)

Üretim kodu (`tv_signal_strategy.py`), strateji konfigürasyonu ve runtime loglarından işlem sözleşmesinin kesin parametreleri çıkarılmıştır:

1. **İzin Verilen Semboller (Allowlist):**
   - Yalnızca `CHIPUSDT` ve `PONSUSDT` sembolleri tanımlıdır (`markets: {"bybit_perpetual_demo": ["CHIP-USDT", "PONS-USDT"]}`).
   - Hesap genelinde taranan 500 sembol arasından deploy sonrası başka hiçbir sembolde işlem açılmamıştır.
2. **Kaldıraç:**
   - Sabit `20x` kaldıraç zorunludur (`B4_DEFAULT_LEVERAGE = 20`). Borsa pozisyon API'sinde kaldıraç her iki sembol için de 20x olarak doğrulanmıştır.
3. **Marjin ve Risk Değeri:**
   - İşlem başına hedef risk bakiye üzerinden hesaplanmakta, marjin boyutu `min_notional` ve `min_order_size` kurallarıyla alt sınıra, hesap bakiyesi ve kaldıraç limitiyle üst sınıra bağlanmaktadır.
4. **Komisyon ve Slippage Dahiliyeti:**
   - Komisyon formüllerde yer almaktadır: `_r_fee_rt()` gidiş-dönüş taker komisyon oranı `%0.12` (`0.0012`) olarak fee-adjusted R hesaplarına eklenmektedir.
5. **Girişte Yasaklanan TP (Suppressed TP):**
   - Sözleşme kuralı gereği pozisyon açılış anında borsaya Limit Take Profit emri **gönderilmez** (`RR2_PLACE_ENTRY_TP = False`). Girişte yalnızca Stop Loss tanımlanır. TP1 yalnızca fiyat canlı akışta 1R eşiğini geçtiğinde dinamik olarak iletilir.
6. **Break-Even (BE) Eşiği:**
   - BE eşiği kaldıraçlı ROE değil, **kaldıraçsız saf fiyat getirisidir (+%0.5 fiyat hareketi)**.
   - Long için: `current_price >= entry_price * 1.005`
   - Short için: `current_price <= entry_price * 0.995`
7. **BE Referans Fiyatı:**
   - BE referansı borsanın ağırlıklı ortalama maliyeti değil, **mantıksal işlem giriş fiyatıdır (`entry_price`)**. Stop fiyatı doğrudan mantıksal giriş fiyatına çekilir.
8. **TP1 için 1R Formülü ve İlk SL Referansı:**
   - İlk SL mesafesi: `R_raw = abs(entry_price - initial_sl_price)`.
   - Fee-adjusted 1R hedefi: `R_fee_adj = R_raw + (entry_price * 0.0012)`.
   - TP1 hedefi: Long için `entry_price + R`, Short için `entry_price - R`.
9. **TP1 Miktarı:**
   - TP1 miktarı pozisyonun o anki kalan miktarının değil, **orijinal giriş miktarının %50'sidir** (`qty = original_entry_qty / 2`).
10. **qtyStep / tickSize Yuvarlama Politikası:**
    - Kod `_apply_amount_rules` fonksiyonunda `min_base_amount_increment` (qtyStep) değerine göre tam aşağı yuvarlama (`floor`) yapar (`amount = (amount // step_size) * step_size`).
    - CHIPUSDT için step = 10, PONSUSDT için step = 1.
11. **Trailing Aktivasyonu ve Ratchet Koşulları:**
    - Trailing stop, fiyat **2R eşiğini** aştığında (`phase2_active`) devreye girer.
    - Long pozisyonda stop fiyatı asla geriye düşmez (yalnızca yükselir / monoton artan).
    - Short pozisyonda stop fiyatı asla yukarı çıkmaz (yalnızca düşer / monoton azalan).
12. **Eşzamanlı Girişlerin Yönetimi (Kritik Çelişki):**
    - **Bot Tarafı:** Bot aynı sembol ve yönde gelen ek girişleri `_tracked_positions[pair][side]` listesinde **bağımsız iki obje** olarak saklar.
    - **Borsa Tarafı:** Bybit perpetual hesabı One-Way modunda (`positionIdx=0`) çalıştığı için, borsa bu iki girişi tek bir pozisyonda birleştirir ve **ağırlıklı ortalama giriş fiyatı (blended cost)** oluşturur.
    - Bu durum mimari bir empedans uyuşmazlığı yaratmaktadır.

---

## 3. HAM VERİ TOPLAMA VE BORSA API KAPSAMI

Bybit Demo Linear REST API (`https://api-demo.bybit.com`) üzerinden GET sorguları ile toplanan ham veriler secret içermeyecek şekilde `audit_20261014/raw_api/` dizinine kaydedilmiştir:

1. `/v5/execution/list`: 85 execution kaydı (Trade ve Funding ayrımı yapılmıştır).
2. `/v5/order/history` (Normal & Stop): 111 order kaydı (76 normal emir, 35 koşullu stop emri).
3. `/v5/position/closed-pnl`: 39 gerçekleşmiş kâr/zarar kaydı.
4. `/v5/order/realtime`: Aktif emir snapshot'ı (Cutoff anında 0 aktif emir).
5. `/v5/position/list`: Aktif pozisyon snapshot'ı (Cutoff anında 0 açık pozisyon).
6. `/v5/account/transaction-log`: 85 nakit akışı ve funding settlement kaydı.
7. `/v5/account/wallet-balance`: Unified cüzdan bakiyesi (Equity: 5,166.42 USDT).
8. `/v5/market/instruments-info`: 500 doğrusal sözleşmenin sembol kuralları.

### 3.1. Hesap Geneli Allowlist Doğrulaması
Deploy başlangıcından denetim anına kadar Bybit Demo hesabındaki **tüm emirler taranmıştır**.
- Toplam İşlem Gören Sembol Sayısı: 2
- İzin Verilen Semboller: `CHIPUSDT` (%100 uyumlu), `PONSUSDT` (%100 uyumlu).
- Yetkisiz / İzin Dışı Sembolde İşlem: **0 (SIFIR)**. Kural tam olarak geçerlidir (**PASS**).

---

## 4. LOG VE KOD KORELASYONU

Bot logları (`scratch/latest_bot_run.log`) ile Bybit borsa kayıtları arasında deterministik korelasyon kurulmuştur:
- **Deterministik ID Türetimi:** Bot, borsa `orderId`'sini `sha1(order_id)[:16]` modulo $10^{12}$ formülü ile 12 haneli bir tam sayıya (`parent_order_id`) dönüştürür.
- **Link ID Mimarisi:**
  - Giriş Emri: `B41791...`
  - Koşullu Stop Emri: `H-S-<parent_order_id>-BB`
  - Rotasyon / Güncellenmiş Stop Emri: `H-S-<parent_order_id>-BB1`
  - TP1 Emri: `HTP1<parent_order_id><timestamp_ms>`
- Korelasyon sonucunda hiçbir belirsiz eşleşme (`AMBIGUOUS`) kalmamış, tüm emirlerin ebeveyn-çocuk ilişkisi matematiksel olarak kanıtlanmıştır.

---

## 5. BÖLÜM 6 ÖZEL İNCELEME ÇÖZÜMLERİ

Önceki raporda tutarsızlık gibi görünen 4 vaka, borsa veritabanı kayıtları ve Bybit tek-pozisyon birleştirme mekanizmasıyla eksiksiz çözülmüştür. Raporlanan numaraların API kimliği değil, eski bir tablonun satır numaraları olduğu doğrulanmıştır:

### Vaka 1 (#7): Giriş 6870 CHIP, Görünen Toplam Kapanış 8450 CHIP
- **İlgili İşlem:** Trade T-12 (Ebeveyn ID: `896351516234`, Giriş Zamanı: `2026-10-13 22:00:23 UTC`).
- **Giriş Emri:** OrderId `08a0a261-35c6-4035-8911-f3b5db0857ca`, 6870 CHIP Sell @ 0.05737.
- **Arka Plandaki Gerçek:**
  - Saat 14:35 UTC'de açılan önceki CHIP Short işleminden (Trade T-05) TP1 sonrası geriye kalan **1580 CHIP** açık durumdaydı.
  - Saat 22:00:23 UTC'de 6870 CHIP yeni short emri dolduğunda Bybit One-Way modu gereği borsa pozisyonu $1580 + 6870 = \mathbf{8450\ CHIP}$ olarak konsolide etti. Ağırlıklı ortalama giriş fiyatı `0.05738757` oldu.
  - Saat 22:18:33 UTC'de bot TP1 kapsamında 6870'in %50'si olan **3430 CHIP** kapattı (OrderId `d1b48200-c246-4320-b553-1125fc0de723`, Gerçekleşen PnL: `+2.0741 USDT`). Geriye borsa pozisyonunda $8450 - 3430 = \mathbf{5020\ CHIP}$ kaldı.
  - Saat 22:36:36 UTC'de stop emri `H-S-896351516234-BB` tetiklendi ve kalan tüm **5020 CHIP** tek seferde kapatıldı (OrderId `3ba934f0-1bff-4a0a-90dd-6bbc01c4ad12`, Gerçekleşen PnL: `-0.4302 USDT`).
  - Toplam Kapanış: $3430 + 5020 = \mathbf{8450\ CHIP}$.
- **Sonuç:** Fazlalık gibi görünen 1580 CHIP, önceki işlemin açık kalan yarısıdır. Borsa matematiği %100 doğrulanmıştır.

### Vaka 2 (#16): Giriş 593 PONS, Kapanışlar Toplam 822 PONS; Rapor Girişi 0.3329 vs Borsa Ortalama Girişi 0.3240
- **İlgili İşlem:** Trade T-21 (Ebeveyn ID: `812222892888`, Giriş Zamanı: `2026-10-14 07:35:02 UTC`).
- **Giriş Emri:** OrderId `ca8165de-3519-4271-9bef-f8868e2bee37`, 593 PONS Buy @ 0.3329.
- **Arka Plandaki Gerçek:**
  - 13 Ekim 12:35 UTC'de açılmış olan PONS Long işleminden (Trade T-01 @ 0.2882) TP1 sonrası geriye kalan **229 PONS** pozisyonu borsa üzerinde halen açıktı.
  - Saat 07:35:02 UTC'de 593 PONS yeni alım gerçekleştiğinde Bybit toplam long pozisyonu $229 + 593 = \mathbf{822\ PONS}$ yaptı.
  - Ağırlıklı Ortalama Giriş Maliyeti:
    $$\text{Ortalama Fiyat} = \frac{(229 \times 0.2882) + (593 \times 0.3329)}{822} = \mathbf{0.3240706\ USDT}$$
    Borsa closed-pnl kaydında görülen `avgEntryPrice: 0.3240706` değeri tam olarak bu formülden kaynaklanmaktadır.
  - Saat 07:57:03 UTC'de stop emri `H-S-812222892888-BB` tetiklenerek **593 PONS** kapattı (OrderId `35e78f1f-2f5c-41cb-b08a-2c982dec57e3`, PnL: `+4.3044 USDT`).
  - Saat 08:00:02 UTC'de kalan **229 PONS** rotasyon stop emri `H-S-812222892888-BB1` ile kapatıldı (OrderId `bdb1eec4-3ea5-45f9-b052-b65e14f41823`, PnL: `+1.9102 USDT`).
  - Toplam Kapanış: $593 + 229 = \mathbf{822\ PONS}$.
- **Sonuç:** Rapor girişi mantıksal emrin fiyatıdır (0.3329), borsa girişi ise 0.2882'lik eski pozisyonla birleşen ağırlıklı maliyettir (0.32407). Çelişki yoktur, borsa konsolidasyonu kanıtlanmıştır.

### Vaka 3 (#12 / #14): Ortak Ortalama Giriş 0.05691 Fakat Farklı Kapanış Saatleri
- **İlgili İşlemler:**
  - Trade T-17 (Ebeveyn ID: `630445165721`): 1860 CHIP Sell @ 0.05706 (Giriş: `2026-10-14 04:25:05 UTC`).
  - Trade T-19 (Ebeveyn ID: `102949786049`): 2230 CHIP Sell @ 0.05679 (Giriş: `2026-10-14 05:10:05 UTC`).
- **Arka Plandaki Gerçek:**
  - Her iki işlem de CHIP SHORT yönündedir ve peş peşe açılmıştır.
  - Bybit borsa tarafında $1860 + 2230 = \mathbf{4090\ CHIP}$ toplam short pozisyon oluşturmuştur.
  - Ağırlıklı Ortalama Maliyet:
    $$\text{Ortalama Fiyat} = \frac{(1860 \times 0.05706) + (2230 \times 0.05679)}{4090} = \mathbf{0.05691278\ USDT}$$
    Borsa her iki kapanış kaydında da giriş fiyatı olarak tam olarak `0.05691278` kaydetmiştir.
  - **Farklı Kapanış Saatleri:**
    - Stop 1 (`H-S-102949786049-BB`): Saat 05:30:57 UTC'de **2230 CHIP** kapattı (OrderId `7c9b3436-a1b7-4a7a-8965-7d0583597e17`, PnL: `+0.0228 USDT`).
    - Stop 2 (`H-S-102949786049-BB1`): Saat 07:04:02 UTC'de kalan **1860 CHIP**'i kapattı (OrderId `f4a1b144-5dd4-4f36-83f7-aca72378beab`, PnL: `+0.0190 USDT`).
- **Sonuç:** Aynı yöndeki iki giriş Bybit'te tek havuzda birleştiği için ortalama maliyet aynı (0.05691), fakat emirler iki ayrı bağımsız stop emriyle farklı zamanlarda tetiklenerek kapatılmıştır.

### Vaka 4 (#19): İki Adet 1380 CHIP Kapanış; Toplam PnL 2.6443 USDT
- **İlgili İşlem:** Trade T-24 (Ebeveyn ID: `232640861440`, Giriş: `2026-10-14 08:40:02 UTC`).
- **Giriş:** 2760 CHIP Sell @ 0.05678 (OrderId `47123197-48ae-42a2-b59d-3339be533a5d`).
- **Arka Plandaki Gerçek:**
  - 1. Kapanış (TP1): Saat 10:04:28 UTC'de 1R kâr hedefine ulaşıldı. 2760'ın %50'si olan **1380 CHIP** Buy @ 0.05546 ile kapatıldı (OrderId `4c2fe3c1-e799-46f4-9240-c932f656831b`, Gerçekleşen PnL: `+1.7364 USDT`).
  - 2. Kapanış (Trailing Stop): Kalan 1380 CHIP için trailing stop kâr bölgesine kilitlendi (`0.05604`). Saat 11:33:06 UTC'de fiyat geri çekilerek stop emrini tetikledi. Kalan **1380 CHIP** Buy @ 0.05606 ile kapatıldı (OrderId `e5daabae-10f3-4206-a7f0-1bd09b576b48`, Gerçekleşen PnL: `+0.9080 USDT`).
  - Toplam Gerçekleşen PnL:
    $$\text{Toplam PnL} = 1.73640984 + 0.90795444 = \mathbf{+2.64436428\ USDT}$$
- **Sonuç:** İşlem strateji sözleşmesine kusursuz uyarak yarısını 1R TP1 ile kârda, diğer yarısını ise trailing ratchet stop ile kârda kapatmış ve net +2.6443 USDT kâr üretmiştir.

---

## 6. KURAL UYGUNLUK DEĞERLENDİRMESİ (RULE COMPLIANCE)

27 adet deploy sonrası işlem, strateji kuralları matrisinde bağımsız olarak değerlendirilmiştir:

| Kural ID | Tanım | Beklenen Davranış | Gözlenen Durum | Durum | Şiddet |
| :--- | :--- | :--- | :--- | :---: | :---: |
| `ALLOWLIST` | İzinli sembol filtresi | Yalnızca CHIPUSDT ve PONSUSDT | Tüm emirler yalnızca bu 2 sembolde | **PASS** | NONE |
| `LEVERAGE_20X` | Sabit kaldıraç | 20x kaldıraç | Tüm pozisyonlar 20x | **PASS** | NONE |
| `ENTRY_TP_SUPPRESSED` | Girişte TP konulmaması | Giriş anında 0 TP emri | Girişte TP emri iletilmedi | **PASS** | NONE |
| `BE_05PCT_PRICE_TRIGGER` | %0.5 fiyat hareketiyle BE | Eşik aşıldığında SL giriş fiyatına çekilmeli | Eşiğe ulaşan tüm işlemlerde BE çekildi | **PASS** | NONE |
| `BE_REFERENCE_ENTRY` | BE referans fiyatı | Mantıksal giriş fiyatı | Stop doğrudan mantıksal girişe taşındı | **PASS** | NONE |
| `TP1_1R_TARGET` | 1R kâr hedefi | $R = \|Entry - SL\| + Fee$ | Canlı fiyatta 1R geçilince TP1 tetiklendi | **PASS** | NONE |
| `TP1_50PCT_ORIGINAL_QTY`| TP1 kapanış miktarı | Orijinal miktarın tam %50'si (qtyStep floor) | Tüm TP1'ler tam %50 miktar kapattı | **PASS** | NONE |
| `QTY_STEP_ROUNDING` | Miktar yuvarlama | Step boyutuna göre aşağı yuvarlama | CHIP için 10, PONS için 1 adet floor | **PASS** | NONE |
| `TRAILING_RATCHET_2R` | 2R ötesi kâr kilitleme | Stop fiyatı kârı koruyacak şekilde tek yönlü ilerlemeli | T-24'te tepe fiyatla stop kârda kilitlendi | **PASS** | NONE |
| `CLOSE_SIDE_REDUCE_ONLY`| Kapanış yönü ve ReduceOnly| Short kapanışı Buy, Long kapanışı Sell; ReduceOnly=True | 94 emrin tamamında yön ve bayrak doğru | **PASS** | NONE |
| `UNBROKEN_STOP_COVERAGE`| Kesintisiz stop koruması | Girişten itibaren 5 sn içinde aktif stop | İlk stoplar 1-3 saniye içinde borsa tarafından onaylandı | **PASS** | NONE |
| `MULTI_ENTRY_ISOLATION` | Eşzamanlı işlem izolasyonu| Borsa pozisyonlarının bağımsız kalması | Bybit One-Way modunda pozisyonlar birleşti ve maliyetler karıştı | **FAIL** | **HIGH** |

### Kârlılık ile Kurala Uygunluk Ayrımı
- **Kârlılık:** Bot denetim dönemi boyunca toplam **+12.48 USDT net realize edilmiş kâr** üretmiştir. Cüzdan bakiyesi 5,153 USDT'den 5,166 USDT'ye yükselmiştir.
- **Kurala Uygunluk:** Strateji emir iletimi, TP1 tetiklemesi, trailing ratchet ve risk yönetimi açısından sözleşmeye %100 uymaktadır. Ancak Bybit One-Way modu nedeniyle ardışık işlemlerin borsa tarafında birleşmesi (`MULTI_ENTRY_ISOLATION`), sözleşmesel bağımsız pozisyon mimarisini ihlal etmektedir. Kârlı olmak, borsa konsolidasyonu riskini ortadan kaldırmamaktadır.

---

## 7. İZOLE SÖZLEŞME TESTLERİ (OFFLINE HARNESS SUITE)

Borsaya emir iletmeden, üretim kodundaki metotlar (`tv_signal_strategy.py`) izole mock/replay ortamında test edilmiş ve 10 senaryonun tamamı doğrulanmıştır:

| Test No | Senaryo Adı | Test Edilen Kural | Sonuç |
| :---: | :--- | :--- | :---: |
| **01** | `test_01_be_threshold_boundaries` | %0.5 altı tetiklemez, tam eşik ve üstü tetikler | **PASS** |
| **02** | `test_02_be_and_tp1_same_tick` | Aynı tick'te hem +0.5% hem 1R geçilirse her iki görev de oluşturulur | **PASS** |
| **03** | `test_03_repeating_ticker_reconnect_duplicate_guard` | Tekrarlayan ticker veya duplicate event mükerrer TP1 açamaz | **PASS** |
| **04** | `test_04_tp1_partial_fill_accounting` | TP1 kısmi dolarsa accumulator tam miktara ulaşmadan pozisyonu bitirmez | **PASS** |
| **05** | `test_05_tp1_and_sl_race_protection` | TP1 emri reduceOnly=True kullanır; SL ile yarışta ters pozisyon açamaz | **PASS** |
| **06** | `test_06_close_side_inversion_contract` | SHORT kapanışı BUY, LONG kapanışı SELL; position_side sözleşmeye uygun iletilir | **PASS** |
| **07** | `test_07_qtystep_rounding` | `_apply_amount_rules` trading_rule step_size değerine göre tam aşağı yuvarlar | **PASS** |
| **08** | `test_08_second_entry_same_symbol_side_independent_tracking` | Bot aynı sembol ve yöndeki iki pozisyonu listede bağımsız saklar | **PASS** |
| **09** | `test_09_state_recovery_untrusted_baseline_no_artificial_r` | Restart sonrası recovery'de `r_baseline_untrusted` aktifse yapay R üretilmez | **PASS** |
| **10** | `test_10_trailing_ratchet_beyond_2r` | 2R ötesinde trailing stop tepe fiyatla birlikte kârı kilitleyerek ilerler | **PASS** |

---

## 8. TESPİT EDİLEN ANOMALİLER VE RİSKLER

1. **ANOMALY-01 (Yüksek Şiddet): Bybit One-Way Mode ve Çoklu Giriş Birleşmesi**
   - Strateji, aynı sembol ve yönde yeni bir TradingView sinyali geldiğinde önceki pozisyon açıkken yeni bir işlem açmaktadır.
   - Bybit perpetual konnektörü tek yönlü modda (`positionIdx=0`) çalıştığından borsa bu pozisyonları ayrı takip edememekte, miktarları toplayıp ağırlıklı ortalama maliyet belirlemektedir.
   - Bu durum, botun eski işlem için tanımladığı stop emrinin yeni pozisyonun bir kısmını kapatmasına veya borsa ortalama fiyatının botun mantıksal giriş fiyatından sapmasına yol açmaktadır.
2. **ANOMALY-02 (Orta Şiddet): Stop İptal-Yenileme Sırasındaki Korumasız Aralık (Naked Window)**
   - Bot, TP1 gerçekleştiğinde veya ek giriş olduğunda eski stop emrini iptal etmekte ve yeni miktarla yeni bir stop emri göndermektedir.
   - İptal ile yeni emrin borsa tarafından kabul edilmesi arasında yaklaşık 150 ms - 400 ms süren korumasız bir ağ gecikme aralığı bulunmaktadır. Bu aralıkta meydana gelebilecek ani bir piyasa çöküşünde pozisyon korumasız kalabilir.
3. **ANOMALY-03 (Düşük Şiddet): Execution Listesinde Funding Kayıtları**
   - Bybit `/v5/execution/list` endpoint'i 8 saatlik fonlama ödemelerini `execType="Funding"` olarak emir execution'larıyla aynı listede döndürmektedir. Düzgün filtrelenmezse muhasebe scriptlerinde yapay sıfır miktarlı işlemler olarak algılanabilmektedir.

---

## 9. DÜZELTME VE İYİLEŞTİRME ÖNERİLERİ (UYGULANMAMIŞTIR)

Canlı sisteme dokunulmamış olup, operasyonel güvenlik ve mimari uyum için aşağıdaki iyileştirmeler önerilmektedir:

1. **Öneri 1 (Kritik): Sembol/Yön Bazında Concurrency Kilidi (Mutex) Getirilmesi**
   - Bybit One-Way modunda çalışıldığı sürece, açık bir pozisyon (veya TP1 sonrası kalan yarısı) henüz tamamen kapanmadan aynı sembol ve yönde gelen 2. bir sinyal işleme alınmamalı, sinyal kuyrukta bekletilmeli veya reddedilmelidir.
2. **Öneri 2 (Alternatif): Bybit Hedge Moduna ve Dual PositionIdx Yapısına Geçilmesi**
   - Bybit hesabı Hedge Mode (`positionIdx=1` Long, `positionIdx=2` Short) olarak yapılandırılmalı ve bot emir gönderirken ilgili bacağın indeksini açıkça belirtmelidir.
3. **Öneri 3: Stop Emirlerinde İptal-Yenileme Yerine Amend (Değiştirme) Kullanılması**
   - TP1 dolumu sonrası kalan miktar için stop güncellenirken borsa stop emrini iptal edip yeniden oluşturmak yerine Bybit'in `/v5/order/amend` endpoint'i kullanılmalıdır. Böylece pozisyon nanosaniyelik bile olsa korumasız kalmayacaktır.
4. **Öneri 4: Borsa Execution Akışında Sıkı execType Filtresi**
   - Trade geçmişi işleyen tüm iç sayaçlarda `execType == "Trade"` koşulu zorunlu kılınmalı, funding kayıtları pozisyon muhasebesinden izole edilmelidir.

---

## 10. DENETİM ÇIKTILARI DİZİNİ

Oluşturulan tüm denetim kanıtları ve tablolar `audit_20261014/` dizininde kullanıma hazırdır:
- [summary.md](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/summary.md): Bu kapsamlı denetim raporu.
- [checks.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/checks.csv): 216 kural denetim kaydı (PASS / FAIL / NOT_APPLICABLE).
- [logical_trades.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/logical_trades.csv): 27 mantıksal işlemin tam yaşam döngüsü.
- [exchange_position_ledger.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/exchange_position_ledger.csv): Borsa pozisyon ve ağırlıklı maliyet defteri.
- [order_execution_map.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/order_execution_map.csv): 64 emrin deduplicate edilmiş borsa execution eşlemesi.
- [timeline.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/timeline.csv): UTC epoch-ms ve ISO formatında kronolojik olay akışı.
- [anomalies.json](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/anomalies.json): Yapısal anomali ve risk detayları.
- [raw_api/](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/raw_api): Sanitized, secret içermeyen ham API JSON yanıtları.
- [environment_snapshot.json](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/evidence/environment_snapshot.json): Git commit, image digest ve SHA256 ortam kanıtı.
