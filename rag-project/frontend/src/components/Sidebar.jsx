import { BookOpenText, MessageSquare, PanelLeftClose, Plus, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function Sidebar({ open, onClose, onNewChat }) {
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/api/pdfs')
      .then((response) => {
        if (!response.ok) throw new Error();
        return response.json();
      })
      .then(setFiles)
      .catch(() => setError('PDF 목록을 불러오지 못했습니다.'))
      .finally(() => setBusy(false));
  }, []);

  async function uploadPdf(event) {
    const input = event.currentTarget;
    const file = input.files[0];
    if (!file) return;
    const body = new FormData();
    body.append('file', file);
    setUploading(true);
    setError('');
    try {
      const response = await fetch('/api/pdfs', { method: 'POST', body });
      const result = await response.json();
      if (!response.ok) {
        setError(result.detail || 'PDF 업로드에 실패했습니다.');
        return;
      }
      setFiles((previous) => [...previous.filter((name) => name !== result), result].sort());
    } catch {
      setError('PDF 업로드에 실패했습니다.');
    } finally {
      input.value = '';
      setUploading(false);
    }
  }

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
        <section className="sidebar-section">
          <label htmlFor="pdf-upload">PDF 업로드</label>
          <input id="pdf-upload" type="file" accept=".pdf,application/pdf" disabled={busy || uploading} onChange={uploadPdf} />
          {uploading && <p role="status">PDF를 임베딩하고 있습니다…</p>}
          {error && <p role="alert">{error}</p>}
          <div className="section-title">업로드된 PDF</div>
          <ul className="pdf-list">
            {files.map((name) => <li key={name}>{name}</li>)}
          </ul>
        </section>
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
