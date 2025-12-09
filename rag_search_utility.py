"""
Pinecone에 저장된 판례 데이터를 RAG로 검색하는 유틸리티
"""

import os
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """검색 결과 데이터 클래스"""
    case_id: int
    casename: str
    chunk_type: str
    text: str
    score: float
    metadata: Dict


class LJPRAGSearch:
    """LJP 판례 RAG 검색 클래스"""
    
    def __init__(self,
                 embedding_model_name: str = "jhgan/ko-sroberta-multitask",
                 pinecone_api_key: str = None,
                 pinecone_index_name: str = "ljp-criminal-rag"):
        """
        Args:
            embedding_model_name: 한국어 임베딩 모델
            pinecone_api_key: Pinecone API 키
            pinecone_index_name: Pinecone 인덱스 이름
        """
        self.embedding_model = SentenceTransformer(embedding_model_name)
        
        if pinecone_api_key is None:
            pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key:
            raise ValueError("Pinecone API 키가 필요합니다.")
        
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index = self.pc.Index(pinecone_index_name)
        self.index_name = pinecone_index_name
    
    def search(self,
               query: str,
               top_k: int = 5,
               filter_dict: Optional[Dict] = None,
               min_score: float = 0.0) -> List[SearchResult]:
        """
        판례 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            filter_dict: 메타데이터 필터 (예: {'casename': '강제추행'})
            min_score: 최소 유사도 점수
        
        Returns:
            SearchResult 리스트
        """
        # 쿼리 임베딩
        query_embedding = self.embedding_model.encode(
            query,
            convert_to_numpy=True
        )
        
        # 검색
        results = self.index.query(
            vector=query_embedding.tolist(),
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict
        )
        
        # 결과 변환
        search_results = []
        for match in results.matches:
            if match.score < min_score:
                continue
            
            # 메타데이터에서 텍스트 추출 (저장 시 텍스트를 메타데이터에 포함했다면)
            # 실제로는 별도 저장소에서 텍스트를 가져와야 할 수도 있음
            metadata = match.metadata
            
            search_results.append(SearchResult(
                case_id=metadata.get('case_id', -1),
                casename=metadata.get('casename', 'Unknown'),
                chunk_type=metadata.get('chunk_type', 'unknown'),
                text=metadata.get('text', ''),  # 실제 구현에서는 별도 저장소에서 가져올 수 있음
                score=match.score,
                metadata=metadata
            ))
        
        return search_results
    
    def search_by_case_type(self,
                            query: str,
                            casename: str,
                            top_k: int = 5) -> List[SearchResult]:
        """특정 사건 유형으로 필터링하여 검색"""
        return self.search(
            query=query,
            top_k=top_k,
            filter_dict={'casename': casename}
        )
    
    def search_high_priority(self,
                            query: str,
                            top_k: int = 5) -> List[SearchResult]:
        """우선순위가 높은 청크만 검색 (전체 판례)"""
        return self.search(
            query=query,
            top_k=top_k,
            filter_dict={'priority': 'high'}
        )
    
    def get_similar_cases(self,
                         case_id: int,
                         top_k: int = 5) -> List[SearchResult]:
        """특정 사건과 유사한 판례 검색"""
        # 해당 사건의 전체 판례 텍스트를 가져와서 검색
        # 실제 구현에서는 case_id로 해당 사건의 텍스트를 먼저 조회해야 함
        # 여기서는 예시로 전체 판례 우선순위로 검색
        results = self.search_high_priority(
            query=f"사건 ID {case_id}",
            top_k=top_k + 1
        )
        # 자기 자신 제외
        return [r for r in results if r.case_id != case_id][:top_k]
    
    def format_search_results(self, results: List[SearchResult]) -> str:
        """검색 결과를 읽기 쉬운 형식으로 포맷팅"""
        if not results:
            return "검색 결과가 없습니다."
        
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"""
[{결과 {i}] 유사도: {result.score:.4f}
사건명: {result.casename}
사건 ID: {result.case_id}
청크 타입: {result.chunk_type}
---
{result.text[:500]}{'...' if len(result.text) > 500 else ''}
""")
        
        return "\n".join(formatted)


# 사용 예제
if __name__ == "__main__":
    # 초기화
    rag_search = LJPRAGSearch()
    
    # 검색 예제
    print("=" * 60)
    print("검색 예제 1: 일반 검색")
    print("=" * 60)
    results = rag_search.search("강제추행 징역 6개월", top_k=3)
    print(rag_search.format_search_results(results))
    
    print("\n" + "=" * 60)
    print("검색 예제 2: 특정 사건 유형으로 필터링")
    print("=" * 60)
    results = rag_search.search_by_case_type("강제추행 징역", "강제추행", top_k=3)
    print(rag_search.format_search_results(results))
    
    print("\n" + "=" * 60)
    print("검색 예제 3: 우선순위 높은 판례만 검색")
    print("=" * 60)
    results = rag_search.search_high_priority("강제추행 처벌", top_k=3)
    print(rag_search.format_search_results(results))
