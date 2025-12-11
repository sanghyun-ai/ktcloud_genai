"""
LJP Criminal Dataset - Reason 컬럼 구조화 모듈

reason 컬럼을 JSON 형식으로 구조화하여 추출
"""

import re
import json
from typing import Dict, List, Optional, Any
from enum import Enum


class ReasonPatternType(Enum):
    """Reason 패턴 타입"""
    BASIC_NARRATIVE = "기본 서술형"
    STRUCTURED_GUIDELINE = "구조화된 양형기준형"
    OMITTED = "약식 생략형"
    WITH_PERSONAL_INFO = "신상정보 포함형"
    HYBRID = "혼합형"


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


if __name__ == '__main__':
    # 테스트 예시
    test_texts = [
        # 기본 서술형
        """양형의 이유
피고인이 동종 범죄로 처벌받은 전력이 있는 점, 피고인이 전동차 안에서 피해자를 추행한 것으로 죄질이 좋지 않은 점은 불리한 정상이다.
다만, 피고인이 범행을 시인하고 반성하고 있는 점, 피해자와 합의되어 피해자가 피고인의 처벌을 원하지 않고 있는 점은 유리한 정상이다.
이러한 정상들과 피고인의 나이, 성행, 환경, 범행의 동기 및 결과를 참작하여 주문과 같은 형을 선고한다.""",
        
        # 구조화된 양형기준형
        """양형의 이유
1. 법률상 처단형의 범위: 징역 1월 ~ 10년
2. 양형기준에 따른 권고형의 범위
[유형의 결정] 성범죄 > 01. 일반적 기준 > 나. 강제추행죄(13세 이상 대상) > [제1유형] 일반강제추행
[특별양형인자] 감경요소 : 처벌불원
[권고영역 및 권고형의 범위] 감경영역, 징역 1월~1년
3. 선고형의 결정 :
추행의 정도가 가볍지 않은 점을 고려하여 징역형으로 처벌하되, 피고인이 이 사건 범행을 인정하고 있는 점을 참작하여 주문과 같이 형을 정한다.""",
        
        # 신상정보 포함형
        """양형의 이유
○ 불리한 정상
- 피고인은 피해자로부터 거부 의사를 확인하였음에도 추행을 계속하였다.
- 피고인은 피해자로부터 용서받지 못하였다.
○ 유리한 정상
- 피고인에게 동종 전과가 없다.
- 피고인이 잘못을 반성하고 있다.
그 밖에 피고인의 나이, 성행, 환경 등을 종합하여 주문과 같이 형을 정한다.
신상정보 등록 및 제출의무
판시 범죄사실에 대하여 유죄판결이 확정되는 경우, 피고인은 성폭력범죄의 처벌 등에 관한 특례법 제42조 제1항에 의하여 신상정보 등록대상자가 되므로, 같은 법 제43조에 따라 관할기관에 신상정보를 제출할 의무가 있다.
공개명령 또는 고지명령의 면제
피고인에게 동종전과가 없는 점 등을 종합하면, 피고인 신상정보의 공개, 고지를 명하여서는 아니 될 특별한 사정이 있다고 판단되므로, 피고인에 대하여 위 각 명령을 선고하지 아니한다."""
    ]
    
    print("="*80)
    print("Reason 구조화 테스트")
    print("="*80)
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n{'='*80}")
        print(f"테스트 {i}")
        print('='*80)
        
        structured = structure_reason(text, case_id=f"TEST_{i}")
        
        # raw_text 제외하고 출력
        output = structured.copy()
        output['raw_text'] = output['raw_text'][:100] + '...'
        
        print(json.dumps(output, ensure_ascii=False, indent=2))
