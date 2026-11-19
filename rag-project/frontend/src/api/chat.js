import { createSseParser } from './sse';

/** POST 요청의 본문은 JSON, 응답은 SSE. GET만 기본 지원하는 EventSource 대신 fetch 사용. */
export async function streamChat(conversationId, question, callbacks, signal) {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ conversation_id: conversationId, question }),
    signal,
  });

  if (!response.ok) {
    let detail = `요청 실패 (HTTP ${response.status})`;
    try {
      const error = await response.json();
      if (typeof error.detail === 'string') detail = error.detail;
    } catch {
      // HTML/기타 오류 응답일 수도 있으므로 기본 메시지를 사용합니다.
    }
    throw new Error(detail);
  }
  if (!response.body) throw new Error('브라우저가 스트리밍 응답을 지원하지 않습니다.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder(); // 한글이 청크 중간에서 잘려도 스트리밍 UTF-8 디코딩
  let completed = false;
  const parser = createSseParser(({ event, data }) => {
    if (event === 'status') callbacks.onStatus?.(data.message);
    if (event === 'sources') callbacks.onSources?.(data.items || []);
    if (event === 'delta') callbacks.onDelta?.(data.text || '');
    if (event === 'done') completed = true;
    if (event === 'error') throw new Error(data.message || '답변 생성에 실패했습니다.');
  });

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
      if (completed) break;
    }
    parser.push(decoder.decode());
    if (!completed) throw new Error('서버 연결이 답변 완료 전에 종료되었습니다.');
  } finally {
    if (!completed) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
