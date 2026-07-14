---
# {{SOURCE_GLOBS}} expands to one quoted glob per line, e.g. "src/**/*.{ts,tsx}"
paths:
  - "{{SOURCE_GLOBS}}"
---

# Performance

Applies when writing or reviewing source. Severity comes from the shared model in code-quality.md,
and is not redefined here: Blocker = falls over in normal operation now; Major = guaranteed to
degrade under realistic growth or load; Minor = wasteful but bounded; Info = observation.
Performance findings that are also security findings (leaky logging, unbounded fan-out to a paid
API) cross-file to security-privacy.md.

## Rule zero: measure before claiming

A performance finding needs ONE of:

1. **A measurement**: a timing, a query count, a bundle-size number, a profiler capture - taken
   from this repo or its own tooling.
2. **A structural argument**: complexity that grows with data (an O(n^2) join in code, an N+1
   query, unbounded fan-out, a full-table scan on a known-growing table). Structure is acceptable
   evidence because the failure is guaranteed by shape; only its DATE is unknown.

Anything else ("this looks slow", "X is faster than Y in general") is a suggestion - report it as
Info, or not at all. Micro-optimizations without measurement are noise.

State the scale assumption in every finding: "at 10k orders this query does 10k+1 round trips" is
checkable; "this is slow" is not.

## Backend and API

| Pattern | Cheap detection | Why it hurts |
|---------|-----------------|--------------|
| N+1 queries via ORM lazy relations | Loop bodies that touch a relation (`order.customer.name` inside `for order of orders`); ORM logs showing repeated identical-shape queries | 1 list query plus N detail queries; latency scales linearly with rows returned |
| Per-item await inside loops | Grep `for` and `map` bodies containing `await` on a database or HTTP call | Serializes independent I/O; 100 items at 50ms each is 5s where one batched call would be 50ms |
| `Promise.all` over unbounded arrays | `Promise.all(items.map(...))` where `items` comes from a query or request with no cap | The opposite failure: unbounded concurrency exhausts the connection pool or trips the provider's rate limit. Needs batching or a concurrency limiter |
| Missing pagination | List endpoints with no limit, cursor, or offset parameter; a find-many or `SELECT *` with no take or LIMIT | Response size grows with the table forever; works in dev with 50 rows, times out in production with 500k |
| Missing indexes versus actual query shape | Collect the real WHERE, ORDER BY, and JOIN columns from ORM calls and raw SQL, then diff against the schema's indexes. Index against the QUERY SHAPE, not "index every column" | Full scans on growing tables. Confirm with an execution plan before claiming, per rule zero |
| Connection pool never sized | Pool configuration absent (ORM default) while the app runs multiple instances or serverless | Defaults times instance count can exceed the database's connection limit, or a tiny pool serializes requests. Either way p99 spikes under load |
| External-call fan-out | One inbound request triggering many outbound API calls (a loop over items, one call each) | Latency equals the slowest callee times the depth; cost and rate-limit exposure scale with traffic |
| A concurrency limiter or retry-with-backoff already in the code | Grep for limiter, throttle, retry, backoff libraries | **A signal, not a sin**: someone already hit throughput pain and patched the symptom. Find WHICH callee forced it - that is where the real finding lives (a batch API? a cache? a queue?) |
| Two uncoordinated cache layers | An in-memory map or LRU in app code AND a shared cache for the same entities, with no shared invalidation | A staleness bug by construction: instance A writes and invalidates the shared cache, instance B still serves its stale local copy for its full TTL. Users see values flip depending on which instance answers |
| Materialized views or summary tables as a symptom | Migrations creating summary or rollup tables; cron jobs rebuilding aggregates | A legitimate technique, but its PRESENCE means the base query shape already lost. Check whether the refresh cadence and staleness window are documented and acceptable |

## Frontend and web

| Pattern | Cheap detection | Why it hurts |
|---------|-----------------|--------------|
| Duplicate-purpose dependencies | Read the manifest for more than one chart library, date library, rich-text editor, or UI kit | Each duplicate ships its full weight to every user; two chart libraries is easily 300-600 KB of parse cost for zero capability gained |
| No route-level code splitting | A single entry importing every page eagerly; no lazy or dynamic imports, no route chunks in the build output | First paint pays for the whole app; the settings page's editor blocks the landing page |
| Long lists without virtualization | A map rendering unbounded query results straight into the DOM | 5k DOM nodes is a slow initial render AND a slow every-subsequent-interaction (layout, memory) |
| Framework dev checks disabled | Strict-mode or equivalent turned off in the framework config | Not a performance bug itself - it HIDES double-invoked effects, unsafe lifecycles, and leaked subscriptions that surface later as performance mysteries. Report as Info, with what it masks |
| Render-blocking work | Heavy synchronous computation in the render path; third-party scripts loaded head-blocking without async or defer | The main thread is the only thread; every blocked millisecond is frozen input |
| Unoptimized images | Raw image tags for large assets, no width or height (layout shift), no modern format or responsive sizes, hero images not preloaded | Commonly the single largest LCP contributor, and the cheapest big win on most sites |

Bundle claims follow rule zero: run the build and read the size report before stating numbers.

## Mobile

| Pattern | Cheap detection | Why it hurts |
|---------|-----------------|--------------|
| Eager lists instead of a builder or virtualized list | A list widget fed a fully materialized child array instead of a lazy builder | Builds every row up front; jank and memory growth proportional to list length |
| Full-resolution images into small slots | Image widgets with no decode-size or resize hint; multi-MB assets shown as thumbnails | Decoded bitmaps live in RAM at FULL size regardless of display size; a prime cause of OOM kills and scroll jank |
| Over-broad observable or state wrappers | One store or provider holding whole-app state; an observer or consumer at the screen root | Any field change rebuilds the whole screen; death by a thousand rebuilds that no single profile explains |
| Main-thread work | JSON parsing of large payloads, crypto, or image processing on the UI thread with no isolate or worker | Directly drops frames; the budget is about 16ms per frame at 60fps |
| Verbose logging interceptor left on in release | HTTP client interceptors logging full request and response bodies, not gated on a debug or build flag | Serializes every payload twice (performance) AND writes tokens and personal data to device logs - **also file this under security-privacy.md** |

## Infrastructure and cloud

| Pattern | Cheap detection | Why it hurts |
|---------|-----------------|--------------|
| Instance sizing by vibes | IaC instance types with no utilization data behind them | Oversized burns money silently; undersized burns latency loudly. Either way, check monitoring before recommending a change (rule zero) |
| Network and availability defaults left unexamined | IaC: a NAT gateway per AZ versus one shared; a single-AZ database in production | These are TRADE-OFFS (cost versus availability). The finding is that the trade-off is undocumented or contradicts the stated availability target, not the choice itself |
| Database engine left on defaults | The managed database's parameter group untouched; performance insights or the slow-query log disabled | Defaults assume a generic workload, and with insights off every database performance question becomes guesswork. Enabling them is the prerequisite to all other database findings |
| Adding capacity before checking cache hit rate | Scaling changes adding replicas while the cache or CDN hit rate is unmeasured or below ~80% | A cache-miss problem survives any amount of hardware; hit rate is a one-line metric read and always the cheaper first check |

## Symptom, cause, confirmation

| Symptom | Likely cause | Cheap confirmation |
|---------|--------------|--------------------|
| A list endpoint slows as data grows | N+1 or a missing index | Enable query logging, hit the endpoint once, count queries; get the execution plan for the slow one |
| p99 spikes under load, p50 fine | Pool exhaustion or lock contention | Pool metrics; the database's connection limit versus instances times pool size |
| One page slow, the rest fine | A route-level bundle or one heavy component | Build-size report per route; a browser performance profile on that route |
| The whole UI slows after weeks of use | Unbounded in-memory cache or state growth | Heap snapshot at start versus an hour in |
| Mobile scroll jank on lists | Eager list build or full-resolution images | Switch one screen to a builder and a decode-size hint; measure frame times before and after |
| The same query is fast, then slow, alternating | Two uncoordinated cache layers serving different generations | Read the same key through both layers after a write; the values differ |
| The cloud bill grows faster than traffic | Fan-out to paid APIs, chatty cross-AZ traffic, or oversized instances | Cost breakdown by service, correlated with request counts |

## Output contract

The code-quality.md contract applies (location, one-sentence defect, concrete scenario, severity,
direction, no patch), plus one performance-specific field: **evidence type**, either
`measured: <number>` or `structural: <argument>`. A finding with neither does not ship.
