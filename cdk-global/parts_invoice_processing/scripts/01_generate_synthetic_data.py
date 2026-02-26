"""Generate synthetic parts invoice processing data for a car dealership."""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from faker import Faker
from pyspark.sql import SparkSession

# =============================================================================
# CONFIGURATION
# =============================================================================
CATALOG = "home_zach_jacobson"
SCHEMA = "cdk"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw_data"

N_SUPPLIERS = 15
N_PURCHASE_ORDERS = 300
N_RECEIVING_REPORTS = 270
N_INVOICES = 200
N_EMAILS = 250

END_DATE = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
START_DATE = END_DATE - timedelta(days=180)

SEED = 42

# =============================================================================
# SETUP
# =============================================================================
np.random.seed(SEED)
Faker.seed(SEED)
fake = Faker()
spark = SparkSession.builder.getOrCreate()

print(f"Creating infrastructure in {CATALOG}.{SCHEMA}...")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_data")

# =============================================================================
# REALISTIC AUTO PARTS DATA
# =============================================================================
SUPPLIER_NAMES = [
    "AutoZone Commercial", "NAPA Auto Parts", "O'Reilly Auto Parts",
    "Genuine Parts Co.", "Dorman Products", "Standard Motor Products",
    "ACDelco Professional", "Motorcraft OEM Supply", "Bosch Automotive",
    "Denso International", "Continental AG Parts", "Delphi Technologies",
    "Gates Corporation", "Dayco Products", "Mahle Aftermarket"
]

PART_CATALOG = [
    ("BRK-001", "Brake Pad Set - Front Ceramic", 45.00, 85.00),
    ("BRK-002", "Brake Rotor - Front", 55.00, 110.00),
    ("BRK-003", "Brake Caliper Assembly", 120.00, 220.00),
    ("FLT-001", "Oil Filter", 4.50, 12.00),
    ("FLT-002", "Air Filter", 8.00, 22.00),
    ("FLT-003", "Cabin Air Filter", 10.00, 28.00),
    ("FLT-004", "Fuel Filter", 15.00, 35.00),
    ("ENG-001", "Spark Plug Set (4)", 18.00, 45.00),
    ("ENG-002", "Ignition Coil", 35.00, 75.00),
    ("ENG-003", "Serpentine Belt", 20.00, 45.00),
    ("ENG-004", "Timing Belt Kit", 85.00, 180.00),
    ("ENG-005", "Water Pump", 55.00, 120.00),
    ("SUS-001", "Strut Assembly - Front", 90.00, 200.00),
    ("SUS-002", "Control Arm with Ball Joint", 75.00, 160.00),
    ("SUS-003", "Tie Rod End", 25.00, 55.00),
    ("ELC-001", "Alternator", 150.00, 320.00),
    ("ELC-002", "Starter Motor", 130.00, 280.00),
    ("ELC-003", "Battery (Group 35)", 95.00, 180.00),
    ("CLG-001", "Radiator Assembly", 110.00, 250.00),
    ("CLG-002", "Thermostat", 12.00, 30.00),
    ("CLG-003", "Coolant Hose Kit", 25.00, 55.00),
    ("EXH-001", "Catalytic Converter", 200.00, 450.00),
    ("EXH-002", "O2 Sensor", 45.00, 95.00),
    ("TRN-001", "CV Axle Assembly", 65.00, 140.00),
    ("TRN-002", "Wheel Bearing Hub Assembly", 80.00, 175.00),
]

DEALERSHIP_DEPARTMENTS = ["Service", "Body Shop", "Parts Counter", "Quick Lane", "Warranty"]

# =============================================================================
# 1. SUPPLIERS (Master Table)
# =============================================================================
print("Generating suppliers...")

suppliers_data = []
for i, name in enumerate(SUPPLIER_NAMES):
    suppliers_data.append({
        "supplier_id": f"SUP-{i+1:03d}",
        "supplier_name": name,
        "address": fake.street_address(),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "zip_code": fake.zipcode(),
        "phone": fake.phone_number(),
        "email": f"orders@{name.lower().replace(chr(32), '').replace(chr(39), '')}.com",
        "payment_terms": np.random.choice(["Net 30", "Net 45", "Net 60", "2/10 Net 30"], p=[0.4, 0.25, 0.15, 0.2]),
        "vendor_tier": np.random.choice(["Preferred", "Standard", "Probationary"], p=[0.4, 0.5, 0.1]),
    })

suppliers_pdf = pd.DataFrame(suppliers_data)
supplier_ids = suppliers_pdf["supplier_id"].tolist()
supplier_name_map = dict(zip(suppliers_pdf["supplier_id"], suppliers_pdf["supplier_name"]))
supplier_tier_map = dict(zip(suppliers_pdf["supplier_id"], suppliers_pdf["vendor_tier"]))

tier_weights = suppliers_pdf["vendor_tier"].map({"Preferred": 4.0, "Standard": 2.0, "Probationary": 0.5})
supplier_weights = (tier_weights / tier_weights.sum()).tolist()

print(f"  Created {len(suppliers_pdf)} suppliers")

# =============================================================================
# 2. PURCHASE ORDERS
# =============================================================================
print("Generating purchase orders...")

po_data = []
for i in range(N_PURCHASE_ORDERS):
    sid = np.random.choice(supplier_ids, p=supplier_weights)
    part = PART_CATALOG[np.random.randint(0, len(PART_CATALOG))]
    part_number, part_name, cost_low, cost_high = part
    quantity = int(np.random.lognormal(1.5, 0.8)) + 1
    quantity = min(quantity, 50)
    unit_price = round(np.random.uniform(cost_low, cost_high), 2)
    order_date = fake.date_between(start_date=START_DATE, end_date=END_DATE)

    po_data.append({
        "po_number": f"PO-{order_date.strftime('%y%m')}-{i+1:04d}",
        "supplier_id": sid,
        "part_number": part_number,
        "part_name": part_name,
        "quantity_ordered": quantity,
        "unit_price": unit_price,
        "total_amount": round(quantity * unit_price, 2),
        "order_date": order_date,
        "expected_delivery_date": order_date + timedelta(days=int(np.random.choice([3, 5, 7, 10, 14], p=[0.2, 0.3, 0.25, 0.15, 0.1]))),
        "status": np.random.choice(["Fulfilled", "Open", "Partially Received", "Cancelled"], p=[0.65, 0.15, 0.12, 0.08]),
        "department": np.random.choice(DEALERSHIP_DEPARTMENTS, p=[0.45, 0.15, 0.20, 0.15, 0.05]),
        "ordered_by": fake.name(),
    })

po_pdf = pd.DataFrame(po_data)
print(f"  Created {len(po_pdf)} purchase orders")

# =============================================================================
# 3. RECEIVING REPORTS
# =============================================================================
print("Generating receiving reports...")

fulfilled_pos = po_pdf[po_pdf["status"].isin(["Fulfilled", "Partially Received"])].head(N_RECEIVING_REPORTS)

rr_data = []
for idx, po in fulfilled_pos.iterrows():
    qty_ordered = po["quantity_ordered"]
    is_partial = po["status"] == "Partially Received"

    if is_partial:
        qty_received = max(1, int(qty_ordered * np.random.uniform(0.5, 0.9)))
    else:
        qty_received = qty_ordered

    has_damage = np.random.random() < 0.08
    qty_damaged = int(np.random.randint(1, max(2, qty_received // 4))) if has_damage else 0

    received_date = po["order_date"] + timedelta(days=np.random.randint(2, 15))
    if received_date > END_DATE.date():
        received_date = END_DATE.date()

    condition = "Damaged" if has_damage else np.random.choice(["Good", "Good", "Good", "Acceptable"])

    rr_data.append({
        "receiving_id": f"RR-{len(rr_data)+1:05d}",
        "po_number": po["po_number"],
        "supplier_id": po["supplier_id"],
        "part_number": po["part_number"],
        "quantity_received": qty_received,
        "quantity_damaged": qty_damaged,
        "received_date": received_date,
        "received_by": fake.name(),
        "condition": condition,
        "notes": f"Damaged packaging on {qty_damaged} units" if has_damage else "",
    })

rr_pdf = pd.DataFrame(rr_data)
print(f"  Created {len(rr_pdf)} receiving reports")

# =============================================================================
# 4. INVOICES (Metadata - matches some POs, some have discrepancies)
# =============================================================================
print("Generating invoice metadata...")

received_pos = po_pdf[po_pdf["status"].isin(["Fulfilled", "Partially Received"])].head(N_INVOICES)

invoice_data = []
for idx, po in received_pos.iterrows():
    inv_num = idx + 1
    sid = po["supplier_id"]
    supplier_name = supplier_name_map[sid]

    invoice_date = po["order_date"] + timedelta(days=np.random.randint(5, 20))
    if invoice_date > END_DATE.date():
        invoice_date = END_DATE.date()

    # Introduce discrepancies for ~20% of invoices
    discrepancy_type = np.random.choice(
        ["none", "price_mismatch", "quantity_mismatch", "no_po_match"],
        p=[0.72, 0.12, 0.10, 0.06]
    )

    if discrepancy_type == "price_mismatch":
        inv_unit_price = round(po["unit_price"] * np.random.uniform(1.03, 1.15), 2)
        inv_quantity = po["quantity_ordered"]
    elif discrepancy_type == "quantity_mismatch":
        inv_unit_price = po["unit_price"]
        inv_quantity = po["quantity_ordered"] + np.random.randint(1, 5)
    elif discrepancy_type == "no_po_match":
        inv_unit_price = po["unit_price"]
        inv_quantity = po["quantity_ordered"]
    else:
        inv_unit_price = po["unit_price"]
        inv_quantity = po["quantity_ordered"]

    inv_total = round(inv_quantity * inv_unit_price, 2)
    tax = round(inv_total * np.random.uniform(0.06, 0.10), 2)

    po_ref = "" if discrepancy_type == "no_po_match" else po["po_number"]

    payment_terms = suppliers_pdf[suppliers_pdf["supplier_id"] == sid]["payment_terms"].values[0]
    if "Net 30" in payment_terms:
        due_date = invoice_date + timedelta(days=30)
    elif "Net 45" in payment_terms:
        due_date = invoice_date + timedelta(days=45)
    elif "Net 60" in payment_terms:
        due_date = invoice_date + timedelta(days=60)
    else:
        due_date = invoice_date + timedelta(days=30)

    invoice_data.append({
        "invoice_id": f"INV-{inv_num:05d}",
        "supplier_id": sid,
        "supplier_name": supplier_name,
        "invoice_number": f"{supplier_name[:3].upper()}-{fake.random_number(digits=6, fix_len=True)}",
        "invoice_date": invoice_date,
        "due_date": due_date,
        "po_number": po_ref,
        "part_number": po["part_number"],
        "part_name": po["part_name"],
        "quantity": inv_quantity,
        "unit_price": inv_unit_price,
        "subtotal": inv_total,
        "tax": tax,
        "total_amount": round(inv_total + tax, 2),
        "payment_terms": payment_terms,
        "status": np.random.choice(["Pending", "Approved", "Paid", "Disputed"], p=[0.35, 0.30, 0.25, 0.10]),
        "discrepancy_type": discrepancy_type,
        "department": po["department"],
    })

invoice_pdf = pd.DataFrame(invoice_data)
print(f"  Created {len(invoice_pdf)} invoices ({(invoice_pdf['discrepancy_type'] != 'none').sum()} with discrepancies)")

# =============================================================================
# 5. EMAILS
# =============================================================================
print("Generating emails...")

dealership_email = "parts@sunsetcdjr.com"
ap_email = "accountspayable@sunsetcdjr.com"

email_data = []
for i in range(N_EMAILS):
    if i < len(invoice_pdf):
        inv = invoice_pdf.iloc[i]
        from_addr = suppliers_pdf[suppliers_pdf["supplier_id"] == inv["supplier_id"]]["email"].values[0]
        subject = f"Invoice {inv['invoice_number']} - {inv['supplier_name']}"
        body = f"Please find attached invoice {inv['invoice_number']} for PO {inv['po_number']}. Total: ${inv['total_amount']:,.2f}. Payment terms: {inv['payment_terms']}."
        has_attachment = True
        attachment_fn = f"{inv['invoice_id']}.pdf"
        invoice_id = inv["invoice_id"]
        recv_date = inv["invoice_date"]
    else:
        from_addr = np.random.choice(suppliers_pdf["email"].tolist())
        subject_templates = [
            "Updated Price List - Q{q} {y}",
            "Shipping Delay Notification - Order Update",
            "New Product Catalog Available",
            "Account Statement - {month} {y}",
            "Reminder: Outstanding Balance",
            "Holiday Schedule - Warehouse Closures",
        ]
        template = np.random.choice(subject_templates)
        subject = template.format(
            q=np.random.randint(1, 5),
            y=END_DATE.year,
            month=fake.month_name()
        )
        body = fake.paragraph(nb_sentences=3)
        has_attachment = np.random.random() < 0.3
        attachment_fn = f"document_{i}.pdf" if has_attachment else ""
        invoice_id = ""
        recv_date = fake.date_between(start_date=START_DATE, end_date=END_DATE)

    email_data.append({
        "email_id": f"EMAIL-{i+1:05d}",
        "from_address": from_addr,
        "to_address": np.random.choice([dealership_email, ap_email]),
        "subject": subject,
        "body_preview": body[:200],
        "received_date": recv_date,
        "has_attachment": has_attachment,
        "attachment_filename": attachment_fn,
        "invoice_id": invoice_id,
    })

email_pdf_df = pd.DataFrame(email_data)
print(f"  Created {len(email_pdf_df)} emails")

# =============================================================================
# 6. SAVE TO VOLUME
# =============================================================================
print(f"\nSaving to {VOLUME_PATH}...")

spark.createDataFrame(suppliers_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/suppliers")
print("  ✓ suppliers")

spark.createDataFrame(po_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/purchase_orders")
print("  ✓ purchase_orders")

spark.createDataFrame(rr_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/receiving_reports")
print("  ✓ receiving_reports")

spark.createDataFrame(invoice_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/invoices")
print("  ✓ invoices")

spark.createDataFrame(email_pdf_df).write.mode("overwrite").parquet(f"{VOLUME_PATH}/emails")
print("  ✓ emails")

# =============================================================================
# 7. VALIDATION
# =============================================================================
print("\n=== VALIDATION ===")
print(f"Suppliers: {len(suppliers_pdf)} | Tier dist: {suppliers_pdf['vendor_tier'].value_counts().to_dict()}")
print(f"Purchase Orders: {len(po_pdf)} | Status dist: {po_pdf['status'].value_counts().to_dict()}")
print(f"Receiving Reports: {len(rr_pdf)} | Avg qty received: {rr_pdf['quantity_received'].mean():.1f}")
print(f"Invoices: {len(invoice_pdf)} | Discrepancy dist: {invoice_pdf['discrepancy_type'].value_counts().to_dict()}")
print(f"Emails: {len(email_pdf_df)} | With attachments: {email_pdf_df['has_attachment'].sum()}")
print(f"Avg invoice total: ${invoice_pdf['total_amount'].mean():,.2f}")
print(f"Total invoice value: ${invoice_pdf['total_amount'].sum():,.2f}")
print("\nDone! Structured data saved to volume.")
