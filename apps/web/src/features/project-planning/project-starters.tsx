export const projectStarters = [
  { id: 'crm', number: '01', category: 'Business tool', title: 'A clearer sales pipeline', short: 'CRM', brief: 'Build a browser-only CRM for a small real estate agency. Show a leads register, pipeline stages, notes and a priority filter using browser state. No server, shared database or authentication is required.' },
  { id: 'booking', number: '02', category: 'Operations', title: 'Fewer missed appointments', short: 'Booking', brief: 'Build a browser-only studio schedule to reduce missed appointments. Show a daily agenda, appointment details and availability using browser state. No server or reminder service is required.' },
  { id: 'game', number: '03', category: 'Browser game', title: 'One more round', short: 'Game', brief: 'Build a simple browser game where players navigate a geometric maze, collect checkpoints and beat their best time, with keyboard controls and a restart button.' },
] as const;

export type StarterId = typeof projectStarters[number]['id'];

export function ProjectStarters({ selected, onSelect, disabled = false, categoryFirst = false }: {
  selected?: StarterId; onSelect: (id: StarterId, brief: string) => void; disabled?: boolean; categoryFirst?: boolean;
}) {
  return <div className="project-starters" aria-label="Project starters">
    <div className="starter-heading"><span className="meta">OR START WITH A DIRECTION</span><span className="meta">01—03</span></div>
    {projectStarters.map(starter => <button key={starter.id} type="button" disabled={disabled}
      className={`starter-row starter-${starter.id}`} aria-pressed={selected === starter.id}
      onClick={() => onSelect(starter.id, starter.brief)}>
      <span className="starter-mark" aria-hidden="true"><i /><i /><i /></span>
      <span className="starter-description"><span>{categoryFirst ? `${starter.short} / ${starter.category}` : starter.title}</span><small>{categoryFirst ? starter.title : starter.category}</small></span>
      <span className="starter-arrow" aria-hidden="true">↗</span>
    </button>)}
  </div>;
}
