import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BookOpenText, FileText } from 'lucide-react';

// 질문, 답변, 출처를 대화 순서대로 표시합니다.
export default function MessageList({ messages, status }) {
  const scrollerRef = useRef(null);

  useEffect(() => {
    const scroller = scrollerRef.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [messages, status]);

  return (
    <div className="messages-scroller" ref={scrollerRef}>
      <div className="messages-inner" role="log" aria-live="polite" aria-relevant="additions text">
        {messages.map((message, index) => (
          <div key={message.id} className={`message-row ${message.role === 'user' ? 'message-user' : 'message-assistant'}`}>
            {message.role === 'assistant' && <div className="assistant-icon" aria-hidden="true"><BookOpenText size={17} /></div>}
            <div className="message-main">
              <div className={message.role === 'user' ? 'user-bubble' : 'assistant-answer'}>
                {message.role === 'user' ? (
                  <span>{message.content}</span>
                ) : message.content ? (
                  <div className="markdown-content"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown></div>
                ) : message.interrupted ? null : (
                  <span className="typing-indicator" aria-label="답변 생성 중" />
                )}
                {message.interrupted && <p className="muted">답변 생성이 중단되었습니다.</p>}
              </div>
              {message.role === 'assistant' && message.sources?.length > 0 && (
                <div className="sources-list">
                  <div className="sources-heading">참고한 학교 규정</div>
                  {message.sources.map((source) => (
                    <span className="source-chip" key={source.index}>
                      <FileText size={14} aria-hidden="true" />
                      <span>[{source.index}] {source.title}{source.page ? ` · ${source.page}쪽` : ''}</span>
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
      </div>
    </div>
  );
}
