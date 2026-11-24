#!/usr/bin/env python3
"""Compute invoice tax amount and discrepancy.

Usage: python calc_tax.py BASE RATE INVOICE_TAX
"""

import sys


def tax_amount(base, rate):
    return round(base * rate / 100, 2)


def variance(actual, expected):
    return round(actual - expected, 2)


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 3:
        print("Usage: calc_tax.py BASE RATE INVOICE_TAX", file=sys.stderr)
        return 2
    base, rate, actual = (float(x) for x in args)
    expected = tax_amount(base, rate)
    print(
        f"Base {base:.2f}, rate {rate:.0f}%, expected tax {expected:.2f}, "
        f"invoice tax {actual:.2f}, variance {variance(actual, expected):.2f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
