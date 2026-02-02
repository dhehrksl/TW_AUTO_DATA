import asyncio
import random
import os
import threading
import tkinter as tk
import sys
import subprocess
from tkinter import filedialog, messagebox, scrolledtext
from playwright.async_api import async_playwright
from config import RESULT_FILENAME
from excel_handler import load_accounts, init_result_excel, save_results
from browser_utils import safe_click, handle_popups, human_click, random_mouse_move
from auth import try_login
from scrapers import (
    get_plan_info, get_data_usage, get_message_info,
    get_gift_info, get_seb_service, get_additional_services,
    get_bill_info
)
from telegram_utils import send_telegram_message

if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.getcwd()

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base_path, "browsers")

log_widget = None
stop_event = threading.Event()

def log_message(msg):
    if log_widget:
        log_widget.insert(tk.END, msg + "\n")
        log_widget.see(tk.END)
    print(msg)

def install_browsers():
    log_message("브라우저 확인 중...")
    try:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--install-worker"]
        else:
            cmd = [sys.executable, "-m", "playwright", "install", "chromium"]

        subprocess.run(
            cmd,
            check=True,
            startupinfo=startupinfo
        )
        log_message("브라우저 확인 완료.")
    except Exception as e:
        log_message(f"브라우저 설치 실패: {e}")

async def process_account(browser, semaphore, account, attempt_dict, results, lock):
    if stop_event.is_set(): return

    async with semaphore:
        if stop_event.is_set(): return

        tw_id = account["id"]
        tw_pw = account["pw"]
        order = account["order"]

        attempt_dict[tw_id] = attempt_dict.get(tw_id, 0) + 1
        attempt_no = attempt_dict[tw_id]

        log_message(f"[{tw_id}] 작업 시작 ({attempt_no}차 시도)")

        status, reason = "성공", "-"
        plan = total = remain = "-"
        gift_d = gift_c = "0"
        mob = inet = wifi = pps = "0"
        msg = "-"
        
        svc_info = "-"
        discount_info = "-"
        option_info = "-"
        bill_info = "-"

        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            has_touch=True,
            permissions=["geolocation"],
            geolocation={"latitude": 37.5665, "longitude": 126.9780},
            java_script_enabled=True,
            bypass_csp=True
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Open Source Technology Center';
                }
                if (parameter === 37446) {
                    return 'Mesa DRI Intel(R) Ivybridge Mobile ';
                }
                return getParameter(parameter);
            };
        """)

        page = await context.new_page()

        try:
            if stop_event.is_set(): raise Exception("사용자 중지")
            await asyncio.sleep(random.uniform(2, 6))

            if stop_event.is_set(): raise Exception("사용자 중지")
            await page.goto("https://w-stg.tworld.co.kr/web/home", wait_until="domcontentloaded")
            
            await random_mouse_move(page)
            await handle_popups(page)

            my_link = page.get_by_role("link", name="MY")
            if not await human_click(page, my_link):
                if not await safe_click(my_link):
                    raise Exception("MY 버튼 클릭 실패")

            await asyncio.sleep(random.uniform(1.5, 3))

            if stop_event.is_set(): raise Exception("사용자 중지")
            if not await try_login(page, tw_id, tw_pw):
                raise Exception("로그인 실패")
            
            log_message(f"[{tw_id}] 로그인 성공")
            
            try:
                await page.wait_for_selector("#section_one_line", timeout=15000, state="visible")
            except:
                raise Exception("페이지 로딩 시간 초과")

            await asyncio.sleep(random.uniform(1.5, 3))

            if stop_event.is_set(): raise Exception("사용자 중지")
            plan = await get_plan_info(page)
            total, remain = await get_data_usage(page)
            msg = await get_message_info(page)
            gift_d, gift_c = await get_gift_info(page)
            mob, inet, wifi, pps = await get_seb_service(page)
            
            log_message(f"[{tw_id}] 청구 요금 수집 중...")
            bill_info = await get_bill_info(page)
            
            log_message(f"[{tw_id}] 기본 정보 수집 완료")

            if stop_event.is_set(): raise Exception("사용자 중지")
            log_message(f"[{tw_id}] 부가서비스 수집 중...")
            svc_info, discount_info, option_info = await get_additional_services(page)
            log_message(f"[{tw_id}] 부가서비스 수집 완료")

        except Exception as e:
            status, reason = "실패", str(e)
            if str(e) != "사용자 중지":
                log_message(f"[{tw_id}] 오류: {e}")
                if not os.path.exists("error"):
                    os.makedirs("error")
                try:
                    await page.screenshot(path=f"error/error_{tw_id}.png")
                except:
                    pass
            else:
                log_message(f"[{tw_id}] 중지됨.")

        finally:
            async with lock:
                results.append({
                    "order": order,
                    "row": [
                        tw_id, plan, total, remain,
                        gift_d, gift_c, mob, inet, wifi, pps,
                        msg, attempt_no, status, 
                        svc_info, discount_info, option_info,
                        bill_info,
                        reason
                    ]
                })
                log_message(f"[{tw_id}] 완료 -> {status}")

            await context.close()

async def run_automation(excel_path, concurrency, app_instance):
    try:
        install_browsers()

        accounts = load_accounts(excel_path)
        if not accounts:
            log_message("엑셀 파일에 계정이 없습니다.")
            app_instance.reset_ui()
            return

        wb, ws = init_result_excel()
        attempt_dict = {}
        results = []
        lock = asyncio.Lock()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", 
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--start-maximized",
                    "--disable-extensions",
                    "--disable-popup-blocking"
                ]
            )
            semaphore = asyncio.Semaphore(concurrency)

            tasks = [
                process_account(browser, semaphore, acc, attempt_dict, results, lock)
                for acc in accounts
            ]
            
            await asyncio.gather(*tasks)

            save_results(wb, results)
            await browser.close()
        
        total_count = len(results)
        success_count = sum(1 for r in results if r["row"][12] == "성공")
        fail_count = total_count - success_count
        
        msg = f"TWorld 자동화 완료!\n\n총 작업: {total_count}건\n성공: {success_count}건\n실패: {fail_count}건\n\n{RESULT_FILENAME} 저장됨"
        
        if fail_count > 0:
            msg += "\n\n[실패 목록]"
            for r in results:
                if r["row"][12] != "성공":
                    msg += f"\n- {r['row'][0]}: {r['row'][-1]}"

        if stop_event.is_set():
            log_message("사용자에 의해 중지되었습니다.")
            send_telegram_message(f"TWorld 자동화 중지됨.\n\n{msg}")
            messagebox.showinfo("중지됨", "작업이 중지되었습니다.\n중지 전까지의 결과는 저장되었습니다.")
        else:
            log_message(f"모든 작업 완료. {RESULT_FILENAME} 저장됨")
            send_telegram_message(msg)
            messagebox.showinfo("완료", f"작업이 완료되었습니다!\n{RESULT_FILENAME} 저장됨")

    except Exception as e:
        log_message(f"치명적 오류: {e}")
        send_telegram_message(f"TWorld 자동화 오류 발생: {e}")
        messagebox.showerror("오류", str(e))
    finally:
        app_instance.reset_ui()

def start_thread(excel_path, concurrency, app_instance):
    stop_event.clear()
    threading.Thread(target=lambda: asyncio.run(run_automation(excel_path, concurrency, app_instance)), daemon=True).start()

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("TWorld 자동화 도구")
        self.root.geometry("600x550")

        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, "my_icon.ico")
            else:
                icon_path = "my_icon.ico"
            
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass

        self.frame_top = tk.Frame(root, pady=10)
        self.frame_top.pack(fill=tk.X)

        self.lbl_file = tk.Label(self.frame_top, text="계정 엑셀 파일:")
        self.lbl_file.pack(side=tk.LEFT, padx=10)

        self.entry_file = tk.Entry(self.frame_top, width=40)
        self.entry_file.pack(side=tk.LEFT, padx=5)

        self.btn_browse = tk.Button(self.frame_top, text="찾아보기", command=self.browse_file)
        self.btn_browse.pack(side=tk.LEFT, padx=5)

        # 브라우저 개수 설정 프레임
        self.frame_settings = tk.Frame(root, pady=5)
        self.frame_settings.pack(fill=tk.X)

        self.lbl_concurrency = tk.Label(self.frame_settings, text="동시 실행 브라우저 수:")
        self.lbl_concurrency.pack(side=tk.LEFT, padx=10)

        self.entry_concurrency = tk.Entry(self.frame_settings, width=5)
        self.entry_concurrency.pack(side=tk.LEFT, padx=5)
        self.entry_concurrency.insert(0, "5") # 기본값 5

        self.frame_btns = tk.Frame(root, pady=10)
        self.frame_btns.pack()

        self.btn_run = tk.Button(self.frame_btns, text="작업 시작", command=self.run, bg="green", fg="white", font=("맑은 고딕", 12, "bold"))
        self.btn_run.pack(side=tk.LEFT, padx=10)

        self.btn_stop = tk.Button(self.frame_btns, text="작업 중지", command=self.stop, bg="red", fg="white", font=("맑은 고딕", 12, "bold"), state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        self.lbl_log = tk.Label(root, text="로그:")
        self.lbl_log.pack(anchor="w", padx=10)

        global log_widget
        log_widget = scrolledtext.ScrolledText(root, height=20)
        log_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.btn_test_tel = tk.Button(root, text="텔레그램 테스트", command=self.test_telegram)
        self.btn_test_tel.pack(pady=5)

    def test_telegram(self):
        log_message("텔레그램 테스트 메시지 전송 시도...")
        send_telegram_message("TWorld 자동화 도구 테스트 메시지입니다.")

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if filename:
            self.entry_file.delete(0, tk.END)
            self.entry_file.insert(0, filename)

    def run(self):
        excel_path = self.entry_file.get()
        if not excel_path or not os.path.exists(excel_path):
            messagebox.showwarning("경고", "올바른 엑셀 파일을 선택해주세요.")
            return
        
        try:
            concurrency = int(self.entry_concurrency.get())
            if concurrency < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("경고", "브라우저 수는 1 이상의 숫자여야 합니다.")
            return
        
        self.btn_run.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        log_widget.delete(1.0, tk.END)
        log_message(f"작업을 시작합니다... (동시 실행: {concurrency}개)")
        
        start_thread(excel_path, concurrency, self)

    def stop(self):
        if messagebox.askyesno("중지", "정말 작업을 중지하시겠습니까?"):
            log_message("중지 중... 현재 진행 중인 작업이 마무리될 때까지 기다려주세요.")
            stop_event.set()
            self.btn_stop.config(state=tk.DISABLED)

    def reset_ui(self):
        self.btn_run.config(state=tk.NORMAL, text="작업 시작")
        self.btn_stop.config(state=tk.DISABLED)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--install-worker":
        from playwright.__main__ import main
        sys.argv = ["playwright", "install", "chromium"]
        sys.exit(main())

    root = tk.Tk()
    app = App(root)
    root.mainloop()
