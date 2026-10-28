# Adli Borsa ve Bot İcra Analiz Raporu & Kanıt Paketi (v3.0)
**Referans Dönemi:** `2026-10-23 09:31:39 UTC` — `2026-10-28 13:00:00 UTC`  
**İncelenen Kohort:** Kesim damgasından sonra açılan **113 Parent Pozisyon**, **173 Borsa Kapanış Kaydı**  
**Çalışan Temel Kod Sürümü:** `51F6CDD4` (`candidate_hybrid_v2_51F6CDD4.py`)  
**SHA-256:** `51f6cdd4c38b680a33273aabdd974120a318a9f6e340504024f4b8d02819f637`  
**Depo / Repo:** `https://github.com/alpcoderalp/tv`  

---

## 1. Yönetici Özeti ve Epistemolojik Çerçeve

Bu rapor, Hummingbot TV Sinyal Stratejisi altındaki canlı işlem kayıtlarını, Bybit demo borsa icra (execution) verilerini ve VPS loglarını inceleyen bağımsız adli denetim paketidir.

> **Bağımsız Kabul ve Değerlendirme İlkesi:**  
> 1. Bu raporda stratejinin piyasa karşısındaki "üstünlüğü", "kârlılığı" veya "başarısızlığı" yönünde hiçbir olumlu ya da olumsuz nedensellik hükmü verilmemiştir.  
> 2. "Yetim emirler kârı artırdı" veya "yazılım hatası kârı kurtardı/yıktı" gibi spekülatif nedensellik çıkarımları askıya alınmıştır.  
> 3. Replay simülasyonu bir kâr vaadi veya optimizasyon kanıtı değil; piyasa kurallarının ve execution varsayımlarının duyarlılığını ölçen bir **tanı aracıdır**.  
> 4. **Yazılım düzeltmelerinin kabulü; simülasyondaki kâr tahminine değil, kesin borsa icra muhasebesine, kardeş pozisyonları tasfiye eden kontrolsüz yetim stopların engellenmesine ve API spam döngülerinin giderilmesine dayanmalıdır.**

---

## 2. Kohort ve Kapanış PnL Mutabakatı (+12.1326 / +8.9941 USDT)

Bybit V5 Perpetual API'sinden çekilen `recent_closed_pnl.json` kayıtlarının tam mutabakatı:

1. **Ham Bybit API Kapanışları (`updatedTime >= 2026-10-23 09:31:39 UTC`):**
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

---

## 3. İcra Tahsis Defteri ve Komisyon Muhasebesi

Bybit V5 Perpetual sözleşmelerinde `closedPnl` alanı:
$$\text{closedPnl} = \text{Brüt Fiyat Farkı PnL} - \text{openFee} - \text{closeFee}$$
olarak tanımlanmıştır. Dolayısıyla Bybit'in sağladığı `closedPnl` değeri **zaten komisyonlar düşülmüş net gerçekleşen PnL'dir**.

Teslim edilen [`execution_allocation_ledger.csv`](execution_allocation_ledger.csv) dosyasında:
* **Brüt PnL Toplamı:** **`+44.018491 USDT`**
* **Bybit'e Ödenen Toplam Komisyon (Açılış + Kapanış):** **`35.024371 USDT`**
* **Net Gerçekleşen PnL:** **`+8.994128 USDT`**
* İkinci bir komisyon düşümü yapılmamış, her satırda kaynak `order_id`, `exec_id`, `qty`, `gross_pnl_usdt`, `open_fee_usdt`, `close_fee_usdt`, `total_fee_usdt`, `net_realized_pnl_usdt`, `origin_cid_parent` ve `physical_target_parent` 1-e-1 eşleştirilmiştir.

---

## 4. Yetim Stop Emirleri ve Sibling Tasfiye Mekanizması

Emir veri tabanında tespit edilen toplam **20 yetim stop emri** (`-BB1` ve `-BB2`) incelenmiştir:
* **Kesim Öncesi:** 1 adet (`#4b28dac1`, 23 Ekim 01:37 UTC)
* **Kohort İçi Toplam:** 19 adet (17 BB1 + 2 BB2)
  * **İptal Edilen:** 1 adet (`#43f4ac4f`)
  * **Borsada Dolan:** **18 adet** (16 BB1 + 2 BB2)

* **Meşru Residual Stop:** **0 adet (%0)**.
* **Kusurlu Yetim (Orphan) Stop:** **18 adet (%100)**.

Orijinal `-BB` stop emri Bybit üzerinde fiilen dolduktan 10.3 saniye ile 422.3 saniye sonra, WebSocket `execution` bildiriminin kaçması nedeniyle bot "stop yok" sanarak yeni bir koşullu emir göndermiştir.  
Borsada hesap düzeyinde tek bir pozisyon tutulduğu için bu dolan 18 yetim emir:
1. **13 vakada:** Açık olan kardeş parent pozisyonlarının sözleşmelerini kapatmıştır (Parent `41272473399`'un 7240 kontratı, `847413379694`, `666412677548`, `182962647145`, `12871875846`, `344083910534`, `780262343342`, `331357774828`, `333431666630`, `113923637725`, `123356490277`, `225276516407`).
2. **5 vakada:** Kendi lingering sözleşmelerini kapatmıştır.

Bu durum, bot loglarında `📁 [POSITION_FLAT CLOSE ARCHIVED]` şeklinde yapay 0.00 USDT PnL ile arşivlenen 7 parent pozisyonunun sırrını açıklamaktadır: Bu pozisyonların sözleşmeleri kardeş yetim stop emirleri tarafından fiilen borsa tarafında kapatılmıştır. Detaylar [`bb1_impact.csv`](bb1_impact.csv) dosyasındadır.

---

## 5. 9.266 Retry Analizi ve Quantize Doğrulama Kusuru

* **Sayı ve Dağılım:** Loglarda 5 gün boyunca **21 farklı parent pozisyondan** kaynaklanan **9.266 adet** `[HYBRID TRAIL 2R RETRY]` uyarısı kaydedilmiştir.
* **Throttle Tutarlılığı:** Ortalama aralık **3.45 – 3.52 saniye** olarak ölçülmüştür (`3.0s` throttle + Bybit REST round-trip).
* **Kök Neden (Quantize Defect):** Bybit stop emrinin fiyatını tick size'a quantize ederek (`0.05393`) borsada güncellemiştir. Ancak bot içindeki doğrulayıcı (`_hybrid_verify_bybit_sl_order`, L27338), quantize edilmiş fiyatı ham float hedefiyle (`0.05393 < 0.05393492 - 1e-6`) kıyasladığı için doğrulamayı reddetmiş, state'i güncellememiş ve 3.5 saniye sonra aynı emri borsaya tekrar göndermiştir. Döküm [`retry_timeline.csv`](retry_timeline.csv) dosyasındadır.

---

## 6. Deterministik Replay, Aynı-Mum Belirsizliği ve Stres Senaryosu

Replay simülasyonu, katı kurallarla koşturulmuştur:
1. **Analiz Bitiş Zamanı:** Yalnızca `start_ts <= ts <= 2026-10-28 13:00:00 UTC` aralığındaki barlar işlenmiştir.
2. **Zaman Çıkışı Yok:** Kodda bulunmayan 4 saatlik çıkış saf replay'den çıkarılmıştır.
3. **Gerçekleşmiş vs Açık Pozisyon Ayrımı:** 13:00:00 UTC'de henüz kapanmamış olan **2 parent pozisyonun** değerlemesi gerçekleşmiş PnL'e karıştırılmamış, `Unrealized MTM` olarak ayrı tutulmuştur.
4. **Dolum Modelleri:**
   * **Standart Model:** Stop emri tetiklenme fiyatında (`current_sl`) gerçekleşir (Bybit koşullu piyasa emrinin normal icra biçimi).
   * **Stres Modeli (Worst Candle):** Stop emri ilgili 1 dakikalık mumun en kötü ucunda (`min(current_sl, l_low)` / `max(current_sl, l_high)`) gerçekleşir.

### Replay Sonuçları Özeti (113 Parent):

| Senaryo / Koşul | Gerçekleşmiş Net PnL | Açık Pozisyon MTM | Toplam Net PnL | Intra-Bar TP1/SL Çakışması | Intra-Bar BE Çakışması |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Fiili Canlı Borsa İcrası** | **`+8.9941 USDT`** | **0.0000 USDT** | **`+8.9941 USDT`** | — | — |
| **Standart Replay [Kötümser]** | **`+15.9368 USDT`** | **`+3.7512 USDT`** | **`+19.6880 USDT`** | 0 trade | 1 trade |
| **Standart Replay [İyimser]** | **`+15.9368 USDT`** | **`+3.7512 USDT`** | **`+19.6880 USDT`** | 0 trade | 1 trade |
| **Stres Modeli [En Kötü Last Fiyatı]** | **`-28.9077 USDT`** | **`+3.7512 USDT`** | **`-25.1565 USDT`** | 0 trade | 1 trade |
| *Duyarlılık: 4h Çıkış (Kötümser)* | `-11.0890 USDT` | `+1.8797 USDT` | `-9.2093 USDT` | 0 trade | 1 trade |

*Not:* 113 trade boyunca aynı 1 dakikalık mumda hem baseline SL hem TP1'in görüldüğü vaka sayısı **0'dır**. Yalnızca 1 trade'de (`#961104007981`) TP1 gerçekleştikten sonra aynı barda BE seviyesine değen bir hareket görülmüştür.

---

## 7. Teslim Edilen Dosya Paketi ve Doğrulama

Tüm paket `https://github.com/alpcoderalp/tv` reposuna teslim edilmiştir:

1. [`execution_allocation_ledger.csv`](execution_allocation_ledger.csv): 173 kapanış kaydının tekil icra, miktar, komisyon ve hedef parent tablosu.
2. [`parent_ledger.csv`](parent_ledger.csv): 113 parent'ın doğrudan CID PnL'i, fiziksel intisap PnL'i, MFE/MAE değerleri ve dinamik replay çıktıları.
3. [`bb1_impact.csv`](bb1_impact.csv): 20 yetim stop emrinin gecikme süresi, dolum ve sibling tasfiye tablosu.
4. [`retry_timeline.csv`](retry_timeline.csv): 21 parent'ın 9.266 retry analizi ve süre dökümü.
5. [`replay_engine.py`](replay_engine.py): Bağımsız deterministik replay motoru (`--slippage standard/stress_worst_candle`, `--mode pessimistic/optimistic`).
6. [`reproduce_audit.py`](reproduce_audit.py): Hash kontrolü, icra tekilliği, miktar tahsisi ve dinamik replay karşılaştırmasını sıfırdan koşturan master test betiği.
7. [`data/`](data/): Gizli bilgilerden tamamen arındırılmış 1m Last/Mark kline'ları, ham borsa JSON verileri ve parent manifestosu.
8. [`data_manifest.json`](data_manifest.json): SHA-256 sağlama toplamları ve üstveriler.

### Yeniden Çalıştırma ve Doğrulama:
```bash
git clone https://github.com/alpcoderalp/tv.git
cd tv
python reproduce_audit.py
```
Bu komut; repo bütünlüğünü, icra tekilliğini, komisyon doğruluğunu ve dinamik simülasyonu çalıştırarak tüm dengeleri borsa verileriyle 1-e-1 teyit eder.
