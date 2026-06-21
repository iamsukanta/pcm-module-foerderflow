# Migration Decisions (confirmed by stakeholder, 2026-06-16)

1. **Auth model:** Magic-link → JWT. Keep passwordless email login (parity with monolith
   UX + GDPR rationale), issue JWT access tokens after email verification. No passwords.
2. **Frontend data fetching:** SSR via BFF. Next.js Server Components call the FastAPI
   REST API; TanStack Query for client-side mutations/lists. Preserves SSR/page behavior.
3. **Execution:** Start Phase 0 (scaffolding) + Phase 1 (full data layer), iterate with
   per-phase verification against the monolith.
