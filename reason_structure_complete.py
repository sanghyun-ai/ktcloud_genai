"""
LJP Criminal Dataset - Reason 컬럼 구조화 (통합 버전)

이 파일은 구조화 함수와 일괄 처리 스크립트를 모두 포함합니다.

사용법:
    # 모듈로 import
    from reason_structure_complete import structure_reason, structure_dataset
    
    # 스크립트로 실행
    python reason_structure_complete.py
"""

import re
import json
from typing import Dict, List, Optional, Any
from enum import Enum
from datasets import load_dataset
from tqdm import tqdm
from collections import Counter


# ============================================================================
# 패턴 타입 정의
# ============================================================================

class ReasonPatternType(Enum):
    """Reason 패턴 타입"""
    BASIC_NARRATIVE = "기본 서술형"
    STRUCTURED_GUIDELINE = "구조화된 양형기준형"
    OMITTED = "약식 생략형"
    WITH_PERSONAL_INFO = "신상정보 포함형"
    HYBRID = "혼합형"


# ============================================================================
# 패턴 감지 함수
# ============================================================================

def detect_pattern_type(text: str) -> ReasonPatternType:
    """
    Reason 텍스트의 패턴 타입을 감지
    
    Args:
        text: reason 텍스트
        
    Returns:
        ReasonPatternType
    """
    # Pattern Type 3: 약식 생략형
    if re.search(r'양형의\s*이유', text) and re.search(r'^\s*생략\s*$', text, re.MULTILINE):
        return ReasonPatternType.OMITTED
    
    # Pattern Type 2: 구조화된 양형기준형
    has_statutory = bool(re.search(r'법률상\s+처단형의\s+범위', text))
    has_guideline = bool(re.search(r'양형기준에\s+따른\s+권고형의\s+범위', text))
    has_decision = bool(re.search(r'선고형의\s+결정', text))
    
    if has_statutory and has_guideline and has_decision:
        return ReasonPatternType.STRUCTURED_GUIDELINE
    
    # Pattern Type 4: 신상정보 포함형
    has_personal_info = bool(re.search(r'신상정보\s+(?:등록|제출의무)', text))
    has_disclosure = bool(re.search(r'(?:공개|고지)명령', text))
    
    # Pattern Type 5: 혼합형
    has_numbering = bool(re.search(r'^\s*\d+\.\s+', text, re.MULTILINE))
    
    if has_numbering and not (has_statutory and has_guideline):
        if has_personal_info or has_disclosure:
            return ReasonPatternType.WITH_PERSONAL_INFO
        return ReasonPatternType.HYBRID
    
    # Pattern Type 1 or 4: 기본 서술형 / 신상정보 포함형
    if has_personal_info or has_disclosure:
        return ReasonPatternType.WITH_PERSONAL_INFO
    
    return ReasonPatternType.BASIC_NARRATIVE


# ============================================================================
# 양형 요소 추출 함수들
# ============================================================================

def extract_factors(text: str, factor_type: str) -> List[str]:
    """
    불리한 정상 또는 유리한 정상 항목 추출
    
    Args:
        text: reason 텍스트
        factor_type: '불리한' 또는 '유리한'
        
    Returns:
        추출된 요소 리스트
    """
    factors = []
    
    # ○ 불리한/유리한 정상 패턴 찾기
    pattern = rf'○\s+{factor_type}\s+정상'
    match = re.search(pattern, text)
    
    if match:
        start_pos = match.end()
        # 다음 ○ 또는 주요 섹션까지 추출
        next_section = re.search(r'(?:○\s+(?:불리한|유리한)\s+정상|신상정보|공개명령|그\s+밖에)', text[start_pos:])
        
        if next_section:
            section_text = text[start_pos:start_pos + next_section.start()]
        else:
            # 적당한 길이까지만 (500자 정도)
            section_text = text[start_pos:start_pos + 800]
            # 마지막 문장 끝까지
            last_period = section_text.rfind('.')
            if last_period > 0:
                section_text = section_text[:last_period + 1]
        
        # - 로 시작하는 항목들 추출
        items = re.findall(r'-\s+([^\n]+(?:\n(?![-○])[^\n]+)*)', section_text)
        factors = [item.strip() for item in items if item.strip()]
        
        # - 가 없는 경우 전체 텍스트를 하나의 항목으로
        if not factors and section_text.strip():
            factors = [section_text.strip()]
    
    # ○가 없고 직접 서술된 경우 (예: "...점은 불리한 정상이다")
    if not factors:
        # "불리한 정상" 또는 "유리한 정상" 키워드를 포함하는 문장 찾기
        pattern = rf'[^\.]*{factor_type}\s+정상[^\.]*\.'
        matches = re.findall(pattern, text)
        if matches:
            # 쉼표로 구분된 항목들 추출
            for match in matches:
                # "~점, ~점은 불리한 정상이다" 형태 파싱
                if ',' in match:
                    parts = match.split(',')
                    for part in parts[:-1]:  # 마지막 부분은 "~은 불리한 정상이다" 형태이므로 제외
                        clean_part = part.strip()
                        if clean_part and len(clean_part) > 5:
                            factors.append(clean_part)
                else:
                    # 쉼표가 없으면 전체를 하나로
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
    
    # [유형의 결정] 추출
    type_match = re.search(r'\[유형의\s+결정\]\s+([^\[]+)', text)
    if type_match:
        type_text = type_match.group(1).strip()
        guidelines["crime_type"] = type_text
        
        # 유형 파싱 (예: "성범죄 > 01. 일반적 기준 > 나. 강제추행죄")
        if '>' in type_text:
            parts = [p.strip() for p in type_text.split('>')]
            if len(parts) >= 2:
                guidelines["sentencing_type"] = parts[-1]
    
    # [특별양형인자] 추출
    factor_match = re.search(r'\[특별양형인자\]\s+([^\[]+)', text)
    if factor_match:
        factor_text = factor_match.group(1).strip()
        
        # 가중요소 추출
        if '가중요소' in factor_text:
            agg_match = re.search(r'가중요소\s*[:：]?\s*([^감경]+)', factor_text)
            if agg_match:
                agg_text = agg_match.group(1).strip()
                guidelines["special_factors"]["aggravating"] = [
                    item.strip() for item in re.split(r'[,，]', agg_text) if item.strip()
                ]
        
        # 감경요소 추출
        if '감경요소' in factor_text:
            mit_match = re.search(r'감경요소\s*[:：]?\s*(.+?)(?=(?:가중요소|$))', factor_text, re.DOTALL)
            if mit_match:
                mit_text = mit_match.group(1).strip()
                guidelines["special_factors"]["mitigating"] = [
                    item.strip() for item in re.split(r'[,，]', mit_text) if item.strip()
                ]
    
    # [권고영역 및 권고형의 범위] 추출
    range_match = re.search(r'\[권고영역\s+및\s+권고형의\s+범위\]\s+([^\n\[]+)', text)
    if range_match:
        range_text = range_match.group(1).strip()
        # "3. 선고형의 결정" 앞까지만
        decision_pos = range_text.find('3.')
        if decision_pos > 0:
            range_text = range_text[:decision_pos].strip()
        guidelines["recommended_range"] = range_text
    
    return guidelines


def extract_final_decision(text: str) -> Optional[str]:
    """선고형의 결정 내용 추출"""
    # "선고형의 결정" 섹션 찾기
    pattern = r'선고형의\s+결정\s*[:：]?\s*\n?(.+?)(?=(?:\n\n|신상정보|공개|고지|$))'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        decision_text = match.group(1).strip()
        # 너무 길면 첫 500자만
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
    
    # 신상정보 등록 및 제출의무
    if re.search(r'신상정보\s*(?:의\s*)?(?:등록|제출)', text):
        personal_info["registration_required"] = True
        
        # 등록 관련 설명 추출 (신상정보 섹션 찾기)
        reg_section_match = re.search(
            r'(신상정보[^\n]*(?:등록|제출)[^\n]*)\n(.+?)(?=\n(?:공개|고지|취업|$))',
            text,
            re.DOTALL
        )
        if reg_section_match:
            title = reg_section_match.group(1).strip()
            desc = reg_section_match.group(2).strip()
            
            # 너무 긴 설명은 잘라내기
            if len(desc) > 400:
                # 첫 두 문장 정도만
                sentences = re.split(r'\.\s+', desc)
                if len(sentences) > 2:
                    desc = '. '.join(sentences[:2]) + '.'
                else:
                    desc = desc[:400] + '...'
            
            personal_info["registration_description"] = desc
    
    # 공개명령 면제
    disclosure_pattern = r'공개(?:명령)?[^\.]*면제'
    if re.search(disclosure_pattern, text):
        personal_info["disclosure_exempted"] = True
        
        # 면제 이유 추출
        exemption_section = re.search(
            r'공개[^\n]*면제[^\n]*\n(.+?)(?=\n\n|\Z)',
            text,
            re.DOTALL
        )
        if exemption_section:
            reason = exemption_section.group(1).strip()
            
            # 괄호 안의 내용 추출 (주로 여기에 이유가 있음)
            paren_match = re.search(r'\(([^)]{20,})\)', reason, re.DOTALL)
            if paren_match:
                reason = paren_match.group(1).strip()
                # 너무 길면 첫 200자
                if len(reason) > 200:
                    reason = reason[:200] + '...'
            else:
                # 괄호가 없으면 전체 설명 중 일부
                if len(reason) > 200:
                    reason = reason[:200] + '...'
            
            personal_info["disclosure_exemption_reason"] = reason
    
    # 고지명령 면제
    if re.search(r'고지(?:명령)?[^\.]*면제', text):
        personal_info["notification_exempted"] = True
    
    # 취업제한
    if re.search(r'취업제한', text):
        if re.search(r'취업제한[^\.]*면제', text):
            personal_info["employment_restriction_exempted"] = True
        else:
            personal_info["employment_restriction"] = True
    
    return personal_info


def extract_general_considerations(text: str) -> Optional[str]:
    """종합 고려사항 추출 (형법 제51조, 양형조건 등)"""
    # "그 밖에" 또는 "위와 같은" 등으로 시작하는 종합 문장
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
        case_id: 케이스 ID (선택)
        
    Returns:
        구조화된 딕셔너리
    """
    # 패턴 타입 감지
    pattern_type = detect_pattern_type(text)
    
    # 기본 구조
    structured = {
        "case_id": case_id,
        "pattern_type": pattern_type.value,
        "raw_text": text,
        "sentencing_reason": {},
        "personal_information": {}
    }
    
    # 약식 생략형인 경우
    if pattern_type == ReasonPatternType.OMITTED:
        structured["sentencing_reason"] = {"omitted": True}
        return structured
    
    # 양형 이유 추출
    sentencing = {}
    
    # 법률상 처단형의 범위 (구조화형, 혼합형)
    if pattern_type in [ReasonPatternType.STRUCTURED_GUIDELINE, ReasonPatternType.HYBRID]:
        statutory_range = extract_statutory_range(text)
        if statutory_range:
            sentencing["statutory_punishment_range"] = statutory_range
    
    # 양형기준 (구조화형)
    if pattern_type == ReasonPatternType.STRUCTURED_GUIDELINE:
        guidelines = extract_sentencing_guidelines(text)
        if any(guidelines.values()):
            sentencing["sentencing_guidelines"] = guidelines
        
        # 선고형의 결정
        final_decision = extract_final_decision(text)
        if final_decision:
            sentencing["final_decision"] = final_decision
    
    # 불리한 정상 / 유리한 정상 (모든 타입)
    unfavorable = extract_factors(text, '불리한')
    if unfavorable:
        sentencing["unfavorable_factors"] = unfavorable
    
    favorable = extract_factors(text, '유리한')
    if favorable:
        sentencing["favorable_factors"] = favorable
    
    # 종합 고려사항
    general = extract_general_considerations(text)
    if general:
        sentencing["general_considerations"] = general
    
    structured["sentencing_reason"] = sentencing
    
    # 신상정보 관련 (신상정보 포함형, 구조화형)
    if pattern_type in [ReasonPatternType.WITH_PERSONAL_INFO, ReasonPatternType.STRUCTURED_GUIDELINE]:
        personal_info = extract_personal_information(text)
        if any(personal_info.values()):
            structured["personal_information"] = personal_info
    
    return structured


def structure_dataset(dataset, id_column='id', reason_column='reason'):
    """
    데이터셋 전체를 구조화
    
    Args:
        dataset: HuggingFace Dataset
        id_column: ID 컬럼명
        reason_column: Reason 컬럼명
        
    Returns:
        구조화된 Dataset
    """
    def process_example(example):
        case_id = example.get(id_column)
        reason_text = example.get(reason_column, '')
        
        structured = structure_reason(reason_text, case_id)
        example['reason_structured'] = structured
        example['reason_pattern_type'] = structured['pattern_type']
        
        return example
    
    return dataset.map(process_example)


# ============================================================================
# 일괄 처리 스크립트
# ============================================================================

def run_batch_structuring(
    split: str = "train[:100]",
    output_file: str = "ljp_criminal_reason_structured.jsonl",
    include_original: bool = True
):
    """
    전체 데이터셋을 구조화하고 JSON 파일로 저장
    
    Args:
        split: 데이터셋 split (예: "train", "train[:100]")
        output_file: 출력 파일명
        include_original: 원본 reason 텍스트 포함 여부
    """
    print("="*80)
    print("LJP Criminal Dataset - Reason 구조화")
    print("="*80)
    
    # 데이터셋 로드
    print(f"\n1. 데이터셋 로딩 중... (split: {split})")
    dataset = load_dataset("lbox/lbox_open", "ljp_criminal", split=split, streaming=False)
    print(f"   ✓ 총 {len(dataset)}개 샘플 로드 완료")
    
    # 구조화
    print("\n2. 데이터셋 구조화 중...")
    structured_dataset = structure_dataset(dataset)
    print(f"   ✓ 구조화 완료")
    
    # 패턴 분포 분석
    print("\n3. 패턴 분포 분석...")
    pattern_counts = Counter()
    for example in structured_dataset:
        pattern_counts[example['reason_pattern_type']] += 1
    
    print("   패턴 타입 분포:")
    for pattern, count in pattern_counts.most_common():
        percentage = (count / len(structured_dataset)) * 100
        print(f"     - {pattern}: {count}개 ({percentage:.1f}%)")
    
    # 통계
    print("\n4. 추출 통계...")
    with_unfavorable = sum(
        1 for ex in structured_dataset 
        if ex['reason_structured']['sentencing_reason'].get('unfavorable_factors')
    )
    
    with_favorable = sum(
        1 for ex in structured_dataset 
        if ex['reason_structured']['sentencing_reason'].get('favorable_factors')
    )
    
    with_registration = sum(
        1 for ex in structured_dataset 
        if ex['reason_structured']['personal_information'].get('registration_required')
    )
    
    with_disclosure_exempt = sum(
        1 for ex in structured_dataset 
        if ex['reason_structured']['personal_information'].get('disclosure_exempted')
    )
    
    print(f"   - 불리한 정상 추출: {with_unfavorable}개 ({with_unfavorable/len(structured_dataset)*100:.1f}%)")
    print(f"   - 유리한 정상 추출: {with_favorable}개 ({with_favorable/len(structured_dataset)*100:.1f}%)")
    print(f"   - 신상정보 등록 필요: {with_registration}개 ({with_registration/len(structured_dataset)*100:.1f}%)")
    print(f"   - 공개명령 면제: {with_disclosure_exempt}개 ({with_disclosure_exempt/len(structured_dataset)*100:.1f}%)")
    
    # JSONL 저장
    print(f"\n5. JSONL 파일로 저장 중... ({output_file})")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for example in tqdm(structured_dataset, desc="   저장 중"):
            output_data = {
                'id': example['id'],
                'casetype': example['casetype'],
                'casename': example['casename'],
                'label': example['label'],
                'reason_structured': {
                    'case_id': example['reason_structured']['case_id'],
                    'pattern_type': example['reason_structured']['pattern_type'],
                    'sentencing_reason': example['reason_structured']['sentencing_reason'],
                    'personal_information': example['reason_structured']['personal_information']
                }
            }
            
            if include_original:
                output_data['reason_original'] = example['reason']
            
            f.write(json.dumps(output_data, ensure_ascii=False) + '\n')
    
    print(f"   ✓ 저장 완료: {output_file}")
    
    # 샘플 출력
    print("\n6. 샘플 데이터 (처음 2개):")
    print("="*80)
    
    with open(output_file, 'r', encoding='utf-8') as f:
        for i in range(min(2, len(structured_dataset))):
            line = f.readline()
            if not line:
                break
            data = json.loads(line)
            
            print(f"\n케이스 ID: {data['id']}")
            print(f"패턴: {data['reason_structured']['pattern_type']}")
            unfav = data['reason_structured']['sentencing_reason'].get('unfavorable_factors', [])
            fav = data['reason_structured']['sentencing_reason'].get('favorable_factors', [])
            print(f"불리한 정상: {len(unfav) if unfav else 0}개")
            print(f"유리한 정상: {len(fav) if fav else 0}개")
            
            if unfav:
                print(f"\n불리한 정상 예시:")
                for j, factor in enumerate(unfav[:2], 1):
                    print(f"  {j}. {factor[:80]}...")
            
            if i == 0:
                print("-"*80)
    
    print("\n" + "="*80)
    print("✅ 모든 작업 완료!")
    print("="*80)
    
    return structured_dataset


# ============================================================================
# 메인 실행
# ============================================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='LJP Criminal Dataset - Reason 구조화')
    parser.add_argument(
        '--split',
        type=str,
        default='train[:100]',
        help='데이터셋 split (예: "train", "train[:100]", "train[:1000]")'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='ljp_criminal_reason_structured.jsonl',
        help='출력 파일명'
    )
    parser.add_argument(
        '--no-original',
        action='store_true',
        help='원본 텍스트를 포함하지 않음'
    )
    
    args = parser.parse_args()
    
    run_batch_structuring(
        split=args.split,
        output_file=args.output,
        include_original=not args.no_original
    )
