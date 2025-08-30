#!/usr/bin/env python3
"""Test script to verify resource context injection is working correctly."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from moba_agent.agent import MCPAgent

# Configure logging to see our debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_resource_injection():
    """Test that resource context is injected only once per thread."""
    
    print("\n" + "="*60)
    print("Testing Resource Context Injection")
    print("="*60)
    
    # Create a mock agent with minimal setup
    agent = MCPAgent()
    
    # Mock the LLM and tools to avoid actual API calls
    agent.llm = AsyncMock()
    agent.llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test response"))
    agent.all_tools = []
    
    # Mock the MCP client to return test resources
    mock_mcp_client = AsyncMock()
    mock_mcp_client.list_resources = AsyncMock(return_value=[
        {"name": "test_resource", "uri": "test://resource"}
    ])
    agent.mcp_client = mock_mcp_client
    
    # Initialize the agent
    await agent.initialize()
    
    # Test 1: First message in thread should inject resources
    print("\nTest 1: First message in thread 'test_thread'")
    print("-" * 40)
    
    # Clear the tracking dictionary
    agent._thread_resources_injected.clear()
    
    # Prepare messages for a new thread
    messages = await agent._prepare_messages_for_thread("Test message", "test_thread")
    
    # Check if resources were injected
    assert "test_thread" in agent._thread_resources_injected, "Thread should be marked as having resources injected"
    
    # Check if SystemMessage with resources is in messages
    has_resource_message = any(
        "Available MCP Resources" in str(msg.content) 
        for msg in messages 
        if hasattr(msg, 'content')
    )
    
    if has_resource_message:
        print("✅ Resources injected on first message")
    else:
        print("❌ Resources NOT found in messages")
    
    # Test 2: Second message in same thread should NOT inject resources again
    print("\nTest 2: Second message in same thread 'test_thread'")
    print("-" * 40)
    
    initial_injection_count = len([
        msg for msg in messages 
        if hasattr(msg, 'content') and "Available MCP Resources" in str(msg.content)
    ])
    
    # Prepare another message for the same thread
    messages2 = await agent._prepare_messages_for_thread("Another test message", "test_thread")
    
    second_injection_count = len([
        msg for msg in messages2 
        if hasattr(msg, 'content') and "Available MCP Resources" in str(msg.content)
    ])
    
    if second_injection_count == 0:
        print("✅ Resources NOT re-injected on second message")
    else:
        print(f"❌ Resources were injected again! Count: {second_injection_count}")
    
    # Test 3: Different thread should get resources injected
    print("\nTest 3: First message in different thread 'another_thread'")
    print("-" * 40)
    
    messages3 = await agent._prepare_messages_for_thread("Test in new thread", "another_thread")
    
    assert "another_thread" in agent._thread_resources_injected, "New thread should be marked"
    
    has_resource_message = any(
        "Available MCP Resources" in str(msg.content) 
        for msg in messages3 
        if hasattr(msg, 'content')
    )
    
    if has_resource_message:
        print("✅ Resources injected for new thread")
    else:
        print("❌ Resources NOT found for new thread")
    
    print("\n" + "="*60)
    print("Test Summary:")
    print(f"Threads tracked: {list(agent._thread_resources_injected.keys())}")
    print("="*60)
    
    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_resource_injection())
        print("\n✅ All tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)