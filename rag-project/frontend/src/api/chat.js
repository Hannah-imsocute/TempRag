import { createSseParser } from './sse';

// 질문을 보내고 SSE 응답을 이벤트별로 전달합니다.
export async function streamChat(conversationId, question, callbacks, signal) {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ conversation_id: conversationId, question }),
    signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : `요청 실패 (HTTP ${response.status})`);
  }
  if (!response.body) throw new Error('브라우저가 스트리밍 응답을 지원하지 않습니다.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
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
