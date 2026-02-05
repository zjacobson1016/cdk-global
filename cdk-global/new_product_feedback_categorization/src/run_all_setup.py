#!/usr/bin/env python3
"""
Run All Setup Scripts
Execute all setup scripts in sequence for the QBR Demo project.

Usage:
    databricks bundle run run_all_setup -t dev
"""

import subprocess
import sys
import os
from pathlib import Path

# Get the directory containing this script
SCRIPT_DIR = Path(__file__).parent

def run_script(script_name: str, script_path: str) -> bool:
    """
    Run a Python script and return success status.
    
    Args:
        script_name: Human-readable name of the script
        script_path: Path to the script to run
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"🚀 Running: {script_name}")
    print(f"{'='*60}\n")
    
    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=SCRIPT_DIR,
            check=True,
            capture_output=False,
            text=True
        )
        
        print(f"\n✅ {script_name} completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {script_name} failed with exit code {e.returncode}")
        print(f"Error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ {script_name} failed with error: {e}")
        return False

def main():
    """Run all setup scripts in sequence."""
    
    print("""
╔════════════════════════════════════════════════════════════╗
║         QBR Demo - Running All Setup Scripts               ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # Define scripts to run in order
    scripts = [
        {
            "name": "Create Database Tables",
            "path": SCRIPT_DIR / "database_operations.py",
            "description": "Create Lakebase tables for quote management"
        },
        {
            "name": "Unity Catalog Functions",
            "path": SCRIPT_DIR / "uc_functions.py",
            "description": "Create UC SQL functions for predictions and parsing"
        },
        {
            "name": "Quote Volume Writer", 
            "path": SCRIPT_DIR / "quote_volume_writer.py",
            "description": "Generate sample quote data and write to UC Volume",
            "args": ["--batches", "5", "--records-per-batch", "20"]
        },
        {
            "name": "Create Genie Space",
            "path": SCRIPT_DIR / "create_genie_space.py",
            "description": "Set up Genie space for natural language queries"
        },
        {
            "name": "Agent Bricks Helper",
            "path": SCRIPT_DIR / "agent_bricks_helper.py",
            "description": "Configure AI agent and RAG components"
        },
        {
            "name": "Generate ASTM PDFs",
            "path": SCRIPT_DIR / "astm_pdf_generator/generate_all_pdfs.py",
            "description": "Generate ASTM specification PDFs"
        }
    ]
    
    # Track results
    results = []
    
    # Run each script
    for i, script in enumerate(scripts, 1):
        print(f"\n📋 Step {i}/{len(scripts)}: {script['name']}")
        print(f"   {script['description']}")
        
        # Check if script exists
        if not script['path'].exists():
            print(f"⚠️  Script not found: {script['path']}")
            print(f"   Skipping...")
            results.append((script['name'], 'skipped'))
            continue
        
        # Run the script
        success = run_script(script['name'], str(script['path']))
        results.append((script['name'], 'success' if success else 'failed'))
        
        # Stop on failure (optional - comment out to continue on errors)
        # if not success:
        #     print(f"\n❌ Stopping due to failure in: {script['name']}")
        #     break
    
    # Print summary
    print(f"\n\n{'='*60}")
    print("📊 EXECUTION SUMMARY")
    print(f"{'='*60}\n")
    
    for script_name, status in results:
        status_icon = "✅" if status == "success" else "❌" if status == "failed" else "⚠️"
        print(f"{status_icon} {script_name}: {status.upper()}")
    
    # Final status
    all_success = all(status == "success" for _, status in results)
    skipped_count = sum(1 for _, status in results if status == "skipped")
    failed_count = sum(1 for _, status in results if status == "failed")
    
    print(f"\n{'='*60}")
    if all_success:
        print("🎉 All scripts completed successfully!")
        return 0
    elif failed_count == 0 and skipped_count > 0:
        print(f"⚠️  Completed with {skipped_count} script(s) skipped")
        return 0
    else:
        print(f"❌ Completed with {failed_count} failure(s)")
        return 1

if __name__ == "__main__":
    sys.exit(main())

