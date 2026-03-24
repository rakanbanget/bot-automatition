"""
proxy_manager.py — Modul manajemen Residential Proxy.
Memformat konfigurasi proxy dari config.json ke format Patchright.
"""

from __future__ import annotations
from typing import Optional


def get_proxy_config(config: dict) -> Optional[dict]:
    """
    Konversi config proxy ke format yang dikenali Patchright/Playwright.

    Returns:
        dict dengan server, username, password — atau None jika proxy tidak dikonfigurasi.
    """
    proxy_cfg = config.get("proxy", {})

    host = proxy_cfg.get("host", "")
    port = proxy_cfg.get("port", 0)
    username = proxy_cfg.get("username", "")
    password = proxy_cfg.get("password", "")

    # Jika host masih placeholder, skip proxy
    if not host or host == "PROXY_HOST":
        print("[Proxy] ⚠️  Proxy tidak dikonfigurasi, berjalan tanpa proxy.")
        return None

    proxy = {
        "server": f"http://{host}:{port}",
        "username": username,
        "password": password,
    }

    print(f"[Proxy] ✅ Menggunakan proxy: {host}:{port} (user: {username})")
    return proxy


def validate_proxy_config(config: dict) -> bool:
    """Validasi apakah semua field proxy sudah diisi."""
    proxy_cfg = config.get("proxy", {})
    required_fields = ["host", "port", "username", "password"]

    for field in required_fields:
        val = proxy_cfg.get(field)
        if not val or str(val) in ["PROXY_HOST", "PROXY_USER", "PROXY_PASS", "0", ""]:
            print(f"[Proxy] ❌ Field proxy '{field}' belum dikonfigurasi di config.json.")
            return False

    return True
