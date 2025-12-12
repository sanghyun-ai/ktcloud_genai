# 빠른 시작 가이드 🚀

이 문서는 **5분 안에** Legal Advisor Agent를 실행하는 방법을 안내합니다.

---

## ✅ 1단계: 필수 요구사항 확인

- Python 3.9 이상
- PostgreSQL 12 이상 (또는 Docker)
- 8GB RAM 이상 (권장)

---

## ✅ 2단계: PostgreSQL 시작 (Docker 사용)

```bash
docker run -d \
  --name legal-postgres \
  -e POSTGRES_PASSWORD=mysecret \
  -e POSTGRES_DB=legal_db \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

---

## ✅ 3단계: 패키지 설치

```bash
cd legal_advisor_agent
pip install -r requirements.txt
```

---

## ✅ 4단계: 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일 편집:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=legal_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=mysecret

OPENAI_API_KEY=sk-your-key-here  # 선택사항
```

---

## ✅ 5단계: 데이터 로드

```bash
python examples/02_data_loading.py
```

출력 예시:
```
🔄 lbox 데이터셋 로드 중...
✅ 총 8400개 데이터 로드 완료
💾 벡터 DB에 저장 중...
✅ 500개 문서 저장 완료!
```

---

## ✅ 6단계: 테스트 실행

```bash
python examples/01_basic_usage.py
```

출력 예시:
```
================================================================================
예제 1: 기본 법률 자문 요청
================================================================================

============================================================
🔍 법률 자문 요청 접수
   요청자: judge
   쿼리: 살인죄 양형 기준
============================================================

📚 1단계: 관련 법령 조회...
   ✓ 관련 법령 5건 발견
⚖️  2단계: 양형기준 조회...
   ✓ 양형기준 발견: 형법 제250조
🔎 3단계: 유사 판례 검색 (RAG)...
   ⚙️  쿼리 정제 중...
   ✓ 2개의 정제된 쿼리 생성
   🔍 하이브리드 검색 (BM25 + Vector)...
   ✓ 15개의 후보 판례 발견
   🎯 Re-ranking 수행 중...
   ✓ 최종 3개 판례 선정

📄 자문 결과:

## 법률 자문 의견서

**사건번호**: 2024고합1234
**요청자**: JUDGE
**쿼리**: 살인죄 양형 기준

---

### 📚 관련 법령

**법령명**: 형법
...
```

---

## ✅ 7단계: API 서버 시작 (선택사항)

```bash
python examples/03_fastapi_server.py
```

브라우저에서 확인:
- API 문서: http://localhost:8000/docs
- Health Check: http://localhost:8000/

**API 호출 예시**:

```bash
curl -X POST "http://localhost:8000/api/advisory/search" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "judge",
    "case_id": "2024고합1234",
    "query": "살인죄 양형 기준",
    "case_type": "형사",
    "top_k": 5
  }'
```

---

## 🎉 완료!

이제 법률 자문 에이전트가 실행 중입니다!

### 다음 단계:
- [전체 README 읽기](README.md)
- 더 많은 예제 확인 (`examples/` 폴더)
- 커스터마이징 (`.env` 파일 수정)

### 문제 해결:

**Q: PostgreSQL 연결 실패**
```bash
# Docker 컨테이너 상태 확인
docker ps -a | grep legal-postgres

# 로그 확인
docker logs legal-postgres
```

**Q: 임베딩 모델 다운로드 느림**
- 처음 실행 시 모델 다운로드에 시간이 걸립니다 (약 1-2분)
- 캐시되므로 이후 실행은 빠릅니다

**Q: 메모리 부족**
- `batch_size`를 줄이세요 (`02_data_loading.py`에서 100 → 50)
- 로딩하는 샘플 수를 줄이세요 (`max_samples=500` → `200`)

---

더 자세한 내용은 [README.md](README.md)를 참고하세요!
