import { useEffect, useRef, useState } from 'react';
import { FileText, Search, Trash2, Upload } from 'lucide-react';
import { requestJson } from '../api/request';

const dateFormat = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium' });
const statusNames = { ready: '등록됨', indexing: '색인 중', deleting: '삭제 진행 중' };

function fileSize(bytes) {
  return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`;
}

export default function Documents() {
  const [files, setFiles] = useState([]);
  const [documents, setDocuments] = useState(null);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('newest');
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState('');
  const [errors, setErrors] = useState([]);
  const [listError, setListError] = useState('');
  const input = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      requestJson(`/api/pdfs?${new URLSearchParams({ q: query, sort })}`, { signal: controller.signal })
        .then((data) => { setDocuments(data); setListError(''); })
        .catch((error) => { if (!controller.signal.aborted) setListError(error.message); });
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, sort, revision]);

  async function upload(event) {
    event.preventDefault();
    if (!files.length || busy) return;
    setBusy(true);
    setErrors([]);
    let completed = 0;
    const failures = [];
    try {
      for (const [index, file] of files.entries()) {
        setProgress(`색인 중 ${index + 1}/${files.length} · ${file.name}`);
        const body = new FormData();
        body.append('file', file);
        try {
          await requestJson('/api/pdfs', { method: 'POST', body });
          completed++;
        } catch (error) {
          failures.push(`${file.name} · ${error.message}`);
        }
        setRevision((value) => value + 1);
      }
      setProgress(`${completed}개 등록 완료${failures.length ? ` · ${failures.length}개 실패` : ''}`);
      setErrors(failures);
      if (input.current) input.current.value = '';
      setFiles([]);
    } finally {
      setBusy(false);
    }
  }

  async function remove(document) {
    if (!window.confirm(`“${document.filename}”과 검색 벡터를 삭제할까요?`)) return;
    setBusy(true);
    setErrors([]);
    setProgress('');
    try {
      await requestJson(`/api/pdfs/${document.id}`, { method: 'DELETE' });
      setProgress(`${document.filename} 삭제 완료`);
    } catch (error) {
      setErrors([error.message]);
    } finally {
      setRevision((value) => value + 1);
      setBusy(false);
    }
  }

  return (
    <section className="documents-page" aria-labelledby="documents-title">
      <h1 id="documents-title">자료 관리</h1>
      <form className="upload-panel" onSubmit={upload}>
        <div>
          <label className="document-label" htmlFor="pdf-upload">PDF 업로드</label>
          <input ref={input} id="pdf-upload" type="file" accept=".pdf,application/pdf" multiple disabled={busy}
            onChange={(event) => setFiles(Array.from(event.target.files))} />
        </div>
        <button className="primary-button" disabled={!files.length || busy}><Upload size={17} />{files.length ? `${files.length}개 업로드` : '업로드'}</button>
      </form>
      {progress && <p className="muted" role="status">{progress}</p>}
      {errors.length > 0 && <ul className="form-error" role="alert">{errors.map((error, index) => <li key={index}>{error}</li>)}</ul>}
      <div className="documents-toolbar">
        <h2>등록된 PDF</h2>
        <label className="search-field"><Search size={17} />
          <input type="search" aria-label="PDF 검색" placeholder="파일 이름 검색" value={query} maxLength={255} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <select aria-label="PDF 정렬" value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="newest">최신순</option>
          <option value="oldest">오래된순</option>
          <option value="name">이름순</option>
          <option value="size">크기순</option>
        </select>
      </div>
      {listError && <p role="alert" className="form-error">{listError}</p>}
      {documents === null && !listError && <p className="muted">목록을 불러오는 중입니다.</p>}
      {documents?.length === 0 && <p className="empty-documents">{query ? '검색 결과가 없습니다.' : '등록된 PDF가 없습니다.'}</p>}
      {documents?.length > 0 && (
        <div className="document-table">
          <table>
            <thead><tr><th scope="col">파일 이름</th><th scope="col">등록일</th><th scope="col">크기</th><th scope="col">상태</th><th scope="col">관리</th></tr></thead>
            <tbody>{documents.map((document) => (
              <tr key={document.id}>
                <td><span className="document-name"><FileText size={18} />{document.filename}</span></td>
                <td>{dateFormat.format(new Date(document.uploaded_at))}</td>
                <td>{fileSize(document.size_bytes)}</td>
                <td>{statusNames[document.status]}</td>
                <td><button className="delete-button" disabled={busy} aria-label={`${document.filename} 삭제`} onClick={() => remove(document)}><Trash2 size={16} /> 삭제</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </section>
  );
}
