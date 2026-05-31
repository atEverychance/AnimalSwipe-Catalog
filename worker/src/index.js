const JSON_CACHE = 'public, max-age=60, stale-while-revalidate=300';
const IMMUTABLE_CACHE = 'public, max-age=31536000, immutable';

function contentTypeFor(key) {
  if (key.endsWith('.json')) return 'application/json; charset=utf-8';
  if (key.endsWith('.jpg') || key.endsWith('.jpeg')) return 'image/jpeg';
  if (key.endsWith('.png')) return 'image/png';
  if (key.endsWith('.webp')) return 'image/webp';
  return 'application/octet-stream';
}

function objectKey(pathname) {
  const clean = pathname.replace(/^\/+/, '');
  if (clean === '' || clean === 'latest.json') return 'latest.json';
  if (clean.startsWith('catalog/') || clean.startsWith('assets/')) return clean;
  if (clean === 'health') return null;
  return undefined;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    }
    const key = objectKey(url.pathname);
    if (key === null) {
      return Response.json({ ok: true, service: 'animalswipe-catalog' }, { headers: { 'Cache-Control': 'no-store' } });
    }
    if (key === undefined) return new Response('Not found', { status: 404 });
    const object = await env.CATALOG_BUCKET.get(key);
    if (!object) return new Response('Not found', { status: 404 });
    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set('etag', object.httpEtag);
    headers.set('content-type', object.httpMetadata?.contentType || contentTypeFor(key));
    headers.set('cache-control', key === 'latest.json' ? JSON_CACHE : IMMUTABLE_CACHE);
    if (request.method === 'HEAD') return new Response(null, { headers });
    return new Response(object.body, { headers });
  }
};
