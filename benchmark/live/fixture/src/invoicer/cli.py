"""Command-line entry point: `python -m invoicer total <items...> [--tax-bp N]`."""

import argparse

from invoicer import config
from invoicer.money import format_cents
from invoicer.pricing import parse_line, subtotal
from invoicer.tax import compute_tax


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invoicer")
    sub = parser.add_subparsers(dest="command", required=True)
    total = sub.add_parser("total", help="print subtotal, tax and total")
    total.add_argument("items", nargs="+", help="name:unit_cents:quantity")
    total.add_argument("--tax-bp", type=int, default=0, help="tax rate in basis points")
    return parser


def cmd_total(args: argparse.Namespace) -> int:
    lines = [parse_line(spec) for spec in args.items]
    sub = subtotal(lines)
    tax = compute_tax(sub, args.tax_bp)
    cur = config.currency()
    print(f"subtotal {format_cents(sub, cur)}")
    print(f"tax      {format_cents(tax, cur)}")
    print(f"total    {format_cents(sub + tax, cur)}")
    return 0


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "total":
        return cmd_total(args)
    return 2
