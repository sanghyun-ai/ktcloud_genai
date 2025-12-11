import os
import re
import pandas as pd
import json
from sqlalchemy import create_engine
from typing import Dict, Any, List, Optional
from datasets import load_dataset

class ReasonPreprocessor:
    def __init__(self):
        # 부가 정보 시작 키워드
        self.extras_keywords = [
            r'신상정보\s*등록', r'신상정보\s*제출', r'신상정보\s*고지', r'신상정보\s*공개',
            r'고지명령', r'공개명령', r'취업제한', r'보호관찰', r'수강명령', r'이수명령',
            r'배상명령', r'몰수', r'추징', r'가납명령'
        ]
        self.extras_pattern = re.compile(r'(' + '|'.join(self.extras_keywords) + r').*', re.DOTALL)
        
        # 섹션 헤더 패턴 (1. 2. 3.)
        self.section_header_pattern = re.compile(r'(?:^|\n)(\d+)\.\s+([^\n]+)')
        
        # Bullet 패턴 (○)
        self.bullet_pattern = re.compile(r'(?:^|\n)\s*[○oㅇ]\s*([^\n]+)')

    def process(self, reason: str) -> Dict[str, Any]:
        """양형 이유 텍스트를 분석하여 구조화된 딕셔너리 반환"""
        if not reason or not isinstance(reason, str):
            return self._create_empty_result()

        # 1. 생략형 체크
        if '생략' in reason and len(reason) < 50:
            return {
                "reason_type": "omitted",
                "reason_main": "",
                "reason_sections": {},
                "reason_bullets": {},
                "reason_extras": "",
                "reason_flags": {"is_omitted": True}
            }

        # 2. 짧은 템플릿형 체크 (80자 이하)
        if len(reason) <= 80:
            return {
                "reason_type": "very_short",
                "reason_main": reason.strip(),
                "reason_sections": {},
                "reason_bullets": {},
                "reason_extras": "",
                "reason_flags": {"is_low_info": True}
            }

        # 3. Extras 분리
        main_text, extras_text = self._split_extras(reason)
        has_extras = bool(extras_text)
        
        # 4. 유형 판단 및 구조화
        # 4-1. 번호 구조형 or 번호+Bullet 혼합형
        sections = self._parse_numbered_sections(main_text)
        if sections:
            # 섹션 내부에 bullet이 있는지 확인
            has_bullets_in_section = any(self._has_bullets(content) for content in sections.values())
            
            if has_bullets_in_section:
                # 번호 + Bullet 혼합형
                structured_sections = {}
                for key, content in sections.items():
                    bullets = self._parse_bullets(content)
                    # Bullet이 없으면 일반 텍스트로 처리하되 구조는 맞춤
                    if not bullets['favorable'] and not bullets['unfavorable'] and not bullets['other']:
                        structured_sections[key] = {
                            "header": key,
                            "content": content,  # 원문 보존
                            "favorable": [],
                            "unfavorable": [],
                            "other": []
                        }
                    else:
                        structured_sections[key] = {
                            "header": key,
                            "favorable": bullets['favorable'],
                            "unfavorable": bullets['unfavorable'],
                            "other": bullets['other']
                        }
                
                return {
                    "reason_type": "num_plus_bullets",
                    "reason_main": main_text,
                    "reason_sections": structured_sections,
                    "reason_bullets": {},
                    "reason_extras": extras_text,
                    "reason_flags": {"has_extras": has_extras, "has_bullets": True}
                }
            else:
                # 번호 구조형
                mapped_sections = self._map_section_keys(sections)
                return {
                    "reason_type": "structured_sections",
                    "reason_main": main_text,
                    "reason_sections": mapped_sections,
                    "reason_bullets": {},
                    "reason_extras": extras_text,
                    "reason_flags": {"has_extras": has_extras, "has_guideline": "guideline" in mapped_sections}
                }

        # 4-2. 동그라미 Bullet형
        if self._has_bullets(main_text):
            bullets = self._parse_bullets(main_text)
            return {
                "reason_type": "bullets_only",
                "reason_main": main_text,
                "reason_sections": {},
                "reason_bullets": bullets,
                "reason_extras": extras_text,
                "reason_flags": {"has_extras": has_extras, "has_bullets": True}
            }

        # 4-3. 양형 이유 + 신상정보/고지명령 포함형 (단순 서술형 + Extras)
        if has_extras:
            return {
                "reason_type": "with_extras",
                "reason_main": main_text.strip(),
                "reason_sections": {},
                "reason_bullets": {},
                "reason_extras": extras_text,
                "reason_flags": {"has_extras": True}
            }

        # 4-4. 단순 서술형
        return {
            "reason_type": "simple_narrative",
            "reason_main": main_text.strip(),
            "reason_sections": {},
            "reason_bullets": {},
            "reason_extras": "",
            "reason_flags": {}
        }

    def _split_extras(self, text: str) -> (str, str):
        """텍스트에서 신상정보 등 부가정보 분리"""
        match = self.extras_pattern.search(text)
        if match:
            start_idx = match.start()
            # 분리 지점이 너무 앞이면(텍스트의 20% 미만 지점) 오탐지일 수 있으므로 체크
            if start_idx < len(text) * 0.1 and len(text) > 200:
                return text, ""
            return text[:start_idx], text[start_idx:]
        return text, ""

    def _parse_numbered_sections(self, text: str) -> Dict[str, str]:
        """번호가 매겨진 섹션 파싱 (1. xxx \n 내용)"""
        sections = {}
        matches = list(self.section_header_pattern.finditer(text))
        
        if not matches:
            return {}

        for i, match in enumerate(matches):
            header = match.group(2).strip()
            start_pos = match.end()
            end_pos = matches[i+1].start() if i + 1 < len(matches) else len(text)
            content = text[start_pos:end_pos].strip()
            sections[header] = content
            
        return sections

    def _map_section_keys(self, sections: Dict[str, str]) -> Dict[str, str]:
        """섹션 제목을 표준 키(law_range, guideline, decision)로 매핑"""
        mapped = {}
        for header, content in sections.items():
            key = header # 기본값
            if '법률상' in header and '범위' in header:
                key = 'law_range'
            elif '권고형' in header or '양형기준' in header:
                key = 'guideline'
            elif '선고형' in header or '결정' in header:
                key = 'decision'
            mapped[key] = content
        return mapped

    def _has_bullets(self, text: str) -> bool:
        """Bullet 포함 여부 확인"""
        return bool(self.bullet_pattern.search(text))

    def _parse_bullets(self, text: str) -> Dict[str, List[str]]:
        """Bullet 텍스트 파싱 및 카테고리 분류"""
        lines = text.split('\n')
        result = {
            "favorable": [],
            "unfavorable": [],
            "other": []
        }
        
        for line in lines:
            line = line.strip()
            match = re.match(r'^[○oㅇ]\s*(.*)', line)
            if match:
                content = match.group(1).strip()
                # 카테고리 분류
                if content.startswith('유리한') or '유리한 정상' in content:
                    # 콜론이나 내용 분리
                    clean_content = re.sub(r'^유리한\s*정상\s*[:;]\s*', '', content)
                    result['favorable'].extend([x.strip() for x in clean_content.split(',') if x.strip()])
                elif content.startswith('불리한') or '불리한 정상' in content:
                    clean_content = re.sub(r'^불리한\s*정상\s*[:;]\s*', '', content)
                    result['unfavorable'].extend([x.strip() for x in clean_content.split(',') if x.strip()])
                else:
                    # 그 외 내용은 통으로 넣거나 쉼표 분리
                    result['other'].append(content)
            elif line and not line.startswith(('1.', '2.', '3.')): # Bullet이 아닌 줄은 이전 카테고리에 붙이거나 other에 추가
                # 여기서는 간단히 무시하거나 other에 추가 (구현의 단순화를 위해 생략 가능)
                pass
                
        return result

    def _create_empty_result(self) -> Dict[str, Any]:
        return {
            "reason_type": "unknown",
            "reason_main": "",
            "reason_sections": {},
            "reason_bullets": {},
            "reason_extras": "",
            "reason_flags": {}
        }


def load_from_db_and_process():
    """DATABASE_URL에서 데이터를 로드하고 전처리 (예시 코드)"""
    database_url = os.environ.get("DATABASE_URL")
    
    if not database_url:
        print("⚠️ DATABASE_URL 환경변수가 설정되지 않았습니다. 로컬 데이터셋으로 테스트를 진행합니다.")
        return load_from_local_and_process()
        
    try:
        print(f"Connecting to database...")
        engine = create_engine(database_url)
        
        # 쿼리 예시 (실제 테이블명에 맞춰 수정 필요)
        query = "SELECT id, reason FROM ljp_criminal_table LIMIT 100" 
        df = pd.read_sql(query, engine)
        
        print(f"Loaded {len(df)} rows from database.")
        
        processor = ReasonPreprocessor()
        
        # 전처리 적용
        results = []
        for _, row in df.iterrows():
            processed = processor.process(row['reason'])
            processed['id'] = row['id'] # ID 보존
            results.append(processed)
            
        return pd.DataFrame(results)
        
    except Exception as e:
        print(f"❌ DB 연결/쿼리 오류: {e}")
        print("로컬 데이터셋으로 대체합니다.")
        return load_from_local_and_process()

def load_from_local_and_process():
    """로컬 데이터셋으로 테스트"""
    print("Loading local ljp_criminal dataset...")
    dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split='train')
    
    # 테스트용 샘플 선택 (다양한 유형이 포함되도록)
    # 실제로는 전체를 돌리겠지만 여기서는 일부만
    df = pd.DataFrame(dataset.select(range(50)))
    
    processor = ReasonPreprocessor()
    
    results = []
    print("Processing reasons...")
    for idx, row in df.iterrows():
        processed = processor.process(row['reason'])
        processed['original_id'] = row['id']
        processed['original_reason_preview'] = row['reason'][:50] + "..."
        results.append(processed)
        
    return pd.DataFrame(results)

if __name__ == "__main__":
    # 데이터 처리 실행
    result_df = load_from_db_and_process()
    
    # 결과 출력 (유형별 통계)
    if not result_df.empty:
        print("\n=== 처리 결과 통계 ===")
        print(result_df['reason_type'].value_counts())
        
        print("\n=== 유형별 샘플 출력 ===")
        for r_type in result_df['reason_type'].unique():
            print(f"\n[Type: {r_type}]")
            sample = result_df[result_df['reason_type'] == r_type].iloc[0]
            print(json.dumps(sample.to_dict(), ensure_ascii=False, indent=2))
            
    # 결과를 JSON 파일로 저장 (선택 사항)
    # result_df.to_json("processed_reasons.json", orient="records", force_ascii=False)
