import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException

# ===================================================================
# CẤU HÌNH
# ===================================================================

# Tên tệp cookie mà Render tạo ra từ "Secret File"
COOKIE_FILE = 'cookie.json' 

# Nội dung bạn muốn đăng
POST_CONTENT = "Đây là bài đăng tự động từ bot Selenium trên Render! (Test lặp lại)"

BASE_URL = "https://m.facebook.com"

# ===================================================================
# THỜI GIAN NGHỈ
# ===================================================================

# Đặt thời gian nghỉ giữa mỗi lần đăng (tính bằng giây)
# Bạn PHẢI thay đổi con số này cho phù hợp với nhu cầu
#
# VÍ DỤ:
# 60 * 15 = 900 giây (15 phút)
# 60 * 60 = 3600 giây (1 giờ)
# 60 * 60 * 6 = 21600 giây (6 giờ)
#
DELAY_BETWEEN_POSTS = 3600  # Hiện đang đặt là 1 giờ

# ===================================================================
# CÁC HÀM CỦA BOT (Giữ nguyên như trước)
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
    print("INFO: Đang đăng nhập bằng cookie...")
    
    if not os.path.exists(cookie_file):
        print(f"LỖI: Không tìm thấy tệp cookie '{cookie_file}'.")
        print("Bạn đã cấu hình 'Secret File' trên Render chưa?")
        return False
        
    try:
        with open(cookie_file, 'r') as f:
            cookies = json.load(f)
        
        driver.get(BASE_URL)
        time.sleep(1)

        for cookie in cookies:
            if 'sameSite' in cookie:
                del cookie['sameSite']
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
    """Đăng bài viết lên tường cá nhân (trên bản di động)."""
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

        except NoSuchElementException:
            print("LỖI: Không tìm thấy ô đăng bài hoặc nút 'Post'.")
            print("INFO: Giao diện Facebook có thể đã thay đổi.")

    except Exception as e:
        print(f"LỖI: Đã xảy ra lỗi khi đăng bài: {e}")

# ===================================================================
# VÒNG LẶP CHÍNH (Chạy liên tục)
# ===================================================================
if __name__ == "__main__":
    print(f"INFO: Bot Facebook (Background Worker) đang khởi động...")
    print(f"INFO: Tần suất lặp lại: mỗi {DELAY_BETWEEN_POSTS} giây.")
    
    while True:
        bot_driver = None  # Đảm bảo driver được reset mỗi lần lặp
        try:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Bắt đầu một lượt chạy mới...")
            
            bot_driver = create_driver()
            
            if bot_driver:
                if login_with_cookie(bot_driver, COOKIE_FILE):
                    # Nếu đăng nhập thành công, thực hiện hành động
                    post_to_wall(bot_driver, POST_CONTENT)
                
                print("INFO: Lượt chạy hoàn tất. Đóng trình duyệt.")
                bot_driver.quit()
            else:
                print("LỖI: Không thể tạo driver. Sẽ thử lại sau.")

        except Exception as e:
            print(f"LỖI NGHIÊM TRỌNG: Đã xảy ra lỗi trong vòng lặp chính: {e}")
            if bot_driver:
                print("WARN: Cố gắng đóng driver bị lỗi...")
                bot_driver.quit()
        
        print(f"INFO: Bot sẽ nghỉ trong {DELAY_BETWEEN_POSTS} giây...")
        time.sleep(DELAY_BETWEEN_POSTS)