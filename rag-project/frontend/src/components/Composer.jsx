import { ArrowUp, Square } from 'lucide-react';

// 질문 입력, 전송, 답변 중단을 위한 입력창입니다.
export default function Composer({ value, onChange, onSubmit, isStreaming, onStop }) {
  // 비어 있지 않은 질문을 전송합니다.
  function send(event) {
    event.preventDefault();
    if (!isStreaming && value.trim()) onSubmit(value);
  }

  // 줄바꿈과 입력기 조합을 구분해 Enter를 처리합니다.
  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      send(event);
    }
  }

  return (
    <form className="composer" onSubmit={send}>
      <textarea
        className="composer-textarea"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="학교 규정에 대해 질문을 입력하세요"
        aria-label="학교 규정 질문"
        enterKeyHint="send"
        rows={1}
        maxLength={3000}
      />
      <div className="composer-bottom">
        <span className="composer-hint"><kbd>Shift</kbd> + <kbd>Enter</kbd> 줄바꿈</span>
        {isStreaming ? (
          <button className="send-button stop-button" type="button" onClick={onStop} title="답변 생성 중단" aria-label="답변 생성 중단"><Square size={15} fill="currentColor" /></button>
        ) : (
          <button className="send-button" type="submit" disabled={!value.trim()} title="전송" aria-label="질문 전송"><ArrowUp size={18} /></button>
        )}
      </div>
    </form>
  );
}
