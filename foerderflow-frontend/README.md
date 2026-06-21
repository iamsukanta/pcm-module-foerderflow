# FörderFlow Frontend (Next.js)

Separated frontend for FörderFlow. Communicates with the FastAPI backend over REST
(SSR-via-BFF: Server Components call the backend; TanStack Query for client data).

## Stack
Next.js 15 (App Router, React 19) · TypeScript (strict) · TailwindCSS · TanStack Query ·
Axios · React Hook Form · Zod · Zustand · lucide-react

## Feature-based structure
```
src/
├── app/         App Router routes + root layout/globals
├── features/    domain modules (foerdermassnahmen, transaktionen, personal, ...)
├── components/  shared UI (components/ui = design-system primitives)
├── services/    API abstraction layer (Axios client + typed resource services)
├── hooks/       shared hooks (TanStack Query wrappers, auth/org context)
├── lib/         framework glue (cn, query keys)
├── types/       shared types (generated from backend OpenAPI)
├── providers/   React context providers (QueryProvider, ...)
├── layouts/     dashboard + admin shells (SidebarNav / AdminSidebar)
└── utils/       pure helpers (German currency/number/date formatting)
```

## Design system
Soft-Depth, ported verbatim from the monolith (`BRAND.md`). Tokens live in
`tailwind.config.ts` + `src/app/globals.css`. Rules: only `soft-*` colors (no default
Tailwind palette, no hex), IBM Plex Sans/Mono, `.numeric` for all numbers, lucide-react
icons only, import primitives from `components/ui`.

## Local development
```bash
npm install
cp .env.example .env.local
npm run dev        # http://localhost:3000
```

## Quality
```bash
npm run typecheck && npm run lint && npm test
```

## Migration status
Phase 0 (scaffold) done. Pages/components/features ported in Phase 4. See
`../docs/02-migration-roadmap.md`.
