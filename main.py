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
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

def get_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

def handle_alert(driver):
    try:
        WebDriverWait(driver, 3).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        print(f"⚠️ 팝업창 발견: {alert.text}")
        alert.accept()
        print("✅ 팝업창 닫음")
        time.sleep(1)
    except TimeoutException:
        pass

def login_hongik(driver):
    print("🔑 로그인 프로세스 시작...")
    
    driver.get(TARGET_URL)
    time.sleep(3)
    handle_alert(driver)
    
    # 📸 [1] 처음 화면 찍기
    driver.save_screenshot("1_start_page.png")

    try:
        # ✅ [수정된 부분] 먼저 '로그인' 버튼을 찾아서 클릭해야 함!
        # 화면에 보이는 '로그인' 글자가 들어간 버튼/링크를 찾음
        print("🖱️ '로그인' 버튼 찾는 중...")
        try:
            # 통합 로그인 버튼 (보통 a 태그나 button 태그)
            login_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '로그인')] | //button[contains(text(), '로그인')]"))
            )
            login_btn.click()
            print("🖱️ 버튼 클릭 성공! 로그인 페이지로 이동 중...")
            time.sleep(3)
        except:
            print("⚠️ 로그인 버튼을 못 찾았습니다. 이미 로그인 페이지거나, 로그인이 되어있을 수 있습니다.")

        # 📸 [2] 버튼 누른 후 화면 찍기
        driver.save_screenshot("2_login_form.png")

        # 이제 아이디/비번 입력 (홍익대 통합로그인 페이지 구조 예상)
        print("⌨️ 아이디/비번 입력 시도...")
        
        # 아이디 입력칸 찾기 (name="USER_ID" 또는 id="USER_ID")
        try:
            id_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='USER_ID'], input[id='USER_ID'], input[type='text']"))
            )
            id_input.clear()
            id_input.send_keys(HONGIK_ID)
        except:
            print("❌ 아이디 입력칸을 못 찾음")

        # 비번 입력칸 찾기
        try:
            pw_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            pw_input.clear()
            pw_input.send_keys(HONGIK_PW)
            pw_input.send_keys(Keys.RETURN) # 엔터
        except:
            print("❌ 비번 입력칸을 못 찾음")
        
        print("⏳ 로그인 정보 전송 완료. 대기 중...")
        time.sleep(5)
        handle_alert(driver)
        
        # 📸 [3] 로그인 완료 후 화면
        driver.save_screenshot("3_after_login.png")
        
    except Exception as e:
        print(f"⚠️ 로그인 과정 중 에러: {e}")
        driver.save_screenshot("error_login.png")

def get_school_coords(school_name, region):
    try:
        geolocator = Nominatim(user_agent="hongik_final_debug_v4")
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
        # 로그인 수행
        login_hongik(driver)
        
        # 로그인 후 게시판으로 다시 이동
        print(f"🌐 게시판으로 이동: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(3)
        handle_alert(driver)
        
        # 📸 [4] 최종 게시판 화면
        driver.save_screenshot("4_board_list.png")
        
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
            msg = f"게시글 {len(rows)}개 발견. 새 공고 없음. (버튼 클릭 성공 🟢)"
            asyncio.run(send_message(msg))

    except Exception as e:
        print(f"에러 발생: {e}")
        driver.save_screenshot("error_final.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
