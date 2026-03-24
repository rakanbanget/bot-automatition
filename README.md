# 🥇 Bot Antam "Antigravity-Gold"

Bot otomatis antrean emas Antam di [logammulia.com](https://www.logammulia.com/id/antrean) menggunakan **Patchright** (Chromium stealth) dengan dukungan Residential Proxy dan notifikasi Telegram.

---

## 📁 Struktur File

```
bot-baru/
├── bot.py             # Entry point utama
├── stealth.py         # Bypass deteksi bot (JS inject, mouse, delay)
├── proxy_manager.py   # Konfigurasi Residential Proxy
├── queue_handler.py   # Logika deteksi slot & isi form antrean
├── notifier.py        # Notifikasi Telegram
├── config.json        # ⚙️ KONFIGURASI UTAMA (edit ini dulu!)
└── requirements.txt   # Library Python yang dibutuhkan
```

---

## ⚙️ Setup (Pertama Kali)

### 1. Install Python 3.11+
Pastikan Python sudah terinstall:
```bash
python3 --version
```

### 2. Buat Virtual Environment (Direkomendasikan)
```bash
cd /Users/aqilarakan/Documents/bot-baru
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
# venv\Scripts\activate       # Windows
```

### 3. Install Library
```bash
pip install -r requirements.txt
```

### 4. Install Browser Patchright
Ini wajib dilakukan sekali setelah install:
```bash
patchright install chromium
```

### 5. Edit `config.json`
Isi semua field berikut di `config.json`:

| Field | Keterangan |
|---|---|
| `proxy.host` | Host Residential Proxy kamu |
| `proxy.port` | Port proxy |
| `proxy.username` | Username proxy |
| `proxy.password` | Password proxy |
| `telegram.bot_token` | Token dari [@BotFather](https://t.me/BotFather) |
| `telegram.chat_id` | Chat ID Telegram kamu |
| `antam.boutique` | Nama butik target (contoh: "Jakarta Pulogadung") |
| `personal_data.*` | Data diri untuk isi form antrean |

> **Cara dapat Chat ID Telegram:** Chat dengan [@userinfobot](https://t.me/userinfobot), ia akan memberi chat ID kamu.

---

## 🚀 Cara Menjalankan

### Dry-Run (Test Tanpa Submit Form)
Digunakan untuk memastikan browser terbuka dan proxy berfungsi, **tanpa** mengisi/submit form:
```bash
python bot.py --test
```

### Full Run (Antrean Otomatis)
```bash
python bot.py
```

Bot akan:
1. Buka browser Chromium dengan stealth mode
2. Akses halaman antrean logammulia.com lewat proxy
3. Tunggu Cloudflare Turnstile selesai secara natural
4. Mendeteksi slot antrean
5. Mengisi form dengan data dari `config.json`
6. Submit dan verifikasi masuk halaman invoice
7. Kirim notifikasi ke Telegram

Jika slot belum tersedia, bot **otomatis retry** setiap `retry_delay_seconds` (default: 30 detik), hingga `max_retry` kali (default: 10 kali).

Untuk menghentikan paksa:
```bash
Ctrl + C
```

---

## 🛡️ Fitur Stealth

| Fitur | Keterangan |
|---|---|
| **Patchright** | Chromium yang sudah di-patch, bypass deteksi webdriver level rendah |
| **JS Injection** | Hapus `navigator.webdriver`, `__playwright`, dll |
| **User-Agent** | Chrome 123 Windows terbaru |
| **Locale & Timezone** | id-ID / Asia/Jakarta |
| **Random Delay** | Jeda 2–5 detik antar aksi |
| **Random Mouse** | Pergerakan kursor acak menyerupai manusia |
| **Residential Proxy** | IP terlihat sebagai user rumahan Indonesia |

---

## ⚡ Tips Penting

- **Jalankan headless: false dulu** untuk memantau visual dan memastikan Turnstile beres
- **Setelah stabil**, set `"headless": true` di `config.json` untuk jalan di background
- **Perbarui selectors** di `queue_handler.py` jika website berubah struktur HTML-nya
- Untuk jadwal otomatis, gunakan `cron` (Mac/Linux) atau Task Scheduler (Windows)

---

## 🆘 Troubleshooting

| Masalah | Solusi |
|---|---|
| `ModuleNotFoundError: patchright` | Jalankan `pip install patchright` |
| Browser tidak terbuka | Jalankan `patchright install chromium` |
| Turnstile selalu timeout | Coba tanpa proxy dulu, atau ganti proxy |
| Form tidak terisi | Cek dan update selector di `queue_handler.py` |
| Telegram tidak terima notif | Pastikan bot sudah di-/start di chat Telegram |
