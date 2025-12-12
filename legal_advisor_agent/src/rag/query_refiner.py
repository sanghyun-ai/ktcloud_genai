"""Query Refinement - 쿼리 정제 및 확장"""
from typing import List, Dict, Any, Optional
import re


class LegalQueryRefiner:
    """
    법률 쿼리 정제 및 확장
    
    Week 2 핵심 기능:
    - 법률 용어 추출 및 확장
    - 유사 용어 매핑
    - 멀티 쿼리 생성
    """

    def __init__(self, llm=None):
        """
        Args:
            llm: LangChain LLM 인스턴스 (선택사항)
        """
        self.llm = llm
        self.legal_term_dict = self._build_term_dict()

    def _build_term_dict(self) -> Dict[str, List[str]]:
        """
        법률 용어 사전 구축
        
        일상 용어 → 법률 용어 매핑
        """
        return {
            # 범죄 관련
            "죽이다": ["살인", "살해", "고의적 살인", "형법 제250조"],
            "사람을 죽였다": ["살인죄", "고의적 살인", "형법 제250조"],
            "훔치다": ["절도", "절취", "형법 제329조"],
            "때리다": ["폭행", "상해", "형법 제260조", "형법 제257조"],
            "사기": ["사기죄", "기망", "형법 제347조"],
            "술먹고 운전": ["음주운전", "도로교통법 위반", "도로교통법 제44조"],
            "성추행": ["강제추행", "성폭력", "형법 제298조"],
            
            # 형량 관련
            "징역": ["자유형", "형벌", "양형"],
            "집행유예": ["형의 집행유예", "선고유예", "양형"],
            "감경": ["작량감경", "양형감경", "감형"],
            
            # 절차 관련
            "고소": ["고소장", "형사고소", "수사"],
            "재판": ["형사재판", "공판", "심리"],
            "항소": ["상소", "항소심", "2심"],
        }

    def refine_query(
        self,
        query: str,
        expand: bool = True,
        use_llm: bool = False
    ) -> List[str]:
        """
        쿼리 정제 및 확장
        
        Args:
            query: 원본 쿼리
            expand: 확장 쿼리 생성 여부
            use_llm: LLM 사용 여부 (더 정교한 정제)
        
        Returns:
            정제/확장된 쿼리 리스트
        """
        refined_queries = [query]  # 원본 쿼리 포함
        
        # 1. 법률 용어 매핑
        expanded = self._expand_with_legal_terms(query)
        if expanded != query:
            refined_queries.append(expanded)
        
        # 2. 법조문 추출 및 강조
        with_articles = self._emphasize_legal_articles(query)
        if with_articles != query:
            refined_queries.append(with_articles)
        
        # 3. LLM 기반 쿼리 재작성 (선택)
        if use_llm and self.llm:
            llm_refined = self._llm_refine(query)
            refined_queries.extend(llm_refined)
        
        # 중복 제거
        return list(set(refined_queries))

    def _expand_with_legal_terms(self, query: str) -> str:
        """일상 용어를 법률 용어로 확장"""
        expanded = query
        
        for informal, legal_terms in self.legal_term_dict.items():
            if informal in query.lower():
                # 첫 번째 법률 용어로 대체
                expanded = expanded.replace(informal, legal_terms[0])
        
        return expanded

    def _emphasize_legal_articles(self, query: str) -> str:
        """
        법조문 추출 및 강조
        
        예: "형법 제250조" → "형법 제250조 살인"
        """
        # 법조문 패턴 (형법 제XXX조, 도로교통법 제XX조 등)
        pattern = r'([가-힣]+법)\s*제(\d+)조'
        matches = re.findall(pattern, query)
        
        if matches:
            # 법조문이 있으면 핵심 키워드 추가
            law_name, article_num = matches[0]
            
            # 법령별 키워드 매핑
            keyword_map = {
                "형법": {
                    "250": "살인",
                    "257": "상해",
                    "260": "폭행",
                    "329": "절도",
                    "347": "사기"
                }
            }
            
            if law_name in keyword_map and article_num in keyword_map[law_name]:
                keyword = keyword_map[law_name][article_num]
                return f"{query} {keyword}"
        
        return query

    def _llm_refine(self, query: str) -> List[str]:
        """
        LLM을 사용한 쿼리 재작성
        
        다양한 관점의 검색 쿼리 생성
        """
        if not self.llm:
            return []
        
        prompt = f"""
다음 법률 질문을 판례 검색에 최적화된 3가지 다른 표현으로 재작성하세요.

원본 질문: {query}

재작성 규칙:
1. 핵심 법률 용어를 포함하세요
2. 관련 법조문이나 판례 키워드를 추가하세요
3. 간결하고 명확하게 작성하세요

재작성된 질문 (한 줄에 하나씩):
"""
        
        try:
            response = self.llm.invoke(prompt)
            # 응답을 줄바꿈으로 분리
            refined = [
                line.strip() 
                for line in response.strip().split('\n') 
                if line.strip() and not line.strip().startswith('#')
            ]
            return refined[:3]  # 최대 3개
        except Exception as e:
            print(f"⚠️ LLM 쿼리 정제 실패: {e}")
            return []

    def extract_filters(self, query: str) -> Dict[str, Any]:
        """
        쿼리에서 필터 조건 추출
        
        예: "2020년 이후 살인죄 대법원 판례"
        → {"date_from": "2020-01-01", "court": "대법원", "crime": "살인"}
        """
        filters = {}
        
        # 1. 날짜 추출
        year_pattern = r'(\d{4})년'
        year_match = re.search(year_pattern, query)
        if year_match:
            year = year_match.group(1)
            if "이후" in query or "이상" in query:
                filters["date_from"] = f"{year}-01-01"
            elif "이전" in query or "이하" in query:
                filters["date_to"] = f"{year}-12-31"
        
        # 2. 법원 추출
        court_keywords = ["대법원", "고등법원", "지방법원", "헌법재판소"]
        for court in court_keywords:
            if court in query:
                filters["court"] = court
                break
        
        # 3. 사건 유형
        case_types = {
            "형사": ["살인", "절도", "폭행", "사기", "성폭력"],
            "민사": ["손해배상", "계약", "채무"],
            "행정": ["행정처분", "과태료"]
        }
        
        for case_type, keywords in case_types.items():
            if any(keyword in query for keyword in keywords):
                filters["case_type"] = case_type
                break
        
        return filters


class LegalDocumentFilter:
    """
    문서 필터링 로직
    
    Week 3 핵심 기능:
    - 에이전트 요청에 따른 필터 생성
    - SQL WHERE 조건 빌더
    """

    @staticmethod
    def build_sql_filter(filters: Dict[str, Any]) -> str:
        """
        필터 딕셔너리를 SQL WHERE 조건으로 변환
        
        Args:
            filters: {
                "doc_type": "precedent",
                "case_type": "형사",
                "court": "대법원",
                "date_from": "2020-01-01"
            }
        
        Returns:
            SQL WHERE 조건 문자열
        """
        conditions = []
        
        if filters.get("doc_type"):
            conditions.append(f"doc_type = '{filters['doc_type']}'")
        
        if filters.get("case_type"):
            conditions.append(f"metadata->>'case_type' = '{filters['case_type']}'")
        
        if filters.get("court"):
            conditions.append(f"metadata->>'court' LIKE '%{filters['court']}%'")
        
        if filters.get("date_from"):
            conditions.append(f"metadata->>'decision_date' >= '{filters['date_from']}'")
        
        if filters.get("date_to"):
            conditions.append(f"metadata->>'decision_date' <= '{filters['date_to']}'")
        
        return " AND ".join(conditions) if conditions else "TRUE"

    @staticmethod
    def filter_by_agent_type(agent_type: str, base_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        에이전트 유형에 따른 필터 조정
        
        Args:
            agent_type: 'judge', 'prosecutor', 'lawyer'
            base_filters: 기본 필터
        
        Returns:
            조정된 필터
        """
        filters = base_filters.copy()
        
        if agent_type == "judge":
            # 판사: 양형 기준, 판례 중심
            filters["priority_keywords"] = ["양형", "형량", "집행유예"]
        
        elif agent_type == "prosecutor":
            # 검사: 유죄 입증, 구형 기준
            filters["priority_keywords"] = ["유죄", "구형", "증거"]
        
        elif agent_type == "lawyer":
            # 변호사: 무죄, 감경 사례
            filters["priority_keywords"] = ["무죄", "감경", "정당방위", "심신미약"]
        
        return filters
