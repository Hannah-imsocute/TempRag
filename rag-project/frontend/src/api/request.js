export async function requestJson(path, options) {
  const response = await fetch(path, options);
  if (response.status === 204) return;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = typeof data?.detail === 'string' ? data.detail : '요청을 처리하지 못했습니다.';
    throw Object.assign(new Error(message), { status: response.status });
  }
  return data;
}

export function postJson(path, body, signal) {
  return requestJson(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
}
