"""
FastAPI 서버 - 다른 에이전트와의 API 통신

이 서버는 판사/검사/변호사 에이전트가 HTTP API로 자문을 요청할 수 있게 합니다.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn

from src.agents.legal_advisor.advisor_agent import LegalAdvisorAgent, AdvisoryRequest


# FastAPI 앱 생성
app = FastAPI(
    title="Legal Advisor Agent API",
    description="법률 자문 에이전트 REST API",
    version="1.0.0"
)

# 전역 에이전트 인스턴스 (서버 시작 시 초기화)
agent = None


# Request/Response 모델
class AdvisoryRequestModel(BaseModel):
    agent_type: str  # 'judge', 'prosecutor', 'lawyer'
    case_id: str
    query: str
    case_type: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    top_k: int = 5


class AdvisoryResponseModel(BaseModel):
    status: str
    advisory: str
    metadata: Dict[str, Any]


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 에이전트 초기화"""
    global agent
    print("🚀 Legal Advisor Agent 초기화 중...")
    agent = LegalAdvisorAgent()
    print("✅ 초기화 완료!")


@app.get("/")
async def root():
    """헬스 체크"""
    return {
        "service": "Legal Advisor Agent API",
        "status": "running",
        "version": "1.0.0"
    }


@app.post("/api/advisory/search", response_model=AdvisoryResponseModel)
async def advisory_search(request: AdvisoryRequestModel):
    """
    법률 자문 요청
    
    사용 예:
    ```
    POST /api/advisory/search
    {
        "agent_type": "judge",
        "case_id": "2024고합1234",
        "query": "살인죄 양형 기준",
        "case_type": "형사",
        "filters": {
            "court": "대법원"
        },
        "top_k": 5
    }
    ```
    """
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    try:
        # AdvisoryRequest 객체 생성
        advisory_request = AdvisoryRequest(
            agent_type=request.agent_type,
            case_id=request.case_id,
            query=request.query,
            case_type=request.case_type,
            filters=request.filters,
            top_k=request.top_k
        )
        
        # 자문 처리
        response = agent.handle_request(advisory_request)
        
        return AdvisoryResponseModel(**response)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """상세 헬스 체크"""
    return {
        "status": "healthy",
        "agent_initialized": agent is not None,
        "database_connected": True  # TODO: 실제 DB 연결 체크
    }


# 테스트용 더미 데이터 엔드포인트
@app.get("/api/test/sample-request")
async def get_sample_request():
    """샘플 요청 데이터"""
    return {
        "agent_type": "judge",
        "case_id": "2024고합1234",
        "query": "살인죄 양형 기준",
        "case_type": "형사",
        "filters": {
            "court": "대법원",
            "date_from": "2020-01-01"
        },
        "top_k": 5
    }


if __name__ == "__main__":
    # 서버 실행
    print("=" * 80)
    print("Legal Advisor Agent API 서버 시작")
    print("=" * 80)
    print()
    print("📍 URL: http://localhost:8000")
    print("📚 API 문서: http://localhost:8000/docs")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
