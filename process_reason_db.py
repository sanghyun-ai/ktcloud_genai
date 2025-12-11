import os
import re
import pandas as pd
import json
from sqlalchemy import create_engine
from typing import Dict, Any, List, Optional, Tuple, Union
from datasets import load_dataset

class ReasonPreprocessor:
    """양형 이유 텍스트를 7가지 유형으로 분류하고 구조화하는 전처리기"""

    def __init__(self):
        # 정규식 패턴 컴파일
        self._compile_patterns()

    def _compile_patterns(self):
        """정규식 패턴 정의"""
        # 부가 정보 키워드 (신상정보, 고지명령 등)
        extras_keywords = [
            r'신상정보\s*등록', r'신상정보\s*제출', r'신상정보\s*고지', r'신상정보\s*공개',
            r'고지명령', r'공개명령', r'취업제한', r'보호관찰', r'수강명령', r'이수명령',
            r'배상명령', r'몰수', r'추징', r'가납명령'
        ]
        self.extras_pattern = re.compile(r'(' + '|'.join(extras_keywords) + r').*', re.DOTALL)
        self.section_header_pattern = re.compile(r'(?:^|\n)(\d+)\.\s+([^\n]+)')
        self.bullet_pattern = re.compile(r'(?:^|\n)\s*[○oㅇ]\s*([^\n]+)')
        self.favorable_pattern = re.compile(r'^유리한\s*정상\s*[:;]?\s*(.*)')
        self.unfavorable_pattern = re.compile(r'^불리한\s*정상\s*[:;]?\s*(.*)')

    def process(self, reason: str) -> Dict[str, Any]:
        """메인 처리 함수: 규칙 우선순위에 따라 텍스트를 분석하여 반환"""
        if not reason or not isinstance(reason, str):
            return self._create_empty_result()

        # 1. 생략형 체크
        if result := self._process_omitted(reason):
            return result

        # 2. 짧은 템플릿형 체크
        if result := self._process_very_short(reason):
            return result

        # 공통: 본문과 부가 정보(Extras) 분리
        main_text, extras_text = self._split_extras(reason)
        
        # 3 & 4. 번호 구조형 (번호+Bullet 혼합형 포함)
        if result := self._process_structured(main_text, extras_text):
            return result
            
        # 5. 동그라미 Bullet형
        if result := self._process_bullets_only(main_text, extras_text):
            return result
            
        # 6 & 7. 서술형 (단순 서술형 또는 Extras 포함형)
        return self._process_narrative(main_text, extras_text)

    # =========================================================================
    # 각 유형별 처리 함수 (Type Processors)
    # =========================================================================

    def _process_omitted(self, text: str) -> Optional[Dict[str, Any]]:
        """1. 생략형 처리"""
        if '생략' in text and len(text) < 50:
            return self._build_result(
                type_name="omitted",
                flags={"is_omitted": True}
            )
        return None

    def _process_very_short(self, text: str) -> Optional[Dict[str, Any]]:
        """7. 짧은 템플릿형 처리"""
        if len(text) <= 80:
            return self._build_result(
                type_name="very_short",
                main=text.strip(),
                flags={"is_low_info": True}
            )
        return None

    def _process_structured(self, main_text: str, extras_text: str) -> Optional[Dict[str, Any]]:
        """2. 번호 구조형 및 4. 번호+Bullet 혼합형 처리"""
        sections = self._parse_numbered_sections(main_text)
        if not sections:
            return None

        # 섹션 내부에 bullet이 있는지 확인
        has_bullets = any(self._has_bullets(content) for content in sections.values())
        
        if has_bullets:
            # 4. 번호 + Bullet 혼합형
            structured_sections = {}
            for key, content in sections.items():
                bullets = self._parse_bullets(content)
                # Bullet이 있으면 구조화, 없으면 원문 보존
                structured_sections[key] = {
                    "header": key,
                    "content": content if not self._is_bullet_content(bullets) else "",
                    "favorable": bullets['favorable'],
                    "unfavorable": bullets['unfavorable'],
                    "other": bullets['other']
                }
            
            return self._build_result(
                type_name="num_plus_bullets",
                main=main_text,
                sections=structured_sections,
                extras=extras_text,
                flags={"has_extras": bool(extras_text), "has_bullets": True}
            )
        else:
            # 2. 번호 구조형 (순수)
            mapped_sections = self._map_section_keys(sections)
            return self._build_result(
                type_name="structured_sections",
                main=main_text,
                sections=mapped_sections,
                extras=extras_text,
                flags={"has_extras": bool(extras_text), "has_guideline": "guideline" in mapped_sections}
            )

    def _process_bullets_only(self, main_text: str, extras_text: str) -> Optional[Dict[str, Any]]:
        """3. 동그라미 Bullet형 처리"""
        if self._has_bullets(main_text):
            bullets = self._parse_bullets(main_text)
            return self._build_result(
                type_name="bullets_only",
                main=main_text,
                bullets=bullets,
                extras=extras_text,
                flags={"has_extras": bool(extras_text), "has_bullets": True}
            )
        return None

    def _process_narrative(self, main_text: str, extras_text: str) -> Dict[str, Any]:
        """5. 단순 서술형 및 6. Extras 포함형 처리"""
        if extras_text:
            # 6. 양형 이유 + 신상정보/고지명령 포함형
            return self._build_result(
                type_name="with_extras",
                main=main_text.strip(),
                extras=extras_text,
                flags={"has_extras": True}
            )
        else:
            # 5. 단순 서술형
            return self._build_result(
                type_name="simple_narrative",
                main=main_text.strip()
            )

    # =========================================================================
    # 파싱 헬퍼 함수 (Parsing Helpers)
    # =========================================================================

    def _split_extras(self, text: str) -> Tuple[str, str]:
        """텍스트에서 부가 정보(신상정보 등) 분리"""
        match = self.extras_pattern.search(text)
        if match:
            start_idx = match.start()
            # 오탐지 방지: 텍스트 앞부분(10%)에 나오면 무시, 전체 길이가 충분히 길 때만 적용
            if start_idx < len(text) * 0.1 and len(text) > 200:
                return text, ""
            return text[:start_idx], text[start_idx:]
        return text, ""

    def _parse_numbered_sections(self, text: str) -> Dict[str, str]:
        """번호가 매겨진 섹션 파싱 (1. 제목 ... 내용)"""
        sections = {}
        matches = list(self.section_header_pattern.finditer(text))
        
        if not matches:
            return {}

        for i, match in enumerate(matches):
            header = match.group(2).strip()
            start_pos = match.end()
            end_pos = matches[i+1].start() if i + 1 < len(matches) else len(text)
            sections[header] = text[start_pos:end_pos].strip()
            
        return sections

    def _parse_bullets(self, text: str) -> Dict[str, List[str]]:
        """Bullet 텍스트 파싱 및 유리/불리 분류"""
        lines = text.split('\n')
        result = {"favorable": [], "unfavorable": [], "other": []}
        
        for line in lines:
            line = line.strip()
            if match := self.bullet_pattern.match(line):
                content = match.group(1).strip()
                self._categorize_bullet_content(content, result)
        return result

    def _categorize_bullet_content(self, content: str, result: Dict[str, List[str]]):
        """Bullet 내용의 카테고리 분류 (유리/불리/기타)"""
        if match := self.favorable_pattern.match(content):
            items = [x.strip() for x in match.group(1).split(',') if x.strip()]
            result['favorable'].extend(items)
        elif match := self.unfavorable_pattern.match(content):
            items = [x.strip() for x in match.group(1).split(',') if x.strip()]
            result['unfavorable'].extend(items)
        else:
            result['other'].append(content)

    def _map_section_keys(self, sections: Dict[str, str]) -> Dict[str, str]:
        """섹션 제목 표준화 (law_range, guideline, decision)"""
        mapped = {}
        for header, content in sections.items():
            key = header # 기본값
            if '법률상' in header and '범위' in header: key = 'law_range'
            elif '권고형' in header or '양형기준' in header: key = 'guideline'
            elif '선고형' in header or '결정' in header: key = 'decision'
            mapped[key] = content
        return mapped

    def _has_bullets(self, text: str) -> bool:
        return bool(self.bullet_pattern.search(text))
    
    def _is_bullet_content(self, bullets: Dict[str, List]) -> bool:
        return any(bullets.values())

    def _build_result(self, type_name: str, main: str = "", sections: Dict = None, 
                      bullets: Dict = None, extras: str = "", flags: Dict = None) -> Dict[str, Any]:
        """결과 딕셔너리 생성 헬퍼"""
        return {
            "reason_type": type_name,
            "reason_main": main,
            "reason_sections": sections or {},
            "reason_bullets": bullets or {},
            "reason_extras": extras,
            "reason_flags": flags or {}
        }

    def _create_empty_result(self) -> Dict[str, Any]:
        return self._build_result("unknown")


# =============================================================================
# 데이터 로드 및 실행 함수
# =============================================================================

def load_data_and_process(db_url: Optional[str] = None):
    """DB 또는 로컬에서 데이터를 로드하여 처리"""
    processor = ReasonPreprocessor()
    
    # 1. DB 연결 시도
    if db_url:
        try:
            print("Connecting to database...")
            engine = create_engine(db_url)
            query = "SELECT id, reason FROM ljp_criminal_table" # 테이블명 수정 필요
            df = pd.read_sql(query, engine)
            print(f"Loaded {len(df)} rows from DB.")
        except Exception as e:
            print(f"❌ DB Error: {e}")
            df = None
    else:
        df = None

    # 2. 실패 시 로컬 데이터셋 사용
    if df is None:
        print("Using local dataset...")
        dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split='train')
        df = pd.DataFrame(dataset)

    # 3. 전처리 실행
    print(f"Processing {len(df)} rows...")
    results = []
    for _, row in df.iterrows():
        processed = processor.process(row['reason'])
        processed['id'] = row['id']
        results.append(processed)

    return pd.DataFrame(results)

if __name__ == "__main__":
    # 환경 변수에서 DB URL 확인
    database_url = os.environ.get("DATABASE_URL")
    
    # 처리 실행
    result_df = load_data_and_process(database_url)
    
    # 결과 출력
    if not result_df.empty:
        print("\n=== 처리 결과 통계 ===")
        print(result_df['reason_type'].value_counts())
        
        print("\n=== 각 유형별 전처리 샘플 ===")
        unique_types = result_df['reason_type'].unique()
        
        for r_type in unique_types:
            print(f"\n[{r_type}] --------------------------------------------------")
            sample = result_df[result_df['reason_type'] == r_type].iloc[0]
            print(json.dumps(sample.to_dict(), ensure_ascii=False, indent=2))
