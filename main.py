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
from selenium.common.exceptions import NoAlertPresentException, TimeoutException, NoSuchElementException

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
        # 3초 동안 팝업 기다림
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
    
    driver.save_screenshot("1_start_page.png")

    # [1] 로그인 버튼 클릭
    try:
        print("🖱️ '로그인' 버튼 찾는 중...")
        # 통합 로그인 버튼 (보통 a 태그나 button 태그)
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '로그인')] | //button[contains(text(), '로그인')]"))
        )
        
        # 버튼을 누르기 전에 현재 창 개수 기억
        original_window = driver.current_window_handle
        windows_before = driver.window_handles
        
        login_btn.click()
        print("🖱️ 버튼 클릭 성공!")
        time.sleep(3)
        
        # [2] 새 창(팝업)이 떴는지 확인하고 거기로 이동! (중요)
        windows_after = driver.window_handles
        if len(windows_after) > len(windows_before):
            print("🚀 새 창(팝업)이 감지되었습니다! 시선을 이동합니다.")
            for window in windows_after:
                if window != original_window:
                    driver.switch_to.window(window)
                    break
        
    except Exception as e:
        print(f"⚠️ 로그인 버튼 클릭 중 문제: {e}")

    # [3] 아이디/비번 입력 (이제 진짜 로그인 화면일 것임)
    try:
        print("⌨️ 입력창 찾는 중...")
        # 페이지가 하얗게 뜨는 걸 방지하기 위해 입력창이 나올 때까지 최대 10초 대기
        id_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='USER_ID'], input[id='USER_ID'], input[type='text']"))
        )
        
        driver.save_screenshot("2_login_ready.png") # 입력 직전 찰칵
        
        id_input.clear()
        id_input.send_keys(HONGIK_ID)
        
        pw_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pw_input.clear()
        pw_input.send_keys(HONGIK_PW)
        
        # 엔터 치고 기다리기
        pw_input.send_keys(Keys.RETURN)
        print("⏳ 엔터 입력함. 로그인 처리 대기 중...")
        
        # 화면이 넘어갈 때까지 충분히 기다림 (10초)
        time.sleep(10)
        
        # 혹시 팝업(비번 변경 등)이 뜨면 닫음
        handle_alert(driver)
        
        # 만약 새 창에서 로그인했다면, 다시 원래 창으로 돌아와야 할 수도 있음
        if len(driver.window_handles) > 1:
            driver.close() # 팝업 닫기
            driver.switch_to.window(original_window) # 본래 창으로 복귀
            print("🔄 본래 창으로 복귀했습니다.")
            time.sleep(2)

        driver.save_screenshot("3_login_finished.png") # 로그인 완료 후 찰칵
        
    except Exception as e:
        print(f"⚠️ 아이디/비번 입력 실패: {e}")
        driver.save_screenshot("error_login_input.png")

def get_school_coords(school_name, region):
    try:
        geolocator = Nominatim(user_agent="hongik_final_debug_v5")
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
        login_hongik(driver)
        
        print(f"🌐 게시판으로 이동: {TARGET_URL}")
        driver.get(TARGET_URL)
        # 페이지 로딩 완료될 때까지 확실히 기다림
        time.sleep(5)
        
        # 📸 [4] 최종 게시판 화면 (여기에 글목록이 보여야 성공!)
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
            msg = f"게시글 {len(rows)}개 발견됨. 새 글 없음. (창 전환 기능 추가됨 🟢)"
            asyncio.run(send_message(msg))

    except Exception as e:
        print(f"에러 발생: {e}")
        driver.save_screenshot("error_final.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
