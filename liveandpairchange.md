# Bybit Live Ortamına Geçiş ve Çoklu Pair Yönetim Kılavuzu (`liveandpairchange.md`)

Bu kılavuz, Hummingbot TradingView sinyal stratejisinin Bybit Demo ortamından **Bybit Live (Gerçek Para)** ortamına nasıl taşınacağını ve işlem yapılan işlem çiftlerinin (**trading pairs**) kod değiştirmeden nasıl eklenip, çıkarılıp güncelleneceğini adım adım ve dosya/satır referanslarıyla açıklar.

---

## 1) Mimari Genel Bakış

* **Borsa Ortamı Ayrımı:** Bybit Demo ve Live tamamen bağımsız iki ortamdır. Demo ortamında API endpoint'i `api-demo.bybit.com` ve connector adı `bybit_perpetual_demo` iken; Live ortamında endpoint `api.bybit.com` ve connector adı `bybit_perpetual`'dır.
* **Dinamik Pair Mimarisi:** Strateji kodu içinde işlem çiftleri hardcoded değildir. Sınıf seviyesindeki varsayılanlar çalışma anında `/home/ubuntu/deploy/bots/conf/scripts/tv_signal_strategy.yml` dosyasından okunarak dinamik olarak yapılandırılır. Tek bir satır Python kodu değiştirmeden pair ekleme/çıkarma yapılır.

---

## BÖLÜM I: Bybit Demo'dan Live (Gerçek Para) Ortamına Geçiş

### 1. Bybit Canlı Hesap Ön Koşulları (Kritik)
Canlıya geçmeden önce Bybit Live hesabınızda şu kontrolleri yapın:
1. **Position Mode (Hedge Mode):** Bybit Canlı hesabında Futures $\rightarrow$ Preferences (Ayarlar) $\rightarrow$ **Position Mode = Hedge Mode** seçilmiş olmalıdır. Demo ve Live ayarları birbirinden bağımsızdır; Live hesabında Hedge Mode açık değilse çoklu parçalı emirler reddedilir.
2. **API Key İzinleri:**
   * **Contract Trading (Orders & Positions):** Okuma ve Yazma (Read & Write) AÇIK.
   * **Withdrawal (Para Çekme):** KESİNLİKLE KAPALI.
3. **IP Whitelist:** Eğer API anahtarında IP kısıtlaması kullanılıyorsa VPS IP'si (`57.129.5.114`) eklenmiş olmalıdır.

---

### 2. VPS ve Bot Üzerinde Değişmesi Gereken Dosyalar ve Satırlar

#### A. Ortam Değişkenleri Dosyası
* **Dosya Yolu:** `/home/ubuntu/deploy/.env.hummingbot`
* **Değiştirilecek Satır:**
  ```env
  # ESKİ:
  BYBIT_ENV=demo

  # YENİ (LIVE):
  BYBIT_ENV=live
  ```

#### B. Strateji Konfigürasyon YAML Dosyası
* **Dosya Yolu:** `/home/ubuntu/deploy/bots/conf/scripts/tv_signal_strategy.yml`
* **Değiştirilecek Bölüm:** `markets:` altındaki connector anahtarı `bybit_perpetual_demo:` yerine `bybit_perpetual:` yapılır (işlem çiftleri listesi korunur):
  ```yaml
  # ESKİ:
  markets:
    bybit_perpetual_demo:
      - PONS-USDT
      - CHIP-USDT

  # YENİ (LIVE):
  markets:
    bybit_perpetual:
      - PONS-USDT
      - CHIP-USDT
  ```

#### C. Bybit Live Connector API Anahtarı
* **Dosya Yolu:** `/home/ubuntu/deploy/bots/conf/connectors/bybit_perpetual.yml`
* **İşlem:** Hummingbot CLI arayüzüne bağlanarak canlı anahtarlar girilir:
  ```bash
  # Hummingbot CLI'ye bağlanın
  docker attach hummingbot
  # Hummingbot prompt'unda:
  connect bybit_perpetual
  # İstenen bybit_perpetual_api_key ve bybit_perpetual_secret_key değerlerini girin.
  # CLI'den ayrılmak için: Ctrl+P ve ardından Ctrl+Q tuşlayın (konteyneri kapatmaz).
  ```

---

### 3. Strateji Kaynak Kodundaki Otomatik Mekanizmalar (`tv_signal_strategy.py`)

Canlı ortama geçiş için `tv_signal_strategy.py` kodunda manuel değişiklik yapılmasına gerek yoktur. Kod ortamı otomatik algılar:
* **Satır 979 (`TVSignalStrategy.__init__`):**
  ```python
  self.BYBIT_ENV = (os.getenv("BYBIT_ENV", "demo") or "demo").strip().lower()
  ```
* **Satır 989–990:**
  ```python
  self.ACTIVE_CONNECTOR = (
      "bybit_perpetual_demo" if self.BYBIT_ENV == "demo" else "bybit_perpetual"
  )
  ```
  `BYBIT_ENV=live` yapıldığında `ACTIVE_CONNECTOR` otomatik olarak `bybit_perpetual` olur.
* **Satır 2527+ (Mount Edilmiş Sabitler):**
  VPS üzerindeki `/home/ubuntu/deploy/bots/custom/bybit_perpetual/bybit_perpetual_constants.py` dosyası konteyner içine mount edilmiş olup, Live REST (`https://api.bybit.com/`) ve WS (`wss://stream.bybit.com/v5/private`) adreslerini eksiksiz tanımlar.
* **Satır 2534+ (`_bybit_raw_credentials`):**
  Connector adı `"demo"` içermediğinde otomatik olarak Bybit Live REST URL'lerini kullanır.

---

### 4. Canlıya Geçiş İçin Kesin Operasyonel Protokol (Adım Adım)

1. **Sinyal Girişini Durdurun:**
   ```bash
   ssh -p 22022 ubuntu@57.129.5.114 "docker stop rogerthat"
   ```
2. **Demo Ortamının Tamamen Flat Olduğunu Teyit Edin:**
   ```powershell
   python scratch/verify_bybit_flat.py
   ```
3. **Hummingbot'u Durdurun:**
   ```bash
   ssh -p 22022 ubuntu@57.129.5.114 "docker stop hummingbot"
   ```
4. **Demo State Dosyasını Temizleyin:**
   Demo işlemlerine ait hiçbir eski kimlik veya defterin canlıya taşınmaması için state dosyasını silin:
   ```bash
   ssh -p 22022 ubuntu@57.129.5.114 "sudo rm -f /home/ubuntu/deploy/bots/data/tv_signal_state.json /home/ubuntu/deploy/bots/data/tv_signal_state.json.bak"
   ```
5. **Konfigürasyonları Güncelleyin:**
   * `/home/ubuntu/deploy/.env.hummingbot` $\rightarrow$ `BYBIT_ENV=live`
   * `/home/ubuntu/deploy/bots/conf/scripts/tv_signal_strategy.yml` $\rightarrow$ `bybit_perpetual:`
6. **Konteyneri Yeniden Oluşturup Başlatın:**
   ```bash
   ssh -p 22022 ubuntu@57.129.5.114 "cd /home/ubuntu/deploy && docker compose up -d --force-recreate hummingbot"
   ```
7. **Başlangıç Loglarında Live Bağlantısını Doğrulayın:**
   ```bash
   ssh -p 22022 ubuntu@57.129.5.114 "docker logs --tail 100 hummingbot | grep -E 'BACKEND panel|conn_ready|B2 boot'"
   ```
   * Görülmesi gereken: `backend=bybit bybit_env=live active=bybit_perpetual` ve `conn_ready=True`.
8. **Sinyal Webhook Servisini Açın:**
   ```bash
   ssh -p 22022 ubuntu@57.129.5.114 "docker start rogerthat"
   ```

---

## BÖLÜM II: Çoklu Pair (İşlem Çifti) Ekleme, Çıkarma ve Güncelleme

### 1. Dinamik Çoklu Pair Mimarisi
* `tv_signal_strategy.py` dosyasında:
  * **Satır 504–520:** Sınıf varsayılanı `markets = {"bybit_perpetual_demo": ["BTC-USDT", ...], ...}` yer alır.
  * **Satır 534–545 (`init_markets`):** Bot açılırken YAML dosyasındaki `markets:` alanını okur ve sınıf değişkenini dinamik olarak ezer.
* Dolayısıyla pair ekleyip çıkarmak için **yalnızca YAML dosyası düzenlenir**.

---

### 2. VPS Üzerinde Pair Değişikliği Nasıl Yapılır?

* **Dosya Yolu:** `/home/ubuntu/deploy/bots/conf/scripts/tv_signal_strategy.yml`
* **Düzenleme Örneği:**

```yaml
markets:
  bybit_perpetual_demo:       # (Live ortamındaysanız bybit_perpetual:)
    - PONS-USDT
    - CHIP-USDT
    - BTC-USDT               # Yeni eklenen pair
    - SOL-USDT               # Yeni eklenen pair
```

> [!IMPORTANT]
> **Pair Adlandırma Kuralı:**
> * Çiftler mutlaka `<BASE>-USDT` formatında (arada tire ile) yazılmalıdır.
> * Çiftin Bybit Linear Perpetual (USDT-M) pazarında aktif olarak listelenmiş olması şarttır.

---

### 3. Pair Çıkarma Güvenlik Kuralı
Bir çifti YAML listesinden çıkarmadan önce:
1. O pariteye ait borsa üzerinde **açık pozisyon bulunmadığından** emin olun.
2. O pariteye ait borsa üzerinde **aktif limit veya koşullu (SL/TP) emir bulunmadığından** emin olun.
3. Pozisyon açıkken parite kaldırılırsa bot o paritenin order book ve WS veri akışını kapatır; pozisyon korumasız kalır.

---

### 4. TradingView ve RogerThat Entegrasyonu

Yeni bir pair eklendiğinde TradingView tarafında alert oluştururken:
* **Sembol Formatı:** TradingView ticker'ı `BTCUSDT.P` veya `BTCUSDT` olabilir.
* **Sembol Çözümleme (`_resolve_tradingview_ticker` L1400+):**
  Bot, TradingView'den gelen `BTCUSDT` veya `BTCUSDT.P` sembolünü otomatik olarak Hummingbot formatı olan `BTC-USDT` standardına dönüştürür.
* **RogerThat Webhook Payload Örneği:**
  ```json
  {
    "ticker": "BTCUSDT",
    "action": "BUY",
    "order_type": "ENTRY",
    "entry": 67500.0,
    "sl": 66800.0,
    "tp": 68900.0
  }
  ```

---

### 5. Pair Güncellemesi Sonrası Uygulama ve Doğrulama Adımları

1. YAML dosyasını kaydedin.
2. Hummingbot konteynerini yeniden başlatın:
   ```bash
   ssh -p 22022 ubuntu@57.129.5.114 "cd /home/ubuntu/deploy && docker compose up -d --force-recreate hummingbot"
   ```
3. Logları kontrol edin:
   ```bash
   ssh -p 22022 ubuntu@57.129.5.114 "tail -n 60 /home/ubuntu/deploy/bots/logs/logs_tv_signal_strategy.log | grep -E 'Initialized order book|BYBIT PUBLIC WS'"
   ```
   * Görülmesi gereken:
     ```text
     Initialized order book for BTC-USDT. 1/4 completed.
     Initialized order book for SOL-USDT. 2/4 completed.
     ...
     🌊 [BYBIT PUBLIC WS] bağlandı: 4 ticker (wss://stream.bybit.com/v5/public/linear)
     ```
   Tüm yeni pair'ler için order book ve public WS ticker bağlantısının başarıyla kurulduğu teyit edilmelidir.

