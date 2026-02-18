#!/usr/bin/env python3
"""
Utility script to extract text from generated PDFs for RAG ingestion
This demonstrates how the PDFs can be processed for a chatbot
"""

import os
import json
from pathlib import Path


def extract_pdf_metadata(pdf_filename):
    """
    Extract metadata from PDF filename and return structured information
    In a real implementation, you would use PyPDF2 or pdfplumber to extract actual text
    """
    # Remove .pdf extension
    designation = pdf_filename.replace('.pdf', '').replace('_', ' ')
    
    # Map to product info (this would come from actual PDF content in production)
    product_map = {
        'F 2345-24': {
            'category': 'Aerospace Materials',
            'product': 'High-Performance Aerospace Composite Panel',
            'keywords': ['aerospace', 'carbon fiber', 'composite', 'structural']
        },
        'B 1567-24': {
            'category': 'Metallic Materials',
            'product': 'Titanium Grade 5 Alloy Bar',
            'keywords': ['titanium', 'alloy', 'aerospace', 'biocompatible']
        },
        'D 4892-24': {
            'category': 'Polymeric Materials',
            'product': 'UHMWPE Sheet',
            'keywords': ['polymer', 'wear resistant', 'low friction']
        },
        'C 2789-24': {
            'category': 'Ceramic Materials',
            'product': 'Ceramic Matrix Composite Turbine Components',
            'keywords': ['ceramic', 'high temperature', 'turbine']
        },
        'A 3456-24': {
            'category': 'Steel and Steel Products',
            'product': 'HSLA Structural Steel Plate',
            'keywords': ['steel', 'structural', 'construction']
        },
        'F 3890-24': {
            'category': 'Medical Devices',
            'product': 'Bioabsorbable Polymer Surgical Mesh',
            'keywords': ['bioabsorbable', 'surgical', 'medical device']
        },
        'E 2567-24': {
            'category': 'Energy Storage',
            'product': 'Lithium-Ion Battery Cells',
            'keywords': ['battery', 'lithium-ion', 'electric vehicle']
        },
        'C 1678-24': {
            'category': 'Ceramic Materials',
            'product': 'Silicon Nitride Ceramic Bearing Balls',
            'keywords': ['ceramic', 'bearing', 'precision']
        },
        'D 5678-24': {
            'category': 'Protective Materials',
            'product': 'Aramid Fiber Ballistic Protection Fabric',
            'keywords': ['aramid', 'ballistic', 'body armor']
        },
        'F 4123-24': {
            'category': 'Smart Materials',
            'product': 'Shape Memory Alloy Actuator Wire',
            'keywords': ['shape memory', 'actuator', 'smart material']
        }
    }
    
    return product_map.get(designation, {
        'category': 'Unknown',
        'product': designation,
        'keywords': []
    })


def create_rag_index():
    """
    Create a simple index file for RAG chatbot ingestion
    In production, this would feed into a vector database like Pinecone, Weaviate, or Chroma
    """
    output_dir = Path('output_pdfs')
    
    if not output_dir.exists():
        print("Error: output_pdfs directory not found. Run generate_all_pdfs.py first.")
        return
    
    pdf_files = list(output_dir.glob('*.pdf'))
    
    if not pdf_files:
        print("Error: No PDF files found in output_pdfs directory.")
        return
    
    print("=" * 70)
    print("RAG Indexing Utility")
    print("=" * 70)
    print(f"\nFound {len(pdf_files)} PDF files\n")
    
    index_data = []
    
    for pdf_file in sorted(pdf_files):
        metadata = extract_pdf_metadata(pdf_file.name)
        
        doc_info = {
            'file_path': str(pdf_file),
            'designation': pdf_file.stem.replace('_', ' '),
            'category': metadata['category'],
            'product_name': metadata['product'],
            'keywords': metadata['keywords'],
            'file_size_kb': pdf_file.stat().st_size / 1024
        }
        
        index_data.append(doc_info)
        
        print(f"✓ Indexed: {doc_info['designation']}")
        print(f"  Category: {doc_info['category']}")
        print(f"  Product: {doc_info['product_name']}")
        print(f"  Size: {doc_info['file_size_kb']:.1f} KB")
        print()
    
    # Save index to JSON file
    index_file = Path('rag_index.json')
    with open(index_file, 'w') as f:
        json.dump(index_data, f, indent=2)
    
    print("=" * 70)
    print(f"Index saved to: {index_file}")
    print(f"Total documents indexed: {len(index_data)}")
    print("=" * 70)
    
    # Print summary by category
    print("\nDocuments by Category:")
    categories = {}
    for doc in index_data:
        cat = doc['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    for category, count in sorted(categories.items()):
        print(f"  {category}: {count}")
    
    print("\n" + "=" * 70)
    print("Next Steps for RAG Integration:")
    print("=" * 70)
    print("1. Install a PDF text extraction library:")
    print("   pip install PyPDF2  # or pdfplumber, pymupdf")
    print()
    print("2. Extract full text from PDFs")
    print()
    print("3. Chunk the text into semantic segments")
    print()
    print("4. Generate embeddings using:")
    print("   - OpenAI embeddings (text-embedding-ada-002)")
    print("   - Sentence Transformers (all-MiniLM-L6-v2)")
    print("   - Cohere embeddings")
    print()
    print("5. Store in a vector database:")
    print("   - Pinecone")
    print("   - Weaviate")
    print("   - Chroma")
    print("   - FAISS")
    print()
    print("6. Build RAG query interface with LangChain or LlamaIndex")
    print("=" * 70)


if __name__ == "__main__":
    create_rag_index()

