"""
LJP Criminal 데이터셋 전처리 가이드

이 스크립트는 lbox/lbox_open 데이터셋의 ljp_criminal split에서 
다음 컬럼들의 전처리 방법을 제공합니다:
- facts: 사건 사실
- label: 판결 형량 레이블
- ruling: 판결문
- reason: 판결 이유
"""

from datasets import load_dataset
import json
import re
from typing import Dict, List, Any, Union


# ============================================================================
# 1. Facts 컬럼 전처리
# ============================================================================

def preprocess_facts(facts: str) -> str:
    """
    Facts 컬럼 전처리 함수
    
    전처리 내용:
    1. 불필요한 공백 제거 및 정규화
    2. 줄바꿈 문자 정리
    3. 연속된 공백 제거
    
    Args:
        facts: 원본 facts 텍스트
    
    Returns:
        전처리된 facts 텍스트
    """
    # 줄바꿈 문자를 공백으로 변환
    text = facts.replace('\n', ' ').replace('\r', ' ')
    
    # 연속된 공백을 하나로 통일
    text = re.sub(r'\s+', ' ', text)
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    return text


# ============================================================================
# 2. Label 컬럼 전처리
# ============================================================================

def preprocess_label(label: Dict[str, Any], format: str = 'dict') -> Any:
    """
    Label 컬럼 전처리 함수
    
    Args:
        label: 원본 label 딕셔너리
        format: 반환 형식
            - 'dict': 원본 딕셔너리 그대로
            - 'text': 텍스트만 추출 (예: "징역 6월")
            - 'multiclass': 가장 높은 형벌 종류를 클래스로
            - 'multilabel': 각 형벌 종류를 독립적인 레이블로
            - 'numeric': 수치형 벡터 [fine_lv, imprisonment_with_labor_lv, imprisonment_without_labor_lv]
            - 'level': 가장 높은 레벨 값
    
    Returns:
        format에 따라 다른 형태로 변환된 label
    """
    if format == 'dict':
        return label
    
    elif format == 'text':
        return label['text']
    
    elif format == 'multiclass':
        # 가장 높은 레벨의 형벌 종류를 클래스로 사용
        if label['imprisonment_with_labor_lv'] > 0:
            return 'imprisonment_with_labor'
        elif label['imprisonment_without_labor_lv'] > 0:
            return 'imprisonment_without_labor'
        elif label['fine_lv'] > 0:
            return 'fine'
        else:
            return 'none'
    
    elif format == 'multilabel':
        # 각 형벌 종류를 독립적인 레이블로
        return {
            'fine': label['fine_lv'] > 0,
            'imprisonment_with_labor': label['imprisonment_with_labor_lv'] > 0,
            'imprisonment_without_labor': label['imprisonment_without_labor_lv'] > 0
        }
    
    elif format == 'numeric':
        # 수치형 벡터로 변환
        return [
            label['fine_lv'],
            label['imprisonment_with_labor_lv'],
            label['imprisonment_without_labor_lv']
        ]
    
    elif format == 'level':
        # 가장 높은 레벨 값 반환
        return max(
            label['fine_lv'],
            label['imprisonment_with_labor_lv'],
            label['imprisonment_without_labor_lv']
        )
    
    else:
        raise ValueError(f"Unknown format: {format}")


# ============================================================================
# 3. Ruling 컬럼 전처리
# ============================================================================

def preprocess_ruling(ruling: Dict[str, Any], extract: str = 'all') -> Any:
    """
    Ruling 컬럼 전처리 함수
    
    Args:
        ruling: 원본 ruling 딕셔너리
        extract: 추출할 정보
            - 'all': 전체 딕셔너리
            - 'text': 텍스트만 추출 및 정리
            - 'parse': 구조화된 parse 정보만
            - 'imprisonment': 징역/금고 정보만
            - 'fine': 벌금 정보만
            - 'combined': 텍스트와 parse를 결합
    
    Returns:
        extract에 따라 다른 형태로 변환된 ruling
    """
    if extract == 'all':
        return ruling
    
    elif extract == 'text':
        # 텍스트만 추출 및 정리
        text = ruling['text']
        # 줄바꿈 정리
        text = re.sub(r'\n+', '\n', text)
        text = text.strip()
        return text
    
    elif extract == 'parse':
        return ruling.get('parse', {})
    
    elif extract == 'imprisonment':
        # 징역/금고 정보만 추출
        parse = ruling.get('parse', {})
        imprisonment = parse.get('imprisonment', {})
        return {
            'type': imprisonment.get('type', ''),
            'unit': imprisonment.get('unit', ''),
            'value': imprisonment.get('value', -1)
        }
    
    elif extract == 'fine':
        # 벌금 정보만 추출
        parse = ruling.get('parse', {})
        fine = parse.get('fine', {})
        return {
            'type': fine.get('type', ''),
            'unit': fine.get('unit', ''),
            'value': fine.get('value', -1)
        }
    
    elif extract == 'combined':
        # 텍스트와 parse를 결합한 정보
        return {
            'text': preprocess_ruling(ruling, 'text'),
            'imprisonment': preprocess_ruling(ruling, 'imprisonment'),
            'fine': preprocess_ruling(ruling, 'fine')
        }
    
    else:
        raise ValueError(f"Unknown extract type: {extract}")


# ============================================================================
# 4. Reason 컬럼 전처리
# ============================================================================

def preprocess_reason(reason: str, mode: str = 'clean') -> Union[str, Dict[str, str]]:
    """
    Reason 컬럼 전처리 함수
    
    Args:
        reason: 원본 reason 텍스트
        mode: 전처리 모드
            - 'clean': 기본 정리 (공백 정규화, 줄바꿈 정리)
            - 'split_sections': 섹션별로 분리하여 딕셔너리로 반환
            - 'extract_key_info': 주요 정보만 추출
            - 'minimal': 최소한의 정리만 (원본 유지)
    
    Returns:
        mode에 따라 다른 형태로 변환된 reason
    """
    if mode == 'clean':
        # 기본 정리: 공백 정규화, 줄바꿈 정리
        text = reason.replace('\r', '\n')
        # 연속된 줄바꿈을 2개로 제한
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 연속된 공백 제거
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()
        return text
    
    elif mode == 'split_sections':
        # 섹션별로 분리
        sections = {}
        lines = reason.split('\n')
        current_section = '기타'
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 섹션 헤더 감지 (숫자로 시작하거나 특정 키워드 포함)
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
    
    elif mode == 'extract_key_info':
        # 주요 정보만 추출
        key_patterns = {
            '법률상 처단형': r'법률상 처단형의 범위[:\s]+([^\n]+)',
            '권고형': r'권고형의 범위[:\s]+([^\n]+)',
            '선고형': r'선고형의 결정[:\s]+([^\n]+)',
            '유형': r'\[유형의 결정\][^\n]+',
            '특별양형인자': r'\[특별양형인자\][^\n]+'
        }
        
        extracted = {}
        for key, pattern in key_patterns.items():
            match = re.search(pattern, reason)
            if match:
                extracted[key] = match.group(1) if match.groups() else match.group(0)
        
        return extracted
    
    elif mode == 'minimal':
        # 최소한의 정리만 (원본 유지)
        return reason.strip()
    
    else:
        raise ValueError(f"Unknown mode: {mode}")


# ============================================================================
# 5. 전체 데이터셋 전처리
# ============================================================================

def preprocess_dataset(dataset, 
                       facts_mode: str = 'clean',
                       label_format: str = 'dict',
                       ruling_extract: str = 'all',
                       reason_mode: str = 'clean'):
    """
    전체 데이터셋에 전처리 적용
    
    Args:
        dataset: HuggingFace Dataset 객체
        facts_mode: facts 전처리 모드 (현재는 'clean'만 지원)
        label_format: label 변환 형식
        ruling_extract: ruling 추출 형식
        reason_mode: reason 전처리 모드
    
    Returns:
        전처리된 데이터셋
    """
    def process_example(example):
        processed = {}
        
        # Facts 전처리
        processed['facts'] = preprocess_facts(example['facts'])
        
        # Label 전처리
        processed['label'] = preprocess_label(example['label'], label_format)
        
        # Ruling 전처리
        processed['ruling'] = preprocess_ruling(example['ruling'], ruling_extract)
        
        # Reason 전처리
        processed['reason'] = preprocess_reason(example['reason'], reason_mode)
        
        # 원본 정보 유지 (필요시)
        processed['id'] = example['id']
        processed['casetype'] = example['casetype']
        processed['casename'] = example['casename']
        
        return processed
    
    return dataset.map(process_example)


# ============================================================================
# 6. 사용 사례별 전처리 함수
# ============================================================================

def prepare_for_text_classification(dataset):
    """텍스트 분류 모델 학습을 위한 전처리"""
    def process(example):
        return {
            'text': preprocess_facts(example['facts']),
            'label': preprocess_label(example['label'], 'text'),
            'id': example['id']
        }
    return dataset.map(process)


def prepare_for_sentence_prediction(dataset):
    """형량 예측 모델 학습을 위한 전처리"""
    def process(example):
        return {
            'input_text': preprocess_facts(example['facts']),
            'target': preprocess_label(example['label'], 'numeric'),
            'target_text': preprocess_label(example['label'], 'text'),
            'id': example['id']
        }
    return dataset.map(process)


def prepare_for_rag(dataset):
    """RAG 시스템을 위한 전처리"""
    def process(example):
        sections = preprocess_reason(example['reason'], 'split_sections')
        return {
            'query': preprocess_facts(example['facts']),
            'context': {
                'ruling': preprocess_ruling(example['ruling'], 'combined'),
                'reason_sections': sections,
                'label': example['label']
            },
            'id': example['id']
        }
    return dataset.map(process)


# ============================================================================
# 사용 예시
# ============================================================================

if __name__ == '__main__':
    # 데이터셋 로드
    print("데이터셋 로드 중...")
    dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split='train')
    
    print(f"데이터셋 크기: {len(dataset)}")
    print(f"컬럼: {dataset.column_names}\n")
    
    # 샘플 데이터 확인
    sample = dataset[0]
    print("=== 샘플 데이터 ===")
    print(f"Facts: {sample['facts'][:100]}...")
    print(f"Label: {sample['label']}")
    print(f"Reason 길이: {len(sample['reason'])} 문자\n")
    
    # 전처리 예시
    print("=== 전처리 예시 ===\n")
    
    # 1. Facts 전처리
    print("1. Facts 전처리:")
    processed_facts = preprocess_facts(sample['facts'])
    print(f"   원본 길이: {len(sample['facts'])}")
    print(f"   전처리 후: {processed_facts[:100]}...\n")
    
    # 2. Label 전처리
    print("2. Label 전처리:")
    print(f"   텍스트 형식: {preprocess_label(sample['label'], 'text')}")
    print(f"   멀티클래스: {preprocess_label(sample['label'], 'multiclass')}")
    print(f"   수치형: {preprocess_label(sample['label'], 'numeric')}\n")
    
    # 3. Ruling 전처리
    print("3. Ruling 전처리:")
    print(f"   텍스트만: {preprocess_ruling(sample['ruling'], 'text')[:100]}...")
    print(f"   징역 정보: {preprocess_ruling(sample['ruling'], 'imprisonment')}\n")
    
    # 4. Reason 전처리
    print("4. Reason 전처리:")
    cleaned_reason = preprocess_reason(sample['reason'], 'clean')
    print(f"   Clean 모드 길이: {len(cleaned_reason)}")
    key_info = preprocess_reason(sample['reason'], 'extract_key_info')
    print(f"   주요 정보 추출: {list(key_info.keys())}\n")
    
    print("전처리 함수들이 준비되었습니다!")
    print("\n사용 사례별 권장사항:")
    print("- 텍스트 분류: prepare_for_text_classification()")
    print("- 형량 예측: prepare_for_sentence_prediction()")
    print("- RAG 시스템: prepare_for_rag()")
