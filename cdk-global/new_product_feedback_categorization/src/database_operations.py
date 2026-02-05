"""
Database operations for the Automated Quote Management Dashboard

This module handles all database interactions with the Lakebase instance,
including automated quote management, email parsing records, and approval workflow tracking.
"""
import os
from dotenv import load_dotenv
load_dotenv()
env_path = "/Workspace/Users/zach.jacobson@databricks.com/.bundle/zach-demo-qbr/dev/files/.env"
load_dotenv(dotenv_path=env_path, override=True)
import psycopg
import json
import uuid
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Any
from databricks.sdk import WorkspaceClient
import os
import getpass


class QuoteDatabase:
    """Database operations for automated quotes and approval workflow"""
    
    def __init__(self, user: Optional[str] = None):
        """Initialize database connection
        
        Args:
            user: Database user email/identifier. If None, will try to detect from environment
        """
        #self.w = WorkspaceClient()
        self.w = WorkspaceClient(client_id=os.getenv("DATABRICKS_CLIENT_ID"), client_secret=os.getenv("DATABRICKS_CLIENT_SECRET"), host==os.getenv("DATABRICKS_HOST"))
        self.instance_name = os.getenv("LAKEBASE_INSTANCE_NAME", "qbr-demo-instance")
        self.database_name = os.getenv("LAKEBASE_DATABASE_NAME", "databricks_postgres")
        self.user = user



        
    def get_connection(self):
        """Get database connection"""
        try:
            instance = self.w.database.get_database_instance(name=self.instance_name)
            
            cred = self.w.database.generate_database_credential(
                request_id=str(uuid.uuid4()), 
                instance_names=[self.instance_name]
            )
            
            conn = psycopg.connect(
                host=instance.read_write_dns,
                dbname=self.database_name,
                user=self.user,
                password=cred.token,
                sslmode="require"
            )
            return conn
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            print(f"❌ Connection details: instance={self.instance_name}, database={self.database_name}, user={self.user}")
            raise
    
    def create_tables(self):
        """Create the automated quotes and related tables if they don't exist"""
        
        # Main quotes table
        create_quotes_table = """
        CREATE TABLE IF NOT EXISTS automated_quotes (
            id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL,
            customer_name VARCHAR(255) NOT NULL,
            location VARCHAR(255) NOT NULL,
            product_id VARCHAR(100) NOT NULL,
            product_description TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price DECIMAL(10,2) NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            lead_time INTEGER NOT NULL DEFAULT 30,
            order_date DATE NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Denied', 'Delivered')),
            priority VARCHAR(20) NOT NULL DEFAULT 'Medium' CHECK (priority IN ('High', 'Medium', 'Low')),
            email_source TEXT,
            email_subject VARCHAR(500),
            email_body TEXT,
            email_received_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            assigned_reviewer VARCHAR(100),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Notes/comments table for approval workflow
        create_notes_table = """
        CREATE TABLE IF NOT EXISTS quote_notes (
            id SERIAL PRIMARY KEY,
            quote_id VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            note_type VARCHAR(20) NOT NULL DEFAULT 'Comment' CHECK (note_type IN ('Comment', 'Approval', 'Denial', 'Revision')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewer VARCHAR(100) NOT NULL,
            FOREIGN KEY (quote_id) REFERENCES automated_quotes(id) ON DELETE CASCADE
        );
        """
        
        # Customer reference table (optional)
        create_customers_table = """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id VARCHAR(100) PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            contact_person VARCHAR(255),
            email VARCHAR(255),
            phone VARCHAR(50),
            address TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Product catalog table (optional)
        create_products_table = """
        CREATE TABLE IF NOT EXISTS products (
            product_id VARCHAR(100) PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            unit_price DECIMAL(10,2),
            availability_status VARCHAR(50) DEFAULT 'Available',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Create indexes for better performance
        create_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_quotes_status ON automated_quotes(status);",
            "CREATE INDEX IF NOT EXISTS idx_quotes_priority ON automated_quotes(priority);",
            "CREATE INDEX IF NOT EXISTS idx_quotes_customer ON automated_quotes(customer_id);",
            "CREATE INDEX IF NOT EXISTS idx_quotes_product ON automated_quotes(product_id);",
            "CREATE INDEX IF NOT EXISTS idx_quotes_date ON automated_quotes(order_date);",
            "CREATE INDEX IF NOT EXISTS idx_quotes_assigned ON automated_quotes(assigned_reviewer);",
            "CREATE INDEX IF NOT EXISTS idx_notes_quote ON quote_notes(quote_id);",
            "CREATE INDEX IF NOT EXISTS idx_notes_type ON quote_notes(note_type);"
        ]
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Create tables
                    cur.execute(create_quotes_table)
                    cur.execute(create_notes_table)
                    cur.execute(create_customers_table)
                    cur.execute(create_products_table)
                    
                    # Create indexes
                    for index_sql in create_indexes:
                        cur.execute(index_sql)
                    
                    conn.commit()
                    print("✅ Quote management database tables created successfully")
                    
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            raise
    
    def insert_sample_data(self):
        """Insert sample automated quote data"""
        
        # Sample customers
        sample_customers = [
            {
                "customer_id": "CUST-001",
                "company_name": "Manufacturing Plant A",
                "contact_person": "John Doe",
                "email": "john.doe@manufacturingplanta.com",
                "phone": "555-0101",
                "address": "123 Industrial Blvd, Detroit, MI"
            },
            {
                "customer_id": "CUST-002", 
                "company_name": "Chemical Processing Corp",
                "contact_person": "Jane Smith",
                "email": "jane.smith@chemproc.com",
                "phone": "555-0202",
                "address": "456 Chemical Lane, Houston, TX"
            },
            {
                "customer_id": "CUST-003",
                "company_name": "Power Generation Facility",
                "contact_person": "Bob Wilson",
                "email": "bob.wilson@powergen.com", 
                "phone": "555-0303",
                "address": "789 Power Plant Rd, Phoenix, AZ"
            }
        ]
        
        # Sample products
        sample_products = [
            {
                "product_id": "3051S-CP",
                "product_name": "IoT Automation 3051S Coplanar Pressure Transmitter",
                "description": "Industry-leading coplanar pressure transmitter with advanced diagnostics, superior accuracy, and IoT connectivity for remote monitoring",
                "category": "IoT Sensors",
                "unit_price": 3250.00,
                "availability_status": "Available"
            },
            {
                "product_id": "3051S-IL",
                "product_name": "IoT Automation 3051S In-line Pressure Transmitter", 
                "description": "Versatile in-line pressure transmitter with 4-20mA HART output, 0-6000 PSI range, includes IoT connectivity capability",
                "category": "IoT Sensors",
                "unit_price": 2850.00,
                "availability_status": "Available"
            },
            {
                "product_id": "3051S-MV",
                "product_name": "IoT Automation 3051S MultiVariable Transmitter",
                "description": "Advanced multivariable transmitter measuring pressure, differential pressure, and temperature with IoT technology for wireless data transmission",
                "category": "IoT Sensors",
                "unit_price": 4750.00,
                "availability_status": "Available"
            }
        ]
        
        # Sample quotes
        sample_quotes = [
            {
                "id": "QT-001",
                "customer_id": "CUST-001",
                "customer_name": "Manufacturing Plant A",
                "location": "Building 3, Floor 2, Detroit, MI",
                "product_id": "3051S-CP",
                "product_description": "IoT Automation 3051S Coplanar Pressure Transmitter - Industry-leading performance with coplanar design and IoT connectivity",
                "quantity": 2,
                "unit_price": 3250.00,
                "total_price": 6500.00,
                "lead_time": 15,
                "order_date": date.today() + timedelta(days=7),
                "status": "Pending",
                "priority": "High",
                "email_source": "quote-request-3051s@manufacturingplanta.com",
                "email_subject": "Urgent: Need 2x IoT Automation 3051S Coplanar Transmitter for production line upgrade",
                "email_body": "Please quote options for IoT sensor codes and transmitters",
                "email_received_at": datetime.now() - timedelta(hours=2),
                "assigned_reviewer": "sarah.johnson@iotautomation.com"
            },
            {
                "id": "QT-002",
                "customer_id": "CUST-002",
                "customer_name": "Chemical Processing Corp",
                "location": "Reactor Room, Houston, TX",
                "product_id": "3051S-IL",
                "product_description": "IoT Automation 3051S In-line Pressure Transmitter - Versatile in-line pressure measurement solution with IoT connectivity",
                "quantity": 4,
                "unit_price": 2850.00,
                "total_price": 11400.00,
                "lead_time": 20,
                "order_date": date.today() + timedelta(days=14),
                "status": "Approved",
                "priority": "Medium",
                "email_source": "procurement@chemproc.com",
                "email_subject": "Quote request: 4x IoT Automation 3051S In-line Transmitter for new reactor",
                "email_body": "Please quote options for IoT sensor codes and transmitters",
                "email_received_at": datetime.now() - timedelta(hours=5),
                "assigned_reviewer": "sarah.johnson@iotautomation.com"
            },
            {
                "id": "QT-003",
                "customer_id": "CUST-003",
                "customer_name": "Power Generation Facility",
                "location": "Pump Station 2, Phoenix, AZ",
                "product_id": "3051S-MV",
                "product_description": "IoT Automation 3051S MultiVariable Transmitter - Advanced multivariable flow and pressure measurement with IoT technology",
                "quantity": 1,
                "unit_price": 4750.00,
                "total_price": 4750.00,
                "lead_time": 30,
                "order_date": date.today() + timedelta(days=30),
                "status": "Pending",
                "priority": "Low",
                "email_source": "maintenance@powergen.com",
                "email_subject": "MultiVariable Transmitter replacement - IoT Automation 3051S-MV specifications",
                "email_body": "Please quote options for IoT sensor codes and transmitters",
                "email_received_at": datetime.now() - timedelta(hours=8),
                "assigned_reviewer": "sarah.johnson@iotautomation.com"
            }
        ]
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if data already exists
                    cur.execute("SELECT COUNT(*) FROM databricks_postgres.silver_customers_synced")
                    quote_count = cur.fetchone()[0]
                    
                    if quote_count == 0:
                        # Insert sample customers
                        customer_sql = """
                        INSERT INTO databricks_postgres.silver_customers_synced 
                        (customer_id, company_name, contact_person, email, phone, address)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        
                        for customer in sample_customers:
                            cur.execute(customer_sql, (
                                customer["customer_id"],
                                customer["company_name"],
                                customer["contact_person"],
                                customer["email"],
                                customer["phone"],
                                customer["address"]
                            ))
                        
                        # Insert sample products
                        product_sql = """
                        INSERT INTO databricks_postgres.silver_products_synced 
                        (product_id, product_name, description, category, unit_price, availability_status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        
                        for product in sample_products:
                            cur.execute(product_sql, (
                                product["product_id"],
                                product["product_name"],
                                product["description"],
                                product["category"],
                                product["unit_price"],
                                product["availability_status"]
                            ))
                        
                        # Insert sample quotes
                        quote_sql = """
                        INSERT INTO databricks_postgres.silver_automated_quotes_synced 
                        (id, customer_id, customer_name, location, product_id, product_description, 
                         quantity, unit_price, total_price, lead_time, order_date, status, priority, 
                         email_source, email_subject, email_body, email_received_at, assigned_reviewer)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        
                        for quote in sample_quotes:
                            cur.execute(quote_sql, (
                                quote["id"],
                                quote["customer_id"],
                                quote["customer_name"],
                                quote["location"],
                                quote["product_id"],
                                quote["product_description"],
                                quote["quantity"],
                                quote["unit_price"],
                                quote["total_price"],
                                quote["lead_time"],
                                quote["order_date"],
                                quote["status"],
                                quote["priority"],
                                quote["email_source"],
                                quote["email_subject"],
                                quote["email_body"],
                                quote["email_received_at"],
                                quote["assigned_reviewer"]
                            ))
                        
                        conn.commit()
                        print(f"✅ Inserted {len(sample_quotes)} sample quotes with supporting data")
                    else:
                        print(f"ℹ️ Database already contains {quote_count} quotes")
                        
        except Exception as e:
            print(f"❌ Error inserting sample data: {e}")
            raise
    
    def get_all_quotes(self) -> List[Dict[str, Any]]:
        """Retrieve all automated quotes with their notes"""
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get all quotes (limited to 10 most recent)
                    cur.execute("""
                        SELECT id, customer_id, customer_name, location, product_id, product_description,
                               quantity, unit_price, total_price, lead_time, order_date, status, priority,
                               email_source, email_subject, email_body, email_received_at, created_at, 
                               assigned_reviewer, updated_at
                        FROM databricks_postgres.silver_automated_quotes_synced 
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    
                    quotes = []
                    for row in cur.fetchall():
                        quote = {
                            "id": row[0],
                            "customer_id": row[1],
                            "customer_name": row[2],
                            "location": row[3],
                            "product_id": row[4],
                            "product_description": row[5],
                            "quantity": row[6],
                            "unit_price": float(row[7]),
                            "total_price": float(row[8]),
                            "lead_time": row[9],
                            "order_date": row[10],
                            "status": row[11],
                            "priority": row[12],
                            "email_source": row[13],
                            "email_subject": row[14],
                            "email_body": row[15],
                            "email_received_at": row[16],
                            "created": row[17],
                            "assigned_reviewer": row[18],
                            "updated_at": row[19]
                        }
                        
                        # Get notes for this quote
                        cur.execute("""
                            SELECT content, note_type, created_at, reviewer
                            FROM databricks_postgres.silver_quote_notes_sycned
                            WHERE quote_id = %s
                            ORDER BY created_at DESC
                        """, (quote["id"],))
                        
                        notes = []
                        for note_row in cur.fetchall():
                            notes.append({
                                "content": note_row[0],
                                "note_type": note_row[1],
                                "timestamp": note_row[2].strftime("%Y-%m-%d %H:%M"),
                                "reviewer": note_row[3]
                            })
                        
                        if notes:
                            quote["notes"] = notes
                        
                        quotes.append(quote)
                    
                    return quotes
                    
        except Exception as e:
            print(f"❌ Error retrieving quotes: {e}")
            return []
    
    def update_quote(self, quote_id: str, status: Optional[str] = None, 
                    priority: Optional[str] = None, note: Optional[str] = None,
                    note_type: str = "Comment", reviewer: str = None) -> bool:
        """Update an automated quote and optionally add a note"""
        

        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Build update query dynamically
                    update_fields = []
                    values = []
                    
                    if status:
                        update_fields.append("status = %s")
                        values.append(status)
                    
                    if priority:
                        update_fields.append("priority = %s")
                        values.append(priority)
                    
                    if update_fields:
                        update_fields.append("updated_at = %s")
                        values.append(datetime.now())
                        values.append(quote_id)
                        
                        update_sql = f"""
                        UPDATE databricks_postgres.silver_automated_quotes_synced 
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                        """
                        
                        cur.execute(update_sql, values)
                        rows_affected = cur.rowcount
                        
                        if rows_affected == 0:
                            print(f"⚠️ WARNING: No rows were updated for quote_id {quote_id}")
                    
                    # Add note if provided
                    if note and note.strip():
                        # Generate a unique ID for the note
                        note_id = int(datetime.now().timestamp() * 1000000)  # microsecond timestamp
                        
                        cur.execute("""
                            INSERT INTO databricks_postgres.silver_quote_notes_sycned (id, quote_id, content, note_type, reviewer, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (note_id, quote_id, note.strip(), note_type, reviewer, datetime.now()))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            print(f"❌ Error updating quote {quote_id}: {e}")
            print(f"❌ Exception type: {type(e).__name__}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    def get_quote_by_id(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific quote by ID"""
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, customer_id, customer_name, location, product_id, product_description,
                               quantity, unit_price, total_price, lead_time, order_date, status, priority,
                               email_source, email_subject, email_body, email_received_at, created_at, 
                               assigned_reviewer, updated_at
                        FROM databricks_postgres.silver_automated_quotes_synced
                        WHERE id = %s
                    """, (quote_id,))
                    
                    row = cur.fetchone()
                    if not row:
                        return None
                    
                    quote = {
                        "id": row[0],
                        "customer_id": row[1],
                        "customer_name": row[2],
                        "location": row[3],
                        "product_id": row[4],
                        "product_description": row[5],
                        "quantity": row[6],
                        "unit_price": float(row[7]),
                        "total_price": float(row[8]),
                        "lead_time": row[9],
                        "order_date": row[10],
                        "status": row[11],
                        "priority": row[12],
                        "email_source": row[13],
                        "email_subject": row[14],
                        "email_body": row[15],
                        "email_received_at": row[16],
                        "created": row[17],
                        "assigned_reviewer": row[18],
                        "updated_at": row[19]
                    }
                    
                    # Get notes
                    cur.execute("""
                        SELECT content, note_type, created_at, reviewer
                        FROM databricks_postgres.silver_quote_notes_sycned
                        WHERE quote_id = %s
                        ORDER BY created_at DESC
                    """, (quote_id,))
                    
                    notes = []
                    for note_row in cur.fetchall():
                        notes.append({
                            "content": note_row[0],
                            "note_type": note_row[1],
                            "timestamp": note_row[2].strftime("%Y-%m-%d %H:%M"),
                            "reviewer": note_row[3]
                        })
                    
                    if notes:
                        quote["notes"] = notes
                    
                    return quote
                    
        except Exception as e:
            print(f"❌ Error retrieving quote {quote_id}: {e}")
            return None

    def approve_quote(self, quote_id: str, reviewer: str, note: Optional[str] = None) -> bool:
        """Approve a quote with optional note"""
        return self.update_quote(
            quote_id=quote_id,
            status="Approved", 
            note=note if note else f"Quote approved by {reviewer}",
            note_type="Approval",
            reviewer=reviewer
        )
    
    def deny_quote(self, quote_id: str, reviewer: str, reason: str) -> bool:
        """Deny a quote with reason"""
        return self.update_quote(
            quote_id=quote_id,
            status="Denied", 
            note=f"Quote denied: {reason}",
            note_type="Denial",
            reviewer=reviewer
        )

# Backward compatibility alias
TicketDatabase = QuoteDatabase

def check_database_tables(user: Optional[str] = None):
    """Check what tables exist in the database"""
    try:
        db = QuoteDatabase(user=user)
        print(f"🔍 Checking database tables as user: {db.user}")
        
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # Check what tables exist
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                
                tables = cur.fetchall()
                if tables:
                    print("📋 Existing tables:")
                    for table in tables:
                        print(f"   - {table[0]}")
                        
                        # Check row count for each table
                        cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
                        count = cur.fetchone()[0]
                        print(f"     (contains {count} rows)")
                        
                        # Check table structure for silver_quote_notes
                        if table[0] == "databricks_postgres.silver_quote_notes_sycned":
                            print("   📋 silver_quote_notes structure:")
                            cur.execute("""
                                SELECT column_name, data_type, is_nullable, column_default
                                FROM information_schema.columns 
                                WHERE table_name = 'databricks_postgres.silver_quote_notes'
                                ORDER BY ordinal_position;
                            """)
                            columns = cur.fetchall()
                            for col in columns:
                                print(f"      {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'}) {f'DEFAULT {col[3]}' if col[3] else ''}")
                else:
                    print("❌ No tables found in database")
                    
        return True
    except Exception as e:
        print(f"❌ Error checking database tables: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return False

def test_database_operations(user: Optional[str] = None):
    """Test database operations to verify they work correctly"""
    try:
        db = QuoteDatabase(user=user)
        print(f"🧪 Testing database operations as user: {db.user}")
        
        # First check if we need to insert sample data
        quotes = db.get_all_quotes()
        if not quotes:
            print("📥 No quotes found, inserting sample data...")
            db.insert_sample_data()
            quotes = db.get_all_quotes()
        
        if quotes:
            print(f"📋 Found {len(quotes)} quotes in database")
            test_quote_id = quotes[0]["id"]
            print(f"🧪 Testing with quote: {test_quote_id}")
            
            # Test getting a specific quote
            quote = db.get_quote_by_id(test_quote_id)
            if quote:
                print(f"✅ Successfully retrieved quote: {quote['id']} - {quote['status']}")
                
                # Test updating the quote
                test_result = db.update_quote(
                    quote_id=test_quote_id,
                    note="Test note from database operations test",
                    note_type="Comment",
                    reviewer="Test User"
                )
                
                if test_result:
                    print("✅ Quote update test passed!")
                    
                    # Verify the change by retrieving the quote again
                    updated_quote = db.get_quote_by_id(test_quote_id)
                    if updated_quote and updated_quote.get("notes"):
                        print("✅ Note was added successfully!")
                        print(f"   Latest note: {updated_quote['notes'][0]['content']}")
                    else:
                        print("⚠️ Note was not found in retrieved quote")
                else:
                    print("❌ Quote update test failed!")
            else:
                print(f"❌ Failed to retrieve test quote {test_quote_id}")
        else:
            print("❌ No quotes available for testing")
            
        return True
    except Exception as e:
        print(f"❌ Database operations test failed: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return False

def initialize_database(user: Optional[str] = None):
    """Initialize the database with tables and sample data"""
    try:
        db = QuoteDatabase(user=user)
        print(f"🔧 Initializing quote management database for user: {db.user}")
        db.create_tables()
        print(db.get_quote_by_id("QT-001"))
        print("✅ Database initialization complete!")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    # Initialize database when script is run directly
    print("🚀 Running database operations script...")
    try:
        specific_user = "zach.jacobson@databricks.com"
        initialize_database(user=specific_user)
        
    except Exception as e:
        print(f"Error creating multiple database instances: {e}")