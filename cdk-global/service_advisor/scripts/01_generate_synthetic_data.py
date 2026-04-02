"""Generate synthetic service advisor data for a car dealership."""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date, time
from faker import Faker
# =============================================================================
# CONFIGURATION
# =============================================================================
from databricks.connect import DatabricksSession

CATALOG = "mfg_mc_se_sa"
SCHEMA = "cdk_service"

spark = DatabricksSession.builder.profile("group-demo").serverless().getOrCreate()
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw_data"

N_CUSTOMERS = 200
N_VEHICLES = 250
N_APPOINTMENTS = 80
N_TECHNICIANS = 12
TODAYS_APPOINTMENTS = 18

END_DATE = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
START_DATE = END_DATE - timedelta(days=365 * 3)
TODAY = END_DATE.date()

SEED = 42

# =============================================================================
# SETUP
# =============================================================================
np.random.seed(SEED)
Faker.seed(SEED)
fake = Faker()

print(f"Creating infrastructure in {CATALOG}.{SCHEMA}...")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_data")

# =============================================================================
# REALISTIC DEALERSHIP DATA
# =============================================================================
VEHICLE_CATALOG = [
    (2024, "Chrysler", "300", "Touring"),
    (2024, "Chrysler", "Pacifica", "Limited"),
    (2023, "Dodge", "Charger", "SXT"),
    (2023, "Dodge", "Durango", "GT"),
    (2023, "Dodge", "Challenger", "R/T"),
    (2022, "Jeep", "Grand Cherokee", "Laredo"),
    (2022, "Jeep", "Wrangler", "Sahara"),
    (2024, "Jeep", "Compass", "Latitude"),
    (2023, "Ram", "1500", "Big Horn"),
    (2024, "Ram", "2500", "Tradesman"),
    (2021, "Jeep", "Cherokee", "Limited"),
    (2020, "Dodge", "Grand Caravan", "SE"),
    (2022, "Chrysler", "Voyager", "LX"),
    (2021, "Ram", "1500", "Laramie"),
    (2023, "Jeep", "Gladiator", "Sport"),
    (2020, "Chrysler", "300", "S"),
    (2024, "Jeep", "Grand Cherokee", "Summit"),
    (2022, "Dodge", "Durango", "R/T"),
    (2021, "Ram", "3500", "Longhorn"),
    (2023, "Jeep", "Wagoneer", "Series II"),
]

SERVICE_TYPES = [
    ("Oil Change", 30),
    ("Brake Service", 90),
    ("Transmission Service", 180),
    ("Engine Diagnostics", 120),
    ("Tire Rotation", 30),
    ("A/C Service", 60),
    ("Recall Service", 90),
    ("Multi-Point Inspection", 45),
    ("Suspension Repair", 150),
    ("Electrical Diagnostics", 120),
    ("Coolant Flush", 45),
    ("Battery Replacement", 30),
]

SPECIALIZATIONS = [
    "Engine & Drivetrain",
    "Brakes & Suspension",
    "Electrical & HVAC",
    "Transmission",
    "General Service",
    "Diesel & Heavy Duty",
]

CERTIFICATIONS = [
    "ASE Master Technician",
    "ASE Brakes (A5)",
    "ASE Engine Repair (A1)",
    "ASE Electrical (A6)",
    "ASE Heating & A/C (A7)",
    "ASE Suspension & Steering (A4)",
    "ASE Manual Drivetrain (A3)",
    "ASE Automatic Transmission (A2)",
    "ASE Engine Performance (A8)",
    "Chrysler Master Tech",
    "Mopar Certified",
    "Diesel Specialist",
]

SERVICE_TO_SPECIALIZATION = {
    "Oil Change": "General Service",
    "Brake Service": "Brakes & Suspension",
    "Transmission Service": "Transmission",
    "Engine Diagnostics": "Engine & Drivetrain",
    "Tire Rotation": "General Service",
    "A/C Service": "Electrical & HVAC",
    "Recall Service": "General Service",
    "Multi-Point Inspection": "General Service",
    "Suspension Repair": "Brakes & Suspension",
    "Electrical Diagnostics": "Electrical & HVAC",
    "Coolant Flush": "Engine & Drivetrain",
    "Battery Replacement": "Electrical & HVAC",
}

APPOINTMENT_TIMES = [
    time(7, 30), time(8, 0), time(8, 30), time(9, 0), time(9, 30),
    time(10, 0), time(10, 30), time(11, 0), time(11, 30),
    time(13, 0), time(13, 30), time(14, 0), time(14, 30),
    time(15, 0), time(15, 30), time(16, 0),
]

# =============================================================================
# 1. CUSTOMERS
# =============================================================================
print("Generating customers...")

customers_data = []
for i in range(N_CUSTOMERS):
    first = fake.first_name()
    last = fake.last_name()
    customers_data.append({
        "customer_id": f"CUST-{i+1:04d}",
        "first_name": first,
        "last_name": last,
        "phone": fake.phone_number(),
        "email": f"{first.lower()}.{last.lower()}@{fake.free_email_domain()}",
        "address": fake.street_address(),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "zip_code": fake.zipcode(),
        "preferred_contact": np.random.choice(
            ["Phone", "Email", "Text"], p=[0.35, 0.30, 0.35]
        ),
        "loyalty_tier": np.random.choice(
            ["Platinum", "Gold", "Silver", "Bronze"], p=[0.10, 0.20, 0.35, 0.35]
        ),
        "customer_since": fake.date_between(
            start_date=START_DATE, end_date=END_DATE - timedelta(days=90)
        ),
    })

customers_pdf = pd.DataFrame(customers_data)
customer_ids = customers_pdf["customer_id"].tolist()
print(f"  Created {len(customers_pdf)} customers")

# =============================================================================
# 2. VEHICLES
# =============================================================================
print("Generating vehicles...")

vehicles_data = []
for i in range(N_VEHICLES):
    cid = np.random.choice(customer_ids)
    veh = VEHICLE_CATALOG[np.random.randint(0, len(VEHICLE_CATALOG))]
    yr, make, model, trim = veh
    mileage = int(np.random.lognormal(10.2, 0.6))
    mileage = min(max(mileage, 5000), 180000)

    vehicles_data.append({
        "vehicle_id": f"VEH-{i+1:04d}",
        "customer_id": cid,
        "vin": fake.bothify(text="1C4?????#?######").upper(),
        "year": yr,
        "make": make,
        "model": model,
        "trim": trim,
        "mileage": mileage,
        "last_service_date": fake.date_between(
            start_date=END_DATE - timedelta(days=365),
            end_date=END_DATE,
        ),
    })

vehicles_pdf = pd.DataFrame(vehicles_data)
vehicle_ids = vehicles_pdf["vehicle_id"].tolist()
vehicle_customer_map = dict(zip(vehicles_pdf["vehicle_id"], vehicles_pdf["customer_id"]))
print(f"  Created {len(vehicles_pdf)} vehicles")

# =============================================================================
# 3. APPOINTMENTS
# =============================================================================
print("Generating appointments...")

appointments_data = []

today_vehicle_ids = np.random.choice(vehicle_ids, size=TODAYS_APPOINTMENTS, replace=False)
for i, vid in enumerate(today_vehicle_ids):
    cid = vehicle_customer_map[vid]
    svc = SERVICE_TYPES[np.random.randint(0, len(SERVICE_TYPES))]
    svc_name, est_dur = svc
    appt_time = APPOINTMENT_TIMES[i % len(APPOINTMENT_TIMES)]

    appointments_data.append({
        "appointment_id": f"APPT-{len(appointments_data)+1:05d}",
        "customer_id": cid,
        "vehicle_id": vid,
        "appointment_date": TODAY,
        "appointment_time": str(appt_time),
        "service_type": svc_name,
        "estimated_duration_mins": est_dur,
        "status": np.random.choice(
            ["Scheduled", "Checked-In"], p=[0.70, 0.30]
        ),
        "advisor_notes": np.random.choice([
            "", "", "",
            "Customer requested early morning slot",
            "Repeat visit for same issue",
            "Customer waiting on-site",
            "Loaner vehicle requested",
            "Warranty claim — verify coverage",
            "Customer mentioned noise from front brakes",
            "Fleet vehicle — priority service",
        ]),
    })

for i in range(N_APPOINTMENTS - TODAYS_APPOINTMENTS):
    vid = np.random.choice(vehicle_ids)
    cid = vehicle_customer_map[vid]
    svc = SERVICE_TYPES[np.random.randint(0, len(SERVICE_TYPES))]
    svc_name, est_dur = svc
    appt_date = fake.date_between(
        start_date=END_DATE - timedelta(days=90),
        end_date=END_DATE - timedelta(days=1),
    )
    appt_time = np.random.choice(APPOINTMENT_TIMES)

    appointments_data.append({
        "appointment_id": f"APPT-{len(appointments_data)+1:05d}",
        "customer_id": cid,
        "vehicle_id": vid,
        "appointment_date": appt_date,
        "appointment_time": str(appt_time),
        "service_type": svc_name,
        "estimated_duration_mins": est_dur,
        "status": np.random.choice(
            ["Completed", "No-Show", "Cancelled"], p=[0.80, 0.10, 0.10]
        ),
        "advisor_notes": np.random.choice([
            "", "",
            "Customer was very satisfied",
            "Recommended additional service",
            "Parts on back-order — follow up needed",
        ]),
    })

appointments_pdf = pd.DataFrame(appointments_data)
print(f"  Created {len(appointments_pdf)} appointments ({TODAYS_APPOINTMENTS} for today)")

# =============================================================================
# 4. CUSTOMER LIFETIME VALUE
# =============================================================================
print("Generating customer lifetime value scores...")

clv_data = []
for _, cust in customers_pdf.iterrows():
    cid = cust["customer_id"]
    tier = cust["loyalty_tier"]
    months = max(1, (END_DATE.date() - cust["customer_since"]).days // 30)

    if tier == "Platinum":
        total_spend = round(np.random.uniform(15000, 60000), 2)
        visit_count = int(np.random.uniform(20, 60))
        referral_count = int(np.random.uniform(3, 10))
    elif tier == "Gold":
        total_spend = round(np.random.uniform(8000, 20000), 2)
        visit_count = int(np.random.uniform(10, 30))
        referral_count = int(np.random.uniform(1, 5))
    elif tier == "Silver":
        total_spend = round(np.random.uniform(3000, 10000), 2)
        visit_count = int(np.random.uniform(5, 15))
        referral_count = int(np.random.uniform(0, 3))
    else:
        total_spend = round(np.random.uniform(500, 4000), 2)
        visit_count = int(np.random.uniform(1, 8))
        referral_count = int(np.random.uniform(0, 1))

    avg_ro = round(total_spend / max(visit_count, 1), 2)

    clv_score = round(
        (total_spend / 1000) * 0.40
        + visit_count * 0.25
        + (months / 12) * 0.15
        + referral_count * 0.10
        + (avg_ro / 100) * 0.10,
        2,
    )

    clv_tier = (
        "High" if clv_score >= 20
        else "Medium" if clv_score >= 8
        else "Low"
    )

    clv_data.append({
        "customer_id": cid,
        "total_spend": total_spend,
        "visit_count": visit_count,
        "avg_repair_order_value": avg_ro,
        "months_as_customer": months,
        "referral_count": referral_count,
        "clv_score": clv_score,
        "clv_tier": clv_tier,
    })

clv_pdf = pd.DataFrame(clv_data)
print(f"  Created {len(clv_pdf)} CLV records | Tier dist: {clv_pdf['clv_tier'].value_counts().to_dict()}")

# =============================================================================
# 5. TECHNICIANS
# =============================================================================
print("Generating technicians...")

tech_first_names = [
    "Marcus", "Elena", "James", "Priya", "Carlos",
    "Sarah", "Dwayne", "Kim", "Roberto", "Angela",
    "Tyler", "Mei",
]
tech_last_names = [
    "Johnson", "Vasquez", "Chen", "Patel", "Martinez",
    "Williams", "Thompson", "Nguyen", "Garcia", "Brooks",
    "Henderson", "Liu",
]

technicians_data = []
for i in range(N_TECHNICIANS):
    spec = SPECIALIZATIONS[i % len(SPECIALIZATIONS)]
    n_certs = np.random.randint(2, 6)
    certs = list(np.random.choice(CERTIFICATIONS, size=n_certs, replace=False))

    technicians_data.append({
        "tech_id": f"TECH-{i+1:03d}",
        "first_name": tech_first_names[i],
        "last_name": tech_last_names[i],
        "certifications": ", ".join(certs),
        "specialization": spec,
        "hire_date": fake.date_between(
            start_date=END_DATE - timedelta(days=365 * 10),
            end_date=END_DATE - timedelta(days=90),
        ),
        "shift": np.random.choice(["Morning", "Afternoon"], p=[0.6, 0.4]),
    })

technicians_pdf = pd.DataFrame(technicians_data)
print(f"  Created {len(technicians_pdf)} technicians")

# =============================================================================
# 6. TECHNICIAN PERFORMANCE
# =============================================================================
print("Generating technician performance metrics...")

perf_data = []
for _, tech in technicians_pdf.iterrows():
    tid = tech["tech_id"]
    total_jobs = int(np.random.uniform(200, 2000))
    avg_time = round(np.random.uniform(40, 140), 1)
    reopen = round(np.random.uniform(1.0, 12.0), 1)
    csat = round(np.random.uniform(3.2, 5.0), 2)
    ftfr = round(np.random.uniform(75.0, 99.0), 1)

    perf_data.append({
        "tech_id": tid,
        "total_jobs": total_jobs,
        "avg_completion_time_mins": avg_time,
        "reopen_rate_pct": reopen,
        "customer_satisfaction_score": csat,
        "first_time_fix_rate_pct": ftfr,
    })

perf_pdf = pd.DataFrame(perf_data)
print(f"  Created {len(perf_pdf)} technician performance records")

# =============================================================================
# 7. SAVE TO VOLUME
# =============================================================================
print(f"\nSaving to {VOLUME_PATH}...")

spark.createDataFrame(customers_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/customers")
print("  ✓ customers")

spark.createDataFrame(vehicles_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/vehicles")
print("  ✓ vehicles")

spark.createDataFrame(appointments_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/appointments")
print("  ✓ appointments")

spark.createDataFrame(clv_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/customer_lifetime_value")
print("  ✓ customer_lifetime_value")

spark.createDataFrame(technicians_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/technicians")
print("  ✓ technicians")

spark.createDataFrame(perf_pdf).write.mode("overwrite").parquet(f"{VOLUME_PATH}/technician_performance")
print("  ✓ technician_performance")

# =============================================================================
# 8. VALIDATION
# =============================================================================
print("\n=== VALIDATION ===")
print(f"Customers: {len(customers_pdf)} | Loyalty dist: {customers_pdf['loyalty_tier'].value_counts().to_dict()}")
print(f"Vehicles: {len(vehicles_pdf)} | Unique customers with vehicles: {vehicles_pdf['customer_id'].nunique()}")
print(f"Appointments: {len(appointments_pdf)} | Today: {(appointments_pdf['appointment_date'] == TODAY).sum()}")
print(f"CLV: {len(clv_pdf)} | Avg CLV score: {clv_pdf['clv_score'].mean():.2f} | Max: {clv_pdf['clv_score'].max():.2f}")
print(f"Technicians: {len(technicians_pdf)} | Specializations: {technicians_pdf['specialization'].value_counts().to_dict()}")
print(f"Tech Performance: {len(perf_pdf)} | Avg CSAT: {perf_pdf['customer_satisfaction_score'].mean():.2f}")
print(f"Avg total spend: ${clv_pdf['total_spend'].mean():,.2f}")
print(f"Max total spend: ${clv_pdf['total_spend'].max():,.2f}")
print("\nDone! Structured data saved to volume.")
