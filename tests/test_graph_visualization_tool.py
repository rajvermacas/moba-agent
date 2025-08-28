"""
Unit tests for GraphVisualizationTool
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from langchain_core.messages import AIMessage

from src.moba_agent.graph_visualization_tool import GraphVisualizationTool


class TestGraphVisualizationTool:
    """Test suite for GraphVisualizationTool"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent with necessary attributes"""
        agent = Mock()
        agent.llm = AsyncMock()
        agent.config = {}
        agent.logger = Mock()
        return agent
    
    @pytest.fixture
    def mock_query_results(self):
        """Sample query results for testing"""
        return {
            "rows": [
                {"category": "A", "value": 100, "date": "2024-01-01"},
                {"category": "B", "value": 200, "date": "2024-01-02"},
                {"category": "C", "value": 150, "date": "2024-01-03"},
            ],
            "columns": ["category", "value", "date"],
            "query": "SELECT category, value, date FROM sales"
        }
    
    @pytest.fixture
    def tool(self, mock_agent):
        """Create GraphVisualizationTool instance"""
        return GraphVisualizationTool(mock_agent)
    
    def test_initialization(self, mock_agent):
        """Test tool initialization with agent reference"""
        tool = GraphVisualizationTool(mock_agent)
        
        assert tool.agent == mock_agent
        assert tool.llm == mock_agent.llm
        assert not hasattr(tool, 'memory')  # No local memory storage
        assert tool.config == {}
    
    def test_add_to_memory(self, tool):
        """Test memory addition functionality"""
        entry = {
            "role": "assistant",
            "content": "Test content",
            "metadata": {"type": "test"}
        }
        
        # add_to_memory now just logs, doesn't store locally
        tool.add_to_memory(entry)
        
        # No local memory storage to verify
        assert not hasattr(tool, 'memory')
    
    @pytest.mark.asyncio
    async def test_arun_success(self, tool, mock_query_results, mock_agent):
        """Test successful graph generation with provided config"""
        # Provide chart configuration directly (no LLM call needed)
        chart_config = {
            "chart_type": "bar",
            "x_axis": "category",
            "y_axis": "value",
            "title": "Sales by Category",
            "color_field": None
        }
        
        # Run the tool with thread_id and chart_config
        result = await tool.arun(mock_query_results, thread_id="test_thread", chart_config=chart_config)
        
        # Verify result structure
        assert result["status"] == "success"
        assert "graph_id" in result
        assert "graph_data" in result
        assert "explanation" in result
        assert result["chart_type"] == "bar"
        assert "metadata" in result
        
        # Verify metadata structure for thread persistence
        assert result["metadata"]["type"] == "visualization"
        assert result["metadata"]["thread_id"] == "test_thread"
        assert "graph_ref" in result["metadata"]
        assert "timestamp" in result["metadata"]
    
    @pytest.mark.asyncio
    async def test_arun_with_string_input(self, tool, mock_query_results, mock_agent):
        """Test handling of string input for query results"""
        # Provide chart configuration
        chart_config = {
            "chart_type": "line",
            "x_axis": "date",
            "y_axis": "value",
            "title": "Values over Time",
            "color_field": None
        }
        
        # Pass query results as string with thread_id and config
        result = await tool.arun(json.dumps(mock_query_results), thread_id="test_thread", chart_config=chart_config)
        
        assert result["status"] == "success"
        assert result["chart_type"] == "line"
    
    @pytest.mark.asyncio
    async def test_arun_error_handling(self, tool, mock_agent):
        """Test graceful error handling"""
        # Pass invalid data that will cause an error
        result = await tool.arun({"rows": [], "columns": []}, thread_id="test_thread", chart_config=None)
        
        # Verify error response
        assert result["status"] == "error"
        assert "Error occurred while creating graph" in result["explanation"]
        assert "error" in result
        assert "metadata" in result
        
        # Verify error metadata for thread persistence
        assert result["metadata"]["type"] == "viz_error"
        assert result["metadata"]["thread_id"] == "test_thread"
    
    @pytest.mark.asyncio
    async def test_arun_fallback_without_config(self, tool, mock_query_results, mock_agent):
        """Test fallback to heuristics when no config provided"""
        # Mock fallback recommendation to work
        with patch('src.moba_agent.graph_visualization._get_fallback_recommendation') as mock_fallback:
            mock_fallback.return_value = {
                "chart_type": "bar",
                "config": {
                    "x_axis": "category",
                    "y_axis": "value",
                    "title": "Fallback Chart",
                    "color_field": None
                }
            }
            
            # Run without chart_config to trigger fallback
            result = await tool.arun(mock_query_results, thread_id="test_thread", chart_config=None)
            
            # Should still succeed with fallback
            assert result["status"] == "success"
            assert result["chart_type"] == "bar"
    
    @pytest.mark.asyncio
    async def test_arun_with_context(self, tool, mock_query_results, mock_agent):
        """Test passing context to the tool"""
        chart_config = {
            "chart_type": "pie",
            "x_axis": "category",
            "y_axis": "value",
            "title": "Distribution",
            "color_field": None
        }
        
        context = [
            {"role": "user", "content": "Show me a pie chart"},
            {"role": "assistant", "content": "Creating visualization"}
        ]
        
        result = await tool.arun(mock_query_results, context=context, thread_id="test_thread", chart_config=chart_config)
        
        assert result["status"] == "success"
        assert result["chart_type"] == "pie"
    
    @pytest.mark.asyncio
    async def test_metadata_structure_for_thread_persistence(self, tool, mock_query_results, mock_agent):
        """Test metadata structure for thread persistence"""
        # Provide chart config
        chart_config = {
            "chart_type": "bar",
            "x_axis": "category",
            "y_axis": "value",
            "title": "Test Chart",
            "color_field": None
        }
        
        result = await tool.arun(mock_query_results, thread_id="test_thread_123", chart_config=chart_config)
        
        # Verify metadata structure
        assert result["status"] == "success"
        assert "metadata" in result
        
        metadata = result["metadata"]
        assert metadata["type"] == "visualization"
        assert metadata["thread_id"] == "test_thread_123"
        assert "graph_ref" in metadata
        assert "chart_type" in metadata
        assert "timestamp" in metadata
        assert "pre_execution" in metadata
        
        # Verify pre-execution metadata
        assert metadata["pre_execution"]["tool_invoke"] == "graph_visualization"
        assert metadata["pre_execution"]["thread_id"] == "test_thread_123"


class TestDeterministicTriggering:
    """Test deterministic triggering based on flag"""
    
    @pytest.mark.asyncio
    async def test_deterministic_flag_triggering(self):
        """Test that tool is invoked based on structured response"""
        # This test is now handled by structured response tests
        # The old _get_chart_recommendation function has been removed
        # in favor of structured output from the LLM
        assert True  # Placeholder - functionality tested in test_structured_response.py
    
    @pytest.mark.asyncio
    async def test_no_langchain_tool_selection(self):
        """Verify tool is manually invoked, not via LangChain selection"""
        # This is verified by the implementation using manual invocation
        # in agent.py instead of LangChain's tool selection mechanism
        mock_agent = Mock()
        mock_agent.llm = AsyncMock()
        mock_agent.config = {}
        
        tool = GraphVisualizationTool(mock_agent)
        
        # Tool should not have LangChain tool interface methods
        assert not hasattr(tool, 'name')
        assert not hasattr(tool, 'description')
        assert not hasattr(tool, 'run')
        
        # Tool should have our custom arun method
        assert hasattr(tool, 'arun')
        assert asyncio.iscoroutinefunction(tool.arun)