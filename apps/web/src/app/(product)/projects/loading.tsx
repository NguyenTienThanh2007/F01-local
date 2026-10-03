export default function Loading() {
  return <div className="page workspace-loading" aria-label="Loading workspace" aria-busy="true" role="status">
    <span className="sr-only">Preparing your workspace.</span>
    <div aria-hidden="true"><div className="skeleton skeleton-eyebrow" /><div className="skeleton skeleton-title" /><div className="skeleton skeleton-subtitle" /><div className="loading-toolbar"><span className="skeleton" /><span className="skeleton" /></div><div className="loading-canvas"><div className="skeleton loading-register" /><div className="loading-copy"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-row" /><div className="skeleton skeleton-subtitle" /></div></div></div>
  </div>;
}
