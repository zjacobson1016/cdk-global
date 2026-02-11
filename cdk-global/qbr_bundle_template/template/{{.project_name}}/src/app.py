#!/usr/bin/env python3
"""
Run script for the Manufacturing Field Technician Dashboard

This script launches the Dash application for field technicians to manage
service tickets and access technical support through an integrated chatbot.

Usage:
    python run_dashboard.py

The dashboard will be available at: http://localhost:8050
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from field_technician_dashboard import app
    
    print("🔧 Starting Manufacturing Field Technician Dashboard...")
    print("📍 Dashboard will be available at: http://localhost:8050")
    print("💡 Features available:")
    print("   • Service ticket alerts and management")
    print("   • Ticket status updates and notes")
    print("   • Technical assistant chatbot")
    print("   • Equipment troubleshooting support")
    print("\n🚀 Launching dashboard...")
    
    app.run_server()
    
except ImportError as e:
    print(f"❌ Error importing dashboard: {e}")
    print("💡 Make sure you have installed the required dependencies:")
    print("   pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error starting dashboard: {e}")
    sys.exit(1)
