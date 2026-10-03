import { fixtureCSS, fixtureJS } from '@/fixtures/previews/fixtures';
export const dynamic = 'force-dynamic';
export async function GET(_request: Request, { params }: { params: Promise<{ asset: string }> }) {
  const { asset } = await params;
  if (!['development', 'test', 'preview'].includes(process.env.APP_ENV ?? 'development') || !['sample.css', 'sample.js'].includes(asset)) return new Response('Asset unavailable.', { status: 404 });
  return new Response(asset === 'sample.css' ? fixtureCSS : fixtureJS, { headers: { 'Content-Type': asset === 'sample.css' ? 'text/css; charset=utf-8' : 'text/javascript; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } });
}
