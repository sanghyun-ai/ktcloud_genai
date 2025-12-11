"""
전체 데이터셋을 구조화하고 JSON 파일로 저장하는 스크립트
"""

from datasets import load_dataset
from structure_reason import structure_dataset
import json
from tqdm import tqdm
from collections import Counter

def main():
    print("="*80)
    print("LJP Criminal Dataset - Reason 구조화")
    print("="*80)
    
    # 데이터셋 로드
    print("\n1. 데이터셋 로딩 중...")
    dataset = load_dataset("lbox/lbox_open", "ljp_criminal", split="train", streaming=False)
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
    print("\n5. JSONL 파일로 저장 중...")
    output_file = 'ljp_criminal_reason_structured.jsonl'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for example in tqdm(structured_dataset, desc="   저장 중"):
            output_data = {
                'id': example['id'],
                'casetype': example['casetype'],
                'casename': example['casename'],
                'label': example['label'],
                'reason_original': example['reason'],  # 원문도 포함
                'reason_structured': {
                    'case_id': example['reason_structured']['case_id'],
                    'pattern_type': example['reason_structured']['pattern_type'],
                    'sentencing_reason': example['reason_structured']['sentencing_reason'],
                    'personal_information': example['reason_structured']['personal_information']
                }
            }
            
            f.write(json.dumps(output_data, ensure_ascii=False) + '\n')
    
    print(f"   ✓ 저장 완료: {output_file}")
    
    # 샘플 출력
    print("\n6. 샘플 데이터 (첫 3개):")
    print("="*80)
    
    with open(output_file, 'r', encoding='utf-8') as f:
        for i in range(3):
            line = f.readline()
            if not line:
                break
            data = json.loads(line)
            
            # raw_text와 reason_original 제외하고 출력
            output = {
                'id': data['id'],
                'pattern_type': data['reason_structured']['pattern_type'],
                'sentencing_reason': data['reason_structured']['sentencing_reason'],
                'personal_information': data['reason_structured']['personal_information']
            }
            
            print(f"\n케이스 ID: {data['id']}")
            print(f"패턴: {data['reason_structured']['pattern_type']}")
            print(json.dumps(output, ensure_ascii=False, indent=2))
            if i < 2:
                print("-"*80)
    
    print("\n" + "="*80)
    print("✅ 모든 작업 완료!")
    print("="*80)


if __name__ == '__main__':
    main()
