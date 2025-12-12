"""Legal Advisor Agent - 법률자문 AI (관련 법령/판례 제공)"""
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.agents.common.base_agent import BaseAgent, AgentMessage
from src.rag.vector_store import PostgresVectorStore
from src.rag.hybrid_search import HybridSearchEngine, CrossEncoderReranker
from src.rag.query_refiner import LegalQueryRefiner, LegalDocumentFilter
from src.api.moleg_api import MolegAPIClient, get_sentencing_guideline


@dataclass
class AdvisoryRequest:
    """자문 요청 표준 포맷"""
    agent_type: str  # 'judge', 'prosecutor', 'lawyer'
    case_id: str
    query: str
    case_type: Optional[str] = None  # '형사', '민사', '행정'
    filters: Optional[Dict[str, Any]] = None
    top_k: int = 5


class LegalAdvisorAgent(BaseAgent):
    """
    법률자문 에이전트 - 관련 법령과 판례를 제공하는 역할

    담당: 법률자문 에이전트 팀 (2인)
    역할:
    - 관련 법령 조문 제공
    - 양형기준표 정보 제공
    - 유사 판례 검색 및 분석 (RAG)
    - 법적 근거 제시
    """

    def __init__(
        self,
        vector_store: Optional[PostgresVectorStore] = None,
        use_reranking: bool = True,
        llm=None
    ):
        """
        Args:
            vector_store: 벡터 저장소 (없으면 자동 생성)
            use_reranking: Re-ranking 사용 여부
            llm: LLM 인스턴스 (쿼리 정제 및 요약용)
        """
        super().__init__(name="LegalAdvisorAgent", role="legal_advisor")
        
        # RAG 시스템 초기화
        self.vector_store = vector_store or PostgresVectorStore()
        self.hybrid_search = HybridSearchEngine(
            vector_store=self.vector_store,
            alpha=float(os.getenv("HYBRID_SEARCH_ALPHA", 0.5))
        )
        
        # Re-ranker
        self.reranker = CrossEncoderReranker() if use_reranking else None
        
        # 쿼리 정제기
        self.query_refiner = LegalQueryRefiner(llm=llm)
        
        # 법제처 API
        self.moleg_api = MolegAPIClient()
        
        # LLM (요약용)
        self.llm = llm
        
        print(f"✅ {self.name} 초기화 완료")

    async def generate_response(
        self,
        case_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AgentMessage:
        """
        법률자문 제공 (메인 메서드)
        
        Args:
            case_info: 사건 정보
                {
                    "id": "2024고합1234",
                    "case_type": "형사",
                    "crime_type": "살인",
                    "summary": "피고인이 피해자를..."
                }
            context: 요청 컨텍스트
                {
                    "requesting_agent": "prosecutor",
                    "query": "살인죄 양형 기준",
                    "specific_request": "유사 판례 및 법령 근거"
                }
        
        Returns:
            AgentMessage: 법률 자문 응답
        """
        requesting_agent = context.get("requesting_agent", "judge")
        query = context.get("query", case_info.get("summary", ""))
        
        print(f"\n{'='*60}")
        print(f"🔍 법률 자문 요청 접수")
        print(f"   요청자: {requesting_agent}")
        print(f"   쿼리: {query}")
        print(f"{'='*60}\n")
        
        # 1. 관련 법령 검색
        print("📚 1단계: 관련 법령 조회...")
        legal_provisions = self.search_legal_provisions(
            crime_type=case_info.get("crime_type", "")
        )
        
        # 2. 양형기준표 조회
        print("⚖️  2단계: 양형기준 조회...")
        sentencing_info = self.get_sentencing_guidelines(
            crime_type=case_info.get("crime_type", "")
        )
        
        # 3. 유사 판례 검색 (RAG)
        print("🔎 3단계: 유사 판례 검색 (RAG)...")
        precedents = self.search_precedents(case_info, context)
        
        # 4. 통합 응답 생성
        print("✍️  4단계: 자문 의견 생성...\n")
        advisory_content = self._compose_advisory(
            requesting_agent=requesting_agent,
            query=query,
            legal_provisions=legal_provisions,
            sentencing_info=sentencing_info,
            precedents=precedents,
            case_info=case_info
        )
        
        return AgentMessage(
            role=self.role,
            content=advisory_content,
            metadata={
                "case_id": case_info.get("id"),
                "requesting_agent": requesting_agent,
                "num_precedents": len(precedents),
                "has_sentencing_info": sentencing_info is not None
            }
        )

    def search_legal_provisions(
        self,
        crime_type: str
    ) -> Dict[str, Any]:
        """
        관련 법령 조문 검색
        
        Args:
            crime_type: 범죄 유형 (예: "살인", "절도")
        
        Returns:
            법령 정보
        """
        if not crime_type:
            return {}
        
        # 법제처 API로 법령 검색
        statutes = self.moleg_api.search_statutes(
            query=crime_type,
            display=5
        )
        
        if statutes:
            print(f"   ✓ 관련 법령 {len(statutes)}건 발견")
            # 첫 번째 법령 상세 조회
            first_statute = statutes[0]
            detail = self.moleg_api.get_statute_content(
                first_statute["id"]
            )
            return detail or first_statute
        
        print(f"   ⚠️ '{crime_type}' 관련 법령을 찾지 못했습니다.")
        return {}

    def get_sentencing_guidelines(
        self,
        crime_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        양형기준표 정보 제공
        
        Args:
            crime_type: 범죄 유형
        
        Returns:
            양형기준 정보
        """
        guideline = get_sentencing_guideline(crime_type)
        
        if guideline:
            print(f"   ✓ 양형기준 발견: {guideline['법조문']}")
        else:
            print(f"   ⚠️ '{crime_type}' 양형기준을 찾지 못했습니다.")
        
        return guideline

    def search_precedents(
        self,
        case_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        유사 판례 검색 (RAG)
        
        Week 2-3 핵심 기능:
        - 쿼리 정제
        - 하이브리드 검색
        - Re-ranking
        - 필터링
        
        Args:
            case_info: 사건 정보
            context: 검색 컨텍스트
        
        Returns:
            판례 리스트
        """
        query = context.get("query", case_info.get("summary", ""))
        requesting_agent = context.get("requesting_agent", "judge")
        
        # 1. 쿼리 정제
        print("   ⚙️  쿼리 정제 중...")
        refined_queries = self.query_refiner.refine_query(
            query,
            expand=True,
            use_llm=False  # LLM 사용 시 True
        )
        print(f"   ✓ {len(refined_queries)}개의 정제된 쿼리 생성")
        
        # 2. 필터 구성
        base_filters = context.get("filters", {})
        if case_info.get("case_type"):
            base_filters["case_type"] = case_info["case_type"]
        
        agent_filters = LegalDocumentFilter.filter_by_agent_type(
            agent_type=requesting_agent,
            base_filters=base_filters
        )
        
        # 3. 하이브리드 검색
        print("   🔍 하이브리드 검색 (BM25 + Vector)...")
        all_results = []
        
        for refined_query in refined_queries[:2]:  # 최대 2개 쿼리 사용
            results = self.hybrid_search.search(
                query=refined_query,
                doc_type="precedent",  # 판례만
                filters=agent_filters,
                top_k=20,
                method="hybrid"
            )
            all_results.extend(results)
        
        # 중복 제거 (ID 기준)
        seen_ids = set()
        unique_results = []
        for result in all_results:
            if result["id"] not in seen_ids:
                seen_ids.add(result["id"])
                unique_results.append(result)
        
        print(f"   ✓ {len(unique_results)}개의 후보 판례 발견")
        
        # 4. Re-ranking
        if self.reranker and len(unique_results) > 0:
            print("   🎯 Re-ranking 수행 중...")
            reranked = self.reranker.rerank(
                query=query,
                documents=unique_results,
                top_k=context.get("top_k", 5)
            )
            print(f"   ✓ 최종 {len(reranked)}개 판례 선정\n")
            return reranked
        
        return unique_results[:context.get("top_k", 5)]

    def _compose_advisory(
        self,
        requesting_agent: str,
        query: str,
        legal_provisions: Dict[str, Any],
        sentencing_info: Optional[Dict[str, Any]],
        precedents: List[Dict[str, Any]],
        case_info: Dict[str, Any]
    ) -> str:
        """
        자문 의견 작성
        
        에이전트 유형별 맞춤 응답 생성
        """
        # 기본 정보
        response_parts = [
            f"## 법률 자문 의견서",
            f"",
            f"**사건번호**: {case_info.get('id', 'N/A')}",
            f"**요청자**: {requesting_agent.upper()}",
            f"**쿼리**: {query}",
            f"",
            f"---",
            f""
        ]
        
        # 1. 관련 법령
        if legal_provisions:
            response_parts.append("### 📚 관련 법령")
            response_parts.append("")
            
            law_name = legal_provisions.get("name", "N/A")
            response_parts.append(f"**법령명**: {law_name}")
            
            if legal_provisions.get("articles"):
                response_parts.append("")
                response_parts.append("**주요 조문**:")
                for article in legal_provisions["articles"][:3]:
                    content = article["content"][:200]
                    response_parts.append(f"- {content}...")
            
            response_parts.append("")
        
        # 2. 양형기준
        if sentencing_info:
            response_parts.append("### ⚖️ 양형기준")
            response_parts.append("")
            response_parts.append(f"**법조문**: {sentencing_info['법조문']}")
            response_parts.append(f"**법정형**: {sentencing_info['법정형']}")
            response_parts.append("")
            
            if "기준" in sentencing_info:
                criteria = sentencing_info["기준"]
                if "일반적 기준" in criteria:
                    response_parts.append("**일반적 기준**:")
                    for level, term in criteria["일반적 기준"].items():
                        response_parts.append(f"- {level}: {term}")
                
                response_parts.append("")
                
                # 가중/감경 요소
                if "가중요소" in criteria:
                    response_parts.append("**가중요소**:")
                    for factor in criteria["가중요소"]:
                        response_parts.append(f"- {factor}")
                    response_parts.append("")
                
                if "감경요소" in criteria:
                    response_parts.append("**감경요소**:")
                    for factor in criteria["감경요소"]:
                        response_parts.append(f"- {factor}")
                    response_parts.append("")
        
        # 3. 유사 판례
        if precedents:
            response_parts.append("### 🔎 유사 판례")
            response_parts.append("")
            
            for i, prec in enumerate(precedents, 1):
                response_parts.append(f"#### [{i}] {prec.get('title', 'N/A')}")
                response_parts.append("")
                
                # 메타데이터
                metadata = prec.get("metadata", {})
                if metadata:
                    response_parts.append(f"- **법원**: {metadata.get('court', 'N/A')}")
                    response_parts.append(f"- **선고일**: {metadata.get('decision_date', 'N/A')}")
                
                # 판례 내용 (요약)
                content = prec.get("content", "")
                summary = content[:300] + "..." if len(content) > 300 else content
                response_parts.append("")
                response_parts.append(f"**판결 요지**:")
                response_parts.append(f"{summary}")
                response_parts.append("")
                
                # 유사도 점수
                score = prec.get("rerank_score") or prec.get("score", 0)
                response_parts.append(f"*관련도: {score:.2f}*")
                response_parts.append("")
        
        # 4. 에이전트별 맞춤 조언
        response_parts.append("### 💡 자문 의견")
        response_parts.append("")
        
        if requesting_agent == "judge":
            response_parts.append("**판사님께**:")
            response_parts.append("- 위 양형기준과 유사 판례를 참고하여 형량을 결정하시기 바랍니다.")
            response_parts.append("- 가중/감경 요소를 충분히 고려하시기 바랍니다.")
        
        elif requesting_agent == "prosecutor":
            response_parts.append("**검사님께**:")
            response_parts.append("- 위 판례의 유죄 입증 방법을 참고하시기 바랍니다.")
            response_parts.append("- 양형기준의 가중요소를 구형 시 활용하시기 바랍니다.")
        
        elif requesting_agent == "lawyer":
            response_parts.append("**변호사님께**:")
            response_parts.append("- 위 판례 중 감경 사례를 변론에 활용하시기 바랍니다.")
            response_parts.append("- 감경요소를 적극 주장하시기 바랍니다.")
        
        response_parts.append("")
        response_parts.append("---")
        response_parts.append(f"*본 자문은 AI 시스템에 의해 생성되었으며, 참고용입니다.*")
        
        return "\n".join(response_parts)

    def handle_request(self, request: AdvisoryRequest) -> Dict[str, Any]:
        """
        자문 요청 처리 (동기 버전)
        
        Args:
            request: AdvisoryRequest 객체
        
        Returns:
            자문 응답
        """
        import asyncio
        
        case_info = {
            "id": request.case_id,
            "case_type": request.case_type,
            "crime_type": request.query  # 간단한 매핑
        }
        
        context = {
            "requesting_agent": request.agent_type,
            "query": request.query,
            "filters": request.filters or {},
            "top_k": request.top_k
        }
        
        # 비동기 메서드를 동기로 실행
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 실행 중인 루프가 있으면 새 태스크 생성
            import nest_asyncio
            nest_asyncio.apply()
        
        response = asyncio.run(self.generate_response(case_info, context))
        
        return {
            "status": "success",
            "advisory": response.content,
            "metadata": response.metadata
        }
