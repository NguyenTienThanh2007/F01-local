import type { ProjectPlan } from '@/lib/planning/contracts';

export function PlanView({ plan }: { plan: ProjectPlan }) {
  return <article className="plan-document" aria-labelledby="plan-title">
    <header className="plan-document-heading">
      <div className="plan-document-topline"><span className="meta">PROJECT / FIRST EDITION</span><span className="meta">DRAFT PLAN</span></div>
      <h2 id="plan-title">{plan.project_title}</h2>
      <p>{plan.product_summary}</p>
      <div className="plan-facts"><span><strong>{plan.core_features.length}</strong> core features</span><span><strong>{plan.implementation_milestones.length}</strong> milestones</span><span>Ready for your review</span></div>
    </header>
    <section className="plan-section" aria-labelledby="users-title">
      <div className="plan-section-label"><span className="meta">01 / AUDIENCE</span><h3 id="users-title">Target users</h3></div>
      <ul className="plan-users">{plan.target_users.map((user, index) => <li key={index}>{user}</li>)}</ul>
    </section>
    <section className="plan-section" aria-labelledby="features-title">
      <div className="plan-section-label"><span className="meta">02 / SCOPE</span><h3 id="features-title">Core features</h3></div>
      <ol className="plan-features">{plan.core_features.map((feature, index) => <li key={index}>
        <span className="plan-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
        <div><h4>{feature.name}</h4><p>{feature.description}</p></div>
      </li>)}</ol>
    </section>
    <section className="plan-section" aria-labelledby="stack-title">
      <div className="plan-section-label"><span className="meta">03 / FOUNDATION</span><h3 id="stack-title">Recommended stack</h3></div>
      <dl className="plan-stack">
        <div><dt>Frontend</dt><dd>{plan.recommended_stack.frontend}</dd></div>
        <div><dt>Backend</dt><dd>{plan.recommended_stack.backend}</dd></div>
        <div><dt>Database</dt><dd>{plan.recommended_stack.database}</dd></div>
      </dl>
      <p className="stack-rationale">{plan.recommended_stack.rationale}</p>
    </section>
    <section className="plan-section" aria-labelledby="milestones-title">
      <div className="plan-section-label"><span className="meta">04 / SEQUENCE</span><h3 id="milestones-title">Implementation milestones</h3></div>
      <ol className="plan-milestones">{plan.implementation_milestones.map((milestone, index) => <li key={index}>
        <span className="plan-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
        <div><h4>{milestone.title}</h4><ul>{milestone.deliverables.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}</ul></div>
      </li>)}</ol>
    </section>
    <footer className="plan-document-footer">Draft plan · Not saved · No build started</footer>
  </article>;
}
