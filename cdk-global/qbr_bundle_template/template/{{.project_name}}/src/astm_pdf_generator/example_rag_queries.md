# Example RAG Chatbot Queries

This document demonstrates the types of questions that could be answered using the generated ASTM specification PDFs in a RAG (Retrieval-Augmented Generation) chatbot system.

## Material Properties Queries

### Query 1: Titanium Alloy Strength
**Question:** "What are the mechanical properties required for Grade 5 titanium alloy bars?"

**Expected Response:** The chatbot would retrieve information from B 1567-24 and respond with:
- Tensile strength: ≥ 895 MPa
- Yield strength: ≥ 828 MPa
- Elongation: ≥ 10%
- Hardness: 280-340 HV

### Query 2: Battery Performance
**Question:** "What is the minimum cycle life for lithium-ion battery cells used in electric vehicles?"

**Expected Response:** From E 2567-24: The cells must maintain 80% capacity retention for at least 1000 cycles.

### Query 3: Composite Panel Temperature
**Question:** "What is the maximum service temperature for Type II aerospace composite panels?"

**Expected Response:** From F 2345-24: Type II panels with quasi-isotropic layup can operate at service temperatures up to 150°C.

## Chemical Composition Queries

### Query 4: Steel Composition
**Question:** "What is the carbon content requirement for HSLA structural steel plate Grade 50?"

**Expected Response:** From A 3456-24: Maximum carbon content is 0.18%, with manganese at 0.80-1.50%.

### Query 5: Ceramic Composition
**Question:** "What are the main constituents of silicon nitride bearing balls?"

**Expected Response:** From C 1678-24: Silicon nitride (Si₃N₄) ≥ 90%, with yttrium oxide (Y₂O₃) and aluminum oxide (Al₂O₃) each at 2-8%.

## Test Method Queries

### Query 6: Tensile Testing
**Question:** "How should I test the tensile strength of aramid ballistic fabric?"

**Expected Response:** From D 5678-24: Cut specimens in both warp and fill directions and test per ASTM D 5034 grab test method. Required strength is ≥ 2200 N/cm in both directions.

### Query 7: Battery Capacity Testing
**Question:** "What is the procedure for testing lithium-ion cell capacity?"

**Expected Response:** From E 2567-24: Fully charge cells to 4.2V, then discharge at 0.5C rate to 2.5V while measuring capacity. The measured capacity must meet or exceed the rated capacity.

## Application-Specific Queries

### Query 8: Medical Device Materials
**Question:** "What materials are suitable for bioabsorbable surgical mesh?"

**Expected Response:** From F 3890-24: Medical grade polymers including:
- Type I: Poly(glycolic acid) - absorbs in 3-4 months
- Type II: Poly(lactic acid) - absorbs in 12-18 months
- Type III: Poly(glycolic-co-lactic acid) copolymer - absorbs in 6-9 months

### Query 9: High-Temperature Applications
**Question:** "What ceramic materials can withstand temperatures above 1200°C in turbine engines?"

**Expected Response:** From C 2789-24: Silicon carbide fiber reinforced ceramic matrix composites (SiC/SiC):
- Class 1: Up to 1200°C
- Class 2: Up to 1400°C
- Class 3: Up to 1500°C

### Query 10: Wear-Resistant Materials
**Question:** "What polymer material offers low friction and high wear resistance for conveyor systems?"

**Expected Response:** From D 4892-24: Ultra-high molecular weight polyethylene (UHMWPE) sheets offer coefficient of friction ≤ 0.20 and elongation at break ≥ 300%, making them ideal for conveyor applications.

## Ordering and Specification Queries

### Query 11: Ordering Information
**Question:** "What information do I need to provide when ordering shape memory alloy wire?"

**Expected Response:** From F 4123-24:
- ASTM designation and year of issue
- Type (LT, MT, or HT)
- Wire diameter (mm)
- Transformation temperatures
- Length (meters)
- Quantity
- Heat treatment condition (trained or as-drawn)

### Query 12: Tolerance Requirements
**Question:** "What are the diameter tolerances for precision silicon nitride bearing balls?"

**Expected Response:** From C 1678-24: Per ISO 3290:
- Grade 3: Sphericity deviation ≤ 0.13 μm, Surface roughness Ra ≤ 0.010 μm
- Grade 5: Sphericity deviation ≤ 0.25 μm, Surface roughness Ra ≤ 0.020 μm
- Grade 10: Sphericity deviation ≤ 0.50 μm, Surface roughness Ra ≤ 0.032 μm

## Compliance and Safety Queries

### Query 13: Safety Requirements
**Question:** "Are there safety warnings for aerospace composite panel manufacturing?"

**Expected Response:** From F 2345-24: "This standard does not purport to address all of the safety concerns, if any, associated with its use. It is the responsibility of the user to establish appropriate safety, health, and environmental practices and determine the applicability of regulatory limitations prior to use."

### Query 14: Certification Requirements
**Question:** "What certification is required when purchasing titanium alloy bars?"

**Expected Response:** From B 1567-24: "A manufacturer's or supplier's certification shall be furnished to the purchaser that the material was manufactured, sampled, tested, and inspected in accordance with this specification and has met the requirements."

## Cross-Document Queries

### Query 15: Material Comparison
**Question:** "Compare the tensile strength of titanium Grade 5 bars versus aerospace composite panels."

**Expected Response:** The chatbot would retrieve from multiple documents:
- Titanium Grade 5 (B 1567-24): ≥ 895 MPa
- Aerospace Composite Panels (F 2345-24): ≥ 600 MPa
The titanium has higher tensile strength, but composites offer better strength-to-weight ratio.

### Query 16: High-Temperature Materials
**Question:** "What materials in the database can operate above 1000°C?"

**Expected Response:** The chatbot would search across all documents and identify:
- Ceramic Matrix Composites (C 2789-24): Up to 1500°C
- Silicon Nitride Ceramics (C 1678-24): High-temperature capability (used in engines)

## Implementation Notes

To implement these queries in a RAG system:

1. **Text Extraction**: Use PyPDF2, pdfplumber, or pymupdf to extract text from PDFs
2. **Chunking**: Break documents into logical chunks (by section or paragraph)
3. **Embeddings**: Generate vector embeddings using:
   - OpenAI: `text-embedding-ada-002`
   - Open Source: `all-MiniLM-L6-v2` (Sentence Transformers)
4. **Vector Database**: Store embeddings in Pinecone, Weaviate, Chroma, or FAISS
5. **Retrieval**: Use semantic search to find relevant chunks
6. **Generation**: Use LLM (GPT-4, Claude, etc.) to generate answers from retrieved context

## Query Performance Tips

- **Specific queries** perform better than vague ones
- Include **relevant keywords** from the domain
- Ask about **specific properties, values, or procedures**
- For comparisons, be explicit about what you're comparing
- Reference **specific standards or materials** when possible

## Advanced Query Types

### Calculation Queries
"If I have a 500mm x 1000mm composite panel, what is the minimum load it can withstand?"
*(Requires extracting dimensions and strength values, then calculating)*

### Compliance Queries
"Does the titanium alloy meet aerospace material requirements?"
*(Requires checking against referenced standards)*

### Recommendation Queries
"What material should I use for a high-temperature, low-weight aerospace application?"
*(Requires comparing multiple materials based on properties)*

---

*These example queries demonstrate the rich technical knowledge encoded in the ASTM specification PDFs and how a RAG chatbot can make this information readily accessible.*

