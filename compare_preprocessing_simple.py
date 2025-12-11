"""
간결한 버전의 전처리 비교 스크립트
한 샘플에 대해 모든 컬럼을 나란히 비교
"""

from datasets import load_dataset
import json
import re
from typing import Dict, Any

# 전처리 함수들 (간단 버전)
def preprocess_facts(facts: str) -> str:
    text = facts.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def preprocess_label(label: Dict[str, Any], format: str = 'text') -> Any:
    if format == 'text':
        return label['text']
    elif format == 'numeric':
        return [label['fine_lv'], label['imprisonment_with_labor_lv'], label['imprisonment_without_labor_lv']]
    return label

def preprocess_ruling(ruling: Dict[str, Any], extract: str = 'text') -> Any:
    if extract == 'text':
        text = ruling['text']
        text = re.sub(r'\n+', '\n', text)
        return text.strip()
    return ruling

def preprocess_reason(reason: str, mode: str = 'clean') -> str:
    if mode == 'clean':
        text = reason.replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()
    return reason

def print_comparison_table(sample_idx, dataset):
    """표 형식으로 비교 출력"""
    sample = dataset[sample_idx]
    
    print("\n" + "="*120)
    print(f"샘플 {sample_idx} 전처리 비교: {sample['casename']}")
    print("="*120)
    
    # Facts
    print("\n【FACTS 컬럼】")
    print("-" * 120)
    original_facts = sample['facts']
    processed_facts = preprocess_facts(original_facts)
    print(f"원문 ({len(original_facts)}자):")
    print(f"  {original_facts}")
    print(f"\n전처리 후 ({len(processed_facts)}자):")
    print(f"  {processed_facts}")
    if original_facts != processed_facts:
        print(f"  ✓ 변경: 줄바꿈 {original_facts.count(chr(10))}개 제거")
    
    # Label
    print("\n【LABEL 컬럼】")
    print("-" * 120)
    original_label = sample['label']
    print(f"원문:")
    print(f"  {json.dumps(original_label, ensure_ascii=False, indent=2)}")
    print(f"\n전처리 후 (텍스트):")
    print(f"  {preprocess_label(original_label, 'text')}")
    print(f"\n전처리 후 (수치형):")
    print(f"  {preprocess_label(original_label, 'numeric')}")
    
    # Ruling
    print("\n【RULING 컬럼】")
    print("-" * 120)
    original_ruling = sample['ruling']
    print(f"원문:")
    print(f"  {json.dumps(original_ruling, ensure_ascii=False, indent=2)}")
    print(f"\n전처리 후 (텍스트만):")
    ruling_text = preprocess_ruling(original_ruling, 'text')
    print(f"  {ruling_text}")
    
    # Reason
    print("\n【REASON 컬럼】")
    print("-" * 120)
    original_reason = sample['reason']
    processed_reason = preprocess_reason(original_reason, 'clean')
    print(f"원문 ({len(original_reason)}자):")
    print(f"  {original_reason[:300]}..." if len(original_reason) > 300 else f"  {original_reason}")
    print(f"\n전처리 후 ({len(processed_reason)}자):")
    print(f"  {processed_reason[:300]}..." if len(processed_reason) > 300 else f"  {processed_reason}")
    
    print("\n" + "="*120 + "\n")

if __name__ == '__main__':
    print("데이터셋 로드 중...")
    dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split='train')
    
    # 여러 샘플 비교
    for idx in [0, 1, 2]:
        print_comparison_table(idx, dataset)
