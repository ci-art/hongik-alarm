import os
import telegram
import asyncio
import time
import random
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# ✅ 탐지 회피용 드라이버
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- [1. 설정] ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
HONGIK_ID = os.environ.get('HONGIK_ID')
HONGIK_PW = os.environ.get('HONGIK_PW')

MY_HOME_COORDS = (37.5088, 127.0817)

# 로그인 주소
LOGIN_URL = "https://my.hongik.ac.kr/my/login.do?Refer=https://inno.hongik.ac.kr/index.aspx"
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

def get_browser():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new") # 최신 헤드리스
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # 드라이버 생성 (version_main을 지정하면 더 안정적이나, 자동 감지에 맡김)
    driver = uc.Chrome(options=options, headless=True, use_subprocess=False)
    return driver

def close_popup(driver):
    print("🧹 팝업창 탐색...")
    time.sleep(2)
    try:
        # Close, 닫기, x 버튼 찾기
        targets = driver.find_elements(By.XPATH, "//*[contains(text(), 'Close')] | //*[contains(text(), '닫기')] | //button[contains(@class, 'close')]")
        for btn in targets:
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                print("🚀 닫기 버튼 클릭함!")
                time.sleep(1)
                return
    except:
        pass

def login_hongik(driver):
    print(f"🔑 로그인 페이지 접속: {LOGIN_URL}")
    
    # 접속 후 충분히 대기
    driver.get(LOGIN_URL)
    time.sleep(10)
    
    # 📸 [진단 1] 접속 직후 화면 (여기서 하얀색이면 진짜 막힌 것)
    driver.save_screenshot("1_login_attempt.png")
    
    # 만약 화면이 하얗다면 HTML 소스라도 찍어본다
    if "<body></body>" in driver.page_source.replace(" ", ""):
        print("❌ 치명적 오류: 화면이 텅 비었습니다 (White Screen).")
        print("HTML Source 일부:", driver.page_source[:500])
        return

    try:
        print("⌨️ 아이디/비번 입력 시도...")
        
        # 입력창 찾기
        id_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='USER_ID']"))
        )
        id_input.clear()
        id_input.send_keys(HONGIK_ID)
        time.sleep(1) # 사람처럼 잠깐 쉬기
        
        pw_input = driver.find_element(By.CSS_SELECTOR, "input[name='PASSWD']")
        pw_input.clear()
        pw_input.send_keys(HONGIK_PW)
        
        driver.save_screenshot("2_input_filled.png")
        
        print("🖱️ 통합로그인 버튼 클릭...")
        login_btn = driver.find_element(By.XPATH, "//button[contains(text(), '통합로그인')] | //a[contains(text(), '통합로그인')]")
        driver.execute_script("arguments[0].click();", login_btn)
        
        print("🚀 로그인 요청! 대기 중...")
        time.sleep(15) # 충분히 대기
        
        driver.save_screenshot("3_popup_check.png")
        close_popup(driver)
        
        driver.save_screenshot("4_login_complete.png")
        print("✅ 로그인 단계 종료")
        
    except Exception as e:
        print(f"⚠️ 로그인 실패: {e}")
        driver.save_screenshot("error_login.png")

def get_school_coords(school_name, region):
    try:
        geolocator = Nominatim(user_agent="hongik_final_uc_v1")
        query = f"서울 {region} {school_name}"
        location = geolocator.geocode(query)
        if not location: location = geolocator.geocode(f"{region} {school_name}")
        if location: return (location.latitude, location.longitude)
        return None
    except:
        return None

def calculate_distance(coords1, coords2):
    try:
        return round(geodesic(coords1, coords2).km, 2)
    except:
        return 9999

def analyze_schools(driver, link):
    try:
        driver.get(link)
        time.sleep(3)
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
                    coords = get_school_coords(school_name, region)
                    if coords:
                        km = calculate_distance(MY_HOME_COORDS, coords)
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

    print("🚀 탐지 회피 브라우저 시작...")
    driver = get_browser()
    
    try:
        login_hongik(driver)
        
        print(f"🌐 게시판 이동: {TARGET_URL}")
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
            msg = f"게시글 {len(rows)}개 발견됨. 새 공고 없음. (탐지 회피 모드 🟢)"
            asyncio.run(send_message(msg))

    except Exception as e:
        print(f"에러 발생: {e}")
        driver.save_screenshot("error_final.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
