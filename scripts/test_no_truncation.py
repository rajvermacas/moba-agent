#!/usr/bin/env python3
"""
Test script to verify no truncation in the LangGraph MCP Agent
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.langgraph_agent_mcp.resources import ResourceHandler
from src.langgraph_agent_mcp.config import Config
from unittest.mock import Mock, AsyncMock


async def test_no_truncation():
    """Test that content is not truncated"""
    print("=" * 70)
    print("Testing No Truncation in MCP Agent")
    print("=" * 70)
    print()
    
    # Create a test resource handler
    config = Config()
    handler = ResourceHandler(config)
    
    # Create mock client with large content
    mock_client = Mock()
    mock_session = AsyncMock()
    
    # Create resources with large content
    large_content = "A" * 15000  # 15K characters
    
    mock_resource = Mock()
    mock_resource.uri = "resource://large"
    mock_resource.name = "Large Test Resource"
    mock_resource.description = "Test resource with large content"
    mock_resource.mimeType = "text/plain"
    
    mock_resources_response = Mock()
    mock_resources_response.resources = [mock_resource]
    
    mock_content = Mock()
    mock_content.text = large_content
    mock_read_response = Mock()
    mock_read_response.contents = mock_content
    
    mock_session.list_resources = AsyncMock(return_value=mock_resources_response)
    mock_session.read_resource = AsyncMock(return_value=mock_read_response)
    
    # Create async context manager
    async_context = AsyncMock()
    async_context.__aenter__ = AsyncMock(return_value=mock_session)
    async_context.__aexit__ = AsyncMock(return_value=None)
    
    mock_client.session = Mock(return_value=async_context)
    handler.set_client(mock_client)
    
    print("Testing with max_content_size=None (unlimited)")
    print("-" * 60)
    
    # Test with no truncation (None)
    resources = await handler.get_all_resources(max_content_size=None)
    
    if resources:
        resource = resources[0]
        content = resource.get('content', '')
        
        print(f"Resource: {resource.get('name')}")
        print(f"Content length: {len(content)} characters")
        print(f"Content starts with: {content[:50]}...")
        print(f"Content ends with: ...{content[-50:]}")
        print(f"Truncation message present: {'truncated' in content}")
        print()
        
        # Verify no truncation
        if len(content) == 15000 and 'truncated' not in content:
            print("✅ SUCCESS: Content was NOT truncated with max_content_size=None")
        else:
            print("❌ FAILED: Content was unexpectedly truncated")
            print(f"   Expected length: 15000, Got: {len(content)}")
    else:
        print("❌ FAILED: No resources returned")
    
    print()
    print("Testing with max_content_size=100 (should truncate)")
    print("-" * 60)
    
    # Test with truncation
    resources_truncated = await handler.get_all_resources(max_content_size=100)
    
    if resources_truncated:
        resource = resources_truncated[0]
        content = resource.get('content', '')
        
        print(f"Resource: {resource.get('name')}")
        print(f"Content length: {len(content)} characters")
        print(f"Content: {content}")
        print()
        
        # Verify truncation works when specified
        if 'truncated at 100 chars' in content:
            print("✅ SUCCESS: Content was correctly truncated when max_content_size=100")
        else:
            print("❌ FAILED: Content was not truncated as expected")
    else:
        print("❌ FAILED: No resources returned")
    
    print()
    print("=" * 70)
    print("Test Complete!")
    print("=" * 70)


async def main():
    """Main entry point"""
    await test_no_truncation()


if __name__ == "__main__":
    asyncio.run(main())