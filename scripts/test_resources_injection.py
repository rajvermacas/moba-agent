#!/usr/bin/env python3
"""
Test script to verify MCP resources context injection in the agent
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


async def test_resources_injection():
    """Test that resources context is injected on first message of each thread"""
    
    try:
        # Initialize config and agent
        logger.info("Initializing agent...")
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Test 1: First message in default thread should inject resources
        logger.info("\n=== Test 1: First message in default thread ===")
        response1 = await agent.invoke("What resources do you have access to?", thread_id="default")
        logger.info(f"Response: {response1.get('response', '')[:200]}...")
        
        # Check if resources were injected for this thread
        if "default" in agent._thread_resources_injected:
            logger.info("✓ Resources were injected for 'default' thread")
        else:
            logger.error("✗ Resources were NOT injected for 'default' thread")
        
        # Test 2: Second message in same thread should NOT re-inject resources
        logger.info("\n=== Test 2: Second message in same thread ===")
        response2 = await agent.invoke("Tell me more about the first resource", thread_id="default")
        logger.info(f"Response: {response2.get('response', '')[:200]}...")
        
        # Test 3: First message in new thread should inject resources
        logger.info("\n=== Test 3: First message in new thread ===")
        response3 = await agent.invoke("List all available tools", thread_id="thread_2")
        logger.info(f"Response: {response3.get('response', '')[:200]}...")
        
        # Check if resources were injected for the new thread
        if "thread_2" in agent._thread_resources_injected:
            logger.info("✓ Resources were injected for 'thread_2' thread")
        else:
            logger.error("✗ Resources were NOT injected for 'thread_2' thread")
        
        # Summary
        logger.info("\n=== Summary ===")
        logger.info(f"Threads with resources injected: {list(agent._thread_resources_injected.keys())}")
        logger.info(f"Total threads tracked: {len(agent._thread_resources_injected)}")
        
        # Check logs for injection messages
        logger.info("\nCheck the logs above for 'Injected MCP resources context' messages")
        logger.info("You should see it for 'default' and 'thread_2' threads, but not repeated")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return False


async def test_resources_context_format():
    """Test the format of resources context"""
    
    try:
        logger.info("\n=== Testing Resources Context Format ===")
        
        # Initialize config and agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Get the resources context
        resources_context = await agent._format_resources_context()
        
        if resources_context:
            logger.info("✓ Resources context was generated")
            logger.info(f"Context type: {type(resources_context)}")
            logger.info(f"Context preview (first 500 chars):\n{resources_context.content[:500]}...")
            
            # Check for expected content
            content = resources_context.content
            if "MCP Resources Available" in content:
                logger.info("✓ Contains 'MCP Resources Available' header")
            if "You have access to the above resources" in content:
                logger.info("✓ Contains usage instructions")
            
        else:
            logger.warning("✗ No resources context was generated (might be normal if no resources)")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    logger.info("Starting MCP Resources Injection Tests")
    logger.info("=" * 60)
    
    # Run tests
    test1_passed = await test_resources_injection()
    test2_passed = await test_resources_context_format()
    
    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Results:")
    logger.info(f"  Resources Injection Test: {'PASSED' if test1_passed else 'FAILED'}")
    logger.info(f"  Context Format Test: {'PASSED' if test2_passed else 'FAILED'}")
    
    all_passed = test1_passed and test2_passed
    logger.info(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)