import os
import telegram
import asyncio
import time
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException, TimeoutException

# --- [1. 설정] ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
HONGIK_ID = os.environ.get('HONGIK_ID')
HONGIK_PW = os.environ.get('HONGIK_PW')

MY_HOME_COORDS = (37.5088, 127.0817)

# 로그인 주소
LOGIN_URL = "https://my.hongik.ac.kr/my/login.do?Refer=https://inno.hongik.ac.kr/index.aspx"
# 목표 게시판 주소
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

def get_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# 🚨 팝업 닫기 (업그레이드: 'Close' 버튼 추가)
def close_popup(driver):
    print("🧹 팝업창(Close 버튼) 탐색 중...")
    time.sleep(3) # 팝업이 뜰 때까지 잠시 대기
    
    # 1. 브라우저 경고창(Alert) 처리
    try:
        alert = driver.switch_to.alert
        alert.accept()
        print("✅ Alert 경고창 닫음")
    except:
        pass

    # 2. 화면 내 'Close' 또는 '닫기' 버튼 찾기
    try:
        # 사진에 보이는 'Close' 텍스트를 가진 모든 요소를 찾음
        close_targets = driver.find_elements(By.XPATH, "//*[contains(text(), 'Close')] | //*[contains(text(), '닫기')]")
        
        if len(close_targets) > 0:
            print(f"🧩 닫기 버튼 후보 {len(close_targets)}개 발견! 클릭 시도...")
            for btn in close_targets:
                try:
                    # 화면에 보인다면 강제 클릭
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        print("🚀 'Close' 버튼 클릭 성공!")
                        time.sleep(2)
                        return # 성공했으니 종료
                except:
                    continue
        else:
            print("ℹ️ 닫기 버튼이 보이지 않습니다. (이미 닫혔거나 없을 수 있음)")
            
    except Exception as e:
        print(f"⚠️ 팝업 닫기 중 오류 (무시 가능): {e}")

def login_hongik(driver):
    print(f"🔑 로그인 페이지 접속: {LOGIN_URL}")
    driver.get(LOGIN_URL)
    time.sleep(3)
    
    driver.save_screenshot("1_login_page.png")

    try:
        print("⌨️ 아이디/비번 입력 중...")
        
        id_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='USER_ID']"))
        )
        id_input.clear()
        id_input.send_keys(HONGIK_ID)
        
        pw_input = driver.find_element(By.CSS_SELECTOR, "input[name='PASSWD']")
        pw_input.clear()
        pw_input.send_keys(HONGIK_PW)
        
        driver.save_screenshot("2_input_filled.png")
        
        # [통합로그인] 버튼 클릭
        print("🖱️ '통합로그인' 버튼 클릭...")
        login_btn = driver.find_element(By.XPATH, "//button[contains(text(), '통합로그인')] | //a[contains(text(), '통합로그인')]")
        driver.execute_script("arguments[0].click();", login_btn)
        
        print("⏳ 로그인 처리 및 팝업 대기 중 (5초)...")
        time.sleep(5)
        
        driver.save_screenshot("3_popup_check.png") # 팝업 떴는지 확인
        
        # ✅ 여기서 'Close' 버튼을 찾아서 닫습니다!
        close_popup(driver)
        
        driver.save_screenshot("4_login_complete.png")
        print("✅ 로그인 과정 완료")
        
    except Exception as e:
        print(f"⚠️ 로그인 실패: {e}")
        driver.save_screenshot("error_login.png")

def get_school_coords(school_name, region):
    try:
        geolocator = Nominatim(user_agent="hongik_final_debug_v9")
        query = f"서울 {region} {school_name}"
        location = geolocator.geocode(query)
        if not location:
             location = geolocator.geocode(f"{region} {school_name}")
        if location:
            return (location.latitude, location.longitude)
        return None
    except:
        return None

def calculate_distance(coords1, coords2):
    try:
        dist = geodesic(coords1, coords2).km
        return round(dist, 2)
    except:
        return 9999

def analyze_schools(driver, link):
    try:
        driver.get(link)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tables = soup.select('table')
        results = []
        for table in tables:
            rows = table.select('tr')
            for row in rows:
                cols = row.select('td')
                if len(cols) >= 3:
                    region = cols[1].get_text(strip=True)
                    school_name = cols[2].get_text(strip=True)
                    school_coords = get_school_coords(school_name, region)
                    if school_coords:
                        km = calculate_distance(MY_HOME_COORDS, school_coords)
                        results.append({'name': school_name, 'region': region, 'km': km})
        results.sort(key=lambda x: x['km'])
        return results
    except:
        return []

async def send_message(text):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text)

def main():
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            sent_posts = f.read().splitlines()
    else:
        sent_posts = []

    driver = get_browser()
    
    try:
        # 1. 로그인 (Close 팝업 처리 포함)
        login_hongik(driver)
        
        # 2. 게시판으로 이동
        print(f"🌐 게시판으로 점프: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(5)
        
        driver.save_screenshot("5_board_list.png")
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.select('table tbody tr')
        if not rows: rows = soup.select('table tr')
        
        print(f"📊 발견된 게시글 수: {len(rows)}개")
        
        new_posts_found = False
        post_links = []

        for row in rows:
            link_tag = row.find('a')
            if not link_tag: continue
            title = link_tag.get_text(strip=True)
            href = link_tag['href']
            if "javascript" in href: continue 
            link = BASE_URL + href if href.startswith('/') else href
            
            if title not in sent_posts:
                post_links.append((title, link))

        for title, link in post_links:
            print(f"🔍 분석: {title}")
            top_schools = analyze_schools(driver, link)
            
            msg = f"🔔 [새 공고]\n제목: {title}\n링크: {link}\n\n"
            if top_schools:
                msg += "📏 **직선거리 가까운 순 TOP 5**\n"
                for i, s in enumerate(top_schools[:5], 1):
                    msg += f"{i}. {s['name']} ({s['region']}) | {s['km']}km\n"
            else:
                msg += "(학교 목록 미발견)"

            asyncio.run(send_message(msg))
            sent_posts.append(title)
            new_posts_found = True
            
            driver.get(TARGET_URL)
            time.sleep(2)

        if new_posts_found:
            with open(FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(sent_posts[-50:]))
            print("업데이트 완료")
        else:
            msg = f"게시글 {len(rows)}개 발견됨. 새 공고 없음. (Close 버튼 격파 성공 🟢)"
            asyncio.run(send_message(msg))

    except Exception as e:
        print(f"에러 발생: {e}")
        driver.save_screenshot("error_final.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
