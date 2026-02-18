# ASTM Standard Specification PDF Generator

This project generates ASTM-compliant specification documents for various technical products. The generated PDFs follow the ASTM Form and Style Manual standards and are suitable for ingestion into RAG (Retrieval-Augmented Generation) chatbots.

## Overview

The system generates 10 different specification documents for fictional products across various industries:

1. **F 2345-24**: High-Performance Aerospace Composite Panel
2. **B 1567-24**: Titanium Grade 5 Alloy Bar
3. **D 4892-24**: Ultra-High Molecular Weight Polyethylene (UHMWPE) Sheet
4. **C 2789-24**: Advanced Ceramic Matrix Composite (CMC) Turbine Components
5. **A 3456-24**: High-Strength Low-Alloy Structural Steel Plate
6. **F 3890-24**: Bioabsorbable Polymer Surgical Mesh
7. **E 2567-24**: Lithium-Ion Battery Cells for Electric Vehicle Applications
8. **C 1678-24**: Advanced Silicon Nitride Ceramic Bearing Balls
9. **D 5678-24**: Aramid Fiber Ballistic Protection Fabric
10. **F 4123-24**: Shape Memory Alloy Actuator Wire

## Features

- **ASTM-Compliant Format**: All documents follow the ASTM Form and Style Manual structure
- **Comprehensive Sections**: Each specification includes all required sections:
  - Scope
  - Referenced Documents
  - Terminology
  - Classification
  - Ordering Information
  - Materials and Manufacture
  - Chemical Composition (where applicable)
  - Mechanical and Physical Requirements
  - Dimensions and Permissible Variations
  - Workmanship, Finish, and Appearance
  - Sampling
  - Test Methods
  - Inspection
  - Rejection and Rehearing
  - Certification
  - Product Marking
  - Packaging and Package Marking
  - Keywords

- **Professional Formatting**: Clean, readable layout with proper heading hierarchy, tables, and styling
- **RAG-Ready**: Structured content ideal for ingestion into RAG chatbot systems

## Installation

1. Ensure you have Python 3.7 or higher installed:
```bash
python3 --version
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Generate PDFs

Generate all 10 specification PDFs:

```bash
source venv/bin/activate
python3 generate_all_pdfs.py
```

The PDFs will be created in the `output_pdfs` directory.

### Prepare for RAG Ingestion

Create an index file for RAG chatbot integration:

```bash
source venv/bin/activate
python3 extract_text_for_rag.py
```

This will create a `rag_index.json` file with metadata for all generated PDFs, which can be used as a starting point for building a RAG system.

## Project Structure

```
.
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── generate_astm_pdfs.py         # Core PDF generation class
├── product_specifications.py      # Product data definitions
├── generate_all_pdfs.py          # Main script to generate all PDFs
├── extract_text_for_rag.py       # RAG indexing utility
├── rag_index.json                # Generated index file (created by extract_text_for_rag.py)
├── venv/                         # Python virtual environment
└── output_pdfs/                  # Generated PDF files (created on first run)
    ├── F_2345-24.pdf
    ├── B_1567-24.pdf
    ├── D_4892-24.pdf
    ├── C_2789-24.pdf
    ├── A_3456-24.pdf
    ├── F_3890-24.pdf
    ├── E_2567-24.pdf
    ├── C_1678-24.pdf
    ├── D_5678-24.pdf
    └── F_4123-24.pdf
```

## Customization

### Adding New Products

To add new product specifications:

1. Open `product_specifications.py`
2. Add a new dictionary to the `PRODUCTS` list following the existing structure
3. Run `generate_all_pdfs.py` to generate the new PDF

### Modifying Existing Products

Edit the product data in `product_specifications.py` and regenerate the PDFs.

### Changing Output Format

Modify the styling and layout in the `ASTMSpecGenerator` class in `generate_astm_pdfs.py`.

## ASTM Compliance

These documents follow the structure outlined in the ASTM Form and Style Manual. Key compliance features:

- Proper section numbering and hierarchy
- Standard terminology and definitions format
- Requirements presented in tables where appropriate
- Referenced standards properly cited
- Keywords section for indexing

## Use Cases

### RAG Chatbot Integration

These PDFs are designed to be ingested into RAG systems for:
- Technical specification lookup
- Product information retrieval
- Standards compliance checking
- Material property queries
- Testing method references

### Training Data

The structured format makes these documents ideal for training technical documentation systems.

### Template Development

Use these as templates for generating real ASTM-style specifications.

## Dependencies

- **reportlab** (4.0.7): PDF generation library with support for complex layouts, tables, and styling

## License

This project is for educational and demonstration purposes. The generated specifications are fictional and should not be used as actual standards.

## Notes

- All product data is fictional and created for demonstration purposes
- Real ASTM standards should be purchased from ASTM International
- The documents are formatted to be readable and suitable for RAG ingestion
- Chemical compositions, mechanical properties, and test methods are representative examples

## Troubleshooting

**Issue**: `ModuleNotFoundError: No module named 'reportlab'`
**Solution**: Install dependencies with `pip install -r requirements.txt`

**Issue**: Permission denied when creating output directory
**Solution**: Ensure you have write permissions in the project directory

**Issue**: PDFs not generating
**Solution**: Check the console output for specific error messages and verify all product data is properly formatted in `product_specifications.py`

## Future Enhancements

Potential improvements:
- Add support for test method standards (Part A of ASTM manual)
- Include practice and guide document types
- Add figure and diagram support
- Generate table of contents
- Add cross-referencing between sections
- Support for appendices and annexes
- Multi-language support

## Contact

For questions or issues, please refer to the project repository or documentation.

