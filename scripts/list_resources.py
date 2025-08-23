#!/usr/bin/env python3
"""
List all available MCP resources
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.moba_agent import MCPAgent, Config


async def main():
    """List all available MCP resources"""
    print("Connecting to MCP server...")
    
    try:
        # Initialize agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Get resources
        resources = await agent.get_available_resources()
        
        print(f"\n📚 Found {len(resources)} resources:\n")
        print("="*60)
        
        if not resources:
            print("No resources available from MCP server")
        else:
            for i, resource in enumerate(resources, 1):
                print(f"\n{i}. Resource URI: {resource['uri']}")
                print("-"*40)
                
                if resource.get('name'):
                    print(f"Name: {resource['name']}")
                
                if resource.get('description'):
                    print(f"Description: {resource['description']}")
                
                if resource.get('mimeType'):
                    print(f"MIME Type: {resource['mimeType']}")
        
        print("\n" + "="*60)
        
        # Close agent
        await agent.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())