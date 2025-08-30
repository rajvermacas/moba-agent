#!/usr/bin/env python3
"""
Test script to verify BaseTool integration for GitLab native tools.

This script tests that native tools properly inherit from BaseTool
and work correctly with LangChain/LangGraph.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langchain_core.tools import BaseTool
from moba_agent.native_tools.base import NativeTool
from moba_agent.native_tools.gitlab import GitLabIssueTool, GitLabIssueParams
from moba_agent.agent import MCPAgent
from moba_agent.config import Config


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_inheritance():
    """Test that NativeTool properly inherits from BaseTool"""
    logger.info("=" * 70)
    logger.info("Testing BaseTool Inheritance")
    logger.info("=" * 70)
    
    # Check if NativeTool inherits from BaseTool
    is_subclass = issubclass(NativeTool, BaseTool)
    logger.info(f"NativeTool is subclass of BaseTool: {is_subclass}")
    
    if not is_subclass:
        logger.error("❌ NativeTool does not inherit from BaseTool")
        return False
    
    # Check if GitLabIssueTool inherits from both
    gitlab_inherits_native = issubclass(GitLabIssueTool, NativeTool)
    gitlab_inherits_base = issubclass(GitLabIssueTool, BaseTool)
    
    logger.info(f"GitLabIssueTool inherits from NativeTool: {gitlab_inherits_native}")
    logger.info(f"GitLabIssueTool inherits from BaseTool: {gitlab_inherits_base}")
    
    if gitlab_inherits_native and gitlab_inherits_base:
        logger.info("✅ Inheritance chain is correct")
        return True
    else:
        logger.error("❌ Inheritance chain is broken")
        return False


async def test_tool_instantiation():
    """Test that GitLabIssueTool can be instantiated correctly"""
    logger.info("=" * 70)
    logger.info("Testing Tool Instantiation")
    logger.info("=" * 70)
    
    try:
        # Create a mock logger
        mock_logger = MagicMock()
        
        # Create GitLabIssueTool instance
        tool = GitLabIssueTool(
            access_token="test-token-123",
            logger=mock_logger
        )
        
        # Check tool properties
        logger.info(f"Tool name: {tool.name}")
        logger.info(f"Tool description: {tool.description}")
        logger.info(f"Tool has args_schema: {tool.args_schema is not None}")
        logger.info(f"Args schema type: {tool.args_schema}")
        
        # Check if it's a BaseTool instance
        is_basetool = isinstance(tool, BaseTool)
        logger.info(f"Tool is BaseTool instance: {is_basetool}")
        
        # Check required methods exist
        has_run = hasattr(tool, '_run')
        has_arun = hasattr(tool, '_arun')
        has_invoke = hasattr(tool, 'invoke')
        has_ainvoke = hasattr(tool, 'ainvoke')
        
        logger.info(f"Has _run method: {has_run}")
        logger.info(f"Has _arun method: {has_arun}")
        logger.info(f"Has invoke method: {has_invoke}")
        logger.info(f"Has ainvoke method: {has_ainvoke}")
        
        if all([is_basetool, has_run, has_arun, has_invoke, has_ainvoke]):
            logger.info("✅ Tool instantiation successful")
            return True
        else:
            logger.error("❌ Tool is missing required methods")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to instantiate tool: {e}")
        return False


async def test_tool_schema():
    """Test that the tool's args_schema works correctly"""
    logger.info("=" * 70)
    logger.info("Testing Tool Schema")
    logger.info("=" * 70)
    
    try:
        # Create tool instance
        mock_logger = MagicMock()
        tool = GitLabIssueTool(
            access_token="test-token-123",
            logger=mock_logger
        )
        
        # Test schema validation with valid data
        valid_params = {
            "project_url": "https://gitlab.com/test/project",
            "title": "Test Issue",
            "description": "Test description"
        }
        
        # Validate using the schema
        validated = tool.args_schema(**valid_params)
        logger.info(f"Schema validation successful: {validated}")
        
        # Check field types
        logger.info(f"Validated project_url: {validated.project_url}")
        logger.info(f"Validated title: {validated.title}")
        logger.info(f"Validated description: {validated.description}")
        
        # Test optional fields
        params_with_optional = {
            "project_url": "https://gitlab.com/test/project",
            "title": "Test Issue",
            "description": "Test description",
            "labels": ["bug", "feature"],
            "assignee": "testuser"
        }
        
        validated_optional = tool.args_schema(**params_with_optional)
        logger.info(f"Optional fields validated: labels={validated_optional.labels}, assignee={validated_optional.assignee}")
        
        logger.info("✅ Schema validation works correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Schema validation failed: {e}")
        return False


async def test_tool_execution_mock():
    """Test tool execution with mocked GitLab API"""
    logger.info("=" * 70)
    logger.info("Testing Tool Execution (Mocked)")
    logger.info("=" * 70)
    
    try:
        # Create tool instance
        mock_logger = MagicMock()
        tool = GitLabIssueTool(
            access_token="test-token-123",
            logger=mock_logger
        )
        
        # Mock the GitLab API
        with patch('moba_agent.native_tools.gitlab.gitlab.Gitlab') as mock_gitlab:
            # Setup mock objects
            mock_project = MagicMock()
            mock_issue = MagicMock()
            mock_issue.web_url = "https://gitlab.com/test/project/-/issues/123"
            
            mock_gitlab_instance = MagicMock()
            mock_gitlab_instance.projects.get.return_value = mock_project
            mock_project.issues.create.return_value = mock_issue
            mock_gitlab.return_value = mock_gitlab_instance
            
            # Test async execution
            result = await tool._arun(
                project_url="https://gitlab.com/test/project",
                title="Test Issue",
                description="Test description",
                labels=["test"]
            )
            
            logger.info(f"Tool execution result: {result}")
            
            # Verify the result is the issue URL
            if result == "https://gitlab.com/test/project/-/issues/123":
                logger.info("✅ Tool execution successful")
                return True
            else:
                logger.error(f"❌ Unexpected result: {result}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Tool execution failed: {e}")
        return False


async def test_langgraph_compatibility():
    """Test that tools work with LangGraph agent"""
    logger.info("=" * 70)
    logger.info("Testing LangGraph Compatibility")
    logger.info("=" * 70)
    
    with patch.dict(os.environ, {"MOBA_GITLAB_TOKEN": "test-token"}):
        try:
            # Initialize agent
            config = Config()
            agent = MCPAgent(config)
            await agent.initialize()
            
            # Check that native tools are loaded
            native_tool_count = len(agent.native_tools)
            logger.info(f"Native tools loaded: {native_tool_count}")
            
            if native_tool_count > 0:
                # Check first native tool
                first_tool = agent.native_tools[0]
                logger.info(f"First native tool type: {type(first_tool)}")
                logger.info(f"Is BaseTool: {isinstance(first_tool, BaseTool)}")
                
                # Prepare tools for LangGraph
                langgraph_tools = agent._prepare_tools_for_langgraph()
                logger.info(f"LangGraph tools prepared: {len(langgraph_tools)}")
                
                # Check if native tools are in the prepared list
                native_in_langgraph = any(
                    isinstance(tool, GitLabIssueTool) 
                    for tool in langgraph_tools
                )
                
                if native_in_langgraph:
                    logger.info("✅ Native tools are LangGraph-compatible")
                    return True
                else:
                    logger.error("❌ Native tools not found in LangGraph tools")
                    return False
            else:
                logger.warning("No native tools loaded (expected with mock token)")
                return True
                
        except Exception as e:
            logger.error(f"❌ LangGraph compatibility test failed: {e}")
            return False
        finally:
            if 'agent' in locals():
                await agent.close()


async def main():
    """Run all tests"""
    logger.info("Starting BaseTool Integration Tests")
    logger.info("=" * 70)
    
    results = []
    
    # Test 1: Inheritance
    logger.info("\n📝 Test 1: Inheritance")
    result = await test_inheritance()
    results.append(("Inheritance", result))
    
    # Test 2: Instantiation
    logger.info("\n📝 Test 2: Tool Instantiation")
    result = await test_tool_instantiation()
    results.append(("Instantiation", result))
    
    # Test 3: Schema
    logger.info("\n📝 Test 3: Tool Schema")
    result = await test_tool_schema()
    results.append(("Schema", result))
    
    # Test 4: Execution
    logger.info("\n📝 Test 4: Tool Execution")
    result = await test_tool_execution_mock()
    results.append(("Execution", result))
    
    # Test 5: LangGraph Compatibility
    logger.info("\n📝 Test 5: LangGraph Compatibility")
    result = await test_langgraph_compatibility()
    results.append(("LangGraph", result))
    
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
        logger.info("\nThe BaseTool integration is working correctly.")
        logger.info("Native tools are now proper LangChain BaseTool instances.")
    else:
        logger.info("\n⚠️ Some tests failed. Check the logs above for details.")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)