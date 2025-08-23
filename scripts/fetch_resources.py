#!/usr/bin/env python3
"""
Fetch MCP resources
"""

import asyncio
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.moba_agent import MCPAgent, Config


async def main():
    """Fetch and display MCP resources"""
    print("MCP Resource Fetcher")
    print("="*60)
    
    try:
        # Initialize agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Get available resources
        resources = await agent.get_available_resources()
        
        if not resources:
            print("No resources available from MCP server")
            await agent.close()
            return
        
        print(f"Found {len(resources)} resources\n")
        
        # Display resources
        print("Available resources:")
        for i, resource in enumerate(resources, 1):
            print(f"  {i}. {resource['uri']}")
            if resource.get('name'):
                print(f"     Name: {resource['name']}")
        
        print("\n" + "-"*60)
        
        # Interactive resource fetching
        while True:
            print("\nOptions:")
            print("  1. Enter resource number to fetch (1-{})".format(len(resources)))
            print("  2. Enter resource URI directly")
            print("  3. Quit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == "3" or choice.lower() == "quit":
                break
            
            resource_uri = None
            
            if choice == "2":
                resource_uri = input("Enter resource URI: ").strip()
            else:
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(resources):
                        resource_uri = resources[index]['uri']
                    else:
                        print("Invalid resource number")
                        continue
                except ValueError:
                    print("Invalid input")
                    continue
            
            if resource_uri:
                print(f"\n📥 Fetching resource: {resource_uri}")
                print("-"*40)
                
                # Fetch resource
                content = await agent.fetch_resource(resource_uri)
                
                if content:
                    print("\n📄 Resource Content:")
                    
                    if isinstance(content, list):
                        for i, item in enumerate(content, 1):
                            print(f"\nItem {i}:")
                            if isinstance(item, dict):
                                for key, value in item.items():
                                    if key == 'text' and isinstance(value, str) and len(value) > 200:
                                        print(f"  {key}: {value[:200]}...")
                                    else:
                                        print(f"  {key}: {value}")
                            else:
                                print(f"  {item}")
                    elif isinstance(content, dict):
                        for key, value in content.items():
                            if key == 'text' and isinstance(value, str) and len(value) > 500:
                                print(f"{key}:\n{value[:500]}...")
                            else:
                                print(f"{key}: {value}")
                    else:
                        print(content)
                else:
                    print("❌ Failed to fetch resource or resource is empty")
            
            print("\n" + "="*60)
        
        # Close agent
        await agent.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())