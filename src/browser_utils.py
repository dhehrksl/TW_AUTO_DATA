import asyncio
import random

async def human_type(page, selector, text, delay_min=0.05, delay_max=0.2):
    try:
        await page.focus(selector)
        for char in text:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(delay_min, delay_max))
    except:
        await page.fill(selector, text)

async def random_mouse_move(page):
    try:
        viewport = page.viewport_size
        if viewport:
            width = viewport['width']
            height = viewport['height']
            for _ in range(random.randint(2, 5)):
                x = random.randint(0, width)
                y = random.randint(0, height)
                await page.mouse.move(x, y, steps=random.randint(5, 15))
                await asyncio.sleep(random.uniform(0.1, 0.3))
    except:
        pass

async def human_click(page, locator, delay=0.5):
    try:
        box = await locator.bounding_box()
        if box:
            x = box["x"] + box["width"] / 2 + random.uniform(-10, 10)
            y = box["y"] + box["height"] / 2 + random.uniform(-5, 5)
            
            await page.mouse.move(x, y, steps=10)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.down()
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await page.mouse.up()
            return True
        else:
            await locator.click()
            return True
    except:
        try:
            await locator.evaluate("el => el.click()")
            return True
        except:
            return False

async def safe_click(locator, retries=5, delay=0.6, force=False):
    for _ in range(retries):
        try:
            await locator.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)
            if force:
                await locator.evaluate("el => el.click()")
            else:
                await locator.click(timeout=10000)
            return True
        except:
            await asyncio.sleep(delay)
    return False

async def handle_popups(page):
    selectors = [
        "button.btn-popup-close",
        "button.popup-close",
        "body .btn-secondary.btn-lg.btn-cancel",
        "body .btn-outline-default.btn-lg",
        "#expiredCloseBtn",
        "#expiredModal .layerPop1 button",
        ".popup-layer button.close",
    ]

    for _ in range(3):
        for sel in selectors:
            try:
                for el in await page.query_selector_all(sel):
                    try:
                        if await el.is_visible():
                            await el.click()
                            await page.wait_for_timeout(300)
                    except:
                        pass
            except:
                pass

async def wait_and_get_text(page, selector, timeout=10000, retries=3):
    for _ in range(retries):
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            text = await page.text_content(selector)
            if text and text.strip():
                return text.strip()
        except:
            await asyncio.sleep(0.5)
    return "-"

async def get_text_from_selectors(page, selectors, timeout=10000, retries=3):
    for _ in range(retries):
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=timeout, state="visible")
                text = await page.text_content(sel)
                if text and text.strip():
                    return text.strip()
            except:
                pass
        await asyncio.sleep(0.5)
    return "-"
