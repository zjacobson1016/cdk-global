#!/usr/bin/env python3
"""
Main script to generate all ASTM specification PDFs and save to Unity Catalog Volume
"""

import os
from generate_astm_pdfs import ASTMSpecGenerator
from product_specifications import PRODUCTS
from databricks.connect import DatabricksSession
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
# Unity Catalog configuration from environment variables
CATALOG = os.getenv("CATALOG_NAME")
SCHEMA = os.getenv("SCHEMA_NAME")
VOLUME = "qbr_databricks_platform_demo"


def ensure_volume(spark: DatabricksSession, catalog: str, schema: str, volume: str) -> str:
    """Create the volume if it doesn't exist and return the base path."""
    print(f"📦 Ensuring volume exists: {catalog}.{schema}.{volume}")
    spark.sql(
        f"CREATE VOLUME IF NOT EXISTS `{catalog}`.`{schema}`.`{volume}` "
        "COMMENT 'ASTM specification PDFs for RAG and product documentation.'"
    )
    base_path = f"/Volumes/{catalog}/{schema}/{volume}"
    print(f"✅ Volume path: {base_path}\n")
    return base_path


def main():
    """Generate all product specification PDFs and save to Unity Catalog Volume"""
    print("=" * 70)
    print("ASTM Specification PDF Generator")
    print("Saving to Unity Catalog Volume")
    print("=" * 70)
    print(f"\nGenerating {len(PRODUCTS)} specification documents...\n")
    
    # Initialize Databricks session
    print("🔌 Connecting to Databricks...")
    spark = DatabricksSession.builder.serverless().profile("dogfood1").getOrCreate()
    print("✅ Connected to Databricks\n")
    
    # Initialize WorkspaceClient for file uploads
    w = WorkspaceClient(profile="dogfood1")
    
    # Ensure volume exists and get path
    volume_path = ensure_volume(spark, CATALOG, SCHEMA, VOLUME)
    
    # Initialize generator with UC Volume path and WorkspaceClient
    print(f"📝 Initializing PDF generator...\n")
    generator = ASTMSpecGenerator(output_dir=volume_path, workspace_client=w)
    
    # Generate PDFs for each product
    success_count = 0
    error_count = 0
    
    for i, product in enumerate(PRODUCTS, 1):
        print(f"[{i}/{len(PRODUCTS)}] Generating {product['designation']}: {product['title'][:50]}...")
        
        # Create filename from designation
        filename = f"{product['designation'].replace(' ', '_')}.pdf"
        
        try:
            generator.generate_specification(product, filename)
            success_count += 1
            print(f"     ✓ Successfully generated {filename}")
            print(f"     📍 Saved to: {volume_path}/{filename}\n")
        except Exception as e:
            error_count += 1
            print(f"     ✗ Error generating {filename}: {str(e)}\n")
    
    # Summary
    print("=" * 70)
    print(f"Generation complete!")
    print(f"✅ Success: {success_count}/{len(PRODUCTS)}")
    if error_count > 0:
        print(f"❌ Errors: {error_count}/{len(PRODUCTS)}")
    print(f"\n📍 PDFs saved to Unity Catalog Volume:")
    print(f"   {CATALOG}.{SCHEMA}.{VOLUME}")
    print(f"   Path: {volume_path}")
    print("=" * 70)
    
    # List generated files
    print(f"\n📋 Verifying files in volume...")
    try:
        files_df = spark.sql(f"LIST '{volume_path}/'")
        file_count = files_df.count()
        print(f"✅ Found {file_count} files in volume")
        
        # Show first few files
        print("\n📄 Sample files:")
        for row in files_df.limit(5).collect():
            print(f"   - {row['name']}")
        
        if file_count > 5:
            print(f"   ... and {file_count - 5} more files")
            
    except Exception as e:
        print(f"⚠️  Could not list files: {e}")


if __name__ == "__main__":
    main()

