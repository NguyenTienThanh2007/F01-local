import type { StarterId } from '@/features/project-planning/project-starters';

export function SampleInterface({ starter }: { starter: StarterId }) {
  if (starter === 'game') return <div className="sample-game">
    <div className="sample-game-heading"><span>CHECKPOINT</span><span className="meta">BEST 00:42</span></div>
    <div className="game-field" aria-label="Static geometric maze illustration"><span className="game-route" /><span className="game-player" /><span className="game-goal">×</span></div>
    <div className="sample-game-footer"><span className="meta">LEVEL 01 / THE WAY THROUGH</span><span className="meta">ILLUSTRATION</span></div>
  </div>;
  if (starter === 'booking') return <div className="sample-booking">
    <div className="sample-heading"><span className="sample-brand">Studio / daybook</span><span className="meta">MONDAY, 12 OCT</span></div>
    <div className="sample-title"><h3>A little room to breathe.</h3><p>Today’s schedule</p></div>
    <div className="booking-schedule">{[['09:00', 'Morning session', 'Mia Chen'], ['10:30', 'Private appointment', 'Jordan Lee'], ['13:00', 'Afternoon session', 'Alex Morgan']].map(([time, title, name]) => <div key={time}><span className="meta">{time}</span><div><strong>{title}</strong><small>{name}</small></div><span className="booking-line" /></div>)}</div>
  </div>;
  return <div className="sample-crm">
    <div className="sample-heading"><span className="sample-brand">Harbor / CRM</span><span className="meta">SALES PIPELINE</span></div>
    <div className="sample-title"><h3>Good relationships.<br />Clear next steps.</h3><p>Your agency, at a glance.</p></div>
    <div className="sample-metrics"><div><span className="meta">OPEN LEADS</span><strong>24</strong></div><div><span className="meta">PIPELINE</span><strong>$148k</strong></div><div><span className="meta">THIS WEEK</span><strong>08</strong></div></div>
    <div className="sample-pipeline">{[['New', 'Westside apartment', 'Mia Chen'], ['In conversation', 'Oceanview residence', 'Jordan Lee'], ['Ready to close', 'Parkside townhouse', 'Alex Morgan']].map(([stage, property, name]) => <div key={stage}><span className="meta">{stage}</span><div><strong>{property}</strong><small>{name}</small><span className="sample-card-rule" /></div></div>)}</div>
  </div>;
}

