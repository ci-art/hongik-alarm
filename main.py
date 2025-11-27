import requests
from bs4 import BeautifulSoup
import os
import telegram
import asyncio
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [1. 설정 및 비밀키] ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

# 내 집 주소 (고정)
MY_HOME_ADDRESS = "서울특별시 송파구 백제고분로 12길 8-26"

# 대상 사이트
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

# --- [2. 네이버 지도 API 함수] ---
def get_geocode(address):
    """ 주소를 좌표(위도,경도)로 변환 """
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
            x = data['addresses'][0]['x']
            y = data['addresses'][0]['y']
            return f"{x},{y}"
        return None
    except:
        return None

def get_driving_info(start, goal):
    """ 출발지->도착지 소요 시간(분) 계산 """
    url = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET
    }
    params = {"start": start, "goal": goal, "option": "trafast"} # 실시간 빠른길
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data['code'] == 0:
            summary = data['route']['trafast'][0]['summary']
            duration_min = round(summary['duration'] / 60000) # 분 단위
            return duration_min
        return 9999
    except:
        return 9999

# --- [3. 학교 분석 함수] ---
def analyze_schools(link, home_coords):
    """ 게시글 표에서 학교를 찾아 거리 순으로 정렬 """
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
                # 표 구조: [No, 지역, 학교명] -> 인덱스 1:지역, 2:학교명
                if len(cols) >= 3:
                    region = cols[1].get_text(strip=True)
                    school_name = cols[2].get_text(strip=True)
                    
                    # 네이버 지도 검색용 쿼리 (예: 송파구 잠실고)
                    query = f"{region} {school_name}"
                    
                    # 좌표 및 거리 계산
                    school_coords = get_geocode(query)
                    if school_coords:
                        mins = get_driving_info(home_coords, school_coords)
                        if mins != 9999:
                            results.append({'name': school_name, 'mins': mins})
        
        # 시간순 정렬 (가장 빠른 순)
        results.sort(key=lambda x: x['mins'])
        return results
    except:
        return []

async def send_message(text):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text)

# --- [4. 메인 실행] ---
def main():
    # 기록 읽기
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            sent_posts = f.read().splitlines()
    else:
        sent_posts = []

    # 내 집 좌표 변환 (시작할 때 한 번만)
    home_coords = get_geocode(MY_HOME_ADDRESS)
    if not home_coords:
        print("❌ 집 주소 변환 실패. 네이버 API 설정을 확인하세요.")
        # 주소 변환 실패해도 프로그램이 죽지 않게 리턴
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

            # 내가 아직 안 본 글이면 무조건 처리
            if title not in sent_posts:
                print(f"새 글 발견! 분석 중: {title}")
                
                # 상세 페이지 들어가서 학교 분석
                top_schools = analyze_schools(link, home_coords)
                
                # 메시지 작성
                msg = f"🔔 [새 공고]\n제목: {title}\n링크: {link}\n\n"
                
                if top_schools:
                    msg += "🏃 **가까운 학교 TOP 5**\n"
                    for i, s in enumerate(top_schools[:5], 1):
                        msg += f"{i}. {s['name']} ({s['mins']}분)\n"
                else:
                    msg += "(학교 목록을 찾지 못했습니다)"

                # 전송 및 기록
                asyncio.run(send_message(msg))
                sent_posts.append(title)
                new_posts_found = True

        # --- [결과 처리] ---
        if new_posts_found:
            with open(FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(sent_posts[-50:]))
            print("업데이트 완료")
        else:
            # 🔔 공고가 없을 때도 메시지 보내기
            print("새로운 공고 없음 - 알림 전송")
            no_post_msg = "현재 새로운 공고가 없습니다. (봇 작동 중 🟢)"
            asyncio.run(send_message(no_post_msg))

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    main()
