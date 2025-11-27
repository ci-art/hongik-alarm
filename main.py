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

# 🚨 내 집 좌표 고정 (송파구 백제고분로 12길 8-26 근처)
# 주소 검색 실패할 일이 없습니다.
MY_HOME_COORDS = (37.5088, 127.0817)

TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

# --- [2. 학교 좌표 찾기 함수] ---
def get_school_coords(school_name, region):
    """ 학교 이름으로 좌표를 찾습니다 """
    try:
        geolocator = Nominatim(user_agent="hongik_job_bot_final")
        # 검색 정확도를 높이기 위해 '서울' + '구' + '학교명' 조합
        query = f"서울 {region} {school_name}"
        location = geolocator.geocode(query)
        
        # 만약 못 찾으면 '서울' 빼고 다시 시도
        if not location:
             location = geolocator.geocode(f"{region} {school_name}")
             
        if location:
            return (location.latitude, location.longitude)
        return None
    except:
        return None

def calculate_distance(coords1, coords2):
    """ 두 지점 사이의 직선 거리(km) 계산 """
    try:
        dist = geodesic(coords1, coords2).km
        return round(dist, 2)
    except:
        return 9999

# --- [3. 메인 로직] ---
def analyze_schools(link):
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
                    
                    # 학교 좌표 구하기
                    school_coords = get_school_coords(school_name, region)
                    
                    if school_coords:
                        # 고정된 내 집 좌표와 거리 계산
                        km = calculate_distance(MY_HOME_COORDS, school_coords)
                        results.append({'name': school_name, 'region': region, 'km': km})
        
        # 거리순 정렬
        results.sort(key=lambda x: x['km'])
        return results

    except Exception as e:
        print(f"분석 중 에러: {e}")
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

    print(f"🏠 내 집 좌표 고정됨: {MY_HOME_COORDS}")

    try:
