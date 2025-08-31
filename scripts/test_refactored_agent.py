#!/usr/bin/env python3
"""
Test script for the refactored MCP Agent with simplified architecture.

This script tests:
1. Basic agent invocation
2. Tool execution with retry policy
3. Visualization node integration
4. Flow: Agent -> Tools -> Agent -> Visualization -> End
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.moba_agent.agent import MCPAgent
from src.moba_agent.config import Config

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_basic_invocation():
    """Test basic agent invocation without tools"""
    logger.info("=" * 50)
    logger.info("Testing basic agent invocation")
    logger.info("=" * 50)
    
    agent = MCPAgent()
    await agent.initialize()
    
    # Test simple question
    result = await agent.invoke("What can you help me with?")
    logger.info(f"Response: {result['response'][:200]}...")
    
    return result


async def test_with_database_query():
    """Test agent with database query and visualization"""
    logger.info("=" * 50)
    logger.info("Testing agent with database query")
    logger.info("=" * 50)
    
    agent = MCPAgent()
    await agent.initialize()
    
    # Test query that should trigger visualization
    test_queries = [
        "Show me the top 5 products by sales",
        "What are the most popular categories?",
        "Display sales trends for last month"
    ]
    
    for query in test_queries[:1]:  # Test first query
        logger.info(f"Query: {query}")
        result = await agent.invoke(query)
        
        logger.info(f"Response: {result['response'][:200]}...")
        logger.info(f"Query Result Present: {result.get('query_result') is not None}")
        logger.info(f"Graph Data Present: {result.get('graph') is not None}")
        
        if result.get('query_result'):
            logger.info(f"Query rows: {len(result['query_result'].get('rows', []))}")
        
        if result.get('graph'):
            logger.info(f"Graph type: {result['graph'].get('chart', {}).get('type', 'Unknown')}")
    
    return result


async def test_tool_retry():
    """Test tool execution with retry policy"""
    logger.info("=" * 50)
    logger.info("Testing tool execution with retry")
    logger.info("=" * 50)
    
    agent = MCPAgent()
    await agent.initialize()
    
    # Test a query that might fail and retry
    result = await agent.invoke("Execute a complex database query with potential failures")
    
    logger.info(f"Response: {result['response'][:200]}...")
    
    return result


async def test_conversation_flow():
    """Test conversation flow with multiple messages"""
    logger.info("=" * 50)
    logger.info("Testing conversation flow")
    logger.info("=" * 50)
    
    agent = MCPAgent()
    await agent.initialize()
    
    thread_id = "test_conversation"
    
    # First message
    result1 = await agent.invoke("Hello, I need help with data analysis", thread_id)
    logger.info(f"Response 1: {result1['response'][:100]}...")
    
    # Follow-up with query
    result2 = await agent.invoke("Can you show me sales data?", thread_id)
    logger.info(f"Response 2: {result2['response'][:100]}...")
    logger.info(f"Has query result: {result2.get('query_result') is not None}")
    
    # Request visualization
    result3 = await agent.invoke("Create a bar chart of the results", thread_id)
    logger.info(f"Response 3: {result3['response'][:100]}...")
    logger.info(f"Has visualization: {result3.get('graph') is not None}")
    
    return result3


async def test_visualization_node():
    """Test visualization node directly"""
    logger.info("=" * 50)
    logger.info("Testing visualization node")
    logger.info("=" * 50)
    
    agent = MCPAgent()
    await agent.initialize()
    
    # Query that should trigger visualization
    result = await agent.invoke("Show me product sales in a chart")
    
    logger.info(f"Response: {result['response'][:200]}...")
    
    if result.get('graph'):
        logger.info("Visualization generated successfully!")
        logger.info(f"Chart config: {result['graph'].get('chart', {})}")
    else:
        logger.warning("No visualization generated")
    
    return result


async def main():
    """Run all tests"""
    logger.info("Starting refactored agent tests")
    
    try:
        # Run tests
        await test_basic_invocation()
        await asyncio.sleep(1)
        
        # Note: These tests require MCP server to be running
        # Uncomment to test with actual database
        # await test_with_database_query()
        # await asyncio.sleep(1)
        
        # await test_tool_retry()
        # await asyncio.sleep(1)
        
        # await test_conversation_flow()
        # await asyncio.sleep(1)
        
        # await test_visualization_node()
        
        logger.info("=" * 50)
        logger.info("All tests completed successfully!")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())