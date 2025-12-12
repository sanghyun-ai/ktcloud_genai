"""
데이터 로딩 예제 - lbox 데이터셋을 벡터 DB에 저장

이 스크립트는 Week 1에서 준비한 데이터를 벡터 DB에 로드합니다.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import load_dataset
from tqdm import tqdm
from src.rag.vector_store import PostgresVectorStore


def load_lbox_criminal_cases(split: str = "train", max_samples: int = 1000):
    """
    lbox 형사 판례 데이터 로드
    
    Args:
        split: 'train', 'valid', 'test'
        max_samples: 최대 로드 샘플 수
    """
    print(f"🔄 lbox 데이터셋 로드 중 (split={split})...")
    
    # 데이터셋 로드
    dataset = load_dataset(
        "lbox/lbox_open",
        "ljp_criminal",
        split=split
    )
    
    print(f"✅ 총 {len(dataset)}개 데이터 로드 완료")
    
    # 벡터 저장소 초기화
    vector_store = PostgresVectorStore()
    
    # 문서 형식으로 변환
    documents = []
    
    for idx, sample in enumerate(tqdm(dataset, desc="데이터 변환")):
        if idx >= max_samples:
            break
        
        # 문서 ID 생성
        doc_id = sample.get("id", f"case_{idx}")
        
        # reason 필드를 content로 사용
        content = sample.get("reason", "")
        
        if not content or len(content) < 10:
            continue
        
        # 메타데이터 구성
        metadata = {
            "casetype": sample.get("casetype", ""),
            "casename": sample.get("casename", ""),
            "label": sample.get("label", ""),
            "case_type": "형사",  # 이 데이터셋은 형사 사건
        }
        
        # facts가 있으면 메타데이터에 추가
        if sample.get("facts"):
            metadata["facts"] = sample["facts"][:500]  # 요약만
        
        documents.append({
            "id": doc_id,
            "doc_type": "precedent",  # 판례
            "title": sample.get("casename", f"사건 {doc_id}"),
            "content": content,
            "metadata": metadata
        })
    
    print(f"\n📊 변환 완료: {len(documents)}개 문서")
    
    # 벡터 DB에 저장
    print("\n💾 벡터 DB에 저장 중...")
    count = vector_store.add_documents(documents, batch_size=100)
    
    print(f"✅ {count}개 문서 저장 완료!\n")
    
    return vector_store


def build_bm25_index(vector_store: PostgresVectorStore):
    """
    BM25 인덱스 구축
    
    하이브리드 검색을 위해 필요
    """
    print("\n🔨 BM25 인덱스 구축 중...")
    
    # DB에서 모든 문서 조회
    with vector_store._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, doc_type, title, content, metadata
                FROM legal_documents
                WHERE doc_type = 'precedent'
            """)
            rows = cur.fetchall()
    
    documents = [
        {
            "id": row[0],
            "doc_type": row[1],
            "title": row[2],
            "content": row[3],
            "metadata": row[4]
        }
        for row in rows
    ]
    
    print(f"📚 {len(documents)}개 문서 로드 완료")
    
    # BM25 인덱스 구축 (HybridSearchEngine에서)
    from src.rag.hybrid_search import HybridSearchEngine
    
    hybrid_search = HybridSearchEngine(vector_store)
    hybrid_search.build_bm25_index(documents)
    
    print("✅ BM25 인덱스 구축 완료!\n")
    
    return hybrid_search


if __name__ == "__main__":
    print("=" * 80)
    print("lbox 형사 판례 데이터 로딩")
    print("=" * 80)
    print()
    
    # PostgreSQL 연결 체크
    if not os.getenv("POSTGRES_HOST"):
        print("⚠️ PostgreSQL 연결 정보가 필요합니다.")
        print("   .env 파일을 설정하세요:")
        print()
        print("   POSTGRES_HOST=localhost")
        print("   POSTGRES_PORT=5432")
        print("   POSTGRES_DB=legal_db")
        print("   POSTGRES_USER=postgres")
        print("   POSTGRES_PASSWORD=your_password")
        print()
        sys.exit(1)
    
    try:
        # 1. 데이터 로드 및 저장
        vector_store = load_lbox_criminal_cases(
            split="train",
            max_samples=500  # 테스트용으로 500개만
        )
        
        # 2. BM25 인덱스 구축
        hybrid_search = build_bm25_index(vector_store)
        
        print("=" * 80)
        print("✅ 모든 작업 완료!")
        print("=" * 80)
        print()
        print("이제 examples/01_basic_usage.py 를 실행할 수 있습니다.")
        
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
