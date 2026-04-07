"""Mock data simulating CDK dealership service advisor workflows."""

from datetime import datetime, timedelta
import random

NOW = datetime.now()


VEHICLES = {
    "VH001": {
        "vin": "1HGCM82633A004352",
        "year": 2022,
        "make": "Honda",
        "model": "Accord",
        "trim": "EX-L",
        "color": "Lunar Silver Metallic",
        "mileage": 34218,
        "engine": "1.5L Turbo I4",
        "transmission": "CVT",
        "license_plate": "ABC-1234",
    },
    "VH002": {
        "vin": "5YJSA1E26MF123456",
        "year": 2021,
        "make": "Toyota",
        "model": "Camry",
        "trim": "SE",
        "color": "Midnight Black",
        "mileage": 52803,
        "engine": "2.5L I4",
        "transmission": "8-Speed Automatic",
        "license_plate": "XYZ-9876",
    },
    "VH003": {
        "vin": "WBAPH5C55BA271190",
        "year": 2023,
        "make": "BMW",
        "model": "330i",
        "trim": "xDrive",
        "color": "Alpine White",
        "mileage": 12456,
        "engine": "2.0L Turbo I4",
        "transmission": "8-Speed Sport Automatic",
        "license_plate": "LUX-5555",
    },
    "VH004": {
        "vin": "1FTFW1E85MFA12345",
        "year": 2020,
        "make": "Ford",
        "model": "F-150",
        "trim": "XLT",
        "color": "Oxford White",
        "mileage": 67891,
        "engine": "3.5L EcoBoost V6",
        "transmission": "10-Speed Automatic",
        "license_plate": "TRK-4321",
    },
    "VH005": {
        "vin": "JN1TBNT30Z0000001",
        "year": 2023,
        "make": "Chevrolet",
        "model": "Equinox",
        "trim": "LT",
        "color": "Iron Gray Metallic",
        "mileage": 18234,
        "engine": "1.5L Turbo I4",
        "transmission": "6-Speed Automatic",
        "license_plate": "CHV-7890",
    },
}

CUSTOMERS = {
    "C001": {
        "name": "Maria Rodriguez",
        "phone": "(555) 234-5678",
        "email": "maria.rodriguez@email.com",
        "address": "1420 Oak Street, Springfield, IL 62704",
        "preferred_contact": "Text",
        "loyalty_tier": "Gold",
        "total_visits": 8,
        "lifetime_value": 12450.00,
        "vehicle_id": "VH001",
    },
    "C002": {
        "name": "James Chen",
        "phone": "(555) 876-5432",
        "email": "j.chen@email.com",
        "address": "305 Maple Ave, Springfield, IL 62701",
        "preferred_contact": "Email",
        "loyalty_tier": "Platinum",
        "total_visits": 15,
        "lifetime_value": 28930.00,
        "vehicle_id": "VH002",
    },
    "C003": {
        "name": "Sarah Thompson",
        "phone": "(555) 345-6789",
        "email": "s.thompson@email.com",
        "address": "782 Elm Drive, Springfield, IL 62703",
        "preferred_contact": "Phone",
        "loyalty_tier": "Silver",
        "total_visits": 3,
        "lifetime_value": 4200.00,
        "vehicle_id": "VH003",
    },
    "C004": {
        "name": "Robert Williams",
        "phone": "(555) 654-3210",
        "email": "r.williams@email.com",
        "address": "1100 Pine Road, Springfield, IL 62702",
        "preferred_contact": "Phone",
        "loyalty_tier": "Gold",
        "total_visits": 11,
        "lifetime_value": 19870.00,
        "vehicle_id": "VH004",
    },
    "C005": {
        "name": "Emily Davis",
        "phone": "(555) 789-0123",
        "email": "emily.d@email.com",
        "address": "445 Birch Lane, Springfield, IL 62705",
        "preferred_contact": "Text",
        "loyalty_tier": "Standard",
        "total_visits": 1,
        "lifetime_value": 890.00,
        "vehicle_id": "VH005",
    },
}

APPOINTMENTS = [
    {
        "id": "APT001",
        "customer_id": "C001",
        "vehicle_id": "VH001",
        "time": (NOW.replace(hour=8, minute=30)).strftime("%I:%M %p"),
        "type": "Oil Change + Tire Rotation",
        "status": "In Progress",
        "advisor": "Mike Johnson",
        "bay": 3,
        "estimated_duration": "1.5 hrs",
        "notes": "Customer mentioned slight vibration at highway speeds",
    },
    {
        "id": "APT002",
        "customer_id": "C002",
        "vehicle_id": "VH002",
        "time": (NOW.replace(hour=9, minute=0)).strftime("%I:%M %p"),
        "type": "Brake Inspection",
        "status": "Waiting",
        "advisor": "Mike Johnson",
        "bay": None,
        "estimated_duration": "2.0 hrs",
        "notes": "Squealing noise when braking. Customer says started 2 weeks ago.",
    },
    {
        "id": "APT003",
        "customer_id": "C003",
        "vehicle_id": "VH003",
        "time": (NOW.replace(hour=10, minute=15)).strftime("%I:%M %p"),
        "type": "30K Mile Service",
        "status": "Scheduled",
        "advisor": "Lisa Park",
        "bay": None,
        "estimated_duration": "3.0 hrs",
        "notes": "First major service. Premium package customer.",
    },
    {
        "id": "APT004",
        "customer_id": "C004",
        "vehicle_id": "VH004",
        "time": (NOW.replace(hour=11, minute=0)).strftime("%I:%M %p"),
        "type": "Engine Diagnostic",
        "status": "Scheduled",
        "advisor": "Mike Johnson",
        "bay": None,
        "estimated_duration": "1.0 hrs",
        "notes": "Check engine light on. Customer reports reduced power.",
    },
    {
        "id": "APT005",
        "customer_id": "C005",
        "vehicle_id": "VH005",
        "time": (NOW.replace(hour=13, minute=30)).strftime("%I:%M %p"),
        "type": "AC Not Cooling",
        "status": "Scheduled",
        "advisor": "Lisa Park",
        "bay": None,
        "estimated_duration": "1.5 hrs",
        "notes": "New customer. AC blowing warm air only.",
    },
]

DIAGNOSTIC_CODES = {
    "VH001": [
        {"code": "P0420", "description": "Catalyst System Efficiency Below Threshold (Bank 1)", "severity": "Medium", "system": "Emissions"},
    ],
    "VH002": [
        {"code": "C0035", "description": "Left Front Wheel Speed Sensor Circuit", "severity": "High", "system": "Brakes/ABS"},
        {"code": "C0040", "description": "Right Front Wheel Speed Sensor Circuit", "severity": "High", "system": "Brakes/ABS"},
    ],
    "VH003": [],
    "VH004": [
        {"code": "P0300", "description": "Random/Multiple Cylinder Misfire Detected", "severity": "Critical", "system": "Engine"},
        {"code": "P0171", "description": "System Too Lean (Bank 1)", "severity": "High", "system": "Fuel System"},
        {"code": "P0174", "description": "System Too Lean (Bank 2)", "severity": "High", "system": "Fuel System"},
    ],
    "VH005": [
        {"code": "B1421", "description": "AC Refrigerant Pressure Sensor Circuit Low", "severity": "Medium", "system": "HVAC"},
    ],
}

INSPECTION_ITEMS = {
    "VH001": [
        {"item": "Engine Oil", "status": "Replace", "urgency": "Due Now", "notes": "Dark, at minimum level"},
        {"item": "Tire Tread - Front", "status": "Monitor", "urgency": "Next Visit", "notes": "5/32\" remaining, uneven wear inside edge"},
        {"item": "Tire Tread - Rear", "status": "OK", "urgency": "None", "notes": "7/32\" remaining"},
        {"item": "Brake Pads - Front", "status": "OK", "urgency": "None", "notes": "6mm remaining"},
        {"item": "Brake Pads - Rear", "status": "Monitor", "urgency": "Next Visit", "notes": "4mm remaining"},
        {"item": "Air Filter", "status": "Replace", "urgency": "Due Now", "notes": "Visibly dirty, restricted airflow"},
        {"item": "Cabin Filter", "status": "OK", "urgency": "None", "notes": "Replaced 6 months ago"},
        {"item": "Battery", "status": "OK", "urgency": "None", "notes": "12.6V, load test passed"},
        {"item": "Coolant", "status": "OK", "urgency": "None", "notes": "Level good, no discoloration"},
        {"item": "Wiper Blades", "status": "Replace", "urgency": "Recommended", "notes": "Streaking, worn edges"},
    ],
    "VH002": [
        {"item": "Brake Pads - Front", "status": "Replace", "urgency": "Due Now", "notes": "2mm remaining, metal-on-metal contact beginning"},
        {"item": "Brake Rotors - Front", "status": "Replace", "urgency": "Due Now", "notes": "Scored, below minimum thickness"},
        {"item": "Brake Pads - Rear", "status": "Monitor", "urgency": "Next Visit", "notes": "4mm remaining"},
        {"item": "Brake Fluid", "status": "Replace", "urgency": "Due Now", "notes": "Moisture content high, due for flush"},
        {"item": "Tire Tread - All", "status": "OK", "urgency": "None", "notes": "6/32\" remaining"},
        {"item": "Engine Oil", "status": "OK", "urgency": "None", "notes": "Changed 2,000 miles ago"},
        {"item": "Battery", "status": "Monitor", "urgency": "6 Months", "notes": "11.9V under load, aging"},
    ],
}

SERVICE_HISTORY = {
    "C001": [
        {"date": (NOW - timedelta(days=120)).strftime("%m/%d/%Y"), "service": "Oil Change", "cost": 89.99, "mileage": 28500},
        {"date": (NOW - timedelta(days=240)).strftime("%m/%d/%Y"), "service": "Tire Rotation + Alignment", "cost": 149.99, "mileage": 22100},
        {"date": (NOW - timedelta(days=365)).strftime("%m/%d/%Y"), "service": "Brake Pad Replacement (Front)", "cost": 349.99, "mileage": 18000},
    ],
    "C002": [
        {"date": (NOW - timedelta(days=60)).strftime("%m/%d/%Y"), "service": "Oil Change", "cost": 79.99, "mileage": 49800},
        {"date": (NOW - timedelta(days=180)).strftime("%m/%d/%Y"), "service": "Transmission Fluid Change", "cost": 249.99, "mileage": 45000},
        {"date": (NOW - timedelta(days=300)).strftime("%m/%d/%Y"), "service": "50K Mile Service", "cost": 599.99, "mileage": 40200},
        {"date": (NOW - timedelta(days=450)).strftime("%m/%d/%Y"), "service": "Oil Change + Air Filter", "cost": 119.99, "mileage": 35000},
    ],
    "C003": [
        {"date": (NOW - timedelta(days=180)).strftime("%m/%d/%Y"), "service": "Oil Change (First Free)", "cost": 0.00, "mileage": 5000},
        {"date": (NOW - timedelta(days=90)).strftime("%m/%d/%Y"), "service": "Tire Rotation", "cost": 49.99, "mileage": 10200},
    ],
    "C004": [
        {"date": (NOW - timedelta(days=45)).strftime("%m/%d/%Y"), "service": "Oil Change", "cost": 99.99, "mileage": 65000},
        {"date": (NOW - timedelta(days=150)).strftime("%m/%d/%Y"), "service": "Spark Plug Replacement", "cost": 289.99, "mileage": 60000},
        {"date": (NOW - timedelta(days=200)).strftime("%m/%d/%Y"), "service": "Brake Service (Full)", "cost": 799.99, "mileage": 55000},
    ],
    "C005": [],
}

RECOMMENDED_SERVICES = {
    "VH001": [
        {"service": "Synthetic Oil Change", "price": 89.99, "priority": "Required", "reason": "Oil at minimum level, dark color indicates breakdown"},
        {"service": "Engine Air Filter Replacement", "price": 49.99, "priority": "Required", "reason": "Restricted airflow affecting performance and fuel economy"},
        {"service": "Tire Rotation", "price": 39.99, "priority": "Required", "reason": "Scheduled service, uneven wear detected on front tires"},
        {"service": "Front Wheel Alignment", "price": 99.99, "priority": "Recommended", "reason": "Uneven inside-edge tire wear indicates misalignment"},
        {"service": "Wiper Blade Replacement", "price": 34.99, "priority": "Recommended", "reason": "Streaking and worn edges, reduced visibility in rain"},
        {"service": "Catalytic Converter Diagnosis", "price": 149.99, "priority": "Investigate", "reason": "P0420 code present - may need further diagnosis"},
    ],
    "VH002": [
        {"service": "Front Brake Pad Replacement", "price": 299.99, "priority": "Critical", "reason": "2mm remaining, metal contact beginning. Safety hazard."},
        {"service": "Front Brake Rotor Replacement (Pair)", "price": 449.99, "priority": "Critical", "reason": "Scored and below minimum thickness. Must replace with pads."},
        {"service": "Brake Fluid Flush", "price": 129.99, "priority": "Required", "reason": "High moisture content degrades braking performance"},
        {"service": "ABS Wheel Speed Sensor (Left Front)", "price": 189.99, "priority": "Required", "reason": "Code C0035 - sensor malfunction affects ABS and traction control"},
        {"service": "ABS Wheel Speed Sensor (Right Front)", "price": 189.99, "priority": "Required", "reason": "Code C0040 - sensor malfunction affects ABS and traction control"},
        {"service": "Battery Replacement", "price": 179.99, "priority": "Recommended", "reason": "Low voltage under load, 4+ years old. Risk of failure."},
    ],
    "VH004": [
        {"service": "Ignition Coil Replacement (Set of 6)", "price": 549.99, "priority": "Critical", "reason": "Multiple cylinder misfire - likely failed coil(s)"},
        {"service": "Spark Plug Replacement (Set of 6)", "price": 189.99, "priority": "Required", "reason": "Replace with coils for complete ignition service"},
        {"service": "Fuel System Cleaning", "price": 199.99, "priority": "Required", "reason": "Lean codes indicate possible fuel delivery issue"},
        {"service": "MAF Sensor Cleaning/Replacement", "price": 89.99, "priority": "Investigate", "reason": "Lean condition may be caused by dirty MAF sensor"},
    ],
}

PARTS_AVAILABILITY = {
    "Front Brake Pads (Toyota Camry)": {"in_stock": True, "qty": 4, "eta": "In Stock"},
    "Front Brake Rotors (Toyota Camry)": {"in_stock": True, "qty": 2, "eta": "In Stock"},
    "ABS Wheel Speed Sensor (Toyota Camry)": {"in_stock": False, "qty": 0, "eta": "Next Day"},
    "Ignition Coil (Ford F-150 3.5L)": {"in_stock": True, "qty": 8, "eta": "In Stock"},
    "Spark Plugs (Ford F-150 3.5L)": {"in_stock": True, "qty": 12, "eta": "In Stock"},
    "MAF Sensor (Ford F-150 3.5L)": {"in_stock": False, "qty": 0, "eta": "2-3 Days"},
    "Engine Air Filter (Honda Accord)": {"in_stock": True, "qty": 6, "eta": "In Stock"},
    "Wiper Blades (Honda Accord)": {"in_stock": True, "qty": 10, "eta": "In Stock"},
    "Synthetic Oil 0W-20 (5 qt)": {"in_stock": True, "qty": 24, "eta": "In Stock"},
    "Oil Filter (Honda Accord)": {"in_stock": True, "qty": 15, "eta": "In Stock"},
}


CHATBOT_RESPONSES = {
    "service_queue": [
        "Based on today's queue, you have {count} appointments. {in_progress} vehicle(s) are currently in service and {waiting} are waiting.",
        "I can see the queue context. The highest priority is the brake inspection for {customer} — their {vehicle} has been making squealing noises for 2 weeks.",
        "Looking at your schedule, you have a gap between the 10:15 AM and 11:00 AM appointments that could be used for walk-ins.",
    ],
    "vehicle_checkin": [
        "I have the full context for this check-in. {customer} is a {tier} loyalty member with {visits} previous visits. Their {vehicle} is here for: {service_type}.",
        "Based on the customer notes and vehicle history, I'd recommend a multi-point inspection alongside the {service_type}. Last service was {last_service}.",
        "This vehicle's mileage ({mileage} mi) suggests it may be due for additional maintenance per the manufacturer schedule.",
    ],
    "diagnostics": [
        "I can see {code_count} diagnostic code(s) for this vehicle. The most critical is {top_code} — {top_desc}.",
        "Cross-referencing the DTC codes with the inspection results: {findings}",
        "Based on the diagnostic data and vehicle history, this appears to be a {system} system issue that should be addressed promptly.",
    ],
    "recommendations": [
        "I've assembled {rec_count} service recommendations totaling ${total:.2f}. {critical} are marked as critical safety items.",
        "For the customer conversation, I'd suggest leading with the safety-critical items first, then presenting the required maintenance, and finishing with recommended services.",
        "Parts availability looks good — {in_stock} of the needed parts are in stock. {backorder} items will need to be ordered.",
    ],
}
