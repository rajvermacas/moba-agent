#!/usr/bin/env python3
"""
Test script for GitLab tool integration with mock token.

This script verifies that the native GitLab tool is properly integrated
with the MOBA Agent without requiring an actual GitLab token.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from moba_agent.agent import MCPAgent
from moba_agent.config import Config
from moba_agent.constants import GITLAB_DEFAULT_PROJECT_URL


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_gitlab_tool_loading_with_mock():
    """Test that GitLab tool is loaded when token is present (using mock)"""
    logger.info("=" * 70)
    logger.info("Testing GitLab Tool Loading with Mock Token")
    logger.info("=" * 70)
    
    # Set a mock GitLab token
    mock_token = "test-gitlab-token-12345"
    
    try:
        # Temporarily set the environment variable
        with patch.dict(os.environ, {"MOBA_GITLAB_TOKEN": mock_token}):
            logger.info("Mock GitLab token set in environment")
            
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
                logger.info("Native tools found:")
                for tool in agent.native_tools:
                    logger.info(f"  - {tool.name}: {tool.description}")
            
            # Check if GitLab tool is present
            gitlab_tool_found = any(
                tool.name == "create_gitlab_issue" 
                for tool in agent.native_tools
            )
            
            if gitlab_tool_found:
                logger.info("✅ GitLab tool successfully loaded!")
                
                # Get the GitLab tool
                gitlab_tool = next(
                    tool for tool in agent.native_tools 
                    if tool.name == "create_gitlab_issue"
                )
                
                # Verify tool properties
                logger.info(f"Tool name: {gitlab_tool.name}")
                logger.info(f"Tool description: {gitlab_tool.description}")
                logger.info(f"Tool has args_schema: {hasattr(gitlab_tool, 'args_schema')}")
                
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


async def test_langgraph_integration_with_mock():
    """Test that GitLab tool works with LangGraph agent (using mock)"""
    logger.info("=" * 70)
    logger.info("Testing LangGraph Integration with Mock Token")
    logger.info("=" * 70)
    
    # Set a mock GitLab token
    mock_token = "test-gitlab-token-12345"
    
    try:
        # Temporarily set the environment variable
        with patch.dict(os.environ, {"MOBA_GITLAB_TOKEN": mock_token}):
            logger.info("Mock GitLab token set for LangGraph test")
            
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
                
                # Check if GitLab tool is in all_tools
                gitlab_in_tools = any(
                    getattr(tool, 'name', '') == 'create_gitlab_issue'
                    for tool in agent.all_tools
                )
                
                if gitlab_in_tools:
                    logger.info("✅ GitLab tool is available in all_tools")
                    
                    # Find the GitLab tool
                    gitlab_tool = next(
                        tool for tool in agent.all_tools
                        if getattr(tool, 'name', '') == 'create_gitlab_issue'
                    )
                    
                    # Verify tool properties
                    logger.info(f"GitLab tool name: {getattr(gitlab_tool, 'name', 'N/A')}")
                    logger.info(f"GitLab tool has description: {hasattr(gitlab_tool, 'description')}")
                    logger.info(f"GitLab tool has args_schema: {hasattr(gitlab_tool, 'args_schema')}")
                    
                    return True
                else:
                    logger.warning("⚠️ GitLab tool not found in all_tools")
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


async def test_tool_structure():
    """Test the structure and architecture of the tool integration"""
    logger.info("=" * 70)
    logger.info("Testing Tool Integration Architecture")
    logger.info("=" * 70)
    
    # Set a mock GitLab token
    mock_token = "test-gitlab-token-12345"
    
    try:
        with patch.dict(os.environ, {"MOBA_GITLAB_TOKEN": mock_token}):
            # Initialize agent
            config = Config()
            agent = MCPAgent(config)
            await agent.initialize()
            
            # Test 1: Verify separate tool lists exist
            logger.info("\n1. Checking tool list architecture:")
            logger.info(f"   - Has mcp_tools list: {hasattr(agent, 'mcp_tools')}")
            logger.info(f"   - Has native_tools list: {hasattr(agent, 'native_tools')}")
            logger.info(f"   - Has all_tools list: {hasattr(agent, 'all_tools')}")
            logger.info(f"   - Legacy 'tools' reference works: {hasattr(agent, 'tools')}")
            
            # Test 2: Verify tool loading methods exist
            logger.info("\n2. Checking tool loading methods:")
            logger.info(f"   - Has _load_native_tools method: {hasattr(agent, '_load_native_tools')}")
            
            # Test 3: Verify tools are properly combined
            logger.info("\n3. Checking tool combination:")
            total_tools = len(agent.mcp_tools) + len(agent.native_tools)
            combined_tools = len(agent.all_tools)
            logger.info(f"   - MCP tools + Native tools = {total_tools}")
            logger.info(f"   - All tools count = {combined_tools}")
            logger.info(f"   - Properly combined: {total_tools == combined_tools}")
            
            # All checks passed
            all_checks_passed = (
                hasattr(agent, 'mcp_tools') and
                hasattr(agent, 'native_tools') and
                hasattr(agent, 'all_tools') and
                hasattr(agent, '_load_native_tools') and
                total_tools == combined_tools
            )
            
            if all_checks_passed:
                logger.info("\n✅ Tool integration architecture is correctly implemented!")
                return True
            else:
                logger.error("\n❌ Some architecture checks failed")
                return False
                
    except Exception as e:
        logger.error(f"Failed to test tool structure: {e}", exc_info=True)
        return False
    finally:
        if 'agent' in locals():
            await agent.close()


async def main():
    """Run all tests"""
    logger.info("Starting GitLab Tool Integration Tests (Mock Version)")
    logger.info("=" * 70)
    
    results = []
    
    # Test 1: Tool Structure
    logger.info("\n📝 Test 1: Tool Integration Architecture")
    result = await test_tool_structure()
    results.append(("Architecture", result))
    
    # Test 2: Tool Loading
    logger.info("\n📝 Test 2: GitLab Tool Loading")
    result = await test_gitlab_tool_loading_with_mock()
    results.append(("Tool Loading", result))
    
    # Test 3: LangGraph Integration
    logger.info("\n📝 Test 3: LangGraph Integration")
    result = await test_langgraph_integration_with_mock()
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
        logger.info("\nThe GitLab tool integration is working correctly.")
        logger.info("To test with a real GitLab server, set these environment variables:")
        logger.info("  - MOBA_GITLAB_TOKEN: Your GitLab personal access token")
        logger.info("  - MOBA_GITLAB_PROJECT_URL: Your GitLab project URL (optional)")
    else:
        logger.info("\n⚠️ Some tests failed. Check the logs above for details.")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)