import { ArrowUp, Square } from 'lucide-react';

export default function Composer({ value, onChange, onSubmit, isStreaming, onStop }) {
  const send = (event) => {
    event?.preventDefault();
    if (!isStreaming && value.trim()) onSubmit(value);
  };

  return (
    <form className="composer" onSubmit={send}>
      <textarea
        className="composer-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          // 한국어 IME 조합 확정 중 엔터를 전송으로 오인하지 않습니다.
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send();
          }
        }}
        placeholder="학교 규정에 대해 무엇이든 물어보세요"
        aria-label="학교 규정 질문"
        rows={2}
        maxLength={3000}
      />
      <div className="composer-bottom">
        <span className="composer-hint">Shift + Enter 줄바꿈</span>
        {isStreaming ? (
          <button className="send-button" type="button" onClick={onStop} title="답변 생성 중단" aria-label="답변 생성 중단"><Square size={15} fill="currentColor" /></button>
        ) : (
          <button className="send-button" type="submit" disabled={!value.trim()} title="전송" aria-label="질문 전송"><ArrowUp size={18} /></button>
        )}
      </div>
    </form>
  );
}
