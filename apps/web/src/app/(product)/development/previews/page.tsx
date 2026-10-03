import { notFound } from 'next/navigation';
import { FixtureShowcase } from '@/features/workspace/preview';
export const dynamic = 'force-dynamic';
export default function Page() { if (!['development', 'test', 'preview'].includes(process.env.APP_ENV ?? 'development')) notFound(); return <FixtureShowcase />; }
