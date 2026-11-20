// 분할된 SSE 데이터를 모아 이벤트 단위로 전달하는 파서를 만듭니다.
export function createSseParser(onEvent) {
  let buffer = '';

  return {
    // 새 데이터에서 완성된 SSE 이벤트를 읽습니다.
    push(text) {
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
