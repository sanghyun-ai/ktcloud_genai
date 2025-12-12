"""Legal Advisor Agent - 법률자문 AI (관련 법령/판례 제공)"""
from datetime import datetime, timezone
from typing import Dict, Any, List
from src.agents.common.base_agent import BaseAgent, AgentMessage
from src.agents.legal_advisor.legal_advice_schema import (
    LegalAdvisorOutput,
    LegalOutputs,
    CaseInfo,
    RetrievalInfo,
    RetrievalQuery,
    RetrievalFilters,
    RetrievalStatus,
    AnalysisResult,
    LegalOpinion,
    QualityInfo,
    Coverage,
)


class LegalAdvisorAgent(BaseAgent):
    """
    법률자문 에이전트 - 관련 법령과 판례를 제공하는 역할

    담당: 법률자문 에이전트 팀 (2인)
    역할:
    - 관련 법령 조문 제공
    - 양형기준표 정보 제공
    - 유사 판례 검색 및 분석
    - 법적 근거 제시
    """

    def __init__(self):
        super().__init__(name="LegalAdvisorAgent", role="legal_advisor")
        print(f"✅ {self.name} 초기화 완료 (기본 버전)")

    async def generate_response(
        self,
        case_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AgentMessage:
        """
        법률자문 제공

        TODO: 팀원이 구현할 로직
        - 법제처 API 연동 (법령 정보)
        - 양형기준표 검색
        - RAG 시스템 연동 (판례 검색)
        - 법적 근거 요약 및 제공
        
        Args:
            case_info: 사건 정보
                {
                    "id" or "case_id": "2024고합1234",
                    "crime_type": "살인",
                    "charges": ["형법 제250조"],
                    "facts_summary": "피고인이..."
                }
            context: 추가 컨텍스트
                {
                    "requesting_agent": "judge"
                }
        """
        print(f"\n{'='*60}")
        print(f"🔍 법률 자문 요청 접수 (기본 버전)")
        print(f"{'='*60}")
        
        # 1) 입력에서 정보 추출
        case_id = case_info.get("id") or case_info.get("case_id")
        crime_type = (case_info.get("crime_type") or "").strip() or "UNKNOWN"
        charges = case_info.get("charges") or []
        facts_summary = (
            case_info.get("facts_summary") 
            or case_info.get("summary") 
            or ""
        ).strip()

        if not facts_summary:
            facts_summary = "사실관계 요약이 제공되지 않았습니다."

        print(f"   사건번호: {case_id}")
        print(f"   범죄유형: {crime_type}")
        print(f"   공소사실: {charges}")
        print(f"{'='*60}\n")

        # 2) 법령/양형/판례 검색 (TODO: 구현 필요)
        print("📚 1단계: 관련 법령 조회... (TODO: 구현 필요)")
        laws = self.search_legal_provisions(crime_type)
        
        print("⚖️  2단계: 양형기준 조회... (TODO: 구현 필요)")
        sentencing_guidelines = self.get_sentencing_guidelines(crime_type)
        
        print("🔎 3단계: 유사 판례 검색... (TODO: 구현 필요)")
        precedents = self.search_precedents(case_info)

        # 3) retrieval(검색 로그) 만들기
        retrieval = RetrievalInfo(
            query=RetrievalQuery(
                crime_type=crime_type,
                keywords=[crime_type],
                filters=RetrievalFilters(
                    court_level=[],
                    year_from=2015,
                    year_to=datetime.now().year,
                ),
            ),
            status=RetrievalStatus(
                laws="fail",                  # TODO: 구현 후 "success"로 변경
                sentencing_guidelines="fail",  # TODO: 구현 후 "success"로 변경
                precedents="fail",             # TODO: 구현 후 "success"로 변경
            ),
            errors=[
                "법령 조회 미구현",
                "양형기준 조회 미구현",
                "판례 검색 미구현"
            ],
        )

        # 4) analysis(자문 요약)
        analysis = AnalysisResult(
            issue_spotting=[],
            legal_opinion=LegalOpinion(
                summary=(
                    f"[기본 버전 응답]\n\n"
                    f"현재 단계에서는 {crime_type} 관련 법령/양형기준/판례 조회 기능이 미구현입니다.\n\n"
                    f"추후 다음 기능을 구현할 예정입니다:\n"
                    f"1. 법제처 API 연동 → 관련 법령 조문 자동 조회\n"
                    f"2. 양형기준표 데이터 → 기준 형량 및 가중/감경 요소 제공\n"
                    f"3. RAG 시스템 연동 → 유사 판례 벡터 검색 및 분석\n\n"
                    f"구현 후 근거 기반 법률 자문을 제공할 수 있습니다."
                ),
                elements_checklist=[],
                counterarguments=[],
            ),
        )

        # 5) quality - 미구현이므로 낮게 설정
        quality = QualityInfo(
            confidence=0.0,
            coverage=Coverage(laws=0.0, guidelines=0.0, precedents=0.0),
            notes=[
                "법령 조회 미구현 (MVP)",
                "양형기준 조회 미구현 (MVP)",
                "판례 검색 미구현 (MVP)"
            ],
            manual_review_required=True,
        )

        # 6) outputs를 스키마대로 묶기
        outputs = LegalOutputs(
            laws=laws if laws else [],
            sentencing_guidelines=sentencing_guidelines,
            precedents=precedents if precedents else [],
        )

        # 7) 최종 payload 만들기
        payload = LegalAdvisorOutput(
            case=CaseInfo(
                case_id=case_id if case_id is not None else "UNKNOWN",
                crime_type=crime_type,
                charges=charges,
                facts_summary=facts_summary,
            ),
            retrieval=retrieval,
            outputs=outputs,
            analysis=analysis,
            citations=[],  # TODO: 구현 시 인용 출처 추가
            quality=quality,
        )

        print("✅ 자문 응답 생성 완료 (기본 버전)\n")

        # AgentMessage로 반환
        return AgentMessage(
            role=self.role,
            content=payload.model_dump_json(indent=2),
            metadata={
                "case_id": case_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "version": "basic"
            },
        )

    def search_legal_provisions(self, crime_type: str) -> List[Dict[str, Any]]:
        """
        관련 법령 조문 검색

        TODO: 구현 필요
        - 법제처 API 호출
        - 범죄 유형에 따른 법령 매핑
        - 조문 내용 추출
        
        현재: 빈 리스트 반환
        """
        print("   ⚠️  법령 조회 미구현 - 빈 결과 반환")
        return []

    def get_sentencing_guidelines(self, crime_type: str) -> None:
        """
        양형기준표 정보 제공

        TODO: 구현 필요
        - 양형기준표 PDF 파싱 결과 조회
        - 범죄 유형별 기준 형량 제공
        - 가중/감경 요소 제시
        
        현재: None 반환
        """
        print("   ⚠️  양형기준 조회 미구현 - None 반환")
        return None

    def search_precedents(self, case_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        유사 판례 검색 (RAG)

        TODO: 구현 필요
        - 벡터 DB 연동 (PostgreSQL + pgvector 또는 Pinecone)
        - LBox Open 데이터 활용
        - 임베딩 모델로 유사도 검색
        - 판례 요약 및 분석
        
        현재: 빈 리스트 반환
        """
        print("   ⚠️  판례 검색 미구현 - 빈 결과 반환")
        return []
