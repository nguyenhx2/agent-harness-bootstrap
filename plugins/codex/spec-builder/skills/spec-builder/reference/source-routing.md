# Source routing - reading the documents before eliciting against them

`scripts/route_sources.py` picks the reader for each source and prints a reason per decision;
`scripts/ingest.py` executes one entry of that plan.

```bash
python scripts/route_sources.py <files-folders-urls> --out-dir <dir> -o <dir>/plan.json
python scripts/ingest.py <source> --via native --out <dir>/source.txt
```

The router self-tests its policy table before touching a file.

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

Pages are rasterized **only** when the text strategy is `vision`.

## The 80-chars-per-page rule

`TEXT_LAYER_MIN_CHARS_PER_PAGE = 80`. A PDF whose extracted text averages fewer than 80
characters per page is treated as having no text layer.

A scanned PDF does not fail: it returns a few characters per page and exit 0, and a model handed
that writes plausible requirements. Both scripts apply the threshold: the router routes to
`vision`, and `ingest.py --via native` refuses the same PDF.

## Overrides

- `--prefer-markitdown` - one uniform Markdown layer across a mixed pile, when consistency
  matters more than page boundaries.
- `--prefer-native` - force the object-model readers for Office formats.
- `ingest.py --via <strategy>` - run any single source through any reader; the plan's choice
  is a default, not a lock.
- `--via vision --render <dir>` - rasterize and read the pixels, for a source whose text
  layer you have decided not to trust.

## When a reader is missing

A missing optional dependency changes the route and names what was lost; it never crashes and
never skips a file quietly.

```
pip install pymupdf python-docx python-pptx openpyxl   # the native readers
pip install firecrawl-anydoc                           # legacy Office, ODF, RTF, spreadsheets
pip install 'markitdown[all]'                          # HTML, CSV, JSON, MSG, EPUB, URLs
```

`route_sources.py` prints which of these it found, and every degraded route says which
install would improve it.

## Unreadable is a finding, not a gap

When nothing installed can read a source, the route is `unreadable` and `ingest.py` exits 2
with the reason. The source becomes an `OI-nn` in section 11 naming the file, why it could not
be read, and the fix - a pip install, or a re-export request. Never drop it, never guess its
content from its filename. An empty extraction is treated the same: `ingest.py` warns on zero
characters.

## Limits

- **No knowledge base.** The output contract is the numbered sections. For a large,
  diagram-dense, cross-checking job, run the `docs-to-knowledge` skill and feed spec-builder
  its output.
- **No diagram reconstruction, no page-versus-text cross-check.** Extracted text is the source.
  A deck whose meaning lives in arrows needs a vision read or `docs-to-knowledge`.
- **No OCR.** `vision` means a model reads the rendered pages; markitdown does not OCR PDFs.
- **No format conversion.** Legacy binary Office is read where a reader exists, never
  converted; LibreOffice is not shelled out to.
- **Unsupported formats are reported, not skipped.** An unrecognised extension goes to
  markitdown and, if that fails, is named in the plan. A planned file that produced no text is
  an `OI-nn`, every time.
