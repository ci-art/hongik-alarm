import requests
from bs4 import BeautifulSoup
import os
import telegram
import asyncio
import urllib3
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [1. 설정] ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 🚨 내 집 주소 (도로명 주소로 정확하게!)
MY_HOME_ADDRESS = "서울특별시 송파구 백제고분로 12길 8-26"

TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

# --- [2. 무료 거리 계산 함수 (키 필요 없음!)] ---
def get_coords(address):
    """ 주소를 위도/경도로 변환 (무료 라이브러리 사용) """
    try:
        # user_agent는 봇의 이름표 같은 겁니다. 아무거나 영어로 적으면 됩니다.
        geolocator = Nominatim(user_agent="hongik_job_bot_v1")
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
        return None
    except:
        return None

def calculate_distance(coords1, coords2):
    """ 두 지점 사이의 직선 거리(km) 계산 """
    try:
        # geodesic은 지구의 굴곡까지 계산해서 정확합니다.
        dist = geodesic(coords1, coords2).km
        return round(dist, 2) # 소수점 2자리까지
    except:
        return 9999

# --- [3. 학교 분석 함수] ---
def analyze_schools(link, home_coords):
    print(f"--> 상세 페이지 분석 중: {link}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(link, headers=headers, verify=False)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tables = soup.select('table')
        results = []

        for table in tables:
            rows = table.select('tr')
            for row in rows:
                cols = row.select('td')
                # 표 구조: [No, 지역, 학교명]
                if len(cols) >= 3:
                    region = cols[1].get_text(strip=True)
                    school_name = cols[2].get_text(strip=True)
                    
                    # 검색어: "지역 + 학교명" (예: 송파구 잠실고)
                    # 팁: 무료 지도는 '서울특별시 송파구 잠실고' 처럼 풀네임을 좋아합니다.
                    query = f"서울특별시 {region} {school_name}"
                    
                    # 학교 좌표 구하기
                    school_coords = get_coords(query)
                    
                    if school_coords:
                        km = calculate_distance(home_coords, school_coords)
                        results.append({'name': school_name, 'region': region, 'km': km})
        
        # 거리순 정렬 (가까운 순)
        results.sort(key=lambda x: x['km'])
        return results

    except Exception as e:
        print(f"분석 중 에러: {e}")
        return []

async def send_message(text):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text)

# --- [4. 메인 실행] ---
def main():
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            sent_posts = f.read().splitlines()
    else:
        sent_posts = []

    # 내 집 좌표 미리 구하기
    print("🏠 내 집 좌표 찾는 중...")
    home_coords = get_coords(MY_HOME_ADDRESS)
    
    if not home_coords:
        # 혹시 상세주소 때문에 못 찾으면 '동'까지만 검색 시도
        print("상세 주소 검색 실패, 도로명까지만 다시 시도합니다.")
        home_coords = get_coords("서울특별시 송파구 백제고분로 12길")
    
    if not home_coords:
        print("❌ 집 주소를 못 찾겠습니다. 주소를 확인해주세요.")
        return

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(TARGET_URL, headers=headers, verify=False)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table tbody tr')
        if not rows: rows = soup.select('table tr')

        new_posts_found = False

        for row in rows:
            link_tag = row.find('a')
            if not link_tag: continue

            title = link_tag.get_text(strip=True)
            href = link_tag['href']
            link = BASE_URL + href if href.startswith('/') else href

            # 안 본 글이면 무조건 분석 (키워드 상관 X)
            if title not in sent_posts:
                print(f"🔍 새 글 분석: {title}")
                
                # 학교 분석
                top_schools = analyze_schools(link, home_coords)
                
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

        if new_posts_found:
            with open(FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(sent_posts[-50:]))
            print("업데이트 완료")
        else:
            # 🔔 공고 없을 때 생존 신고 (너무 자주 오면 여기를 주석 처리하세요)
            msg = "현재 새로운 공고가 없습니다. (무료 봇 생존 🟢)"
            asyncio.run(send_message(msg))
            print("새로운 공고 없음")

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    main()
