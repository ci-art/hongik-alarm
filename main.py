import os
import telegram
import asyncio
import time
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

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

# 내 집 좌표 (송파구 백제고분로 12길 8-26)
MY_HOME_COORDS = (37.5088, 127.0817)

# ✅ 타겟 지역 설정 (여기에 포함된 지역만 찾음)
TARGET_REGIONS = ["송파", "강남"]

LOGIN_URL = "https://my.hongik.ac.kr/my/login.do?auty=LOGIN&referer=%2Fmy%2Findex.do%3Fauty%3D2"
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

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

def get_school_coords(school_name, region):
    try:
        geolocator = Nominatim(user_agent="hongik_target_v2")
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

# --- [상세 페이지 분석 함수 (필터링 추가)] ---
def analyze_detail_page(driver):
    print("--> 송파구/강남구 학교만 골라내는 중...")
    time.sleep(3)
    
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
                    
                    # ✅ [필터링] 송파 또는 강남이 아니면 과감히 패스!
                    is_target_region = False
                    for target in TARGET_REGIONS:
                        if target in region:
                            is_target_region = True
                            break
                    
                    if not is_target_region:
                        continue # 다음 학교로 넘어감

                    # 조건에 맞는 학교만 좌표 검색
                    print(f"   🎯 타겟 지역 발견: {school_name} ({region})")
                    school_coords = get_school_coords(school_name, region)
                    if school_coords:
                        km = calculate_distance(MY_HOME_COORDS, school_coords)
                        results.append({'name': school_name, 'region': region, 'km': km})
        
        results.sort(key=lambda x: x['km'])
        return results
    except Exception as e:
        print(f"   -> 분석 중 에러: {e}")
        return []

async def send_message(text):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text)

def main():
    # 파일이 없으면 생성
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", encoding="utf-8") as f: pass

    with open(FILE_PATH, "r", encoding="utf-8") as f:
        sent_posts = f.read().splitlines()

    print("🚀 홍익대 알바 봇 시작 (No.1 게시글 집중 공략)")
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
        
        # ✅ [수정] 무조건 첫 번째(No.1) 게시글만 가져옴
        if len(rows) > 0:
            target_row = rows[0] # 맨 위 게시글
            
            cols = target_row.select('td')
            if len(cols) >= 3:
                # 제목 추출
                title = cols[1].get_text(strip=True)
                if not title: title = cols[2].get_text(strip=True)

                print(f"🔍 No.1 게시글 확인: {title}")

                # 이미 본 글인지 확인
                if title not in sent_posts:
                    print("🆕 새로운 최신 글입니다! 분석 시작.")
                    
                    # 버튼 찾기
                    detail_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), '상세보기')] | //button[contains(text(), '상세보기')] | //input[@value='상세보기']")
                    
                    if len(detail_buttons) > 0:
                        # 첫 번째 버튼 클릭
                        first_btn = detail_buttons[0]
                        driver.execute_script("arguments[0].click();", first_btn)
                        time.sleep(3)
                        
                        # 📸 상세 화면 확인용
                        driver.save_screenshot("detail_view_no1.png")
                        
                        # 학교 분석 (송파/강남 필터링)
                        top_schools = analyze_detail_page(driver)
                        
                        msg = f"🔔 [최신 알바 공고]\n제목: {title}\n\n"
                        if top_schools:
                            msg += "🏃 **송파/강남 추천 학교**\n"
                            for idx, s in enumerate(top_schools, 1):
                                msg += f"{idx}. {s['name']} ({s['region']}) | {s['km']}km\n"
                        else:
                            msg += "(송파구/강남구 학교가 없거나 위치를 못 찾았습니다.)"

                        asyncio.run(send_message(msg))
                        
                        # 보낸 목록에 추가
                        sent_posts.append(title)
                        
                        # 파일 저장
                        with open(FILE_PATH, "w", encoding="utf-8") as f:
                            f.write("\n".join(sent_posts[-50:]))
                        print("✅ 업데이트 완료")
                        
                    else:
                        print("⚠️ 상세보기 버튼을 못 찾았습니다.")
                else:
                    print("💤 이미 확인한 글입니다. (패스)")
            else:
                print("⚠️ 게시글 구조가 이상합니다.")
        else:
            print("⚠️ 게시글이 하나도 없습니다.")

    except Exception as e:
        print(f"에러 발생: {e}")
        driver.save_screenshot("error_final.png")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
