"""
법정공방 시뮬레이션용 전처리 비교 스크립트

원문 데이터와 전처리된 데이터를 나란히 비교하여 출력합니다.
"""

from datasets import load_dataset
import json
import re
from typing import Dict, Any

# 전처리 함수들 (시뮬레이션용)
def preprocess_facts_for_agent(facts: str) -> str:
    text = facts.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def preprocess_label_for_comparison(label: Dict[str, Any]) -> Dict[str, Any]:
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

def preprocess_ruling_for_feedback(ruling: Dict[str, Any]) -> Dict[str, Any]:
    text = ruling.get('text', '')
    parse = ruling.get('parse', {})
    imprisonment = parse.get('imprisonment', {})
    fine = parse.get('fine', {})
    
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

def preprocess_reason_for_explanation(reason: str) -> Dict[str, str]:
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

def print_comparison_for_simulation(sample_idx, dataset):
    """시뮬레이션용 전처리 비교 출력"""
    sample = dataset[sample_idx]
    
    print("\n" + "="*120)
    print(f"샘플 {sample_idx} 전처리 비교: {sample['casename']} (법정공방 시뮬레이션용)")
    print("="*120)
    
    # 1. Facts - 에이전트 전달용
    print("\n【1. FACTS 컬럼 - 에이전트 전달용】")
    print("-" * 120)
    original_facts = sample['facts']
    processed_facts = preprocess_facts_for_agent(original_facts)
    
    print("📄 원문 데이터:")
    print(f"  {original_facts}")
    print(f"  [길이: {len(original_facts)}자, 줄바꿈: {original_facts.count(chr(10))}개]")
    
    print("\n✨ 전처리된 데이터 (에이전트에게 전달):")
    print(f"  {processed_facts}")
    print(f"  [길이: {len(processed_facts)}자, 줄바꿈: {processed_facts.count(chr(10))}개]")
    
    if original_facts != processed_facts:
        print(f"\n  ✓ 변경사항: 줄바꿈 제거, 공백 정리")
    
    # 2. Label - 비교용
    print("\n\n【2. LABEL 컬럼 - 형량 비교용】")
    print("-" * 120)
    original_label = sample['label']
    processed_label = preprocess_label_for_comparison(original_label)
    
    print("📄 원문 데이터:")
    print(f"  {json.dumps(original_label, ensure_ascii=False, indent=2)}")
    
    print("\n✨ 전처리된 데이터 (유저 선택 형량과 비교하기 위함):")
    print(f"  {json.dumps(processed_label, ensure_ascii=False, indent=2)}")
    
    print("\n📊 비교에 사용되는 주요 정보:")
    print(f"  - 형량 텍스트: {processed_label['text']}")
    print(f"  - 주요 형벌 종류: {processed_label['main_type']}")
    print(f"  - 주요 형벌 레벨: {processed_label['main_level']}")
    print(f"  - 수치 벡터: {processed_label['numeric_vector']}")
    print(f"  - 벌금 여부: {processed_label['is_fine']}")
    print(f"  - 징역 여부: {processed_label['is_imprisonment']}")
    
    # 3. Ruling - 피드백용
    print("\n\n【3. RULING 컬럼 - 피드백용】")
    print("-" * 120)
    original_ruling = sample['ruling']
    processed_ruling = preprocess_ruling_for_feedback(original_ruling)
    
    print("📄 원문 데이터:")
    print(f"  {json.dumps(original_ruling, ensure_ascii=False, indent=2)}")
    
    print("\n✨ 전처리된 데이터 (유저에게 피드백 제공용):")
    print(f"  {json.dumps(processed_ruling, ensure_ascii=False, indent=2)}")
    
    print(f"\n📊 요약 정보: {processed_ruling['summary']}")
    
    # 4. Reason - 설명용
    print("\n\n【4. REASON 컬럼 - 설명용】")
    print("-" * 120)
    original_reason = sample['reason']
    processed_reason = preprocess_reason_for_explanation(original_reason)
    
    print("📄 원문 데이터:")
    print(f"  {original_reason[:300]}..." if len(original_reason) > 300 else f"  {original_reason}")
    print(f"  [길이: {len(original_reason)}자]")
    
    print(f"\n✨ 전처리된 데이터 (섹션별 분리 - {len(processed_reason)}개 섹션):")
    for i, (section, content) in enumerate(list(processed_reason.items())[:5]):
        print(f"\n  [{section}]")
        print(f"  {content[:200]}..." if len(content) > 200 else f"  {content}")
    if len(processed_reason) > 5:
        print(f"\n  ... 외 {len(processed_reason) - 5}개 섹션")
    
    # 5. 사용 시나리오 예시
    print("\n\n【5. 사용 시나리오】")
    print("-" * 120)
    print("1️⃣ 에이전트에게 전달:")
    print(f"   → Facts: {processed_facts[:80]}...")
    print("\n2️⃣ 유저가 형량 선택 후 비교:")
    print(f"   → 실제 형량: {processed_label['text']} (타입: {processed_label['main_type']}, 레벨: {processed_label['main_level']})")
    print(f"   → 유저 선택 형량과 비교하여 정확도 계산 및 피드백 제공")
    print("\n3️⃣ 피드백 제공:")
    print(f"   → Ruling 요약: {processed_ruling['summary']}")
    print(f"   → Reason 섹션별 설명 제공")
    
    print("\n" + "="*120 + "\n")

if __name__ == '__main__':
    print("데이터셋 로드 중...")
    dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split='train')
    
    # 여러 샘플 비교
    for idx in [0, 1, 2]:
        print_comparison_for_simulation(idx, dataset)
