"""
bot.py — Entry point utama Bot Antam "Antigravity-Gold"
========================================================
Bot otomatis antrean emas Antam (logammulia.com) menggunakan Patchright.

Cara pakai:
  python bot.py           — jalankan bot penuh
  python bot.py --test    — dry-run, hanya buka browser & cek halaman
  python bot.py --help    — tampilkan bantuan

Konfigurasi: edit config.json sebelum menjalankan.
"""

import asyncio
import json
import sys
import time
import traceback
from pathlib import Path

from patchright.async_api import async_playwright

from stealth import apply_stealth, human_delay, random_mouse_movement
from proxy_manager import get_proxy_config
from queue_handler import (
    wait_for_turnstile,
    check_quota,
    select_boutique,
    fill_personal_data,
    submit_queue_form,
    verify_invoice_success,
    do_login,
    navigate_to_queue,
    click_queue_button,
    select_waktu_kedatangan,
)
from notifier import notify_slot_found, notify_success, notify_error, notify_retry
from swarm import broadcast_open_slot, read_open_slot, clear_signal, get_shard


# ─────────────────────────────────────────────
# Konstanta
# ─────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "config.json"
LOG_SEP = "─" * 55


def load_config(config_file: str = "config.json") -> dict:
    """Load dan validasi config.json."""
    config_path = Path(__file__).parent / config_file
    if not config_path.exists():
        print(f"❌ {config_file} tidak ditemukan. Buat dari template yang tersedia.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    print(f"[Config] ✅ {config_file} berhasil dimuat.")
    return cfg


def print_banner():
    print(f"""
{LOG_SEP}
  🥇  Bot Antam - Antigravity Gold
     Target : logammulia.com/id/antrean
     Engine : Patchright (Stealth Chromium)
{LOG_SEP}
""")


def print_network_debug(request):
    """Intercept request log untuk melihat cookie dan user-agent cloudflare."""
    url = request.url
    if ("turnstile" in url or "logammulia.com" in url) and request.resource_type in ["document", "fetch", "xhr", "script"]:
        headers = request.headers
        ua = headers.get('user-agent', 'MISSING')
        cookie = headers.get('cookie', 'MISSING')
        
        print(f"\n[Network Inspector] 📡 {request.method} {request.resource_type.upper()} {url[:80]}...")
        print(f"   ├─ User-Agent : {ua}")
        print(f"   └─ Cookie     : {cookie[:100]}..." if cookie != "MISSING" else f"   └─ Cookie     : {cookie}")

def check_response_cookies(response):
    """Event listener untuk menandai masuknya Set-Cookie dari Cloudflare."""
    headers = response.headers
    set_cookie = headers.get('set-cookie', '')
    if 'cf_clearance' in set_cookie or '__cf_bm' in set_cookie:
        print("\n[Auth] 🔑 Cookie Cloudflare (cf_clearance/__cf_bm) ditemukan via Set-Cookie! Menyimpan sesi...")



# ─────────────────────────────────────────────
# Fungsi utama bot (satu siklus)
# ─────────────────────────────────────────────

async def run_bot_cycle(page, config: dict, dry_run: bool = False,
                        account_id: int = 0, total_accounts: int = 1, account_name: str = "Akun-1",
                        cooldowns: dict = None) -> bool:
    """
    Jalankan satu siklus lengkap bot:
    1. Login ke antrean.logammulia.com
    2. Tunggu Turnstile selesai
    3. Navigasi ke halaman antrean
    4. Deteksi slot
    5. Klik Ambil Antrean + isi form
    6. Verifikasi sukses

    Returns:
        True jika berhasil masuk antrean, False jika belum.
    """
    antam_cfg = config.get("antam", {})
    browser_cfg = config.get("browser", {})
    personal_data = config.get("personal_data", {})
    boutique = antam_cfg.get("boutique", "")
    turnstile_timeout = browser_cfg.get("turnstile_timeout_seconds", 60)
    
    if cooldowns is None:
        cooldowns = {}

    # ── Step 1: Navigasi & Login (atau cek sesi)
    print(f"\n[Bot] 🌐 Step 1: Navigasi ke halaman antrean")
    nav_ok = await navigate_to_queue(page)
    
    # Tunggu sebentar untuk memastikan laman loading sempurna
    await human_delay(1.5, 3.0)
    
    # Tangkap kemungkinan Cloudflare muncul di halaman pertama
    turnstile_early = await wait_for_turnstile(page, timeout_seconds=turnstile_timeout)
    if not turnstile_early:
        print("[Bot] ⚠️  Gagal menembus Cloudflare di pintu masuk URL. Retry.")
        return False
    
    # Cek apakah halaman mem-forward ke beranda / login karena belum ada sesi
    if "login" in page.url or "home" in page.url or "antrean" not in page.url:
        print("[Bot] 🔐 Sesi belum ada. Memulai proses Login...")
        login_ok = await do_login(page, config)
        if not login_ok:
            print("[Bot] ❌ Login gagal. Cek email/password di config.json")
            return False
            
        turnstile_done = await wait_for_turnstile(page, timeout_seconds=turnstile_timeout)
        if not turnstile_done:
            print("[Bot] ⚠️  Turnstile timeout dari fungsi Login, akan retry.")
            return False
            
        print("[Bot] 💾 Sesi persisten tersimpan otomatis di ./user_data")
        
        # Navigasi kembali ke halaman antrean utamanya
        nav_ok = await navigate_to_queue(page)
        if not nav_ok:
            return False
            
        # Kadang URL utama dihantam Cloudflare lagi
        turnstile_post = await wait_for_turnstile(page, timeout_seconds=turnstile_timeout)
        if not turnstile_post:
            return False
            
    title = await page.title()
    print(f"[Bot] ✅ Halaman: {title}")

    # ── Step 2: Cek Kuota (Swarm Shard + Signal Convergence)
    all_boutiques = antam_cfg.get("boutique", [])
    if isinstance(all_boutiques, str):
        all_boutiques = [all_boutiques]

    # Bagi array butik menjadi shard sesuai ID akun
    boutiques = get_shard(all_boutiques, account_id, total_accounts)
    if not boutiques:
        boutiques = all_boutiques  # fallback jika tidak ada swarm

    if dry_run:
        print(f"\n[Bot] 🧪 DRY-RUN [{account_name}]: Memindai {len(boutiques)} target butik (shard {account_id+1}/{total_accounts})...")
    else:
        print(f"\n[Bot] 🔍 [{account_name}] Step 2: Memindai Shard {account_id+1}/{total_accounts} — {len(boutiques)} Butik Target")
        print(f"[🐝 Swarm] Butik shard ini: {', '.join(boutiques)}")

    available_boutique = None

    # Prioritas: cek apakah ada sinyal dari bot lain terlebih dahulu
    swarm_signal = read_open_slot()
    if swarm_signal:
        print(f"\n[🐝 Swarm] 🚨 KONVERGENSI! Sinyal masuk dari bot lain → Butik '{swarm_signal}' TERBUKA!")
        print(f"[🐝 Swarm] Bot [{account_name}] navigasi ke target: {swarm_signal}")
        # Tetap harus pilih butik di dropdown agar halaman antrean terbuka dengan benar
        await navigate_to_queue(page)
        await human_delay(1.0, 2.0)
        quota_ok, _ = await check_quota(page, swarm_signal)
        if quota_ok:
            available_boutique = swarm_signal
            print(f"[🐝 Swarm] ✅ [{account_name}] Konfirmasi kuota di '{swarm_signal}' berhasil! Lanjut booking.")
        else:
            print(f"[🐝 Swarm] ❌ Kuota di '{swarm_signal}' sudah habis saat tiba. Kembali ke shard sendiri.")
            # Clear sinyal yang sudah basi lalu scan shard sendiri
            clear_signal()
    else:
        for b in boutiques:
            # 1. Cek apakah Butik ini sedang dalam masa Standby (belum buka)
            if b in cooldowns and time.time() < cooldowns[b]:
                sisa_waktu = int(cooldowns[b] - time.time())
                print(f"[Queue] ⏳ Butik '{b}' sedang dalam mode Standby. Sisa waktu: {sisa_waktu//60}m {sisa_waktu%60}s")
                continue

            print(f"\n[Queue] 🔍 [{account_name}] Memindai Kuota Butik: {b}")

            # Reset dropdown pra-pemindaian
            await navigate_to_queue(page)
            await human_delay(1.0, 2.0)

            quota_available, cooldown_sec = await check_quota(page, b)
            
            if cooldown_sec > 0:
                cooldowns[b] = time.time() + cooldown_sec
                print(f"[Queue] 🔒 Mengamankan '{b}' agar tidak discan lagi sampai {int(cooldown_sec//60)} menit ke depan.")
                continue
                
            if quota_available:
                available_boutique = b
                print(f"[Queue] 🎉 [{account_name}] KUOTA DITEMUKAN DI: {b}!")
                # Siaran ke semua bot lain via swarm signal
                broadcast_open_slot(b, account_name)
                break
            else:
                print(f"[Queue] 🔴 Kuota {b} TIDAK Tersedia. Lanjut...")
                await human_delay(1.5, 3.0)
            
    if not available_boutique:
        print(f"[Queue] 🔴 [{account_name}] Shard scan selesai. Semua target penuh. Cek sinyal Swarm...")
        # Satu kesempatan terakhir: mungkin bot lain baru saja nemu
        swarm_late = read_open_slot()
        if swarm_late:
            print(f"[🐝 Swarm] ⚡ Sinyal terlambat diterima → Konvergensi ke: {swarm_late}")
            await navigate_to_queue(page)
            await human_delay(1.0, 2.0)
            quota_ok, _ = await check_quota(page, swarm_late)
            if quota_ok:
                available_boutique = swarm_late
                print(f"[🐝 Swarm] ✅ Konfirmasi kuota di '{swarm_late}' berhasil! Lanjut booking.")
            else:
                print(f"[🐝 Swarm] ❌ Slot '{swarm_late}' sudah habis. Sinyal expired.")
                clear_signal()
                return False
        else:
            return False

    if dry_run:
        print("\n[Bot] 🧪 DRY-RUN MODE — Bot berhenti sebelum eksekusi Ambil Antrean & Isi Form.")
        print("[Bot] ✅ Multi-Pemindaian Butik berhasil! Stealth & Logic beroperasi 100%!")
        return True

    # Notifikasi slot ditemukan
    notify_slot_found(config, available_boutique)
    await human_delay(1.0, 2.0)

    # ── Step 3: Waktu Kedatangan & Ambil Antrean
    print(f"\n[Bot] 🕒 Step 3: Pilih Waktu Kedatangan & Klik Ambil Antrean")
    await select_waktu_kedatangan(page)
    await human_delay(0.5, 1.5)
    
    # Verifikasi Turnstile Inline (muncul pasca-waktu kedatangan)
    print(f"\n[Bot] 🛡️ Verifikasi Cloudflare Turnstile Inline")
    await wait_for_turnstile(page, timeout_seconds=turnstile_timeout)
    
    clicked = await click_queue_button(page)
    if not clicked:
        return False

    # ── Step 4: Isi data diri (jika form muncul)
    print(f"\n[Bot] 📝 Step 4: Isi form data diri")
    await fill_personal_data(page, personal_data)
    await human_delay(2.0, 4.0)

    # ── Step 5: Submit form
    submitted = await submit_queue_form(page)
    if not submitted:
        print("[Bot] ❌ Gagal submit. Akan retry.")
        return False

    # ── Step 6: Verifikasi sukses
    success = await verify_invoice_success(page)
    if success:
        notify_success(config, available_boutique)
        return True

    return False


# ─────────────────────────────────────────────
# Main — Loop utama
# ─────────────────────────────────────────────

async def main(dry_run: bool = False, config_file: str = "config.json", user_data_dir: str = "./user_data",
               account_id: int = 0, total_accounts: int = 1, account_name: str = "Akun-1"):
    print_banner()
    config = load_config(config_file)

    antam_cfg = config.get("antam", {})
    browser_cfg = config.get("browser", {})
    max_retry = antam_cfg.get("max_retry", 10)
    retry_delay = antam_cfg.get("retry_delay_seconds", 30)

    # Konfigurasi proxy
    proxy_cfg = get_proxy_config(config)

    async with async_playwright() as p:
        # ── Launch browser via Patchright (Persistent Context)
        print(f"[Bot] 🚀 Meluncurkan browser Patchright (Persistent Context di {user_data_dir})...")
        launch_kwargs = {
            "headless": browser_cfg.get("headless", False),
            "no_viewport": True,
            "args": [
                "--disable-blink-features=AutomationControlled"
            ],
            "extra_http_headers": {
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        }

        if proxy_cfg:
            launch_kwargs["proxy"] = proxy_cfg

        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            **launch_kwargs
        )

        # ── Gunakan halaman pertama di context atau buat baru
        page = context.pages[0] if context.pages else await context.new_page()
        
        # ── Pasang Interceptor Network
        page.on("request", print_network_debug)
        page.on("response", check_response_cookies)

        # ── Terapkan stealth
        await apply_stealth(page, config)

        print(f"[Bot] ✅ Browser siap. Menjalankan loop (max {max_retry}x retry)...\n")

        # Inisialisasi memori standby
        bot_cooldowns = {}

        # ── Loop retry utama
        for attempt in range(1, max_retry + 1):
            print(f"\n{LOG_SEP}")
            print(f"[Bot] 🔄 Percobaan ke-{attempt}/{max_retry} — {time.strftime('%H:%M:%S')}")
            print(f"{LOG_SEP}")

            try:
                success = await run_bot_cycle(page, config, dry_run=dry_run,
                                              account_id=account_id, total_accounts=total_accounts,
                                              account_name=account_name, cooldowns=bot_cooldowns)

                if success:
                    print(f"\n[Bot] 🎉 BERHASIL pada percobaan ke-{attempt}!")
                    break

                if dry_run:
                    break

            except Exception as e:
                err_msg = str(e)
                print(f"[Bot] ❌ Error tidak terduga: {err_msg}")
                print(traceback.format_exc())
                notify_error(config, err_msg)

            if not success and attempt < max_retry:
                print(f"\n[Bot] ⏳ Menunggu {retry_delay} detik sebelum retry...\n")

                # Kirim notifikasi retry setiap 5 kali
                if attempt % 5 == 0:
                    notify_retry(config, attempt, max_retry)

                await asyncio.sleep(retry_delay)

                # Reload halaman untuk retry bersih
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await human_delay(2.0, 4.0)
                except Exception:
                    pass

        if not success and not dry_run:
            print(f"\n[Bot] 😞 Bot berhenti setelah {max_retry} percobaan tanpa hasil.")
            notify_error(config, f"Bot berhenti setelah {max_retry} percobaan tanpa slot tersedia.")

        # ── Jangan tutup browser langsung di dry-run, biarkan user lihat
        if dry_run:
            print("\n[Bot] 🧪 Dry-run selesai. Browser dibiarkan terbuka 10 detik...")
            await asyncio.sleep(10)

        await context.close()
        print("[Bot] 🔒 Browser Persistent Context ditutup. Selesai.")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    import argparse
    parser = argparse.ArgumentParser(description="Bot Antam - Antigravity Gold")
    parser.add_argument("--test", action="store_true", help="Jalankan dalam mode simulasi/dry-run")
    parser.add_argument("--config", default="config.json", help="Path file konfigurasi spesifik akun")
    parser.add_argument("--user-data", default="./user_data", help="Folder isolasi cookie browser")
    parser.add_argument("--account-id", type=int, default=0, help="ID akun dalam Swarm (0-indexed). Contoh: 0, 1, 2")
    parser.add_argument("--total-accounts", type=int, default=1, help="Total akun/bot yang berjalan paralel")
    parser.add_argument("--account-name", default="Akun-1", help="Nama label akun untuk log")
    args = parser.parse_args()
    
    if args.test:
        print("🧪 Mode: DRY-RUN — Bot tidak akan mengisi/submit form.")
    else:
        print("⚡ Mode: FULL — Bot akan mengisi dan submit form antrean.")

    try:
        asyncio.run(main(
            dry_run=args.test,
            config_file=args.config,
            user_data_dir=args.user_data,
            account_id=args.account_id,
            total_accounts=args.total_accounts,
            account_name=args.account_name,
        ))
    except KeyboardInterrupt:
        print("\n[Bot] ⚠️  Dihentikan oleh user (Ctrl+C).")
        sys.exit(0)
