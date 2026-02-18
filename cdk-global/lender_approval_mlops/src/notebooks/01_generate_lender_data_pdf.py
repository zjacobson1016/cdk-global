"""
Generate synthetic pay stubs (PDF) and photo IDs (JPEG) for loan applicants.
Each document is linked to an application_id so the SDP pipeline can join
them with the structured parquet applications.

Pay stubs  → /Volumes/{catalog}/{schema}/raw_data/pay_stubs/
Photo IDs  → /Volumes/{catalog}/{schema}/raw_data/photo_ids/

Run directly:
  python src/notebooks/01_generate_lender_data_pdf.py --count 100

With custom settings:
  python src/notebooks/01_generate_lender_data_pdf.py --count 200 --profile group-demo
"""

import argparse
import io
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from faker import Faker
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

DEFAULT_CATALOG = os.getenv("CATALOG_NAME", "mfg_mc_se_sa")
DEFAULT_SCHEMA = os.getenv("SCHEMA_NAME", "cdk")
DEFAULT_VOLUME = "raw_data"
PAY_STUBS_SUBDIR = "pay_stubs"
PHOTO_IDS_SUBDIR = "photo_ids"


# ---------------------------------------------------------------------------
# Font helper (Pillow)
# ---------------------------------------------------------------------------
_FONT_CACHE: dict = {}

def _get_font(size: int = 12) -> ImageFont.FreeTypeFont:
    """Load a TrueType font with caching; fall back to Pillow default."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",                          # macOS
        "/System/Library/Fonts/Supplemental/Arial.ttf",                 # macOS alt
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",             # Linux
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, size)
            _FONT_CACHE[size] = font
            return font
        except (OSError, IOError):
            continue
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:
        font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


# ---------------------------------------------------------------------------
# Person profile generator
# ---------------------------------------------------------------------------
def generate_person_profile(fake: Faker, idx: int) -> dict:
    """Generate consistent personal data used for both pay stub and photo ID."""
    app_id = f"APP-{idx:06d}"
    first = fake.first_name()
    last = fake.last_name()
    dob = fake.date_of_birth(minimum_age=21, maximum_age=70)

    # Address
    street = fake.street_address()
    city = fake.city()
    state = fake.state_abbr()
    zipcode = fake.zipcode()

    # Employer info
    employer = fake.company()
    employer_street = fake.street_address()
    employer_city = fake.city()
    employer_state = fake.state_abbr()
    employer_zip = fake.zipcode()
    job_title = fake.job()

    # Income (lognormal — mirrors 01_generate_lender_data.py distribution)
    annual_salary = round(
        float(np.clip(np.random.lognormal(mean=10.5, sigma=0.6) * 1000, 25_000, 350_000)), 2
    )

    # Pay period details (biweekly)
    pay_date = fake.date_between(start_date="-60d", end_date="today")
    pay_period_end = pay_date - timedelta(days=random.randint(1, 3))
    pay_period_start = pay_period_end - timedelta(days=13)
    gross_per_period = round(annual_salary / 26, 2)

    # Deductions
    fed_rate = 0.12 if annual_salary < 45_000 else (0.22 if annual_salary < 100_000 else 0.24)
    fed_tax = round(gross_per_period * fed_rate, 2)
    state_tax = round(gross_per_period * random.uniform(0.03, 0.07), 2)
    ss_tax = round(gross_per_period * 0.062, 2)
    medicare = round(gross_per_period * 0.0145, 2)
    health_ins = round(random.uniform(120, 320), 2)
    ret_rate = round(random.uniform(0.03, 0.08), 3)
    retirement = round(gross_per_period * ret_rate, 2)
    total_deductions = round(fed_tax + state_tax + ss_tax + medicare + health_ins + retirement, 2)
    net_pay = round(gross_per_period - total_deductions, 2)

    # YTD (approximate: 2 pay periods per month)
    periods_elapsed = max(1, pay_date.month * 2 + (1 if pay_date.day > 15 else 0))
    ytd_gross = round(gross_per_period * periods_elapsed, 2)
    ytd_fed = round(fed_tax * periods_elapsed, 2)
    ytd_state = round(state_tax * periods_elapsed, 2)
    ytd_ss = round(ss_tax * periods_elapsed, 2)
    ytd_medicare = round(medicare * periods_elapsed, 2)
    ytd_health = round(health_ins * periods_elapsed, 2)
    ytd_retirement = round(retirement * periods_elapsed, 2)
    ytd_deductions = round(total_deductions * periods_elapsed, 2)
    ytd_net = round(net_pay * periods_elapsed, 2)

    # Driver license info
    sex = random.choice(["M", "F"])
    dl_number = fake.bothify("??######", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    eye_color = random.choice(["BRN", "BLU", "GRN", "HZL", "GRY"])
    height_ft = random.randint(5, 6)
    height_in = random.randint(0, 11)
    weight = random.randint(120, 280)
    dl_issue = fake.date_between(start_date="-4y", end_date="-1y")
    try:
        dl_expiry = dl_issue.replace(year=dl_issue.year + 5)
    except ValueError:  # Feb 29 → non-leap year
        dl_expiry = dl_issue.replace(year=dl_issue.year + 5, day=28)

    return {
        "application_id": app_id,
        "first_name": first,
        "last_name": last,
        "full_name": f"{first} {last}",
        "dob": dob,
        "street": street,
        "city": city,
        "state": state,
        "zipcode": zipcode,
        # Employer
        "employer": employer,
        "employer_street": employer_street,
        "employer_city": employer_city,
        "employer_state": employer_state,
        "employer_zip": employer_zip,
        "job_title": job_title,
        # Pay
        "annual_salary": annual_salary,
        "pay_date": pay_date,
        "pay_period_start": pay_period_start,
        "pay_period_end": pay_period_end,
        "gross_per_period": gross_per_period,
        "fed_tax": fed_tax,
        "state_tax": state_tax,
        "ss_tax": ss_tax,
        "medicare": medicare,
        "health_ins": health_ins,
        "retirement": retirement,
        "ret_rate": ret_rate,
        "total_deductions": total_deductions,
        "net_pay": net_pay,
        "ytd_gross": ytd_gross,
        "ytd_fed": ytd_fed,
        "ytd_state": ytd_state,
        "ytd_ss": ytd_ss,
        "ytd_medicare": ytd_medicare,
        "ytd_health": ytd_health,
        "ytd_retirement": ytd_retirement,
        "ytd_deductions": ytd_deductions,
        "ytd_net": ytd_net,
        # Driver license
        "sex": sex,
        "dl_number": dl_number,
        "eye_color": eye_color,
        "height": f"{height_ft}'{height_in:02d}\"",
        "weight": weight,
        "dl_issue": dl_issue,
        "dl_expiry": dl_expiry,
    }


# ---------------------------------------------------------------------------
# Pay stub PDF
# ---------------------------------------------------------------------------
def _section_header(pdf: FPDF, title: str):
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(225, 225, 235)
    pdf.cell(0, 7, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(2)


def _field_row(pdf: FPDF, label: str, value: str):
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(65, 6, f"  {label}:", new_x="RIGHT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")


def _table_header(pdf: FPDF, col1: str, col2: str, col3: str):
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(200, 200, 215)
    pdf.cell(80, 6, f"  {col1}", fill=True)
    pdf.cell(45, 6, col2, align="R", fill=True)
    pdf.cell(45, 6, col3, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")


def _table_row(pdf: FPDF, col1: str, col2: str, col3: str, bold: bool = False):
    style = "B" if bold else ""
    pdf.set_font("Helvetica", style, 9)
    pdf.cell(80, 5, f"  {col1}")
    pdf.cell(45, 5, col2, align="R")
    pdf.cell(45, 5, col3, align="R", new_x="LMARGIN", new_y="NEXT")


def create_pay_stub_pdf(p: dict) -> bytes:
    """Create a realistic pay stub PDF from a person profile."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Company header ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, p["employer"], new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(
        0, 4,
        f"{p['employer_street']}, {p['employer_city']}, "
        f"{p['employer_state']} {p['employer_zip']}",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "EARNINGS STATEMENT", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # --- Employee information ---
    _section_header(pdf, "EMPLOYEE INFORMATION")
    _field_row(pdf, "Employee Name", p["full_name"])
    _field_row(pdf, "Reference Number", p["application_id"])
    _field_row(pdf, "Job Title", p["job_title"])
    _field_row(pdf, "Pay Date", p["pay_date"].strftime("%m/%d/%Y"))
    _field_row(
        pdf, "Pay Period",
        f"{p['pay_period_start'].strftime('%m/%d/%Y')} - "
        f"{p['pay_period_end'].strftime('%m/%d/%Y')}",
    )
    pdf.ln(4)

    # --- Earnings ---
    _section_header(pdf, "EARNINGS")
    _table_header(pdf, "Description", "Current", "YTD")
    _table_row(pdf, "Regular Pay", f"${p['gross_per_period']:,.2f}", f"${p['ytd_gross']:,.2f}")
    pdf.ln(1)
    _table_row(pdf, "GROSS PAY", f"${p['gross_per_period']:,.2f}", f"${p['ytd_gross']:,.2f}", bold=True)
    pdf.ln(4)

    # --- Deductions ---
    _section_header(pdf, "DEDUCTIONS")
    _table_header(pdf, "Description", "Current", "YTD")
    _table_row(pdf, "Federal Income Tax", f"${p['fed_tax']:,.2f}", f"${p['ytd_fed']:,.2f}")
    _table_row(pdf, "State Income Tax", f"${p['state_tax']:,.2f}", f"${p['ytd_state']:,.2f}")
    _table_row(pdf, "Social Security (OASDI)", f"${p['ss_tax']:,.2f}", f"${p['ytd_ss']:,.2f}")
    _table_row(pdf, "Medicare", f"${p['medicare']:,.2f}", f"${p['ytd_medicare']:,.2f}")
    _table_row(pdf, "Health Insurance", f"${p['health_ins']:,.2f}", f"${p['ytd_health']:,.2f}")
    _table_row(pdf, f"401(k) ({p['ret_rate']:.1%})", f"${p['retirement']:,.2f}", f"${p['ytd_retirement']:,.2f}")
    pdf.ln(1)
    _table_row(pdf, "TOTAL DEDUCTIONS", f"${p['total_deductions']:,.2f}", f"${p['ytd_deductions']:,.2f}", bold=True)
    pdf.ln(4)

    # --- Net pay ---
    _section_header(pdf, "NET PAY")
    _table_header(pdf, "", "Current", "YTD")
    _table_row(pdf, "NET PAY", f"${p['net_pay']:,.2f}", f"${p['ytd_net']:,.2f}", bold=True)
    pdf.ln(8)

    # --- Footer ---
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(
        0, 4,
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC  |  "
        "Confidential - Retain for your records.",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
    return pdf.output()


# ---------------------------------------------------------------------------
# Photo ID (JPEG — driver's license style)
# ---------------------------------------------------------------------------
def create_photo_id_jpeg(p: dict) -> bytes:
    """Create a driver-license-style JPEG image from a person profile."""
    W, H = 1000, 620
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    fnt_title = _get_font(26)
    fnt_sub = _get_font(18)
    fnt_label = _get_font(13)
    fnt_value = _get_font(17)
    fnt_small = _get_font(12)

    # Header bar
    draw.rectangle([(0, 0), (W, 65)], fill=(0, 51, 102))
    _center_text(draw, f"STATE OF {p['state']}", fnt_title, W, y=8, fill="white")
    _center_text(draw, "DRIVER LICENSE", fnt_sub, W, y=36, fill=(200, 210, 255))

    # Photo placeholder
    px, py, pw, ph = 35, 90, 220, 280
    draw.rectangle([(px, py), (px + pw, py + ph)], fill=(210, 210, 220), outline=(170, 170, 180))
    _center_text(draw, "PHOTO", _get_font(22), pw, y=py + ph // 2 - 12, fill=(140, 140, 150), x_offset=px)

    # Info fields (right side)
    ix = 290
    y = 90
    gap = 38

    _label_value(draw, ix, y, "DL", p["dl_number"], fnt_label, fnt_value)
    y += gap
    _label_value(draw, ix, y, "NAME", p["full_name"].upper(), fnt_label, fnt_value)
    y += gap
    _label_value(draw, ix, y, "ADDRESS", p["street"], fnt_label, fnt_value)
    y += 28
    draw.text((ix + 90, y), f"{p['city']}, {p['state']} {p['zipcode']}", fill="black", font=fnt_value)
    y += gap
    _label_value(draw, ix, y, "DOB", p["dob"].strftime("%m/%d/%Y"), fnt_label, fnt_value)
    y += gap

    # Physical descriptors (inline)
    draw.text((ix, y), "SEX", fill=(100, 100, 100), font=fnt_label)
    draw.text((ix + 45, y), p["sex"], fill="black", font=fnt_value)
    draw.text((ix + 110, y), "HT", fill=(100, 100, 100), font=fnt_label)
    draw.text((ix + 145, y), p["height"], fill="black", font=fnt_value)
    draw.text((ix + 270, y), "WT", fill=(100, 100, 100), font=fnt_label)
    draw.text((ix + 305, y), f"{p['weight']} lbs", fill="black", font=fnt_value)
    y += gap

    draw.text((ix, y), "EYES", fill=(100, 100, 100), font=fnt_label)
    draw.text((ix + 55, y), p["eye_color"], fill="black", font=fnt_value)
    draw.text((ix + 170, y), "CLASS", fill=(100, 100, 100), font=fnt_label)
    draw.text((ix + 230, y), "C", fill="black", font=fnt_value)
    y += gap

    draw.text((ix, y), "ISS", fill=(100, 100, 100), font=fnt_label)
    draw.text((ix + 45, y), p["dl_issue"].strftime("%m/%d/%Y"), fill="black", font=fnt_value)
    draw.text((ix + 270, y), "EXP", fill=(100, 100, 100), font=fnt_label)
    draw.text((ix + 315, y), p["dl_expiry"].strftime("%m/%d/%Y"), fill="black", font=fnt_value)

    # Bottom bar
    draw.rectangle([(0, H - 35), (W, H)], fill=(0, 51, 102))
    _center_text(draw, "NOT FOR REAL ID PURPOSES", fnt_small, W, y=H - 28, fill=(180, 190, 220))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _center_text(draw, text, font, width, y, fill, x_offset=0):
    """Draw horizontally centered text."""
    tw = draw.textlength(text, font=font)
    draw.text((x_offset + (width - tw) / 2, y), text, fill=fill, font=font)


def _label_value(draw, x, y, label, value, fnt_label, fnt_value):
    """Draw a label: value pair."""
    draw.text((x, y), label, fill=(100, 100, 100), font=fnt_label)
    label_w = max(draw.textlength(label, font=fnt_label) + 12, 60)
    draw.text((x + label_w, y), value, fill="black", font=fnt_value)


# ---------------------------------------------------------------------------
# Volume / upload helpers
# ---------------------------------------------------------------------------
def upload_file(w: WorkspaceClient, volume_path: str, filename: str, content: bytes):
    """Upload a single file to the UC volume."""
    target = f"{volume_path}/{filename}"
    w.files.upload(target, io.BytesIO(content), overwrite=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate synthetic pay stubs (PDF) and photo IDs (JPEG) to a UC volume."
    )
    parser.add_argument("--catalog", default=os.getenv("CATALOG_NAME", DEFAULT_CATALOG))
    parser.add_argument("--schema", dest="schema_", default=os.getenv("SCHEMA_NAME", DEFAULT_SCHEMA))
    parser.add_argument("--volume", default=os.getenv("LENDER_VOLUME", DEFAULT_VOLUME))
    parser.add_argument("--count", type=int, default=100, help="Number of applicants to generate docs for.")
    parser.add_argument("--max-workers", type=int, default=8, help="Parallel upload threads.")
    parser.add_argument(
        "--profile",
        default=os.getenv("DATABRICKS_PROFILE", "DEFAULT"),
        help="Databricks CLI profile.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    w = WorkspaceClient(profile=args.profile)

    base_path = f"/Volumes/{args.catalog}/{args.schema_}/{args.volume}"
    pay_stub_path = f"{base_path}/{PAY_STUBS_SUBDIR}"
    photo_id_path = f"{base_path}/{PHOTO_IDS_SUBDIR}"

    print(f"Generating {args.count} pay stubs  → {pay_stub_path}")
    print(f"Generating {args.count} photo IDs  → {photo_id_path}")

    # Seed for reproducibility
    fake = Faker()
    Faker.seed(42)
    np.random.seed(42)
    random.seed(42)

    # Generate all person profiles
    profiles = [generate_person_profile(fake, i) for i in range(args.count)]
    print(f"  Generated {len(profiles)} person profiles")

    # Build (path, filename, bytes) upload tasks
    upload_tasks: list[tuple[str, str, bytes]] = []
    for p in profiles:
        upload_tasks.append((pay_stub_path, f"{p['application_id']}_paystub.pdf", create_pay_stub_pdf(p)))
        upload_tasks.append((photo_id_path, f"{p['application_id']}_photoid.jpg", create_photo_id_jpeg(p)))

    print(f"  Created {len(upload_tasks)} documents ({args.count} pay stubs + {args.count} photo IDs)")

    # Parallel upload
    successes = 0
    failures = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {}
        for vol_path, fname, content in upload_tasks:
            fut = pool.submit(upload_file, w, vol_path, fname, content)
            futures[fut] = fname

        for fut in as_completed(futures):
            fname = futures[fut]
            try:
                fut.result()
                successes += 1
                if successes % 50 == 0:
                    print(f"  Uploaded {successes}/{len(upload_tasks)} files...")
            except Exception as e:
                failures += 1
                print(f"  FAILED {fname}: {e}")

    elapsed = time.time() - start_time
    print(f"\nDone: {successes} uploaded, {failures} failed in {elapsed:.1f}s")
    print(f"  Pay stubs : {pay_stub_path}")
    print(f"  Photo IDs : {photo_id_path}")


if __name__ == "__main__":
    main()
