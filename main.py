import requests
from bs4 import BeautifulSoup
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET_URL = "https://inno.hongik.ac.kr/EmpInfo/Part/B/partb0020s.aspx?mc=0638"

def debug_site():
    print("----- [웹사이트 투시 시작] -----")
    
    try:
        # 1. 봇이 아닌 척 위장하기 (User-Agent)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(TARGET_URL, headers=headers, verify=False)
        response.encoding = 'utf-8' # 한글 깨짐 방지
        
        print(f"📡 접속 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. 표(Table)가 있는지 확인
            tables = soup.select('table')
            print(f"📊 발견된 표(Table) 개수: {len(tables)}개")
            
            # 3. 행(tr)이 있는지 확인
            rows = soup.select('tr')
            print(f"📑 발견된 행(tr) 개수: {len(rows)}개")
            
            # 4. 링크(a)가 있는지 확인
            links = soup.select('a')
            print(f"🔗 발견된 링크(a) 개수: {len(links)}개")
            
            # 5. 혹시 내용이 아예 없는지 확인 (보안 차단 시 글자 수가 적음)
            print(f"📄 전체 글자 수: {len(response.text)}자")
            
            if len(rows) > 0:
                print("\n[첫 번째 줄 내용 미리보기]:")
                print(rows[0].prettify()[:500]) # 앞부분만 살짝 출력
            else:
                print("\n❌ 경고: 게시글 줄(tr)을 하나도 못 찾았습니다!")
                print("웹사이트가 표(Table) 구조가 아니거나, 자바스크립트로 로딩되는 방식일 수 있습니다.")

        else:
            print("❌ 접속 실패! 학교 서버가 봇을 차단했을 수 있습니다.")

    except Exception as e:
        print(f"에러 발생: {e}")

    print("----- [진단 종료] -----")

if __name__ == "__main__":
    debug_site()
