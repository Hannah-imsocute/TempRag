import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Award, CalendarDays, GraduationCap, PanelLeftOpen } from 'lucide-react';
import AuthForm from './components/AuthForm';
import Sidebar from './components/Sidebar';
import Composer from './components/Composer';
import Documents from './components/Documents';
import MessageList from './components/MessageList';
import { streamChat } from './api/chat';
import { requestJson } from './api/request';

const EXAMPLES = [
  { question: '졸업에 필요한 학점은 몇 학점인가요?', icon: GraduationCap },
  { question: '휴학 신청은 어떻게 하나요?', icon: CalendarDays },
  { question: '장학금 지급 기준이 궁금해요.', icon: Award },
];

// 로그인 상태에 따라 인증 화면 또는 작업공간을 표시합니다.
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

  if (user === undefined) return <main className="auth-page auth-loading" role="status">로그인 상태를 확인하는 중입니다.</main>;
  if (!user) return <AuthForm sessionError={error} onLogin={(account) => { setError(''); setUser(account); }} />;
  return <Workspace user={user} onLogout={() => setUser(null)} />;
}

// 채팅과 관리자 자료 관리 화면의 상태를 관리합니다.
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

  // 현재 사용자의 대화 목록을 새로 불러옵니다.
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

  // 모바일에서 메뉴 항목을 선택하면 사이드바를 닫습니다.
  function closeOnMobile() {
    if (window.innerWidth < 700) setSidebarOpen(false);
  }

  // 진행 중인 요청을 중지하고 채팅 화면을 초기화합니다.
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

  // 빈 대화로 이동합니다.
  function newChat() {
    resetChat();
    setView('chat');
    closeOnMobile();
  }

  // 선택한 대화의 저장된 메시지를 불러옵니다.
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

  // 서버 세션을 종료하고 로그인 화면으로 이동합니다.
  async function logout() {
    try {
      await requestJson('/api/auth/logout', { method: 'POST' });
      onLogout();
    } catch (problem) {
      setError(problem.message);
    }
  }

  // 질문을 전송하고 수신한 답변과 출처를 표시합니다.
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

  const hasMessages = messages.length > 0;
  const chatTitle = conversations.find((chat) => chat.id === selectedId)?.title || '새 채팅';
  const title = view === 'documents' ? '관리자' : chatTitle;

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} onNewChat={newChat}
        onSelect={selectConversation} conversations={conversations} selectedId={selectedId} user={user}
        onDocuments={() => { setView('documents'); closeOnMobile(); }} view={view} onLogout={logout} />
      <main className="main-panel">
        <header className="topbar">
          {!sidebarOpen && (
            <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-controls="workspace-sidebar" aria-expanded={false} aria-label="사이드바 열기" title="사이드바 열기">
              <PanelLeftOpen size={20} />
            </button>
          )}
          <span className="view-title" title={title}>{title}</span>
        </header>
        {error && <p className="app-alert form-error" role="alert">{error}</p>}
        {view === 'documents' ? <Documents /> : loading ? (
          <p className="chat-loading muted" role="status">대화를 불러오는 중입니다.</p>
        ) : (
          <section className={`chat-panel ${hasMessages ? 'chat-active' : 'chat-welcome'}`} aria-label="학교 규정 채팅">
            <div className="chat-body">
              {hasMessages ? <MessageList messages={messages} status={status} /> : (
                <div className="welcome-content">
                  <div className="welcome-symbol" aria-hidden="true"><GraduationCap size={32} strokeWidth={1.65} /></div>
                  <h1><span>학교 규정</span>이 궁금하신가요?</h1>
                  <p>학칙과 학교 규정을 검색해 출처와 함께 답변합니다.</p>
                </div>
              )}
            </div>
            <div className="composer-region">
              <div className="composer-width">
                <Composer value={draft} onChange={setDraft} onSubmit={sendQuestion} isStreaming={isStreaming}
                  onStop={() => controllerRef.current?.abort()} />
                {hasMessages ? (
                  <p className="disclaimer">중요한 학사 결정은 학교 공지와 담당 부서에서 확인하세요.</p>
                ) : (
                  <div className="example-list" role="group" aria-label="예시 질문">
                    {EXAMPLES.map(({ question, icon: Icon }) => (
                      <button type="button" className="example-button" disabled={isStreaming}
                        onClick={() => sendQuestion(question)} key={question}>
                        <span className="example-icon"><Icon size={19} strokeWidth={1.75} /></span>
                        <span>{question}</span>
                        <ArrowUpRight className="example-arrow" size={15} aria-hidden="true" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
