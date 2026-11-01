/** Browser API requests: authenticated cookies plus a session-bound CSRF token. */
export async function apiFetch(input: string, init: RequestInit = {}) {
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  const destination = new URL(input, backend);
  if (destination.origin !== new URL(backend).origin) throw new Error('Unexpected API destination');
  const headers = new Headers(init.headers);
  if (!['GET', 'HEAD', 'OPTIONS'].includes((init.method || 'GET').toUpperCase())) {
    const response = await fetch(`${backend}/auth/status`, { credentials: 'include', cache: 'no-store' });
    if (!response.ok) throw new Error('Cannot verify your session');
    const session = await response.json();
    if (!session.connected || !session.csrf_token) throw new Error('Please connect your account again');
    headers.set('X-Koe-CSRF', session.csrf_token);
  }
  return fetch(destination, { ...init, headers, credentials: 'include' });
}
