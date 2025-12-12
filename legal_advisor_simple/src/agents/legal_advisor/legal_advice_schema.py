"""Legal Advisor Output Schema - Pydantic 모델 정의"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# 사건 정보 (Case Information)
# ============================================================================

class CaseInfo(BaseModel):
    """사건 기본 정보"""
    case_id: str = Field(description="사건 번호")
    crime_type: str = Field(description="범죄 유형 (예: 살인, 절도)")
    charges: List[str] = Field(default_factory=list, description="공소 사실 (법조문)")
    facts_summary: str = Field(description="사건 사실관계 요약")


# ============================================================================
# 검색/조회 정보 (Retrieval Information)
# ============================================================================

class RetrievalFilters(BaseModel):
    """검색 필터 조건"""
    court_level: List[str] = Field(default_factory=list, description="법원 레벨 (대법원, 고등법원 등)")
    year_from: Optional[int] = Field(default=None, description="검색 시작 연도")
    year_to: Optional[int] = Field(default=None, description="검색 종료 연도")


class RetrievalQuery(BaseModel):
    """검색 쿼리 정보"""
    crime_type: str = Field(description="범죄 유형")
    keywords: List[str] = Field(default_factory=list, description="검색 키워드")
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters, description="필터 조건")


class RetrievalStatus(BaseModel):
    """각 데이터 소스별 조회 상태"""
    laws: Literal["success", "fail", "skip"] = Field(default="skip", description="법령 조회 상태")
    sentencing_guidelines: Literal["success", "fail", "skip"] = Field(default="skip", description="양형기준 조회 상태")
    precedents: Literal["success", "fail", "skip"] = Field(default="skip", description="판례 조회 상태")


class RetrievalInfo(BaseModel):
    """검색/조회 로그"""
    query: RetrievalQuery = Field(description="검색 쿼리")
    status: RetrievalStatus = Field(description="데이터 소스별 상태")
    errors: List[str] = Field(default_factory=list, description="에러 메시지")


# ============================================================================
# 법률 데이터 (Legal Data Outputs)
# ============================================================================

class LawItem(BaseModel):
    """법령 조문"""
    law_name: str = Field(description="법령명 (예: 형법)")
    article_number: str = Field(description="조문 번호 (예: 제250조)")
    article_title: Optional[str] = Field(default=None, description="조문 제목")
    content: str = Field(description="조문 내용")
    relevant_reason: Optional[str] = Field(default=None, description="이 조문이 관련된 이유")


class SentencingRange(BaseModel):
    """양형 범위"""
    min_months: Optional[int] = Field(default=None, description="최소 형량 (월)")
    max_months: Optional[int] = Field(default=None, description="최대 형량 (월)")
    description: str = Field(description="범위 설명 (예: 3년~5년)")


class SentencingGuidelines(BaseModel):
    """양형기준표 정보"""
    crime_type: str = Field(description="범죄 유형")
    legal_basis: str = Field(description="법적 근거 (법조문)")
    basic_range: SentencingRange = Field(description="기본 형량 범위")
    mitigated_range: Optional[SentencingRange] = Field(default=None, description="감경 범위")
    aggravated_range: Optional[SentencingRange] = Field(default=None, description="가중 범위")
    mitigating_factors: List[str] = Field(default_factory=list, description="감경 요소")
    aggravating_factors: List[str] = Field(default_factory=list, description="가중 요소")


class PrecedentItem(BaseModel):
    """판례 정보"""
    case_number: str = Field(description="사건 번호")
    court: str = Field(description="법원명")
    decision_date: str = Field(description="선고일")
    summary: str = Field(description="판결 요지")
    relevance_score: Optional[float] = Field(default=None, description="유사도 점수")
    reasoning: Optional[str] = Field(default=None, description="판결 이유 요약")


class LegalOutputs(BaseModel):
    """법률 자료 조회 결과"""
    laws: List[LawItem] = Field(default_factory=list, description="관련 법령")
    sentencing_guidelines: Optional[SentencingGuidelines] = Field(default=None, description="양형기준")
    precedents: List[PrecedentItem] = Field(default_factory=list, description="유사 판례")


# ============================================================================
# 분석 결과 (Analysis Results)
# ============================================================================

class LegalOpinion(BaseModel):
    """법률 의견"""
    summary: str = Field(description="자문 요약")
    elements_checklist: List[str] = Field(default_factory=list, description="구성요건 체크리스트")
    counterarguments: List[str] = Field(default_factory=list, description="예상 반론")


class AnalysisResult(BaseModel):
    """사건 분석 결과"""
    issue_spotting: List[str] = Field(default_factory=list, description="쟁점 정리")
    legal_opinion: LegalOpinion = Field(description="법률 의견")


# ============================================================================
# 품질 정보 (Quality Information)
# ============================================================================

class Coverage(BaseModel):
    """데이터 커버리지"""
    laws: float = Field(default=0.0, ge=0.0, le=1.0, description="법령 커버리지 (0~1)")
    guidelines: float = Field(default=0.0, ge=0.0, le=1.0, description="양형기준 커버리지 (0~1)")
    precedents: float = Field(default=0.0, ge=0.0, le=1.0, description="판례 커버리지 (0~1)")


class QualityInfo(BaseModel):
    """응답 품질 정보"""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="전체 신뢰도 (0~1)")
    coverage: Coverage = Field(default_factory=Coverage, description="데이터 커버리지")
    notes: List[str] = Field(default_factory=list, description="품질 관련 메모")
    manual_review_required: bool = Field(default=False, description="수동 검토 필요 여부")


# ============================================================================
# 최종 출력 (Final Output)
# ============================================================================

class LegalAdvisorOutput(BaseModel):
    """법률 자문 에이전트 최종 출력"""
    case: CaseInfo = Field(description="사건 정보")
    retrieval: RetrievalInfo = Field(description="검색/조회 로그")
    outputs: LegalOutputs = Field(description="법률 자료")
    analysis: AnalysisResult = Field(description="분석 결과")
    citations: List[str] = Field(default_factory=list, description="인용 출처")
    quality: QualityInfo = Field(description="품질 정보")
    
    class Config:
        json_schema_extra = {
            "example": {
                "case": {
                    "case_id": "2024고합1234",
                    "crime_type": "살인",
                    "charges": ["형법 제250조"],
                    "facts_summary": "피고인이 피해자를..."
                },
                "retrieval": {
                    "query": {
                        "crime_type": "살인",
                        "keywords": ["살인", "형법 제250조"],
                        "filters": {
                            "court_level": ["대법원"],
                            "year_from": 2020,
                            "year_to": 2024
                        }
                    },
                    "status": {
                        "laws": "success",
                        "sentencing_guidelines": "success",
                        "precedents": "success"
                    },
                    "errors": []
                },
                "outputs": {
                    "laws": [
                        {
                            "law_name": "형법",
                            "article_number": "제250조",
                            "article_title": "살인",
                            "content": "사람을 살해한 자는 사형, 무기 또는 5년 이상의 징역에 처한다.",
                            "relevant_reason": "본 사건의 기본 법조문"
                        }
                    ],
                    "sentencing_guidelines": {
                        "crime_type": "살인",
                        "legal_basis": "형법 제250조",
                        "basic_range": {
                            "min_months": 84,
                            "max_months": 132,
                            "description": "7년~11년"
                        },
                        "mitigating_factors": ["우발적 범행", "진지한 반성"],
                        "aggravating_factors": ["계획적 범행", "잔혹한 방법"]
                    },
                    "precedents": []
                },
                "analysis": {
                    "issue_spotting": ["고의 인정 여부", "양형 감경 사유"],
                    "legal_opinion": {
                        "summary": "형법 제250조 살인죄가 성립하며...",
                        "elements_checklist": ["고의", "살해 행위", "사망 결과"],
                        "counterarguments": []
                    }
                },
                "citations": [],
                "quality": {
                    "confidence": 0.85,
                    "coverage": {
                        "laws": 1.0,
                        "guidelines": 1.0,
                        "precedents": 0.0
                    },
                    "notes": ["판례 검색 미구현"],
                    "manual_review_required": False
                }
            }
        }
