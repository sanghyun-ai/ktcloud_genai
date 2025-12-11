"""
LJP Criminal 데이터셋 전처리 - 법정공방 시뮬레이션용

목적:
1. Facts만 검사/변호사/판사 역할의 에이전트에게 전달
2. 유저(판사)가 선택한 형량과 실제 형량(label)을 비교

전처리 전략:
- Facts: 에이전트에게 전달하기 적합한 형태로 정리
- Label: 비교하기 쉬운 형태로 변환 (텍스트, 수치형 등)
- Ruling/Reason: 피드백이나 설명에 활용
"""

from datasets import load_dataset
import json
import re
from typing import Dict, List, Any, Union, Tuple


# ============================================================================
# 1. Facts 전처리 - 에이전트 전달용
# ============================================================================

def preprocess_facts_for_agent(facts: str) -> str:
    """
    Facts를 에이전트에게 전달하기 위한 전처리
    
    전처리 내용:
    1. 줄바꿈을 공백으로 변환 (한 줄로 정리)
    2. 연속된 공백 정리
    3. 앞뒤 공백 제거
    4. 문장 끝 정리 (마침표 확인)
    
    Args:
        facts: 원본 facts 텍스트
    
    Returns:
        에이전트에게 전달하기 적합한 facts 텍스트
    """
    # 줄바꿈을 공백으로 변환
    text = facts.replace('\n', ' ').replace('\r', ' ')
    
    # 연속된 공백을 하나로 통일
    text = re.sub(r'\s+', ' ', text)
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    # 문장 끝에 마침표가 없으면 추가 (선택사항)
    # if text and not text.endswith(('.', '!', '?')):
    #     text += '.'
    
    return text


# ============================================================================
# 2. Label 전처리 - 형량 비교용
# ============================================================================

def preprocess_label_for_comparison(label: Dict[str, Any]) -> Dict[str, Any]:
    """
    Label을 유저 선택 형량과 비교하기 쉽도록 변환
    
    반환 형태:
    {
        'text': '징역 6월',  # 원본 텍스트
        'fine_lv': 0,
        'imprisonment_with_labor_lv': 2,
        'imprisonment_without_labor_lv': 0,
        'main_type': 'imprisonment_with_labor',  # 주요 형벌 종류
        'main_level': 2,  # 주요 형벌 레벨
        'numeric_vector': [0, 2, 0],  # 비교용 수치 벡터
        'is_fine': False,
        'is_imprisonment': True
    }
    
    Args:
        label: 원본 label 딕셔너리
    
    Returns:
        비교에 최적화된 label 딕셔너리
    """
    # 주요 형벌 종류 결정
    if label['imprisonment_with_labor_lv'] > 0:
        main_type = 'imprisonment_with_labor'
        main_level = label['imprisonment_with_labor_lv']
    elif label['imprisonment_without_labor_lv'] > 0:
        main_type = 'imprisonment_without_labor'
        main_level = label['imprisonment_without_labor_lv']
    elif label['fine_lv'] > 0:
        main_type = 'fine'
        main_level = label['fine_lv']
    else:
        main_type = 'none'
        main_level = 0
    
    return {
        'text': label['text'],
        'fine_lv': label['fine_lv'],
        'imprisonment_with_labor_lv': label['imprisonment_with_labor_lv'],
        'imprisonment_without_labor_lv': label['imprisonment_without_labor_lv'],
        'main_type': main_type,
        'main_level': main_level,
        'numeric_vector': [
            label['fine_lv'],
            label['imprisonment_with_labor_lv'],
            label['imprisonment_without_labor_lv']
        ],
        'is_fine': label['fine_lv'] > 0,
        'is_imprisonment': (label['imprisonment_with_labor_lv'] > 0 or 
                           label['imprisonment_without_labor_lv'] > 0)
    }


def compare_user_sentence_with_actual(user_sentence: Dict[str, Any], 
                                      actual_label: Dict[str, Any]) -> Dict[str, Any]:
    """
    유저가 선택한 형량과 실제 형량을 비교
    
    Args:
        user_sentence: 유저가 선택한 형량 (preprocess_label_for_comparison 형식)
        actual_label: 실제 형량 (preprocess_label_for_comparison 형식)
    
    Returns:
        비교 결과 딕셔너리
    """
    # 형벌 종류 일치 여부
    type_match = user_sentence['main_type'] == actual_label['main_type']
    
    # 레벨 차이
    level_diff = user_sentence['main_level'] - actual_label['main_level']
    
    # 수치 벡터 차이
    vector_diff = [
        user_sentence['numeric_vector'][i] - actual_label['numeric_vector'][i]
        for i in range(3)
    ]
    
    # 정확도 점수 (0-1)
    if type_match and level_diff == 0:
        accuracy = 1.0
    elif type_match:
        # 같은 종류이지만 레벨이 다름 (레벨 차이에 따라 감점)
        accuracy = max(0.0, 1.0 - abs(level_diff) * 0.2)
    else:
        # 다른 종류 (0점)
        accuracy = 0.0
    
    return {
        'type_match': type_match,
        'level_diff': level_diff,
        'vector_diff': vector_diff,
        'accuracy': accuracy,
        'user_text': user_sentence['text'],
        'actual_text': actual_label['text'],
        'feedback': generate_feedback(user_sentence, actual_label, type_match, level_diff)
    }


def generate_feedback(user_sentence: Dict[str, Any], 
                      actual_label: Dict[str, Any],
                      type_match: bool,
                      level_diff: int) -> str:
    """비교 결과에 대한 피드백 생성"""
    if type_match and level_diff == 0:
        return "정확한 형량을 선택하셨습니다!"
    elif type_match:
        if level_diff > 0:
            return f"형벌 종류는 맞았지만, 실제보다 {abs(level_diff)}단계 높게 선택하셨습니다. (실제: {actual_label['text']})"
        else:
            return f"형벌 종류는 맞았지만, 실제보다 {abs(level_diff)}단계 낮게 선택하셨습니다. (실제: {actual_label['text']})"
    else:
        return f"형벌 종류가 다릅니다. 선택하신 형량: {user_sentence['text']}, 실제 형량: {actual_label['text']}"


# ============================================================================
# 3. Ruling 전처리 - 피드백용
# ============================================================================

def preprocess_ruling_for_feedback(ruling: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ruling을 피드백에 활용하기 위한 전처리
    
    Returns:
        {
            'text': 판결문 텍스트,
            'imprisonment': 징역/금고 정보,
            'fine': 벌금 정보,
            'summary': 요약 정보
        }
    """
    text = ruling.get('text', '')
    parse = ruling.get('parse', {})
    
    imprisonment = parse.get('imprisonment', {})
    fine = parse.get('fine', {})
    
    # 요약 정보 생성
    summary_parts = []
    if imprisonment.get('value', -1) > 0:
        unit_map = {'mo': '개월', 'yr': '년', 'day': '일'}
        unit = unit_map.get(imprisonment.get('unit', ''), imprisonment.get('unit', ''))
        summary_parts.append(f"{imprisonment.get('type', '')} {imprisonment.get('value')}{unit}")
    if fine.get('value', -1) > 0:
        summary_parts.append(f"벌금 {fine.get('value'):,}원")
    
    return {
        'text': text.strip(),
        'imprisonment': {
            'type': imprisonment.get('type', ''),
            'unit': imprisonment.get('unit', ''),
            'value': imprisonment.get('value', -1)
        },
        'fine': {
            'type': fine.get('type', ''),
            'unit': fine.get('unit', ''),
            'value': fine.get('value', -1)
        },
        'summary': ', '.join(summary_parts) if summary_parts else '형량 정보 없음'
    }


# ============================================================================
# 4. Reason 전처리 - 설명용
# ============================================================================

def preprocess_reason_for_explanation(reason: str) -> Dict[str, str]:
    """
    Reason을 설명에 활용하기 위한 전처리
    
    Returns:
        섹션별로 분리된 딕셔너리
    """
    sections = {}
    lines = reason.split('\n')
    current_section = '기타'
    current_content = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 섹션 헤더 감지
        if re.match(r'^\d+\.', line) or any(keyword in line for keyword in 
            ['법률상', '양형기준', '선고형', '신상정보', '유형의 결정', '특별양형인자']):
            if current_content:
                sections[current_section] = ' '.join(current_content)
            current_section = line
            current_content = []
        else:
            current_content.append(line)
    
    if current_content:
        sections[current_section] = ' '.join(current_content)
    
    return sections


# ============================================================================
# 5. 전체 데이터셋 전처리 - 시뮬레이션용
# ============================================================================

def preprocess_for_simulation(dataset, sample_idx: int = None):
    """
    법정공방 시뮬레이션을 위한 데이터 전처리
    
    Args:
        dataset: HuggingFace Dataset 객체
        sample_idx: 특정 샘플 인덱스 (None이면 전체)
    
    Returns:
        전처리된 데이터
    """
    if sample_idx is not None:
        dataset = dataset.select([sample_idx])
    
    def process_example(example):
        return {
            # 에이전트에게 전달할 facts
            'facts_for_agent': preprocess_facts_for_agent(example['facts']),
            
            # 비교용 label
            'label_for_comparison': preprocess_label_for_comparison(example['label']),
            
            # 피드백용 ruling
            'ruling_for_feedback': preprocess_ruling_for_feedback(example['ruling']),
            
            # 설명용 reason
            'reason_for_explanation': preprocess_reason_for_explanation(example['reason']),
            
            # 원본 정보 (참고용)
            'id': example['id'],
            'casetype': example['casetype'],
            'casename': example['casename'],
            'original_facts': example['facts'],
            'original_label': example['label']
        }
    
    return dataset.map(process_example)


# ============================================================================
# 6. 사용 예시
# ============================================================================

if __name__ == '__main__':
    # 데이터셋 로드
    print("데이터셋 로드 중...")
    dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split='train')
    
    # 샘플 하나 전처리
    sample = dataset[0]
    print(f"\n샘플 0: {sample['casename']}")
    print("="*100)
    
    # 1. Facts 전처리 (에이전트 전달용)
    print("\n【1. Facts - 에이전트 전달용】")
    print("-" * 100)
    facts_for_agent = preprocess_facts_for_agent(sample['facts'])
    print("원문:")
    print(sample['facts'])
    print(f"\n전처리 후 (에이전트 전달용):")
    print(facts_for_agent)
    
    # 2. Label 전처리 (비교용)
    print("\n\n【2. Label - 비교용】")
    print("-" * 100)
    label_for_comparison = preprocess_label_for_comparison(sample['label'])
    print("원문:")
    print(json.dumps(sample['label'], ensure_ascii=False, indent=2))
    print(f"\n전처리 후 (비교용):")
    print(json.dumps(label_for_comparison, ensure_ascii=False, indent=2))
    
    # 3. 비교 예시
    print("\n\n【3. 형량 비교 예시】")
    print("-" * 100)
    
    # 실제 형량
    actual = preprocess_label_for_comparison(sample['label'])
    print(f"실제 형량: {actual['text']} (타입: {actual['main_type']}, 레벨: {actual['main_level']})")
    
    # 유저가 선택한 형량 (예시 1: 정확한 선택)
    user_correct = {
        'text': '징역 6월',
        'fine_lv': 0,
        'imprisonment_with_labor_lv': 2,
        'imprisonment_without_labor_lv': 0
    }
    user_correct_processed = preprocess_label_for_comparison(user_correct)
    comparison_correct = compare_user_sentence_with_actual(user_correct_processed, actual)
    print(f"\n유저 선택 (정확): {user_correct_processed['text']}")
    print(f"비교 결과: {json.dumps(comparison_correct, ensure_ascii=False, indent=2)}")
    
    # 유저가 선택한 형량 (예시 2: 레벨 차이)
    user_wrong_level = {
        'text': '징역 8월',
        'fine_lv': 0,
        'imprisonment_with_labor_lv': 3,  # 레벨 차이를 보이기 위해 3으로 설정
        'imprisonment_without_labor_lv': 0
    }
    user_wrong_level_processed = preprocess_label_for_comparison(user_wrong_level)
    comparison_wrong_level = compare_user_sentence_with_actual(user_wrong_level_processed, actual)
    print(f"\n유저 선택 (레벨 차이): {user_wrong_level_processed['text']}")
    print(f"비교 결과: {json.dumps(comparison_wrong_level, ensure_ascii=False, indent=2)}")
    
    # 유저가 선택한 형량 (예시 3: 타입 차이)
    user_wrong_type = {
        'text': '벌금 5000000원',
        'fine_lv': 3,
        'imprisonment_with_labor_lv': 0,
        'imprisonment_without_labor_lv': 0
    }
    user_wrong_type_processed = preprocess_label_for_comparison(user_wrong_type)
    comparison_wrong_type = compare_user_sentence_with_actual(user_wrong_type_processed, actual)
    print(f"\n유저 선택 (타입 차이): {user_wrong_type_processed['text']}")
    print(f"비교 결과: {json.dumps(comparison_wrong_type, ensure_ascii=False, indent=2)}")
    
    # 4. Ruling 전처리 (피드백용)
    print("\n\n【4. Ruling - 피드백용】")
    print("-" * 100)
    ruling_for_feedback = preprocess_ruling_for_feedback(sample['ruling'])
    print(json.dumps(ruling_for_feedback, ensure_ascii=False, indent=2))
    
    # 5. Reason 전처리 (설명용)
    print("\n\n【5. Reason - 설명용 (섹션별 분리)】")
    print("-" * 100)
    reason_for_explanation = preprocess_reason_for_explanation(sample['reason'])
    for section, content in list(reason_for_explanation.items())[:3]:
        print(f"\n[{section}]")
        print(content[:200] + "..." if len(content) > 200 else content)
    
    print("\n\n" + "="*100)
    print("전처리 완료! 이제 시뮬레이션에 사용할 수 있습니다.")
    print("="*100)
