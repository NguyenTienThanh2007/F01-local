'use client';
export default function Error({ reset }: { reset: () => void }) { return <div className="workspace-document"><h2>This project surface could not be opened.</h2><p>Your saved records remain on the server.</p><button className="button button-secondary" onClick={reset}>Retry surface</button></div>; }
