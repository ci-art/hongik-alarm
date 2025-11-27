import requests
from bs4 import BeautifulSoup
import os
import telegram
import asyncio
import urllib3
import json

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [1. 비밀키 불러오기] ---
# 깃허브 Secrets에 저장된 값을 가져옵니다.
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')     # 아까 알려주신 ID (zud...)
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET') # 아까 알려주신 Secret (IkI...)

# --- [2. 사용자 설정] ---
# 감시할 키워드 (제목에 이 단어가 있으면 분석 시작)
KEYWORDS = ["고사장", "TOEIC", "아르바이트"]

# 🚨 내 집 주소 (고정)
MY_HOME_ADDRESS = "서울특별시 송파구 백제고분로 12길 8-26"

# 대상 사이트
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

# --- [3. 네이버 지도 API 함수] ---

def get_geocode(address):
    """ 주소를 위도/경도 좌표로 변환 (Geocoding API) """
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
            x = data['addresses'][0]['x'] # 경도
            y = data['addresses'][0]['y'] # 위도
            return f"{x},{y}"
        else:
            return None
    except Exception as e:
        print(f"주소 변환 에러({address}): {e}")
        return None

def get_driving_info(start, goal):
    """ 출발지->도착지 실제 주행 시간/거리 계산 (Driving API) """
    url = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }
    params = {
        "start": start,
        "goal": goal,
        "option": "trafast" # 실시간 빠른길
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data['code'] == 0:
            summary = data['route']['trafast'][0]['summary']
            duration_min = round(summary['duration'] / 60000) # 분 단위 변환
            distance_km = round(summary['distance'] / 1000, 1) # km 단위 변환
            return duration_min, distance_km
        else:
            return 9999, 9999 # 경로 없음
    except:
        return 9999, 9999

# --- [4. 텔레그램 전송 함수] ---
async def send_telegram_message(message):
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

# --- [5. 학교 목록 분석 및 정렬] ---
def analyze_schools_in_post(link, home_coords):
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
                # 보여주신 표 구조: [No, 지역, 학교명, ...] -> 인덱스 0, 1, 2
                if len(cols) >= 3:
                    region = cols[1].get_text(strip=True)
                    school_name = cols[2].get_text(strip=True)
                    
                    # 1. 학교 좌표 찾기 (검색어: "송파구 잠실고")
                    query = f"{region} {school_name}"
                    school_coords = get_geocode(query)
                    
                    if school_coords:
                        # 2. 거리 계산
                        mins, km = get_driving_info(home_coords, school_coords)
                        if mins != 9999:
                            results.append({
                                'name': school_name,
                                'region': region,
                                'mins': mins,
                                'km': km
                            })
        
        # 3. 시간순 정렬 (가장 빠른 순)
        results.sort(key=lambda x: x['mins'])
        return results

    except Exception as e:
        print(f"분석 중 에러: {e}")
        return []

# --- [6. 메인 실행 함수] ---
def main():
    # 저장된 파일 읽기
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            sent_posts = f.read().splitlines()
    else:
        sent_posts = []

    # 내 집 좌표 미리 변환
    home_coords = get_geocode(MY_HOME_ADDRESS)
    if not home_coords:
        print(f"❌ 집 주소 변환 실패: {MY_HOME_ADDRESS}")
        print("네이버 API ID/Secret이 올바른지 확인해주세요.")
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

            # 키워드 발견 & 안 보낸 글
            if any(keyword in title for keyword in KEYWORDS):
                if title not in sent_posts:
                    print(f"🎯 키워드 발견! 거리 계산 시작: {title}")
                    
                    # 학교 분석 시작
                    sorted_schools = analyze_schools_in_post(link, home_coords)
                    
                    # 메시지 작성
                    msg = f"🔔 [새 고사장 알림]\n제목: {title}\n링크: {link}\n"
                    
                    if sorted_schools:
                        msg += "\n🚗 **집에서 가장 빠른 학교 TOP 5**\n"
                        # 상위 5개만 추출
                        top5 = sorted_schools[:5]
                        for i, s in enumerate(top5, 1):
                            msg += f"{i}. {s['name']} ({s['region']}) | ⏱️{s['mins']}분 ({s['km']}km)\n"
                    else:
                        msg += "\n(학교 위치 정보를 찾지 못했습니다. 직접 확인해주세요.)"

                    # 전송
                    asyncio.run(send_telegram_message(msg))
                    sent_posts.append(title)
                    new_posts_found = True

        # 파일 저장
        if new_posts_found:
            with open(FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(sent_posts[-50:]))
            print("업데이트 완료")
        else:
            print("새로운 공고 없음")

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    main()
