import { useState } from 'react';
import { BookOpenText } from 'lucide-react';
import { postJson } from '../api/request';

export default function AuthForm({ onLogin }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true);
    setError('');
    try {
      onLogin(await postJson(register ? '/api/auth/register' : '/api/auth/login', fields));
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <BookOpenText size={28} aria-hidden="true" />
        <h1>학교 규정 GPT</h1>
        <h2>{register ? '회원가입' : '로그인'}</h2>
        <label>아이디
          <input name="username" autoComplete="username" pattern="[A-Za-z0-9_.\-]{3,40}" title="영문, 숫자, 점, 밑줄, 하이픈 3–40자" required />
        </label>
        <label>비밀번호
          <input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 8 : 1} maxLength={128} required />
        </label>
        {error && <p role="alert" className="form-error">{error}</p>}
        <button className="primary-button" disabled={busy}>{register ? '계정 만들기' : '로그인'}</button>
        <button type="button" className="text-button" disabled={busy} onClick={() => { setRegister(!register); setError(''); }}>
          {register ? '로그인으로 돌아가기' : '회원가입'}
        </button>
      </form>
    </main>
  );
}
