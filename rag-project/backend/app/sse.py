"""SSE: event 이름과 JSON 데이터를 두 줄로 인코딩합니다."""
import json


def encode_sse(event: str, payload: dict) -> str:
    # ensure_ascii=False로 한국어를 그대로 전달하고 JSON으로 개행을 안전하게 이스케이프합니다.
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"
