"""Vector Store 테스트"""
import pytest
from src.rag.vector_store import PostgresVectorStore


@pytest.fixture
def vector_store():
    """벡터 저장소 픽스처"""
    return PostgresVectorStore()


def test_add_and_search_documents(vector_store):
    """문서 추가 및 검색 테스트"""
    # 테스트 문서
    test_docs = [
        {
            "id": "test_001",
            "doc_type": "precedent",
            "title": "테스트 판례 1",
            "content": "피고인이 피해자를 살해한 사건",
            "metadata": {"case_type": "형사"}
        },
        {
            "id": "test_002",
            "doc_type": "precedent",
            "title": "테스트 판례 2",
            "content": "피고인이 물건을 절취한 사건",
            "metadata": {"case_type": "형사"}
        }
    ]
    
    # 문서 추가
    count = vector_store.add_documents(test_docs)
    assert count == 2
    
    # 검색
    results = vector_store.search(
        query="살인 사건",
        doc_type="precedent",
        top_k=2
    )
    
    assert len(results) > 0
    assert results[0]["id"] in ["test_001", "test_002"]
    
    # 정리
    vector_store.delete_by_doc_type("precedent")


def test_search_with_filters(vector_store):
    """필터링 검색 테스트"""
    # 테스트 문서
    test_docs = [
        {
            "id": "test_filter_001",
            "doc_type": "precedent",
            "title": "형사 사건",
            "content": "형사 사건 내용",
            "metadata": {"case_type": "형사", "court": "대법원"}
        },
        {
            "id": "test_filter_002",
            "doc_type": "precedent",
            "title": "민사 사건",
            "content": "민사 사건 내용",
            "metadata": {"case_type": "민사", "court": "지방법원"}
        }
    ]
    
    vector_store.add_documents(test_docs)
    
    # 형사 사건만 검색
    results = vector_store.search(
        query="사건",
        doc_type="precedent",
        top_k=10
    )
    
    assert len(results) > 0
    
    # 정리
    vector_store.delete_by_doc_type("precedent")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
