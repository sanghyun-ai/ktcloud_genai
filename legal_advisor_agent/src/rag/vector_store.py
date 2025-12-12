"""PostgreSQL Vector Store with pgvector"""
import os
from typing import List, Dict, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from sentence_transformers import SentenceTransformer


class PostgresVectorStore:
    """PostgreSQL + pgvector를 사용한 벡터 저장소"""

    def __init__(
        self,
        embedding_model: str = "jhgan/ko-sroberta-multitask",
        connection_params: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            embedding_model: 임베딩 모델 이름
            connection_params: PostgreSQL 연결 파라미터
        """
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()

        # DB 연결 설정
        if connection_params is None:
            connection_params = {
                "host": os.getenv("POSTGRES_HOST", "localhost"),
                "port": os.getenv("POSTGRES_PORT", 5432),
                "database": os.getenv("POSTGRES_DB", "legal_db"),
                "user": os.getenv("POSTGRES_USER", "postgres"),
                "password": os.getenv("POSTGRES_PASSWORD", ""),
            }

        self.connection_params = connection_params
        self._init_database()

    def _get_connection(self):
        """DB 연결 생성"""
        return psycopg2.connect(**self.connection_params)

    def _init_database(self):
        """데이터베이스 초기화 (테이블 및 인덱스 생성)"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # pgvector 확장 설치
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # 테이블 생성
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS legal_documents (
                        id TEXT PRIMARY KEY,
                        doc_type TEXT NOT NULL,
                        title TEXT,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        embedding vector({self.embedding_dim}),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 인덱스 생성
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_doc_type 
                    ON legal_documents(doc_type);
                """)

                # 벡터 검색 인덱스 (HNSW 또는 IVFFlat)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_embedding_cosine 
                    ON legal_documents 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                """)

                conn.commit()

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> int:
        """
        문서 추가

        Args:
            documents: 문서 리스트
                [{
                    "id": "doc_001",
                    "doc_type": "precedent",
                    "title": "대법원 2020도1234",
                    "content": "판결 내용...",
                    "metadata": {...}
                }]
            batch_size: 배치 크기

        Returns:
            추가된 문서 수
        """
        import json

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                count = 0
                for i in range(0, len(documents), batch_size):
                    batch = documents[i:i + batch_size]

                    # 임베딩 생성
                    contents = [doc["content"] for doc in batch]
                    embeddings = self.embedding_model.encode(
                        contents,
                        show_progress_bar=True,
                        normalize_embeddings=True
                    )

                    # 데이터 준비
                    values = [
                        (
                            doc["id"],
                            doc["doc_type"],
                            doc.get("title", ""),
                            doc["content"],
                            json.dumps(doc.get("metadata", {}), ensure_ascii=False),
                            embedding.tolist()
                        )
                        for doc, embedding in zip(batch, embeddings)
                    ]

                    # 삽입 (중복 시 업데이트)
                    execute_values(
                        cur,
                        """
                        INSERT INTO legal_documents 
                        (id, doc_type, title, content, metadata, embedding)
                        VALUES %s
                        ON CONFLICT (id) DO UPDATE SET
                            doc_type = EXCLUDED.doc_type,
                            title = EXCLUDED.title,
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            embedding = EXCLUDED.embedding
                        """,
                        values
                    )

                    count += len(batch)
                    conn.commit()

        return count

    def search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        벡터 유사도 검색

        Args:
            query: 검색 쿼리
            doc_type: 문서 타입 필터 ('precedent', 'statute', 등)
            filters: 추가 필터 조건
            top_k: 반환할 문서 수

        Returns:
            검색 결과 리스트
        """
        # 쿼리 임베딩
        query_embedding = self.embedding_model.encode(
            query,
            normalize_embeddings=True
        )

        # SQL 쿼리 구성
        where_clauses = []
        params = [query_embedding.tolist(), top_k]

        if doc_type:
            where_clauses.append("doc_type = %s")
            params.insert(1, doc_type)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        sql = f"""
            SELECT 
                id, doc_type, title, content, metadata,
                1 - (embedding <=> %s::vector) AS similarity
            FROM legal_documents
            {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """

        # 파라미터 순서 조정
        if doc_type:
            search_params = [query_embedding.tolist(), doc_type, query_embedding.tolist(), top_k]
        else:
            search_params = [query_embedding.tolist(), query_embedding.tolist(), top_k]

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, search_params)
                results = cur.fetchall()

        # 결과 포맷팅
        return [
            {
                "id": row[0],
                "doc_type": row[1],
                "title": row[2],
                "content": row[3],
                "metadata": row[4],
                "score": float(row[5])
            }
            for row in results
        ]

    def delete_by_doc_type(self, doc_type: str) -> int:
        """특정 타입의 모든 문서 삭제"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM legal_documents WHERE doc_type = %s",
                    (doc_type,)
                )
                deleted = cur.rowcount
                conn.commit()
        return deleted
