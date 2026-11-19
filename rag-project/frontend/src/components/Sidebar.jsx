import { BookOpenText, FolderOpen, LogOut, MessageSquare, PanelLeftClose, Plus } from 'lucide-react';

export default function Sidebar({ open, onClose, onNewChat, onSelect, conversations, selectedId, user, onDocuments, view, onLogout }) {
  return (
    <>
      {open && <button className="mobile-backdrop" aria-label="메뉴 닫기" onClick={onClose} />}
      <aside className={`sidebar ${open ? 'sidebar-open' : 'sidebar-closed'}`}>
        <div className="sidebar-header">
          <span className="sidebar-brand"><BookOpenText size={19} /> 학교 규정 GPT</span>
          <button className="icon-button close-sidebar" onClick={onClose} aria-label="사이드바 접기"><PanelLeftClose size={19} /></button>
        </div>
        <div className="sidebar-actions">
          <button className="sidebar-action active" onClick={onNewChat}><Plus size={17} /> 새 채팅</button>
          {user.role === 'admin' && (
            <button className={`sidebar-action ${view === 'documents' ? 'selected' : ''}`} aria-current={view === 'documents' ? 'page' : undefined} onClick={onDocuments}>
              <FolderOpen size={17} /> 자료 관리
            </button>
          )}
        </div>
        <nav className="chat-history" aria-label="채팅 기록">
          <h2 className="section-title">채팅 기록</h2>
          {!conversations.length && <p className="muted">저장된 대화가 없습니다.</p>}
          {conversations.map((chat) => (
            <button key={chat.id} className={`sidebar-action history-item ${selectedId === chat.id && view === 'chat' ? 'selected' : ''}`}
              aria-current={selectedId === chat.id && view === 'chat' ? 'page' : undefined} title={chat.title} onClick={() => onSelect(chat.id)}>
              <MessageSquare size={15} /><span>{chat.title}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="profile-avatar">{user.username[0].toUpperCase()}</div>
          <div className="profile-name"><strong>{user.username}</strong><small>{user.role === 'admin' ? '관리자' : '일반 사용자'}</small></div>
          <button className="icon-button" onClick={onLogout} aria-label="로그아웃"><LogOut size={17} /></button>
        </div>
      </aside>
    </>
  );
}
