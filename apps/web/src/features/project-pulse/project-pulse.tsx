export type Lifecycle = 'idle' | 'understanding' | 'planning' | 'building' | 'verifying' | 'deploying' | 'live' | 'error';
export type PulseState = Lifecycle | 'thinking' | 'shipping';
export const lifecycleLabels: Record<PulseState, string> = { idle: 'Idle', understanding: 'Understanding', planning: 'Planning', thinking: 'Thinking', building: 'Building', verifying: 'Verifying', deploying: 'Deploying', shipping: 'Shipping', live: 'Live', error: 'Error' };
export function PulseMark() {
  return <svg className="pulse-mark" viewBox="0 0 48 48" fill="none" aria-hidden="true"><path className="pulse-branch pulse-branch-one" d="M8 36V14H16" /><path className="pulse-branch pulse-branch-two" d="M20 40V8H28" /><path className="pulse-branch pulse-branch-three" d="M32 36V20H40" /><path className="pulse-ground" d="M5 44H43" /><rect x="13" y="11" width="6" height="6" /><rect x="25" y="5" width="6" height="6" /><rect x="37" y="17" width="6" height="6" /></svg>;
}

export function ProjectPulse({ state, label, animate = false, variant = 'compact' }: { state: PulseState; label?: string; animate?: boolean; variant?: 'compact' | 'instrument' }) {
  return <span className={`project-pulse pulse-${state} ${animate ? 'pulse-animated' : ''} pulse-${variant}`}>
    {variant === 'instrument' ? <PulseMark /> : <span className="pulse-strokes" aria-hidden="true"><i /><i /><i /></span>}<span>{label ?? lifecycleLabels[state]}</span>
  </span>;
}
