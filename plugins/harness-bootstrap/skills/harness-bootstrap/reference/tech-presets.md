# Tech presets - recommending a CURRENT stack, not a remembered one

A model's knowledge has a cutoff: left to habit it scaffolds Next.js 15 when 16 is out, or pins a
deprecated package. This reference makes version currency a CHECKED step, not a memory, plus compressed
pick-vs-pitfall tables so a proposal is reasoned, not guessed. Read at intake Batch B/F with
[`intake.md`](intake.md).

## The currency rule, first

**Never write a version number from memory into a generated file.** Verify each pinned choice against
the real registry; record BOTH the version found and the date checked in `docs/context/tech-stack.md`.

| Ecosystem | Command |
|---|---|
| npm package | `npm view <pkg> version` (history: `... versions --json`) |
| PyPI package | `pip index versions <pkg>` |
| GitHub-released tool | `gh api repos/<org>/<repo>/releases/latest --jq .tag_name` |
| Own release channel | its docs/changelog page, when it outpaces the registry |

Verified working via `npm view <pkg> version` for next, react, tailwindcss, @tiptap/core, prisma,
vitest, @playwright/test, and via `gh api repos/vercel/next.js/releases/latest --jq .tag_name`. Numbers
omitted on purpose - they'd be stale by the time this file is read.

**No network -> write `unverified`**, never a guess; register a task to check it before relying on the
pin. Row shape: `| next | 16.3.0 | npm view next version | 2026-08-06 |`.

## Presets

Pick the row, never the version - bootstrap fills the version in per the rule above. Pitfall column is
`-` where none is genuinely non-obvious.

### Editors - prose and code

| Pick | When | Pitfall |
|---|---|---|
| TipTap | Most product editors; ProseMirror discipline, easier curve, collab | Some extensions (comments, AI) are paid |
| Lexical | React-first, fine node/perf control on huge docs | Younger, fewer ready extensions |
| ProseMirror | Need schema control TipTap's layer blocks | TipTap already wraps it |
| Slate | Fully custom React doc model | API breaks across versions - repin |
| Quill | Simple formatting box, fast integration | Not schema-extensible |
| Monaco | Code input, IDE-grade (IntelliSense, diff) | Heavy bundle for a plain textarea |
| CodeMirror 6 | Code input, size/mobile matters | v5->v6 rewrite - old snippets don't apply |

Prose vs code picks the family. Prose: collab/schema -> TipTap/ProseMirror, React-scale -> Lexical,
basic -> Quill. Code: IDE-grade -> Monaco, size-constrained -> CodeMirror 6.

### Frontend frameworks and meta-frameworks

| Pick | When | Pitfall |
|---|---|---|
| React + Next.js | Default web app - biggest ecosystem, per-route SSR/SSG/ISR | Confirm App vs Pages router default |
| Vue + Nuxt | Team knows Vue, wants SSR built into templates | Smaller niche-integration ecosystem |
| Svelte + SvelteKit | Bundle/runtime perf over ecosystem breadth | Smaller talent pool/library selection |
| Angular | Large team wants DI/forms/routing + LTS | Steep onboarding |
| Astro | Content-heavy, mostly static, islands | Fights a mostly-interactive app |
| Solid | React-like JSX, smaller runtime | Smallest ecosystem here |

SSR/SSG/SPA: indexable/fast-paint -> SSR/SSG (per-route); near-all-static -> SSG/Astro; interactive +
no-SEO can be SPA, but a meta-framework keeps SSR optional cheaply.

### CSS and component systems

| Pick | When | Pitfall |
|---|---|---|
| Tailwind | Default utility-first | Long class lists on complex components |
| CSS Modules | Plain scoped CSS, no new syntax | No built-in token system |
| vanilla-extract | CSS-in-JS feel, zero runtime | Smaller ecosystem than Tailwind |
| shadcn/ui | Owned/editable source on Radix+Tailwind | Not an npm dep - manual updates |
| Radix | Custom design system, unstyled a11y | Ships zero styling |
| MUI | Need a large pre-styled set fast | Fights a very distinct brand |
| Mantine | Pre-styled, lighter than MUI | Smaller community - check it has the component |
| Chakra | Pre-styled, simple theming | v3 styling engine differs from v2 |
| Ant Design | Enterprise admin/dashboard | Opinionated look unless themed hard |

Headless (Radix) = full control, build visuals yourself. Styled (MUI/Mantine/Chakra/Ant) = finished look
fast. shadcn/ui = owned source on a headless base. Tailwind/Modules/vanilla-extract compose with any.

### Icons

| Pick | When | Pitfall |
|---|---|---|
| Lucide | Default - MIT, tree-shakeable, maintained | - |
| Heroicons | Already on Tailwind's ecosystem | Smaller set than Lucide/Phosphor |
| Phosphor | Need weight variants (thin/bold/duotone) | Verify import path tree-shakes |
| Tabler | Very large, consistent, MIT set | Overlaps Lucide - pick one |
| Font Awesome | Need its brand-logo set | Full set is Pro (paid); free is a subset |
| react-icons | Need multiple sets via one API | Each icon keeps its source licence |

Confirm imports are per-icon, not a barrel import of the whole set.

### State, data fetching, forms, validation

| Pick | When | Pitfall |
|---|---|---|
| TanStack Query | Default server-state cache/refetch/dedup | Don't also add a client store for the same data |
| Zustand | Lightweight client-only state | Not a server cache - pair with Query |
| Redux Toolkit | Complex state, time-travel/middleware, existing investment | More ceremony than Zustand normally needs |
| Jotai | Fine-grained atomic state | Large atom graphs need discipline |
| SWR | Lighter alt to Query | Weaker mutations/devtools than Query |
| React Hook Form | Default form lib, uncontrolled-input perf | Dynamic fields need `useFieldArray` |
| Zod | Default validation, infers TS types | Huge discriminated unions can slow `tsc` |
| Valibot | Bundle size is a hard constraint | Fewer resolver integrations than Zod |
| Yup | Existing codebase already on it | New projects: default to Zod/Valibot |

### Tables, charts, dates

| Pick | When | Pitfall |
|---|---|---|
| TanStack Table | Default headless table logic | Ships zero UI |
| AG Grid | Enterprise grid at scale (pivot, Excel-edit) | Advanced features are commercial-licensed |
| Recharts | Default charting, standard chart types | Struggles at very large datasets |
| visx | Custom non-standard chart types | More code than Recharts for standard cases |
| ECharts | Large built-in chart catalog (maps, 3D) | Confirm type isn't a paid extension in that version |
| date-fns | Default date lib, tree-shakeable | Timezone needs `date-fns-tz` |
| Day.js | Moment-style migration, small core | Most features are opt-in plugins - audit them |
| Temporal | New code, no legacy constraint | Verify runtime/browser support unpolyfilled |

### Testing

| Pick | When | Pitfall |
|---|---|---|
| Vitest | Default for Vite-based/modern JS-TS | Some Jest plugins lack an equivalent |
| Jest | Existing codebase, or non-Vite build | New Vite projects: default to Vitest |
| Playwright | Default E2E, multi-browser, current standard | CI needs `playwright install --with-deps` |
| Cypress | Existing suite investment | Playwright is the default for new setups |
| Testing Library | Default component-level tests | Don't test internal state through it |

### Backend/runtime, ORM, auth

| Pick | When | Pitfall |
|---|---|---|
| Node.js | Default runtime | - |
| Bun | Faster install/test/runtime | Verify native-binding deps work under it |
| Deno | Built-in TS, permissions security | Node-compat layer misses some npm pkgs |
| Fastify | Fast schema-validated HTTP | Smaller plugin ecosystem than Express |
| Hono | One framework, Node/Bun/Deno/edge | Younger, fewer large-scale references |
| NestJS | Large team, DI-based structure | Ceremony overkill for a small service |
| Prisma | Default TS ORM, migrations + typegen | Generated client is a build step everywhere |
| Drizzle | SQL-close, no codegen, full control | More hand code for complex joins |
| TypeORM | Existing codebase already on it | Check maintenance activity first |
| Auth.js | Default Next/JS OAuth, no separate service | Confirm the DB adapter exists |
| Clerk | Managed auth, prebuilt UI | Vendor lock-in on user/session data |
| Lucia | Full control, roll-your-own sessions | More code to own than Clerk/Auth.js |
| Supabase Auth | Already on Supabase DB/backend | Raises cost of migrating off |

### Python (brief)

| Pick | When | Pitfall |
|---|---|---|
| FastAPI | Default new API - async, Pydantic | Confirm the deploy target runs ASGI |
| Django | Content/admin-heavy app | Fights a pure-API microservice shape |
| Flask | Small service, assemble it yourself | Weaker async story than FastAPI |
| SQLAlchemy | Default Python ORM/toolkit | 2.x API differs a lot from 1.x |
| pytest | Default test runner | - |
| ruff | Default lint/format (was flake8+isort+black) | Some flake8 rules lack an equivalent |
| uv | Default package/env manager, fast | Migrating off Poetry/pip-tools is a real decision |

## Greenfield vs brownfield - who wins

**Greenfield**: this file is the DEFAULT proposal - present the pick and its checked version, confirm
before writing `tech-stack.md`. **Brownfield**: [`codebase-analysis.md`](codebase-analysis.md) wins,
always. A preset contradicting what's installed is never a silent override - it becomes a
migration-backlog task (Phase F), noted in `docs/context/known-issues.md`.

## Licence awareness

Flag these at intake, tied to `ip-compliance.md`'s allow/deny table (`{{ALLOWED_LICENCES}}` /
`{{DENIED_LICENCES}}`): **AG Grid** Community (MIT) vs Enterprise (paid - scale pivoting, Excel-style
edit). **Font Awesome** Free (subset) vs Pro (paid, leaks through react-icons too). **ECharts**
(Apache-2.0, free) vs **Highcharts** (source-available, commercial licence for most commercial use) -
not interchangeable defaults. Any of these in a dependency change goes through `ip-compliance.md`'s
"check on a diff": state the package, licence, and which row it lands in. No row cited, no add.
