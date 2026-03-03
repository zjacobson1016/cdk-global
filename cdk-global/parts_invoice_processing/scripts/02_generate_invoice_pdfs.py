"""Generate realistic PDF invoices from structured invoice data for ai_parse_document."""
import os
import pandas as pd
from datetime import datetime
from pyspark.sql import SparkSession

# =============================================================================
# CONFIGURATION
# =============================================================================
CATALOG = "mfg_mc_se_sa"
SCHEMA = "cdk"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw_data"
PDF_OUTPUT_PATH = f"{VOLUME_PATH}/invoice_pdfs"
N_PDFS = 50  # Generate PDFs for the first 50 invoices

spark = SparkSession.builder.getOrCreate()

# =============================================================================
# LOAD STRUCTURED DATA
# =============================================================================
print("Loading invoice and supplier data...")
invoices_df = spark.read.parquet(f"{VOLUME_PATH}/invoices").toPandas()
suppliers_df = spark.read.parquet(f"{VOLUME_PATH}/suppliers").toPandas()

supplier_lookup = suppliers_df.set_index("supplier_id").to_dict("index")
invoices_to_pdf = invoices_df.head(N_PDFS)

print(f"Generating {len(invoices_to_pdf)} invoice PDFs...")

# =============================================================================
# GENERATE PDFS USING fpdf2
# =============================================================================
from fpdf import FPDF

DEALERSHIP_NAME = "Sunset Chrysler Dodge Jeep Ram"
DEALERSHIP_ADDR = "4567 Automotive Blvd, Orlando, FL 32819"
DEALERSHIP_PHONE = "(407) 555-0199"

os.makedirs(PDF_OUTPUT_PATH, exist_ok=True)

for idx, inv in invoices_to_pdf.iterrows():
    sid = inv["supplier_id"]
    sup = supplier_lookup.get(sid, {})

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Supplier Header ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, inv["supplier_name"], ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, sup.get("address", ""), ln=True)
    pdf.cell(0, 5, f"{sup.get('city', '')}, {sup.get('state', '')} {sup.get('zip_code', '')}", ln=True)
    pdf.cell(0, 5, f"Phone: {sup.get('phone', '')}  |  Email: {sup.get('email', '')}", ln=True)

    pdf.ln(8)
    pdf.set_draw_color(0, 0, 0)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # --- INVOICE Title ---
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "INVOICE", ln=True, align="R")
    pdf.ln(3)

    # --- Invoice Details ---
    pdf.set_font("Helvetica", "", 10)
    detail_x = 130
    pdf.set_xy(detail_x, pdf.get_y())
    pdf.cell(30, 6, "Invoice #:", align="R")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 6, str(inv["invoice_number"]), ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(detail_x, pdf.get_y())
    pdf.cell(30, 6, "Date:", align="R")
    pdf.cell(40, 6, str(inv["invoice_date"]), ln=True)

    pdf.set_xy(detail_x, pdf.get_y())
    pdf.cell(30, 6, "Due Date:", align="R")
    pdf.cell(40, 6, str(inv["due_date"]), ln=True)

    pdf.set_xy(detail_x, pdf.get_y())
    pdf.cell(30, 6, "Terms:", align="R")
    pdf.cell(40, 6, str(inv["payment_terms"]), ln=True)

    if inv["po_number"]:
        pdf.set_xy(detail_x, pdf.get_y())
        pdf.cell(30, 6, "PO Ref:", align="R")
        pdf.cell(40, 6, str(inv["po_number"]), ln=True)

    # --- Bill To ---
    bill_y = pdf.get_y() - 30
    pdf.set_xy(10, bill_y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 6, "BILL TO:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_x(10)
    pdf.cell(60, 5, DEALERSHIP_NAME, ln=True)
    pdf.set_x(10)
    pdf.cell(60, 5, DEALERSHIP_ADDR, ln=True)
    pdf.set_x(10)
    pdf.cell(60, 5, f"Phone: {DEALERSHIP_PHONE}", ln=True)
    pdf.set_x(10)
    pdf.cell(60, 5, f"Dept: {inv['department']}", ln=True)

    pdf.ln(10)

    # --- Line Items Table ---
    pdf.set_fill_color(41, 65, 122)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)

    col_widths = [25, 70, 25, 30, 40]
    headers = ["Part #", "Description", "Qty", "Unit Price", "Line Total"]
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)

    line_total = round(inv["quantity"] * inv["unit_price"], 2)
    row_data = [
        str(inv["part_number"]),
        str(inv["part_name"]),
        str(inv["quantity"]),
        f"${inv['unit_price']:,.2f}",
        f"${line_total:,.2f}",
    ]
    for w, d in zip(col_widths, row_data):
        pdf.cell(w, 7, d, border=1, align="C")
    pdf.ln()

    # --- Totals ---
    pdf.ln(5)
    totals_x = 120
    pdf.set_x(totals_x)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(40, 7, "Subtotal:", align="R")
    pdf.cell(30, 7, f"${inv['subtotal']:,.2f}", align="R", ln=True)

    pdf.set_x(totals_x)
    pdf.cell(40, 7, "Tax:", align="R")
    pdf.cell(30, 7, f"${inv['tax']:,.2f}", align="R", ln=True)

    pdf.set_x(totals_x)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 9, "TOTAL DUE:", align="R")
    pdf.cell(30, 9, f"${inv['total_amount']:,.2f}", align="R", ln=True)

    # --- Footer ---
    pdf.ln(15)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Payment Terms: {inv['payment_terms']}. Please remit payment by {inv['due_date']}.", ln=True)
    pdf.cell(0, 5, "Please include invoice number on your payment. Thank you for your business!", ln=True)

    # Save directly to volume (FUSE mount)
    output_path = f"{PDF_OUTPUT_PATH}/{inv['invoice_id']}.pdf"
    pdf.output(output_path)

print(f"Generated and saved {len(invoices_to_pdf)} PDFs to {PDF_OUTPUT_PATH}")

# =============================================================================
# VALIDATION
# =============================================================================
pdf_files = [f for f in os.listdir(PDF_OUTPUT_PATH) if f.endswith(".pdf")]
print(f"\nValidation: {len(pdf_files)} PDFs in {PDF_OUTPUT_PATH}")
for f in pdf_files[:5]:
    size = os.path.getsize(f"{PDF_OUTPUT_PATH}/{f}")
    print(f"  {f} ({size} bytes)")
print("  ...")
print("Done!")
