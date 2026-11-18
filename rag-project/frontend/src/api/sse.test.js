import test from 'node:test';
import assert from 'node:assert/strict';
import { createSseParser } from './sse.js';

test('SSE가 임의 위치에서 분리되어 도착해도 이벤트별로 조립한다', () => {
  const received = [];
  const parser = createSseParser((event) => received.push(event));
  parser.push('event: sta');
  parser.push('tus\ndata: {"message":"검색');
  parser.push(' 중"}\n\nevent: delta\ndata: {"text":"안녕"}\n\n');
  assert.deepEqual(received, [
    { event: 'status', data: { message: '검색 중' } },
    { event: 'delta', data: { text: '안녕' } },
  ]);
});

test('한 번의 청크에 다수의 이벤트가 와도 구분한다', () => {
  const received = [];
  createSseParser(({ event }) => received.push(event))
    .push('event: sources\ndata: {"items":[]}\n\nevent: done\ndata: {}\n\n');
  assert.deepEqual(received, ['sources', 'done']);
});

test('한글 UTF-8 문자가 바이트 단위로 잘려도 TextDecoder 스트림이 복원한다', () => {
  const received = [];
  const parser = createSseParser((item) => received.push(item));
  const bytes = new TextEncoder().encode('event: delta\ndata: {"text":"안녕"}\n\n');
  const decoder = new TextDecoder();
  for (const byte of bytes) parser.push(decoder.decode(Uint8Array.of(byte), { stream: true }));
  parser.push(decoder.decode());
  assert.deepEqual(received, [{ event: 'delta', data: { text: '안녕' } }]);
});
