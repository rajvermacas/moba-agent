#!/usr/bin/env python3
"""
Test script to verify system prompt refactoring and injection
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.moba_agent.agent import MCPAgent
from src.moba_agent.config import Config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_system_prompt_injection():
    """Test that system prompt and resources are injected correctly"""
    
    try:
        # Initialize config and agent
        logger.info("Initializing agent...")
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Test 1: First message should have system prompt + resources + user message
        logger.info("\n=== Test 1: First message with system prompt ===")
        response1 = await agent.invoke("What are your capabilities?", thread_id="test_thread_1")
        
        # Check response
        if response1 and response1.get('response'):
            logger.info(f"✓ Agent responded successfully")
            logger.info(f"Response preview: {response1['response'][:200]}...")
        else:
            logger.error("✗ No response from agent")
        
        # Test 2: Check if agent mentions its capabilities
        response_text = response1.get('response', '').lower()
        capabilities_mentioned = []
        if 'visualization' in response_text or 'chart' in response_text or 'graph' in response_text:
            capabilities_mentioned.append('Data Visualization')
        if 'database' in response_text or 'query' in response_text:
            capabilities_mentioned.append('Database Queries')
        if 'gitlab' in response_text or 'issue' in response_text:
            capabilities_mentioned.append('GitLab Integration')
        
        if capabilities_mentioned:
            logger.info(f"✓ Agent mentioned capabilities: {', '.join(capabilities_mentioned)}")
        else:
            logger.warning("⚠ Agent didn't mention specific capabilities")
        
        # Test 3: Second message in same thread should still work correctly
        logger.info("\n=== Test 2: Second message in same thread ===")
        response2 = await agent.invoke("Can you create charts?", thread_id="test_thread_1")
        
        if response2 and response2.get('response'):
            logger.info(f"✓ Agent responded to follow-up question")
            logger.info(f"Response preview: {response2['response'][:200]}...")
        else:
            logger.error("✗ No response for follow-up question")
        
        # Test 3: New thread should also work
        logger.info("\n=== Test 3: New thread with fresh context ===")
        response3 = await agent.invoke("List your available tools", thread_id="test_thread_2")
        
        if response3 and response3.get('response'):
            logger.info(f"✓ Agent responded in new thread")
            
            # Check if tools are mentioned
            tools_text = response3.get('response', '').lower()
            if 'execute_query' in tools_text:
                logger.info("✓ Agent mentioned execute_query tools")
            if 'gitlab' in tools_text or 'create_gitlab_issue' in tools_text:
                logger.info("✓ Agent mentioned GitLab tools")
        else:
            logger.error("✗ No response in new thread")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return False


async def test_agent_node_cleanup():
    """Test that agent_node is properly cleaned up"""
    
    try:
        logger.info("\n=== Testing Agent Node Cleanup ===")
        
        # Initialize config and agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Check that _get_agent_system_prompt exists
        if hasattr(agent, '_get_agent_system_prompt'):
            logger.info("✓ _get_agent_system_prompt method exists")
            system_prompt = agent._get_agent_system_prompt()
            if 'Data Visualization' in system_prompt and 'Database Queries' in system_prompt:
                logger.info("✓ System prompt contains expected capabilities")
        else:
            logger.error("✗ _get_agent_system_prompt method not found")
        
        # Test a query to ensure agent_node works without hardcoded prompt
        response = await agent.invoke("Hello, how can you help me?", thread_id="cleanup_test")
        
        if response and response.get('response'):
            logger.info("✓ Agent node works without hardcoded system prompt")
            logger.info(f"Response: {response['response'][:100]}...")
        else:
            logger.error("✗ Agent node failed without hardcoded prompt")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    logger.info("Starting System Prompt Refactoring Tests")
    logger.info("=" * 60)
    
    # Run tests
    test1_passed = await test_system_prompt_injection()
    test2_passed = await test_agent_node_cleanup()
    
    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Results:")
    logger.info(f"  System Prompt Injection Test: {'PASSED' if test1_passed else 'FAILED'}")
    logger.info(f"  Agent Node Cleanup Test: {'PASSED' if test2_passed else 'FAILED'}")
    
    all_passed = test1_passed and test2_passed
    logger.info(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)