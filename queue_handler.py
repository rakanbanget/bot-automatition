"""
queue_handler.py — Modul logika antrean Antam.
Target: https://antrean.logammulia.com/

Flow website:
  1. Login dengan email/WA + password
  2. Masuk ke halaman antrean
  3. Pilih butik (outlet)
  4. Klik "Ambil Antrean"
  5. Isi data jika diperlukan → Submit
  6. Verifikasi berhasil
"""

import asyncio
import random
from stealth import human_delay, random_mouse_movement, human_click, human_type


# ─── URL ────────────────────────────────────────────────
BASE_URL       = "https://antrean.logammulia.com"
LOGIN_URL      = f"{BASE_URL}/login"
QUEUE_URL      = f"{BASE_URL}/antrean"
REGISTER_URL   = f"{BASE_URL}/register"

# ─── CSS Selectors ──────────────────────────────────────
SELECTORS = {
    # ── Login page
    "login_email":    "input[name='email'], input[type='email'], input#email, input[name='username'], input#username, input[placeholder*='sername'], input[placeholder*='mail']",
    "login_password": "input[name='password'], input[type='password'], input#password",
    "login_btn":      "button[type='submit'], input[type='submit'], button.btn-login, button:has-text('Masuk'), button:has-text('Login')",

    # ── Butik / outlet dropdown (setelah login)
    "boutique_select": "select[name='site'], select[name='lokasi'], select[name='outlet_id'], select[name='office_id'], select#outlet_id, select#office_id, select.select-butik, select.form-select, select",

    # ── Tombol Ambil Antrean
    "queue_button": "button:has-text('Ambil Antrean'), a:has-text('Ambil Antrean'), button.btn-antrean, a.btn-antrean, button[id*='antrean'], a[href*='antrean/ambil']",

    # ── Form data diri (jika diminta setelah klik Ambil Antrean)
    "field_nik":   "input[name='nik'], input[name='ktp'], input#nik, input[placeholder*='NIK'], input[placeholder*='KTP']",
    "field_nama":  "input[name='nama'], input[name='name'], input#nama, input#name, input[placeholder*='Nama']",
    "field_hp":    "input[name='no_hp'], input[name='phone'], input[name='whatsapp'], input#no_hp, input[placeholder*='WhatsApp'], input[placeholder*='HP']",
    "field_email": "input[name='email'], input[type='email'], input#email",

    # ── Submit form antrean
    "submit_btn": "button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Ambil'), button:has-text('Daftar')",

    # ── Indikator sukses
    "success_indicator": ".success, .alert-success, .nomor-antrean, #nomor-antrean, h2.success, p:has-text('berhasil'), p:has-text('Antrean Anda')",

    # ── Indikator slot tidak tersedia
    "unavailable_indicator": ".alert-danger:has-text('penuh'), .alert-warning:has-text('habis'), p:has-text('Kuota Penuh'), p:has-text('Tidak Tersedia'), .kuota-habis",

    # ── Turnstile iframe
    "turnstile_iframe": "iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile']",

    # ── Indikator sudah login (elemen yang ada di dashboard)
    "logged_in_indicator": ".navbar-brand, nav.navbar, .user-profile, a[href*='logout'], a:has-text('Keluar')",
}


# ─────────────────────────────────────────────────────────
# TURNSTILE
# ─────────────────────────────────────────────────────────

async def check_cf_clearance(context, page, max_wait: int = 90) -> bool:
    """Verifikasi mutlak bahwa cookie cf_clearance sudah tertanam di browser dengan anti-stuck reload."""
    print(f"\n[Cookie Validator] ⏳ Memulai pengecekan cookie 'cf_clearance' (Max {max_wait} detik)...")
    for sec in range(1, max_wait + 1):
        cookies = await context.cookies()
        
        cf_cookie = next((c for c in cookies if c.get('name') == 'cf_clearance'), None)
        if cf_cookie:
            val = cf_cookie.get('value', '')
            print(f"[Cookie Validator] ✅ Detik ke-{sec}: cf_clearance DIDAPATKAN!")
            print(f"   └─ Payload: {val[:35]}...[TRUNCATED]")
            return True
            
        print(f"[Cookie Validator] ❌ Detik ke-{sec}: cf_clearance masih MISSING...")
        await asyncio.sleep(1.0)
        
    print("[Cookie Validator] 🚨 90 Detik berlalu tanpa cf_clearance. Mengeksekusi page.reload() Anti-Stuck...")
    
    try:
        await page.reload(wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5.0)
        
        # Re-check satu kali lagi setelah reload
        cookies = await context.cookies()
        if any(c.get('name') == 'cf_clearance' for c in cookies):
            print("[Cookie Validator] ✅ Cookie cf_clearance ajaibnya muncul paska-reload!")
            return True
    except Exception as e:
        print(f"[Cookie Validator] ❌ Reload gagal: {e}")

    print("[Cookie Validator] 🚨 FATAL: cf_clearance tetap hilang. Terindikasi IP Block / Silent Trap.")
    return False

async def wait_for_recaptcha(page, timeout_seconds: int = 45) -> bool:
    """Mendeteksi dan mencoba menyelesaikan Google reCAPTCHA v2 (Checkbox fallback)."""
    try:
        # Cek apakah iframe recaptcha dipasang oleh WAF
        recaptcha_iframe = await page.query_selector('iframe[src*="recaptcha/api2/anchor"]')
        if not recaptcha_iframe:
            return True # Tidak ada recaptcha, aman

        print("\n[Security] 🛡️ Google reCAPTCHA v2 WAF Fallback terdeteksi! Mengeksekusi manuver klik...")
        
        # Dapatkan frame internal dari elemen iframe reCAPTCHA
        frame = await recaptcha_iframe.content_frame()
        if frame:
            checkbox = await frame.query_selector('.recaptcha-checkbox-border')
            if checkbox:
                # Hover dan klik bak manusia
                await checkbox.hover()
                await human_delay(0.5, 1.2)
                await checkbox.click()
                print("[Security] 🖱️ Checkbox reCAPTCHA diklik.")
                
                # Tunggu animasi sinkronisasi selesai
                print("[Security] ⏳ Menunggu tantangan sinkron (Max 45s)...")
                
                for attempt in range(timeout_seconds):
                    # Cek apakah ceklis hijau sudah muncul
                    is_checked = await frame.evaluate("document.querySelector('.recaptcha-checkbox').getAttribute('aria-checked')")
                    if is_checked == "true":
                        print("[Security] ✅ Google reCAPTCHA berhasil di-Bypass!")
                        await human_delay(1.0, 2.0)
                        return True
                        
                    # Cek apakah muncul image puzzle (bisa dicek dari iframe bframe yang muncul di halaman utama)
                    puzzle_iframe = await page.query_selector('iframe[src*="recaptcha/api2/bframe"]')
                    if puzzle_iframe:
                        box = await puzzle_iframe.bounding_box()
                        # Jika puzzle terlihat di layar (bukan hidden)
                        if box and box['width'] > 0 and box['height'] > 0:
                            if attempt % 5 == 0:
                                print("\n[Security] 🚨 ALERT: reCAPTCHA meminta Image Puzzle (Lampu Merah / Zebra Cross)!")
                                print("[Security] 🚨 ALERT: Silakan lengkapi puzzle SECARA MANUAL di layar browser sekarang juga!")
                                print("[Security] 🚨 ALERT: Bot akan menunggu sampai centang hijau muncul...\n")
                    
                    await asyncio.sleep(1.0)
                    
                print("[Security] ❌ Timeout menunggu Google reCAPTCHA.")
                return False
        return True
    except Exception as e:
        print(f"[Security] ⚠️ Gagal klik reCAPTCHA: {e}")
        return False


async def wait_for_turnstile(page, timeout_seconds: int = 60) -> bool:
    """
    Tunggu hingga Cloudflare Turnstile selesai.
    Jika muncul checkbox "Buktikan bahwa Anda adalah manusia", bot akan mencoba mengkliknya
    dengan gerakan kursor simulasi manusia. Juga mengatasi reCAPTCHA v2 Fallback.
    """
    # ── Eksekusi Pemindaian WAF Fallback (Google reCAPTCHA) sebelum Turnstile
    await wait_for_recaptcha(page, timeout_seconds)
    
    print(f"[Queue] ⏳ Menunggu Cloudflare Turnstile (max {timeout_seconds}s)...")

    for elapsed in range(0, timeout_seconds, 2):
        # 1. Cek apakah halaman sedang dalam cengkraman Cloudflare
        title = await page.title()
        is_cf_active = (
            any("challenges.cloudflare.com" in f.url for f in page.frames) or
            "Tunggu sebentar" in title or
            "Just a moment" in title
        )
        
        if not is_cf_active:
            current_url = page.url
            if "challenges.cloudflare.com" not in current_url:
                print(f"[Queue] ✅ Tidak terdeteksi Turnstile, lanjut ({elapsed}s).")
                return True

        # 2. Cek token turnstile di DOM (berarti sudah lolos otomatis)
        token = await page.evaluate("""
            () => {
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                return input ? input.value : '';
            }
        """)

        if token and len(token) > 10:
            print(f"[Queue] ✅ Token Turnstile terisi dalam ~{elapsed}s!")
            
            # Simulasi gerakan mouse kecil paska-centang
            print("[Queue] 🛡️ Simulasi mouse trigger manual di sekitar Turnstile...")
            await random_mouse_movement(page, steps=3)
            
            # Tunggu validasi cookie mutlak dengan anti-stuck reload
            is_cleared = await check_cf_clearance(page.context, page, max_wait=90)
            if is_cleared:
                await human_delay(1.0, 2.5)
                return True
                
            return False

        # 3. Coba cari dan klik interaktif checkbox Turnstile
        try:
            for frame in page.frames:
                if "challenges.cloudflare.com" in frame.url:
                    # Cloudflare Turnstile checkbox biasanya adalah element input atau label
                    # Coba klik body atau target spesifik jika ada
                    ctc_checkbox = await frame.query_selector("input[type='checkbox'], .ctc-checkbox, label")
                    if ctc_checkbox:
                        if elapsed % 4 == 0:
                            print(f"[Queue] 🛡️ Mencoba klik checkbox Turnstile (detik ke-{elapsed})...")
                            try:
                                # Hover secara otomatis menghitung koordinat viewport absolut menembus iframe
                                await ctc_checkbox.hover(timeout=3000)
                                await asyncio.sleep(random.uniform(0.6, 1.5))
                                
                                # Realistic mousedown/mouseup native
                                await page.mouse.down()
                                await asyncio.sleep(random.uniform(0.07, 0.2))
                                await page.mouse.up()
                            except Exception as e:
                                print(f"[Queue] ❌ Gagal klik checkbox: {e}")
                    else:
                        # Fallback klik tengah iframe jika checkbox specifik tidak ketemu
                        if elapsed in (4, 10, 16):
                            body = await frame.query_selector("body")
                            if body:
                                try:
                                    print(f"[Queue] 🛡️ Fallback klik area Turnstile (detik ke-{elapsed})...")
                                    await body.hover(timeout=3000)
                                    await asyncio.sleep(0.4)
                                    await page.mouse.down()
                                    await asyncio.sleep(0.1)
                                    await page.mouse.up()
                                except Exception:
                                    pass
        except Exception as e:
            pass

        # Gerakan acak tambahan
        if elapsed % 6 == 0 and elapsed > 0:
            await random_mouse_movement(page, steps=2)

        await asyncio.sleep(2)

    print(f"[Queue] ❌ Turnstile timeout setelah {timeout_seconds}s.")
    return False


# ─────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────

async def is_logged_in(page) -> bool:
    """Cek apakah user sudah login dengan melihat elemen navbar/profil."""
    try:
        element = await page.query_selector(SELECTORS["logged_in_indicator"])
        return element is not None
    except Exception:
        return False


async def do_login(page, config: dict) -> bool:
    """
    Login ke antrean.logammulia.com dengan email dan password dari config.

    Returns:
        True jika login berhasil.
    """
    personal = config.get("personal_data", {})
    email = personal.get("email", "")
    password = personal.get("password", "")

    if not email or not password or password == "PASSWORD_KAMU":
        print("[Queue] ❌ Email atau password belum diisi di config.json!")
        return False

    print(f"[Queue] 🔐 Mencoba login dengan: {email}")

    try:
        # Buka halaman login
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        await human_delay(1.5, 3.0)

        # Tunggu Turnstile di halaman login
        await wait_for_turnstile(page, timeout_seconds=45)

        # Isi email (Bersihkan autonya jika ada autofill browser)
        email_field = await page.query_selector(SELECTORS["login_email"])
        if email_field:
            await email_field.fill("")
            await human_type(page, SELECTORS["login_email"], email)
            await human_delay(0.5, 1.2)

        # Isi password (Bersihkan field terlebih dahulu)
        password_field = await page.query_selector(SELECTORS["login_password"])
        if password_field:
            await password_field.fill("")
            await human_type(page, SELECTORS["login_password"], password)
            await human_delay(0.8, 1.5)

        # Solve Math Challenge
        math_solved = await solve_math_challenge(page)
        if not math_solved:
            print("[Queue] ⚠️ Peringatan: Gagal/Timeout menyelesaikan Math Captcha saat Login. Melanjutkan sisa skrip (semoga sudah valid).")

        # Klik tombol login
        await human_click(page, SELECTORS["login_btn"])
        await human_delay(2.0, 4.0)

        # Verifikasi login berhasil
        if await is_logged_in(page):
            print("[Queue] ✅ Login berhasil!")
            return True
        else:
            current_url = page.url
            print(f"[Queue] ❌ Login gagal. URL sekarang: {current_url}")
            return False

    except Exception as e:
        print(f"[Queue] ❌ Error saat login: {e}")
        return False


# ─────────────────────────────────────────────────────────
# ANTREAN
# ─────────────────────────────────────────────────────────

async def solve_math_challenge(page) -> bool:
    """Selesaikan captcha matematika NLP secara general. Cek DOM untuk pertanyaan."""
    for attempt_math in range(8):
        try:
            page_text = await page.inner_text("body")
            import re
            
            # Menangkap SEMUA variasi kalimat dari Antam (termasuk 'Hitunglah 6 dikali 2 ?')
            m = re.search(r'(?i)(?:berapa|hasil|hitunglah)[^\d]*(\d+)\s+(ditambah|dikurangi|dikali|[-+*])\s+(\d+)', page_text)
            if m:
                num1, op_str, num2 = m.groups()
                print(f"[Queue] 🧠 Deteksi teks Captcha murni: '{m.group(0).strip()}'")
                
                n1, n2 = int(num1), int(num2)
                op_str = op_str.lower()
                if op_str in ['ditambah', '+']:
                    ans = n1 + n2
                elif op_str in ['dikurangi', '-']:
                    ans = n1 - n2
                else:
                    ans = n1 * n2
                print(f"[Queue] 🧠 Math Challenge Solver: {num1} {op_str} {num2} = {ans}")
                
                # Spesifikasi input (Tambah input[type='number'] untuk /masuk-pool)
                captcha_selectors = 'input[placeholder*="Jawaban"], input[placeholder*="Kode"], input[name*="captcha"], input[id*="captcha"], input[name*="math"], input[id*="math"], .math-captcha, input[type="number"]'
                captcha_input = await page.query_selector(captcha_selectors)
                if captcha_input:
                    await captcha_input.fill("")
                    await human_type(page, captcha_selectors, str(ans))
                    await human_delay(0.5, 1.0)
                    # Submit otomatis jika ada tombol 'Jawab' atau 'Verify' /masuk-pool
                    solve_btn = page.locator("button:has-text('Kirim'), button:has-text('Jawab'), button:has-text('Submit'), button:has-text('Verifikasi'), button:has-text('Verify')")
                    if await solve_btn.count() > 0 and await solve_btn.first.is_visible():
                        await human_click(page, "button:has-text('Kirim'), button:has-text('Jawab'), button:has-text('Submit'), button:has-text('Verifikasi'), button:has-text('Verify')")
                        await human_delay(1.0, 2.0)
                    return True
                else:
                    print("[Queue] ⚠️ Kotak input Captcha tidak ditemukan!")
            else:
                print(f"[Queue] ⏱️ Math Captcha belum ter-render di body. Retry {attempt_math + 1}/8...")
                await asyncio.sleep(1.0)
                
        except Exception as e:
            print(f"[Queue] ⚠️ Math solver error: {e}")
            await asyncio.sleep(1.0)
            
    return False

async def navigate_to_queue(page) -> bool:
    """Navigasi ke halaman antrean utama."""
    try:
        print(f"[Queue] 🌐 Navigasi ke halaman antrean: {QUEUE_URL}")
        await page.goto(QUEUE_URL, wait_until="domcontentloaded", timeout=30000)
        await human_delay(1.5, 3.0)
        return True
    except Exception as e:
        print(f"[Queue] ❌ Gagal navigasi ke queue: {e}")
        return False


async def check_quota(page, boutique_name: str) -> tuple[bool, int]:
    """Cek apakah masih ada sisa kuota antrean untuk butik tertentu.
    Returns:
        (is_available, cooldown_seconds)
    """
    print(f"[Queue] 🔍 Pengecekan Kuota Butik: {boutique_name}")

    # 1. Pilih Butik (termasuk strict verification)
    success_select = await select_boutique(page, boutique_name)
    if not success_select:
        return False, 0

    # 2. Klik Tampilkan Butik
    try:
        btn = await page.query_selector("button:has-text('Tampilkan Butik'), button:has-text('Tampilkan'), input[value*='Tampil']")
        if btn:
            await btn.click()
            print("[Queue] 📋 Klik 'Tampilkan Butik'")
            await human_delay(1.5, 3.0)
        else:
            print("[Queue] ⚠️  Tombol 'Tampilkan Butik' tidak ditemukan, menunggu auto-load...")
            await human_delay(2.0, 3.0)
    except Exception as e:
        print(f"[Queue] ⚠️  Gagal klik tampilkan: {e}")

    # 3. Evaluasi Kuota
    try:
        # Tunggu sampai teks kuota muncul (tersedia atau tidak)
        await page.wait_for_selector("text='Kuota Tersedia', text='Kuota Tidak Tersedia'", timeout=8000)
    except:
        pass

    page_text = await page.inner_text("body")
    page_text_lower = page_text.lower()
    
    import re
    import datetime
    
    # 1. Deteksi Jadwal Buka (Smart Standby Mode) DULUAN!
    # Mencegah bot tertipu Sisa: 25 padahal sesi aslinya baru buka jam 11:00.
    schedule_match = re.search(r'(?:dibuka|buka|terbuka|sesi waktu ambil antrean.*?:)\s+(?:di\s+jam|pada\s+pukul|pada\s+jam|jam\s+pukul|jam|pukul|pada)?\s*(\d{1,2}[:.]\d{2})', page_text_lower)
    if schedule_match:
        time_str = schedule_match.group(1).replace('.', ':')
        try:
            now = datetime.datetime.now()
            parts = time_str.split(':')
            target = now.replace(hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0)
            
            # Jika target masih di depan (misal sekarang 10:16, target 11:00) -> Hold!
            if target > now:
                print(f"[Queue] 🕗 Butik {boutique_name} TERJADWAL PUKUL {time_str}! Mengaktifkan mode Standby.")
                cooldown_sec = (target - now).total_seconds()
                cooldown_sec -= 60 # Mulai bersiap 1 menit sebelum buka
                if cooldown_sec > 0:
                    return False, int(cooldown_sec)
            # Jika target <= now, berarti sesi sedang berlangsung. Terus turun ke Cek Kuota!
        except Exception as e:
            print(f"[Queue] ⚠️ Parsing jadwal '{time_str}' gagal: {e}")

    # 2. Cek Sisa Kuota
    # Mencari pola "sisa : 10" atau "sisa: 0"
    match = re.search(r'sisa\s*:\s*(\d+)', page_text_lower)
    
    if match:
        sisa = int(match.group(1))
        if sisa > 0:
            print(f"[Queue] 🟢 Kuota TERSEDIA! Sisa slot: {sisa}")
            return True, 0
        else:
            print("[Queue] 🔴 Kuota PENUH (Sisa: 0). Menunggu delay anti-stuck (3-6s)...")
            await asyncio.sleep(random.uniform(3.0, 6.0))
            return False, 0

    # 5. Fallback murni teks untuk penolakan
    if "kuota tidak tersedia" in page_text_lower or "kuota antrean tidak tersedia" in page_text_lower or "tidak tersedia" in page_text_lower:
        print("[Queue] 🔴 Kuota TIDAK Tersedia (Text). Delay anti-stuck...")
        await asyncio.sleep(random.uniform(3.0, 6.0))
        return False, 0

    print("[Queue] 🔴 Status kuota tidak terbaca dengan jelas. Loop diulang.")
    return False, 0

async def select_waktu_kedatangan(page) -> bool:
    """Pilih waktu kedatangan (dropdown/radio) pertama yang tersedia."""
    try:
        # Skenario 1: Coba Native Dropdown Select secara Global
        try:
            # Ambil seluruh elemen <select> yang ada tanpa mempedulikan id/name
            all_selects = await page.query_selector_all("select")
            for sel in all_selects:
                options = await sel.query_selector_all("option")
                for opt in options:
                    text_content = await opt.inner_text()
                    if "Tersedia" in text_content or "✅" in text_content:
                        val = await opt.get_attribute("value")
                        if val and val.strip() and val != "0" and val != "": # Hindari placeholder
                            await sel.select_option(value=val)
                            print(f"[Queue] 🕒 Waktu kedatangan dipilih (Native Override): {text_content.strip()}")
                            return True
        except:
            pass
            
        # Skenario 2: Coba Custom Dropdown SPA (Pilih Waktu Kedatangan)
        # Cek apakah opsi sudah terbuka lebar di layar tanpa harus diklik
        available_option = page.locator("li, .splide__slide, .dropdown-item, .option, div[class*='option']").filter(has_text="Tersedia")
        if await available_option.count() > 0 and await available_option.first.is_visible():
            text_content = await available_option.first.inner_text()
            await available_option.first.click()
            print(f"[Queue] 🕒 Waktu kedatangan diklik langsung: {text_content.strip()}")
            return True
            
        # Cari trigger yang memunculkan list overlay dropdown (pake regex agar ga peduli spasi/simbol)
        trigger = page.locator("text=/Pilih Waktu Kedatangan/i, text=/Pilih Waktu/i, select-time")
        if await trigger.count() > 0:
            print(f"[Queue] ⚠️ Menyesuaikan interaksi Dropdown Waktu ke mode Custom/SPA... ({await trigger.first.inner_text()})")
            await trigger.first.click()
            await human_delay(1.0, 2.0)
            
            # Cari elemen list/opsi dropdown yang TEPAT berisi slot kosong, abaikan yang 'Penuh'
            if await available_option.count() > 0:
                text_content = await available_option.first.inner_text()
                await available_option.first.click()
                print(f"[Queue] 🕒 Waktu kedatangan dipilih (Custom): {text_content.strip()}")
                return True
            else:
                print("[Queue] 🔴 Opsi SPA Dropdown terbuka, tapi SEMUA JAM PENUH / tidak ada 'Tersedia'!")
                return False
                
    except Exception as e:
        print(f"[Queue] ⚠️ Gagal pilih Waktu Kedatangan: {e}")
        return False
        
    print("[Queue] ℹ️ Pilihan Waktu Kedatangan tidak ditemukan layar, mungkin auto-assigned.")
    return True


async def click_queue_button(page) -> bool:
    """Klik tombol 'Ambil Antrean' dan tangani modal penolakan Bootstrap."""
    try:
        # PROTEKSI RACE-CONDITION: Jika telat, modal "Mohon Maaf, Antrean sudah Tutup" mungkin muncul instan.
        modal_tutup = page.locator("text='Mohon Maaf, Antrean sudah Tutup'")
        if await modal_tutup.count() > 0 and await modal_tutup.first.is_visible():
            print("[Queue] ❌ Race condition: Muncul SweetAlert 'Antrean sudah Tutup' dari Antam!")
            ok_btn = page.locator("button:has-text('OK')")
            if await ok_btn.count() > 0:
                await ok_btn.first.click()
            return False

        # Klik tombol aslinya
        await human_click(page, SELECTORS["queue_button"])
        print("[Queue] 📋 Tombol Ambil Antrean diklik.")
        await human_delay(1.5, 3.0)
        return True
    except Exception as e:
        print(f"[Queue] ❌ Gagal klik tombol antrean: {e}")
        return False


async def select_boutique(page, boutique_name: str) -> bool:
    """Pilih butik dari dropdown dengan dukungan Native & Custom Dropdown."""
    try:
        # Stabilisasi halaman jika terjadi silent reload
        print("[Queue] ⏳ Menunggu stabilisasi halaman paska-Turnstile (5 detik)...")
        await asyncio.sleep(5.0)
        
        print(f"[Queue] ⏳ Mencari elemen dropdown untuk butik '{boutique_name}'...")
        
        # Skenario 1: Cek apakah ada native <select> yang visible (Fallback)
        try:
            select = await page.wait_for_selector(SELECTORS["boutique_select"], state="visible", timeout=3000)
            if select:
                print("[Queue] ✅ Dropdown native ditemukan! Menyeleksi butik...")
                await select.select_option(label=boutique_name)
                print(f"[Queue] 🏪 Butik dipilih: {boutique_name}")
                await human_delay(1.0, 2.0)
                return True
        except:
            pass
            
        # Skenario 2: Custom Dropdown (React/Bootstrap/Select2)
        print("[Queue] ⚠️ Dropdown native tidak terlihat/tersembunyi. Mengeksekusi manuver klik Custom Dropdown...")
        
        # Klik string placeholder layar "-- Pilih BELM --"
        trigger = page.locator("text='Pilih BELM'")
        if await trigger.count() > 0:
            await trigger.first.click()
            print(f"[Queue] 🖲️ Trigger dropdown '{await trigger.first.inner_text()}' diklik.")
            await human_delay(1.0, 2.0)
            
            # Cari string target butik di list terbang
            option = page.locator(f"text='{boutique_name}'").last
            if await option.count() > 0:
                await option.click()
                print(f"[Queue] 🏪 Butik (Custom Dropdown) berhasil dipilih: {boutique_name}")
                await human_delay(1.0, 2.0)
                return True
            else:
                print(f"[Queue] ❌ Target butik '{boutique_name}' tidak muncul dalam list Custom Dropdown!")
                return False
        else:
            print("[Queue] ❌ Teks '-- Pilih BELM --' tidak terlihat di layar!")
            return False
            
    except Exception as e:
        print(f"[Queue] ❌ Strict Verification Gagal: {e}")
        return False


async def fill_personal_data(page, personal_data: dict) -> bool:
    """Isi form data diri (jika form muncul setelah klik Ambil Antrean)."""
    fields = {
        SELECTORS["field_nik"]:   personal_data.get("no_ktp", ""),
        SELECTORS["field_nama"]:  personal_data.get("nama_lengkap", ""),
        SELECTORS["field_hp"]:    personal_data.get("no_hp", ""),
        SELECTORS["field_email"]: personal_data.get("email", ""),
    }

    filled_any = False
    for selector, value in fields.items():
        if not value:
            continue
        try:
            element = await page.query_selector(selector)
            if element:
                await human_type(page, selector, value)
                await human_delay(0.5, 1.2)
                filled_any = True
        except Exception as e:
            print(f"[Queue] ⚠️  Gagal isi field: {e}")

    if filled_any:
        print("[Queue] 📝 Data diri selesai diisi.")
    else:
        print("[Queue] ℹ️  Tidak ada form data diri ditemukan (mungkin sudah dari akun).")

    return True


async def submit_queue_form(page) -> bool:
    """Submit form antrean."""
    try:
        submit = await page.query_selector(SELECTORS["submit_btn"])
        if submit:
            await human_click(page, SELECTORS["submit_btn"])
            print("[Queue] 📤 Form antrean disubmit.")
            await human_delay(2.0, 4.0)
            return True
        else:
            # Mungkin form tidak ada, antrean langsung dikonfirmasi
            print("[Queue] ℹ️  Tidak ada form submit, antrean mungkin langsung dikonfirmasi.")
            return True
    except Exception as e:
        print(f"[Queue] ❌ Gagal submit form: {e}")
        return False


async def verify_invoice_success(page, timeout: int = 15) -> bool:
    """Verifikasi apakah berhasil mendapatkan nomor antrean / invoice atau masuk ruang tunggu."""
    is_success = False
    
    print("[Queue] ⏳ Memverifikasi status hasil akhir (Invoice / Ruang Tunggu)...")
    
    # Heuristik Ruang Tunggu Tertahan (Hold / Wait Loop)
    waiting_heuristics = ["ruang tunggu", "menunggu giliran", "harap tunggu", "mengundi", "diproses", "waiting"]
    
    # Tunggu beberapa detik untuk render awal
    await asyncio.sleep(3.0)
    
    for _ in range(360): # Max hold 1 jam di ruang tunggu (360 putaran x 10 detik)
        current_url = page.url.lower()
        try:
            page_text = (await page.inner_text("body")).lower()
        except:
            page_text = ""
            
        # 1. Cek Sukses Mutlak
        if any(kw in current_url for kw in ["sukses", "success", "nomor", "konfirmasi", "antrean/", "invoice"]):
            print(f"[Queue] 🎉 BERHASIL! Rute sukses terdeteksi: {current_url}")
            is_success = True
            break
            
        try:
            if await page.query_selector(SELECTORS["success_indicator"]):
                print("[Queue] 🎉 BERHASIL mendapatkan antrean (Indikator DOM muncul)!")
                is_success = True
                break
        except:
            pass
            
        if "berhasil" in page_text and "antrean" in page_text and "nomor" in page_text:
            print("[Queue] 🎉 BERHASIL! (Teks sukses terdeteksi di layar).")
            is_success = True
            break
            
        # 2. Cek Ruang Tunggu (Berdasarkan Info Tanggal 25)
        if "ruang-tunggu" in current_url or any(w in page_text for w in waiting_heuristics):
            print("[Queue] 🕒 Anda berada di RUANG TUNGGU! Menunggu antrean (Bot siaga menjaga sesi)...")
            
            # RUANG TUNGGU DEFENSE: Kadang disuruh isi Math Captcha selagi nunggu!
            math_solved = await solve_math_challenge(page)
            if math_solved:
                print("[Queue] 🧮 Math Captcha di Ruang Tunggu berhasil diselesaikan!")
            
            await asyncio.sleep(5.0)
            continue # Terus memutar loop hold
            
        # 3. Cek Penolakan / Gagal Mutlak di ujung
        if "kuota habis" in page_text or "tidak terpilih" in page_text or "kuota penuh" in page_text or "slot penuh" in page_text or "antrean penuh" in page_text:
            print("[Queue] 💔 Server menolak / Kuota meluap saat di dalam ruang tunggu.")
            return False
            
        # 4. Cek Post-Submit Math Captcha Interception (Modal atau url /masuk-pool)
        try:
            if "masuk-pool" in current_url:
                print("[Queue] ⚠️ Terdeteksi URL /masuk-pool (Math Captcha Pra-Antrean)!")
                await solve_math_challenge(page)
                await asyncio.sleep(2.0)
                continue
                
            math_modal = page.locator("text=/hasil penjumlahan/i, text=/hasil pengurangan/i, text=/Berapa hasil/i, text=/hitunglah /i")
            if await math_modal.count() > 0 and await math_modal.first.is_visible():
                print("[Queue] ⚠️ Terdeteksi Math Captcha pasca-submit (Modal)!")
                await solve_math_challenge(page)
                await asyncio.sleep(2.0)
                continue
        except:
            pass

        # Jika tidak ada trigger ruang tunggu dan tidak sukses selama timeout detik pertama, berarti gagal biasa.
        if _ > (timeout / 5): # Setiap iterasi = 5 detik
            break
            
        await asyncio.sleep(5.0)

    if is_success:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Evidence Capture: Ambil Full Page Screenshot
        screenshot_name = f"ANTREAN_BERHASIL_{timestamp}.png"
        try:
            await asyncio.sleep(2.0) # Tunggu animasi render selesai
            await page.screenshot(path=screenshot_name, full_page=True)
            print(f"[Queue] 📸 Bukti screenshot invoice disimpan ke: {screenshot_name}")
        except Exception as e:
            print(f"[Queue] ⚠️ Gagal simpan screenshot: {e}")
            
        # 2. Evidence Capture: Scraping Nomor Antrean & Simpan ke Txt
        nomor_antrean = "Tidak Tedeteksi Oleh Parser (Cek Gambar PNG)"
        try:
            # Selektor pencarian standar Invoice Antam
            nodes = await page.query_selector_all("h1, h2, h3, h4, .nomor-antrean, .ticket-number, strong")
            for node in nodes:
                text = await node.inner_text()
                if "BELM-" in text.upper() or "ANTREAN" in text.upper() or len(text) > 8:
                    nomor_antrean = text.strip()
                    if "BELM-" in text.upper():
                         break # Break jika ketemu referensi mutlak
        except:
            pass
            
        try:
            with open("data_cuan.txt", "a") as f:
                f.write(f"[{timestamp}] BERHASIL! Nomor Antrean: {nomor_antrean}\n")
            print(f"[Queue] 💾 Log nomor antrean '{nomor_antrean}' diamankan ke data_cuan.txt")
        except Exception as e:
            print(f"[Queue] ⚠️ Gagal append ke data_cuan.txt: {e}")
            
        return True
        
    print(f"[Queue] ❌ Indikator sukses tidak muncul. URL Fallback: {page.url}")
    return False

