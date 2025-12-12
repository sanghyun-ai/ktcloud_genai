"""Hybrid Search: BM25 + Vector Search with Re-ranking"""
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
import numpy as np
from collections import defaultdict


class HybridSearchEngine:
    """
    하이브리드 검색 엔진 (BM25 + 벡터 검색)
    
    Week 2 핵심 기능:
    - BM25 키워드 검색
    - 벡터 유사도 검색
    - RRF (Reciprocal Rank Fusion) 결합
    """

    def __init__(self, vector_store, alpha: float = 0.5):
        """
        Args:
            vector_store: PostgresVectorStore 인스턴스
            alpha: 벡터 검색 가중치 (0~1, 높을수록 의미 검색 중시)
        """
        self.vector_store = vector_store
        self.alpha = alpha
        self.bm25_index = None
        self.documents = []

    def build_bm25_index(self, documents: List[Dict[str, Any]]):
        """
        BM25 인덱스 구축
        
        Args:
            documents: 문서 리스트
                [{"id": "doc1", "content": "...", ...}]
        """
        self.documents = documents
        
        # 한국어 토크나이징 (간단한 공백 기반, 실제로는 KoNLPy 등 사용 권장)
        tokenized_corpus = [
            self._tokenize(doc["content"]) 
            for doc in documents
        ]
        
        self.bm25_index = BM25Okapi(tokenized_corpus)
        print(f"✅ BM25 인덱스 구축 완료: {len(documents)}개 문서")

    def _tokenize(self, text: str) -> List[str]:
        """
        간단한 토크나이징 (공백 기반)
        
        TODO: KoNLPy 등으로 개선 가능
        """
        # 공백 기반 분리
        tokens = text.split()
        
        # 길이 제한 및 소문자 변환
        tokens = [t.lower() for t in tokens if len(t) > 1]
        
        return tokens

    def search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        method: str = "hybrid"
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색 수행
        
        Args:
            query: 검색 쿼리
            doc_type: 문서 타입
            filters: 필터 조건
            top_k: 반환할 결과 수
            method: 'hybrid', 'vector', 'bm25'
        
        Returns:
            검색 결과 (점수순 정렬)
        """
        if method == "vector":
            return self._vector_search(query, doc_type, filters, top_k)
        
        elif method == "bm25":
            return self._bm25_search(query, doc_type, top_k)
        
        else:  # hybrid
            return self._hybrid_search(query, doc_type, filters, top_k)

    def _vector_search(
        self,
        query: str,
        doc_type: Optional[str],
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """벡터 유사도 검색"""
        return self.vector_store.search(
            query=query,
            doc_type=doc_type,
            filters=filters,
            top_k=top_k
        )

    def _bm25_search(
        self,
        query: str,
        doc_type: Optional[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """BM25 키워드 검색"""
        if self.bm25_index is None:
            raise ValueError("BM25 인덱스가 구축되지 않았습니다. build_bm25_index()를 먼저 호출하세요.")
        
        # 쿼리 토크나이징
        tokenized_query = self._tokenize(query)
        
        # BM25 점수 계산
        scores = self.bm25_index.get_scores(tokenized_query)
        
        # doc_type 필터링
        if doc_type:
            filtered_scores = [
                (i, score) for i, score in enumerate(scores)
                if self.documents[i].get("doc_type") == doc_type
            ]
        else:
            filtered_scores = list(enumerate(scores))
        
        # 점수순 정렬
        filtered_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Top-K 결과
        results = []
        for idx, score in filtered_scores[:top_k]:
            doc = self.documents[idx].copy()
            doc["score"] = float(score)
            results.append(doc)
        
        return results

    def _hybrid_search(
        self,
        query: str,
        doc_type: Optional[str],
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색 (RRF 알고리즘 사용)
        
        Reciprocal Rank Fusion:
        score = sum(1 / (rank + k)) for each method
        """
        # 1. 벡터 검색 (Top 20)
        vector_results = self._vector_search(
            query, doc_type, filters, top_k=20
        )
        
        # 2. BM25 검색 (Top 20)
        bm25_results = self._bm25_search(
            query, doc_type, top_k=20
        )
        
        # 3. RRF 점수 계산
        k = 60  # RRF 상수
        rrf_scores = defaultdict(float)
        doc_map = {}
        
        # 벡터 검색 결과 반영
        for rank, doc in enumerate(vector_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] += self.alpha / (rank + k)
            doc_map[doc_id] = doc
        
        # BM25 검색 결과 반영
        for rank, doc in enumerate(bm25_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] += (1 - self.alpha) / (rank + k)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
        
        # 4. RRF 점수순 정렬
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 5. Top-K 결과 반환
        results = []
        for doc_id, score in sorted_docs[:top_k]:
            doc = doc_map[doc_id].copy()
            doc["score"] = float(score)
            doc["hybrid_score"] = float(score)
            results.append(doc)
        
        return results


class CrossEncoderReranker:
    """
    Cross-Encoder 기반 Re-ranking
    
    Week 2 핵심 기능:
    - 쿼리-문서 쌍의 관련성 점수 재계산
    - 검색 정확도 향상
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"):
        """
        Args:
            model_name: Cross-Encoder 모델
        """
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(model_name)
            self.available = True
        except ImportError:
            print("⚠️ sentence-transformers 설치 필요. Re-ranking 비활성화됨.")
            self.available = False

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        문서 Re-ranking
        
        Args:
            query: 검색 쿼리
            documents: 검색된 문서 리스트
            top_k: 최종 반환 문서 수
        
        Returns:
            Re-ranking된 문서 리스트
        """
        if not self.available:
            # Re-ranking 불가능 시 원본 반환
            return documents[:top_k]
        
        if not documents:
            return []
        
        # 쿼리-문서 쌍 생성
        pairs = [[query, doc.get("content", "")] for doc in documents]
        
        # Cross-Encoder 점수 계산
        scores = self.model.predict(pairs)
        
        # 점수 기반 정렬
        scored_docs = [
            (doc, float(score)) 
            for doc, score in zip(documents, scores)
        ]
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Top-K 반환
        results = []
        for doc, rerank_score in scored_docs[:top_k]:
            doc_copy = doc.copy()
            doc_copy["rerank_score"] = rerank_score
            results.append(doc_copy)
        
        return results
