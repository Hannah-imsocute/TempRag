# 학교 규정 GPT 실행 가이드

[서비스 흐름과 저장소 구조](../README.md)를 먼저 확인할 수 있습니다.

## 실행하기

### 1. 기존 서비스 확인

`rag-project/`에서 아래 명령을 실행합니다. Compose는 `rag-app`을 빌드하고 외부 Docker 네트워크 `db-connect`에 연결합니다.

| 컨테이너 | 연결 | 준비 사항 |
| --- | --- | --- |
| `postgre` | `postgre:5432` | PostgreSQL에 `rag` 데이터베이스와 `admin` 계정 준비 |
| `weaviate` | HTTP `weaviate:8080`, gRPC `weaviate:50051` | 두 포트로 앱 컨테이너에서 접속 가능해야 함 |
| `ollama` | `http://ollama:11434` | 임베딩과 답변 생성 모델 준비 |

```bash
cd rag-project
docker network inspect db-connect
docker exec ollama ollama list
docker exec ollama ollama pull qwen3-embedding:8b
docker exec ollama ollama pull exaone3.5:7.8b
```

### 2. 환경 변수 설정

`rag-project/.env`를 만들고 환경에 맞는 값을 지정합니다.

| 변수 | 설정 |
| --- | --- |
| `POSTGRES_PASSWORD` | 기존 PostgreSQL `admin` 계정의 비밀번호. 필수. |
| `ADMIN_PASSWORD` | 웹 관리자 계정을 처음 만들 때 쓰는 별도의 8자 이상 비밀번호. |
| `ADMIN_USERNAME` | 웹 관리자 아이디. 기본값 `admin`. |
| `COOKIE_SECURE` | 공개 HTTPS 환경에서 `true`. 기본값 `false`. |
| `EMBEDDING_MODEL` | PDF와 질문의 임베딩에 사용하는 모델. 기본값 `qwen3-embedding:8b`. |
| `LLM_MODEL` | 답변 생성 모델. 기본값 `exaone3.5:7.8b`. |
| `WEAVIATE_COLLECTION` | 검색에 사용할 컬렉션. 기본값 `Test`. |

웹 관리자 계정이 생성되면 환경에서 `ADMIN_PASSWORD`를 제거할 수 있습니다. 기존 웹 관리자 비밀번호는 앱을 재시작해도 유지됩니다. 검색에는 같은 임베딩 모델로 색인한 컬렉션을 사용합니다.

### 3. 앱 기동

```bash
docker compose up -d --build
curl --fail http://localhost:8000/api/health
```

브라우저에서 <http://localhost:8000>을 엽니다. 일반 사용자는 로그인 화면에서 회원가입할 수 있습니다. 관리자는 로그인 후 사이드바의 **자료 관리**에서 PDF를 여러 개 선택해 올리고 파일별 색인 결과를 확인할 수 있습니다.

## 저장과 삭제

- **PostgreSQL**은 시작 시 필요한 테이블(`users`, `login_sessions`, `conversations`, `messages`, `pdf_documents`)을 준비합니다. 로그인 쿠키에는 임의의 세션 토큰을 쓰고, DB에는 토큰 해시를 저장합니다. 대화 메시지에는 출처와 답변 중단 여부가 포함됩니다.
- **PDF 원본**은 `uploads/`에 저장합니다. 자료 관리에서 이름과 등록일 등을 확인하고, 목록을 검색하거나 정렬할 수 있습니다.
- **자료 삭제**는 원본과 해당 문서 ID의 Weaviate 벡터를 함께 제거합니다. 삭제가 중단되면 자료 관리에서 다시 시도할 수 있습니다.
- **이전 버전 자료**는 시작 시 `uploads/`에서 발견한 PDF를 자료 목록에 등록합니다. 삭제할 때는 기존 벡터의 `pdfFileName`과 정확히 일치하는 항목도 제거합니다. 이전에 파일만 저장한 문서는 삭제한 뒤 다시 업로드하면 색인할 수 있습니다.

## 프런트엔드 확인

```bash
cd rag-project/frontend
npm install --no-package-lock
node --test src/api/sse.test.js
npm run build
```

`npm run dev`로 Vite 개발 서버를 실행할 수 있습니다. 개발 서버는 `/api` 요청을 `http://127.0.0.1:8000`으로 전달합니다.
