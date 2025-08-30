#!/usr/bin/env python3
"""
Test script for GitLab tool integration.

This script verifies that the native GitLab tool is properly integrated
with the MOBA Agent and can be invoked alongside MCP tools.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from moba_agent.agent import MCPAgent
from moba_agent.config import Config
from moba_agent.constants import GITLAB_DEFAULT_PROJECT_URL


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_gitlab_tool_loading():
    """Test that GitLab tool is loaded when token is present"""
    logger.info("=" * 70)
    logger.info("Testing GitLab Tool Loading")
    logger.info("=" * 70)
    
    # Check for GitLab token
    gitlab_token = os.getenv("MOBA_GITLAB_TOKEN")
    if not gitlab_token:
        logger.warning("MOBA_GITLAB_TOKEN not set in environment")
        logger.info("To test GitLab integration, set MOBA_GITLAB_TOKEN environment variable")
        return False
    else:
        logger.info("GitLab token found in environment")
    
    try:
        # Initialize agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Check native tools were loaded
        logger.info(f"MCP tools loaded: {len(agent.mcp_tools)}")
        logger.info(f"Native tools loaded: {len(agent.native_tools)}")
        logger.info(f"Total tools available: {len(agent.all_tools)}")
        
        # List native tools
        if agent.native_tools:
            logger.info("Native tools:")
            for tool in agent.native_tools:
                logger.info(f"  - {tool.name}: {tool.description}")
        
        # Check if GitLab tool is present
        gitlab_tool_found = any(
            tool.name == "create_gitlab_issue" 
            for tool in agent.native_tools
        )
        
        if gitlab_tool_found:
            logger.info("✅ GitLab tool successfully loaded!")
            return True
        else:
            logger.error("❌ GitLab tool not found in native tools")
            return False
            
    except Exception as e:
        logger.error(f"Failed to test GitLab tool loading: {e}", exc_info=True)
        return False
    finally:
        if 'agent' in locals():
            await agent.close()


async def test_gitlab_tool_invocation():
    """Test creating a GitLab issue using the native tool"""
    logger.info("=" * 70)
    logger.info("Testing GitLab Tool Invocation")
    logger.info("=" * 70)
    
    # Check for GitLab token
    gitlab_token = os.getenv("MOBA_GITLAB_TOKEN")
    if not gitlab_token:
        logger.warning("Skipping invocation test - no GitLab token")
        return False
    
    # Get project URL from environment or use default
    project_url = os.getenv("MOBA_GITLAB_PROJECT_URL", GITLAB_DEFAULT_PROJECT_URL)
    logger.info(f"Using GitLab project: {project_url}")
    
    # Check if it's the default test URL
    if project_url == GITLAB_DEFAULT_PROJECT_URL:
        logger.warning("Using default test project URL - this may fail")
        logger.info("Set MOBA_GITLAB_PROJECT_URL to a real GitLab project for testing")
        return False
    
    try:
        # Initialize agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Find GitLab tool
        gitlab_tool = None
        for tool in agent.native_tools:
            if tool.name == "create_gitlab_issue":
                gitlab_tool = tool
                break
        
        if not gitlab_tool:
            logger.error("GitLab tool not found")
            return False
        
        # Test parameters
        test_params = {
            "project_url": project_url,
            "title": "Test Issue from MOBA Agent Integration",
            "description": "This is a test issue created to verify GitLab tool integration.\n\n"
                          "**Details:**\n"
                          "- Created by: MOBA Agent test script\n"
                          "- Purpose: Verify native tool integration\n"
                          "- Type: Integration test\n\n"
                          "This issue can be closed.",
            "labels": ["test", "integration"]
        }
        
        logger.info("Creating test GitLab issue...")
        logger.debug(f"Parameters: {test_params}")
        
        # Invoke the tool using BaseTool interface
        try:
            result = await gitlab_tool._arun(**test_params)
            logger.info(f"✅ Successfully created GitLab issue!")
            logger.info(f"Issue URL: {result}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create issue: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to test GitLab tool invocation: {e}", exc_info=True)
        return False
    finally:
        if 'agent' in locals():
            await agent.close()


async def test_langgraph_integration():
    """Test that GitLab tool works with LangGraph agent"""
    logger.info("=" * 70)
    logger.info("Testing LangGraph Integration")
    logger.info("=" * 70)
    
    # Check for GitLab token
    gitlab_token = os.getenv("MOBA_GITLAB_TOKEN")
    if not gitlab_token:
        logger.warning("Skipping LangGraph test - no GitLab token")
        return False
    
    try:
        # Initialize agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Check that agent was created with tools
        if agent.agent:
            logger.info("✅ LangGraph agent created successfully")
            
            # Count tools in the agent
            tool_count = len(agent.all_tools)
            logger.info(f"Agent has access to {tool_count} tools")
            
            # Test if we can prepare tools for LangGraph
            try:
                langgraph_tools = agent._prepare_tools_for_langgraph()
                logger.info(f"✅ Successfully prepared {len(langgraph_tools)} tools for LangGraph")
                
                # Check if GitLab tool is in the prepared tools
                gitlab_in_langgraph = any(
                    getattr(tool, 'name', '') == 'create_gitlab_issue'
                    for tool in langgraph_tools
                )
                
                if gitlab_in_langgraph:
                    logger.info("✅ GitLab tool is available in LangGraph format")
                    return True
                else:
                    logger.warning("⚠️ GitLab tool not found in LangGraph tools")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to prepare tools for LangGraph: {e}")
                return False
        else:
            logger.error("❌ Agent not created")
            return False
            
    except Exception as e:
        logger.error(f"Failed to test LangGraph integration: {e}", exc_info=True)
        return False
    finally:
        if 'agent' in locals():
            await agent.close()


async def main():
    """Run all tests"""
    logger.info("Starting GitLab Tool Integration Tests")
    logger.info("=" * 70)
    
    results = []
    
    # Test 1: Tool Loading
    logger.info("\n📝 Test 1: Tool Loading")
    result = await test_gitlab_tool_loading()
    results.append(("Tool Loading", result))
    
    # Test 2: Tool Invocation (only if token is set)
    if os.getenv("MOBA_GITLAB_TOKEN"):
        logger.info("\n📝 Test 2: Tool Invocation")
        result = await test_gitlab_tool_invocation()
        results.append(("Tool Invocation", result))
    
    # Test 3: LangGraph Integration
    logger.info("\n📝 Test 3: LangGraph Integration")
    result = await test_langgraph_integration()
    results.append(("LangGraph Integration", result))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("Test Summary")
    logger.info("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        logger.info("\n🎉 All tests passed!")
    else:
        logger.info("\n⚠️ Some tests failed. Check the logs above for details.")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)