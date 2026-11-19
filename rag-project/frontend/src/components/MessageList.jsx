import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { BookOpenText } from 'lucide-react';

export default function MessageList({ messages, status }) {
  const bottomRef = useRef(null);

  // 수신되는 텍스트 청크마다 화면을 아래로 이동하여 답변이 보이게 합니다.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' });
  }, [messages, status]);

  return (
    <div className="messages-scroller">
      <div className="messages-inner" role="log" aria-live="polite" aria-relevant="additions text">
        {messages.map((message, index) => (
          <div key={message.id} className={`message-row ${message.role === 'user' ? 'message-user' : 'message-assistant'}`}>
            {message.role === 'assistant' && <div className="assistant-icon"><BookOpenText size={18} /></div>}
            <div className="message-main">
              <div className={message.role === 'user' ? 'user-bubble' : 'assistant-answer'}>
                {message.interrupted && <p className="muted">답변 생성이 중단되었습니다.</p>}
              {message.role === 'user' ? (
                  <span>{message.content}</span>
                ) : message.content ? (
                  <div className="markdown-content"><ReactMarkdown>{message.content}</ReactMarkdown></div>
                ) : message.interrupted ? null : (
                  <span className="typing-indicator" aria-label="답변 생성 중"><span /></span>
                )}
              </div>
              {message.role === 'assistant' && message.sources?.length > 0 && (
                <div className="sources-list">
                  <div className="sources-heading">참고한 학교 규정</div>
                  {message.sources.map((source) => (
                    <span className="source-chip" key={source.index} title={`검색 결과 ${source.index}`}>
                      [{source.index}] {source.title}{source.page ? ` · ${source.page}쪽` : ''}
                    </span>
                  ))}
                </div>
              )}
              {message.role === 'assistant' && index === messages.length - 1 && status && (
                <div className="stream-status"><span className="status-dot" /> {status}</div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
