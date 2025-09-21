import time
import json
import os
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from flask import Flask, jsonify, render_template_string, request

# ===================================================================
# CẤU HÌNH VÀ BIẾN TOÀN CỤC (Đọc từ Environment Variables)
# ===================================================================

# Đọc đường dẫn tệp cookie từ 'env'. 
# Nếu không đặt, mặc định là 'cookie.json' để khớp với Secret File.
COOKIE_FILE = os.getenv("COOKIE_FILE_PATH", "cookie.json") 

# Đọc URL cơ sở từ 'env'
BASE_URL = os.getenv("FB_BASE_URL", "https://m.facebook.com")

# --- Biến trạng thái điều khiển (An toàn cho đa luồng) ---
lock = threading.Lock()

# Lấy cài đặt MẶC ĐỊNH từ 'env'
# Giao diện web sẽ cho phép bạn THAY ĐỔI chúng khi chạy
DEFAULT_CONTENT = os.getenv(
    "DEFAULT_POST_CONTENT", 
    "Đây là nội dung mặc định. Hãy thay đổi trên UI."
)
DEFAULT_DELAY = int(os.getenv("DEFAULT_DELAY_SECONDS", 3600)) # Mặc định 1 giờ

bot_status = {
    "is_bot_running": False,
    "post_content": DEFAULT_CONTENT,
    "delay_seconds": DEFAULT_DELAY,
    "last_run_status": "Chưa chạy lần nào."
}

# ===================================================================
# LOGIC BOT SELENIUM (Sẽ chạy trong một luồng riêng)
# ===================================================================

def create_driver():
    """Khởi tạo trình duyệt Chrome ở chế độ headless cho Render."""
    print("INFO: Khởi tạo trình duyệt Chrome ở chế độ Headless...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1920x1080")
    
    options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")

    if not options.binary_location or not chromedriver_path:
        print("LỖI: Không tìm thấy GOOGLE_CHROME_BIN hoặc CHROMEDRIVER_PATH.")
        print("Bạn đã thêm Buildpacks cho Chrome và Chromedriver chưa?")
        return None
    try:
        s = Service(chromedriver_path)
        driver = webdriver.Chrome(service=s, options=options)
        return driver
    except Exception as e:
        print(f"LỖI: Không thể khởi động WebDriver: {e}")
        return None

def login_with_cookie(driver, cookie_file):
    """Đăng nhập vào Facebook bằng cookie."""
    print(f"INFO: Đang đăng nhập bằng cookie từ tệp: {cookie_file}")
    if not os.path.exists(cookie_file):
        print(f"LỖI: Không tìm thấy tệp cookie '{cookie_file}'.")
        print("Bạn đã cấu hình 'Secret File' trên Render chưa?")
        return False
    try:
        with open(cookie_file, 'r') as f: cookies = json.load(f)
        driver.get(BASE_URL)
        time.sleep(1)
        for cookie in cookies:
            if 'sameSite' in cookie: del cookie['sameSite']
            driver.add_cookie(cookie)
        driver.refresh()
        time.sleep(3) 
        if "checkpoint" in driver.current_url:
            print("LỖI: Đăng nhập thất bại. Tài khoản có thể bị checkpoint.")
            return False
        print("INFO: Đăng nhập thành công!")
        return True
    except Exception as e:
        print(f"LỖI: Đã xảy ra lỗi khi đăng nhập: {e}")
        return False

def post_to_wall(driver, content):
    """Đăng bài viết lên tường cá nhân."""
    print(f"INFO: Chuẩn bị đăng bài: '{content[:20]}...'")
    try:
        driver.get(BASE_URL)
        time.sleep(3)
        try:
            textarea = driver.find_element(By.NAME, "xc_message")
            textarea.send_keys(content)
            time.sleep(2)
            post_button = driver.find_element(By.XPATH, "//button[@value='Post']")
            post_button.click()
            print("INFO: Đăng bài thành công!")
            time.sleep(5) 
            return "Đăng bài thành công!"
        except NoSuchElementException:
            print("LỖI: Không tìm thấy ô đăng bài hoặc nút 'Post'. Giao diện Facebook có thể đã thay đổi.")
            return "Lỗi: Không tìm thấy ô đăng bài."
    except Exception as e:
        print(f"LỖI: Đã xảy ra lỗi khi đăng bài: {e}")
        return f"Lỗi: {e}"

def run_facebook_bot():
    """Vòng lặp bot chạy nền (trong thread)."""
    global bot_status, lock
    
    print("INFO: Luồng (thread) bot Facebook đã khởi động.")
    
    while True:
        # Lấy trạng thái hiện tại một cách an toàn
        with lock:
            is_running = bot_status["is_bot_running"]
            content = bot_status["post_content"]
            delay = bot_status["delay_seconds"]

        if not is_running:
            # Nếu bot bị tắt, chỉ cần nghỉ và kiểm tra lại
            time.sleep(5)
            continue
        
        # Nếu bot được BẬT, thực hiện một lượt chạy
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Bắt đầu một lượt chạy bot...")
        bot_driver = None
        run_message = "Chưa khởi động"
        
        try:
            bot_driver = create_driver()
            if bot_driver:
                if login_with_cookie(bot_driver, COOKIE_FILE):
                    run_message = post_to_wall(bot_driver, content)
                else:
                    run_message = "Lỗi: Đăng nhập thất bại (Checkpoint?)."
                
                print("INFO: Lượt chạy hoàn tất. Đóng trình duyệt.")
                bot_driver.quit()
            else:
                run_message = "Lỗi: Không thể tạo driver."

        except Exception as e:
            run_message = f"Lỗi nghiêm trọng: {e}"
            print(f"LỖI NGHIÊM TRỌNG: {e}")
            if bot_driver:
                bot_driver.quit()
        
        # Cập nhật trạng thái lần chạy cuối
        with lock:
            bot_status["last_run_status"] = f"[{time.strftime('%H:%M:%S')}] {run_message}"
        
        print(f"INFO: Bot sẽ nghỉ trong {delay} giây...")
        time.sleep(delay)

# ===================================================================
# MÁY CHỦ WEB FLASK (Để điều khiển)
# ===================================================================

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Bot Control</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #e0e0e0; display: flex; flex-direction: column; align-items: center; gap: 20px; padding: 20px; }
        .panel { background-color: #1e1e1e; padding: 25px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.5); width: 100%; max-width: 600px; display: flex; flex-direction: column; gap: 20px;}
        h1 { color: #1877F2; margin-top: 0; } .status { font-size: 1.1em; }
        .status-on { color: #03dac6; } .status-off { color: #cf6679; }
        button { background-color: #1877F2; color: #fff; border: none; padding: 12px 24px; font-size: 1.1em; border-radius: 5px; cursor: pointer; transition: all 0.3s; font-weight: bold; width: 100%;}
        button:hover { background-color: #166FE5; }
        button.stop-btn { background-color: #cf6679; }
        button.stop-btn:hover { background-color: #b00020; }
        label { font-weight: bold; color: #aaa; margin-bottom: -10px; }
        textarea, input { width: 100%; box-sizing: border-box; border: 1px solid #444; background-color: #333; color: #eee; padding: 12px; border-radius: 5px; font-size: 1em; resize: vertical;}
        #last_status { font-size: 0.9em; color: #888; background-color: #222; padding: 10px; border-radius: 5px; word-wrap: break-word; }
    </style>
</head>
<body>
    <h1>Facebook Bot Control Panel</h1>
    <div class="panel">
        <div id="bot-status" class="status">Đang tải...</div>
        
        <label for="post-content">Nội dung bài đăng:</label>
        <textarea id="post-content" rows="4"></textarea>
        
        <label for="delay-seconds">Thời gian nghỉ (giây):</label>
        <input type="number" id="delay-seconds" value="3600">
        
        <button id="toggleBotBtn" onclick="toggleBot()">BẬT BOT</button>
        
        <label>Trạng thái lần chạy cuối:</label>
        <pre id="last_status">...</pre>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                const statusDiv = document.getElementById('bot-status');
                const toggleBtn = document.getElementById('toggleBotBtn');
                
                if (data.is_bot_running) {
                    statusDiv.textContent = 'Trạng thái: ĐANG CHẠY';
                    statusDiv.className = 'status status-on';
                    toggleBtn.textContent = 'TẮT BOT';
                    toggleBtn.className = 'stop-btn';
                } else {
                    statusDiv.textContent = 'Trạng thái: ĐÃ DỪNG';
                    statusDiv.className = 'status status-off';
                    toggleBtn.textContent = 'BẬT BOT';
                    toggleBtn.className = '';
                }
                
                // Chỉ cập nhật nếu người dùng không đang gõ
                if (document.activeElement.id !== 'post-content') {
                    document.getElementById('post-content').value = data.post_content;
                }
                if (document.activeElement.id !== 'delay-seconds') {
                    document.getElementById('delay-seconds').value = data.delay_seconds;
                }
                
                document.getElementById('last_status').textContent = data.last_run_status;
                
            } catch (error) {
                document.getElementById('bot-status').textContent = 'Lỗi kết nối server.';
            }
        }
        
        async function toggleBot() {
            const isCurrentlyRunning = document.getElementById('bot-status').textContent.includes('ĐANG CHẠY');
            const newStatus = !isCurrentlyRunning;
            
            const content = document.getElementById('post-content').value;
            const delay = parseInt(document.getElementById('delay-seconds').value, 10);
            
            await fetch('/api/toggle_bot', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    run: newStatus,
                    content: content,
                    delay: delay
                })
            });
            
            fetchStatus(); // Cập nhật ngay
        }
        
        document.addEventListener('DOMContentLoaded', () => {
            fetchStatus();
            setInterval(fetchStatus, 3000); // Cập nhật trạng thái mỗi 3 giây
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    """Phục vụ trang web điều khiển chính."""
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/status", methods=['GET'])
def get_status():
    """Cung cấp trạng thái hiện tại của bot cho UI."""
    with lock:
        return jsonify(bot_status)

@app.route("/api/toggle_bot", methods=['POST'])
def toggle_bot():
    """Nhận lệnh Bật/Tắt và cài đặt từ UI."""
    global bot_status, lock
    data = request.get_json()
    
    with lock:
        bot_status["is_bot_running"] = data.get("run", False)
        bot_status["post_content"] = data.get("content", "")
        bot_status["delay_seconds"] = data.get("delay", 3600)
        
        if bot_status["is_bot_running"]:
            print(f"[CONTROL] Nhận lệnh BẬT bot. Delay: {bot_status['delay_seconds']}s")
            bot_status["last_run_status"] = "Đã nhận lệnh BẬT, chờ lượt chạy tiếp theo..."
        else:
            print("[CONTROL] Nhận lệnh TẮT bot.")
            bot_status["last_run_status"] = "Đã nhận lệnh TẮT."
            
    return jsonify({"status": "ok"})

# ===================================================================
# KHỞI CHẠY (ĐÃ SỬA LỖI CHO GUNICORN)
# ===================================================================

# 1. Khởi động luồng (thread) bot Facebook
# PHẢI ĐỂ BÊN NGOÀI __main__ để Gunicorn có thể chạy nó
print("[INIT] Khởi động luồng bot Facebook (chạy nền)...")
fb_thread = threading.Thread(target=run_facebook_bot, daemon=True)
fb_thread.start()

if __name__ == "__main__":
    # 2. Khởi động máy chủ web Flask (chỉ dùng khi chạy local)
    port = int(os.environ.get("PORT", 10000))
    print(f"[SERVER] Khởi động Web Server tại http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
