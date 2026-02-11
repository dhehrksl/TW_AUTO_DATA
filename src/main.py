import asyncio
import random
import os
import threading
import tkinter as tk
import sys
import subprocess
import datetime
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

# 경로 설정
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 폴더 경로
BROWSERS_PATH = os.path.join(BASE_PATH, "browsers")
DATA_DIR = os.path.join(BASE_PATH, "data")
LOG_DIR = os.path.join(BASE_PATH, "logs")
ERROR_DIR = os.path.join(BASE_PATH, "error")
ASSETS_DIR = os.path.join(BASE_PATH, "assets")

# 파일 경로
LOG_FILE = os.path.join(LOG_DIR, "debug.log")
DEFAULT_ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.xlsx")
ICON_FILE = os.path.join(ASSETS_DIR, "my_icon.ico")

# 브라우저 경로 설정
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSERS_PATH

# 폴더 없으면 생성
for directory in [DATA_DIR, LOG_DIR, ERROR_DIR, ASSETS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

log_widget = None
stop_event = threading.Event()

def log_message(msg):
    # 로그 출력 및 저장
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    
    if log_widget:
        log_widget.insert(tk.END, formatted_msg + "\n")
        log_widget.see(tk.END)
    print(formatted_msg)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    except:
        pass

def install_browsers():
    log_message(f"브라우저 경로: {BROWSERS_PATH}")
    
    if not os.path.exists(BROWSERS_PATH) or not os.listdir(BROWSERS_PATH):
        log_message("브라우저 설치 시도...")
    else:
        log_message("브라우저 확인됨")

    try:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--install-worker"]
        else:
            cmd = [sys.executable, "-m", "playwright", "install", "chromium"]

        env = os.environ.copy()
        
        subprocess.run(
            cmd,
            check=True,
            startupinfo=startupinfo,
            env=env
        )
        log_message("설치 완료")
    except Exception as e:
        log_message(f"설치 오류: {e}")

async def process_account(browser, semaphore, account, attempt_dict, results, lock):
    if stop_event.is_set(): return

    async with semaphore:
        if stop_event.is_set(): return

        tw_id = account["id"]
        tw_pw = account["pw"]
        order = account["order"]

        attempt_dict[tw_id] = attempt_dict.get(tw_id, 0) + 1
        attempt_no = attempt_dict[tw_id]

        log_message(f"[{tw_id}] 시작 ({attempt_no}차)")

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
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        page = await context.new_page()

        try:
            if stop_event.is_set(): raise Exception("중지됨")
            await asyncio.sleep(random.uniform(1, 3))

            if stop_event.is_set(): raise Exception("중지됨")
            await page.goto("https://w-stg.tworld.co.kr/web/home", wait_until="domcontentloaded")
            
            await handle_popups(page)

            my_link = page.get_by_role("link", name="MY")
            if not await human_click(page, my_link):
                if not await safe_click(my_link):
                    raise Exception("MY 버튼 클릭 실패")

            await asyncio.sleep(random.uniform(1, 2))

            if stop_event.is_set(): raise Exception("중지됨")
            if not await try_login(page, tw_id, tw_pw):
                raise Exception("로그인 실패")
            
            log_message(f"[{tw_id}] 로그인 성공")
            
            try:
                await page.wait_for_selector("#section_one_line", timeout=15000, state="visible")
            except:
                raise Exception("로딩 시간 초과")

            await asyncio.sleep(random.uniform(1, 2))

            if stop_event.is_set(): raise Exception("중지됨")
            plan = await get_plan_info(page)
            total, remain = await get_data_usage(page)
            msg = await get_message_info(page)
            gift_d, gift_c = await get_gift_info(page)
            mob, inet, wifi, pps = await get_seb_service(page)
            
            log_message(f"[{tw_id}] 요금 정보 수집...")
            bill_info = await get_bill_info(page)
            
            log_message(f"[{tw_id}] 기본 정보 완료")

            if stop_event.is_set(): raise Exception("중지됨")
            log_message(f"[{tw_id}] 부가서비스 수집...")
            svc_info, discount_info, option_info = await get_additional_services(page)
            log_message(f"[{tw_id}] 부가서비스 완료")

        except Exception as e:
            status, reason = "실패", str(e)
            if str(e) != "중지됨":
                log_message(f"[{tw_id}] 에러: {e}")
                
                try:
                    screenshot_path = os.path.join(ERROR_DIR, f"error_{tw_id}.png")
                    await page.screenshot(path=screenshot_path)
                    log_message(f"[{tw_id}] 스크린샷: {screenshot_path}")
                except Exception as s_e:
                    log_message(f"[{tw_id}] 스크린샷 실패: {s_e}")
            else:
                log_message(f"[{tw_id}] 중지.")

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
            log_message("계정 없음")
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

            # 결과 저장
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            result_filename = f"result_{timestamp}.xlsx"
            result_path = os.path.join(DATA_DIR, result_filename)
            
            wb.save(result_path)
            log_message(f"저장됨: {result_path}")
            
            await browser.close()
        
        total_count = len(results)
        success_count = sum(1 for r in results if r["row"][12] == "성공")
        fail_count = total_count - success_count
        
        msg = f"완료!\n\n총: {total_count}건\n성공: {success_count}건\n실패: {fail_count}건\n\n{result_filename} 저장됨"
        
        if fail_count > 0:
            msg += "\n\n[실패]"
            for r in results:
                if r["row"][12] != "성공":
                    msg += f"\n- {r['row'][0]}: {r['row'][-1]}"

        if stop_event.is_set():
            log_message("중지됨")
            send_telegram_message(f"중지됨.\n\n{msg}")
            messagebox.showinfo("중지", "작업 중지됨")
        else:
            log_message(f"완료. {result_filename}")
            send_telegram_message(msg)
            messagebox.showinfo("완료", f"작업 완료!\n{result_filename}")

    except Exception as e:
        log_message(f"오류: {e}")
        send_telegram_message(f"오류 발생: {e}")
        messagebox.showerror("오류", str(e))
    finally:
        app_instance.reset_ui()

def start_thread(excel_path, concurrency, app_instance):
    stop_event.clear()
    threading.Thread(target=lambda: asyncio.run(run_automation(excel_path, concurrency, app_instance)), daemon=True).start()

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("TWorld 자동화")
        self.root.geometry("600x550")

        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, "assets", "my_icon.ico")
            else:
                icon_path = ICON_FILE
            
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass

        self.frame_top = tk.Frame(root, pady=10)
        self.frame_top.pack(fill=tk.X)

        self.lbl_file = tk.Label(self.frame_top, text="계정 파일:")
        self.lbl_file.pack(side=tk.LEFT, padx=10)

        self.entry_file = tk.Entry(self.frame_top, width=40)
        self.entry_file.pack(side=tk.LEFT, padx=5)
        
        if os.path.exists(DEFAULT_ACCOUNTS_FILE):
            self.entry_file.insert(0, DEFAULT_ACCOUNTS_FILE)

        self.btn_browse = tk.Button(self.frame_top, text="찾기", command=self.browse_file)
        self.btn_browse.pack(side=tk.LEFT, padx=5)

        self.frame_settings = tk.Frame(root, pady=5)
        self.frame_settings.pack(fill=tk.X)

        self.lbl_concurrency = tk.Label(self.frame_settings, text="브라우저 수:")
        self.lbl_concurrency.pack(side=tk.LEFT, padx=10)

        self.entry_concurrency = tk.Entry(self.frame_settings, width=5)
        self.entry_concurrency.pack(side=tk.LEFT, padx=5)
        self.entry_concurrency.insert(0, "5")

        self.frame_btns = tk.Frame(root, pady=10)
        self.frame_btns.pack()

        self.btn_run = tk.Button(self.frame_btns, text="시작", command=self.run, bg="green", fg="white", font=("맑은 고딕", 12, "bold"))
        self.btn_run.pack(side=tk.LEFT, padx=10)

        self.btn_stop = tk.Button(self.frame_btns, text="중지", command=self.stop, bg="red", fg="white", font=("맑은 고딕", 12, "bold"), state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        self.lbl_log = tk.Label(root, text="로그:")
        self.lbl_log.pack(anchor="w", padx=10)

        global log_widget
        log_widget = scrolledtext.ScrolledText(root, height=20)
        log_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def browse_file(self):
        initial_dir = DATA_DIR if os.path.exists(DATA_DIR) else BASE_PATH
        filename = filedialog.askopenfilename(
            initialdir=initial_dir,
            filetypes=[("Excel Files", "*.xlsx")]
        )
        if filename:
            self.entry_file.delete(0, tk.END)
            self.entry_file.insert(0, filename)

    def run(self):
        excel_path = self.entry_file.get()
        if not excel_path or not os.path.exists(excel_path):
            messagebox.showwarning("경고", "파일을 확인해주세요.")
            return
        
        try:
            concurrency = int(self.entry_concurrency.get())
            if concurrency < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("경고", "숫자를 입력해주세요.")
            return
        
        self.btn_run.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        log_widget.delete(1.0, tk.END)
        log_message(f"시작... ({concurrency}개)")
        
        start_thread(excel_path, concurrency, self)

    def stop(self):
        if messagebox.askyesno("중지", "중지하시겠습니까?"):
            log_message("중지 중...")
            stop_event.set()
            self.btn_stop.config(state=tk.DISABLED)

    def reset_ui(self):
        self.btn_run.config(state=tk.NORMAL, text="시작")
        self.btn_stop.config(state=tk.DISABLED)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--install-worker":
        from playwright.__main__ import main
        sys.argv = ["playwright", "install", "chromium"]
        sys.exit(main())

    root = tk.Tk()
    app = App(root)
    root.mainloop()
