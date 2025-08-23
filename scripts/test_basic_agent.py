#!/usr/bin/env python3
"""
Basic test of the agent with multi-MCP configuration
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from langgraph_agent_mcp.config import Config
from langgraph_agent_mcp.agent import MCPAgent


async def main():
    """Test basic agent functionality"""
    print("Testing Multi-MCP Agent")
    print("=" * 50)
    
    try:
        # Load configuration
        config = Config()
        print(f"✓ Configuration loaded")
        print(f"✓ {len(config.mcp_servers)} MCP servers configured:")
        for server in config.mcp_servers:
            print(f"  - {server['name']} ({server['transport']})")
        
        # Initialize agent
        print("\nInitializing agent...")
        agent = MCPAgent(config)
        await agent.initialize()
        print("✓ Agent initialized successfully")
        
        # Get available tools
        tools = await agent.get_available_tools()
        print(f"\n✓ Found {len(tools)} tools available")
        
        # Get available resources
        resources = await agent.get_available_resources()
        print(f"✓ Found {len(resources)} resources available")
        
        # Test a simple query
        print("\nTesting simple query: 'What is 2+2?'")
        response = await agent.invoke("What is 2+2?")
        print(f"Response: {response}")
        
        # Close agent
        await agent.close()
        print("\n✓ Agent closed successfully")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)