from browser_utils import safe_click, handle_popups, wait_and_get_text, get_text_from_selectors

async def get_plan_info(page):
    selectors = [
        "#section_one_line .calling.line-none a span",
        "#section_one_line .calling.line-none a",
    ]
    return await get_text_from_selectors(page, selectors)

async def get_message_info(page):
    return await wait_and_get_text(page, "#section_one_line > div.my-section__message > h1 > span")

async def get_data_usage(page):
    total = await get_text_from_selectors(page, ["#section_one_data span.bar-amount"])
    remain = await get_text_from_selectors(page, ["#section_one_data div.section-data.title a"])
    return total, remain

async def get_gift_info(page):
    try:
        btn = page.locator("#section_one_data .button-wrap button:nth-child(2)")
        if await btn.count() == 0:
            return "0", "0"

        await safe_click(btn, force=True)
        await page.wait_for_timeout(2000)
        await handle_popups(page)

        data = await wait_and_get_text(page, "#s_tabCon01 .gift_check.col3 dl:nth-child(1)")
        count = await wait_and_get_text(page, "#s_tabCon01 .gift_check.col3 dl:nth-child(2)")
        return data, count
    except:
        return "0", "0"

async def get_seb_service(page):
    try:
        await safe_click(page.get_by_role("link", name="MY"))
        await page.wait_for_timeout(1500)
        await handle_popups(page)

        toggle = page.locator("#commonToggle_button_6")
        if await toggle.count() == 0:
            return "0", "0", "0", "0"

        await safe_click(toggle, force=True)
        await page.wait_for_timeout(2000)

        async def get_count(sel):
            try:
                if await page.locator(sel).count() > 0:
                    return (await page.text_content(sel)).strip()
            except:
                pass
            return "0"

        return (
            await get_count("#content .mobile.off span.count"),
            await get_count("#content .internet.none span.count"),
            await get_count("#content .wifi.none span.count"),
            await get_count("#content .pps.none span.count"),
        )
    except:
        return "0", "0", "0", "0"

async def get_bill_info(page):
    try:
        toggle = page.locator("#commonToggle_button_5")
        if await toggle.count() == 0:
            return "-"
        
        await safe_click(toggle, force=True)
        await page.wait_for_timeout(1500)

        detail_btn = page.locator("#paid-amt-month-main > div.conBox_center > div.tabCon > div.newChargeInfo > div.topContInfo > a")
        if await detail_btn.count() == 0:
            return "-"
            
        await safe_click(detail_btn, force=True)
        await page.wait_for_timeout(1500)

        list_selector = "#paid-amt-month-main > div.conBox_center > div.tabCon > div.newChargeInfo > div.topContInfo > div.monthLayer > div.inMonthLayer > div > div > ul > li"
        
        items = []
        elements = await page.locator(list_selector).all()
        
        for el in elements:
            text = await el.text_content()
            if text and text.strip():
                clean_text = " ".join(text.split())
                items.append(clean_text)
        
        if items:
            return "\n".join([f"{idx+1}. {item}" for idx, item in enumerate(items)])
            
    except:
        pass
        
    return "-"

async def get_additional_services(page):
    svc_result = []
    discount_result = []
    option_result = []
    max_groups = 5

    try:
        await safe_click(page.get_by_role("link", name="MY"))
        await page.wait_for_timeout(1500)
        
        entry_button_selector = "#submain_section_four > div > div > div > div > div:nth-child(3) > a"
        target_frame = None
        for frame in page.frames:
            if await frame.locator(entry_button_selector).count() > 0:
                target_frame = frame
                break
        
        if not target_frame:
            return "-", "-", "-"

        async with page.expect_navigation(wait_until="load", timeout=15000):
            await target_frame.locator(entry_button_selector).click()
        
        await page.wait_for_timeout(2000)

        for i in range(1, max_groups + 1):
            detail_btn_selector = f"#openWirelessDetail{i}"
            
            if await page.locator(detail_btn_selector).count() == 0:
                break
            
            await safe_click(page.locator(detail_btn_selector), force=True)
            await page.wait_for_timeout(1500)

            tbody_selector = f"#wirelessAddSvcTobdy{i}"
            items = []
            try:
                rows = await page.locator(f"{tbody_selector} > tr").all()
                for row in rows:
                    cols = await row.locator("td").all()
                    for col in cols:
                        dt_tag = col.locator("dl > dt")
                        if await dt_tag.count() > 0:
                            text = await dt_tag.text_content()
                            if text and text.strip():
                                clean_text = " ".join(text.split())
                                items.append(clean_text)
            except:
                pass
            
            if items:
                formatted_items = [f"{idx+1}. {item}" for idx, item in enumerate(items)]
                svc_result.append(f"[Line {i}]\n" + "\n".join(formatted_items))

            discount_selector = f"#wirelessDiscountSvc{i}"
            discounts = []
            try:
                dl_elements = await page.locator(f"{discount_selector} > dd > dl").all()
                for dl in dl_elements:
                    text = await dl.text_content()
                    if text and text.strip():
                        clean_text = " ".join(text.split())
                        discounts.append(clean_text)
            except:
                pass

            if discounts:
                formatted_discounts = [f"{idx+1}. {item}" for idx, item in enumerate(discounts)]
                discount_result.append(f"[Line {i}]\n" + "\n".join(formatted_discounts))

            option_selector = f"#wirelessOptionSvc{i}"
            options = []
            try:
                dl_elements = await page.locator(f"{option_selector} > dd > dl").all()
                for dl in dl_elements:
                    dt = dl.locator("dt")
                    if await dt.count() > 0:
                        text = await dt.text_content()
                        if text and text.strip():
                            clean_text = " ".join(text.split())
                            options.append(clean_text)
            except:
                pass

            if options:
                formatted_options = [f"{idx+1}. {item}" for idx, item in enumerate(options)]
                option_result.append(f"[Line {i}]\n" + "\n".join(formatted_options))

    except:
        pass

    final_svc = "\n\n".join(svc_result) if svc_result else "-"
    final_discount = "\n\n".join(discount_result) if discount_result else "-"
    final_option = "\n\n".join(option_result) if option_result else "-"

    return final_svc, final_discount, final_option
