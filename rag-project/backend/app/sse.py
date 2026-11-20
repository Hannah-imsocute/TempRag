import json


# 이벤트 이름과 JSON 데이터를 SSE 형식으로 변환합니다.
def encode_sse(event: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"
