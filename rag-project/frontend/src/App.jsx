import { useEffect, useRef, useState } from 'react';
import { BookOpen, GraduationCap, Menu } from 'lucide-react';
import AuthForm from './components/AuthForm';
import Sidebar from './components/Sidebar';
import Composer from './components/Composer';
import Documents from './components/Documents';
import MessageList from './components/MessageList';
import { streamChat } from './api/chat';
import { requestJson } from './api/request';

const EXAMPLES = [
  '졸업에 필요한 학점은 몇 학점인가요?',
  '휴학 신청은 어떻게 하나요?',
  '장학금 지급 기준이 궁금해요.',
];

export default function App() {
  const [user, setUser] = useState(undefined);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    requestJson('/api/auth/me', { signal: controller.signal })
      .then(setUser)
      .catch((problem) => {
        if (!controller.signal.aborted) {
          if (problem.status !== 401) setError(problem.message);
          setUser(null);
        }
      });
    return () => controller.abort();
  }, []);

  if (user === undefined) return <main className="auth-page" role="status">로그인 상태를 확인하는 중입니다.</main>;
  if (!user) return <>{error && <p className="app-alert form-error" role="alert">{error}</p>}<AuthForm onLogin={(account) => { setError(''); setUser(account); }} /></>;
  return <Workspace user={user} onLogout={() => setUser(null)} />;
}

function Workspace({ user, onLogout }) {
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 700);
  const [view, setView] = useState('chat');
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const controllerRef = useRef(null);
  const selectionRef = useRef(null);

  function refreshHistory(signal) {
    return requestJson('/api/chat/conversations', { signal }).then(setConversations).catch((problem) => {
      if (!signal?.aborted) setError(problem.message);
    });
  }

  useEffect(() => {
    const controller = new AbortController();
    refreshHistory(controller.signal);
    return () => {
      controller.abort();
      controllerRef.current?.abort();
      selectionRef.current?.abort();
    };
  }, []);

  function closeOnMobile() {
    if (window.innerWidth < 700) setSidebarOpen(false);
  }

  function resetChat() {
    controllerRef.current?.abort();
    controllerRef.current = null;
    selectionRef.current?.abort();
    selectionRef.current = null;
    setMessages([]);
    setSelectedId(null);
    setDraft('');
    setStatus('');
    setError('');
    setLoading(false);
    setIsStreaming(false);
  }

  function newChat() {
    resetChat();
    setView('chat');
    closeOnMobile();
  }

  async function selectConversation(id) {
    if (id === selectedId && view === 'chat') return closeOnMobile();
    resetChat();
    setView('chat');
    closeOnMobile();
    setLoading(true);
    const controller = new AbortController();
    selectionRef.current = controller;
    try {
      const conversation = await requestJson(`/api/chat/conversations/${id}`, { signal: controller.signal });
      if (selectionRef.current === controller) {
        setMessages(conversation.messages);
        setSelectedId(id);
      }
    } catch (problem) {
      if (!controller.signal.aborted) setError(problem.message);
    } finally {
      if (selectionRef.current === controller) {
        selectionRef.current = null;
        setLoading(false);
      }
    }
  }

  async function logout() {
    try {
      await requestJson('/api/auth/logout', { method: 'POST' });
      onLogout();
    } catch (problem) {
      setError(problem.message);
    }
  }

  async function sendQuestion(text) {
    const question = text.trim();
    if (!question || controllerRef.current || loading) return;
    const controller = new AbortController();
    const answerId = `answer-${Date.now()}`;
    controllerRef.current = controller;
    setError('');
    setIsStreaming(true);
    setStatus('질문을 보내고 있습니다...');
    const current = () => controllerRef.current === controller;
    const updateAnswer = (update) => {
      if (current()) setMessages((previous) => previous.map((message) =>
        message.id === answerId ? { ...message, ...update(message) } : message));
    };
    let chatId = selectedId;
    try {
      if (!chatId) {
        const chat = await requestJson('/api/chat/conversations', { method: 'POST', signal: controller.signal });
        if (!current()) return;
        chatId = chat.id;
        setSelectedId(chatId);
      }
      setDraft('');
      setMessages((previous) => [
        ...previous,
        { id: `question-${answerId}`, role: 'user', content: question },
        { id: answerId, role: 'assistant', content: '', sources: [] },
      ]);
      await streamChat(chatId, question, {
        onStatus(message) {
          if (current()) setStatus(message);
        },
        onSources(items) {
          updateAnswer(() => ({ sources: items }));
        },
        onDelta(chunk) {
          updateAnswer((message) => ({ content: message.content + chunk }));
        },
      }, controller.signal);
    } catch (problem) {
      if (current() && problem.name === 'AbortError') {
        updateAnswer(() => ({ interrupted: true }));
      } else if (current()) {
        setError(problem.message);
        setMessages((previous) => previous.filter((message) => message.id !== answerId || message.content));
      }
    } finally {
      if (current()) {
        controllerRef.current = null;
        setIsStreaming(false);
        setStatus('');
      }
      if (chatId) refreshHistory();
    }
  }

  const composer = <Composer value={draft} onChange={setDraft} onSubmit={sendQuestion} isStreaming={isStreaming} onStop={() => controllerRef.current?.abort()} />;

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} onNewChat={newChat}
        onSelect={selectConversation} conversations={conversations} selectedId={selectedId} user={user}
        onDocuments={() => { setView('documents'); closeOnMobile(); }} view={view} onLogout={logout} />
      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            {!sidebarOpen && <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-label="사이드바 열기"><Menu size={21} /></button>}
            <span className="model-title">{view === 'documents' ? '관리자' : '학교 규정 GPT'}</span>
          </div>
          {view === 'chat' && <div className="topbar-right"><BookOpen size={19} /><span>학칙 기반 답변</span></div>}
        </header>
        {error && <p className="app-alert form-error" role="alert">{error}</p>}
        {view === 'documents' ? <Documents /> : loading ? (
          <p className="app-alert muted" role="status">대화를 불러오는 중입니다.</p>
        ) : messages.length === 0 ? (
          <div className="welcome-area">
            <div className="welcome-content">
              <div className="welcome-symbol"><GraduationCap size={29} strokeWidth={1.6} /></div>
              <h1>학교 규정에 대해 무엇이든 물어보세요</h1>
              <p>학교 규정 문서를 검색해 근거와 함께 답변합니다.</p>
              {composer}
              <div className="example-list">
                {EXAMPLES.map((question) => <button className="example-button" disabled={isStreaming} onClick={() => sendQuestion(question)} key={question}>{question}</button>)}
              </div>
            </div>
          </div>
        ) : (
          <>
            <MessageList messages={messages} status={status} />
            <div className="bottom-composer">
              <div className="composer-width">
                {composer}
                <div className="disclaimer">중요한 학사 결정은 학교 공지와 담당 부서에서 확인하세요.</div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
