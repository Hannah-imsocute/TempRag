/**
 * SSE는 'event: name\ndata: JSON\n\n'이라는 텍스트 규약입니다.
 * 네트워크의 read() 경계는 이벤트 경계와 일치하지 않으므로 버퍼를 유지합니다.
 */
export function createSseParser(onEvent) {
  let buffer = '';

  return {
    push(text) {
      // 백엔드에서 보내는 개행은 LF. 경계가 나뉜 상태에서도 버퍼를 유지합니다.
      buffer += text;
      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const lines = block.split('\n');
        let event = 'message';
        const dataLines = [];
        for (const line of lines) {
          if (line.startsWith('event:')) event = line.slice(6).trim();
          if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
        }
        if (dataLines.length) {
          const data = JSON.parse(dataLines.join('\n'));
          onEvent({ event, data });
        }
        boundary = buffer.indexOf('\n\n');
      }
    },
  };
}
