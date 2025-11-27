import requests
from bs4 import BeautifulSoup
import os
import telegram
import asynciohttps://github.com/ci-art/hongik-alarm/tree/main
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 깃허브 Secrets에서 정보를 가져옵니다
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
KEYWORDS = ["고사장 준비"]
TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"
BASE_URL = "https://inno.hongik.ac.kr"
FILE_PATH = "sent_posts.txt"

async def send_telegram_message(message):
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def main():
    # 1. 기존에 보낸 목록 파일에서 읽어오기
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            sent_posts = f.read().splitlines()
    else:
        sent_posts = []

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

            # 키워드 체크 & 중복 체크
            if any(keyword in title for keyword in KEYWORDS):
                if title not in sent_posts:
                    message = f"🔔 [알바 발견!]\n제목: {title}\n링크: {link}"
                    
                    # 텔레그램 전송
                    asyncio.run(send_telegram_message(message))
                    
                    # 목록에 추가
                    sent_posts.append(title)
                    new_posts_found = True

        # 2. 새로운 글이 있었다면 파일 업데이트 (최신 50개만 유지)
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
