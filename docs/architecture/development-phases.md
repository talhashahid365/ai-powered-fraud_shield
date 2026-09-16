# Development Phases & Team Ownership

See the master prompt's section "32. Development Phases" for the full
10-phase plan. This scaffold implements the core of Phases 1-6 end-to-end:

- Phase 1 (Foundation): auth, JWT, roles, DB models, initial APIs, frontend
  shell, mock rules/ML — DONE.
- Phase 2 (Transaction System): manual + CSV transactions, listing, search,
  filtering, detail view — DONE.
- Phase 3 (Risk Intelligence): rules engine, feature engineering, Isolation
  Forest, risk decision engine — DONE (train on real data via `ml/training`).
- Phase 4 (AI): AI explanations, investigation assistant — DONE (provider-
  independent, falls back to templates without an LLM key).
- Phase 5 (Investigation): alerts, investigation workspace, notes, customer
  profiles, related transactions, fraud network — DONE (network as list;
  upgrade to interactive graph as noted in overview.md).
- Phase 6 (Dashboard & Reports): charts, fraud trends, statistics, reports,
  CSV export — DONE (PDF/Excel export are natural next additions).
- Phase 7 (Real-Time Processing / Redis workers), Phase 8 (feedback-driven
  model retraining), Phase 9 (security/testing hardening), and Phase 10
  (production deployment) are the recommended next milestones for the team.
