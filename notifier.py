"""
notifier.py — Modul notifikasi Telegram.
Mengirim pesan ke chat Telegram saat event penting terjadi.
"""

import requests
import time


def send_telegram(config: dict, message: str) -> bool:
    """
    Kirim pesan ke Telegram via Bot API.

    Args:
        config: Dict konfigurasi dari config.json
        message: Pesan yang ingin dikirim

    Returns:
        True jika berhasil, False jika gagal.
    """
    tg_cfg = config.get("telegram", {})
    bot_token = tg_cfg.get("bot_token", "")
    chat_id = tg_cfg.get("chat_id", "")

    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
        print("[Notifier] ⚠️  Telegram token belum dikonfigurasi, skip notifikasi.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[Notifier] ✅ Notifikasi Telegram terkirim.")
            return True
        else:
            print(f"[Notifier] ❌ Gagal kirim Telegram: {response.text}")
            return False
    except requests.RequestException as e:
        print(f"[Notifier] ❌ Error koneksi Telegram: {e}")
        return False


def notify_slot_found(config: dict, boutique: str):
    """Notifikasi saat slot antrean ditemukan."""
    msg = (
        "🟢 <b>SLOT ANTREAN TERSEDIA!</b>\n\n"
        f"🏪 Butik: <b>{boutique}</b>\n"
        f"⏰ Waktu: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "Bot sedang mengisi form antrean... ⚡"
    )
    send_telegram(config, msg)


def notify_success(config: dict, boutique: str):
    """Notifikasi saat form berhasil disubmit dan masuk ke halaman invoice."""
    msg = (
        "✅ <b>ANTREAN BERHASIL DIPESAN!</b>\n\n"
        f"🏪 Butik: <b>{boutique}</b>\n"
        f"⏰ Waktu: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "Segera cek halaman invoice kamu! 🎉"
    )
    send_telegram(config, msg)


def notify_error(config: dict, error_msg: str):
    """Notifikasi saat terjadi error fatal."""
    msg = (
        "🔴 <b>BOT ERROR</b>\n\n"
        f"❌ Error: {error_msg}\n"
        f"⏰ Waktu: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "Bot dihentikan. Cek terminal untuk detail."
    )
    send_telegram(config, msg)


def notify_retry(config: dict, attempt: int, max_retry: int):
    """Notifikasi saat bot melakukan retry."""
    msg = (
        f"🔄 <b>RETRY #{attempt}/{max_retry}</b>\n"
        f"Slot belum tersedia, bot mencoba lagi...\n"
        f"⏰ {time.strftime('%H:%M:%S')}"
    )
    send_telegram(config, msg)
