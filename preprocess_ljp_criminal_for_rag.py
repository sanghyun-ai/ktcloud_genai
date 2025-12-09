"""
ljp_criminal 데이터셋을 RAG용으로 전처리하여 Pinecone에 저장하는 스크립트
"""

import os
from datasets import load_dataset
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
import json
from tqdm import tqdm
from typing import List, Dict
import hashlib

class LJPPreprocessor:
    def __init__(self, 
                 embedding_model_name: str = "jhgan/ko-sroberta-multitask",
                 pinecone_api_key: str = None,
                 pinecone_index_name: str = "ljp-criminal-rag",
                 dimension: int = 768):
        """
        Args:
            embedding_model_name: 한국어 임베딩 모델 (기본값: ko-sroberta-multitask)
            pinecone_api_key: Pinecone API 키
            pinecone_index_name: Pinecone 인덱스 이름
            dimension: 임베딩 차원 수
        """
        self.embedding_model = SentenceTransformer(embedding_model_name)
        self.dimension = dimension
        
        # Pinecone 초기화
        if pinecone_api_key is None:
            pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key:
            raise ValueError("Pinecone API 키가 필요합니다. 환경변수 PINECONE_API_KEY를 설정하거나 인자로 전달하세요.")
        
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index_name = pinecone_index_name
        
    def create_index(self, metric: str = "cosine"):
        """Pinecone 인덱스 생성 (이미 존재하면 스킵)"""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        
        if self.index_name not in existing_indexes:
            print(f"인덱스 '{self.index_name}' 생성 중...")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=metric,
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            print(f"인덱스 '{self.index_name}' 생성 완료!")
        else:
            print(f"인덱스 '{self.index_name}'가 이미 존재합니다.")
        
        self.index = self.pc.Index(self.index_name)
        return self.index
    
    def create_chunks(self, case: Dict) -> List[Dict]:
        """
        판례 데이터를 RAG 검색에 적합한 청크로 분할
        
        전략:
        1. 전체 판례를 하나의 문서로 (사건 개요)
        2. 사실 관계만 별도 청크
        3. 판결 이유만 별도 청크
        4. 판결 내용만 별도 청크
        """
        chunks = []
        case_id = case['id']
        casename = case['casename']
        casetype = case['casetype']
        
        # 청크 1: 전체 판례 요약 (검색 우선순위 높음)
        full_text = f"""
사건명: {casename}
사건 유형: {casetype}

【사건 사실】
{case['facts']}

【판결 내용】
{case['ruling']['text']}

【판결 이유】
{case['reason']}
""".strip()
        
        chunks.append({
            'text': full_text,
            'metadata': {
                'chunk_type': 'full_case',
                'case_id': case_id,
                'casename': casename,
                'casetype': casetype,
                'priority': 'high'  # 전체 판례는 검색 우선순위 높음
            }
        })
        
        # 청크 2: 사실 관계만 (사건 상황 검색용)
        if case['facts']:
            chunks.append({
                'text': f"사건명: {casename}\n\n【사건 사실】\n{case['facts']}",
                'metadata': {
                    'chunk_type': 'facts',
                    'case_id': case_id,
                    'casename': casename,
                    'casetype': casetype,
                    'priority': 'medium'
                }
            })
        
        # 청크 3: 판결 이유만 (법리 검색용)
        if case['reason']:
            chunks.append({
                'text': f"사건명: {casename}\n\n【판결 이유】\n{case['reason']}",
                'metadata': {
                    'chunk_type': 'reason',
                    'case_id': case_id,
                    'casename': casename,
                    'casetype': casetype,
                    'priority': 'medium'
                }
            })
        
        # 청크 4: 판결 내용만 (형량 검색용)
        if case['ruling']['text']:
            ruling_text = case['ruling']['text']
            # 형량 정보 추가
            if 'parse' in case['ruling']:
                parse = case['ruling']['parse']
                if parse.get('imprisonment', {}).get('value', -1) >= 0:
                    imprisonment = parse['imprisonment']
                    ruling_text += f"\n[형량 정보] {imprisonment.get('type', '')} {imprisonment.get('value', 0)}{imprisonment.get('unit', '')}"
                if parse.get('fine', {}).get('value', -1) >= 0:
                    fine = parse['fine']
                    ruling_text += f"\n[벌금 정보] {fine.get('value', 0)}{fine.get('unit', '')}"
            
            chunks.append({
                'text': f"사건명: {casename}\n\n【판결 내용】\n{ruling_text}",
                'metadata': {
                    'chunk_type': 'ruling',
                    'case_id': case_id,
                    'casename': casename,
                    'casetype': casetype,
                    'priority': 'medium',
                    'imprisonment_lv': case['label'].get('imprisonment_with_labor_lv', 0),
                    'fine_lv': case['label'].get('fine_lv', 0)
                }
            })
        
        return chunks
    
    def generate_id(self, case_id: int, chunk_type: str, chunk_idx: int) -> str:
        """고유 ID 생성"""
        return f"case_{case_id}_{chunk_type}_{chunk_idx}"
    
    def process_and_upload(self, 
                          split: str = 'train',
                          batch_size: int = 100,
                          max_cases: int = None):
        """
        데이터셋을 처리하여 Pinecone에 업로드
        
        Args:
            split: 데이터셋 split ('train', 'valid', 'test', 'test2')
            batch_size: 배치 크기
            max_cases: 최대 처리할 사건 수 (None이면 전체)
        """
        print(f"\n{'='*60}")
        print(f"데이터셋 로드: {split} split")
        print(f"{'='*60}")
        
        # 데이터셋 로드
        dataset = load_dataset('lbox/lbox_open', 'ljp_criminal', split=split)
        
        if max_cases:
            dataset = dataset.select(range(min(max_cases, len(dataset))))
        
        print(f"총 {len(dataset):,}건의 판례를 처리합니다.")
        
        # 인덱스 생성
        self.create_index()
        
        # 배치 처리
        all_chunks = []
        total_chunks = 0
        
        print(f"\n{'='*60}")
        print("판례를 청크로 분할 중...")
        print(f"{'='*60}")
        
        for case in tqdm(dataset, desc="청크 생성"):
            chunks = self.create_chunks(case)
            for idx, chunk in enumerate(chunks):
                chunk_id = self.generate_id(case['id'], chunk['metadata']['chunk_type'], idx)
                all_chunks.append({
                    'id': chunk_id,
                    'text': chunk['text'],
                    'metadata': chunk['metadata']
                })
                total_chunks += 1
        
        print(f"\n총 {total_chunks:,}개의 청크가 생성되었습니다.")
        
        # 임베딩 생성 및 업로드
        print(f"\n{'='*60}")
        print("임베딩 생성 및 Pinecone 업로드 중...")
        print(f"{'='*60}")
        
        for i in tqdm(range(0, len(all_chunks), batch_size), desc="업로드 진행"):
            batch = all_chunks[i:i+batch_size]
            
            # 텍스트 추출
            texts = [chunk['text'] for chunk in batch]
            
            # 임베딩 생성
            embeddings = self.embedding_model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # Pinecone 형식으로 변환
            vectors = []
            for j, chunk in enumerate(batch):
                vectors.append({
                    'id': chunk['id'],
                    'values': embeddings[j].tolist(),
                    'metadata': chunk['metadata']
                })
            
            # 업로드
            self.index.upsert(vectors=vectors)
        
        print(f"\n{'='*60}")
        print("업로드 완료!")
        print(f"{'='*60}")
        print(f"인덱스: {self.index_name}")
        print(f"총 청크 수: {total_chunks:,}개")
        
        # 인덱스 통계 확인
        stats = self.index.describe_index_stats()
        print(f"\n인덱스 통계:")
        print(f"  총 벡터 수: {stats.total_vector_count:,}개")
        print(f"  차원: {stats.dimension}차원")
    
    def search_example(self, query: str, top_k: int = 5):
        """검색 예제"""
        print(f"\n{'='*60}")
        print(f"검색 예제: '{query}'")
        print(f"{'='*60}")
        
        # 쿼리 임베딩
        query_embedding = self.embedding_model.encode(query, convert_to_numpy=True)
        
        # 검색
        results = self.index.query(
            vector=query_embedding.tolist(),
            top_k=top_k,
            include_metadata=True
        )
        
        print(f"\n상위 {top_k}개 결과:\n")
        for i, match in enumerate(results.matches, 1):
            print(f"{i}. [유사도: {match.score:.4f}]")
            print(f"   사건명: {match.metadata.get('casename', 'N/A')}")
            print(f"   청크 타입: {match.metadata.get('chunk_type', 'N/A')}")
            print(f"   사건 ID: {match.metadata.get('case_id', 'N/A')}")
            print(f"   텍스트 미리보기: {match.metadata.get('text', '')[:200]}...")
            print()


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ljp_criminal 데이터셋을 RAG용으로 전처리하여 Pinecone에 저장')
    parser.add_argument('--split', type=str, default='train', 
                       choices=['train', 'valid', 'test', 'test2'],
                       help='처리할 데이터셋 split')
    parser.add_argument('--max-cases', type=int, default=None,
                       help='최대 처리할 사건 수 (테스트용)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='배치 크기')
    parser.add_argument('--embedding-model', type=str, 
                       default='jhgan/ko-sroberta-multitask',
                       help='임베딩 모델 이름')
    parser.add_argument('--index-name', type=str, default='ljp-criminal-rag',
                       help='Pinecone 인덱스 이름')
    parser.add_argument('--test-search', type=str, default=None,
                       help='검색 테스트 쿼리 (예: "강제추행 징역")')
    
    args = parser.parse_args()
    
    # 전처리기 생성
    preprocessor = LJPPreprocessor(
        embedding_model_name=args.embedding_model,
        pinecone_index_name=args.index_name
    )
    
    # 데이터 처리 및 업로드
    preprocessor.process_and_upload(
        split=args.split,
        batch_size=args.batch_size,
        max_cases=args.max_cases
    )
    
    # 검색 테스트
    if args.test_search:
        preprocessor.search_example(args.test_search)
    else:
        # 기본 검색 예제
        preprocessor.search_example("강제추행 징역")


if __name__ == "__main__":
    main()
