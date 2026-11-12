# RAG Project — React + FastAPI

- React + Vite + TypeScript: UI
- FastAPI: 백엔드 API, React 정적 파일 서비스
- 기존 Ollama, Weaviate Docker 컨테이너 재사용 (새로 생성하지 않음)

## 사전 조건

기존 Docker 네트워크 `db-connect`가 있어야 하고, `ollama`와 `weaviate`라는 이름(또는 네트워크 별칭)으로 접근할 수 있어야 합니다.

```bash
docker network ls
docker network inspect db-connect
```

실행 중인 기존 컨테이너가 네트워크에 없다면 (컨테이너 이름이 실제로 일치하는지 확인):

```bash
docker network connect db-connect ollama
docker network connect db-connect weaviate
```

## 시작

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f rag-app
```

- 웹 UI: http://localhost:8000/
- API 상태: http://localhost:8000/api/health
- Swagger: http://localhost:8000/docs

호스트/서버 밖에서 접속할 때는 localhost 대신 서버 IP를 사용합니다. EC2라면 보안 그룹 인바운드 규칙도 확인하세요.

## 개발

- `frontend/src/App.tsx`: React 화면
- `backend/main.py`: FastAPI 엔드포인트
- `backend/requirements.txt`: Python 패키지
- `compose.yaml`: 외부 컨테이너 연결 환경 변수

이 Compose 구성은 배포형 통합 이미지입니다. 코드를 수정하면 `docker compose up -d --build`로 반영하세요. Git 커밋은 호스트 프로젝트 폴더에서 수행합니다.

`/api/health`는 **FastAPI 상태만** 확인합니다. Ollama/Weaviate 연결을 실제로 검사하지는 않습니다.

RAG 로직과 PDF 업로드/질문 API는 아직 구현하지 않은 최소 뼈대입니다.

프론트엔드의 `package-lock.json`은 포함하지 않았습니다. 최초 Docker 빌드에서는 `npm install`이 실행됩니다. 로컬에서 `cd frontend && npm install` 후 생성된 lock 파일을 Git에 커밋하면 이후 Docker 빌드는 `npm ci`를 사용합니다.
