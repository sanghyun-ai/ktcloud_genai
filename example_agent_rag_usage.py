"""
에이전트에서 RAG를 활용하는 예제
"""

from rag_search_utility import LJPRAGSearch
from typing import List


class DefenseAttorneyAgent:
    """변호사 에이전트 - RAG를 활용한 변호 전략 수립"""
    
    def __init__(self):
        self.rag_search = LJPRAGSearch()
        self.name = "변호사 에이전트"
    
    def find_favorable_precedents(self, case_facts: str, casename: str) -> List:
        """유리한 판례 검색 (형량이 낮거나 무죄 판결)"""
        # 사건 사실 기반 검색
        results = self.rag_search.search(
            query=f"{case_facts} {casename}",
            top_k=10,
            filter_dict={'casename': casename}
        )
        
        # 유리한 판례 선별 (형량 수준이 낮은 것)
        favorable = []
        for result in results:
            imprisonment_lv = result.metadata.get('imprisonment_lv', 10)
            if imprisonment_lv <= 2:  # 형량이 낮은 경우
                favorable.append(result)
        
        return favorable[:5]  # 상위 5개만
    
    def build_defense_argument(self, case_facts: str, casename: str) -> str:
        """변호 논거 구성"""
        print(f"\n[{self.name}] 판례 검색 중...")
        
        # 유리한 판례 검색
        precedents = self.find_favorable_precedents(case_facts, casename)
        
        # 판결 이유에서 감경 사유 검색
        mitigation_factors = self.rag_search.search(
            query=f"{case_facts} 감경 합의",
            top_k=3,
            filter_dict={'chunk_type': 'reason'}
        )
        
        argument = f"""
【변호 논거】

1. 유사 판례 분석:
"""
        for i, prec in enumerate(precedents[:3], 1):
            argument += f"""
   판례 {i}:
   - 사건명: {prec.casename}
   - 형량 수준: {prec.metadata.get('imprisonment_lv', 'N/A')}
   - 판결 요지: {prec.text[:200]}...
"""
        
        argument += f"""
2. 감경 사유:
"""
        for i, factor in enumerate(mitigation_factors[:2], 1):
            argument += f"""
   사유 {i}: {factor.text[:150]}...
"""
        
        return argument


class ProsecutorAgent:
    """검사 에이전트 - RAG를 활용한 기소 전략 수립"""
    
    def __init__(self):
        self.rag_search = LJPRAGSearch()
        self.name = "검사 에이전트"
    
    def find_similar_cases(self, case_facts: str, casename: str) -> List:
        """유사 사건의 판례 검색"""
        results = self.rag_search.search_by_case_type(
            query=case_facts,
            casename=casename,
            top_k=5
        )
        return results
    
    def analyze_sentencing_pattern(self, casename: str) -> dict:
        """형량 패턴 분석"""
        results = self.rag_search.search(
            query=f"{casename} 형량",
            top_k=10,
            filter_dict={'chunk_type': 'ruling', 'casename': casename}
        )
        
        # 형량 수준 분포 계산
        imprisonment_levels = [
            r.metadata.get('imprisonment_lv', 0) 
            for r in results
        ]
        
        avg_level = sum(imprisonment_levels) / len(imprisonment_levels) if imprisonment_levels else 0
        
        return {
            'average_level': avg_level,
            'cases': results[:5]
        }
    
    def build_prosecution_argument(self, case_facts: str, casename: str) -> str:
        """기소 논거 구성"""
        print(f"\n[{self.name}] 판례 검색 중...")
        
        # 유사 사건 검색
        similar_cases = self.find_similar_cases(case_facts, casename)
        
        # 형량 패턴 분석
        sentencing = self.analyze_sentencing_pattern(casename)
        
        argument = f"""
【기소 논거】

1. 유사 사건 판례:
"""
        for i, case in enumerate(similar_cases[:3], 1):
            argument += f"""
   사건 {i}:
   - 형량 수준: {case.metadata.get('imprisonment_lv', 'N/A')}
   - 판결 요지: {case.text[:200]}...
"""
        
        argument += f"""
2. 형량 패턴 분석:
   - 평균 형량 수준: {sentencing['average_level']:.1f}
   - 참고 판례 수: {len(sentencing['cases'])}건
"""
        
        return argument


class JudgeAgent:
    """판사 에이전트 - RAG를 활용한 판결 연구"""
    
    def __init__(self):
        self.rag_search = LJPRAGSearch()
        self.name = "판사 에이전트"
    
    def research_comprehensive_precedents(self, case_facts: str, casename: str) -> dict:
        """종합적인 판례 연구"""
        # 전체 판례 검색
        full_cases = self.rag_search.search_high_priority(
            query=case_facts,
            top_k=10
        )
        
        # 판결 이유 검색
        legal_reasons = self.rag_search.search(
            query=case_facts,
            top_k=5,
            filter_dict={'chunk_type': 'reason', 'casename': casename}
        )
        
        # 형량 정보 검색
        sentencing_info = self.rag_search.search(
            query=f"{casename} 형량",
            top_k=5,
            filter_dict={'chunk_type': 'ruling', 'casename': casename}
        )
        
        return {
            'full_cases': full_cases,
            'legal_reasons': legal_reasons,
            'sentencing': sentencing_info
        }
    
    def make_judgment(self, case_facts: str, casename: str) -> str:
        """판결 작성"""
        print(f"\n[{self.name}] 판례 연구 중...")
        
        research = self.research_comprehensive_precedents(case_facts, casename)
        
        # 가장 유사한 판례
        most_similar = research['full_cases'][0] if research['full_cases'] else None
        
        judgment = f"""
【판결 근거】

1. 참고 판례:
"""
        if most_similar:
            judgment += f"""
   가장 유사한 판례:
   - 사건명: {most_similar.casename}
   - 유사도: {most_similar.score:.4f}
   - 판결 요지: {most_similar.text[:300]}...
"""
        
        judgment += f"""
2. 법리 검토:
"""
        for i, reason in enumerate(research['legal_reasons'][:3], 1):
            judgment += f"""
   법리 {i}: {reason.text[:200]}...
"""
        
        judgment += f"""
3. 형량 참고:
"""
        for i, sent in enumerate(research['sentencing'][:3], 1):
            judgment += f"""
   참고 {i}: 형량 수준 {sent.metadata.get('imprisonment_lv', 'N/A')}
   {sent.text[:150]}...
"""
        
        return judgment


def simulate_court_session(case_facts: str, casename: str):
    """모의법정 시뮬레이션"""
    print("=" * 60)
    print("모의법정 시뮬레이션")
    print("=" * 60)
    print(f"\n사건명: {casename}")
    print(f"\n사건 사실:\n{case_facts[:300]}...")
    
    # 에이전트 초기화
    defense = DefenseAttorneyAgent()
    prosecutor = ProsecutorAgent()
    judge = JudgeAgent()
    
    # 변호사 변론
    print("\n" + "=" * 60)
    print("변호사 변론")
    print("=" * 60)
    defense_arg = defense.build_defense_argument(case_facts, casename)
    print(defense_arg)
    
    # 검사 공소
    print("\n" + "=" * 60)
    print("검사 공소")
    print("=" * 60)
    prosecution_arg = prosecutor.build_prosecution_argument(case_facts, casename)
    print(prosecution_arg)
    
    # 판사 판결
    print("\n" + "=" * 60)
    print("판사 판결")
    print("=" * 60)
    judgment = judge.make_judgment(case_facts, casename)
    print(judgment)


if __name__ == "__main__":
    # 예제 사건
    example_case = {
        'casename': '강제추행',
        'facts': """
        피고인은 2020. 9. 25. 23:45경 포항시 남구 B에 있는 피해자 C(여, 62세) 운영의 D에서 
        피해자와 함께 술을 마신 후 결제를 하고 나왔고, 피해자가 피고인을 배웅하자 갑자기 
        피해자의 양 손목을 잡고 포항시 남구 E에 있는 F 출입구까지 약 20m 가량 끌고 간 뒤, 
        피해자를 강제로 끌어안고 입을 맞추며 손으로 피해자의 가슴을 수회 만졌다.
        """
    }
    
    simulate_court_session(
        case_facts=example_case['facts'],
        casename=example_case['casename']
    )
