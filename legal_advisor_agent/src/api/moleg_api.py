"""법제처 Open API 연동 모듈"""
import os
import requests
from typing import List, Dict, Any, Optional
import xml.etree.ElementTree as ET
from urllib.parse import urlencode


class MolegAPIClient:
    """
    법제처(Ministry of Government Legislation) Open API 클라이언트
    
    제공 데이터:
    - 현행 법령
    - 판례
    - 법령해석례
    - 행정심판례
    """

    BASE_URL = "http://www.law.go.kr/DRF"

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: 법제처 Open API 키
        """
        self.api_key = api_key or os.getenv("MOLEG_API_KEY", "")
        
        if not self.api_key:
            print("⚠️ 법제처 API 키가 설정되지 않았습니다.")
            print("   .env 파일에 MOLEG_API_KEY를 설정하거나")
            print("   https://www.law.go.kr/DRF/lawService.do 에서 발급받으세요.")

    def search_statutes(
        self,
        query: str,
        display: int = 10,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        현행 법령 검색
        
        Args:
            query: 검색어 (예: "형법", "도로교통법")
            display: 페이지당 결과 수
            page: 페이지 번호
        
        Returns:
            법령 목록
        """
        endpoint = f"{self.BASE_URL}/lawSearch.do"
        
        params = {
            "OC": self.api_key,
            "target": "law",
            "type": "JSON",
            "query": query,
            "display": display,
            "page": page
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("law"):
                return [
                    {
                        "id": item.get("법령일련번호"),
                        "name": item.get("법령명한글"),
                        "law_type": item.get("법령구분"),
                        "enact_date": item.get("제정일자"),
                        "law_id": item.get("법령ID")
                    }
                    for item in data["law"]
                ]
            return []
        
        except Exception as e:
            print(f"❌ 법령 검색 실패: {e}")
            return []

    def get_statute_content(
        self,
        law_serial_no: str
    ) -> Optional[Dict[str, Any]]:
        """
        법령 본문 조회
        
        Args:
            law_serial_no: 법령일련번호
        
        Returns:
            법령 상세 정보
        """
        endpoint = f"{self.BASE_URL}/lawService.do"
        
        params = {
            "OC": self.api_key,
            "target": "law",
            "type": "JSON",
            "MST": law_serial_no
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("law"):
                law = data["law"][0]
                return {
                    "id": law.get("법령일련번호"),
                    "name": law.get("법령명한글"),
                    "content": law.get("조문내용"),
                    "articles": self._parse_articles(law.get("조문내용", ""))
                }
            
            return None
        
        except Exception as e:
            print(f"❌ 법령 본문 조회 실패: {e}")
            return None

    def search_precedents(
        self,
        query: str,
        display: int = 10,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        판례 검색
        
        Args:
            query: 검색어
            display: 페이지당 결과 수
            page: 페이지 번호
        
        Returns:
            판례 목록
        """
        endpoint = f"{self.BASE_URL}/lawSearch.do"
        
        params = {
            "OC": self.api_key,
            "target": "prec",
            "type": "JSON",
            "query": query,
            "display": display,
            "page": page
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("prec"):
                return [
                    {
                        "id": item.get("판례일련번호"),
                        "case_name": item.get("사건명"),
                        "case_number": item.get("사건번호"),
                        "court": item.get("법원명"),
                        "decision_date": item.get("선고일자"),
                        "case_type": item.get("사건종류명")
                    }
                    for item in data["prec"]
                ]
            return []
        
        except Exception as e:
            print(f"❌ 판례 검색 실패: {e}")
            return []

    def get_precedent_content(
        self,
        prec_serial_no: str
    ) -> Optional[Dict[str, Any]]:
        """
        판례 본문 조회
        
        Args:
            prec_serial_no: 판례일련번호
        
        Returns:
            판례 상세 정보
        """
        endpoint = f"{self.BASE_URL}/lawService.do"
        
        params = {
            "OC": self.api_key,
            "target": "prec",
            "type": "JSON",
            "ID": prec_serial_no
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("prec"):
                prec = data["prec"][0]
                return {
                    "id": prec.get("판례일련번호"),
                    "case_name": prec.get("사건명"),
                    "case_number": prec.get("사건번호"),
                    "court": prec.get("법원명"),
                    "decision_date": prec.get("선고일자"),
                    "summary": prec.get("판시사항"),
                    "reason": prec.get("판결요지"),
                    "full_text": prec.get("판례내용")
                }
            
            return None
        
        except Exception as e:
            print(f"❌ 판례 본문 조회 실패: {e}")
            return None

    def search_interpretations(
        self,
        query: str,
        display: int = 10
    ) -> List[Dict[str, Any]]:
        """
        법령해석례 검색
        
        Args:
            query: 검색어
            display: 결과 수
        
        Returns:
            법령해석례 목록
        """
        endpoint = f"{self.BASE_URL}/lawSearch.do"
        
        params = {
            "OC": self.api_key,
            "target": "expc",
            "type": "JSON",
            "query": query,
            "display": display
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("expc"):
                return [
                    {
                        "id": item.get("해석례일련번호"),
                        "title": item.get("해석례제목"),
                        "organ": item.get("해석기관"),
                        "date": item.get("해석일자")
                    }
                    for item in data["expc"]
                ]
            return []
        
        except Exception as e:
            print(f"❌ 법령해석례 검색 실패: {e}")
            return []

    def _parse_articles(self, content: str) -> List[Dict[str, str]]:
        """
        조문 내용 파싱
        
        Args:
            content: 조문 HTML 텍스트
        
        Returns:
            조문 리스트
        """
        # 간단한 파싱 (실제로는 더 정교하게 처리 필요)
        articles = []
        
        if not content:
            return articles
        
        # HTML 태그 제거 (기본적인 처리)
        import re
        clean_content = re.sub(r'<[^>]+>', '', content)
        
        # "제X조" 패턴으로 분리
        article_pattern = r'(제\d+조[^제]*)'
        matches = re.findall(article_pattern, clean_content)
        
        for match in matches:
            articles.append({
                "content": match.strip()
            })
        
        return articles


# 양형기준표 데이터 (간단 버전)
SENTENCING_GUIDELINES = {
    "살인": {
        "법조문": "형법 제250조",
        "법정형": "사형, 무기 또는 5년 이상의 징역",
        "기준": {
            "일반적 기준": {
                "감경": "3년 ~ 5년",
                "기본": "7년 ~ 11년",
                "가중": "11년 ~ 16년"
            },
            "가중요소": [
                "무고한 피해자",
                "계획적 범행",
                "잔혹한 방법",
                "다수 피해자"
            ],
            "감경요소": [
                "우발적 범행",
                "피해자의 부당한 행위 유발",
                "처벌불원",
                "진지한 반성"
            ]
        }
    },
    "절도": {
        "법조문": "형법 제329조",
        "법정형": "6년 이하의 징역 또는 1천만원 이하의 벌금",
        "기준": {
            "일반적 기준": {
                "감경": "벌금 ~ 8월",
                "기본": "6월 ~ 1년",
                "가중": "10월 ~ 2년"
            }
        }
    }
}


def get_sentencing_guideline(crime_type: str) -> Optional[Dict[str, Any]]:
    """
    양형기준표 조회
    
    Args:
        crime_type: 범죄 유형 (예: "살인", "절도")
    
    Returns:
        양형기준 정보
    """
    for key in SENTENCING_GUIDELINES:
        if key in crime_type or crime_type in key:
            return SENTENCING_GUIDELINES[key]
    
    return None
