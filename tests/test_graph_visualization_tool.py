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
        assert tool.memory == []
        assert tool.config == {}
    
    def test_add_to_memory(self, tool):
        """Test memory addition functionality"""
        entry = {
            "role": "assistant",
            "content": "Test content",
            "metadata": {"type": "test"}
        }
        
        tool.add_to_memory(entry)
        
        assert len(tool.memory) == 1
        assert tool.memory[0] == entry
    
    @pytest.mark.asyncio
    async def test_arun_success(self, tool, mock_query_results, mock_agent):
        """Test successful graph generation"""
        # Mock LLM response
        mock_llm_response = AIMessage(content=json.dumps({
            "chart_type": "bar",
            "reasoning": "Bar chart is suitable for categorical comparison",
            "config": {
                "x_axis": "category",
                "y_axis": "value",
                "title": "Sales by Category",
                "color_field": None
            }
        }))
        mock_agent.llm.ainvoke.return_value = mock_llm_response
        
        # Run the tool
        result = await tool.arun(mock_query_results)
        
        # Verify result structure
        assert result["status"] == "success"
        assert "graph_id" in result
        assert "graph_data" in result
        assert "explanation" in result
        assert result["chart_type"] == "bar"
        
        # Verify memory was updated
        assert len(tool.memory) == 2  # Pre and post execution
        assert tool.memory[0]["role"] == "assistant"
        assert tool.memory[0]["metadata"]["tool_invoke"] == "graph_visualization"
        assert tool.memory[1]["role"] == "tool"
        assert tool.memory[1]["metadata"]["type"] == "visualization"
    
    @pytest.mark.asyncio
    async def test_arun_with_string_input(self, tool, mock_query_results, mock_agent):
        """Test handling of string input for query results"""
        # Mock LLM response
        mock_llm_response = AIMessage(content=json.dumps({
            "chart_type": "line",
            "reasoning": "Line chart for time series",
            "config": {
                "x_axis": "date",
                "y_axis": "value",
                "title": "Values over Time",
                "color_field": None
            }
        }))
        mock_agent.llm.ainvoke.return_value = mock_llm_response
        
        # Pass query results as string
        result = await tool.arun(json.dumps(mock_query_results))
        
        assert result["status"] == "success"
        assert result["chart_type"] == "line"
    
    @pytest.mark.asyncio
    async def test_arun_error_handling(self, tool, mock_agent):
        """Test graceful error handling"""
        # Make LLM raise an exception
        mock_agent.llm.ainvoke.side_effect = Exception("LLM error")
        
        result = await tool.arun({"rows": [], "columns": []})
        
        # Verify error response
        assert result["status"] == "error"
        assert "Error occurred while creating graph" in result["explanation"]
        assert "error" in result
        
        # Verify error was logged to memory
        assert len(tool.memory) == 2
        assert tool.memory[1]["metadata"]["type"] == "viz_error"
    
    @pytest.mark.asyncio
    async def test_arun_invalid_json_response(self, tool, mock_query_results, mock_agent):
        """Test handling of invalid JSON in LLM response"""
        # Mock LLM response with invalid JSON
        mock_llm_response = AIMessage(content="This is not valid JSON")
        mock_agent.llm.ainvoke.return_value = mock_llm_response
        
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
            
            result = await tool.arun(mock_query_results)
            
            # Should still succeed with fallback
            assert result["status"] == "success"
            assert result["chart_type"] == "bar"
    
    @pytest.mark.asyncio
    async def test_arun_with_context(self, tool, mock_query_results, mock_agent):
        """Test passing context to the tool"""
        mock_llm_response = AIMessage(content=json.dumps({
            "chart_type": "pie",
            "reasoning": "Pie chart for distribution",
            "config": {
                "x_axis": "category",
                "y_axis": "value",
                "title": "Distribution",
                "color_field": None
            }
        }))
        mock_agent.llm.ainvoke.return_value = mock_llm_response
        
        context = [
            {"role": "user", "content": "Show me a pie chart"},
            {"role": "assistant", "content": "Creating visualization"}
        ]
        
        result = await tool.arun(mock_query_results, context=context)
        
        assert result["status"] == "success"
        assert result["chart_type"] == "pie"
    
    def test_memory_entry_structure(self, tool):
        """Test memory entry structure follows expected format"""
        # Pre-invocation marker
        pre_entry = {
            "role": "assistant",
            "content": "Generating visualization...",
            "metadata": {
                "tool_invoke": "graph_visualization",
                "timestamp": datetime.now().isoformat()
            }
        }
        tool.add_to_memory(pre_entry)
        
        # Post-success entry
        post_entry = {
            "role": "tool",
            "content": "Graph shows 5 entities with 8 relationships...",
            "metadata": {
                "type": "visualization",
                "graph_ref": "graph_12345",
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        }
        tool.add_to_memory(post_entry)
        
        assert len(tool.memory) == 2
        assert tool.memory[0]["metadata"]["tool_invoke"] == "graph_visualization"
        assert tool.memory[1]["metadata"]["type"] == "visualization"
        assert tool.memory[1]["metadata"]["graph_ref"] == "graph_12345"


class TestDeterministicTriggering:
    """Test deterministic triggering based on flag"""
    
    @pytest.mark.asyncio
    async def test_deterministic_flag_triggering(self):
        """Test that tool is invoked based on deterministic flag"""
        from src.moba_agent.graph_visualization import _get_chart_recommendation
        
        # Test with should_visualize=True
        result_true = await _get_chart_recommendation("test prompt", True, None)
        assert result_true["visualization_needed"] == True
        assert result_true["chart_type"] == "pending"
        assert "prompt" in result_true
        
        # Test with should_visualize=False
        result_false = await _get_chart_recommendation("test prompt", False, None)
        assert result_false["visualization_needed"] == False
        assert result_false["chart_type"] == "pending"
        assert "prompt" in result_false
    
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