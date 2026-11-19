# 학교 규정 GPT

## Docker 실행

기존 `ollama`, `weaviate`, `postgre` 컨테이너와 같은 외부 `db-connect` 네트워크에서 `rag-app`을 실행합니다. PostgreSQL은 `postgre:5432`의 `rag` 데이터베이스에 `admin`으로 접속합니다. 이 프로젝트의 Compose는 기존 서비스 컨테이너를 재사용합니다.

```bash
docker network inspect db-connect
docker exec ollama ollama list
```

`rag-project/.env`를 만들고 `POSTGRES_PASSWORD`에 기존 PostgreSQL 비밀번호를 지정합니다. 첫 시작 시 웹 관리자 계정을 만들려면 `ADMIN_PASSWORD`에 별도의 8자 이상 비밀번호를 넣습니다. 웹 관리자의 아이디는 `ADMIN_USERNAME`으로 지정할 수 있으며 기본값은 `admin`입니다. 계정이 생성되면 `ADMIN_PASSWORD`는 환경에서 제거해도 됩니다. 기존 웹 관리자 비밀번호는 시작할 때 덮어쓰지 않습니다. 공개 HTTPS 배포에서는 `COOKIE_SECURE=true`로 설정합니다.

기본 모델은 임베딩에 `qwen3-embedding:8b`, 답변 생성에 `exaone3.5:7.8b`를 사용합니다. Ollama에 두 모델을 준비한 뒤 시작합니다.

```bash
docker exec ollama ollama pull qwen3-embedding:8b
docker exec ollama ollama pull exaone3.5:7.8b
docker compose up -d --build
```

접속 포트는 `8000`입니다. `EMBEDDING_MODEL`, `LLM_MODEL`, `WEAVIATE_COLLECTION`(기본값 `Test`)을 설정으로 변경할 수 있습니다. 컬렉션에는 같은 임베딩 모델의 벡터를 사용합니다.

## 계정, 대화, 자료

- 일반 계정은 로그인 화면에서 회원가입합니다. 토글 사이드바에서 새 채팅을 시작하거나 본인의 대화 기록을 다시 엽니다.
- 관리자는 사이드바의 **자료 관리** 화면에서 검색·정렬 및 삭제를 할 수 있습니다. 여러 PDF를 한 번에 선택하면 파일별로 색인하고 결과를 표시합니다. 텍스트가 없는 스캔 PDF는 OCR을 적용한 뒤 업로드합니다.
- PostgreSQL이 비어 있으면 서버 시작 시 `users`, `login_sessions`, `conversations`, `messages`, `pdf_documents`를 생성합니다. 로그인 쿠키에는 임의의 세션 토큰을 사용하며 PostgreSQL에는 토큰 해시를 저장합니다. 대화 메시지에는 저장된 출처 및 답변 중단 상태가 포함됩니다.
- 원본은 `uploads/`에, 이름·등록일·상태 등 문서 정보는 PostgreSQL에 저장합니다. PDF별 ID를 Weaviate의 청크 벡터에 기록하므로 자료를 삭제하면 해당 벡터와 원본도 삭제됩니다. 삭제가 중단되면 자료 관리에서 다시 시도할 수 있습니다.
- 이전 버전의 `uploads/` PDF는 시작 시 목록에 등록합니다. 삭제 시 기존 Weaviate 벡터의 `pdfFileName`과 정확히 일치하는 벡터도 제거합니다. 이전에 파일만 저장한 문서를 색인하려면 해당 문서를 삭제한 뒤 다시 업로드합니다.
