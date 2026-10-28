# TV Signal Strategy — Pozisyon Yönetim Modları Geçiş Kılavuzu (`strategy_changer.md`)

Bu kılavuz, `tv_signal_strategy.py` üzerinde desteklenen üç temel pozisyon yönetim modeli (**`legacy`**, **`rr2_trailing`**, **`hybrid_trailing`**) ve acil durum / pasif modeli (**`passive`**) arasında nasıl güvenli ve hatasız geçiş yapılacağını, VPS ve bot üzerinde değişmesi gereken tüm dosya, satır, parametre ve operasyonel adımları ayrıntılı olarak açıklar.

---

## 1) Modların Karşılaştırmalı Çalışma Prensipleri

| Kriter / Aşama | `legacy` Modu | `rr2_trailing` Modu | `hybrid_trailing` Modu | `passive` Modu |
|---|---|---|---|---|
| **Temel Felsefe** | Klasik Faz 2: 1R'de %50 kısmi kâr al, SL'yi girişe çek, kalanı dinamik merdivenle sür. | Saf Trend Runner: 1R'de işlem yapma, 2R'de SL'yi R1'e kitle, fitil zeminleriyle çok aşamalı sür. | Hibrit Denge: 1R'de %50 TP1 al + SL girişe çek (BE). 1R-2R arası bekle. 2R'de dinamik trailing, 3R'de ratchet. | Yalnızca giriş ve ilk SL/TP konur; dinamik yönetim ve koruma onarımları kapalıdır. |
| **Girişte TP Emri** | **KONUR** (Fix BR fee-aware 2R limit TP). | **KONULMAZ** (`RR2_PLACE_ENTRY_TP=0`). | **KONULMAZ** (`tp_suppressed=True`). | **KONUR** (Orijinal sinyal TP'si). |
| **1R Seviyesinde** | `_try_trigger_legacy_phase2`: %50 market kapatılır + SL girişe taşınır. | **HİÇBİR ŞEY YAPILMAZ** (`1r_reached=False`, doğru davranış). | `_try_trigger_hybrid_trailing`: %50 TP1 kapatılır + SL girişe (+%0.5 BE) taşınır. | Hiçbir şey yapılmaz. |
| **1R – 2R Arasında** | Dinamik trailing başlar. | Normal pozisyon gibi ilk SL korunur. | `HYBRID_HOLD_ENTRY`: Stop girişte kilitli tutulur, trailing çalışmaz (erken çıkış önlenir). | Hiçbir şey yapılmaz. |
| **2R Seviyesinde** | Faz 2 TP2 hedefi hit olur (`TARGET HIT`). | `_try_trigger_rr2_management`: SL fee-aware R1'e kilitlenir (`RR2_ARMED_R1`) → +%0.2 ile `RR2_TRAIL_2R`. | `HYBRID_TRAIL_2R`: Dinamik trailing merdiveni devreye girer. | Hiçbir şey yapılmaz. |
| **3R ve Üzerinde** | Pozisyon zaten 2R'de tamamen kapanmıştır. | Multi-stage ratchet: 3R..10R fitil zeminleri (`floor`), max 11R tavanı. | `HYBRID_TRAIL_3R`: Tam RR2 multi-stage ratchet mantığına devredilir. | Hiçbir şey yapılmaz. |

---

## 2) VPS ve Bot Üzerinde Değişmesi Gereken Dosyalar ve Satırlar

### A. VPS Host Ortam Değişkenleri Dosyası
* **Host Dosya Yolu:** `/home/ubuntu/deploy/.env.hummingbot`
* **Konteyner İçi Bağlantısı:** Docker Compose tarafından `hummingbot` konteynerine environment olarak aktarılır.
* **Değiştirilecek Satırlar:**

```bash
# ==============================================================================
# POZİSYON YÖNETİM MODU SEÇİMİ
# Seçenekler: legacy | rr2_trailing | hybrid_trailing | passive
# ==============================================================================
POSITION_MANAGEMENT_MODE=hybrid_trailing

# ==============================================================================
# GİRİŞTE TP EMRİ YERLEŞTİRME KONTROLÜ
# legacy için: 1 (veya varsayılan)
# rr2_trailing için: 0 (ZORUNLU - aksi halde TP 2R'de pozisyonu kapatır, trailing ölür)
# hybrid_trailing için: 0 (ZORUNLU - TP1 zaten 1R'de dinamik yürütülür)
# ==============================================================================
RR2_PLACE_ENTRY_TP=0

# ==============================================================================
# OPSİYONEL İNCE AYARLAR (İsteğe bağlı)
# ==============================================================================
# RR2_TRAIL_SWITCH_PCT=0.002   # 2R sonrası trailing merdivenine geçiş marjı (+%0.2)
```

---

### B. Bot Strateji Kaynak Kodu (`tv_signal_strategy.py`)
* **Host Dosya Yolu:** `/home/ubuntu/deploy/bots/scripts/tv_signal_strategy.py`
* **Konteyner Dosya Yolu:** `/home/hummingbot/scripts/tv_signal_strategy.py`
* **İlgili Fonksiyonlar ve Satır Aralıkları:**

1. **Modun Okunması ve Başlatılması:**
   * **Satır 1962 – 1976 (`TVSignalStrategy.__init__`):**
     ```python
     self.POSITION_MANAGEMENT_MODE = (
         os.getenv("POSITION_MANAGEMENT_MODE", "legacy") or "legacy"
     ).strip().lower()
     if self.POSITION_MANAGEMENT_MODE not in (
         "legacy",
         "rr2_trailing",
         "passive",
         "hybrid_trailing",
     ):
         self.logger().warning(...)
         self.POSITION_MANAGEMENT_MODE = "legacy"
     ```
   * **Satır 1987 – 1991:** `self.RR2_PLACE_ENTRY_TP` env kontrolü.

2. **Mod Sorgulama Yardımcısı (Helper):**
   * **Satır 25846 (`_position_management_mode`):**
     Strateji genelinde aktif modu `legacy`, `rr2_trailing`, `hybrid_trailing` veya `passive` olarak döndüren merkezi fonksiyon.

3. **Ana Değerlendirme Döngüsü (Monitor Dispatcher):**
   * **Satır 27938 (`_monitor_positions`):**
     * Her tick'te pozisyonları tarar.
     * `legacy` ise $\rightarrow$ Satır 27780 `_try_trigger_legacy_phase2` çağrılır.
     * `rr2_trailing` ise $\rightarrow$ Satır 26322 `_try_trigger_rr2_management` çağrılır.
     * `hybrid_trailing` ise $\rightarrow$ Satır 26839 `_try_trigger_hybrid_trailing` ve Satır 28042 blokları çağrılır.
     * `passive` ise $\rightarrow$ Değerlendirme ve trailing atlanır.

4. **1R ve 2R Tetikleyici Fonksiyonları:**
   * **Satır 27780 (`_try_trigger_legacy_phase2`):** Legacy %50 kısmi kapanış ve SL'nin başabaşa taşınması.
   * **Satır 26322 (`_try_trigger_rr2_management`):** RR2 2R kontrolü, R1 kilit emri, failsafe limit/market kapatıcıları.
   * **Satır 26900 – 27150 (`_try_trigger_hybrid_trailing`):** Hybrid TP1 yürütülmesi, BE taşınması ve `HYBRID_HOLD_ENTRY` aşamasına geçiş.

5. **Dinamik Trailing ve Borsa Amend Motoru:**
   * **Satır 34234 (`_update_trailing_sl_rr2_strict`):** Borsa koşullu emrinin atomik olarak değiştirilmesi ve readback ile doğrulanması.
   * **Satır 34283 – 34550 (`_handle_phase2_trailing`):**
     * `legacy`: Normal %0.1 merdivenli trailing.
     * `rr2_trailing`: Multi-stage wick ratchet zeminleri (Satır 34390+).
     * `hybrid_trailing`: 2R seviyesinde dinamik trailing (`HYBRID_TRAIL_2R`), 3R seviyesinde ratchet devri (`HYBRID_TRAIL_3R`).

---

## 3) Kesin Geçiş Protokolü (Adım Adım Operasyonel Yönerge)

> [!CAUTION]
> **MODLAR KARMA ÇALIŞMAZ!**
> Açık pozisyon varken mod değiştirilemez. Eski modun hafıza bayrakları (`management_stage`, `phase2_active`, `r1_price`) yeni modun mantığıyla uyuşmaz ve pozisyonun donmasına veya kontrolsüz kalmasına yol açar. Geçiş daima **FLAT (Sıfır Pozisyon)** durumunda yapılmalıdır.

### Adım 1: Yeni Sinyal Girişini Durdurun
Yeni sinyal gelerek işlem açılmasını önlemek için RogerThat webhook servisini durdurun:
```bash
ssh -p 22022 ubuntu@57.129.5.114 "docker stop rogerthat"
```

### Adım 2: Mevcut Pozisyonların Kapanmasını Sağlayın
* Açık pozisyonların doğal olarak kâr/zarar hedeflerine ulaşmasını bekleyin veya Bybit arayüzünden manuel olarak kapatın.
* Borsa üzerinde açık emir kalmadığından emin olun.

### Adım 3: Borsa Sıfırlığını Doğrulayın
Lokal doğrulama betiğini çalıştırarak borsa tarafında sıfır pozisyon ve sıfır emir olduğunu kesinleştirin:
```powershell
python scratch/verify_bybit_flat.py
```
Çıktıda `IS BYBIT COMPLETELY FLAT -> True` görülmelidir.

### Adım 4: Hummingbot Servisini Durdurun
```bash
ssh -p 22022 ubuntu@57.129.5.114 "docker stop hummingbot"
```

### Adım 5: Eski State Dosyasını Temizleyin (ZORUNLU)
Eski moda ait kalıntı aşama bayraklarının yeni moda sızmaması için state dosyasını sıfırlayın:
```bash
ssh -p 22022 ubuntu@57.129.5.114 "sudo rm -f /home/ubuntu/deploy/bots/data/tv_signal_state.json /home/ubuntu/deploy/bots/data/tv_signal_state.json.bak"
```

### Adım 6: `.env.hummingbot` Dosyasında Hedef Modu Ayarlayın
VPS üzerinde `/home/ubuntu/deploy/.env.hummingbot` dosyasını düzenleyin:
* **`legacy` için:**
  ```env
  POSITION_MANAGEMENT_MODE=legacy
  RR2_PLACE_ENTRY_TP=1
  ```
* **`rr2_trailing` için:**
  ```env
  POSITION_MANAGEMENT_MODE=rr2_trailing
  RR2_PLACE_ENTRY_TP=0
  ```
* **`hybrid_trailing` için:**
  ```env
  POSITION_MANAGEMENT_MODE=hybrid_trailing
  RR2_PLACE_ENTRY_TP=0
  ```

### Adım 7: Konteyneri Yeniden Oluşturup Başlatın
Ortam değişkenlerinin temiz şekilde geçerli olması için konteyneri recreate edin:
```bash
ssh -p 22022 ubuntu@57.129.5.114 "cd /home/ubuntu/deploy && docker compose up -d --force-recreate hummingbot"
```

### Adım 8: Başlangıç Loglarını Doğrulayın (İlk 60 Saniye)
```bash
ssh -p 22022 ubuntu@57.129.5.114 "docker logs --tail 100 hummingbot | grep -E 'POSITION_MANAGEMENT|State yükleniyor'"
```
* Doğru modun yüklendiğini (`POSITION_MANAGEMENT_MODE=<hedef_mod>`) doğrulayın.
* `Geçersiz POSITION_MANAGEMENT_MODE` uyarısı OLMAMALIDIR.

### Adım 9: Sinyal Girişini Yeniden Açın
```bash
ssh -p 22022 ubuntu@57.129.5.114 "docker start rogerthat"
```

---

## 4) Mod Bazında Doğrulama Log Tablosu

Geçiş sonrası gelen ilk işlemde aşağıdaki log imzaları takip edilmelidir:

| Aşama | `legacy` Modunda Görülmesi Gereken | `rr2_trailing` Modunda Görülmesi Gereken | `hybrid_trailing` Modunda Görülmesi Gereken |
|---|---|---|---|
| **Giriş Anı** | `✅ [B4 BYBIT SLTP] ... SL=... TP=...` | `🔀 [RR2 ENTRY] ... TP emri KONULMAYACAK` | `🔀 [RR2 ENTRY] [HYBRID] ... TP emri KONULMAYACAK` |
| **1R Seviyesi** | `🚀 [FAZ 2 AKTİVASYON]` + `%50 kapama` | **HİÇBİR LOG OLMAZ** (doğru davranış) | `🚀 [HYBRID TRIGGER] ... 1R geçildi` + `🛡️ [HYBRID +0.5% BE]` |
| **1R-2R Arası** | `🔺/🔻 [FAZ 2 TRAILING]` | İlk SL ile normal bekleme | `HYBRID_HOLD_ENTRY` (Trailing çalışmaz, BE korunur) |
| **2R Seviyesi** | `🎯 [PHASE2 TP2 HIT]` (Pozisyon biter) | `🚀 [RR2 TRIGGER]` $\rightarrow$ `🛡️ [RR2 ARMED]` | `🚀 [HYBRID 2R REACHED]` $\rightarrow$ Dinamik trailing başlar |
| **3R Seviyesi** | — | `🚀 [RR2 RATCHET]` 3R zemin kilidi | `🚀 [HYBRID 3R RATCHET]` Ratchet devralır |

> [!WARNING]
> **YASAKLI LOG KONTROLÜ:**
> * `rr2_trailing` veya `hybrid_trailing` modunda çalışırken `✅ [BYBIT LIMIT TP]` veya `🚀 [FAZ 2 AKTİVASYON]` görürseniz mod env'si doğru yüklenmemiştir; derhal 6. ve 7. adımları tekrarlayın.

---

## 5) Hızlı Acil Geri Dönüş (Rollback)

Herhangi bir beklenmeyen durumda `legacy` moduna geri dönmek için:
1. `ssh -p 22022 ubuntu@57.129.5.114 "docker stop rogerthat"`
2. Pozisyonları kapatın / sıfırlayın.
3. `/home/ubuntu/deploy/.env.hummingbot` içinde `POSITION_MANAGEMENT_MODE=legacy` ve `RR2_PLACE_ENTRY_TP=1` yapın.
4. `ssh -p 22022 ubuntu@57.129.5.114 "sudo rm -f /home/ubuntu/deploy/bots/data/tv_signal_state.json"`
5. `ssh -p 22022 ubuntu@57.129.5.114 "cd /home/ubuntu/deploy && docker compose up -d --force-recreate hummingbot && docker start rogerthat"`

