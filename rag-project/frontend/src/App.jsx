import { useRef, useState } from 'react';
import { BookOpen, GraduationCap, Menu } from 'lucide-react';
import Sidebar from './components/Sidebar';
import Composer from './components/Composer';
import MessageList from './components/MessageList';
import { streamChat } from './api/chat';

// 현재 단계에서는 DB가 없으므로 이 ID는 React 화면 목록용으로만 사용합니다.
function makeId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

const EXAMPLES = [
  '졸업에 필요한 학점은 몇 학점인가요?',
  '휴학 신청은 어떻게 하나요?',
  '장학금 지급 기준이 궁금해요.',
];

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState('');
  const controllerRef = useRef(null);

  function newChat() {
    // 이전 HTTP 스트림이 늦게 응답하더라도 새 채팅 화면을 변경하지 못하도록 중단합니다.
    controllerRef.current?.abort();
    controllerRef.current = null;
    setMessages([]);
    setDraft('');
    setStatus('');
    setIsStreaming(false);
    if (window.innerWidth < 700) setSidebarOpen(false);
  }

  function stopGeneration() {
    controllerRef.current?.abort();
  }

  async function sendQuestion(text) {
    const question = text.trim();
    if (!question || isStreaming) return;
    const answerId = makeId();
    const controller = new AbortController();
    controllerRef.current = controller;
    setDraft('');
    setIsStreaming(true);
    setStatus('질문을 보내고 있습니다...');
    setMessages((prev) => [
      ...prev,
      { id: makeId(), role: 'user', content: question },
      { id: answerId, role: 'assistant', content: '', sources: [] },
    ]);

    const updateAnswer = (update) => {
      if (controllerRef.current !== controller) return;
      setMessages((prev) => prev.map((m) => (m.id === answerId ? { ...m, ...update(m) } : m)));
    };

    try {
      await streamChat(question, {
        onStatus(message) {
          if (controllerRef.current === controller) setStatus(message);
        },
        onSources(items) {
          updateAnswer(() => ({ sources: items }));
        },
        onDelta(textChunk) {
          updateAnswer((m) => ({ content: m.content + textChunk }));
        },
      }, controller.signal);
    } catch (error) {
      if (controllerRef.current !== controller) return;
      const message = error.name === 'AbortError'
        ? '\n\n*(답변 생성이 중단되었습니다.)*'
        : `\n\n⚠️ ${error.message}`;
      updateAnswer((m) => ({ content: m.content + message }));
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setIsStreaming(false);
        setStatus('');
      }
    }
  }

  const isWelcome = messages.length === 0;

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} onNewChat={newChat} />
      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            {!sidebarOpen && <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-label="사이드바 열기"><Menu size={21} /></button>}
            <div className="model-title">학교 규정 GPT <span className="model-tag">RAG</span></div>
          </div>
          <div className="topbar-right"><BookOpen size={19} /><span>학칙 기반 답변</span></div>
        </header>
        {isWelcome ? (
          <div className="welcome-area">
            <div className="welcome-content">
              <div className="welcome-symbol"><GraduationCap size={29} strokeWidth={1.6} /></div>
              <h1>학교 규정에 대해 무엇이든 물어보세요</h1>
              <p>학교 규정 문서를 검색해 근거와 함께 답변합니다.</p>
              <Composer value={draft} onChange={setDraft} onSubmit={sendQuestion} isStreaming={isStreaming} onStop={stopGeneration} />
              <div className="example-list">
                {EXAMPLES.map((question) => <button className="example-button" onClick={() => sendQuestion(question)} key={question}>{question}</button>)}
              </div>
            </div>
          </div>
        ) : (
          <>
            <MessageList messages={messages} status={status} />
            <div className="bottom-composer">
              <div className="composer-width">
                <Composer value={draft} onChange={setDraft} onSubmit={sendQuestion} isStreaming={isStreaming} onStop={stopGeneration} />
                <div className="disclaimer">AI 답변은 참고용입니다. 중요한 학사 결정은 학교 공지와 담당 부서에 다시 확인하세요.</div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
