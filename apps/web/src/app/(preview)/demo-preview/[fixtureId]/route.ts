import { fixtureHTML, fixtureIds, previewCSP } from '@/fixtures/previews/fixtures';
export const dynamic = 'force-dynamic';
export async function GET(_request: Request, { params }: { params: Promise<{ fixtureId: string }> }) {
  const { fixtureId } = await params;
  if (!['development', 'test', 'preview'].includes(process.env.APP_ENV ?? 'development') || !fixtureIds.includes(fixtureId as typeof fixtureIds[number])) return new Response('Sample unavailable.', { status: 404 });
  return new Response(fixtureHTML(fixtureId as typeof fixtureIds[number]), { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Content-Security-Policy': previewCSP, 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff' } });
}
