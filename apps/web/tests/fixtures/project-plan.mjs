export const projectPlan = {
  project_title: 'Harbor CRM',
  product_summary: 'Manage a small real estate agency’s leads and sales pipeline.',
  target_users: ['Real estate agents', 'Agency managers'],
  core_features: [
    { name: 'Authentication', description: 'Sign in and manage access.' },
    { name: 'Leads', description: 'Record prospects and follow-up notes.' },
  ],
  recommended_stack: {
    frontend: 'Next.js, React, TypeScript, Tailwind CSS',
    backend: 'FastAPI, Python', database: 'PostgreSQL',
    rationale: 'A maintainable web stack with relational data and clear API boundaries.',
  },
  implementation_milestones: [
    { title: 'Foundation', deliverables: ['Project scaffold', 'Identity boundary'] },
    { title: 'CRM workflows', deliverables: ['Lead records', 'Pipeline views'] },
  ],
};
