# Performance review - knowledge base (project-bootstrap)

Loaded by the `perf-reviewer` agent (and the orchestrator in audit mode - see
[audit-mode.md](audit-mode.md)). Uses the shared severity model from
[code-quality-review.md](code-quality-review.md); security-adjacent findings cross-file to
[security-review.md](security-review.md). Organized by surface: backend/API, frontend/web, mobile,
infra/cloud.

## Table of contents

- [Rule zero: measure before claiming](#rule-zero-measure-before-claiming)
- [Backend / API](#backend--api)
- [Frontend / web](#frontend--web)
- [Mobile](#mobile)
- [Infra / cloud](#infra--cloud)
- [Symptom -> cause -> confirmation](#symptom---cause---confirmation)
- [Output contract](#output-contract)

## Rule zero: measure before claiming

A perf finding needs ONE of:

1. **A measurement**: a timing, a query count, a bundle-size number, a profiler capture - from this
   repo or its tooling.
2. **A structural argument**: algorithmic complexity that grows with data (O(n^2) join in code,
   N+1 query, unbounded fan-out, full-table scan against a known-growing table). Structure is
   acceptable evidence because the failure is guaranteed by shape, only its DATE is unknown.

Anything else ("this looks slow", "X is faster than Y in general") is a **suggestion** - report it
as Info or not at all. Micro-optimizations without measurement are noise. Severity follows the
shared model: Blocker = falls over in normal operation now; Major = guaranteed to degrade under
realistic growth/load; Minor = wasteful but bounded; Info = observation.

State the scale assumption in every finding: "at 10k orders this query does 10k+1 round trips" is
checkable; "this is slow" is not.

## Backend / API

| Pattern | Cheap detection | Why it hurts |
|---------|-----------------|--------------|
| N+1 queries via ORM lazy relations | Loop bodies that touch a relation (`order.customer.name` inside `for order of orders`); ORM logs showing repeated identical-shape queries | 1 list query + N detail queries; latency scales linearly with rows returned |
| Per-item await inside loops | Grep `for` / `map` bodies containing `await` on a DB or HTTP call | Serializes independent I/O; 100 items x 50ms = 5s where one batched call would be 50ms |
| `Promise.all` over unbounded arrays | `Promise.all(items.map(...))` where `items` comes from a query/request with no cap | Opposite failure: unbounded concurrency exhausts the connection pool or trips the provider's rate limit; needs batching or a concurrency limiter |
| Missing pagination | List endpoints with no `limit`/`cursor`/`offset` param; `findMany()`/`SELECT *` with no `take`/`LIMIT` | Response size grows with the table forever; works in dev with 50 rows, times out in prod with 500k |
| Missing indexes vs actual query shape | Collect the real WHERE/ORDER BY/JOIN columns from ORM calls and raw SQL, diff against schema indexes (`@@index`, `CREATE INDEX`). Index-vs-QUERY-SHAPE, not "index every column" | Full scans on growing tables; confirm with `EXPLAIN` before claiming, per rule zero |
| Connection pool never sized | Pool config absent (ORM default) while the app runs multiple instances/serverless | Defaults x instance count can exceed the DB's `max_connections`, or a tiny pool serializes requests; either way p99 spikes under load |
| External-call fan-out | One inbound request triggering many outbound API calls (loop over items -> one call each) | Latency = slowest callee x depth; cost and rate-limit exposure scale with traffic |
| `p-limit` / retry-with-backoff already in the code | Grep `p-limit`, `bottleneck`, `retry`, `backoff` | **A signal, not a sin**: someone already hit throughput pain and patched the symptom. Find WHICH callee forced it - that is where the real finding lives (batch API? cache? queue?) |
| Two uncoordinated cache layers | In-memory `Map`/LRU in app code AND Redis for the same entities, no shared invalidation | Staleness bug by construction: instance A writes and invalidates Redis, instance B still serves its stale local copy for its full TTL; users see values flip depending on which instance answers |
| Materialized views / summary tables as symptom | Migrations creating `*_summary`, `*_mv`, cron jobs rebuilding aggregates | Legitimate technique, but its PRESENCE means the base query shape already lost; check whether the refresh cadence and staleness window are documented and acceptable |

## Frontend / web

| Pattern | Cheap detection | Why it hurts |
|---------|-----------------|--------------|
| Duplicate-purpose dependencies | Read `package.json` for >1 chart lib, >1 date lib, >1 rich-text editor, >1 UI kit (the canonical bundle-audit finding) | Each duplicate ships its full weight to every user; two chart libs is easily 300-600 KB of parse cost for zero capability gained |
| No route-level code splitting | Single entry importing every page eagerly; no `dynamic()` / `lazy()` / route chunks in build output | First paint pays for the whole app; the settings page's editor blocks the landing page |
| Long lists without virtualization | `.map()` rendering unbounded query results straight into the DOM | 5k DOM nodes = slow initial render AND slow every subsequent interaction (layout, memory) |
| `reactStrictMode: false` (or equivalent dev-checks disabled) | Framework config | Not a perf bug itself - it HIDES double-invoked-effect bugs, unsafe lifecycles, and leaked subscriptions that surface later as perf mysteries; report as Info with what it masks |
| Render-blocking work | Heavy sync computation in components/render path; third-party scripts loaded head-blocking without `async`/`defer` | Main thread is the only thread; every blocked ms is frozen input |
| Unoptimized images | Raw `<img>` for large assets, no width/height (layout shift), no modern format/responsive sizes, hero images not preloaded | Commonly the single largest LCP contributor; cheapest big win on most sites |

Bundle claims follow rule zero: run the build and read the size report / analyzer output before
stating numbers.

## Mobile

| Pattern | Cheap detection | Why it hurts |
|---------|-----------------|--------------|
| Eager lists instead of builder/virtualized | `ListView(children: ...)` vs `ListView.builder` (Flutter); `ScrollView`+map vs `FlatList` (RN); `Column` fed a mapped full list | Builds every row up front; jank and memory growth proportional to list length |
| Full-resolution images into small slots | Image widgets with no `cacheWidth`/`cacheHeight`/resize; multi-MB assets shown as thumbnails | Decoded bitmaps live in RAM at FULL size regardless of display size; prime cause of OOM kills and scroll jank |
| Over-broad observable/state wrappers | One store/provider holding whole-app state; screen-root `Observer`/`Consumer`/`setState` at the top of the tree | Any field change rebuilds the whole screen; death by a thousand rebuilds that no single profile explains |
| Main-thread work | JSON parsing of large payloads, crypto, image processing on the UI thread (no isolate/worker) | Directly drops frames; 16ms budget per frame at 60fps |
| Verbose logging interceptor left on in release | HTTP client interceptors logging full request/response bodies, not gated on debug/build flag | Serializes every payload twice (perf) AND writes tokens/PII to device logs - **also file this under [security-review.md](security-review.md)** |

## Infra / cloud

| Pattern | Cheap detection | Why it hurts |
|---------|-----------------|--------------|
| Instance sizing by vibes | IaC instance types with no utilization data behind them | Oversized burns money silently; undersized burns latency loudly; either way check monitoring before recommending a change (rule zero) |
| NAT gateway / single-AZ as unexamined defaults | IaC: NAT per AZ vs one shared; single-AZ DB in prod | These are TRADE-OFFS (cost vs availability); the finding is when the trade-off is undocumented or contradicts the stated availability target, not the choice itself |
| DB engine left on defaults | RDS/managed-DB parameter group untouched; Performance Insights / slow-query log disabled | Defaults assume a generic workload; with insights off, every DB perf question becomes guesswork - enabling them is the prerequisite to all other DB findings |
| Adding capacity before checking cache hit rate | Scaling tickets/IaC diffs adding replicas while Redis/CDN hit rate is unmeasured or < ~80% | A cache-miss problem survives any amount of hardware; hit rate is a one-line metric read and always the cheaper first check |

## Symptom -> cause -> confirmation

| Symptom | Likely cause | Cheap confirmation |
|---------|--------------|--------------------|
| List endpoint slows as data grows | N+1 or missing index | Enable ORM query logging, hit endpoint once, count queries; `EXPLAIN` the slow one |
| p99 spikes under load, p50 fine | Pool exhaustion or lock contention | Pool metrics / DB `max_connections` vs instances x pool size |
| One page slow, rest fine | Route-level bundle or heavy component | Build-size report per route; browser performance profile on that route |
| Whole UI slow after weeks of use | Unbounded in-memory cache/state growth | Heap snapshot at t0 vs t+1h |
| Mobile scroll jank on lists | Eager list build or full-res images | Switch one screen to builder/virtualized + `cacheWidth`; measure frame times before/after |
| Same query fast then slow, alternating | Two uncoordinated cache layers serving different generations | Read the same key via both layers after a write; values differ |
| Cloud bill grows faster than traffic | Fan-out to paid APIs, chatty cross-AZ traffic, or oversized instances | Cost explorer grouped by service; correlate with request counts |

## Output contract

Same contract as [code-quality-review.md](code-quality-review.md) - file:line, one-sentence defect,
concrete scenario, severity, direction, no patches - plus one perf-specific field: **evidence type**
(`measured: <number>` or `structural: <argument>`). A finding with neither field does not ship.
