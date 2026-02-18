# Databricks notebook source
from pipeline.ingestion_pipeline import ingest
from libs.source_loader import get_register_function

# Connector source name
source_name = "qualtrics"

# =============================================================================
# INGESTION PIPELINE CONFIGURATION
# =============================================================================
# Update the spec below to configure your ingestion pipeline.
#
# pipeline_spec
# ├── connection_name (required): The Unity Catalog connection name
# └── objects[]: List of tables to ingest
#     └── table
#         ├── source_table (required): The table name in the source system
#         ├── destination_catalog (optional): Target catalog (defaults to pipeline's default)
#         ├── destination_schema (optional): Target schema (defaults to pipeline's default)
#         ├── destination_table (optional): Target table name (defaults to source_table)
#         └── table_configuration (optional)
#             ├── scd_type (optional): "SCD_TYPE_1" (default), "SCD_TYPE_2", or "APPEND_ONLY"
#             ├── primary_keys (optional): List of columns to override connector's default keys
#             └── (other options): See source connector's README
# =============================================================================
pipeline_spec = {
    "connection_name": "qualtrics_connector_demo_connection",
    "objects": [
        {
            "table": {
                "source_table": "surveys",
                "destination_table": "surveys"
            }
        },
        {
            "table": {
                "source_table": "directories",
                "destination_table": "directories"
            }
        },
        {
            "table": {
                "source_table": "users",
                "destination_table": "users"
            }
        },
        {
            "table": {
                "source_table": "survey_definitions",
                "destination_table": "survey_definitions",
                "table_configuration": {
                    "scd_type": "SCD_TYPE_2",
                    "primary_keys": [
                        "survey_id"
                    ]
                }
            }
        },
        {
            "table": {
                "source_table": "distributions",
                "destination_table": "distributions",
                "table_configuration": {
                    "scd_type": "SCD_TYPE_1",
                    "primary_keys": [
                        "id"
                    ]
                }
            }
        },
        {
            "table": {
                "source_table": "survey_responses",
                "destination_table": "survey_responses",
                "table_configuration": {
                    "scd_type": "APPEND_ONLY",
                    "primary_keys": [
                        "response_id"
                    ],
                    "surveyId": "SV_6J3cuObw2G9Iuns"
                }
            }
        },
        {
            "table": {
                "source_table": "mailing_lists",
                "destination_table": "mailing_lists",
                "table_configuration": {
                    "scd_type": "SCD_TYPE_2",
                    "primary_keys": [
                        "mailing_list_id"
                    ],
                    "directoryId": "POOL_2s74jRYyTkLxXl5"
                }
            }
        },
        {
            "table": {
                "source_table": "mailing_list_contacts",
                "destination_table": "mailing_list_contacts",
                "table_configuration": {
                    "scd_type": "SCD_TYPE_2",
                    "primary_keys": [
                        "contact_id"
                    ],
                    "directoryId": "POOL_2s74jRYyTkLxXl5",
                    "mailingListId": "CG_3EHey1hpikviMcz"
                }
            }
        },
        {
            "table": {
                "source_table": "directory_contacts",
                "destination_table": "directory_contacts",
                "table_configuration": {
                    "scd_type": "SCD_TYPE_2",
                    "primary_keys": [
                        "contact_id"
                    ],
                    "directoryId": "POOL_2s74jRYyTkLxXl5"
                }
            }
        }
    ]
}

# Dynamically import and register the LakeFlow source
register_lakeflow_source = get_register_function(source_name)
register_lakeflow_source(spark)

# Ingest the tables specified in the pipeline spec
ingest(spark, pipeline_spec)
