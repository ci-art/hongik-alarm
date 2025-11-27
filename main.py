import os
import telegram
import asyncio
import time
import requests # 네이버 요청용
from bs4 import BeautifulSoup

# 탐지 회피용 드라이버
import undetected_chromedriver as uc
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

# 네이버 API 키
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

# 내 집 주소 (송파구 백제고분로 12길 8-26)
# 네이버 API는 좌표 변환을 스스로 하므로 주소 텍스트만 있으면 됩니다.
MY_HOME_ADDRESS = "서울특별시 송파구 백제고분로 12길 8-26"

TARGET_REGIONS = ["송파", "강남"]

LOGIN_URL = "https://my.hongik.ac.kr/my/login.do?auty=LOGIN&referer=%2Fmy%2Findex.do%3Fauty%3D2"
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

# --- [네이버 API 함수들] ---
def get_naver_coords(address):
    """ 주소를 입력받아 (경도, 위도) 좌표를 반환 """
    url = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }
    params = {"query": address}
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data.get('addresses'):
            # 네이버는 x가 경도(longitude), y가 위도(latitude)
            x = data['addresses'][0]['x']
            y = data['addresses'][0]['y']
            return f"{x},{y}" # 문자열 "경도,위도" 반환
        else:
            return None
    except Exception as e:
        print(f"네이버 주소 변환 에러: {e}")
        return None

def get_naver_driving(start, goal):
    """ 출발지~도착지 실제 주행 거리(km)와 시간(분) 계산 """
    url = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }
    params = {
        "start": start, # 경도,위도
        "goal": goal,   # 경도,위도
        "option": "trafast" # 실시간 빠른길
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data['code'] == 0:
            summary = data['route']['trafast'][0]['summary']
            duration_min = round(summary['duration'] / 60000) # 밀리초 -> 분
            distance_km = round(summary['distance'] / 1000, 1) # 미터 -> km
            return duration_min, distance_km
        else:
            return 9999, 9999
    except Exception as e:
        print(f"네이버 거리 계산 에러: {e}")
        return 9999, 9999

# --- [브라우저 설정] ---
def get_browser():
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    driver = uc.Chrome(options=options, headless=False, use_subprocess=False)
    return driver

def close_popup(driver):
    time.sleep(2)
    try:
        try:
            driver.switch_to.alert.accept()
        except:
            pass

        targets = driver.find_elements(By.XPATH, "//*[contains(text(), 'Close')] | //*[contains(text(), '닫기')] | //button[contains(@class, 'close')]")
        for btn in targets:
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)
                return
    except:
        pass

def login_hongik(driver):
    print("🔑 로그인 시작...")
    driver.get(LOGIN_URL)
    time.sleep(5)
    
    try:
        id_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='USER_ID']"))
        )
        id_input.click()
        id_input.clear()
        id_input.send_keys(HONGIK_ID)
        time.sleep(0.5)
        
        pw_input = driver.find_element(By.CSS_SELECTOR, "input[name='PASSWD']")
        pw_input.click()
        pw_input.clear()
        pw_input.send_keys(HONGIK_PW)
        time.sleep(0.5)
        
        try:
            login_btn = driver.find_element(By.XPATH, "//button[contains(text(), '통합로그인')]")
            driver.execute_script("arguments[0].click();", login_btn)
        except:
            pw_input.send_keys(Keys.RETURN)

        print("⏳ 로그인 처리 대기 (10초)...")
        time.sleep(10)
        close_popup(driver)
        print("✅ 로그인 완료")
        
    except Exception as e:
        print(f"⚠️ 로그인 중 오류: {e}")

# --- [상세 페이지 분석 함수 (네이버 적용)] ---
def analyze_detail_page(driver):
    print("--> 네이버 지도로 분석 시작...")
    time.sleep(3)
    
    # 내 집 좌표 먼저 구하기 (API 호출)
    my_coords = get_naver_coords(MY_HOME_ADDRESS)
    if not my_coords:
        print("❌ 내 집 주소 변환 실패 (API 키 확인 필요)")
        return []

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
                    
                    # 1. 지역 필터링
                    is_target_region = False
                    for target in TARGET_REGIONS:
                        if target in region:
                            is_target_region = True
                            break
                    if not is_target_region: continue

                    # 2. 학교 이름 보정 (중 -> 중학교)
                    search_name = school_name
                    if not search_name.endswith("학교"):
                        if search_name.endswith("중"): search_name += "학교"
                        elif search_name.endswith("고"): search_name += "등학교"
                        elif search_name.endswith("초"): search_name += "등학교"

                    # 3. 네이버 API로 학교 좌표 구하기
                    full_address_query = f"서울 {region} {search_name}"
                    school_coords = get_naver_coords(full_address_query)
                    
                    if school_coords:
                        # 4. 네이버 API로 주행 거리/시간 계산
                        mins, km = get_naver_driving(my_coords, school_coords)
                        
                        if mins != 9999:
                            print(f"   🚗 {school_name}: {mins}분 ({km}km)")
                            results.append({
                                'name': school_name, 
                                'region': region, 
                                'mins': mins, 
                                'km': km
                            })
                        else:
                            print(f"   ❌ 경로 탐색 실패: {school_name}")
                    else:
                        print(f"   ❌ 위치 못 찾음: {school_name}")
        
        # 소요 시간(분) 순서로 정렬
        results.sort(key=lambda x: x['mins'])
        return results
    except Exception as e:
        print(f"   -> 분석 중 에러: {e}")
        return []

async def send_message(text):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text)

def main():
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", encoding="utf-8") as f: pass

    with open(FILE_PATH, "r", encoding="utf-8") as f:
        sent_posts = f.read().splitlines()

    print("🚀 홍익대 알바 봇 (Set 2: 네이버 지도 버전)")
    
    # 네이버 키 확인
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("❌ 네이버 API 키가 없습니다! GitHub Secrets를 확인하세요.")
        return

    try:
        driver = get_browser()
    except Exception as e:
        print(f"브라우저 실행 실패: {e}")
        return

    try:
        login_hongik(driver)
        
        print(f"🌐 게시판 목록 이동: {TARGET_URL}")
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

                print(f"🔍 No.1 게시글: {title}")

                if title not in sent_posts:
                    print("🆕 새 글 분석 시작!")
                    
                    detail_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), '상세보기')] | //button[contains(text(), '상세보기')] | //input[@value='상세보기']")
                    
                    if len(detail_buttons) > 0:
                        first_btn = detail_buttons[0]
                        driver.execute_script("arguments[0].click();", first_btn)
                        time.sleep(3)
                        
                        # 네이버 지도 분석 실행
                        top_schools = analyze_detail_page(driver)
                        
                        msg = f"🔔 [최신 알바 공고]\n제목: {title}\n\n"
                        if top_schools:
                            msg += "🚗 **내비게이션(빠른길) 순위**\n"
                            for idx, s in enumerate(top_schools, 1):
                                msg += f"{idx}. {s['name']} ({s['region']}) | ⏱️{s['mins']}분 ({s['km']}km)\n"
                        else:
                            msg += "(송파/강남 학교가 없거나 네이버 API 오류)"

                        asyncio.run(send_message(msg))
                        sent_posts.append(title)
                        
                        with open(FILE_PATH, "w", encoding="utf-8") as f:
                            f.write("\n".join(sent_posts[-50:]))
                        print("✅ 전송 완료")
                    else:
                        print("⚠️ 상세보기 버튼 없음")
                else:
                    print("💤 이미 본 글입니다.")
        else:
            print("⚠️ 게시글 없음")

    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
