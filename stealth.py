"""
stealth.py — Modul stealth untuk bypass deteksi bot.
Mengelola User-Agent, viewport, penghapusan sinyal webdriver,
dan simulasi perilaku manusia (delay & gerakan kursor acak).
"""

import asyncio
import random


# Script JS untuk menghapus semua jejak otomasi Chromium
STEALTH_JS = """
// Hapus navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// Mock plugins & mimeTypes
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => [1, 2, 3, 4],
});

Object.defineProperty(navigator, 'languages', {
    get: () => ['id-ID', 'id', 'en-US', 'en'],
});

// Pastikan chrome object tersedia (seperti browser asli)
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {},
};

// Hapus automation flags
delete window.__playwright;
delete window.__pw_manual;
delete window.__patchright;

// Perbaiki permissions API
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

// WebGL Vendor spoofing untuk Cloudflare
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    // UNMASKED_VENDOR_WEBGL
    if (parameter === 37445) {
        return 'Intel Inc.';
    }
    // UNMASKED_RENDERER_WEBGL
    if (parameter === 37446) {
        return 'Intel Iris OpenGL Engine';
    }
    return getParameter.apply(this, [parameter]);
};

"""


STEALTH_JS = """
// Removed toxic property proxies. Patchright handles stealth natively at the CDP level.
"""

async def apply_stealth(page, config: dict):
    """
    Terapkan anti-deteksi JS murni.
    Dikosongkan karena Patchright versi terbaru bentrok jika disuntik JS
    (Cloudflare mendeteksi adanya Object.defineProperty getters palsu).
    """
    pass


async def human_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Jeda acak menyerupai perilaku manusia."""
    delay = random.uniform(min_sec, max_sec)
    print(f"[Stealth] ⏳ Human delay: {delay:.2f} detik...")
    await asyncio.sleep(delay)


async def random_mouse_movement(page, steps: int = 5):
    """Gerakkan kursor secara acak di layar untuk mensimulasikan manusia."""
    viewport = page.viewport_size
    if not viewport:
        return

    width = viewport["width"]
    height = viewport["height"]

    # Titik awal acak
    current_x = random.randint(100, width - 100)
    current_y = random.randint(100, height - 100)

    for _ in range(steps):
        target_x = random.randint(100, width - 100)
        target_y = random.randint(100, height - 100)

        # Gerak bertahap (bezier curve simulasi)
        num_sub_steps = random.randint(5, 15)
        for i in range(num_sub_steps):
            t = i / num_sub_steps
            # Interpolasi dengan sedikit noise
            x = current_x + (target_x - current_x) * t + random.randint(-5, 5)
            y = current_y + (target_y - current_y) * t + random.randint(-5, 5)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.01, 0.04))

        current_x, current_y = target_x, target_y

    print(f"[Stealth] 🖱️  Mouse moved {steps} steps acak.")


async def human_click(page, selector: str):
    """Klik elemen dengan delay dan gerakan kursor manusiawi."""
    element = await page.wait_for_selector(selector, timeout=10000)
    if not element:
        raise Exception(f"Element tidak ditemukan: {selector}")

    box = await element.bounding_box()
    if box:
        # Klik di titik acak dalam bounding box elemen
        x = box["x"] + random.uniform(5, box["width"] - 5)
        y = box["y"] + random.uniform(5, box["height"] - 5)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.2, 0.6))
        await page.mouse.click(x, y)
    else:
        await element.click()

    print(f"[Stealth] 🖱️  Human click pada: {selector}")


async def human_type(page, selector: str, text: str):
    """Ketik teks karakter per karakter dengan delay acak."""
    await human_click(page, selector)
    await asyncio.sleep(random.uniform(0.3, 0.7))

    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.18))

    prefix_length = min(10, len(text))
    preview = text[:prefix_length]
    print(f"[Stealth] ⌨️  Typed: {preview}...")
