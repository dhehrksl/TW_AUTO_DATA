import asyncio
from browser_utils import handle_popups, safe_click, human_type

async def try_login(page, tw_id, tw_pw, max_attempts=2):
    for _ in range(max_attempts):
        try:
            await handle_popups(page)

            target = next(
                (f for f in page.frames if "login" in (f.name or "").lower() or "auth" in f.url.lower()),
                page
            )

            await target.wait_for_selector("input#inputId", timeout=8000)
            
            await human_type(target, "input#inputId", tw_id)
            await asyncio.sleep(0.5)
            await human_type(target, "input#inputPassword", tw_pw)
            await asyncio.sleep(0.5)

            await safe_click(target.locator('button[data-click-id="login"]'), force=True)
            await page.wait_for_timeout(1500)
            await handle_popups(page)

            if "auth" not in page.url.lower():
                return True
        except:
            await asyncio.sleep(1)
    return False
