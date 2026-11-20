import { BookOpenText, FolderOpen, LogOut, MessageSquare, PanelLeftClose, Plus } from 'lucide-react';

// 대화 기록, 관리자 메뉴, 계정 작업을 표시합니다.
export default function Sidebar({ open, onClose, onNewChat, onSelect, conversations, selectedId, user, onDocuments, view, onLogout }) {
  return (
    <>
      {open && <button className="mobile-backdrop" aria-label="메뉴 닫기" onClick={onClose} />}
      <aside id="workspace-sidebar" aria-label="작업공간 사이드바" className={`sidebar ${open ? 'sidebar-open' : 'sidebar-closed'}`}
        onKeyDown={(event) => { if (event.key === 'Escape') onClose(); }}>
        <div className="sidebar-header">
          <span className="sidebar-brand"><span className="brand-mark"><BookOpenText size={19} /></span>학교 규정 GPT</span>
          <button className="icon-button" onClick={onClose} aria-controls="workspace-sidebar" aria-expanded={true} aria-label="사이드바 접기" title="사이드바 접기"><PanelLeftClose size={18} /></button>
        </div>
        <div className="sidebar-actions">
          <button className="sidebar-action new-chat-button" onClick={onNewChat}><Plus size={18} /> 새 채팅</button>
          {user.role === 'admin' && (
            <button className={`sidebar-action ${view === 'documents' ? 'selected' : ''}`} aria-current={view === 'documents' ? 'page' : undefined} onClick={onDocuments}>
              <FolderOpen size={17} /> 자료 관리
            </button>
          )}
        </div>
        <nav className="chat-history" aria-label="채팅 기록">
          <h2 className="section-title">채팅 기록</h2>
          <div className="history-list">
            {!conversations.length && <p className="history-empty">저장된 대화가 없습니다.</p>}
            {conversations.map((chat) => (
              <button key={chat.id} className={`sidebar-action history-item ${selectedId === chat.id && view === 'chat' ? 'selected' : ''}`}
                aria-current={selectedId === chat.id && view === 'chat' ? 'page' : undefined} title={chat.title} onClick={() => onSelect(chat.id)}>
                <MessageSquare size={15} /><span>{chat.title}</span>
              </button>
            ))}
          </div>
        </nav>
        <div className="sidebar-footer">
          <div className="profile-avatar">{user.username[0].toUpperCase()}</div>
          <div className="profile-name"><strong>{user.username}</strong><small>{user.role === 'admin' ? '관리자' : '일반 사용자'}</small></div>
          <button className="icon-button" onClick={onLogout} aria-label="로그아웃" title="로그아웃"><LogOut size={17} /></button>
        </div>
      </aside>
    </>
  );
}
