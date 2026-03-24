"""
swarm.py — Antigravity Gold Hive Mind Coordinator
─────────────────────────────────────────────────
Koordinasi multi-proses antar 3 instance bot berjalan paralel.

Cara Kerja:
- Setiap bot memantau shard (irisan) butik miliknya masing-masing.
- Begitu SALAH SATU bot mendeteksi kuota terbuka, ia menulis
  "swarm_signal.json" sebagai sinyal siaran Global.
- Bot-bot lain yang sedang berpatroli akan mendeteksi file sinyal
  ini di setiap siklus loop mereka dan LANGSUNG berpindah haluan
  ke butik yang sudah terkonfirmasi buka, untuk ikut masuk
  ke Ruang Tunggu bersama-sama.
"""

import json
import os
import time
from pathlib import Path

SIGNAL_FILE = Path(__file__).parent / "swarm_signal.json"
SIGNAL_TTL_SECONDS = 120  # Sinyal kadaluarsa otomatis setelah 2 menit


def broadcast_open_slot(boutique_name: str, detected_by: str):
    """
    Dipanggil oleh bot yang MENEMUKAN kuota terbuka.
    Menulis sinyal ke swarm_signal.json agar dibaca bot lain.
    """
    payload = {
        "boutique": boutique_name,
        "detected_by": detected_by,
        "timestamp": time.time()
    }
    with open(SIGNAL_FILE, "w") as f:
        json.dump(payload, f)
    print(f"\n[🐝 Swarm] 📡 SIARAN: Kuota terbuka di '{boutique_name}' (oleh {detected_by})! "
          f"Semua bot akan konvergen ke target ini!")


def read_open_slot() -> str | None:
    """
    Dibaca oleh SETIAP bot di setiap siklus loop.
    Jika ada sinyal segar yang belum kedaluwarsa, kembalikan nama butiknya.
    Jika sinyal sudah kedaluwarsa atau tidak ada, kembalikan None.
    """
    if not SIGNAL_FILE.exists():
        return None

    try:
        with open(SIGNAL_FILE, "r") as f:
            data = json.load(f)

        age = time.time() - data.get("timestamp", 0)
        if age > SIGNAL_TTL_SECONDS:
            # Sinyal kedaluarsa, bersihkan
            SIGNAL_FILE.unlink(missing_ok=True)
            return None

        return data.get("boutique")
    except Exception:
        return None


def clear_signal():
    """
    Hapus sinyal setelah bot sukses booking (atau gagal).
    Agar bot lain tidak salah masuk ke butik yang sudah dead.
    """
    SIGNAL_FILE.unlink(missing_ok=True)
    print("[🐝 Swarm] 🗑️  Sinyal swarm dibersihkan.")


def get_shard(all_boutiques: list[str], account_id: int, total_accounts: int) -> list[str]:
    """
    Membagi array butik menjadi irisan merata berdasarkan ID akun.

    Contoh:
      13 butik, 3 akun:
      Akun 0 → butik [0,1,2,3,4]   (5 butik)
      Akun 1 → butik [5,6,7,8]      (4 butik)
      Akun 2 → butik [9,10,11,12]   (4 butik)
    """
    total = len(all_boutiques)
    base = total // total_accounts
    remainder = total % total_accounts

    shards = []
    idx = 0
    for i in range(total_accounts):
        size = base + (1 if i < remainder else 0)
        shards.append(all_boutiques[idx: idx + size])
        idx += size

    shard = shards[account_id] if account_id < len(shards) else []
    return shard
