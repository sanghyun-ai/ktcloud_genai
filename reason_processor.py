"""
LJP Criminal Dataset - Reason 컬럼 전처리 및 구조화 (DB 통합 버전)

.env의 DATABASE_URL에서 데이터를 불러와 전처리 + 구조화를 수행하고 JSON으로 저장

필수 패키지:
    pip install python-dotenv sqlalchemy psycopg2-binary

사용법:
    python reason_processor.py
"""

import os
import re
import json
from typing import Dict, List, Optional, Any
from enum import Enum
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tqdm import tqdm

# .env 파일 로드
load_dotenv()


# ============================================================================
# 전처리 함수
# ============================================================================

def preprocess_reason(text: str) -> str:
    """
    reason 컬럼 전처리 함수
    
    원본 텍스트를 최대한 유지하면서 다음만 수행:
    1. 줄 끝 공백 제거
    2. 리스트 마커 뒤 공백 정규화 (단일 공백)
    3. 숫자 섹션 헤더 뒤 공백 정규화 (단일 공백)
    4. 연속된 빈 줄 정리 (최대 2개)
    5. 전체 문서 앞뒤 공백 제거
    
    Args:
        text: 원본 reason 텍스트
        
    Returns:
        전처리된 reason 텍스트
    """
    if not text or not isinstance(text, str):
        return text
    
    # 1. 줄 단위로 분리
    lines = text.split('\n')
    
    # 2. 각 줄 처리
    processed_lines = []
    for line in lines:
        # 줄 끝 공백 제거
        line = line.rstrip()
        
        # 리스트 마커로 시작하는 경우
        if re.match(r'^\s*[○●•\-\*]\s+', line):
            line = line.lstrip()
            line = re.sub(r'^([○●•\-\*])\s+', r'\1 ', line)
        
        # 숫자 섹션 헤더인 경우
        elif re.match(r'^\s*\d+\.\s+', line):
            line = line.lstrip()
            line = re.sub(r'^(\d+\.)\s+', r'\1 ', line)
        
        # 일반 헤더로 보이는 경우
        elif line.strip() and len(line.strip()) < 50:
            if re.search(r'(이유|의무|명령|면제)$', line.strip()):
                line = line.strip()
        
        processed_lines.append(line)
    
    # 3. 다시 합치기
    result = '\n'.join(processed_lines)
    
    # 4. 연속된 빈 줄 정리
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    # 5. 전체 앞뒤 공백 제거
    result = result.strip()
    
    return result


# ============================================================================
# 구조화 - 패턴 타입 정의
# ============================================================================

class ReasonPatternType(Enum):
    """Reason 패턴 타입"""
    BASIC_NARRATIVE = "기본 서술형"
    STRUCTURED_GUIDELINE = "구조화된 양형기준형"
    OMITTED = "약식 생략형"
    WITH_PERSONAL_INFO = "신상정보 포함형"
    HYBRID = "혼합형"


def detect_pattern_type(text: str) -> ReasonPatternType:
    """패턴 타입 감지"""
    if re.search(r'양형의\s*이유', text) and re.search(r'^\s*생략\s*$', text, re.MULTILINE):
        return ReasonPatternType.OMITTED
    
    has_statutory = bool(re.search(r'법률상\s+처단형의\s+범위', text))
    has_guideline = bool(re.search(r'양형기준에\s+따른\s+권고형의\s+범위', text))
    has_decision = bool(re.search(r'선고형의\s+결정', text))
    
    if has_statutory and has_guideline and has_decision:
        return ReasonPatternType.STRUCTURED_GUIDELINE
    
    has_personal_info = bool(re.search(r'신상정보\s+(?:등록|제출의무)', text))
    has_disclosure = bool(re.search(r'(?:공개|고지)명령', text))
    has_numbering = bool(re.search(r'^\s*\d+\.\s+', text, re.MULTILINE))
    
    if has_numbering and not (has_statutory and has_guideline):
        if has_personal_info or has_disclosure:
            return ReasonPatternType.WITH_PERSONAL_INFO
        return ReasonPatternType.HYBRID
    
    if has_personal_info or has_disclosure:
        return ReasonPatternType.WITH_PERSONAL_INFO
    
    return ReasonPatternType.BASIC_NARRATIVE


# ============================================================================
# 구조화 - 양형 요소 추출 함수들
# ============================================================================

def extract_factors(text: str, factor_type: str) -> List[str]:
    """불리한 정상 또는 유리한 정상 항목 추출"""
    factors = []
    
    pattern = rf'○\s+{factor_type}\s+정상'
    match = re.search(pattern, text)
    
    if match:
        start_pos = match.end()
        next_section = re.search(r'(?:○\s+(?:불리한|유리한)\s+정상|신상정보|공개명령|그\s+밖에)', text[start_pos:])
        
        if next_section:
            section_text = text[start_pos:start_pos + next_section.start()]
        else:
            section_text = text[start_pos:start_pos + 800]
            last_period = section_text.rfind('.')
            if last_period > 0:
                section_text = section_text[:last_period + 1]
        
        items = re.findall(r'-\s+([^\n]+(?:\n(?![-○])[^\n]+)*)', section_text)
        factors = [item.strip() for item in items if item.strip()]
        
        if not factors and section_text.strip():
            factors = [section_text.strip()]
    
    if not factors:
        pattern = rf'[^\.]*{factor_type}\s+정상[^\.]*\.'
        matches = re.findall(pattern, text)
        if matches:
            for match in matches:
                if ',' in match:
                    parts = match.split(',')
                    for part in parts[:-1]:
                        clean_part = part.strip()
                        if clean_part and len(clean_part) > 5:
                            factors.append(clean_part)
                else:
                    clean = match.strip()
                    if clean and len(clean) > 5:
                        factors.append(clean)
    
    return factors


def extract_statutory_range(text: str) -> Optional[str]:
    """법률상 처단형의 범위 추출"""
    pattern = r'법률상\s+처단형의\s+범위\s*[:：]?\s*([^\n]+)'
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return None


def extract_sentencing_guidelines(text: str) -> Dict[str, Any]:
    """양형기준 정보 추출"""
    guidelines = {
        "crime_type": None,
        "sentencing_type": None,
        "special_factors": {
            "aggravating": [],
            "mitigating": []
        },
        "recommended_range": None
    }
    
    type_match = re.search(r'\[유형의\s+결정\]\s+([^\[]+)', text)
    if type_match:
        type_text = type_match.group(1).strip()
        guidelines["crime_type"] = type_text
        
        if '>' in type_text:
            parts = [p.strip() for p in type_text.split('>')]
            if len(parts) >= 2:
                guidelines["sentencing_type"] = parts[-1]
    
    factor_match = re.search(r'\[특별양형인자\]\s+([^\[]+)', text)
    if factor_match:
        factor_text = factor_match.group(1).strip()
        
        if '가중요소' in factor_text:
            agg_match = re.search(r'가중요소\s*[:：]?\s*([^감경]+)', factor_text)
            if agg_match:
                agg_text = agg_match.group(1).strip()
                guidelines["special_factors"]["aggravating"] = [
                    item.strip() for item in re.split(r'[,，]', agg_text) if item.strip()
                ]
        
        if '감경요소' in factor_text:
            mit_match = re.search(r'감경요소\s*[:：]?\s*(.+?)(?=(?:가중요소|$))', factor_text, re.DOTALL)
            if mit_match:
                mit_text = mit_match.group(1).strip()
                guidelines["special_factors"]["mitigating"] = [
                    item.strip() for item in re.split(r'[,，]', mit_text) if item.strip()
                ]
    
    range_match = re.search(r'\[권고영역\s+및\s+권고형의\s+범위\]\s+([^\n\[]+)', text)
    if range_match:
        range_text = range_match.group(1).strip()
        decision_pos = range_text.find('3.')
        if decision_pos > 0:
            range_text = range_text[:decision_pos].strip()
        guidelines["recommended_range"] = range_text
    
    return guidelines


def extract_final_decision(text: str) -> Optional[str]:
    """선고형의 결정 내용 추출"""
    pattern = r'선고형의\s+결정\s*[:：]?\s*\n?(.+?)(?=(?:\n\n|신상정보|공개|고지|$))'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        decision_text = match.group(1).strip()
        if len(decision_text) > 500:
            decision_text = decision_text[:500] + '...'
        return decision_text
    return None


def extract_personal_information(text: str) -> Dict[str, Any]:
    """신상정보 관련 내용 추출"""
    personal_info = {
        "registration_required": False,
        "registration_description": None,
        "disclosure_exempted": False,
        "disclosure_exemption_reason": None,
        "notification_exempted": False,
        "employment_restriction": False,
        "employment_restriction_exempted": False
    }
    
    if re.search(r'신상정보\s*(?:의\s*)?(?:등록|제출)', text):
        personal_info["registration_required"] = True
        
        reg_section_match = re.search(
            r'(신상정보[^\n]*(?:등록|제출)[^\n]*)\n(.+?)(?=\n(?:공개|고지|취업|$))',
            text,
            re.DOTALL
        )
        if reg_section_match:
            desc = reg_section_match.group(2).strip()
            if len(desc) > 400:
                sentences = re.split(r'\.\s+', desc)
                if len(sentences) > 2:
                    desc = '. '.join(sentences[:2]) + '.'
                else:
                    desc = desc[:400] + '...'
            personal_info["registration_description"] = desc
    
    disclosure_pattern = r'공개(?:명령)?[^\.]*면제'
    if re.search(disclosure_pattern, text):
        personal_info["disclosure_exempted"] = True
        
        exemption_section = re.search(
            r'공개[^\n]*면제[^\n]*\n(.+?)(?=\n\n|\Z)',
            text,
            re.DOTALL
        )
        if exemption_section:
            reason = exemption_section.group(1).strip()
            paren_match = re.search(r'\(([^)]{20,})\)', reason, re.DOTALL)
            if paren_match:
                reason = paren_match.group(1).strip()
                if len(reason) > 200:
                    reason = reason[:200] + '...'
            else:
                if len(reason) > 200:
                    reason = reason[:200] + '...'
            personal_info["disclosure_exemption_reason"] = reason
    
    if re.search(r'고지(?:명령)?[^\.]*면제', text):
        personal_info["notification_exempted"] = True
    
    if re.search(r'취업제한', text):
        if re.search(r'취업제한[^\.]*면제', text):
            personal_info["employment_restriction_exempted"] = True
        else:
            personal_info["employment_restriction"] = True
    
    return personal_info


def extract_general_considerations(text: str) -> Optional[str]:
    """종합 고려사항 추출"""
    patterns = [
        r'그\s+밖에[^\.]+양형조건[^\.]+\.',
        r'위와\s+같은\s+사정[^\.]+\.',
        r'이러한\s+정상들과[^\.]+\.',
        r'형법\s+제51조[^\.]+\.'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(0).strip()
    
    return None


# ============================================================================
# 메인 구조화 함수
# ============================================================================

def structure_reason(text: str, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Reason 텍스트를 구조화된 JSON으로 변환
    
    Args:
        text: reason 텍스트
        case_id: 케이스 ID
        
    Returns:
        구조화된 딕셔너리
    """
    pattern_type = detect_pattern_type(text)
    
    structured = {
        "case_id": case_id,
        "pattern_type": pattern_type.value,
        "sentencing_reason": {},
        "personal_information": {}
    }
    
    if pattern_type == ReasonPatternType.OMITTED:
        structured["sentencing_reason"] = {"omitted": True}
        return structured
    
    sentencing = {}
    
    if pattern_type in [ReasonPatternType.STRUCTURED_GUIDELINE, ReasonPatternType.HYBRID]:
        statutory_range = extract_statutory_range(text)
        if statutory_range:
            sentencing["statutory_punishment_range"] = statutory_range
    
    if pattern_type == ReasonPatternType.STRUCTURED_GUIDELINE:
        guidelines = extract_sentencing_guidelines(text)
        if any(guidelines.values()):
            sentencing["sentencing_guidelines"] = guidelines
        
        final_decision = extract_final_decision(text)
        if final_decision:
            sentencing["final_decision"] = final_decision
    
    unfavorable = extract_factors(text, '불리한')
    if unfavorable:
        sentencing["unfavorable_factors"] = unfavorable
    
    favorable = extract_factors(text, '유리한')
    if favorable:
        sentencing["favorable_factors"] = favorable
    
    general = extract_general_considerations(text)
    if general:
        sentencing["general_considerations"] = general
    
    structured["sentencing_reason"] = sentencing
    
    if pattern_type in [ReasonPatternType.WITH_PERSONAL_INFO, ReasonPatternType.STRUCTURED_GUIDELINE]:
        personal_info = extract_personal_information(text)
        if any(personal_info.values()):
            structured["personal_information"] = personal_info
    
    return structured


# ============================================================================
# 데이터베이스 처리
# ============================================================================

def load_data_from_db():
    """
    DATABASE_URL에서 데이터를 로드
    
    Returns:
        데이터 리스트
    """
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL이 .env 파일에 설정되지 않았습니다.")
    
    print(f"데이터베이스 연결 중... ({database_url.split('@')[0]}@...)")
    
    engine = create_engine(database_url)
    
    # 테이블명과 컬럼명은 실제 DB 구조에 맞게 수정 필요
    query = """
    SELECT 
        id,
        casetype,
        casename,
        facts,
        label,
        ruling,
        reason
    FROM ljp_criminal
    WHERE reason IS NOT NULL 
      AND reason != ''
      AND TRIM(reason) != ''
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query))
        data = [dict(row._mapping) for row in result]
    
    return data


def process_and_save(output_file: str = "ljp_criminal_processed.json"):
    """
    데이터베이스에서 데이터를 불러와 전처리 + 구조화하고 JSON으로 저장
    
    Args:
        output_file: 출력 파일명
    """
    print("="*80)
    print("LJP Criminal Dataset - Reason 전처리 및 구조화")
    print("="*80)
    
    # 1. 데이터베이스에서 로드
    print("\n1. 데이터베이스에서 데이터 로딩 중...")
    try:
        data = load_data_from_db()
        print(f"   ✓ reason 값이 있는 {len(data)}개 행 로드 완료")
    except Exception as e:
        print(f"   ✗ 에러: {e}")
        return
    
    # 2. 전처리 + 구조화
    print("\n2. 전처리 및 구조화 진행 중...")
    processed_data = []
    
    for row in tqdm(data, desc="   처리 중"):
        # 전처리
        original_reason = row['reason']
        preprocessed_reason = preprocess_reason(original_reason)
        
        # 구조화
        structured = structure_reason(preprocessed_reason, case_id=row.get('id'))
        
        # 결과 저장
        result = {
            'id': row.get('id'),
            'casetype': row.get('casetype'),
            'casename': row.get('casename'),
            'label': row.get('label'),
            'reason_original': original_reason,
            'reason_preprocessed': preprocessed_reason,
            'reason_structured': {
                'case_id': structured['case_id'],
                'pattern_type': structured['pattern_type'],
                'sentencing_reason': structured['sentencing_reason'],
                'personal_information': structured['personal_information']
            }
        }
        
        processed_data.append(result)
    
    print(f"   ✓ {len(processed_data)}개 행 처리 완료")
    
    # 3. 통계
    print("\n3. 처리 통계...")
    from collections import Counter
    pattern_counts = Counter(item['reason_structured']['pattern_type'] for item in processed_data)
    
    print("   패턴 타입 분포:")
    for pattern, count in pattern_counts.most_common():
        percentage = (count / len(processed_data)) * 100
        print(f"     - {pattern}: {count}개 ({percentage:.1f}%)")
    
    with_unfavorable = sum(
        1 for item in processed_data 
        if item['reason_structured']['sentencing_reason'].get('unfavorable_factors')
    )
    with_favorable = sum(
        1 for item in processed_data 
        if item['reason_structured']['sentencing_reason'].get('favorable_factors')
    )
    
    print(f"\n   추출 통계:")
    print(f"     - 불리한 정상: {with_unfavorable}개 ({with_unfavorable/len(processed_data)*100:.1f}%)")
    print(f"     - 유리한 정상: {with_favorable}개 ({with_favorable/len(processed_data)*100:.1f}%)")
    
    # 4. JSON 저장
    print(f"\n4. JSON 파일로 저장 중... ({output_file})")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)
    
    print(f"   ✓ 저장 완료: {output_file}")
    
    # 5. 샘플 출력
    print("\n5. 샘플 데이터 (첫 2개):")
    print("="*80)
    
    for i in range(min(2, len(processed_data))):
        item = processed_data[i]
        print(f"\n케이스 ID: {item['id']}")
        print(f"패턴: {item['reason_structured']['pattern_type']}")
        unfav = item['reason_structured']['sentencing_reason'].get('unfavorable_factors', [])
        fav = item['reason_structured']['sentencing_reason'].get('favorable_factors', [])
        print(f"불리한 정상: {len(unfav) if unfav else 0}개")
        print(f"유리한 정상: {len(fav) if fav else 0}개")
        
        if i == 0:
            print("-"*80)
    
    print("\n" + "="*80)
    print("✅ 모든 작업 완료!")
    print(f"✅ 결과 파일: {output_file}")
    print("="*80)


# ============================================================================
# 메인 실행
# ============================================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='LJP Criminal Dataset - Reason 전처리 및 구조화')
    parser.add_argument(
        '--output',
        type=str,
        default='ljp_criminal_processed.json',
        help='출력 JSON 파일명'
    )
    
    args = parser.parse_args()
    
    process_and_save(output_file=args.output)
