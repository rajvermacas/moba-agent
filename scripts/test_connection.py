#!/usr/bin/env python3
"""
Test MCP server connection
"""

import asyncio
import sys
import os
import httpx

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.moba_agent.config import Config


async def test_sse_connection():
    """Test SSE/Streamable HTTP connection to MCP server"""
    config = Config()
    
    print("Testing MCP Server Connection")
    print("="*60)
    print(f"Server URL: {config.mcp_server_url}")
    print(f"Transport: {config.mcp_transport}")
    print("="*60)
    
    try:
        # Test basic HTTP connection
        print("\n1. Testing HTTP connectivity...")
        async with httpx.AsyncClient() as client:
            # Try to connect to the base URL
            try:
                # For SSE endpoints, just check if we can connect
                response = await client.get(
                    config.mcp_server_url,
                    timeout=httpx.Timeout(5.0, connect=5.0, read=1.0),
                    follow_redirects=True
                )
                print(f"   ✅ Server responded with status: {response.status_code}")
                
                # Check headers
                if 'content-type' in response.headers:
                    print(f"   Content-Type: {response.headers['content-type']}")
                    if 'text/event-stream' in response.headers['content-type']:
                        print("   ✅ SSE endpoint confirmed")
                
            except httpx.ConnectError:
                print(f"   ❌ Failed to connect to {config.mcp_server_url}")
                print("   Make sure the MCP server is running")
                return False
            except httpx.ReadTimeout:
                # For SSE, a read timeout is expected as it's a streaming endpoint
                print(f"   ✅ Server is responding (SSE streaming endpoint)")
            except httpx.TimeoutException as e:
                print(f"   ❌ Connection timeout to {config.mcp_server_url}: {e}")
                return False
        
        # Test MCP client connection
        print("\n2. Testing MCP client connection...")
        from langchain_mcp_adapters.client import MultiServerMCPClient
        
        server_config = config.get_mcp_server_config()
        client = MultiServerMCPClient(server_config)
        
        # Try to get tools
        print("   Attempting to fetch tools...")
        tools = await client.get_tools()
        
        if tools:
            print(f"   ✅ Successfully connected! Found {len(tools)} tools")
            tool_names = [t.name if hasattr(t, 'name') else str(t) for t in tools[:3]]
            if tool_names:
                print(f"   Sample tools: {', '.join(tool_names)}")
        else:
            print("   ⚠️  Connected but no tools available")
        
        # Try to get resources via session
        print("\n3. Testing resource access...")
        try:
            async with client.session(config.mcp_server_name) as session:
                resources_response = await session.list_resources()
                
                if hasattr(resources_response, 'resources'):
                    resources = resources_response.resources
                    print(f"   ✅ Found {len(resources)} resources")
                else:
                    print("   ⚠️  No resources available")
        except Exception as e:
            print(f"   ⚠️  Could not fetch resources: {e}")
        
        print("\n" + "="*60)
        print("✅ Connection test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Connection test failed: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure MCP server is running at", config.mcp_server_url)
        print("2. Check that the server supports", config.mcp_transport, "transport")
        print("3. Verify firewall/network settings")
        print("4. Check server logs for errors")
        return False


async def main():
    """Main entry point"""
    success = await test_sse_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())