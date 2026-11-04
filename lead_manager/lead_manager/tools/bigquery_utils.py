"""
BigQuery utility tools for Lead Manager.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from google.adk.tools import FunctionTool
from google.cloud import bigquery
from ..config import PROJECT, DATASET_ID, TABLE_ID, MEETING_TABLE_ID

logger = logging.getLogger(__name__)

async def check_hot_lead(email_address: str) -> bool:
    """
    Check if an email address is in the hot leads database.

    Args:
        email_address: Email address to check

    Returns:
        bool indicating if the email is a hot lead or not, along with lead data if found.
    """

    # Sleep for 2 sec
    try:
        logger.info(f"🔍 Checking if {email_address} is a hot lead...")

        import os
        if os.environ.get("MOCK_LEAD_FINDER", "").lower() == "true":
            logger.info("Using MOCK mode for BigQuery hot lead check")
            return {
                "success": True,
                "is_hot_lead": True,
                "email": email_address,
                "lead_data": {
                    "email": email_address,
                    "name": "Mock Business",
                    "id": "mock-uuid"
                },
                "message": f"{email_address} found in hot leads database (MOCK)"
            }

        # Initialize BigQuery client
        client = bigquery.Client(project=PROJECT)

        # Query to check if email exists in hot leads table
        query = f"""
        SELECT
            *
        FROM `{PROJECT}.{DATASET_ID}.{TABLE_ID}`
        WHERE LOWER(email) = LOWER(@email_address)
        LIMIT 1
        """

        # Configure query parameters
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("email_address", "STRING", email_address),
            ]
        )

        # Execute query
        query_job = client.query(query, job_config=job_config)
        results = list(query_job)

        if not results:
            logger.info(f"❌ {email_address} is not a hot lead")
            return {
                "success": True,
                "is_hot_lead": False,
                "email": email_address,
                "lead_data": None,
                "message": f"{email_address} is not found in hot leads database"
            }

        # Convert BigQuery row to dictionary
        lead_data = dict(results[0])

        # Convert any datetime objects to strings for JSON serialization
        for key, value in lead_data.items():
            if isinstance(value, datetime):
                lead_data[key] = value.isoformat()

        logger.info(f"✅ {email_address} is a hot lead!")
        return {
            "success": True,
            "is_hot_lead": True,
            "email": email_address,
            "lead_data": lead_data,
            "message": f"{email_address} found in hot leads database"
        }

    except Exception as e:
        logger.error(f"❌ Error checking hot lead: {e}")
        return {
            "success": False,
            "is_hot_lead": False,
            "email": email_address,
            "lead_data": None,
            "error": str(e),
            "message": f"Error checking hot lead status: {str(e)}"
        }

async def save_meeting_arrangement(
    calendar_request: Dict[str, Any],
    email_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Persist the confirmed receipt in the designated owner-scoped SQLite store."""
    from common.integration_store import IntegrationStore
    from common.execution_store import WorkStore
    try:
        WorkStore().require_job()
        key = calendar_request.get('action_key')
        if not key:
            return {'success': False, 'persisted': False, 'error': 'Confirmed action_key is required'}
        return await asyncio.to_thread(IntegrationStore().save_meeting, key)
    except Exception:
        return {'success': False, 'persisted': False, 'storage': 'local_sqlite',
                'error': 'Meeting persistence failed; retry with the same confirmed action key'}

# Create the tools
check_hot_lead_tool = FunctionTool(func=check_hot_lead)

save_meeting_tool = FunctionTool(func=save_meeting_arrangement)
