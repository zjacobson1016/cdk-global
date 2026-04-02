# Gold Layer — Invoice Routing Rules

The `gold_invoice_match` materialized view performs a **3-way match** between AI-parsed invoice PDFs, purchase orders, and receiving reports. It produces three computed columns that classify and route every invoice: `match_status`, `approval_route`, and `invoice_classification`.

Rules are evaluated top-to-bottom. The **first matching condition wins**.

---

## Match Status

Determines the outcome of the 3-way match between the invoice, PO, and receiving report.

| Status | Condition |
|---|---|
| `NO_PO_REFERENCE` | Invoice has no PO reference (null or empty) |
| `PO_NOT_FOUND` | Invoice references a PO, but no matching PO exists in the system |
| `NOT_RECEIVED` | PO exists but no receiving report was found |
| `QTY_AND_PRICE_MISMATCH` | Invoice quantity differs from PO **and** unit price differs by more than $0.01 |
| `QUANTITY_MISMATCH` | Invoice quantity differs from PO quantity (prices match) |
| `PRICE_MISMATCH` | Invoice unit price differs from PO unit price by more than $0.01 (quantities match) |
| `PARTIAL_RECEIPT` | PO and receiving report exist, but accepted quantity is less than ordered quantity |
| `MATCHED` | All three documents align — quantities, prices, and receipt are consistent |

---

## Approval Route

Determines who must approve the invoice before it can be paid. Rules layer exception handling on top of dollar-amount thresholds.

| Route | Condition | Approver |
|---|---|---|
| `PO_REQUIRED` | Invoice has no PO reference (null or empty) | AP team must obtain a PO before processing |
| `EXCEPTION_REVIEW` | PO referenced but not found in the system, **or** any quantity/price mismatch exists | Controller / AP Manager |
| `RECEIVING_REVIEW` | No receiving report, **or** accepted quantity is less than ordered | Receiving / Warehouse Manager |
| `AUTO_APPROVED` | Fully matched **and** total <= $1,000 for a **Preferred** vendor | No human approval needed |
| `AUTO_APPROVED` | Fully matched **and** total <= $500 (any vendor tier) | No human approval needed |
| `SERVICE_MANAGER` | Fully matched **and** total $500.01 – $5,000 | Service Manager |
| `PARTS_DIRECTOR` | Fully matched **and** total $5,000.01 – $15,000 | Parts Director |
| `GENERAL_MANAGER` | Fully matched **and** total > $15,000 | General Manager / Dealer Principal |

### Dollar threshold summary (matched invoices only)

```
$0 ──────── $500 ──────── $1,000 ──────── $5,000 ──────── $15,000 ──────── ...
 AUTO_APPROVED              │                │                │
 (any vendor)          AUTO_APPROVED    SERVICE_MANAGER   PARTS_DIRECTOR   GENERAL_MANAGER
                       (Preferred only)
```

---

## Invoice Classification

A simplified category used for reporting and agent prompts.

| Classification | Condition |
|---|---|
| `UNMATCHED` | No PO reference, or PO not found in the system |
| `DISCREPANCY` | Quantity mismatch or price mismatch (> $0.01 variance) |
| `RECEIVING_ISSUE` | No receiving report, or partial receipt (accepted < ordered) |
| `STANDARD` | All checks pass — fully matched, no discrepancies |

---

## Computed Metrics

Two additional numeric columns support the match analysis:

- **`price_variance_pct`** — `((invoice_unit_price - po_unit_price) / po_unit_price) * 100`, rounded to 2 decimal places. Null if no PO price exists.
- **`quantity_variance`** — `invoice_quantity - po_quantity_ordered`. Positive means the invoice claims more units than the PO. Null if no PO exists.

---

## Source Tables Joined

| Alias | Silver Table | Join Key |
|---|---|---|
| `inv` | `silver_parsed_invoices_flat` | — (driving table) |
| `po` | `silver_purchase_orders` | `inv.po_reference = po.po_number` |
| `rr` | `silver_receiving_reports` | `po.po_number = rr.po_number` |
| `sup` | `silver_suppliers` | `inv.vendor_name = sup.supplier_name` |
| `em` | `silver_emails` | `invoice_id` extracted from `inv.file_path` |
