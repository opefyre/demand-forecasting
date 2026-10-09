// Fail closed until durable state, identity and recovery pass deployment checks.
// Deliberately no assets, secrets, storage bindings or container wake-up path.
export default {
  async fetch(request) {
    const headers = new Headers({
      'Cache-Control': 'no-store',
      'Retry-After': '3600',
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
      'Referrer-Policy': 'no-referrer',
      'X-Robots-Tag': 'noindex, nofollow',
      'Strict-Transport-Security': 'max-age=31536000',
    });
    const path = new URL(request.url).pathname;
    const api = path === '/api' || path.startsWith('/api/');
    headers.set('Content-Type', api ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8');
    const body = api
      ? JSON.stringify({ error: 'deployment_not_ready', message: 'Forecast is not available yet.' })
      : 'Forecast is being prepared. Please try again later.\n';
    return new Response(request.method === 'HEAD' ? null : body, { status: 503, headers });
  },
};
