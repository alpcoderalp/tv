# Adli Borsa ve Bot İcra Analiz Raporu & Kanıt Paketi
**Referans Zaman Kesiti:** `2026-10-23 09:31:39 UTC` — `2026-10-28 13:00:00 UTC`  
**İncelenen Kohort:** Kesim zaman damgasından sonra açılan **113 Parent Pozisyon**, **173 Borsa Kapanış Kaydı**  
**Çalışan Temel Sürüm:** `51F6CDD4` (`candidate_hybrid_v2_51F6CDD4.py`)  
**SHA-256:** `51f6cdd4c38b680a33273aabdd974120a318a9f6e340504024f4b8d02819f637`

---

## 1. Kohort ve PnL Mutabakatı (+12.13 / +10.6689 / +8.9941 Farkının Kesin Kanıtı)

Bybit Demo API'sinden çekilen ve bu aralıkta güncellenmiş tüm kapanış kayıtlarının kesin dökümü:

1. **Ham Borsa API Toplamı (`updatedTime >= 09:31:39 UTC`):**
   * Toplam 176 kapanış kaydı $\rightarrow$ **`+12.132616 USDT`**.
2. **Kesim Öncesi Pozisyonların Kapanışları:**
   * `661706686159` (PONS): Giriş `09:15:11 UTC`, Kapanış `11:28:21 UTC` (`#91613cc0`) $\rightarrow$ **`+1.618341 USDT`**
   * `513350689420` (CHIP): Giriş `09:30:11 UTC`
     * TP1 Kapanışı `14:16:36 UTC` (`#70b4e92e`) $\rightarrow$ **`+1.674826 USDT`**
     * SL Kapanışı `14:57:36 UTC` (`#30615015`) $\rightarrow$ **`-0.154680 USDT`**
     * Subtotal: **`+1.520146 USDT`**
   * **Toplam Kesim Öncesi Kapanış PnL:** $1.618341 + 1.520146 = \mathbf{+3.138487\text{ USDT}}$ (3 kayıt).
3. **Kesim Anından İtibaren Açılan Tam Kohort PnL:**
   $$\text{Kohort Net PnL} = 12.132616 - 3.138487 = \mathbf{+8.994129\text{ USDT}}$$
   * **Parent Sayısı:** **113 adet**
   * **Borsa Kapanış Kaydı:** **173 adet**
   * **Eşleşme Oranı:** **%100 (173 / 173 kayıt doğrudan parent'lara eşleştirilmiştir, sapma 0.000000 USDT'dir).**
   * *Not:* Önceki taslak raporda görülen `+10.6689` değeri, `513350689420`'nin TP1 bacağının (`+1.6748`) henüz kesim öncesi sayılmamasından; `+10.63` ise Oct 22 log rotasyonundaki 11 parent'ın ilk taramada eksik kalmasından kaynaklanmıştır. Bu raporda tüm loglar (`2026-10-22` dahil) birleştirilmiş ve tam kohort bazında eşitlenmiştir.

---

## 2. BB1 Emirlerinin Sınıflandırılması ve Sibling Pozisyon Etkileri

İncelenen 18 adet BB1 koşullu stop emrinin tamamı denetlenmiştir:
* **Meşru Residual BB1:** **0 adet (%0)**
* **Yanlış Üretilmiş Erroneous Orphan BB1:** **18 adet (%100)**
* **Borsada Dolan:** **14 adet** | **İptal Edilen:** **4 adet**

### Kök Neden:
Her 18 vakanın tamamında, parent pozisyonun orijinal `-BB` stopu Bybit borsasında **fiilen dolduktan 11 saniye ile 5 dakika sonra**, kaçan/geciken WebSocket `execution` bildirimi nedeniyle botun periyodik kontrol mekanizması "stop eksik" sanarak borsaya yeni bir yetim `BB1` stopu göndermiştir.

### Sibling Pozisyonları Tasfiye Etme Mekanizması:
Borsada bu 14 yetim stop emri tetiklendiğinde, pozisyon zaten kapalı olduğu için borsa hesap düzeyinde ters yönde işlem yapmış ve **açık olan kardeş (sibling) parent pozisyonlarını erkenden kapatmıştır**:
* `H-S-652176419954-BB1`: CHIP LONG `#847413379694`'ü kapattı (+2.0075 USDT).
* `H-S-109125793223-BB1` & `H-S-768409125624-BB1`: CHIP SHORT `#666412677548` ve `#182962647145`'i kapattı (-0.7642 ve -0.2471 USDT).
* `H-S-874632478783-BB1`: PONS SHORT `#344083910534`'ü kapattı (-0.9233 USDT).
* `H-S-832905025513-BB1` & `H-S-698726366611-BB1`: PONS SHORT `#331357774828`'i kapattı (-0.4999 USDT).
* `H-S-467109777758-BB1`: PONS LONG `#780262343342`'yi kapattı (-0.4222 USDT).
* `H-S-458490098872-BB1`: CHIP LONG `#12871875846`'yı kapattı (+1.3530 USDT).

Tüm detaylar [`bb1_impact.csv`](bb1_impact.csv) dosyasında tablo halinde sunulmuştur.

---

## 3. Gerçek Execution PnL'inin 7 Parent'a Fiziksel İntisabı ve Tekillik Kanıtı

İlk taslakta `total_realized_pnl = 0.00` görünen 7 parent'ın kapanışları, Bybit tarafından onları kapatan BB1 emirlerinin ID'lerine kaydedilmiştir. Bu execution'lar fiziksel olarak kapatılan sözleşmelerin sahibi olan parent'lara paylaştırılmış ve şu sonuç doğrulanmıştır:

$$\sum_{i=1}^{113} \text{Allocated Parent Realized PnL} = \mathbf{+8.994129\text{ USDT}}$$

Hiçbir execution çift sayılmamış, hiçbir kapanış ihmal edilmemiştir. Gerçekleşen fiziksel kapanış değerleri [`parent_ledger.csv`](parent_ledger.csv) içindeki `allocated_realized_pnl` sütununa 1-e-1 işlenmiştir.

---

## 4. 9.266 Retry Analizi ve 3s Throttle Doğrulaması

1. **Toplam Sayı:** 5 gün boyunca loglarda üretilen toplam retry uyarısı **9.266 adettir**.
2. **Dağılım:** Bu retrying tek bir pozisyondan değil, **21 farklı parent pozisyondan** kaynaklanmıştır.
3. **Throttle Doğrulaması:**
   * Örnek `#885285766398`: Süre **31.4 dakika (1.881 saniye)**, retry sayısı **539**, ortalama aralık **3.50 saniye** (3.0s throttle + ~0.5s Bybit API round-trip). Throttle kusursuz çalışmıştır.
   * En uzun retry yapan `#808409635108`: Süre **139.2 dakika**, retry sayısı **2.520**, ortalama aralık **3.32 saniye**.
4. **Borsa vs Bot Ayrımı:**
   * Bybit borsası `v5/order/amend` isteklerini kabul etmiş ve tetikleme fiyatını tick size'a göre (`0.05393`, `0.05398`...) yukarı taşımıştır.
   * Ancak botun iç doğrulayıcısı (`_hybrid_verify_bybit_sl_order`, satır 27338), borsadan gelen quantize edilmiş fiyatı ham float hedefiyle (`0.05393 < 0.05393492 - 1e-6`) kıyasladığı için doğrulamayı reddetmiş ve state'i güncellememiştir.
   * Tüm döküm [`retry_timeline.csv`](retry_timeline.csv) dosyasındadır.

---

## 5. Replay Simülasyonu ve Aynı-Mum Belirsizliği Raporu

Strateji parametreleri (1R TP1 %50, BE stop seviyesi, 2R trailing ratchet tabanı) **%100 sabit tutularak**, yalnızca:
* Quantize hatası giderilmiş (hedef fiyata `round_to_tick` uygulanmış),
* Erroneous orphan BB1 emirleri engellenmiştir.

### Sonuçlar:
* **Fiili Gerçekleşen (Böcekli) Kohort PnL:** **`+8.9941 USDT`**
* **Replay Kötümser (Pessimistic - Belirsiz barda SL önce):** **`+16.5939 USDT`**
* **Replay İyimser (Optimistic - Belirsiz barda TP/Peak önce):** **`+16.5939 USDT`**
* **Net Yazılım Düzeltme Farkı (Delta):** **`+7.5998 USDT` (%+84.5 artış)**

*Not:* 1 dakikalık barlarda 2R genişliğinde (hem -1R baseline SL hem +1R TP1'e aynı 60 saniyede değen) çubuk bulunmadığı için kötümser ve iyimser senaryolar kohort genelinde aynı sonucu üretmiştir.

---

## 6. Dosya Manifestosu (Teslim Edilen Dosyalar)

| Dosya | Açıklama |
| :--- | :--- |
| [`parent_ledger.csv`](parent_ledger.csv) | 113 parent'ın eksiksiz giriş, çıkış, PnL, MFE ve replay dökümü |
| [`bb1_impact.csv`](bb1_impact.csv) | 18 yetim BB1 emrinin sınıflandırması ve sibling etki analizi |
| [`retry_timeline.csv`](retry_timeline.csv) | 21 parent'ın 9.266 retry dökümü ve süre analizi |
| [`replay_engine.py`](replay_engine.py) | Deterministik ve belirsizlik kontrollü replay simülasyon kodu |
| [`strategy_version_51F6CDD4.py`](strategy_version_51F6CDD4.py) | VPS'te çalışan canlı strateji dosyasının referans kopyası |
| [`data_manifest.json`](data_manifest.json) | Tüm girdi verilerinin ve çıktıların SHA-256 doğrulama özeti |
