#!/usr/bin/env python3
"""
List all available MCP tools
"""

import asyncio
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.moba_agent import MCPAgent, Config


async def main():
    """List all available MCP tools"""
    print("Connecting to MCP server...")
    
    try:
        # Initialize agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Get tools
        tools = await agent.get_available_tools()
        
        print(f"\n📦 Found {len(tools)} tools:\n")
        print("="*60)
        
        if not tools:
            print("No tools available from MCP server")
        else:
            for i, tool in enumerate(tools, 1):
                print(f"\n{i}. Tool: {tool['name']}")
                print("-"*40)
                
                if tool.get('description'):
                    print(f"Description: {tool['description']}")
                
                if tool.get('type'):
                    print(f"Type: {tool['type']}")
                
                if tool.get('parameters'):
                    print("Parameters:")
                    params = tool['parameters']
                    if isinstance(params, dict):
                        print(json.dumps(params, indent=2))
                    else:
                        print(f"  {params}")
        
        print("\n" + "="*60)
        
        # Close agent
        await agent.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())