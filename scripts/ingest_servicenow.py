#!/usr/bin/env python3
"""
ServiceNow Incident Ingestion Script for Vector Search Service
This script processes ServiceNow XML incidents and ingests them into the vector database
"""

import os
import sys
import xml.etree.ElementTree as ET
import asyncio
import httpx
import json
from pathlib import Path
from typing import List, Dict, Any
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment or defaults
VECTOR_SERVICE_URL = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8000")
SERVICENOW_DATA_PATH = os.getenv("SERVICENOW_DATA_PATH", "./data/servicenow")
COLLECTION_NAME = "servicenow_incidents"

def parse_servicenow_xml(file_path: str) -> Dict[str, Any]:
    """Parse ServiceNow incident XML file"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        incident = root.find('.//incident')
        if incident is None:
            logger.error(f"No incident found in {file_path}")
            return None
        
        # Extract key fields
        data = {}
        fields_to_extract = [
            'number', 'description', 'short_description', 'category', 
            'subcategory', 'priority', 'impact', 'urgency', 'state',
            'assigned_to', 'assignment_group', 'caller_id', 'close_notes',
            'resolution_notes', 'work_notes', 'comments', 'knowledge',
            'u_affected_service', 'u_root_cause', 'u_business_impact',
            'opened_at', 'closed_at', 'resolved_at', 'sys_created_on',
            'sys_updated_on', 'active', 'incident_state', 'close_code'
        ]
        
        for field in fields_to_extract:
            element = incident.find(field)
            if element is not None and element.text:
                # Handle display_value attributes
                if element.get('display_value'):
                    data[field] = element.get('display_value')
                else:
                    data[field] = element.text.strip()
        
        # Create a searchable text field combining key information
        searchable_parts = []
        
        if data.get('number'):
            searchable_parts.append(f"Incident: {data['number']}")
        if data.get('short_description'):
            searchable_parts.append(f"Summary: {data['short_description']}")
        if data.get('description'):
            searchable_parts.append(f"Description: {data['description']}")
        if data.get('category'):
            searchable_parts.append(f"Category: {data['category']}")
        if data.get('subcategory'):
            searchable_parts.append(f"Subcategory: {data['subcategory']}")
        if data.get('close_notes'):
            searchable_parts.append(f"Resolution: {data['close_notes']}")
        if data.get('resolution_notes'):
            searchable_parts.append(f"Resolution Notes: {data['resolution_notes']}")
        if data.get('work_notes'):
            searchable_parts.append(f"Work Notes: {data['work_notes']}")
        if data.get('u_root_cause'):
            searchable_parts.append(f"Root Cause: {data['u_root_cause']}")
        
        data['searchable_text'] = "\n\n".join(searchable_parts)
        data['source_file'] = os.path.basename(file_path)
        
        return data
        
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {str(e)}")
        return None

async def create_collection(client: httpx.AsyncClient):
    """Create ServiceNow collection if it doesn't exist"""
    try:
        # Check if collection exists
        response = await client.get(f"{VECTOR_SERVICE_URL}/api/v1/collections/{COLLECTION_NAME}")
        if response.status_code == 200:
            logger.info(f"Collection '{COLLECTION_NAME}' already exists")
            return
        
        # Create collection
        collection_data = {
            "name": COLLECTION_NAME,
            "description": "ServiceNow incident data for RAG",
            "metadata": {
                "source": "servicenow",
                "type": "incidents",
                "created_at": datetime.utcnow().isoformat()
            }
        }
        
        response = await client.post(
            f"{VECTOR_SERVICE_URL}/api/v1/collections",
            json=collection_data
        )
        
        if response.status_code == 201:
            logger.info(f"Created collection '{COLLECTION_NAME}'")
        else:
            logger.error(f"Failed to create collection: {response.text}")
            
    except Exception as e:
        logger.error(f"Error creating collection: {str(e)}")

async def ingest_document(client: httpx.AsyncClient, incident_data: Dict[str, Any]):
    """Ingest a single ServiceNow incident into the vector database"""
    try:
        # Prepare document for ingestion
        document = {
            "collection_name": COLLECTION_NAME,
            "content": incident_data['searchable_text'],
            "metadata": {
                k: v for k, v in incident_data.items() 
                if k != 'searchable_text' and v is not None
            }
        }
        
        # If we have an incident number, use it as document ID
        if incident_data.get('number'):
            document['document_id'] = f"incident_{incident_data['number']}"
        
        # Send to vector service
        response = await client.post(
            f"{VECTOR_SERVICE_URL}/api/v1/documents",
            json=document,
            timeout=30.0
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"Successfully ingested incident: {incident_data.get('number', 'unknown')}")
            return True
        else:
            logger.error(f"Failed to ingest incident: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error ingesting document: {str(e)}")
        return False

async def main():
    """Main ingestion process"""
    # Find all ServiceNow XML files
    data_path = Path(SERVICENOW_DATA_PATH)
    xml_files = list(data_path.glob("incident_*.xml"))
    
    logger.info(f"Found {len(xml_files)} ServiceNow incident files")
    
    if not xml_files:
        logger.error("No incident files found")
        return
    
    # Parse all incidents
    incidents = []
    for xml_file in xml_files:
        logger.info(f"Parsing {xml_file}")
        incident_data = parse_servicenow_xml(str(xml_file))
        if incident_data:
            incidents.append(incident_data)
    
    logger.info(f"Successfully parsed {len(incidents)} incidents")
    
    # Ingest into vector database
    async with httpx.AsyncClient() as client:
        # Create collection first
        await create_collection(client)
        
        # Ingest documents
        success_count = 0
        for incident in incidents:
            if await ingest_document(client, incident):
                success_count += 1
        
        logger.info(f"Successfully ingested {success_count}/{len(incidents)} incidents")
        
        # Test search to verify
        if success_count > 0:
            logger.info("Testing search functionality...")
            search_response = await client.post(
                f"{VECTOR_SERVICE_URL}/api/v1/search",
                json={
                    "collection_name": COLLECTION_NAME,
                    "query": "x-window error display",
                    "limit": 3
                }
            )
            
            if search_response.status_code == 200:
                results = search_response.json()
                logger.info(f"Search test returned {len(results.get('results', []))} results")
            else:
                logger.error(f"Search test failed: {search_response.text}")

if __name__ == "__main__":
    asyncio.run(main())