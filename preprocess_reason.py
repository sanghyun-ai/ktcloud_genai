"""
LJP Criminal Dataset - Reason 컬럼 전처리 모듈

원본 텍스트를 최대한 보존하면서 최소한의 정규화만 수행
"""

import re
from typing import Optional


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
        # 줄 끝 공백 제거 (줄 시작 공백은 들여쓰기일 수 있으므로 신중하게 처리)
        line = line.rstrip()
        
        # 리스트 마커로 시작하는 경우: 앞 공백 제거 + 마커 뒤 공백 정규화
        # ○, ●, •, -, * 등
        if re.match(r'^\s*[○●•\-\*]\s+', line):
            # 앞 공백 제거
            line = line.lstrip()
            # 마커 뒤 공백을 단일 공백으로
            line = re.sub(r'^([○●•\-\*])\s+', r'\1 ', line)
        
        # 숫자 섹션 헤더인 경우: 앞 공백 제거 + 숫자. 뒤 공백 정규화
        # 예: "1. 법률상 처단형의 범위"
        elif re.match(r'^\s*\d+\.\s+', line):
            # 앞 공백 제거
            line = line.lstrip()
            # 숫자. 뒤 공백을 단일 공백으로
            line = re.sub(r'^(\d+\.)\s+', r'\1 ', line)
        
        # 일반 헤더로 보이는 경우 (짧고 특정 키워드 포함)
        # 예: "양형의 이유", "신상정보 등록 및 제출의무"
        elif line.strip() and len(line.strip()) < 50:
            if re.search(r'(이유|의무|명령|면제)$', line.strip()):
                line = line.strip()
        
        processed_lines.append(line)
    
    # 3. 다시 합치기
    result = '\n'.join(processed_lines)
    
    # 4. 연속된 빈 줄 정리 (3개 이상의 연속 빈 줄을 2개로)
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    # 5. 전체 앞뒤 공백 제거
    result = result.strip()
    
    return result


def validate_preprocessing(original: str, preprocessed: str) -> dict:
    """
    전처리 검증 함수
    원본과 전처리된 텍스트를 비교하여 주요 내용이 유지되었는지 확인
    
    Args:
        original: 원본 텍스트
        preprocessed: 전처리된 텍스트
        
    Returns:
        검증 결과 딕셔너리
    """
    # 공백을 모두 제거하고 비교 (내용이 동일한지 확인)
    orig_no_space = re.sub(r'\s+', '', original)
    prep_no_space = re.sub(r'\s+', '', preprocessed)
    
    # 주요 패턴 개수 확인
    patterns_to_check = {
        '리스트_마커_○': r'○',
        '리스트_마커_-': r'^-\s',
        '법률_조항': r'제\d+조',
        '괄호': r'\([^)]+\)',
        '섹션_헤더': r'^\d+\.\s+[가-힣]',
    }
    
    pattern_counts = {}
    for name, pattern in patterns_to_check.items():
        orig_count = len(re.findall(pattern, original, re.MULTILINE))
        prep_count = len(re.findall(pattern, preprocessed, re.MULTILINE))
        pattern_counts[name] = {
            'original': orig_count,
            'preprocessed': prep_count,
            'match': orig_count == prep_count
        }
    
    return {
        'content_preserved': orig_no_space == prep_no_space,
        'original_length': len(original),
        'preprocessed_length': len(preprocessed),
        'length_diff': len(preprocessed) - len(original),
        'pattern_counts': pattern_counts,
        'all_patterns_match': all(v['match'] for v in pattern_counts.values())
    }


def preprocess_dataset(dataset, column_name='reason', validate=True):
    """
    데이터셋의 reason 컬럼 전체 전처리
    
    Args:
        dataset: HuggingFace Dataset 객체
        column_name: 전처리할 컬럼 이름 (기본값: 'reason')
        validate: 전처리 검증 수행 여부
        
    Returns:
        전처리된 Dataset 객체
    """
    def process_example(example):
        original = example[column_name]
        preprocessed = preprocess_reason(original)
        example[f'{column_name}_preprocessed'] = preprocessed
        
        if validate:
            validation = validate_preprocessing(original, preprocessed)
            example[f'{column_name}_validation'] = validation
        
        return example
    
    return dataset.map(process_example)


if __name__ == '__main__':
    # 테스트 예시
    test_text = """양형의 이유
○  불리한 정상
-  피고인은 피해자로부터 거부 의사를 확인하였음에도 추행을 계속하였다.
-   피고인은 피해자로부터 용서받지 못하였다.
○ 유리한 정상
- 피고인에게 동종 전과가 없다.


신상정보 등록 및 제출의무  
판시 범죄사실에 대하여 유죄판결이 확정되는 경우, 피고인은 성폭력범죄의 처벌 등에 관한 특례법 제42조 제1항에 의하여 신상정보 등록대상자가 되므로, 같은 법 제43조에 따라 관할기관에 신상정보를 제출할 의무가 있다.
"""
    
    print("=== 원본 ===")
    print(repr(test_text))
    print("\n" + "="*80 + "\n")
    
    preprocessed = preprocess_reason(test_text)
    print("=== 전처리 결과 ===")
    print(repr(preprocessed))
    print("\n" + "="*80 + "\n")
    
    validation = validate_preprocessing(test_text, preprocessed)
    print("=== 검증 결과 ===")
    print(f"내용 보존: {validation['content_preserved']}")
    print(f"원본 길이: {validation['original_length']}")
    print(f"전처리 후 길이: {validation['preprocessed_length']}")
    print(f"길이 차이: {validation['length_diff']} (제거된 불필요한 공백)")
    print(f"\n패턴 개수 일치: {validation['all_patterns_match']}")
    for pattern_name, counts in validation['pattern_counts'].items():
        print(f"  {pattern_name}: {counts['original']} → {counts['preprocessed']} ({'✓' if counts['match'] else '✗'})")
