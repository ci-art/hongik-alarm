import os
import telegram
import asyncio
import time
import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyvirtualdisplay import Display

# --- [1. 설정] ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
HONGIK_ID = os.environ.get('HONGIK_ID')
HONGIK_PW = os.environ.get('HONGIK_PW')

NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

# ✅ [보안 강화] 주소와 좌표를 금고(Secrets)에서 꺼내옵니다.
MY_HOME_ADDRESS = os.environ.get('MY_HOME_ADDRESS')

# 좌표 문자열("37.5,127.0")을 숫자로 변환
coords_str = os.environ.get('MY_HOME_COORDS')
if coords_str:
    lat, lon = map(float, coords_str.split(','))
    MY_HOME_COORDS_FIXED = (lat, lon)
else:
    MY_HOME_COORDS_FIXED = (0.0, 0.0) # 비상용 기본값

TARGET_REGIONS = ["송파", "강남"]

LOGIN_URL = "https://my.hongik.ac.kr/my/login.do?auty=LOGIN&referer=%2Fmy%2Findex.do%3Fauty%3D2"
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

# --- [기능 1: 네이버 지도 API] ---
def get_naver_coords(address):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET: return None
    url = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }
    try:
        response = requests.get(url, headers=headers, params={"query": address})
        data = response.json()
        if data.get('addresses'):
            return f"{data['addresses'][0]['x']},{data['addresses'][0]['y']}"
        else:
            return None
    except:
        return None

def get_naver_driving(start, goal):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET: return 9999, 9999
    url = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }
    params = {"start": start, "goal": goal, "option": "trafast"}
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data['code'] == 0:
            summary = data['route']['trafast'][0]['summary']
            return round(summary['duration'] / 60000), round(summary['distance'] / 1000, 1)
    except:
        pass
    return 9999, 9999

# --- [기능 2: 무료 지도 (비상용)] ---
def get_free_coords(school_name, region):
    try:
        geolocator = Nominatim(user_agent="hongik_hybrid_v2")
        if school_name.endswith("중") and not school_name.endswith("학교"): school_name += "학교"
        if school_name.endswith("고") and not school_name.endswith("학교"): school_name += "등학교"
        
        query = f"서울 {region} {school_name}"
        location = geolocator.geocode(query)
        if not location: location = geolocator.geocode(f"{region} {school_name}")
        
        if location: return (location.latitude, location.longitude)
    except:
        pass
    return None

def get_free_distance(coords1, coords2):
    try:
        return round(geodesic(coords1, coords2).km, 2)
    except:
        return 9999

# --- [분석 함수] ---
def analyze_smart(driver):
    print("--> 🧠 스마트 분석 시작...")
    time.sleep(3)
    
    my_naver_coords = get_naver_coords(MY_HOME_ADDRESS)
    naver_active = True if my_naver_coords else False
    
    if not naver_active:
        print("⚠️ 네이버 API 사용 불가. 무료 모드 가동.")

    try:
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
                    
                    is_target = False
                    for target in TARGET_REGIONS:
                        if target in region:
                            is_target = True
                            break
                    if not is_target: continue

                    success_naver = False
                    if naver_active:
                        full_name = f"서울 {region} {school_name}"
                        school_naver_coords = get_naver_coords(full_name)
                        
                        if school_naver_coords:
                            mins, km = get_naver_driving(my_naver_coords, school_naver_coords)
                            if mins != 9999:
                                print(f"   🚗 [Naver] {school_name}: {mins}분, {km}km")
                                results.append({
                                    'name': school_name, 'region': region, 
                                    'info': f"⏱️{mins}분 ({km}km)", 'sort_key': mins
                                })
                                success_naver = True
                    
                    if not success_naver:
                        school_free_coords = get_free_coords(school_name, region)
                        if school_free_coords:
                            km = get_free_distance(MY_HOME_COORDS_FIXED, school_free_coords)
                            print(f"   📏 [Free] {school_name}: {km}km")
                            results.append({
                                'name': school_name, 'region': region, 
                                'info': f"{km}km (직선)", 'sort_key': km
                            })
                        else:
                            print(f"   ❌ 위치 확인 불가: {school_name}")

        results.sort(key=lambda x: x['sort_key'])
        return results
    except Exception as e:
        print(f"분석 에러: {e}")
        return []

# --- [브라우저 및 로그인] ---
def get_browser():
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return uc.Chrome(options=options, headless=False, use_subprocess=False)

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
    print("🔑 로그인...")
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

    print("🚀 시크릿 모드 봇 시작 (주소 숨김)")
    try:
        driver = get_browser()
    except:
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
                print(f"🔍 최신글: {title}")

                if title not in sent_posts:
                    print("🆕 분석 시작")
                    btns = driver.find_elements(By.XPATH, "//input[@value='상세보기']")
                    if not btns: btns = driver.find_elements(By.XPATH, "//a[contains(text(),'상세보기')]")
                    
                    if btns:
                        driver.execute_script("arguments[0].click();", btns[0])
                        time.sleep(3)
                        top_schools = analyze_smart(driver)
                        
                        msg = f"🔔 [최신 알바 공고]\n제목: {title}\n\n"
                        if top_schools:
                            msg += "🏃 **가까운 학교 순위**\n"
                            for idx, s in enumerate(top_schools, 1):
                                msg += f"{idx}. {s['name']} ({s['region']}) | {s['info']}\n"
                        else:
                            msg += "(조건에 맞는 학교 없음)"

                        asyncio.run(send_message(msg))
                        sent_posts.append(title)
                        with open(FILE_PATH, "w", encoding="utf-8") as f:
                            f.write("\n".join(sent_posts[-50:]))
                        print("✅ 완료")
                    else:
                        print("⚠️ 버튼 없음")
                else:
                    print("💤 이미 본 글")
    except Exception as e:
        print(f"에러: {e}")
    finally:
        try: driver.quit()
        except: pass

if __name__ == "__main__":
    main()
