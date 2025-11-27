import os
import telegram
import asyncio
import time
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 가짜 브라우저(Selenium)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- [1. 설정] ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
HONGIK_ID = os.environ.get('HONGIK_ID') # 🔐 아이디 가져오기
HONGIK_PW = os.environ.get('HONGIK_PW') # 🔐 비번 가져오기

# 🚨 내 집 좌표 고정
MY_HOME_COORDS = (37.5088, 127.0817)

TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

# --- [2. 브라우저 설정] ---
def get_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# --- [3. 로그인 함수 (핵심!)] ---
def login_hongik(driver):
    print("🔑 로그인 시도 중...")
    try:
        # 1. 사이트 접속 (로그인 페이지로 리다이렉트 될 것임)
        driver.get(TARGET_URL)
        time.sleep(2)
        
        # 2. 로그인 입력창 찾기 (홍익대 통합로그인 화면 기준)
        # 보통 아이디 입력창은 name='USER_ID' 또는 id='uuid' 등을 씁니다.
        # 가장 일반적인 input 태그를 찾아서 시도합니다.
        
        try:
            # 아이디 입력창 찾기 (name="USER_ID" 가 일반적)
            id_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
            )
            id_input.clear()
            id_input.send_keys(HONGIK_ID)
            
            # 비밀번호 입력창 찾기 (type="password")
            pw_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            pw_input.clear()
            pw_input.send_keys(HONGIK_PW)
            
            # 엔터키 입력 (로그인 버튼 클릭 효과)
            pw_input.send_keys(Keys.RETURN)
            
            print("⏳ 로그인 정보 입력 완료. 접속 대기 중...")
            time.sleep(5) # 로그인 후 페이지 이동 대기
            
            # 로그인 성공 여부 확인 (URL이 바뀌었거나, 특정 요소가 나왔는지)
            print(f"📍 현재 페이지 제목: {driver.title}")
            
        except Exception as e:
            print(f"⚠️ 로그인 입력 중 문제 발생 (이미 로그인 되었거나 구조가 다름): {e}")

    except Exception as e:
        print(f"❌ 로그인 전체 과정 실패: {e}")

# --- [4. 학교 좌표 및 거리 계산] ---
def get_school_coords(school_name, region):
    try:
        geolocator = Nominatim(user_agent="hongik_job_bot_final_v3")
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

# --- [5. 상세 페이지 분석] ---
def analyze_schools(driver, link):
    print(f"--> 상세 페이지 이동 중: {link}")
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

    except Exception as e:
        print(f"분석 중 에러: {e}")
        return []

async def send_message(text):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text)

# --- [6. 메인 실행] ---
def main():
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            sent_posts = f.read().splitlines()
    else:
        sent_posts = []

    print("🚀 브라우저 시작...")
    driver = get_browser()
    
    try:
        # ✅ 먼저 로그인을 수행합니다!
        login_hongik(driver)
        
        # 로그인 후 다시 타겟 페이지로 이동 (확실하게 하기 위해)
        print(f"🌐 게시판 페이지로 이동: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(3)
        
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
            print(f"🔍 새 글 분석 시작: {title}")
            top_schools = analyze_schools(driver, link)
            
            msg = f"🔔 [새 공고]\n제목: {title}\n링크: {link}\n\n"
            
            if top_schools:
                msg += "📏 **직선거리 가까운 순 TOP 5**\n"
                for i, s in enumerate(top_schools[:5], 1):
                    msg += f"{i}. {s['name']} ({s['region']}) | {s['km']}km\n"
            else:
                msg += "(학교 목록을 찾지 못했습니다)"

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
            msg = "현재 새로운 공고가 없습니다. (로그인 버전 🟢)"
            asyncio.run(send_message(msg))
            print("새로운 공고 없음")

    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
