import urllib.request
import urllib.parse
import json
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram token or chat ID not set.")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        
        data_encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=data_encoded)
        
        with urllib.request.urlopen(req) as response:
            if response.getcode() == 200:
                print("Telegram message sent.")
            else:
                print(f"Failed to send Telegram message. Status code: {response.getcode()}")
                
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
