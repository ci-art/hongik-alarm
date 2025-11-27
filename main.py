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

MY_HOME_COORDS = (37.5088, 127.0817)

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
        geolocator = Nominatim(user_agent="hongik_final_screenshot_v1")
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

# --- [상세 페이지 분석 함수] ---
def analyze_detail_page(driver):
    print("--> 상세 페이지 분석 중...")
    time.sleep(2)
    
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tables = soup.select('table')
        results = []
        
        print(f"   -> 발견된 표 개수: {len(tables)}")

        for table in tables:
            rows = table.select('tr')
            for row in rows:
                cols = row.select('td')
                if len(cols) >= 3:
                    region = cols[1].get_text(strip=True)
                    school_name = cols[2].get_text(strip=True)
                    
                    if len(school_name) < 2 or "학교" in school_name:
                         if "학교명" in school_name: continue

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
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", encoding="utf-8") as f: pass

    with open(FILE_PATH, "r", encoding="utf-8") as f:
        sent_posts = f.read().splitlines()

    print("🚀 봇 시작 (상세화면 스크린샷 포함)")
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
        
        # 목록 화면도 찍어봅니다
        driver.save_screenshot("list_view.png")
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.select('table tbody tr')
        if not rows: rows = soup.select('table tr')
        
        print(f"📊 목록에서 {len(rows)}개의 행 발견")
        
        new_posts_found = False
        
        detail_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), '상세보기')] | //button[contains(text(), '상세보기')] | //input[@value='상세보기']")
        
        for i, row in enumerate(rows):
            if i >= len(detail_buttons): break
            
            cols = row.select('td')
            if len(cols) < 3: continue
            
            title = cols[1].get_text(strip=True)
            if not title: title = cols[2].get_text(strip=True)

            if title in sent_posts:
                continue
            
            print(f"🔍 새 공고 발견! : {title}")
            
            current_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), '상세보기')] | //button[contains(text(), '상세보기')] | //input[@value='상세보기']")
            if i < len(current_buttons):
                btn = current_buttons[i]
                driver.execute_script("arguments[0].click();", btn)
                
                # 상세 페이지 로딩 대기
                time.sleep(5)
                
                # 📸 [여기가 추가됨] 상세 페이지 찰칵!
                screenshot_name = f"detail_view_{i}.png"
                driver.save_screenshot(screenshot_name)
                print(f"📸 상세 화면 저장됨: {screenshot_name}")
                
                top_schools = analyze_detail_page(driver)
                
                msg = f"🔔 [새 알바 공고]\n제목: {title}\n\n"
                if top_schools:
                    msg += "📏 **가까운 학교 TOP 5**\n"
                    for idx, s in enumerate(top_schools[:5], 1):
                        msg += f"{idx}. {s['name']} ({s['region']}) | {s['km']}km\n"
                else:
                    msg += "(학교 위치 정보 없음 또는 분석 실패)"

                asyncio.run(send_message(msg))
                sent_posts.append(title)
                new_posts_found = True
                
                driver.back()
                time.sleep(3)
            else:
                print("⚠️ 상세보기 버튼을 찾을 수 없음")

        if new_posts_found:
            with open(FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(sent_posts[-50:]))
            print("✅ 업데이트 완료")
        else:
            msg = "새로운 공고 없음 (봇 작동중 🟢)"
            asyncio.run(send_message(msg))

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
