"""
Product specifications for ASTM-compliant documents
Contains data for 10 fake products
"""

PRODUCTS = [
    {
        "designation": "F 2345-24",
        "title": "Standard Specification for High-Performance Aerospace Composite Panel",
        "issue_date": "January 15, 2024",
        "product_name": "aerospace composite panels",
        "scope": "carbon fiber reinforced polymer composite panels designed for aerospace structural applications",
        "intended_use": "aircraft fuselage sections, wing components, and interior structural elements requiring high strength-to-weight ratios",
        "referenced_standards": [
            "D 3039/D 3039M Test Method for Tensile Properties of Polymer Matrix Composite Materials",
            "D 790 Test Methods for Flexural Properties of Unreinforced and Reinforced Plastics",
            "D 2344 Test Method for Short-Beam Strength of Polymer Matrix Composite Materials",
            "E 1640 Test Method for Assignment of the Glass Transition Temperature by Dynamic Mechanical Analysis"
        ],
        "terminology": {
            "composite panel": "a laminated structure consisting of multiple plies of carbon fiber fabric impregnated with epoxy resin",
            "cure cycle": "the time-temperature profile used during manufacturing to polymerize the resin matrix",
            "void content": "the volumetric percentage of air pockets or voids present in the cured laminate"
        },
        "classification_basis": "fiber orientation, thickness, and intended service temperature",
        "classifications": [
            {"name": "Type I", "description": "Unidirectional layup, 3-6 mm thickness, service temperature up to 120°C"},
            {"name": "Type II", "description": "Quasi-isotropic layup, 6-12 mm thickness, service temperature up to 150°C"},
            {"name": "Type III", "description": "Custom layup, variable thickness, service temperature up to 180°C"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Type (I, II, or III)",
            "Dimensions (length × width × thickness in mm)",
            "Quantity (number of panels)",
            "Surface finish requirements (if any)"
        ],
        "materials": [
            "The reinforcement shall consist of continuous carbon fiber fabric with a minimum tensile modulus of 230 GPa.",
            "The matrix shall be epoxy resin compatible with autoclave or vacuum bag processing.",
            "All materials shall be from certified aerospace suppliers with documented traceability."
        ],
        "chemical_composition": {
            "Carbon fiber (by weight)": "60 ± 3%",
            "Epoxy resin": "38 ± 3%",
            "Void content (max)": "< 2%"
        },
        "requirements": [
            {"property": "Tensile strength", "value": "≥ 600 MPa", "test_method": "ASTM D 3039"},
            {"property": "Flexural modulus", "value": "≥ 50 GPa", "test_method": "ASTM D 790"},
            {"property": "Short-beam strength", "value": "≥ 70 MPa", "test_method": "ASTM D 2344"},
            {"property": "Glass transition temp", "value": "≥ 180°C", "test_method": "ASTM E 1640"}
        ],
        "dimensions": [
            "Standard panel dimensions shall be 1000 mm × 500 mm with thickness tolerance of ±0.2 mm.",
            "Custom dimensions are available upon request with tolerance of ±1.0 mm for length and width."
        ],
        "workmanship": "Panels shall be free from delaminations, wrinkles, dry spots, and foreign material inclusions. Surface finish shall be smooth with no visual defects.",
        "sampling": "Sampling shall be conducted in accordance with a statistically valid plan. At minimum, one panel per production lot shall be selected for destructive testing.",
        "test_methods": [
            {"property": "Tensile Testing", "description": "Conduct tensile tests per ASTM D 3039 using specimens cut from the qualification panels."},
            {"property": "Flexural Testing", "description": "Perform three-point bend tests per ASTM D 790."},
            {"property": "Void Content Analysis", "description": "Determine void content using ultrasonic C-scan or acid digestion methods."}
        ],
        "product_marking": "Each panel shall be permanently marked with the manufacturer's name, production date, lot number, and ASTM designation.",
        "packaging": "Panels shall be packaged in moisture-barrier bags with desiccant and packed in rigid containers to prevent damage during shipping.",
        "keywords": ["aerospace", "carbon fiber", "composite panel", "epoxy", "structural", "high-performance"]
    },
    
    {
        "designation": "B 1567-24",
        "title": "Standard Specification for Titanium Grade 5 Alloy Bar",
        "issue_date": "March 22, 2024",
        "product_name": "titanium alloy bars",
        "scope": "titanium Grade 5 (Ti-6Al-4V) alloy bars for general engineering and aerospace applications",
        "intended_use": "manufacturing of aerospace components, medical implants, and high-performance automotive parts requiring excellent strength-to-weight ratio and corrosion resistance",
        "referenced_standards": [
            "B 348 Specification for Titanium and Titanium Alloy Bars and Billets",
            "E 8 Test Methods for Tension Testing of Metallic Materials",
            "E 384 Test Method for Microindentation Hardness of Materials",
            "E 1409 Test Method for Determination of Oxygen and Nitrogen in Titanium"
        ],
        "terminology": {
            "alpha-beta alloy": "a titanium alloy containing both alpha and beta phase stabilizing elements",
            "mill annealed": "heat treatment condition produced during manufacturing to optimize mechanical properties",
            "ultimate tensile strength": "the maximum stress that a material can withstand while being stretched"
        },
        "classification_basis": "diameter range and heat treatment condition",
        "classifications": [
            {"name": "Grade 5A", "description": "Annealed condition, diameter 6-25 mm"},
            {"name": "Grade 5B", "description": "Annealed condition, diameter 25-75 mm"},
            {"name": "Grade 5C", "description": "Solution treated and aged, diameter 6-50 mm"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Grade (5A, 5B, or 5C)",
            "Diameter (mm)",
            "Length (m)",
            "Quantity (number of bars or total weight in kg)",
            "Heat treatment condition"
        ],
        "materials": [
            "The titanium alloy shall be produced by vacuum arc remelting (VAR) or vacuum induction melting (VIM).",
            "The material shall be hot worked and heat treated to meet the specified mechanical properties.",
            "Chemical composition shall conform to requirements specified in Section 7."
        ],
        "chemical_composition": {
            "Aluminum (Al)": "5.5 - 6.75%",
            "Vanadium (V)": "3.5 - 4.5%",
            "Iron (Fe), max": "0.30%",
            "Oxygen (O), max": "0.20%",
            "Carbon (C), max": "0.08%",
            "Nitrogen (N), max": "0.05%",
            "Hydrogen (H), max": "0.015%",
            "Titanium (Ti)": "Balance"
        },
        "requirements": [
            {"property": "Tensile strength", "value": "≥ 895 MPa", "test_method": "ASTM E 8"},
            {"property": "Yield strength", "value": "≥ 828 MPa", "test_method": "ASTM E 8"},
            {"property": "Elongation", "value": "≥ 10%", "test_method": "ASTM E 8"},
            {"property": "Hardness", "value": "280-340 HV", "test_method": "ASTM E 384"}
        ],
        "dimensions": [
            "Bar diameter tolerance shall be ±0.5 mm for diameters up to 25 mm.",
            "For diameters greater than 25 mm, tolerance shall be ±1.0 mm.",
            "Length tolerance shall be +25 mm/-0 mm.",
            "Straightness shall not exceed 2 mm per meter of length."
        ],
        "workmanship": "Bars shall be free from cracks, laps, seams, and other surface defects. Minor surface imperfections may be removed by grinding provided the diameter remains within tolerance.",
        "sampling": "One tensile specimen and one chemistry sample shall be taken from each heat. Additional testing may be required for critical applications.",
        "test_methods": [
            {"property": "Tensile Testing", "description": "Machine tensile specimens per ASTM E 8 and test at ambient temperature."},
            {"property": "Chemical Analysis", "description": "Perform chemical analysis using appropriate methods for each element."},
            {"property": "Hardness Testing", "description": "Conduct Vickers hardness testing per ASTM E 384 on prepared cross-sections."}
        ],
        "product_marking": "Each bar shall be tagged or marked with heat number, grade designation, and manufacturer identification.",
        "packaging": "Bars shall be bundled and wrapped to prevent damage and contamination during transit. Protective end caps shall be applied.",
        "keywords": ["titanium", "Ti-6Al-4V", "Grade 5", "bar", "aerospace", "alloy", "biocompatible"]
    },
    
    {
        "designation": "D 4892-24",
        "title": "Standard Specification for Ultra-High Molecular Weight Polyethylene (UHMWPE) Sheet",
        "issue_date": "February 10, 2024",
        "product_name": "UHMWPE sheets",
        "scope": "ultra-high molecular weight polyethylene sheets for wear-resistant and impact-resistant applications",
        "intended_use": "manufacturing of conveyor components, chute liners, bearing surfaces, and machine parts requiring low friction and high abrasion resistance",
        "referenced_standards": [
            "D 792 Test Methods for Density and Specific Gravity of Plastics",
            "D 638 Test Method for Tensile Properties of Plastics",
            "D 4020 Test Method for Ultra-High-Molecular-Weight Polyethylene Molding and Extrusion Materials",
            "D 1894 Test Method for Static and Kinetic Coefficients of Friction of Plastic Film"
        ],
        "terminology": {
            "ultra-high molecular weight": "polyethylene with molecular weight greater than 3 million g/mol",
            "virgin material": "polymer that has not been previously processed or recycled",
            "coefficient of friction": "the ratio of the force of friction between two bodies"
        },
        "classification_basis": "thickness and molecular weight grade",
        "classifications": [
            {"name": "Type A", "description": "Molecular weight 3-6 million g/mol, thickness 6-25 mm"},
            {"name": "Type B", "description": "Molecular weight 6-9 million g/mol, thickness 25-100 mm"},
            {"name": "Type C", "description": "Molecular weight > 9 million g/mol, custom thickness"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Type (A, B, or C)",
            "Sheet dimensions (length × width × thickness in mm)",
            "Quantity (number of sheets or total area in m²)",
            "Color (natural white, black, or custom)"
        ],
        "materials": [
            "Sheets shall be manufactured from virgin UHMWPE resin meeting molecular weight requirements.",
            "No reground or recycled material shall be used without prior approval.",
            "Colorants and additives, if used, shall not adversely affect mechanical properties."
        ],
        "requirements": [
            {"property": "Density", "value": "0.930-0.945 g/cm³", "test_method": "ASTM D 792"},
            {"property": "Tensile strength", "value": "≥ 21 MPa", "test_method": "ASTM D 638"},
            {"property": "Elongation at break", "value": "≥ 300%", "test_method": "ASTM D 638"},
            {"property": "Coefficient of friction", "value": "≤ 0.20", "test_method": "ASTM D 1894"}
        ],
        "dimensions": [
            "Standard sheet sizes are 1220 mm × 2440 mm. Custom sizes available upon request.",
            "Thickness tolerance shall be ±10% for sheets up to 50 mm thick.",
            "For sheets greater than 50 mm thick, tolerance shall be ±15%.",
            "Flatness deviation shall not exceed 5 mm per meter."
        ],
        "workmanship": "Sheets shall have uniform color and be free from cracks, voids, foreign inclusions, and surface defects that would impair function.",
        "sampling": "One test specimen per production lot shall be sampled for property verification. Lot size shall not exceed 5000 kg.",
        "test_methods": [
            {"property": "Density Measurement", "description": "Determine density using water displacement method per ASTM D 792."},
            {"property": "Tensile Testing", "description": "Machine specimens per ASTM D 638 and test at standard conditions."},
            {"property": "Friction Testing", "description": "Measure static and kinetic friction coefficients per ASTM D 1894 against polished steel."}
        ],
        "product_marking": "Each sheet shall be labeled with manufacturer name, material type, production date, and lot number on protective film.",
        "packaging": "Sheets shall be wrapped in protective polyethylene film and stacked on pallets with corner protection. Moisture barriers are not required.",
        "keywords": ["UHMWPE", "polyethylene", "wear resistant", "low friction", "impact resistant", "sheet"]
    },
    
    {
        "designation": "C 2789-24",
        "title": "Standard Specification for Advanced Ceramic Matrix Composite (CMC) Turbine Components",
        "issue_date": "April 8, 2024",
        "product_name": "ceramic matrix composite turbine components",
        "scope": "silicon carbide fiber reinforced ceramic matrix composite components for high-temperature turbine applications",
        "intended_use": "gas turbine engines, aerospace propulsion systems, and power generation equipment operating at temperatures exceeding 1200°C",
        "referenced_standards": [
            "C 1275 Test Method for Monotonic Tensile Behavior of Continuous Fiber-Reinforced Advanced Ceramics",
            "C 1358 Test Method for Monotonic Compressive Strength Testing of Continuous Fiber-Reinforced Advanced Ceramics",
            "C 1366 Test Method for Tensile Strength of Monolithic Advanced Ceramics at Elevated Temperatures",
            "E 1461 Test Method for Thermal Diffusivity by the Flash Method"
        ],
        "terminology": {
            "ceramic matrix composite": "a composite material consisting of ceramic fibers embedded in a ceramic matrix",
            "environmental barrier coating": "a protective coating applied to prevent oxidation and degradation in combustion environments",
            "interphase": "a thin coating applied to fibers to control fiber-matrix bonding and enable toughening mechanisms"
        },
        "classification_basis": "fiber architecture, matrix composition, and maximum service temperature",
        "classifications": [
            {"name": "Class 1", "description": "2D woven SiC/SiC, service temperature up to 1200°C"},
            {"name": "Class 2", "description": "2.5D woven SiC/SiC, service temperature up to 1400°C"},
            {"name": "Class 3", "description": "3D woven SiC/SiC, service temperature up to 1500°C"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Class (1, 2, or 3)",
            "Component type and geometry",
            "Quantity",
            "Environmental barrier coating specification (if required)",
            "Quality assurance level"
        ],
        "materials": [
            "Reinforcement shall be continuous silicon carbide fibers with diameter 10-15 μm.",
            "Matrix shall be silicon carbide deposited by chemical vapor infiltration (CVI) or polymer infiltration and pyrolysis (PIP).",
            "Fiber coating (interphase) shall be boron nitride or carbon with thickness 0.1-0.5 μm."
        ],
        "chemical_composition": {
            "Silicon carbide (fiber + matrix)": "≥ 85%",
            "Boron nitride (interphase)": "2-5%",
            "Free silicon": "< 5%",
            "Oxygen": "< 2%",
            "Porosity": "10-20%"
        },
        "requirements": [
            {"property": "Tensile strength (RT)", "value": "≥ 200 MPa", "test_method": "ASTM C 1275"},
            {"property": "Tensile strength (1200°C)", "value": "≥ 150 MPa", "test_method": "ASTM C 1366"},
            {"property": "Elastic modulus", "value": "200-300 GPa", "test_method": "ASTM C 1275"},
            {"property": "Thermal conductivity", "value": "15-25 W/m·K", "test_method": "ASTM E 1461"}
        ],
        "dimensions": [
            "Dimensional tolerances shall be specified on component drawings.",
            "General tolerance on machined surfaces shall be ±0.25 mm unless otherwise specified.",
            "Surface roughness shall be Ra ≤ 3.2 μm on critical surfaces."
        ],
        "workmanship": "Components shall be free from cracks, large pores, and delaminations detectable by non-destructive evaluation. Minor surface defects may be acceptable if they do not affect structural integrity.",
        "sampling": "Qualification specimens representing each component geometry shall be manufactured and tested. Production components shall undergo 100% non-destructive inspection.",
        "test_methods": [
            {"property": "Mechanical Testing", "description": "Test representative specimens at room temperature and elevated temperatures per ASTM C 1275 and C 1366."},
            {"property": "Microstructural Analysis", "description": "Examine polished cross-sections using optical and scanning electron microscopy."},
            {"property": "Non-Destructive Evaluation", "description": "Inspect all components using ultrasonic, radiographic, or computed tomography methods."}
        ],
        "product_marking": "Components shall be marked with unique serial numbers using laser engraving or other permanent methods that do not compromise structural integrity.",
        "packaging": "Components shall be individually packaged in custom foam inserts within rigid containers. Containers shall be sealed and labeled with handling instructions.",
        "keywords": ["ceramic matrix composite", "CMC", "silicon carbide", "turbine", "high temperature", "aerospace"]
    },
    
    {
        "designation": "A 3456-24",
        "title": "Standard Specification for High-Strength Low-Alloy Structural Steel Plate",
        "issue_date": "January 30, 2024",
        "product_name": "HSLA structural steel plates",
        "scope": "high-strength low-alloy structural steel plates for construction and heavy equipment applications",
        "intended_use": "bridges, buildings, pressure vessels, mining equipment, and other structural applications requiring high strength and good weldability",
        "referenced_standards": [
            "A 6 Specification for General Requirements for Rolled Structural Steel Bars, Plates, Shapes, and Sheet Piling",
            "A 370 Test Methods and Definitions for Mechanical Testing of Steel Products",
            "E 23 Test Methods for Notched Bar Impact Testing of Metallic Materials",
            "E 3 Guide for Preparation of Metallographic Specimens"
        ],
        "terminology": {
            "high-strength low-alloy steel": "steel with enhanced mechanical properties achieved through microalloying and controlled processing",
            "normalized": "heat treatment involving heating above the upper critical temperature followed by air cooling",
            "Charpy V-notch energy": "measure of material toughness determined by impact testing of notched specimens"
        },
        "classification_basis": "minimum yield strength and thickness range",
        "classifications": [
            {"name": "Grade 50", "description": "Minimum yield strength 345 MPa, thickness 6-50 mm"},
            {"name": "Grade 60", "description": "Minimum yield strength 415 MPa, thickness 6-40 mm"},
            {"name": "Grade 70", "description": "Minimum yield strength 485 MPa, thickness 6-32 mm"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Grade (50, 60, or 70)",
            "Dimensions (length × width × thickness in mm)",
            "Quantity (number of plates or total weight in tonnes)",
            "Heat treatment condition",
            "Impact testing temperature (if required)"
        ],
        "materials": [
            "Steel shall be killed and produced to fine grain practice.",
            "Material may be supplied in hot-rolled, normalized, or thermomechanically processed condition.",
            "Chemical composition shall be optimized for weldability and shall meet requirements in Section 7."
        ],
        "chemical_composition": {
            "Carbon (C), max": "0.18%",
            "Manganese (Mn)": "0.80-1.50%",
            "Phosphorus (P), max": "0.025%",
            "Sulfur (S), max": "0.015%",
            "Silicon (Si)": "0.15-0.50%",
            "Niobium (Nb)": "0.02-0.05%",
            "Vanadium (V)": "0.03-0.08%",
            "Copper (Cu), max": "0.35%"
        },
        "requirements": [
            {"property": "Yield strength (Grade 50)", "value": "≥ 345 MPa", "test_method": "ASTM A 370"},
            {"property": "Tensile strength", "value": "450-620 MPa", "test_method": "ASTM A 370"},
            {"property": "Elongation (50 mm)", "value": "≥ 18%", "test_method": "ASTM A 370"},
            {"property": "Charpy V-notch (-20°C)", "value": "≥ 27 J avg", "test_method": "ASTM E 23"}
        ],
        "dimensions": [
            "Thickness tolerance shall conform to ASTM A 6 for plates.",
            "Width and length tolerances shall be per ASTM A 6 unless otherwise specified.",
            "Flatness shall meet requirements of ASTM A 6 for the applicable thickness."
        ],
        "workmanship": "Plates shall be free from injurious defects. Surface imperfections may be removed by grinding provided minimum thickness is maintained.",
        "sampling": "One set of mechanical tests shall be performed per heat and thickness range. Impact tests required when specified.",
        "test_methods": [
            {"property": "Tensile Testing", "description": "Machine longitudinal tensile specimens per ASTM A 370 and test to determine yield strength, tensile strength, and elongation."},
            {"property": "Impact Testing", "description": "Prepare Charpy V-notch specimens per ASTM E 23 and test at specified temperature."},
            {"property": "Chemical Analysis", "description": "Perform ladle or product analysis to verify chemistry compliance."}
        ],
        "product_marking": "Plates shall be stenciled or tagged with heat number, grade, thickness, and manufacturer identification.",
        "packaging": "Plates shall be bundled and strapped for shipment. Coating or wrapping may be specified to prevent corrosion during transit.",
        "keywords": ["steel", "HSLA", "structural", "plate", "high strength", "weldable", "construction"]
    },
    
    {
        "designation": "F 3890-24",
        "title": "Standard Specification for Bioabsorbable Polymer Surgical Mesh",
        "issue_date": "May 15, 2024",
        "product_name": "bioabsorbable surgical mesh",
        "scope": "bioabsorbable polymer mesh for soft tissue reinforcement and repair in surgical procedures",
        "intended_use": "hernia repair, pelvic floor reconstruction, and other soft tissue support applications where temporary reinforcement is needed",
        "referenced_standards": [
            "F 2103 Guide for Characterization and Testing of Biomaterials for Surgical Mesh",
            "D 638 Test Method for Tensile Properties of Plastics",
            "F 1635 Test Method for in vitro Degradation Testing of Hydrolytically Degradable Polymer Resins",
            "F 756 Practice for Assessment of Hemolytic Properties of Materials"
        ],
        "terminology": {
            "bioabsorbable": "capable of being absorbed by living tissue through biological processes",
            "degradation time": "the time required for the polymer to lose mechanical integrity and be absorbed by the body",
            "mesh porosity": "the percentage of void space in the mesh structure"
        },
        "classification_basis": "polymer composition and degradation rate",
        "classifications": [
            {"name": "Type I", "description": "Poly(glycolic acid) based, complete absorption in 3-4 months"},
            {"name": "Type II", "description": "Poly(lactic acid) based, complete absorption in 12-18 months"},
            {"name": "Type III", "description": "Poly(glycolic-co-lactic acid) copolymer, complete absorption in 6-9 months"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Type (I, II, or III)",
            "Mesh dimensions (length × width in cm)",
            "Pore size specification",
            "Quantity (number of units)",
            "Sterile or non-sterile",
            "Packaging requirements"
        ],
        "materials": [
            "Polymers shall be medical grade with documented biocompatibility testing.",
            "Materials shall be free from additives, plasticizers, or colorants not approved for implantation.",
            "Raw materials shall have certificates of analysis demonstrating compliance with specifications."
        ],
        "requirements": [
            {"property": "Tensile strength (initial)", "value": "≥ 100 N/cm width", "test_method": "ASTM D 638"},
            {"property": "Elongation at break", "value": "30-80%", "test_method": "ASTM D 638"},
            {"property": "Pore size", "value": "0.5-3.0 mm", "test_method": "Microscopy"},
            {"property": "Porosity", "value": "≥ 70%", "test_method": "Calculated"}
        ],
        "dimensions": [
            "Standard mesh dimensions range from 5 cm × 5 cm to 30 cm × 30 cm.",
            "Dimension tolerance shall be ±5 mm for sides less than 15 cm and ±10 mm for sides greater than 15 cm.",
            "Thickness shall be 0.3-1.5 mm depending on mesh design."
        ],
        "workmanship": "Mesh shall be free from tears, holes, and contamination. Edges may be finished or unfinished as specified. Color shall be uniform.",
        "sampling": "Sampling plans shall follow ISO 2859-1 acceptable quality limit procedures. Biocompatibility testing required for each material lot.",
        "test_methods": [
            {"property": "Mechanical Testing", "description": "Test mesh samples in both machine and cross directions per ASTM D 638 adapted for mesh geometry."},
            {"property": "Degradation Testing", "description": "Evaluate in vitro degradation in phosphate buffered saline at 37°C per ASTM F 1635."},
            {"property": "Biocompatibility", "description": "Conduct cytotoxicity, sensitization, and irritation testing per ISO 10993 series standards."}
        ],
        "product_marking": "Sterile packages shall be labeled with product name, dimensions, lot number, sterilization method, expiration date, and manufacturer information.",
        "packaging": "Individual meshes shall be packaged in pouches using validated sterilization-compatible materials. Sterilization by ethylene oxide or gamma radiation.",
        "keywords": ["bioabsorbable", "surgical mesh", "hernia", "polymer", "biodegradable", "implant", "medical device"]
    },
    
    {
        "designation": "E 2567-24",
        "title": "Standard Specification for Lithium-Ion Battery Cells for Electric Vehicle Applications",
        "issue_date": "March 5, 2024",
        "product_name": "lithium-ion battery cells",
        "scope": "high-energy density lithium-ion cylindrical cells for electric vehicle battery packs",
        "intended_use": "powering battery electric vehicles (BEVs) and plug-in hybrid electric vehicles (PHEVs) requiring high energy storage capacity and power delivery",
        "referenced_standards": [
            "E 2950 Standard Guide for Chemical Analysis of Lithium-Ion Battery Materials",
            "D 7032 Test Method for Determination of Fluorine in Aromatic Compounds",
            "IEC 62660 Secondary lithium-ion cells for the propulsion of electric road vehicles",
            "UN 38.3 Recommendations on the Transport of Dangerous Goods, Manual of Tests and Criteria"
        ],
        "terminology": {
            "nominal capacity": "the charge capacity of a cell measured under standard discharge conditions",
            "C-rate": "a measure of charge or discharge current relative to cell capacity",
            "state of charge": "the percentage of available capacity remaining in a cell"
        },
        "classification_basis": "cell format, capacity range, and cathode chemistry",
        "classifications": [
            {"name": "Format A", "description": "Cylindrical 18650, capacity 2.5-3.5 Ah, NMC cathode"},
            {"name": "Format B", "description": "Cylindrical 21700, capacity 4.0-5.0 Ah, NMC cathode"},
            {"name": "Format C", "description": "Cylindrical 46800, capacity 20-25 Ah, NCA cathode"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Cell format (A, B, or C)",
            "Minimum capacity (Ah)",
            "Quantity (number of cells)",
            "Voltage and temperature specifications",
            "Quality grade (automotive or industrial)"
        ],
        "materials": [
            "Cathode active material shall be lithium nickel manganese cobalt oxide (NMC) or lithium nickel cobalt aluminum oxide (NCA).",
            "Anode shall be graphite-based with optional silicon content not exceeding 5%.",
            "Electrolyte shall be lithium hexafluorophosphate (LiPF6) in organic carbonate solvents.",
            "Separator shall be tri-layer polyolefin with ceramic coating."
        ],
        "chemical_composition": {
            "Cathode (NMC 811)": "LiNi0.8Mn0.1Co0.1O2",
            "Anode": "Graphite (95-100%) + Si (0-5%)",
            "Electrolyte": "1M LiPF6 in EC:EMC (3:7)",
            "Moisture content": "< 20 ppm"
        },
        "requirements": [
            {"property": "Nominal capacity", "value": "≥ Rated capacity", "test_method": "IEC 62660-1"},
            {"property": "Energy density", "value": "≥ 250 Wh/kg", "test_method": "Calculated"},
            {"property": "Cycle life (80% retention)", "value": "≥ 1000 cycles", "test_method": "IEC 62660-1"},
            {"property": "DC resistance", "value": "≤ 20 mΩ", "test_method": "IEC 62660-1"}
        ],
        "dimensions": [
            "Cell dimensions shall conform to standard battery formats with ±0.5 mm tolerance.",
            "18650: Diameter 18.4 ±0.2 mm, Length 65.2 ±0.5 mm",
            "21700: Diameter 21.0 ±0.2 mm, Length 70.5 ±0.5 mm",
            "Weight variation shall not exceed ±3% within a production lot."
        ],
        "workmanship": "Cells shall be free from physical damage, electrolyte leakage, and terminal defects. Insulation sleeve shall be properly applied and free from tears.",
        "sampling": "Sample size shall follow ANSI/ASQC Z1.4 acceptable quality level of 0.25%. Each lot shall undergo safety and performance testing.",
        "test_methods": [
            {"property": "Capacity Testing", "description": "Fully charge cells to 4.2V, then discharge at 0.5C to 2.5V while measuring capacity."},
            {"property": "Cycle Life Testing", "description": "Cycle cells between 100% and 0% SOC at 1C rate until capacity drops to 80% of initial."},
            {"property": "Safety Testing", "description": "Conduct overcharge, short circuit, crush, and thermal abuse tests per UN 38.3 and IEC 62660-2."}
        ],
        "product_marking": "Each cell shall be marked with manufacturer name, model number, rated capacity, rated voltage, and date code. Polarity shall be clearly indicated.",
        "packaging": "Cells shall be packaged at 30-50% state of charge in anti-static trays with protective caps. Packages shall comply with UN 38.3 shipping requirements.",
        "keywords": ["lithium-ion", "battery", "electric vehicle", "energy storage", "rechargeable", "NMC", "automotive"]
    },
    
    {
        "designation": "C 1678-24",
        "title": "Standard Specification for Advanced Silicon Nitride Ceramic Bearing Balls",
        "issue_date": "February 28, 2024",
        "product_name": "silicon nitride ceramic bearing balls",
        "scope": "high-performance silicon nitride ceramic balls for use in rolling element bearings",
        "intended_use": "aerospace bearings, machine tool spindles, and high-speed rotating machinery requiring low density, high stiffness, and resistance to corrosion",
        "referenced_standards": [
            "C 1326 Test Method for Knoop Indentation Hardness of Advanced Ceramics",
            "C 1327 Test Method for Vickers Indentation Hardness of Advanced Ceramics",
            "C 1624 Test Method for Adhesion Strength and Mechanical Failure Modes of Ceramic Coatings",
            "ISO 3290 Rolling bearings - Balls"
        ],
        "terminology": {
            "silicon nitride": "a ceramic material with composition Si3N4 produced by hot isostatic pressing",
            "grade number": "specification of geometric and surface quality per ISO 3290",
            "surface waviness": "the periodic deviation of the surface from perfect sphericity"
        },
        "classification_basis": "diameter and precision grade",
        "classifications": [
            {"name": "Grade 3", "description": "Diameter 3.175-25.4 mm, ultra-precision grade"},
            {"name": "Grade 5", "description": "Diameter 3.175-50.8 mm, high-precision grade"},
            {"name": "Grade 10", "description": "Diameter 3.175-76.2 mm, standard-precision grade"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Grade (3, 5, or 10)",
            "Nominal ball diameter (mm)",
            "Quantity",
            "Lot diameter variation tolerance",
            "Surface finish requirements"
        ],
        "materials": [
            "Balls shall be manufactured from silicon nitride powder densified by hot isostatic pressing (HIP).",
            "Sintering aids shall be limited to yttria (Y2O3) and/or alumina (Al2O3).",
            "Final density shall be ≥ 99.5% of theoretical density."
        ],
        "chemical_composition": {
            "Silicon nitride (Si3N4)": "≥ 90%",
            "Yttrium oxide (Y2O3)": "2-8%",
            "Aluminum oxide (Al2O3)": "2-8%",
            "Metallic impurities": "< 0.1%"
        },
        "requirements": [
            {"property": "Density", "value": "3.20-3.28 g/cm³", "test_method": "Archimedes"},
            {"property": "Hardness", "value": "≥ 1500 HV1", "test_method": "ASTM C 1327"},
            {"property": "Fracture toughness", "value": "≥ 6.0 MPa·m^0.5", "test_method": "Indentation"},
            {"property": "Flexural strength", "value": "≥ 700 MPa", "test_method": "4-point bend"}
        ],
        "dimensions": [
            "Diameter tolerance shall conform to ISO 3290 for the specified grade.",
            "Sphericity deviation: Grade 3 ≤ 0.13 μm, Grade 5 ≤ 0.25 μm, Grade 10 ≤ 0.50 μm",
            "Surface roughness Ra: Grade 3 ≤ 0.010 μm, Grade 5 ≤ 0.020 μm, Grade 10 ≤ 0.032 μm",
            "Lot diameter variation shall not exceed grade tolerance."
        ],
        "workmanship": "Balls shall be free from cracks, chips, pits, and scratches. Surface finish shall be achieved through lapping and polishing operations.",
        "sampling": "100% inspection of diameter and surface defects. Destructive testing on representative samples from each manufacturing lot.",
        "test_methods": [
            {"property": "Dimensional Measurement", "description": "Measure diameter using laser micrometry or precision mechanical gauging per ISO 3290."},
            {"property": "Hardness Testing", "description": "Determine Vickers hardness on polished flat ground on balls per ASTM C 1327."},
            {"property": "Microstructural Examination", "description": "Examine polished and etched cross-sections to verify grain size and phase distribution."}
        ],
        "product_marking": "Balls shall be supplied in labeled containers indicating diameter, grade, quantity, lot number, and manufacturer.",
        "packaging": "Balls shall be packaged in compartmented trays or bulk containers with protective cushioning. Containers shall be sealed to prevent contamination.",
        "keywords": ["silicon nitride", "ceramic", "bearing balls", "high-performance", "aerospace", "precision"]
    },
    
    {
        "designation": "D 5678-24",
        "title": "Standard Specification for Aramid Fiber Ballistic Protection Fabric",
        "issue_date": "April 12, 2024",
        "product_name": "aramid ballistic fabric",
        "scope": "high-strength aramid fiber woven fabrics for ballistic protection applications",
        "intended_use": "manufacturing of soft body armor, helmets, vehicle armor panels, and protective equipment for law enforcement and military personnel",
        "referenced_standards": [
            "D 7269 Test Methods for Tensile Testing of Aramid Yarns",
            "D 3822 Test Method for Tensile Properties of Single Textile Fibers",
            "D 3776 Test Methods for Mass Per Unit Area (Weight) of Fabric",
            "NIJ 0101.06 Ballistic Resistance of Body Armor"
        ],
        "terminology": {
            "aramid fiber": "a class of heat-resistant and strong synthetic fibers with aromatic polyamide structure",
            "denier": "unit of linear mass density of fibers equal to mass in grams per 9000 meters",
            "ballistic performance": "the ability of material to resist penetration by projectiles"
        },
        "classification_basis": "fiber type, fabric construction, and areal density",
        "classifications": [
            {"name": "Style 328", "description": "Para-aramid, plain weave, 200 g/m², threat level IIA"},
            {"name": "Style 706", "description": "Para-aramid, basket weave, 440 g/m², threat level IIIA"},
            {"name": "Style 929", "description": "Meta-para aramid blend, plain weave, 360 g/m², threat level II"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Style (328, 706, or 929)",
            "Width (cm)",
            "Quantity (linear meters or m²)",
            "Color (natural yellow, or custom dyed)",
            "Edge finish (selvage or cut)"
        ],
        "materials": [
            "Yarns shall be made from 100% virgin aramid fiber with no reprocessed content.",
            "Para-aramid fibers shall have minimum tensile strength of 3.0 GPa.",
            "Weaving shall be performed on modern looms with appropriate tension control."
        ],
        "requirements": [
            {"property": "Tensile strength (warp)", "value": "≥ 2200 N/cm", "test_method": "ASTM D 5034"},
            {"property": "Tensile strength (fill)", "value": "≥ 2200 N/cm", "test_method": "ASTM D 5034"},
            {"property": "Areal density", "value": "±5% of nominal", "test_method": "ASTM D 3776"},
            {"property": "Thickness", "value": "0.25-0.75 mm", "test_method": "ASTM D 1777"}
        ],
        "dimensions": [
            "Standard fabric width is 150 cm ±2 cm.",
            "Fabric shall be supplied in continuous rolls of specified length.",
            "Selvage width shall not exceed 15 mm on each side.",
            "Bow and skew shall not exceed 2% of fabric width."
        ],
        "workmanship": "Fabric shall be free from holes, tears, broken yarns, oil spots, and other defects that would impair ballistic performance. Weave shall be uniform and tight.",
        "sampling": "Sample testing shall be conducted per MIL-STD-105 with AQL of 1.5. Each production lot shall undergo verification testing.",
        "test_methods": [
            {"property": "Tensile Testing", "description": "Cut specimens in warp and fill directions and test per ASTM D 5034 grab test method."},
            {"property": "Ballistic Testing", "description": "Construct test panels per NIJ 0101.06 and conduct ballistic testing at accredited facility."},
            {"property": "Fabric Analysis", "description": "Determine thread count, crimp, and fabric construction parameters using microscopy and mechanical analysis."}
        ],
        "product_marking": "Fabric rolls shall be labeled with style number, lot number, width, length, mass per unit area, and production date.",
        "packaging": "Fabric shall be rolled on cores and wrapped in protective polyethylene. Rolls shall be stored in cool, dry conditions away from UV exposure.",
        "keywords": ["aramid", "ballistic", "body armor", "Kevlar", "protective fabric", "bulletproof", "high strength"]
    },
    
    {
        "designation": "F 4123-24",
        "title": "Standard Specification for Shape Memory Alloy Actuator Wire",
        "issue_date": "June 1, 2024",
        "product_name": "shape memory alloy wire",
        "scope": "nickel-titanium (NiTi) shape memory alloy wire for actuator and medical device applications",
        "intended_use": "robotic actuators, aerospace mechanisms, biomedical devices, and smart structures requiring thermally-activated shape change",
        "referenced_standards": [
            "F 2063 Standard Specification for Wrought Nickel-Titanium Shape Memory Alloys for Medical Devices",
            "F 2516 Test Method for Tension Testing of Nickel-Titanium Superelastic Materials",
            "E 1876 Test Method for Dynamic Young's Modulus, Shear Modulus, and Poisson's Ratio by Impulse Excitation",
            "E 1269 Test Method for Determining Specific Heat Capacity by Differential Scanning Calorimetry"
        ],
        "terminology": {
            "shape memory effect": "the ability of certain alloys to recover a predetermined shape upon heating",
            "transformation temperature": "the temperature at which the alloy transforms between austenite and martensite phases",
            "recovery stress": "the stress generated during constrained shape recovery"
        },
        "classification_basis": "transformation temperature range and wire diameter",
        "classifications": [
            {"name": "Type LT", "description": "Low temperature, Af = 40-60°C, diameter 0.1-2.0 mm"},
            {"name": "Type MT", "description": "Medium temperature, Af = 70-90°C, diameter 0.1-2.5 mm"},
            {"name": "Type HT", "description": "High temperature, Af = 100-120°C, diameter 0.1-3.0 mm"}
        ],
        "ordering_info": [
            "ASTM designation and year of issue",
            "Type (LT, MT, or HT)",
            "Wire diameter (mm)",
            "Transformation temperatures (As, Af, Ms, Mf if critical)",
            "Length (meters)",
            "Quantity",
            "Heat treatment condition (trained or as-drawn)"
        ],
        "materials": [
            "Wire shall be produced from high-purity nickel-titanium alloy by vacuum induction melting and hot working.",
            "Final wire diameter shall be achieved through cold drawing with intermediate annealing.",
            "Shape memory training shall be performed if specified, using appropriate thermal-mechanical cycling."
        ],
        "chemical_composition": {
            "Nickel (Ni)": "55.0-56.5 wt%",
            "Titanium (Ti)": "Balance",
            "Carbon (C), max": "0.05%",
            "Oxygen (O), max": "0.05%",
            "Nitrogen (N), max": "0.005%",
            "Hydrogen (H), max": "0.005%"
        },
        "requirements": [
            {"property": "Transformation temp Af", "value": "Within ±5°C of target", "test_method": "DSC per E 1269"},
            {"property": "Recovery strain", "value": "≥ 6%", "test_method": "Bend and free recovery"},
            {"property": "Recovery stress", "value": "≥ 400 MPa", "test_method": "Constrained recovery"},
            {"property": "Fatigue life", "value": "≥ 10,000 cycles at 4% strain", "test_method": "Cyclic testing"}
        ],
        "dimensions": [
            "Wire diameter tolerance shall be ±0.010 mm for diameters < 0.5 mm.",
            "For diameters ≥ 0.5 mm, tolerance shall be ±2% of nominal diameter.",
            "Surface finish shall be bright and smooth without deep scratches or pits.",
            "Straightness shall be ≤ 5 mm deviation per meter length."
        ],
        "workmanship": "Wire shall be free from cracks, laps, inclusions, and surface defects that could serve as crack initiation sites during cyclic loading.",
        "sampling": "Transformation temperatures shall be measured for each production batch. Mechanical properties verified on representative samples.",
        "test_methods": [
            {"property": "Transformation Temperature", "description": "Determine As, Af, Ms, Mf by differential scanning calorimetry (DSC) per ASTM E 1269."},
            {"property": "Shape Memory Testing", "description": "Deform wire in martensite condition, then heat above Af and measure recovery strain and stress."},
            {"property": "Fatigue Testing", "description": "Cycle wire through transformation by thermal or mechanical means and monitor degradation of properties."}
        ],
        "product_marking": "Wire spools shall be labeled with alloy composition, wire diameter, transformation temperatures, lot number, and production date.",
        "packaging": "Wire shall be wound on plastic spools and packaged in sealed bags with desiccant. Storage at room temperature in dry conditions.",
        "keywords": ["shape memory alloy", "NiTi", "nitinol", "actuator", "smart material", "superelastic", "transformation"]
    }
]

