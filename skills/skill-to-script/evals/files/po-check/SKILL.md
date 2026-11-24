---
name: po-check
description: Compares purchase orders against incoming invoices to detect amount, VAT/tax, and unit price mismatches. Use when a user asks to verify an invoice, match a PO, or run purchasing reconciliation.
---

# Purchase Order – Invoice Check

The user supplies a purchase order (PO) and one or more invoices. Your job is to check each invoice against the PO and list any discrepancies.

## Workflow

1. Read the PO file. Sum line items: item code, quantity, unit price, total. Note the tax rate.
2. Read the invoice file. Extract the same fields. Process multiple invoices individually.
3. Calculate the difference on each line: invoice quantity minus PO quantity; invoice unit price minus PO unit price. Also express the amount variance as a percentage.
4. Compute tax amount: multiply taxable base by tax rate. Compare against invoice tax; flag variances over one cent as a mismatch.
5. Sum the grand total and compare against PO total. Set tolerance as appropriate; ask the user if needed.
6. Print the result as a table: line, field, PO value, invoice value, variance.
7. Sort discrepancies with the largest dollar variance first.
8. Summarize for the user. If matched, say "ready to approve"; otherwise explain what needs a decision.
9. Write the report to a file if needed; pick any filename you want.

## Notes

- If currencies differ, ask the user for the exchange rate; never compare without one.
- If the same item code appears on multiple lines, aggregate quantities before comparing.
