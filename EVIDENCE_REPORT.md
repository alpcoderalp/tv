# Adli Borsa ve Bot İcra Analiz Raporu & Kanıt Paketi (v2.0)
**Referans Dönemi:** `2026-10-23 09:31:39 UTC` — `2026-10-28 13:00:00 UTC`  
**İncelenen Kohort:** Kesim damgasından sonra açılan **113 Parent Pozisyon**, **173 Borsa Kapanış Kaydı**  
**Çalışan Temel Kod Sürümü:** `51F6CDD4` (`candidate_hybrid_v2_51F6CDD4.py`)  
**SHA-256:** `51f6cdd4c38b680a33273aabdd974120a318a9f6e340504024f4b8d02819f637`  
**Depo / Repo:** `https://github.com/alpcoderalp/tv`  

---

## Yönetici Özeti ve Temel İlke

Bu rapor, Hummingbot TV Sinyal Stratejisi altındaki canlı işlem kayıtlarını, Bybit demo borsa icra (execution) verilerini ve VPS loglarını inceleyen bağımsız adli kanıt paketidir.

> **Kabul ve Doğrulama İlkesi:**  
> Yazılım düzeltmelerinin kabulü, varsayımsal bir kâr simülasyonuna veya "+X USDT kaçırıldı" iddialarına değil; **kesin borsa execution muhasebesine**, **kardeş pozisyonları tasfiye eden yetim (orphan) emirlerin önlenmesine** ve **gerçek kod yollarındaki regresyonların giderilmesine** dayanmalıdır.  
> Daha önceki taslaklarda yer alan `+7.5998 USDT` replay kâr farkı iddiası; borsa komisyonlarının ihmal edilmesi, yapay 4 saatlik çıkış varsayımı (`TIMEOUT_4H`) ve ters SHORT 3R koşulu içerdiği için **geçersiz kılınmış ve geri çekilmiştir**.

---

## 1. Kohort ve Kapanış PnL Mutabakatı (+12.1326 / +8.9941 USDT)

Bybit V5 Perpetual API'sinden çekilen `recent_closed_pnl.json` kayıtlarının tam mutabakatı:

1. **Ham Bybit API Kayıtları (`updatedTime >= 2026-10-23 09:31:39 UTC`):**
   * Toplam **176 kapanış kaydı** $\rightarrow$ **`+12.132616 USDT`**.
2. **Kesim Öncesi Pozisyonların Kapanışları:**
   * Kesim zamanından önce (09:15 ve 09:30 UTC'de) açılmış 2 parent pozisyona ait 3 bacak, kesimden sonra kapanmıştır:
     * `661706686159` (PONS LONG): TP1 Kapanışı `11:28:21 UTC` (`#91613cc0`) $\rightarrow$ **`+1.618341 USDT`**
     * `513350689420` (CHIP SHORT):
       * TP1 Kapanışı `14:16:36 UTC` (`#70b4e92e`) $\rightarrow$ **`+1.674826 USDT`**
       * SL Kapanışı `14:57:36 UTC` (`#30615015`) $\rightarrow$ **`-0.154680 USDT`**
     * **Kesim Öncesi Kapanışlar Toplamı:** $1.618341 + 1.674826 - 0.154680 = \mathbf{+3.138487\text{ USDT}}$ (3 kayıt).
3. **Kesim Anından İtibaren Açılan Tam Kohort PnL:**
   $$\text{Kohort Net Gerçekleşen PnL} = 12.132616 - 3.138487 = \mathbf{+8.994129\text{ USDT}}$$
   * **Parent Pozisyon Sayısı:** **113 adet** (22 Ekim log rotasyonu dahil).
   * **Kohort Kapanış Kaydı:** **173 adet**.
   * **Eşleşme Oranı:** **%100 (173 / 173 kayıt eksiksiz eşleştirilmiştir; sapma 0.000000 USDT'dir).**

Tüm 173 kapanış kaydı kaynak `orderId`, `execId`, miktar, komisyon ve fiziksel hedef parent pozisyonuyla [`execution_allocation_ledger.csv`](execution_allocation_ledger.csv) dosyasına işlenmiştir.

---

## 2. BB1 / BB2 Yetim Emirlerinin Denetimi ve Sibling Tasfiye Mekanizması

Borsa emir veri tabanında tespit edilen toplam **20 yetim stop emri** (`-BB1` ve `-BB2`) incelenmiştir:
* **Kesim Öncesi:** 1 adet (`#4b28dac1`, 01:37 UTC)
* **Kohort İçi Toplam:** 19 adet (17 BB1 + 2 BB2)
  * **İptal Edilen:** 1 adet (`#43f4ac4f`, pozisyon kapanışında Bybit tarafından iptal edildi)
  * **Borsada Dolan:** **18 adet** (16 BB1 + 2 BB2)

### Kök Neden Analizi:
18 vakanın tamamında, parent pozisyonun orijinal `-BB` stop emri Bybit üzerinde **fiilen dolduktan 10.3 saniye ile 422.3 saniye (ve bir vakada 2.5 saat) SONRA** yetim stop emri üretilmiştir.
* **Meşru Residual Stop:** **0 adet (%0)**.
* **Kusurlu Yetim (Orphan) Stop:** **18 adet (%100)**.
WebSocket `execution` bildirimlerinin gecikmesi veya atlanması nedeniyle bot, borsa pozisyonunu sorguladığında stop emrini görememiş ve "stop kayıp" varsayarak yeni bir koşullu emir göndermiştir.

### Kardeş (Sibling) Pozisyon Tasfiyeleri:
Borsada pozisyon hesap düzeyinde tutulduğu için (tek bir net long veya short), dolan 18 yetim stop emri şu fiziksel etkiyi doğurmuştur:
1. **Sibling Pozisyon Tasfiyesi (13 icra):** Orijinal parent zaten kapalı olduğundan, borsadaki açık kardeş parent pozisyonlarının sözleşmelerini erken kapatmıştır:
   * `9f6223df` (BB1, 6600 qty) + `94a946ba` (BB2, 640 qty) $\rightarrow$ Parent `41272473399`'un 7240 sözleşmesini tamamen tasfiye etti (-0.7476 USDT).
   * `588f5fbc` (BB1, 4440 qty) $\rightarrow$ Parent `847413379694`'ü kapattı (+2.0075 USDT).
   * `5f39ce0a` (BB1, 3860 qty) $\rightarrow$ Parent `666412677548`'i kapattı (-0.7642 USDT).
   * `2047e993` (BB1, 2810 qty) $\rightarrow$ Parent `182962647145`'i kapattı (-0.2471 USDT).
   * `9f0ab105` (BB1, 1120 qty) $\rightarrow$ Parent `12871875846`'yı kapattı (+1.3530 USDT).
   * `7121817e` (BB1, 227 qty) $\rightarrow$ Parent `344083910534`'ü kapattı (-0.9233 USDT).
   * `d9ff0af7` (BB1, 342 qty) $\rightarrow$ Parent `780262343342`'yi kapattı (-0.4222 USDT).
   * `b5264eff` (831 qty) + `029c2b44` (264 qty) $\rightarrow$ Parent `331357774828`'i kapattı (-0.4999 USDT).
   * `bbf2a567` (BB1, 651 qty) $\rightarrow$ Parent `333431666630` (326 qty) ve `113923637725` (325 qty)'i kapattı.
   * `8a60827d` (BB1, 238 qty) $\rightarrow$ Parent `123356490277`'yi kapattı.
   * `76e2690e` (BB1, 449 qty) $\rightarrow$ Parent `225276516407`'yi kapattı.
2. **Kendi Residual'ını Kapatma (5 icra):** Orijinal parent'ın kalan lingering sözleşmelerini kapatmıştır (`4ad13e25`, `04a70588`, `e878da91`, `7305c638`, `2c714a30`).

Bu durum, botun loglarında `📁 [POSITION_FLAT CLOSE ARCHIVED]` şeklinde yapay 0.00 veya tahmini PnL ile arşivlenen **7 parent pozisyonunun sırrını kesin olarak çözmüştür**. Bu pozisyonların gerçek PnL'i sıfır değil, borsa tarafında onları tasfiye eden yetim emirlerin gerçekleşen PnL'idir!

Tüm detaylar [`bb1_impact.csv`](bb1_impact.csv) dosyasında mevcuttur.

---

## 3. 9.266 Retry Analizi ve Quantize Doğrulama Kusuru

1. **Sayı ve Dağılım:** Loglarda 5 gün boyunca toplam **9.266 adet** `[HYBRID TRAIL 2R RETRY]` uyarısı kaydedilmiştir. Bu döngü tek bir pozisyondan değil, **21 farklı parent pozisyondan** kaynaklanmıştır.
2. **Throttle Tutarlılığı:**
   * Bot içindeki `3.0s` throttle mantığı kusursuz çalışmıştır.
   * Ortalama retry aralığı **3.45 – 3.52 saniye** olarak ölçülmüştür (`3.0s` throttle + Bybit REST API round-trip gecikmesi).
   * Örnek `#808409635108`: 139.2 dakika boyunca 2.520 retry, ortalama 3.32s aralık.
   * Örnek `#885285766398`: 31.4 dakika boyunca 539 retry, ortalama 3.50s aralık.
3. **Borsa vs Bot Ayrımı (Quantize Defect):**
   * **Borsada Stop İlerledi mi?:** **EVET.** Bybit `v5/order/amend` isteklerini 200 OK ile kabul etmiş ve stop fiyatını tick size'a quantize ederek (`0.05393`) borsada fiilen güncellemiştir.
   * **Bot Neden Döngüye Girdi?:** Botun doğrulayıcısı (`_hybrid_verify_bybit_sl_order`, satır 27338), ham float hesaplama sonucunu (`target_sl = 0.05393492`) borsadan dönen quantize fiyatla (`f_price = 0.05393`) şu mantıkla kıyaslamıştır:
     ```python
     if f_price < target_sl - 1e-6:  # 0.05393 < 0.05393392 -> TRUE!
         return None  # Doğrulama başarısız!
     ```
     Bu kontrol `True` döndüğü için bot, borsadaki stopun hedefe ulaştığını **doğrulayamamış**, state'i güncellememiş ve 3.5 saniye sonra aynı emri borsaya tekrar göndermiştir.
   * Tüm zaman çizelgesi [`retry_timeline.csv`](retry_timeline.csv) dosyasındadır.

---

## 4. Replay Simülasyonu ve Duyarlılık Analizi

Replay simülasyonu, kullanıcının uyarısı doğrultusunda **yapay 4 saatlik çıkıştan arındırılmış**, gerçek **MarkPrice tetikleme** referansı, Bybit komisyon çizelgesi (taker %0.055, TP1 maker %0.020) ve düzeltilmiş SHORT 3R koşulu ile yeniden koşturulmuştur:

### Replay Sonuçları Matrisi:

| Senaryo / Varyant | TP1 Sayısı | Brüt PnL (USDT) | Komisyon (USDT) | Net PnL (USDT) | Not |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Fiili Borsa İcrası (Mevcut Bot)** | **62 / 113** | **+40.92** | **-31.93** | **`+8.9941`** | **Gerçekleşen fiziksel sonuç** |
| **Saf Replay [Kötümser - SL Önce]** | 63 / 113 | +6.92 | -31.93 | **`-25.0128`** | Zaman kısıtı yok; intra-bar SL öncelikli |
| **Saf Replay [İyimser - TP1 Önce]** | 63 / 113 | +7.10 | -31.93 | **`-24.8324`** | Zaman kısıtı yok; intra-bar TP1 öncelikli |
| *Duyarlılık Varyantı: 4h Çıkış (Kötümser)* | 55 / 113 | -15.40 | -32.13 | **`-47.5316`** | 240 bar sonunda zorunlu market çıkışı |

### Çıkarılan Temel Adli Sonuçlar:
1. **+7.5998 USDT İddiasının Çöküşü:** Önceki taslakta yer alan kâr artışı iddiası, komisyonların (`~32 USDT`) düşülmemesinden ve yapay 4 saatlik çıkış varsayımından kaynaklanan bir simülasyon yanılgısıdır.
2. **Kripto Testere Piyasasında (Chop) Zaman Çıkışsız Strateji:** Strateji kuralları gereği 4 saatlik bir zaman çıkışı **kodda mevcut değildir**. Kalan %50 pozisyon bir zaman sınırı olmadan açık tutulduğunda, piyasa dalgalanmaları uzun vadede neredeyse tüm pozisyonları başa-baş (BE) veya stop seviyesinde durdurmakta ve işlem masrafları net sonucu negatif yapmaktadır.
3. **Canlı Bot Nasıl +8.99 USDT Yaptı?:** Canlı botun +8.99 USDT yapabilmesinin nedeni; yetim BB1 emirlerinin piyasa zirvelerinde sibling pozisyonları tesadüfen kârla kapatması (+2.00, +1.35, +3.19 USDT gibi), quantize döngülerine rağmen bazı trailing stopların borsada fiilen daralmış olması ve sentetik borsa düzeltmeleridir.

> **Sonuç:** Yazılım düzeltmesi (quantize toleransı ve yetim stop engellemesi), stratejinin kârını garanti eden bir sihirli değnek değil; **botun başka pozisyonları rastgele tasfiye etmesini engelleyen, borsa API'sini spamlamayı durduran ve muhasebeyi şeffaflaştıran bir zorunluluktur.**

---

## 5. Teslim Edilen Dosya Paketi ve Doğrulama

Tüm paket `https://github.com/alpcoderalp/tv` reposuna teslim edilmiştir:

1. [`execution_allocation_ledger.csv`](execution_allocation_ledger.csv): 173 kapanış kaydının her birinin kaynak orderId, execId, miktar, net PnL ve fiziksel hedef parent eşleştirmesi.
2. [`parent_ledger.csv`](parent_ledger.csv): 113 kohort parent'ının doğrudan CID PnL'i, fiziksel intisap PnL'i, MFE/MAE değerleri ve replay sonuçları.
3. [`bb1_impact.csv`](bb1_impact.csv): 20 yetim stop emrinin detaylı zamanlama, dolum ve sibling tasfiye tablosu.
4. [`retry_timeline.csv`](retry_timeline.csv): 21 parent'ın 9.266 retry analizi, süre ve throttle dökümü.
5. [`replay_engine.py`](replay_engine.py): Parametrik ve bağımsız deterministik replay motoru (`--mode pessimistic/optimistic`, `--with-4h-timeout`).
6. [`reproduce_audit.py`](reproduce_audit.py): Tüm denetimi sıfırdan koşturan, veri bütünlüğünü ve PnL toplamlarını 6 haneli doğrulayan ana çalıştırma betiği.
7. [`data/`](data/): Gizli bilgilerden (API anahtarı, IP, şifre) tamamen arındırılmış 1m Last/Mark kline'ları, ham borsa JSON verileri ve parent manifestosu.
8. [`data_manifest.json`](data_manifest.json): SHA-256 sağlama toplamları ve kohort üstverileri.

### Yeniden Çalıştırma (Doğrulama):
```bash
git clone https://github.com/alpcoderalp/tv.git
cd tv
python reproduce_audit.py
```
Bu komut çalıştırıldığında tüm kohort dengeleri `8.994129 USDT` hedefiyle tam olarak doğrulanacaktır.
