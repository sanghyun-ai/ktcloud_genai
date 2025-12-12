"""
기본 사용 예제 - LegalAdvisorAgent

이 예제는 법률 자문 에이전트의 기본적인 사용법을 보여줍니다.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.legal_advisor.advisor_agent import LegalAdvisorAgent, AdvisoryRequest


def example_1_basic_query():
    """예제 1: 기본 쿼리"""
    print("=" * 80)
    print("예제 1: 기본 법률 자문 요청")
    print("=" * 80)
    
    # 에이전트 초기화
    agent = LegalAdvisorAgent()
    
    # 자문 요청
    request = AdvisoryRequest(
        agent_type="judge",
        case_id="2024고합1234",
        query="살인죄 양형 기준",
        case_type="형사",
        top_k=3
    )
    
    # 응답 받기
    response = agent.handle_request(request)
    
    print("\n📄 자문 결과:")
    print(response["advisory"])
    print("\n" + "=" * 80 + "\n")


def example_2_prosecutor_request():
    """예제 2: 검사의 요청"""
    print("=" * 80)
    print("예제 2: 검사의 법률 자문 요청")
    print("=" * 80)
    
    agent = LegalAdvisorAgent()
    
    request = AdvisoryRequest(
        agent_type="prosecutor",
        case_id="2024고합5678",
        query="절도죄 구형 기준 및 유사 판례",
        case_type="형사",
        filters={
            "court": "대법원",
            "date_from": "2020-01-01"
        },
        top_k=5
    )
    
    response = agent.handle_request(request)
    
    print("\n📄 자문 결과:")
    print(response["advisory"])
    print("\n" + "=" * 80 + "\n")


def example_3_lawyer_request():
    """예제 3: 변호사의 요청"""
    print("=" * 80)
    print("예제 3: 변호사의 법률 자문 요청")
    print("=" * 80)
    
    agent = LegalAdvisorAgent()
    
    request = AdvisoryRequest(
        agent_type="lawyer",
        case_id="2024고합9999",
        query="정당방위 인정 사례",
        case_type="형사",
        top_k=3
    )
    
    response = agent.handle_request(request)
    
    print("\n📄 자문 결과:")
    print(response["advisory"])
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    # 환경 변수 체크
    if not os.getenv("POSTGRES_HOST"):
        print("⚠️ 경고: PostgreSQL 연결 정보가 설정되지 않았습니다.")
        print("   .env 파일을 설정하거나 환경 변수를 설정하세요.")
        print()
    
    # 예제 실행
    try:
        # 예제 1 실행
        example_1_basic_query()
        
        # 더 많은 예제를 실행하려면 주석 해제
        # example_2_prosecutor_request()
        # example_3_lawyer_request()
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
