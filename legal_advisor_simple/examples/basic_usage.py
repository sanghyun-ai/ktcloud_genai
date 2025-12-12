"""
기본 사용 예제 - LegalAdvisorAgent (Simple Version)

이 예제는 법률 자문 에이전트의 기본 골격을 보여줍니다.
실제 법령/양형/판례 조회 기능은 TODO로 남겨두었습니다.
"""
import os
import sys
import asyncio
import json

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.legal_advisor.advisor_agent import LegalAdvisorAgent


async def example_1_basic_request():
    """예제 1: 기본 자문 요청"""
    print("=" * 80)
    print("예제 1: 판사의 법률 자문 요청")
    print("=" * 80)
    
    # 에이전트 생성
    agent = LegalAdvisorAgent()
    
    # 사건 정보
    case_info = {
        "case_id": "2024고합1234",
        "crime_type": "살인",
        "charges": ["형법 제250조"],
        "facts_summary": (
            "피고인은 2024년 5월 1일 서울시 강남구에서 "
            "피해자를 흉기로 찔러 살해하였다."
        )
    }
    
    # 컨텍스트
    context = {
        "requesting_agent": "judge"
    }
    
    # 자문 요청
    response = await agent.generate_response(case_info, context)
    
    # 결과 출력
    print("\n📄 자문 결과 (JSON):")
    print("=" * 80)
    
    # JSON 파싱해서 예쁘게 출력
    try:
        content_json = json.loads(response.content)
        print(json.dumps(content_json, indent=2, ensure_ascii=False))
    except:
        print(response.content)
    
    print("\n" + "=" * 80)
    print(f"메타데이터: {response.metadata}")
    print("=" * 80 + "\n")


async def example_2_prosecutor_request():
    """예제 2: 검사의 자문 요청"""
    print("=" * 80)
    print("예제 2: 검사의 법률 자문 요청")
    print("=" * 80)
    
    agent = LegalAdvisorAgent()
    
    case_info = {
        "case_id": "2024고합5678",
        "crime_type": "절도",
        "charges": ["형법 제329조"],
        "facts_summary": "피고인은 편의점에서 물건을 훔쳤다."
    }
    
    context = {
        "requesting_agent": "prosecutor"
    }
    
    response = await agent.generate_response(case_info, context)
    
    print("\n📄 자문 결과:")
    print("=" * 80)
    
    try:
        content_json = json.loads(response.content)
        
        # 주요 정보만 출력
        print(f"\n[사건 정보]")
        print(f"  사건번호: {content_json['case']['case_id']}")
        print(f"  범죄유형: {content_json['case']['crime_type']}")
        
        print(f"\n[검색 상태]")
        print(f"  법령: {content_json['retrieval']['status']['laws']}")
        print(f"  양형기준: {content_json['retrieval']['status']['sentencing_guidelines']}")
        print(f"  판례: {content_json['retrieval']['status']['precedents']}")
        
        print(f"\n[자문 요약]")
        print(f"  {content_json['analysis']['legal_opinion']['summary']}")
        
        print(f"\n[품질 정보]")
        print(f"  신뢰도: {content_json['quality']['confidence']}")
        print(f"  수동 검토 필요: {content_json['quality']['manual_review_required']}")
        
    except:
        print(response.content)
    
    print("\n" + "=" * 80 + "\n")


async def example_3_lawyer_request():
    """예제 3: 변호사의 자문 요청"""
    print("=" * 80)
    print("예제 3: 변호사의 법률 자문 요청")
    print("=" * 80)
    
    agent = LegalAdvisorAgent()
    
    case_info = {
        "id": "2024고합9999",  # "case_id" 대신 "id" 사용 가능
        "crime_type": "폭행",
        "charges": ["형법 제260조"],
        "summary": "피고인은 피해자를 때렸다."  # "facts_summary" 대신 "summary" 사용 가능
    }
    
    context = {
        "requesting_agent": "lawyer"
    }
    
    response = await agent.generate_response(case_info, context)
    
    print("\n📄 자문 결과 (AgentMessage):")
    print("=" * 80)
    print(f"Role: {response.role}")
    print(f"Metadata: {response.metadata}")
    print(f"\nContent (일부):")
    print(response.content[:500] + "...")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("\n" + "🏛️ Legal Advisor Agent - 기본 사용 예제".center(80))
    print("=" * 80 + "\n")
    
    # 예제 실행
    try:
        # 예제 1: 기본 요청
        asyncio.run(example_1_basic_request())
        
        # 예제 2: 검사 요청
        # asyncio.run(example_2_prosecutor_request())
        
        # 예제 3: 변호사 요청
        # asyncio.run(example_3_lawyer_request())
        
    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
