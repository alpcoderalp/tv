# Hummingbot / Bybit Demo Stratejisi Bağımsız Uygunluk Denetim Raporu (Revize)

**Denetim Tarihi:** 2026-10-14T12:05:06Z (15:05:06 TSI)  
**Denetim Kapsamı:** Deploy Sonrası Canlı İşlem Sözleşmesi Uygunluğu, Çalışma Ortamı Doğrulaması ve Borsa Muhasebesi  
**Hedef Sistem:** Hummingbot VPS Docker Konteyneri (`hummingbot`) / Bybit Demo Linear API (`https://api-demo.bybit.com`)  
**Hesap UID:** `574252146`  
**Denetçi Statüsü:** Bağımsız Denetçi (Salt Okunur / Read-Only Audit — Canlı bot dosyalarına, emirlerine veya konfigürasyonuna dokunulmamıştır)

---

## 1. ÇALIŞAN SÜRÜM VE ÇALIŞMA AĞACI DOĞRULAMASI (REVISED)

Yerel repo çalışma ağacı, git geçmişi ve VPS üzerindeki canlı container birebir incelenerek kriptografik kanıtlar çıkarılmıştır:

| Parametre | Değer / Kanıt | Notlar ve Fark Analizi |
| :--- | :--- | :--- |
| **Git HEAD Commit** | `99343fef7a364d0e1893b0cdff00cc2b64c0d558` | Branch: `bybit_migration` |
| **Çalışma Ağacı Durumu** | **DIRTY (Commit edilmemiş değişiklikler mevcut)** | `tv_signal_strategy.py` üzerinde +3498 satır commit edilmemiş değişiklik vardır. |
| **HEAD Commit Strategy SHA256** | `94DF73B9A70792751C0805E0CFB4565409A23FC333A0D6030B40CCAFB488EE92` | Git HEAD sürümünün hash'i |
| **Yerel Çalışma Dosyası SHA256** | `3BA526095332836B5BB91CC308EE1A057DDBFB6BA9E4D24BEEA83D55960E12DB` | Çalışma ağacındaki aktif dosya |
| **Canlı VPS Container SHA256** | `3BA526095332836B5BB91CC308EE1A057DDBFB6BA9E4D24BEEA83D55960E12DB` | **Canlıda çalışan sürüm, git HEAD commit'i DEĞİL, commit edilmemiş DIRTY çalışma kopyasıdır.** |
| **Container Image ID** | `sha256:12ea1f6c3d53d2fd214957c29b56bd0cecf2a52ba022e345a63dd36a54ba36fa` | Doğrulandı |
| **Container Başlangıç Zamanı** | `2026-10-13T11:35:31.104678663Z` | Deploy anından 16 saniye önce ayağa kaldırıldı |
| **Aktif Strateji Modu** | `POSITION_MANAGEMENT_MODE: "hybrid_trailing"` | Doğrulandı |
| **Borsa Hesap Modu** | Tek Yönlü Mod (One-Way Mode, `positionIdx=0`), Çapraz Marjin | Bybit API ile teyit edildi |

---

## 2. STRATEJİ İŞLEM SÖZLEŞMESİ ÇIKARIMI (CONTRACT SPECIFICATION)

1. **İzin Verilen Semboller:** Yalnızca `CHIPUSDT` ve `PONSUSDT`.
2. **Kaldıraç:** Sabit `20x` (`B4_DEFAULT_LEVERAGE = 20`).
3. **Komisyon / Slippage:** Komisyon dahil; `_r_fee_rt()` gidiş-dönüş komisyon oranı `%0.12` (`0.0012`) olarak 1R ve risk hesaplarına eklenmektedir.
4. **Girişte Yasaklanan TP (Suppressed TP):** Giriş anında borsaya Take Profit limit emri **iletilmez** (`RR2_PLACE_ENTRY_TP = False`). TP1 yalnızca fiyat canlı akışta 1R eşiğini geçtiğinde dinamik olarak iletilir.
5. **Break-Even (BE) Eşiği:** Kaldıraçlı ROE değil, **kaldıraçsız saf fiyat getirisidir (+%0.5)** (`price >= entry * 1.005` veya `price <= entry * 0.995`).
6. **BE Referansı:** Borsa ağırlıklı maliyeti değil, **mantıksal işlem giriş fiyatıdır (`entry_price`)**.
7. **TP1 için 1R Formülü:** $R = |Entry - SL| + (Entry \times 0.0012)$. TP1 seviyesi $Entry \pm R$.
8. **TP1 Miktarı:** Pozisyonun kalan miktarının değil, **orijinal giriş miktarının %50'sidir** (`qtyStep` floor yuvarlama ile).
9. **Trailing Stop:** Fiyat **2R eşiğini** aştığında devreye girer; tepe fiyatla birlikte kârı kilitleyerek tek yönlü (monotonik) ilerler.
10. **Eşzamanlı Giriş Yönetimi (Temel Çelişki):**
    - **Bot Mantığı:** Aynı sembol/yöndeki işlemleri bellekte bağımsız iki obje olarak saklar.
    - **Borsa Mantığı:** Bybit One-Way modunda (`positionIdx=0`) aynı yöndeki tüm girişleri tek bir havuzda birleştirir ve **ağırlıklı ortalama giriş fiyatı (blended cost)** oluşturur.
    - **Hedge Mode Yanılgısı:** Bybit Hedge modu yalnızca Long ile Short bacaklarını (`positionIdx=1` ve `positionIdx=2`) ayırır; **aynı yöndeki iki Long veya iki Short pozisyonunu AYIRMAZ**. Bu nedenle Hedge modu eşzamanlı aynı yönlü işlemleri izole edemez.

---

## 3. BORSA MUHASEBESİ, FEE/PNL VE LOOKBACK ANALİZİ (REVISED)

### 3.1. Ücret ve PnL Muhasebe Anlamı
Bybit V5 `/v5/position/closed-pnl` endpoint'indeki alanların muhasebe anlamı doğrulanmıştır:
- `cumEntryValue`: Toplam giriş değeri ($Qty \times avgEntryPrice$).
- `cumExitValue`: Toplam çıkış değeri ($Qty \times avgExitPrice$).
- `openFee`: Giriş anında ödenen borsa komisyonu.
- `closeFee`: Kapanış anında ödenen borsa komisyonu.
- `closedPnl`: Gerçekleşen kâr/zarar tutarı.
  $$\text{closedPnl} = (\text{cumExitValue} - \text{cumEntryValue}) \times \text{direction} - \text{openFee} - \text{closeFee}$$
- **Kritik Doğrulama:** Bybit'in `closedPnl` alanı **açılış ve kapanış komisyonlarını ZATEN DÜŞMÜŞTÜR (NET TUTAR)**. Dolayısıyla pozisyon nakit akışı hesaplanırken `closedPnl` üzerinden `closeFee` bir kez daha düşülmemelidir (mükerrer komisyon kesintisi yapılmamalıdır).

### 3.2. Deploy Öncesi Başlangıç Durumu (Lookback Analizi)
- Lookback aralığı `2026-10-12T00:00:00Z` ile deploy anı `2026-10-13T11:35:47Z` arasında çalıştırılmıştır.
- **CHIPUSDT ve PONSUSDT:** Deploy anından önce hesapta hiçbir CHIP veya PONS işlemi bulunmamaktadır. Her iki sembolün de başlangıç pozisyonu **tam olarak 0 (FLAT)** durumundadır.
- **Diğer Semboller:** `2026-10-12` öncesinden kalan geçmiş ZAMAUSDT pozisyonu lookback penceresi başında açık kalmıştır; ancak lookback başlangıcı öncesi veriler bilinmediğinden `2026-10-12` öncesi başlangıç bakiye durumu **EKSİK KANIT (LOOKBACK ÖNCESİ BİLİNMİYOR)** olarak işaretlenmiştir.
- **Funding settlements:** `/v5/execution/list` endpoint'inde yer alan 8 saatlik `execType == "Funding"` kayıtları trade emirlerinden izole edilmiştir.

---

## 4. ÖZEL İNCELEME BULGULARI (BÖLÜM 6 VAKALARI)

### Vaka 1 (#7): Giriş 6870 CHIP, 5020'lik Kapanışın Parent/CID ve Aggregate Fallback Gerekçesi
- **İlgili İşlem:** Trade `T-12` (Ebeveyn ID: `896351516234`, Giriş: `2026-10-13 22:00:23 UTC`, 6870 CHIP Sell @ 0.05737).
- **Arka Plandaki Gerçek Mekanizma:**
  1. Saat 14:35 UTC'de açılmış olan Trade `T-05`'ten (parent `#18400454197`) TP1 sonrası geriye kalan **1580 CHIP** açık durumdaydı.
  2. Saat 22:00:23 UTC'de 6870 CHIP yeni short girildiğinde Bybit tek pozisyonda $1580 + 6870 = \mathbf{8450\ CHIP}$ aggregate short pozisyon oluşturdu.
  3. Bot saat 22:00:26 UTC'de `qty=6870` olan `H-S-896351516234-BB` stop emrini (OrderId: `3ba934f0-1bff-4a0a-90dd-6bbc01c4ad12`) iletti.
  4. Saat 22:18:33 UTC'de TP1 kapsamında 6870'in %50'si olan **3430 CHIP** kapatıldı (`HTP18963515162341791929913426`). Borsa üzerinde geriye kalan aggregate pozisyon boyutu $8450 - 3430 = \mathbf{5020\ CHIP}$ oldu.
  5. Bybit üzerindeki koşullu stop emri `closeOnTrigger: True` ve `reduceOnly: True` bayraklarına sahipti. Saat 22:36:36 UTC'de bu stop tetiklendiğinde borsa emri **mevcut tüm borsa pozisyon boyutu olan 5020 CHIP** üzerinden doldurdu.
  6. **Aggregate Fallback ve Yamyamlık (Cannibalization):** Stop emri `H-S-896351516234-BB`, 5020 CHIP doldurarak önceki ebeveyne (`#18400454197`) ait **1580 CHIP**'lik kalıntıyı da yuttu. Borsa pozisyonu sıfırlanınca bot loglara şu kaydı düştü:
     ```text
     22:36:36,664 - ⚡ [WS POS CLOSED] CHIP-USDT SHORT size=0 → kalan tüm legler ve parça tracking'i anında temizleniyor
     22:36:38,346 - ⚡ [WS POS CLOSED] CHIP-USDT SHORT - H-S-18400454197-BB (COND SL) anında iptal edildi
     22:36:38,348 - 📁 [POSITION_FLAT CLOSE ARCHIVED] CHIP-USDT SHORT #18400454197 - qty=1580 @ 0.05827 pnl=0.0000 (close_order=SYNTH_FLAT_18400454197)
     ```
- **Sonuç:** Kapanış miktarlarının $3430 + 5020 = 8450$ tutması bir izolasyon kanıtı DEĞİLDİR. Aksine, ebeveyn `896351516234`'e ait stop emrinin ebeveyn `18400454197`'nin pozisyonunu yuttuğunun ve botun borsa sıfırlandığı için acil sentetik temizlik (`SYNTH_FLAT`) yaptığının açık kanıtıdır.

### Vaka 2 (#16): Çok Aşamalı Ağırlıklı Giriş Hesabı (0.3240706 USDT Kesin İspatı)
- **Hata Düzeltmesi:** Önceki raporda yapılan $(229 \times 0.2882 + 593 \times 0.3329) / 822 = 0.32044708$ hesabı eksiktir; çünkü 229 PONS'luk bakiye aradaki iki işlemle iki kez ağırlıklı ortalamaya uğramıştır.
- **Eksiksiz Kronolojik Ağırlıklı Maliyet Türetimi:**
  1. **Aşama 1 (Trade T-01):** 13 Ekim 12:35 UTC'de 457 PONS @ 0.2882 alındı. TP1 ile 228 satıldı; geriye **229 PONS @ 0.2882** kaldı.
  2. **Aşama 2 (Trade T-08):** 13 Ekim 19:10:03 UTC'de 590 PONS @ 0.3053 alındı (OrderId: `a394b40c-1e79-4373-9338-5bad52ec15f9`).
     $$\text{Blended Entry 1} = \frac{(229 \times 0.2882) + (590 \times 0.3053)}{819} = \mathbf{0.30051869\ USDT}$$
     *(Borsa closed-pnl kaydı: Order `1fef9171-5567-40dc-84a0-5144846d10f7`, 590 PONS satıldı, avgEntryPrice: `0.30051869`).*
     Satış sonrası kalan 229 PONS'un yeni maliyeti **0.30051869 USDT** oldu.
  3. **Aşama 3 (Trade T-13):** 13 Ekim 22:35:02 UTC'de 815 PONS @ 0.3014 alındı (OrderId: `f8b28ce5-ff05-4768-949d-5fcf38df543d`).
     $$\text{Blended Entry 2} = \frac{(229 \times 0.30051869) + (815 \times 0.3014)}{1044} = \mathbf{0.30120669\ USDT}$$
     *(Borsa closed-pnl kaydı: Order `df9d7871-f632-4d23-9065-34da022340a3`, 815 PONS satıldı, avgEntryPrice: `0.30120669`).*
     Satış sonrası kalan 229 PONS'un yeni maliyeti **0.30120669 USDT** oldu.
  4. **Aşama 4 (Trade T-21 / #16):** 14 Ekim 07:35:02 UTC'de 593 PONS @ 0.3329 alındı (OrderId: `ca8165de-3519-4271-9bef-f8868e2bee37`).
     $$\text{Nihai Blended Entry} = \frac{(229 \times 0.30120669) + (593 \times 0.3329)}{822} = \frac{68.97633201 + 197.4097}{822} = \mathbf{0.32407059855...\ USDT}$$
     Bu değer 7 ondalık basamakta tam olarak **0.3240706 USDT**'dir!
  5. **Kapanışlar:** Saat 07:57:03'te stop emri 593 PONS kapattı (OrderId: `35e78f1f`, Entry: `0.3240706`, PnL: `+4.3044 USDT`). Saat 08:00:02'de rotasyon stopu kalan 229 PONS'u kapattı (OrderId: `bdb1eec4`, Entry: `0.3240706`, PnL: `+1.9102 USDT`).
- **Sonuç:** Borsa closed-pnl kaydındaki `0.3240706` maliyeti, aradaki tüm işlemlerin ağırlıklı maliyet zinciriyle tam olarak uyuşmaktadır.

### Vaka 3 (#12 / #14): Ortak Ortalama Giriş 0.05691 ve Farklı Kapanış Saatleri
- Trade `T-17` (1860 CHIP @ 0.05706) ve Trade `T-19` (2230 CHIP @ 0.05679) peş peşe açılmıştır.
- Borsa toplam $1860 + 2230 = 4090\ CHIP$ short pozisyonunu $\frac{1860 \times 0.05706 + 2230 \times 0.05679}{4090} = \mathbf{0.05691278\ USDT}$ maliyetle birleştirmiştir.
- Stop 1 (`H-S-102949786049-BB`) saat 05:30:57 UTC'de **2230 CHIP** kapatmış; Stop 2 (`H-S-102949786049-BB1`) saat 07:04:02 UTC'de kalan **1860 CHIP**'i kapatmıştır.

### Vaka 4 (#19): İki Adet 1380 CHIP Kapanış ve Net 2.6443 USDT Kâr
- Trade `T-24` (2760 CHIP Sell @ 0.05678, Giriş: `2026-10-14 08:40:02 UTC`).
- 1. Kapanış (TP1): 10:04:28 UTC'de 1380 CHIP Buy @ 0.05546 ile kapatıldı (OrderId: `4c2fe3c1`, Net PnL: `+1.7364 USDT`).
- 2. Kapanış (Trailing Stop): Kalan 1380 CHIP için trailing stop kâr bölgesine (`0.05604`) kilitlendi. 11:33:06 UTC'de fiyat geri çekilerek **1380 CHIP** Buy @ 0.05606 ile kapatıldı (OrderId: `e5daabae`, Net PnL: `+0.9080 USDT`).
- Toplam Net Realize PnL: $1.73640984 + 0.90795444 = \mathbf{+2.64436428\ USDT}$.

---

## 5. KURAL UYGUNLUK MATRİSİ VE KANIT DAYANAKLI SONUÇLAR (REVISED)

27 deploy sonrası mantıksal işlem üzerinde yürütülen **216 kural denetimi**, sabit değerler kullanılmaksızın kanıtlardan dinamik olarak türetilmiştir:

| Kural ID | Değerlendirme Esası | PASS | FAIL | UNVERIFIABLE | NOT_APPLICABLE | Açıklama |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ALLOWLIST` | Hesap geneli tüm emirlerin taranması | **27** | 0 | 0 | 0 | Sadece CHIPUSDT ve PONSUSDT işlem gördü. |
| `LEVERAGE_20X` | Closed PnL ve ortam konfigürasyonu | **26** | 0 | **1** | 0 | Borsa closed PnL kayıtlarında 20x teyit edildi; 1 işlemde doğrudan kayıt yoktu. |
| `ENTRY_TP_SUPPRESSED` | Giriş anı (ilk 3 sn) limit TP kontrolü | **27** | 0 | 0 | 0 | Hiçbir işlemde girişte TP gönderilmedi. |
| `BE_05PCT_PRICE_TRIGGER` | Canlı fiyat akışında +%0.5 geçiş kanıtı | 0 | 0 | **23** | **4** | Sub-second tick verisi olmadığından borsa fiyat geçişi bağımsız doğrulanamıyor (UNVERIFIABLE). |
| `TP1_50PCT_ORIGINAL_QTY` | Orijinal miktarın %50'si (qtyStep floor) | **7** | 0 | 0 | **20** | TP1'e ulaşan 7 işlem tam %50 miktar kapattı; 20 işlem 1R'a ulaşamadı. |
| `CLOSE_SIDE_REDUCE_ONLY` | Order JSON reduceOnly ve ters yön bayrağı | **27** | 0 | 0 | 0 | Emirlerin `reduceOnly: True` ve `side` değerleri JSON üzerinden doğrulandı. |
| `UNBROKEN_STOP_COVERAGE` | Girişten itibaren 5 sn içinde onaylı stop | **27** | 0 | 0 | 0 | İlk stoplar 1-3 saniye içinde borsa tarafından onaylandı. |
| `MULTI_ENTRY_ISOLATION` | Örtüşen zaman aralığı ve borsa pozisyonu | **14** | **13** | 0 | 0 | 13 işlem aynı sembol ve yönde çakışarak tek pozisyonda birleşti (FAIL). |

### Kural Sonuçları İstatistik Özeti:
- **Toplam Denetim Sayısı:** 216
- **PASS:** 155
- **FAIL:** 13 (Tümü borsa tek yönlü modda aynı yönlü pozisyonların birleşmesinden kaynaklanan `MULTI_ENTRY_ISOLATION` ihlalidir).
- **UNVERIFIABLE:** 24 (23 adet BE fiyat eşiği geçiş anı; 1 adet münferit kaldıraç kaydı).
- **NOT_APPLICABLE:** 24 (1R hedefine ulaşamadan kapanan işlemlerin TP1 kuralı).

---

## 6. MODEL, GERÇEK GÖVDE VE ENTEGRASYON TESTLERİNİN AYRIMI

1. **Canlı Borsa ve Çalışma Zamanı Kanıtları:**
   - 27 işlemin emir, execution, closed-pnl ve stop yönetimi Bybit Demo API ve VPS loglarından izlenmiş; tek-yönlü pozisyon birleşmesi (`MULTI_ENTRY_ISOLATION`) **FAIL** olarak tespit edilmiştir.
2. **İzole Sözleşme Testleri (Offline Mock Suite — 10/10 PASS):**
   - Üretim fonksiyonları borsaya emir göndermeden izole harness altında test edilmiştir:
     * `test_01_be_threshold_boundaries`: PASS
     * `test_02_be_and_tp1_same_tick`: PASS
     * `test_03_repeating_ticker_reconnect_duplicate_guard`: PASS
     * `test_04_tp1_partial_fill_accounting`: PASS
     * `test_05_tp1_and_sl_race_protection`: PASS
     * `test_06_close_side_inversion_contract`: PASS
     * `test_07_qtystep_rounding`: PASS
     * `test_08_second_entry_same_symbol_side_independent_tracking`: PASS (Botun hafıza mantığı)
     * `test_09_state_recovery_untrusted_baseline_no_artificial_r`: PASS
     * `test_10_trailing_ratchet_beyond_2r`: PASS
3. **Test Edilmeyen / Doğrulanamayan Alanlar:**
   - Canlı ortamda sub-second tick düzeyinde +%0.5 fiyat geçiş anı ve 100ms gecikme tespiti bağımsız borsa tick verisi bulunmadığından **UNVERIFIABLE** bırakılmış, yapay olarak PASS verilmemiştir.

---

## 7. ANOMALİLER VE RİSKLER (REVISED)

1. **ANOMALY-01 (Yüksek Şiddet): Bybit One-Way Mode Multi-Entry Pozisyon Birleşmesi**
   - Bot aynı sembol ve yöndeki pozisyonları bellekte bağımsız saklarken, Bybit tek-yönlü modda (`positionIdx=0`) pozisyonları ve maliyetleri tek havuzda birleştirmektedir.
   - **Hedge Mode Düzeltmesi:** Hedge Mode aynı yöndeki parent'ları ayırmaz; bu nedenle Hedge Mode bu mimari empedans uyuşmazlığına çözüm değildir.
2. **ANOMALY-02 (Yüksek Şiddet): İkinci Giriş Stopunun Önceki İşlem Kalıntısını Yutması (Case #7)**
   - İkinci işlemin `closeOnTrigger: True` olan stop emri tetiklendiğinde borsa pozisyonunun tamamını kapatmakta ve önceki işlemin kalan miktarını yutmaktadır. Bot borsa pozisyonu sıfırlandığı için acil sentetik kapanış (`SYNTH_FLAT`) üretmektedir.
3. **ANOMALY-03 (Orta Şiddet): Stop İptal-Yenileme Arasındaki Korumasız Aralık**
   - Stop miktarı güncellenirken iptal ile yeni emrin kabulü arasında 150-400 ms'lik korumasız ağ gecikmesi aralığı bulunmaktadır.
4. **ANOMALY-04 (Düşük Şiddet): Execution Akışında Funding Kayıtları**
   - Bybit `/v5/execution/list` 8 saatlik fonlama ödemelerini `execType="Funding"` olarak döndürmektedir; trade hesaplamalarında filtrelenmelidir.

---

## 8. AYRI DÜZELTME VE İYİLEŞTİRME ÖNERİLERİ LİSTESİ (UYGULANMAMIŞTIR)

Canlı sisteme dokunulmamış olup, ileride yapılacak geliştirmeler için öneriler aşağıdadır:

1. **Sembol ve Yön Bazında Concurrency Mutex (Kritik):**
   - Bybit tek-yönlü modda çalışırken, aynı sembol ve yönde açık bir işlem (veya TP1 sonrası kalıntısı) tamamen kapanmadan yeni bir giriş sinyali kabul edilmemeli, reddedilmeli veya kuyruğa alınmalıdır.
2. **Alt Hesap (Subaccount) Mimarisi (Çoklu Giriş İsteniyorsa):**
   - Aynı sembol ve yönde bağımsız eşzamanlı işlemler yürütülmek isteniyorsa, her mantıksal işlem Bybit üzerinde ayrı bir alt hesaba (subaccount) yönlendirilmelidir.
3. **Stop Güncellemelerinde Amend Kullanımı:**
   - TP1 sonrası kalan miktar için stop güncellenirken Bybit `/v5/order/amend` endpoint'i kullanılmalı, iptal-yenileme kaynaklı korumasız aralık ortadan kaldırılmalıdır.
4. **Git ve Deployed Senkronizasyonu:**
   - VPS'te çalışan uncommitted dirty sürüm, yerel git geçmişinde açık ve şeffaf bir commit ile sabitlenmeli ve branch HEAD ile eşitlenmelidir.

---

## 9. DENETİM ARTEFAKTLARI DİZİNİ

- [summary.md](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/summary.md): Bu kapsamlı revize denetim raporu.
- [checks.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/checks.csv): 216 dinamik kural denetimi (PASS: 155, UNVERIFIABLE: 24, FAIL: 13, NOT_APPLICABLE: 24).
- [logical_trades.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/logical_trades.csv): 27 mantıksal işlemin yaşam döngüsü ve aggregate kapanış etiketleri.
- [exchange_position_ledger.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/exchange_position_ledger.csv): Borsa pozisyon ve net PnL defteri.
- [order_execution_map.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/order_execution_map.csv): Gerçek borsa reduceOnly bayraklarını içeren 64 emir kaydı.
- [timeline.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/timeline.csv): UTC kronolojik olay akışı.
- [anomalies.json](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/anomalies.json): Yapısal anomali detayları.
- [raw_api/](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/raw_api): Sanitized ham API JSON dosyaları.
- [environment_snapshot.json](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/evidence/environment_snapshot.json): Dirty diff ve commit hash ortam kanıtı.
- [inspect_pons_math.py](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/scripts/inspect_pons_math.py): PONSUSDT 0.3240706 çok aşamalı maliyet türetme scripti.
