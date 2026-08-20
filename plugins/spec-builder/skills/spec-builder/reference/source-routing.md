# Source routing - reading the documents before eliciting against them

You cannot elicit against a document you have not read, and you cannot tell a document you
read badly from one you read well by looking at the output. `scripts/route_sources.py`
decides which reader owns each source and prints a reason per decision;
`scripts/ingest.py` executes one entry of that plan.

```bash
python scripts/route_sources.py <files-folders-urls> --out-dir <dir> -o <dir>/plan.json
python scripts/ingest.py <source> --via native --out <dir>/source.txt
```

The router runs its own policy table on every invocation before it touches a file, so a
routing bug surfaces in milliseconds rather than after twelve extractions.

## Routing table

| Format | Text strategy | Kept | Lost |
|---|---|---|---|
| `.pdf`, real text layer | `native` (pymupdf) | page boundaries, reading order | layout, colour, anything drawn rather than written |
| `.pdf`, scanned or flat | **`vision`** | everything a human eye sees | copy-paste fidelity; costs the most |
| `.docx` | `native` (python-docx) | paragraphs, table rows | page numbers - a .docx has none before rendering |
| `.pptx` | `native` (python-pptx) | slide boundaries, table cells, grouped shapes | positions, diagram geometry |
| `.xlsx` / `.xlsm` | `anydoc` when installed, else `markitdown`, else `native` (openpyxl) | Markdown tables (engines) or sheet-tagged rows (openpyxl) | cell addresses; formulas (values only) |
| `.doc` `.ppt` `.xls` `.rtf` `.odt` `.ods` `.odp` `.xlsb` | `anydoc`, else `markitdown` | text, tables | page and slide boundaries |
| `.html` `.csv` `.json` `.xml` `.msg` `.eml` `.epub` `.ipynb` `.zip` | `markitdown` | clean Markdown, broad coverage | structure, position |
| images | `vision` | everything visible | no text layer exists at all |
| `.md` `.txt` `.log` | `read` | the bytes | nothing |
| `http(s)://` | `markitdown` | fetched and converted | whatever the page renders in script |
| anything else | `markitdown`, then report | - | reported by name, never assumed empty |

Visual output is narrow on purpose: pages are rasterized **only** when the text strategy is
`vision`. A readable document gains nothing from a PNG of itself, and rendering everything
is how a routing step turns into an image pipeline.

## The 80-chars-per-page rule

`TEXT_LAYER_MIN_CHARS_PER_PAGE = 80`. A PDF whose extracted text averages fewer than 80
characters per page is treated as having no text layer.

The number matters because a scanned PDF does not fail. It returns a few characters per
page and an exit code of zero. A model handed that, about a file the user called "the
requirements", writes plausible requirements - which is the never-invent failure arriving
through the file reader instead of through the interview. Both scripts apply the threshold:
the router routes to `vision`, and `ingest.py --via native` refuses the same PDF rather than
hand back near-empty text.

## Overrides

- `--prefer-markitdown` - one uniform Markdown layer across a mixed pile, when consistency
  matters more than page boundaries.
- `--prefer-native` - force the object-model readers for Office formats.
- `ingest.py --via <strategy>` - run any single source through any reader; the plan's choice
  is a default, not a lock.
- `--via vision --render <dir>` - rasterize and read the pixels, for a source whose text
  layer you have decided not to trust.

## When a reader is missing

Optional dependencies are all optional. A missing one changes the route and names what was
lost; it never crashes and never skips a file quietly.

```
pip install pymupdf python-docx python-pptx openpyxl   # the native readers
pip install firecrawl-anydoc                           # legacy Office, ODF, RTF, spreadsheets
pip install 'markitdown[all]'                          # HTML, CSV, JSON, MSG, EPUB, URLs
```

`route_sources.py` prints which of these it found, and every degraded route says which
install would improve it.

## Unreadable is a finding, not a gap

When nothing installed can read a source, the route is `unreadable` and `ingest.py` exits 2
with the reason. That source becomes an `OI-nn` in section 11 naming the file, why it could
not be read, and what would make it readable - a pip install, or a re-export request to the
user. It is never dropped from the pile, and its content is never guessed at from its
filename. Same discipline the skill already applies to unstated requirements, extended down
to the file-reading layer.

An empty extraction gets the same treatment: `ingest.py` warns on zero characters, because
an empty result is not evidence of an empty document.

## Limits

What this deliberately does **not** do, and why:

- **No knowledge base.** The mechanism here is distilled from the `docs-to-knowledge` skill,
  whose output contract is a rendered knowledge base with an audit-review loop. That skill's
  `render_knowledge.py`, `gen_audit_review.py`, its knowledge schema and its audit playbook
  were left behind on purpose: spec-builder's output contract is its numbered sections. For
  a genuinely large, diagram-dense, cross-checking job, run that skill and feed spec-builder
  its output.
- **No diagram reconstruction, no page-versus-text cross-check.** Extracted text is taken as
  the source; nothing here compares it against the pixels. A diagram-heavy deck whose meaning
  lives in arrows is a case for a vision read or for `docs-to-knowledge`.
- **No OCR.** `vision` means a model reads the rendered pages. There is no OCR engine in this
  skill, and markitdown does not OCR PDFs either.
- **No format conversion.** Legacy binary Office is read where a reader exists; it is never
  converted in place, and LibreOffice is not shelled out to.
- **Unsupported formats are reported, not skipped.** An extension nothing recognises is
  routed to markitdown and, if that also fails, named in the plan and in the run's output.
  A file that appears in the plan and produced no text is an `OI-nn`, every time.
