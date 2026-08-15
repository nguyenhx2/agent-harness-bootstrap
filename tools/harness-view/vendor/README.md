# Vendored libraries

Third-party code committed verbatim, inlined into the served page with `include_str!` so the
viewer stays self-contained: it makes no network request, and there is no build step and no
package manager in this repo.

| File | Library | Version | Licence | Source |
|---|---|---|---|---|
| `marked.min.js` | [marked](https://github.com/markedjs/marked) | 12.0.2 | MIT (`LICENSE.marked.txt`) | `https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js` |
| `purify.min.js` | [DOMPurify](https://github.com/cure53/DOMPurify) | 3.1.6 | Apache-2.0 OR MPL-2.0 (`LICENSE.dompurify.txt`) | `https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js` |

## Why these two

`marked` replaced a hand-rolled markdown parser. The hand-rolled one did not implement GFM tables
faithfully, and every fix to it was a fix nobody else had reviewed. It is small, fast, and its
table support is the specific thing that was broken.

`DOMPurify` exists because `marked` returns an HTML **string** and the markdown comes from the
repository being inspected. Putting that string into `innerHTML` unsanitised would undo the
injection fix made earlier in this tool, and the page it would run in is same-origin with a
mutating `POST /toggle` endpoint. Writing that sanitiser by hand is exactly the kind of security
code that should not be first-party, so it is vendored rather than improvised.

Raw mode never goes near either library: it is `textContent` and stays byte-exact.

## Updating

Download the new minified file and its LICENSE to this directory, update the version in the table
above, then re-run the checks. `scripts/check_js.py` parses every embedded script, so a corrupt or
truncated download fails there rather than in a browser.
