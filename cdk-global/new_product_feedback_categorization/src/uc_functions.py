from dotenv import load_dotenv
from pathlib import Path
from databricks.connect import DatabricksSession
import os
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
# Load .env from repo root so it works regardless of cwd
from databricks.connect import DatabricksSession
# Default to serverless so bundle runs don't require a cluster_id in ~/.databrickscfg
spark = DatabricksSession.builder.profile("dogfood1").serverless().getOrCreate()

# Unity Catalog configuration from environment variables
CATALOG = os.getenv("CATALOG_NAME", "mfg_mid_central_sa")
SCHEMA = os.getenv("SCHEMA_NAME", "qbr_demo")

def uc_functions():
    lead_time_prediction_function_text = f"""CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.predict_lead_time(
  quantity INT,
  unit_price STRING,
  total_price STRING,
  priority_encoded INT,
  status_encoded INT,
  product_encoded INT
)
RETURNS DOUBLE
LANGUAGE SQL
COMMENT 'Predicts lead time for a quote by calling the lead_time_predictor model serving endpoint'
RETURN (
  SELECT ai_query(
    'dev_zach_jacobson_zach-demo-serving-endpoint-qbr',
    named_struct(
      'quantity', quantity,
      'unit_price', unit_price,
      'total_price', total_price,
      'priority_encoded', priority_encoded,
      'status_encoded', status_encoded,
      'product_encoded', product_encoded
    )
  )
);"""

    parse_email_function_text = f"""CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.parse_email(email STRING)
RETURNS STRING
LANGUAGE SQL
RETURN
select ai_query(
    'databricks-gpt-oss-20b',
    concat(
        'Extract quote information from the following text data: ',
        email
    ),
    responseFormat => '{{
        "type": "json_schema",
        "json_schema": {{
            "name": "quote_extraction",
            "schema": {{
                "type": "object",
                "properties": {{
                    "id": {{"type": "string"}},
                    "customer_id": {{"type": "string"}},
                    "customer_name": {{"type": "string"}},
                    "location": {{"type": "string"}},
                    "product_id": {{"type": "string"}},
                    "product_description": {{"type": "string"}},
                    "quantity": {{"type": "integer"}},
                    "unit_price": {{"type": "number"}},
                    "total_price": {{"type": "number"}},
                    "order_date": {{"type": "string"}},
                    "status": {{"type": "string"}},
                    "priority": {{"type": "string"}},
                    "email_source": {{"type": "string"}},
                    "email_subject": {{"type": "string"}},
                    "email_body": {{"type": "string"}},
                    "email_received_at": {{"type": "string"}},
                    "assigned_reviewer": {{"type": "string"}}
                }}
            }}
        }}
    }}'
)"""
    print('Executing SQL...')
    spark.sql(lead_time_prediction_function_text)
    print('Executing SQL...')
    spark.sql(parse_email_function_text)

if __name__ == "__main__":
    uc_functions()