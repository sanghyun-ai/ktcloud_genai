"""
LJP Criminal 데이터셋 전처리 비교 스크립트

각 전처리 단계별로 원문 데이터와 전처리된 데이터를 나란히 비교해서 출력합니다.
"""

from datasets import load_dataset
import json
import re
from typing import Dict, List, Any, Union

# 전처리 함수들
def preprocess_facts(facts: str) -> str:
    text = facts.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def preprocess_label(label: Dict[str, Any], format: str = 'dict') -> Any:
    if format == 'dict':
        return label
    elif format == 'text':
        return label['text']
    elif format == 'multiclass':
        if label['imprisonment_with_labor_lv'] > 0:
            return 'imprisonment_with_labor'
        elif label['imprisonment_without_labor_lv'] > 0:
            return 'imprisonment_without_labor'
        elif label['fine_lv'] > 0:
            return 'fine'
        else:
            return 'none'
    elif format == 'multilabel':
        return {
            'fine': label['fine_lv'] > 0,
            'imprisonment_with_labor': label['imprisonment_with_labor_lv'] > 0,
            'imprisonment_without_labor': label['imprisonment_without_labor_lv'] > 0
        }
    elif format == 'numeric':
        return [
            label['fine_lv'],
            label['imprisonment_with_labor_lv'],
            label['imprisonment_without_labor_lv']
        ]
    elif format == 'level':
        return max(
            label['fine_lv'],
            label['imprisonment_with_labor_lv'],
            label['imprisonment_without_labor_lv']
        )
    else:
        raise ValueError(f"Unknown format: {format}")

def preprocess_ruling(ruling: Dict[str, Any], extract: str = 'all') -> Any:
    if extract == 'all':
        return ruling
    elif extract == 'text':
        text = ruling['text']
        text = re.sub(r'\n+', '\n', text)
        return text.strip()
    elif extract == 'parse':
        return ruling.get('parse', {})
    elif extract == 'imprisonment':
        parse = ruling.get('parse', {})
        imprisonment = parse.get('imprisonment', {})
        return {
            'type': imprisonment.get('type', ''),
            'unit': imprisonment.get('unit', ''),
            'value': imprisonment.get('value', -1)
        }
    elif extract == 'fine':
        parse = ruling.get('parse', {})
        fine = parse.get('fine', {})
        return {
            'type': fine.get('type', ''),
            'unit': fine.get('unit', ''),
            'value': fine.get('value', -1)
        }
    elif extract == 'combined':
        return {
            'text': preprocess_ruling(ruling, 'text'),
            'imprisonment': preprocess_ruling(ruling, 'imprisonment'),
            'fine': preprocess_ruling(ruling, 'fine')
        }
    else:
        raise ValueError(f"Unknown extract type: {extract}")

def preprocess_reason(reason: str, mode: str = 'clean') -> Union[str, Dict[str, str]]:
    if mode == 'clean':
        text = reason.replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()
    elif mode == 'split_sections':
        sections = {}
        lines = reason.split('\n')
        current_section = '기타'
        current_content = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
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
        return reason.strip()
    else:
        raise ValueError(f"Unknown mode: {mode}")

def print_separator(char='=', length=100):
    print(char * length)

def compare_facts(original, processed, sample_num):
    """Facts 전처리 비교 출력"""
    print_separator()
    print(f"샘플 {sample_num} - Facts 컬럼 전처리 비교")
    print_separator()
    print("\n📄 원문 데이터:")
    print("-" * 100)
    print(original)
    print(f"\n[통계] 길이: {len(original)} 문자, 줄바꿈: {original.count(chr(10))}개, 공백: {original.count(' ')}개")
    
    print("\n\n✨ 전처리된 데이터:")
    print("-" * 100)
    print(processed)
    print(f"\n[통계] 길이: {len(processed)} 문자, 줄바꿈: {processed.count(chr(10))}개, 공백: {processed.count(' ')}개")
    
    print("\n\n📊 변경 사항:")
    print("-" * 100)
    changes = []
    if original != processed:
        if original.count('\n') > 0:
            changes.append(f"✓ 줄바꿈 제거: {original.count(chr(10))}개 → 0개")
        if len(original) != len(processed):
            changes.append(f"✓ 길이 변화: {len(original)} → {len(processed)} 문자 ({len(original) - len(processed):+d})")
        if re.search(r'\s{2,}', original) and not re.search(r'\s{2,}', processed):
            changes.append("✓ 연속 공백 정리 완료")
    else:
        changes.append("변경사항 없음")
    
    for change in changes:
        print(change)
    print("\n")

def compare_label(original, sample_num):
    """Label 전처리 비교 출력"""
    print_separator()
    print(f"샘플 {sample_num} - Label 컬럼 전처리 비교")
    print_separator()
    
    print("\n📄 원문 데이터:")
    print("-" * 100)
    print(json.dumps(original, ensure_ascii=False, indent=2))
    
    print("\n\n✨ 전처리된 데이터 (다양한 형식):")
    print("-" * 100)
    
    formats = [
        ('text', '텍스트 형식'),
        ('multiclass', '멀티클래스 형식'),
        ('multilabel', '멀티라벨 형식'),
        ('numeric', '수치형 형식'),
        ('level', '레벨 형식')
    ]
    
    for fmt, desc in formats:
        processed = preprocess_label(original, fmt)
        print(f"\n[{desc} ({fmt})]")
        print("-" * 50)
        if isinstance(processed, dict):
            print(json.dumps(processed, ensure_ascii=False, indent=2))
        elif isinstance(processed, list):
            print(processed)
        else:
            print(processed)
    print("\n")

def compare_ruling(original, sample_num):
    """Ruling 전처리 비교 출력"""
    print_separator()
    print(f"샘플 {sample_num} - Ruling 컬럼 전처리 비교")
    print_separator()
    
    print("\n📄 원문 데이터:")
    print("-" * 100)
    print(json.dumps(original, ensure_ascii=False, indent=2))
    
    print("\n\n✨ 전처리된 데이터 (다양한 추출 방식):")
    print("-" * 100)
    
    extract_types = [
        ('text', '텍스트만 추출'),
        ('parse', '구조화된 Parse 정보'),
        ('imprisonment', '징역/금고 정보만'),
        ('fine', '벌금 정보만'),
        ('combined', '텍스트와 Parse 결합')
    ]
    
    for extract_type, desc in extract_types:
        processed = preprocess_ruling(original, extract_type)
        print(f"\n[{desc} ({extract_type})]")
        print("-" * 50)
        if isinstance(processed, dict):
            print(json.dumps(processed, ensure_ascii=False, indent=2))
        else:
            print(processed)
    print("\n")

def compare_reason(original, sample_num):
    """Reason 전처리 비교 출력"""
    print_separator()
    print(f"샘플 {sample_num} - Reason 컬럼 전처리 비교")
    print_separator()
    
    print("\n📄 원문 데이터:")
    print("-" * 100)
    print(original)
    print(f"\n[통계] 길이: {len(original)} 문자, 줄 수: {len(original.split(chr(10)))}줄")
    
    print("\n\n✨ 전처리된 데이터 (다양한 모드):")
    print("-" * 100)
    
    modes = [
        ('clean', '기본 정리 모드'),
        ('split_sections', '섹션별 분리 모드'),
        ('extract_key_info', '주요 정보 추출 모드'),
        ('minimal', '최소 정리 모드')
    ]
    
    for mode, desc in modes:
        processed = preprocess_reason(original, mode)
        print(f"\n[{desc} ({mode})]")
        print("-" * 50)
        if isinstance(processed, dict):
            print(f"[딕셔너리 형태 - {len(processed)}개 섹션]")
            for i, (key, value) in enumerate(list(processed.items())[:3]):  # 처음 3개만 표시
                print(f"\n  [{key}]")
                print(f"  {value[:150] + '...' if len(str(value)) > 150 else value}")
            if len(processed) > 3:
                print(f"\n  ... 외 {len(processed) - 3}개 섹션")
        else:
            print(processed[:500] + "..." if len(processed) > 500 else processed)
            print(f"\n[통계] 길이: {len(processed)} 문자")
    print("\n")

def detailed_comparison(idx, dataset):
    """한 샘플의 모든 컬럼을 상세하게 비교"""
    sample = dataset[idx]
    
    print_separator('=', 120)
    print(f"샘플 {idx} - 전체 컬럼 상세 비교")
    print_separator('=', 120)
    print()
    
    # 기본 정보
    print(f"📋 기본 정보:")
    print(f"  - ID: {sample['id']}")
    print(f"  - 사건 유형: {sample['casetype']}")
    print(f"  - 사건명: {sample['casename']}\n")
    
    # Facts 비교
    print_separator('-', 120)
    print("📄 FACTS 컬럼")
    print_separator('-', 120)
    original_facts = sample['facts']
    processed_facts = preprocess_facts(original_facts)
    print("\n[원문]")
    print(original_facts)
    print(f"\n[전처리 후]")
    print(processed_facts)
    print(f"\n변경: {len(original_facts)} → {len(processed_facts)} 문자 ({len(original_facts) - len(processed_facts):+d})\n")
    
    # Label 비교
    print_separator('-', 120)
    print("📄 LABEL 컬럼")
    print_separator('-', 120)
    original_label = sample['label']
    print("\n[원문]")
    print(json.dumps(original_label, ensure_ascii=False, indent=2))
    print("\n[전처리 후 - 텍스트]")
    print(preprocess_label(original_label, 'text'))
    print("\n[전처리 후 - 수치형]")
    print(preprocess_label(original_label, 'numeric'))
    print("\n[전처리 후 - 멀티클래스]")
    print(preprocess_label(original_label, 'multiclass'))
    print()
    
    # Ruling 비교
    print_separator('-', 120)
    print("📄 RULING 컬럼")
    print_separator('-', 120)
    original_ruling = sample['ruling']
    print("\n[원문]")
    print(json.dumps(original_ruling, ensure_ascii=False, indent=2))
    print("\n[전처리 후 - 텍스트만]")
    print(preprocess_ruling(original_ruling, 'text'))
    print("\n[전처리 후 - 징역 정보]")
    print(json.dumps(preprocess_ruling(original_ruling, 'imprisonment'), ensure_ascii=False, indent=2))
    print()
    
    # Reason 비교
    print_separator('-', 120)
    print("📄 REASON 컬럼")
    print_separator('-', 120)
    original_reason = sample['reason']
    print("\n[원문]")
    print(original_reason)
    print(f"\n[길이: {len(original_reason)} 문자]")
    print("\n[전처리 후 - Clean 모드]")
    processed_reason = preprocess_reason(original_reason, 'clean')
    print(processed_reason)
    print(f"\n[길이: {len(processed_reason)} 문자]")
    print("\n[전처리 후 - 주요 정보 추출]")
    key_info = preprocess_reason(original_reason, 'extract_key_info')
    print(json.dumps(key_info, ensure_ascii=False, indent=2))
    print()
    
    print_separator('=', 120)
    print()

if __name__ == '__main__':
    # 데이터셋 로드
    print("데이터셋 로드 중...")
    dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split='train')
    
    print(f"데이터셋 크기: {len(dataset)}")
    print(f"컬럼: {dataset.column_names}\n")
    
    # 비교할 샘플 인덱스
    sample_indices = [0, 1, 2]
    
    print("\n" + "="*120)
    print("전처리 비교 리포트 시작")
    print("="*120 + "\n")
    
    # 1. Facts 비교
    print("\n" + "#"*120)
    print("# 1. FACTS 컬럼 전처리 비교")
    print("#"*120 + "\n")
    for idx in sample_indices:
        sample = dataset[idx]
        original_facts = sample['facts']
        processed_facts = preprocess_facts(original_facts)
        compare_facts(original_facts, processed_facts, idx)
    
    # 2. Label 비교
    print("\n" + "#"*120)
    print("# 2. LABEL 컬럼 전처리 비교")
    print("#"*120 + "\n")
    for idx in sample_indices:
        sample = dataset[idx]
        original_label = sample['label']
        compare_label(original_label, idx)
    
    # 3. Ruling 비교
    print("\n" + "#"*120)
    print("# 3. RULING 컬럼 전처리 비교")
    print("#"*120 + "\n")
    for idx in sample_indices:
        sample = dataset[idx]
        original_ruling = sample['ruling']
        compare_ruling(original_ruling, idx)
    
    # 4. Reason 비교
    print("\n" + "#"*120)
    print("# 4. REASON 컬럼 전처리 비교")
    print("#"*120 + "\n")
    for idx in sample_indices:
        sample = dataset[idx]
        original_reason = sample['reason']
        compare_reason(original_reason, idx)
    
    # 5. 상세 비교 (첫 번째 샘플)
    print("\n" + "#"*120)
    print("# 5. 샘플 0 전체 상세 비교")
    print("#"*120 + "\n")
    detailed_comparison(0, dataset)
    
    print("\n" + "="*120)
    print("전처리 비교 리포트 완료")
    print("="*120)
