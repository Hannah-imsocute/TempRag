import { useEffect, useState } from 'react'

export default function App() {
  const [status, setStatus] = useState('확인 중...')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => {
        if (!res.ok) throw new Error('API 응답 오류')
        return res.json() as Promise<{ status: string }>
      })
      .then((data) => setStatus(data.status))
      .catch(() => setStatus('연결 실패'))
  }, [])

  return (
    <main style={{ fontFamily: 'sans-serif', padding: 32 }}>
      <h1>RAG Project</h1>
      <p>React + FastAPI</p>
      <p>FastAPI 상태: {status}</p>
    </main>
  )
}
