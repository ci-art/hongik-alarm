import requests
import os

# 깃허브에 저장된 키 가져오기
CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')
ADDRESS = "서울특별시 송파구 백제고분로 12길 8-26"

def test_naver_api():
    print("----- [네이버 API 진단 시작] -----")
    
    # 1. 키가 제대로 들어왔는지 확인 (보안을 위해 일부만 출력)
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ 실패: 깃허브 Secrets에서 키를 가져오지 못했습니다.")
        print("   -> 해결책: Secrets 이름이 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 인지 확인하세요.")
        return
    else:
        print(f"✅ 키 확인: ID는 '{CLIENT_ID[:3]}***' 로 시작합니다.")

    # 2. 주소 변환 요청 (Geocoding)
    url = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": CLIENT_ID,
        "X-NCP-APIGW-API-KEY": CLIENT_SECRET
    }
    params = {"query": ADDRESS}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        print(f"📡 응답 상태 코드: {response.status_code}")
        print(f"📩 네이버가 보낸 메시지: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('addresses'):
                print(f"🎉 성공! 좌표 변환 완료: {data['addresses'][0]['x']}, {data['addresses'][0]['y']}")
            else:
                print("❌ 실패: 네이버가 주소를 못 찾겠다고 합니다.")
                print("   -> 해결책: 주소를 '송파구 백제고분로 12길' 까지만 줄여보세요.")
        elif response.status_code == 401:
            print("❌ 실패: [인증 오류] 키가 틀렸거나 승인되지 않았습니다.")
            print("   -> 해결책: 네이버 콘솔에서 ID/Secret을 재발급받아 깃허브에 다시 등록하세요.")
        elif response.status_code == 403:
            print("❌ 실패: [권한 오류] API 사용 권한이 없습니다.")
            print("   -> 해결책: 네이버 콘솔 > Application > 변경 에서 'Geocoding'이 체크되어 있는지 다시 확인하세요.")
        else:
            print("❌ 실패: 알 수 없는 오류입니다.")

    except Exception as e:
        print(f"❌ 에러 발생: {e}")

    print("----- [진단 종료] -----")

if __name__ == "__main__":
    test_naver_api()
