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

# 🎯 목표 게시판 주소
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"

# 🔑 로그인 전용 주소 (여기로 바로 접속합니다!)
LOGIN_URL = "https://my.hongik.ac.kr/my/login.do?Refer=https://inno.hongik.ac.kr/index.aspx"

FILE_PATH = "sent_posts.txt"

def get_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # 봇 탐지 회피
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

def handle_alert(driver):
    try:
        WebDriverWait(driver, 3).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        print(f"⚠️ 팝업창 발견: {alert.text}")
        alert.accept()
        time.sleep(1)
    except TimeoutException:
        pass

def login_hongik(driver):
    print(f"🔑 로그인 페이지로 직행: {LOGIN_URL}")
    
    # 1. 로그인 페이지 직접 접속
    driver.get(LOGIN_URL)
    time.sleep(3)
    handle_alert(driver)
    driver.save_screenshot("1_login_page.png")

    try:
        print("⌨️ 아이디/비번 입력 시작...")
        
        # 홍익대 통합로그인 페이지 입력창 찾기
        # name="USER_ID" 가 확실해 보입니다.
        id_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='USER_ID']"))
        )
        id_input.clear()
        id_input.send_keys(HONGIK_ID)
        
        pw_input = driver.find_element(By.CSS_SELECTOR, "input[name='PASSWD']")
        pw_input.clear()
        pw_input.send_keys(HONGIK_PW)
        
        driver.save_screenshot("2_input_filled.png")
        
        # 엔터키로 로그인 실행
        pw_input.send_keys(Keys.RETURN)
        print("🚀 엔터 입력! 로그인 진행 중...")
        
        # 로그인 처리 대기 (넉넉하게 10초)
        time.sleep(10)
        handle_alert(driver) # 비번 변경 팝업 등 처리
        
        driver.save_screenshot("3_login_complete.png")
        print(f"📍 현재 페이지 제목: {driver.title}")
        
    except Exception as e:
        print(f"⚠️ 로그인 입력 실패: {e}")
        driver.save_screenshot("error_login.png")

def get_school_coords(school_name, region):
    try:
        geolocator = Nominatim(user_agent="hongik_final_debug_v7")
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
        # [1] 로그인 먼저 수행
        login_hongik(driver)
        
        # [2] 로그인이 된 상태(세션 유지)로 알바 게시판 이동
        print(f"🌐 게시판으로 점프: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(5) # 게시판 로딩 대기
        
        driver.save_screenshot("4_board_list.png")
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.select('table tbody tr')
        if not rows: rows = soup.select('table tr')
        
        print(f"📊 발견된 게시글 수: {len(rows)}개")
        
        new_posts_found = False
        post_links = []

        # 목록 수집
        for row in rows:
            link_tag = row.find('a')
            if not link_tag: continue
            title = link_tag.get_text(strip=True)
            href = link_tag['href']
            if "javascript" in href: continue 
            link = BASE_URL + href if href.startswith('/') else href
            
            if title not in sent_posts:
                post_links.append((title, link))

        # 상세 분석
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
            
            # 목록으로 복귀
            driver.get(TARGET_URL)
            time.sleep(2)

        if new_posts_found:
            with open(FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(sent_posts[-50:]))
            print("업데이트 완료")
        else:
            msg = f"게시글 {len(rows)}개 발견. 새 공고 없음. (로그인 직행 성공 🟢)"
            asyncio.run(send_message(msg))

    except Exception as e:
        print(f"에러 발생: {e}")
        driver.save_screenshot("error_final.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
