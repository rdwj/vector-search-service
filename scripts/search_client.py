#!/usr/bin/env python3
"""
Simple search client for Vector Search Service
Tests RAG functionality with ServiceNow data
"""

import httpx
import asyncio
import json
import os
from typing import List, Dict, Any

# Configuration
VECTOR_SERVICE_URL = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8000")
COLLECTION_NAME = "servicenow_incidents"

async def search_incidents(query: str, limit: int = 5):
    """Search for incidents using semantic search"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VECTOR_SERVICE_URL}/api/v1/search",
            json={
                "collection_name": COLLECTION_NAME,
                "query": query,
                "limit": limit,
                "include_metadata": True
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Search failed: {response.status_code} - {response.text}")
            return None

def format_result(result: Dict[str, Any], index: int):
    """Format a single search result for display"""
    metadata = result.get('metadata', {})
    score = result.get('score', 0.0)
    
    print(f"\n{'='*60}")
    print(f"Result #{index + 1} (Score: {score:.4f})")
    print(f"{'='*60}")
    
    if metadata.get('number'):
        print(f"Incident: {metadata['number']}")
    
    if metadata.get('short_description'):
        print(f"Summary: {metadata['short_description']}")
    
    if metadata.get('category'):
        print(f"Category: {metadata['category']}")
        
    if metadata.get('subcategory'):
        print(f"Subcategory: {metadata['subcategory']}")
    
    print(f"\nDescription:")
    desc = metadata.get('description', 'N/A')
    if len(desc) > 200:
        print(f"{desc[:200]}...")
    else:
        print(desc)
    
    if metadata.get('close_notes'):
        print(f"\nResolution:")
        notes = metadata['close_notes']
        if len(notes) > 200:
            print(f"{notes[:200]}...")
        else:
            print(notes)

async def interactive_search():
    """Interactive search session"""
    print("ServiceNow RAG Search Client")
    print("Type 'quit' to exit")
    print("-" * 60)
    
    while True:
        query = input("\nEnter search query: ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            break
        
        if not query:
            continue
        
        print(f"\nSearching for: '{query}'...")
        
        results = await search_incidents(query)
        
        if results and 'results' in results:
            search_results = results['results']
            print(f"\nFound {len(search_results)} relevant incidents")
            
            for i, result in enumerate(search_results):
                format_result(result, i)
        else:
            print("No results found")

async def test_queries():
    """Run some test queries"""
    test_queries = [
        "x-window display error",
        "VNC connection issues",
        "authentication problems",
        "software installation",
        "network connectivity"
    ]
    
    print("Running test queries...")
    print("-" * 60)
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = await search_incidents(query, limit=3)
        
        if results and 'results' in results:
            print(f"Found {len(results['results'])} results")
            for i, result in enumerate(results['results']):
                metadata = result.get('metadata', {})
                score = result.get('score', 0.0)
                print(f"  {i+1}. Incident {metadata.get('number', 'N/A')} (Score: {score:.4f})")
                print(f"     {metadata.get('short_description', 'No description')[:80]}")
        else:
            print("  No results found")

async def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            await test_queries()
        else:
            # Single query mode
            query = " ".join(sys.argv[1:])
            results = await search_incidents(query)
            
            if results and 'results' in results:
                search_results = results['results']
                print(f"\nFound {len(search_results)} relevant incidents for '{query}'")
                
                for i, result in enumerate(search_results):
                    format_result(result, i)
            else:
                print("No results found")
    else:
        # Interactive mode
        await interactive_search()

if __name__ == "__main__":
    asyncio.run(main())