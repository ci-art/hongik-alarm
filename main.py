import requests

# --- [여기에 직접 키를 적어서 테스트해보세요] ---
# ⚠️ 주의: 테스트 후에는 이 키를 지워야 안전합니다!
TEMP_CLIENT_ID = "5q54bn8o4r"       # 예: "zud7p20wei"
TEMP_CLIENT_SECRET = "bgKAVOFC2DUJk88u5M9DUGewSyYlHAeWx6ANrBQL" # 예: "UTP9..." (앞뒤 공백 조심!)

def final_test():
    print("----- [직접 입력 테스트 시작] -----")
    
    # 1. 키에 공백이 숨어있는지 확인 (제일 흔한 실수!)
    clean_id = TEMP_CLIENT_ID.strip()
    clean_secret = TEMP_CLIENT_SECRET.strip()
    
    if len(TEMP_CLIENT_ID) != len(clean_id) or len(TEMP_CLIENT_SECRET) != len(clean_secret):
        print("⚠️ 발견됨!! 키 앞뒤에 몰래 숨어있던 '띄어쓰기'를 발견했습니다.")
        print("   -> 깃허브 Secrets에 등록할 때 이 공백도 같이 들어갔을 겁니다.")
        print("   -> 코드가 자동으로 공백을 삭제하고 다시 시도합니다...")
    
    # 2. 네이버에 요청 보내기
    url = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": clean_id,
        "X-NCP-APIGW-API-KEY": clean_secret
    }
    # 주소: 송파구 백제고분로 12길 8-26
    params = {"query": "서울특별시 송파구 백제고분로 12길 8-26"}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"📩 결과 코드: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 대성공!!! 네이버 API는 정상입니다.")
            print("=> 결론: 네이버 설정은 완벽함. 깃허브 Secrets에 오타나 공백이 있었던 것임.")
            print(f"📍 찾은 좌표: {response.json()['addresses'][0]['x']}")
        else:
            print(f"❌ 여전히 실패: {response.text}")
            print("=> 결론: 네이버 클라우드 설정(결제카드, 체크박스 등) 문제임.")

    except Exception as e:
        print(f"에러: {e}")

if __name__ == "__main__":
    final_test()
