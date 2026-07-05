import os
import telegram
import asyncio
import time
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyvirtualdisplay import Display

# --- [사용자 설정] ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
HONGIK_ID = os.environ.get('HONGIK_ID')
HONGIK_PW = os.environ.get('HONGIK_PW')

LOGIN_URL = "https://my.hongik.ac.kr/my/login.do?auty=LOGIN&referer=%2Fmy%2Findex.do%3Fauty%3D2"
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
FILE_PATH = "sent_posts.txt"

def get_browser():
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled") # 봇 탐지 회피
    
    # 💡 핵심: 깃허브 서버의 크롬 버전에 맞는 조종사를 자동으로 섭외함
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # 봇이 아닌 척 위장
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """ Object.defineProperty(navigator, 'webdriver', { get: () => undefined }) """
    })
    
    return driver

def close_popup(driver):
    time.sleep(2)
    try:
        try:
            driver.switch_to.alert.accept()
        except: pass
        targets = driver.find_elements(By.XPATH, "//*[contains(text(), 'Close')] | //*[contains(text(), '닫기')] | //button[contains(@class, 'close')]")
        for btn in targets:
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)
                return
    except: pass

def login_hongik(driver):
    print("🔑 로그인 시작...")
    driver.get(LOGIN_URL)
    time.sleep(8)
    try:
        id_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='USER_ID']")))
        id_input.click(); id_input.clear(); id_input.send_keys(HONGIK_ID); time.sleep(0.5)
        pw_input = driver.find_element(By.CSS_SELECTOR, "input[name='PASSWD']")
        pw_input.click(); pw_input.clear(); pw_input.send_keys(HONGIK_PW); time.sleep(0.5)
        
        try:
            login_btn = driver.find_element(By.XPATH, "//button[contains(text(), '통합로그인')]")
            driver.execute_script("arguments[0].click();", login_btn)
        except:
            pw_input.send_keys(Keys.RETURN)
        
        time.sleep(10)
        close_popup(driver)
        print("✅ 로그인 완료")
    except Exception as e:
        print(f"로그인 에러: {e}")

async def send_message(text):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text)

def main():
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", encoding="utf-8") as f: pass
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        sent_posts = f.read().splitlines()

    print("🚀 홍익대 초간단 새 글 알림 봇 (버전 자동맞춤 적용)")
    try:
        driver = get_browser()
    except Exception as e:
        print(f"브라우저 에러: {e}")
        return

    try:
        login_hongik(driver)
        print(f"🌐 게시판 이동: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(5)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.select('table tbody tr')
        if not rows: rows = soup.select('table tr')
        
        if len(rows) > 0:
            target_row = rows[0]
            cols = target_row.select('td')
            if len(cols) >= 3:
                title = cols[1].get_text(strip=True)
                if not title: title = cols[2].get_text(strip=True)
                print(f"🔍 최신글 확인: {title}")

                if title not in sent_posts:
                    print("🆕 새로운 글 발견! 텔레그램으로 보냅니다.")
                    
                    msg = f"🔔 [새로운 알바 공고 등록]\n\n📌 제목: {title}\n\n👉 링크 들어가서 확인하기:\n{TARGET_URL}"
                    asyncio.run(send_message(msg))
                    
                    sent_posts.append(title)
                    with open(FILE_PATH, "w", encoding="utf-8") as f:
                        f.write("\n".join(sent_posts[-50:]))
                    print("✅ 전송 및 저장 완료")
                else:
                    print("💤 이미 확인한 게시글입니다.")
    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        try: driver.quit()
        except: pass

if __name__ == "__main__":
    main()
