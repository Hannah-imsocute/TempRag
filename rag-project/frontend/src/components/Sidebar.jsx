import { BookOpenText, MessageSquare, PanelLeftClose, Plus, Search, X } from 'lucide-react';

export default function Sidebar({ open, onClose, onNewChat }) {
  return (
    <>
      {open && <button className="mobile-backdrop" aria-label="메뉴 닫기" onClick={onClose} />}
      <aside className={`sidebar ${open ? 'sidebar-open' : 'sidebar-closed'}`}>
        <div className="sidebar-header">
          <span className="sidebar-brand"><BookOpenText size={19} /> 학교 규정 GPT</span>
          <button className="icon-button close-sidebar" onClick={onClose} title="사이드바 접기" aria-label="사이드바 접기">
            <PanelLeftClose size={19} />
          </button>
        </div>
        <div className="sidebar-actions">
          <button className="sidebar-action active" onClick={onNewChat}><Plus size={17} /> 새 채팅</button>
          <div className="sidebar-action disabled" aria-disabled="true"><Search size={16} /> 채팅 검색 <span className="later">예정</span></div>
        </div>
        <div className="sidebar-section">
          <div className="section-title">채팅 기록</div>
          <div className="sidebar-empty">
            <MessageSquare size={18} strokeWidth={1.4} />
            <p>히스토리는 다음 단계에서<br />계정과 DB를 연결합니다.</p>
          </div>
        </div>
        <div className="sidebar-footer"><div className="profile-avatar">S</div><div><strong>학교 규정 챗봇</strong><small>RAG 실험 버전</small></div></div>
      </aside>
    </>
  );
}
