# invoicer

A small command-line invoicing tool. It prices line items, applies sales tax and prints a total.
All money is held as integer cents (see `docs/adr/0001-integer-cents.md`).

## Install

No dependencies. Python 3.11 or newer.

## Usage

```
python -m invoicer total widget:250:2 gadget:1000:1
python -m invoicer total widget:250:2 --tax-bp 825
```

A line item is `name:unit_cents:quantity`. `--tax-bp` is the tax rate in basis points
(825 = 8.25%).

## Tests

```
python -m unittest discover -s tests -t .
```
