# Hummingbot / Bybit Demo Stratejisi Bağımsız Uygunluk Denetim Raporu (Nihai Revizyon)

**Denetim Tarihi:** 2026-10-14T12:05:06Z (15:05:06 TSI)  
**Denetim Kapsamı:** Deploy Sonrası Canlı İşlem Sözleşmesi Uygunluğu, Çalışma Ortamı Doğrulaması ve Borsa Muhasebesi  
**Hedef Sistem:** Hummingbot VPS Docker Konteyneri (`hummingbot`) / Bybit Demo Linear API (`https://api-demo.bybit.com`)  
**Hesap UID:** `574252146`  
**Denetçi Statüsü:** Bağımsız Denetçi (Salt Okunur / Read-Only Audit — Canlı bot dosyalarına, emirlerine, giriş politikasına veya konfigürasyonuna dokunulmamıştır)

---

## 1. YÖNETİCİ ÖZETİ VE DOĞRULANAN ÇALIŞMA ORTAMI

Canlı bot durdurulmadan ve konfigürasyonu değiştirilmeden çalışan container ve repo durumu kriptografik olarak sabitlenmiştir:

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
8. **TP1 Miktarı:** Pozisyonun kalan miktarının değil, **orijinal giriş miktarının %50'sidir** (`qtyStep` floor yuvarlama ile; CHIP için 10, PONS için 1).
9. **Trailing Stop:** Fiyat **2R eşiğini** aştığında devreye girer; tepe fiyatla birlikte kârı kilitleyerek tek yönlü (monotonik) ilerler.
10. **Eşzamanlı Giriş ve Pozisyon İzolasyonu:**
    - Bot hafızada bağımsız iki obje olarak saklasa da, Bybit One-Way modunda (`positionIdx=0`) aynı yöndeki tüm girişleri tek bir havuzda birleştirir ve ağırlıklı ortalama maliyet oluşturur.
    - **Hedge Mode Sınırı:** Bybit Hedge modu yalnızca Long (`positionIdx=1`) ile Short (`positionIdx=2`) bacaklarını ayırır; **aynı yöndeki iki Long veya iki Short pozisyonunu AYIRMAZ**.

---

## 3. BORSA MUHASEBESİ, FEE/PNL VE LOOKBACK ANALİZİ

### 3.1. Ücret ve PnL Muhasebe Anlamı
Bybit V5 `/v5/position/closed-pnl` endpoint'indeki alanların muhasebe anlamı doğrulanmıştır:
- `cumEntryValue`: Toplam giriş değeri ($Qty \times avgEntryPrice$).
- `cumExitValue`: Toplam çıkış değeri ($Qty \times avgExitPrice$).
- `openFee`: Giriş anında ödenen borsa komisyonu.
- `closeFee`: Kapanış anında ödenen borsa komisyonu.
- `closedPnl`: Gerçekleşen net kâr/zarar tutarı.
  $$\text{closedPnl} = (\text{cumExitValue} - \text{cumEntryValue}) \times \text{direction} - \text{openFee} - \text{closeFee}$$
- **Kritik Doğrulama:** Bybit'in `closedPnl` alanı **açılış ve kapanış komisyonlarını ZATEN DÜŞMÜŞTÜR (NET TUTAR)**. Dolayısıyla pozisyon nakit akışı hesaplanırken `closedPnl` üzerinden `closeFee` bir kez daha düşülmemelidir.

### 3.2. Deploy Öncesi Başlangıç Durumu (Lookback Analizi)
- Lookback aralığı `2026-10-12T00:00:00Z` ile deploy anı `2026-10-13T11:35:47Z` arasında çalıştırılmıştır.
- **CHIPUSDT ve PONSUSDT:** Deploy anından önce hesapta hiçbir CHIP veya PONS işlemi bulunmamaktadır. Her iki sembolün de başlangıç pozisyonu **tam olarak 0 (FLAT)** durumundadır.
- **Diğer Semboller:** `2026-10-12` öncesinden kalan geçmiş ZAMAUSDT pozisyonu lookback penceresi başında açık kalmıştır; ancak lookback başlangıcı öncesi veriler bilinmediğinden başlangıç bakiye durumu `EKSİK KANIT (LOOKBACK ÖNCESİ BİLİNMİYOR)` olarak işaretlenmiştir.
- **Funding settlements:** `/v5/execution/list` endpoint'inde yer alan 8 saatlik `execType == "Funding"` kayıtları (10 adet) trade emirlerinden (75 adet) izole edilmiştir.

---

## 4. ÖZEL İNCELEME BULGULARI VE KÖK NEDEN KANITLARI

### 4.1. Vaka #7 (T-12): 5020 CHIP Stop Kapanışının Gerçek Request/Response/CID Kök Nedeni
- **İlgili İşlem:** Trade `T-12` (Ebeveyn ID: `896351516234`, Giriş: `2026-10-13 22:00:23 UTC`, 6870 CHIP Sell @ 0.05737).
- **Emir Kimlikleri:** OrderId: `3ba934f0-1bff-4a0a-90dd-6bbc01c4ad12`, CID: `H-S-896351516234-BB`.
- **Kök Neden Akışı (Kod, Log ve API Kanıtlarıyla):**
  1. **İlk Stop Oluşturma (22:00:26 UTC):** Bot `_place_bybit_trading_stop` üzerinden Bybit `v5/order/create` endpoint'ine şu gövdeyi iletti:
     - `orderLinkId: H-S-896351516234-BB`
     - `qty: "6870"`, `triggerPrice: "0.05790"`, `closeOnTrigger: True`, `reduceOnly: True`
     - Borsa `orderId: 3ba934f0-1bff-4a0a-90dd-6bbc01c4ad12` oluşturdu.
     *(Log kanıtı: `22:00:26,045 - ✅ [BYBIT COND SL] CHIP-USDT SHORT @ 0.05790 qty=6870`).*
  2. **Break-Even Güncellemesi (22:11:41 UTC):** Fiyat kâra geçince bot `_hybrid_apply_05_be` çağrısı yaptı. CID duplicate olduğundan kod `_amend_bybit_conditional_order` (Bybit `v5/order/amend`) çağırarak **yalnızca triggerPrice'ı 0.05737 seviyesine güncelledi**. Miktar bu sırada henüz TP1 gerçekleşmediği için 6870 olarak kaldı.
     *(Log kanıtı: `22:11:41,380 - 🛡️ [HYBRID +0.5% BE] CHIP-USDT SHORT #896351516234 SL -> entry (0.05737) doğrulandı`).*
  3. **TP1 Dolumu ve Eksik Miktar Güncellemesi (22:18:33 UTC):** TP1 market emri `d1b48200-c246-4320-b553-1125fc0de723` (CID: `HTP18963515162341791929913426`) ile 3430 CHIP kapattı. Ancak **bot borsadaki stop emrinin miktarını kalan 3440 CHIP'e revize eden bir amend çağrısı göndermedi**. Stop emri Bybit üzerinde `qty: 6870` ve `closeOnTrigger: True` bayrağıyla beklemeye devam etti.
  4. **Borsa Tarafı Clamping (22:36:36 UTC):** Fiyat 0.05737'ye gerilediğinde stop tetiklendi. O anda borsa tek yönlü pozisyonunda:
     $$\text{Açık Pozisyon} = 1580 \text{ (T-05 kalıntısı)} + 3440 \text{ (T-12 kalıntısı)} = \mathbf{5020\ CHIP}$$
     bulunmaktaydı. Bybit eşleştirme motoru `closeOnTrigger: True` kuralları gereği, 6870'lik emri mevcut açık pozisyon boyutu olan **5020 CHIP'e otomatik daralttı (clamped)** ve 5020 CHIP tek seferde kapandı.
  5. **Aggregate Karar Değil, Reaktif Temizlik:** Bot 5020 CHIP kapama kararı almamıştır. Borsa emri 5020 doldurup pozisyonu sıfırlayınca (`size=0`), bot reaktif olarak önceki trade'in (`#18400454197`) 1580'lik stopunu iptal etmiş ve sentetik flat kaydı (`SYNTH_FLAT_18400454197`) oluşturmuştur.

### 4.2. Vaka #16 (T-21): Çok Aşamalı Ağırlıklı Giriş Hesabı (0.3240706 USDT İspatı)
229 PONS'luk kalıntı aradaki işlemlerle peş peşe ağırlıklı maliyet güncellemesine uğramıştır:
1. **Aşama 1 (Trade T-01):** 457 PONS @ 0.2882 alındı. TP1 ile 228 satıldı; geriye **229 PONS @ 0.2882** kaldı.
2. **Aşama 2 (Trade T-08 - 19:10:03 UTC):** 590 PONS @ 0.3053 alındı (OrderId: `a394b40c`).
   $$\text{Ağırlıklı Ortalama 1} = \frac{(229 \times 0.2882) + (590 \times 0.3053)}{819} = \mathbf{0.30051869\ USDT}$$
   *(Bybit closed PnL Order `1fef9171-5567-40dc-84a0-5144846d10f7` bu fiyattan 590 kapattı).* Kalan 229 PONS'un maliyeti **0.30051869 USDT** oldu.
3. **Aşama 3 (Trade T-13 - 22:35:02 UTC):** 815 PONS @ 0.3014 alındı (OrderId: `f8b28ce5`).
   $$\text{Ağırlıklı Ortalama 2} = \frac{(229 \times 0.30051869) + (815 \times 0.3014)}{1044} = \mathbf{0.30120669\ USDT}$$
   *(Bybit closed PnL Order `df9d7871-f632-4d23-9065-34da022340a3` bu fiyattan 815 kapattı).* Kalan 229 PONS'un maliyeti **0.30120669 USDT** oldu.
4. **Aşama 4 (Trade T-21 / #16 - 07:35:02 UTC):** 593 PONS @ 0.3329 alındı (OrderId: `ca8165de`).
   $$\text{Nihai Ağırlıklı Ortalama} = \frac{(229 \times 0.30120669) + (593 \times 0.3329)}{822} = \frac{68.97633201 + 197.4097}{822} = \mathbf{0.32407059855...\ USDT}$$
   Bu değer Bybit kapalı PnL kayıtlarında (Order `35e78f1f` ve `bdb1eec4`) görülen **0.3240706 USDT** ile 7 ondalık basamakta birebir eşleşmektedir.

### 4.3. Vaka #12 / #14: Ortak Ortalama Giriş 0.05691 ve Farklı Kapanış Saatleri
- Trade `T-17` (1860 CHIP @ 0.05706) ve Trade `T-19` (2230 CHIP @ 0.05679) peş peşe açılmıştır.
- Borsa toplam $1860 + 2230 = 4090\ CHIP$ short pozisyonunu $\frac{1860 \times 0.05706 + 2230 \times 0.05679}{4090} = \mathbf{0.05691278\ USDT}$ maliyetle birleştirmiştir.
- Stop 1 (`H-S-102949786049-BB`) saat 05:30:57 UTC'de **2230 CHIP** kapatmış; Stop 2 (`H-S-102949786049-BB1`) saat 07:04:02 UTC'de kalan **1860 CHIP**'i kapatmıştır.

### 4.4. Vaka #19: İki Adet 1380 CHIP Kapanış ve Net 2.6443 USDT Kâr
- Trade `T-24` (2760 CHIP Sell @ 0.05678, Giriş: `2026-10-14 08:40:02 UTC`).
- 1. Kapanış (TP1): 10:04:28 UTC'de 1380 CHIP Buy @ 0.05546 ile kapatıldı (OrderId: `4c2fe3c1`, Net PnL: `+1.7364 USDT`).
- 2. Kapanış (Trailing Stop): Kalan 1380 CHIP için trailing stop kâr bölgesine (`0.05604`) kilitlendi. 11:33:06 UTC'de fiyat geri çekilerek **1380 CHIP** Buy @ 0.05606 ile kapatıldı (OrderId: `e5daabae`, Net PnL: `+0.9080 USDT`).
- Toplam Net Realize PnL: $1.73640984 + 0.90795444 = \mathbf{+2.64436428\ USDT}$.

---

## 5. AYRIŞTIRILMIŞ KURAL DENETİM TABLOSU (CHECKS.CSV)

27 deploy sonrası mantıksal işlem üzerinde overlap, stop bütünlüğü ve koruma sürekliliği ayrıştırılarak **270 kural denetimi** yapılmıştır:

| Kural ID | Değerlendirme Esası | PASS | FAIL | UNVERIFIABLE | NOT_APPLICABLE | Açıklama |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ALLOWLIST` | Tüm hesap emirleri (500+ sembol taraması) | **27** | 0 | 0 | 0 | Sadece CHIPUSDT ve PONSUSDT işlem gördü. |
| `LEVERAGE_20X` | Kapalı PnL ve ortam snapshot kayıtları | **26** | 0 | **1** | 0 | Borsa kapalı PnL kayıtlarında 20x teyit edildi; 1 işlemde doğrudan kayıt yoktu. |
| `ENTRY_TP_SUPPRESSED` | Giriş anı (ilk 3 sn) limit TP emri kontrolü | **27** | 0 | 0 | 0 | Hiçbir işlemde girişte TP gönderilmedi. |
| `BE_05PCT_PRICE_TRIGGER` | Canlı fiyat akışında +%0.5 geçiş kanıtı | 0 | 0 | **23** | **4** | Sub-second tick verisi olmadığından borsa fiyat geçiş anı bağımsız doğrulanamıyor. |
| `TP1_50PCT_ORIGINAL_QTY` | 1R dolumunda tam %50 miktar (qtyStep floor) | **7** | 0 | 0 | **20** | TP1'e ulaşan 7 işlem tam %50 miktar kapattı; 20 işlem 1R'a ulaşamadı. |
| `CLOSE_SIDE_REDUCE_ONLY` | Ham borsa order JSON `reduceOnly: True` bayrağı | **27** | 0 | 0 | 0 | Emirlerin `reduceOnly: True` ve `side` değerleri JSON üzerinden doğrulandı. |
| `INITIAL_STOP_PLACEMENT` | Giriş sonrası 5 sn içinde onaylı stop varlığı | **27** | 0 | 0 | 0 | İlk stoplar 1-3 saniye içinde borsa tarafından onaylandı. |
| `UNBROKEN_STOP_COVERAGE` | Cancel/replace arası mikrosaniye koruma kanıtı | 0 | 0 | **27** | 0 | Borsa içi telemetri olmadan korumasız ağ gecikmesi aralığı bağımsız kanıtlanamaz. |
| `CONCURRENT_OVERLAP` | Runner ömrüyle örtüşen zaman aralığı | **14** | **13** | 0 | 0 | 13 işlem aynı sembol ve yönde açık bir runner varken açıldı (Örtüşme durumu). |
| `PARENT_STOP_AMOUNT_INTEGRITY`| Stop emrinin parent miktarını aşmaması / yamyamlık | **25** | **2** | 0 | 0 | T-12 stopu 5020 kapattı (FAIL), T-05 stopu iptal edilip yutuldu (FAIL). |

### Kural Sonuçları İstatistik Özeti:
- **Toplam Denetim Sayısı:** 270
- **PASS:** 179
- **UNVERIFIABLE:** 51 (23 BE fiyat eşiği geçiş anı; 27 kesintisiz koruma sürekliliği; 1 münferit kaldıraç kaydı).
- **FAIL:** 15 (13 adet eşzamanlı aktif runner örtüşmesi `CONCURRENT_OVERLAP`; 2 adet parent stop miktar bütünlüğü ihlali `PARENT_STOP_AMOUNT_INTEGRITY`).
- **NOT_APPLICABLE:** 25 (1R hedefine ulaşamadan kapanan işlemlerin TP1 kuralı).

---

## 6. GERÇEK ÇALIŞMA SÜRELERİ (RUNNER LIFETIMES)

İlk TP1 dolum anı tam kapanış sayılmamış; açık kalan %50 runner'ın borsa üzerindeki gerçek ömrü hesaplanmıştır:
- **Trade T-01:** Giriş: `2026-10-13 12:35:04` -> Çıkış: `2026-10-14 08:03:09 UTC` (**1168.1 dakika / 19.5 saat açık kaldı**).
- **Trade T-05:** Giriş: `2026-10-13 14:35:03` -> Çıkış: `2026-10-13 22:36:38 UTC` (**481.6 dakika / 8.0 saat açık kaldı**).
- **Trade T-17:** Giriş: `2026-10-14 04:25:05` -> Çıkış: `2026-10-14 07:04:05 UTC` (**159.0 dakika açık kaldı**).
- **Trade T-24:** Giriş: `2026-10-14 08:40:02` -> Çıkış: `2026-10-14 11:33:06 UTC` (**173.1 dakika açık kaldı**).

---

## 7. AYRI DÜZELTME VE İYİLEŞTİRME ÖNERİLERİ LİSTESİ (KOD DEĞİŞTİRİLMEDEN)

Canlı sisteme dokunulmamış olup, operasyonel güvenlik için şu adımlar önerilmektedir:
1. **Sembol/Yön Bazında Concurrency Mutex (Kritik):**
   - Bybit tek yönlü modda (`positionIdx=0`) çalıştığı sürece, açık bir pozisyon (veya TP1 sonrası kalan yarısı) tamamen kapanmadan aynı sembol ve yönde yeni bir giriş sinyali kabul edilmemeli, reddedilmeli veya kuyrukta bekletilmelidir.
2. **TP1 Sonrası Stop Miktarının Açıkça Revize Edilmesi:**
   - TP1 piyasa emri dolduğunda, borsada bekleyen stop emri derhal Bybit `v5/order/amend` çağrısıyla kalan net miktara (örn. 3440 CHIP) revize edilmeli; borsa clamping mekanizmasına bırakılmamalıdır.
3. **Alt Hesap (Subaccount) Mimarisi (Çoklu Giriş İsteniyorsa):**
   - Aynı sembol ve yönde bağımsız eşzamanlı işlemler yürütülmek isteniyorsa, Hedge Mode aynı yönlü pozisyonları ayırmadığından her mantıksal işlem Bybit üzerinde bağımsız bir alt hesaba yönlendirilmelidir.
4. **Git ve Container Sürüm Eşitlemesi:**
   - VPS'te çalışan commit edilmemiş dirty sürüm (+3498 satır), repo üzerinde şeffaf bir commit ile kayıt altına alınmalı ve branch HEAD ile eşitlenmelidir.

---

## 8. DENETİM ARTEFAKTLARI VE KANIT DOSYALARI

Tüm denetim çıktıları ve doğrulanabilir tablolar [audit_20261014](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014) dizinine yazılmıştır:
- [summary.md](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/summary.md): Bu kapsamlı nihai denetim raporu.
- [checks.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/checks.csv): 270 dinamik kural denetimi (PASS: 179, UNVERIFIABLE: 51, FAIL: 15, NOT_APPLICABLE: 25).
- [logical_trades.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/logical_trades.csv): 27 mantıksal işlemin tam yaşam döngüsü ve aggregate kapanış etiketleri.
- [exchange_position_ledger.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/exchange_position_ledger.csv): Borsa pozisyon ve net nakit akış defteri.
- [order_execution_map.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/order_execution_map.csv): Borsa `reduceOnly` değerlerini içeren 64 emir eşleme kaydı.
- [timeline.csv](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/timeline.csv): UTC kronolojik olay akışı.
- [anomalies.json](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/anomalies.json): Yapısal anomali ve kök neden detayları.
- [compute_true_lifetimes.py](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/scripts/compute_true_lifetimes.py): Runner ömrüyle gerçek işlem süresi hesaplama scripti.
- [inspect_pons_math.py](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/scripts/inspect_pons_math.py): PONS 0.3240706 USDT 4 aşamalı ağırlıklı maliyet doğrulama scripti.
- [raw_api/](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/raw_api): Sanitized, 906 sembolü kapsayan ham API JSON yanıtları.
- [environment_snapshot.json](file:///c:/Users/bu_da/hummingbot-ooem-patch/audit_20261014/evidence/environment_snapshot.json): Deployed hash ve dirty çalışma ağacı kanıtı.
