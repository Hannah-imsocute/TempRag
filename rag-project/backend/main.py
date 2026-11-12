import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="RAG Project")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# RAG API 추가 위치: /api/upload, /api/chat
# 연결 설정은 환경 변수에서 읽을 수 있습니다.
# os.environ["OLLAMA_BASE_URL"]
# os.environ["WEAVIATE_HTTP_HOST"]

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(static_dir / "index.html")
