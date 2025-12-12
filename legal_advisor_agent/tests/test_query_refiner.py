"""Query Refiner 테스트"""
import pytest
from src.rag.query_refiner import LegalQueryRefiner, LegalDocumentFilter


def test_expand_with_legal_terms():
    """법률 용어 확장 테스트"""
    refiner = LegalQueryRefiner()
    
    # 일상 용어 → 법률 용어
    query = "사람을 죽였어요"
    refined = refiner._expand_with_legal_terms(query)
    
    assert "살인" in refined or "살해" in refined


def test_emphasize_legal_articles():
    """법조문 강조 테스트"""
    refiner = LegalQueryRefiner()
    
    query = "형법 제250조 관련 판례"
    refined = refiner._emphasize_legal_articles(query)
    
    # 살인 키워드가 추가되어야 함
    assert "살인" in refined


def test_refine_query():
    """쿼리 정제 종합 테스트"""
    refiner = LegalQueryRefiner()
    
    query = "술 먹고 운전하다 사고"
    refined_queries = refiner.refine_query(query, expand=True)
    
    assert len(refined_queries) > 0
    assert query in refined_queries  # 원본 쿼리 포함


def test_extract_filters():
    """필터 추출 테스트"""
    refiner = LegalQueryRefiner()
    
    # 날짜 필터
    query = "2020년 이후 대법원 살인죄 판례"
    filters = refiner.extract_filters(query)
    
    assert "date_from" in filters
    assert filters["date_from"] == "2020-01-01"
    assert "court" in filters
    assert filters["court"] == "대법원"


def test_build_sql_filter():
    """SQL 필터 빌더 테스트"""
    filters = {
        "doc_type": "precedent",
        "case_type": "형사",
        "court": "대법원"
    }
    
    sql = LegalDocumentFilter.build_sql_filter(filters)
    
    assert "doc_type = 'precedent'" in sql
    assert "case_type" in sql
    assert "court" in sql


def test_filter_by_agent_type():
    """에이전트별 필터 조정 테스트"""
    base_filters = {"case_type": "형사"}
    
    # 판사
    judge_filters = LegalDocumentFilter.filter_by_agent_type("judge", base_filters)
    assert "priority_keywords" in judge_filters
    assert "양형" in judge_filters["priority_keywords"]
    
    # 검사
    prosecutor_filters = LegalDocumentFilter.filter_by_agent_type("prosecutor", base_filters)
    assert "유죄" in prosecutor_filters["priority_keywords"]
    
    # 변호사
    lawyer_filters = LegalDocumentFilter.filter_by_agent_type("lawyer", base_filters)
    assert "무죄" in lawyer_filters["priority_keywords"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
