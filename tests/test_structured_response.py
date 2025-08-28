"""
Tests for structured LLM response functionality.

This module tests the new structured output implementation that replaces
text-based parsing with type-safe structured responses.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any

from src.moba_agent.schemas import (
    StructuredAgentResponse,
    ChartConfig,
    ChartType,
    QueryMetadata
)
from src.moba_agent.agent import MCPAgent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class TestStructuredResponse:
    """Test structured response schema and functionality."""
    
    def test_chart_config_model(self):
        """Test ChartConfig Pydantic model."""
        config = ChartConfig(
            chart_type=ChartType.BAR,
            title="Sales by Region",
            x_axis="region",
            y_axis="sales_amount",
            group_by="product_category"
        )
        
        assert config.chart_type == ChartType.BAR
        assert config.title == "Sales by Region"
        assert config.x_axis == "region"
        assert config.y_axis == "sales_amount"
        assert config.group_by == "product_category"
        
        # Test serialization
        config_dict = config.model_dump()
        assert config_dict["chart_type"] == "bar"
        assert "title" in config_dict
    
    def test_structured_agent_response_model(self):
        """Test StructuredAgentResponse model."""
        response = StructuredAgentResponse(
            content="Here are the top 10 products by revenue.",
            should_visualize=True,
            chart_config=ChartConfig(
                chart_type=ChartType.BAR,
                title="Top 10 Products",
                x_axis="product_name",
                y_axis="revenue"
            ),
            query_metadata=QueryMetadata(
                query_executed=True,
                query_type="SELECT",
                rows_affected=10,
                columns=["product_name", "revenue"]
            ),
            reasoning="Bar chart is best for categorical comparisons"
        )
        
        assert response.should_visualize is True
        assert response.chart_config is not None
        assert response.chart_config.chart_type == ChartType.BAR
        assert response.query_metadata.rows_affected == 10
    
    def test_response_model_with_no_visualization(self):
        """Test response when visualization is not needed."""
        response = StructuredAgentResponse(
            content="Database connection successful.",
            should_visualize=False,
            chart_config=None,
            query_metadata=None,
            reasoning="No data to visualize"
        )
        
        assert response.should_visualize is False
        assert response.chart_config is None
        assert response.query_metadata is None


class TestMCPAgentStructuredOutput:
    """Test MCPAgent with structured output integration."""
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock MCPAgent instance."""
        with patch('src.moba_agent.agent.MultiServerMCPClient'):
            agent = MCPAgent()
            agent.llm = Mock()
            agent.llm_structured = AsyncMock()
            agent.agent = Mock()
            agent._initialized = True
            agent.graph_viz_tool = Mock()
            return agent
    
    @pytest.mark.asyncio
    async def test_get_structured_response_with_visualization(self, mock_agent):
        """Test _get_structured_response when visualization is needed."""
        # Mock query result
        query_result = {
            "data": [
                {"product": "A", "sales": 100},
                {"product": "B", "sales": 150},
                {"product": "C", "sales": 200}
            ]
        }
        
        # Mock structured response
        expected_response = StructuredAgentResponse(
            content="Top products by sales",
            should_visualize=True,
            chart_config=ChartConfig(
                chart_type=ChartType.BAR,
                title="Product Sales",
                x_axis="product",
                y_axis="sales"
            ),
            reasoning="Bar chart for categorical comparison"
        )
        
        mock_agent.llm_structured.ainvoke.return_value = expected_response
        
        # Test
        messages = [HumanMessage(content="Show me product sales")]
        result = await mock_agent._get_structured_response(messages, query_result)
        
        assert result.should_visualize is True
        assert result.chart_config.chart_type == ChartType.BAR
        assert result.chart_config.x_axis == "product"
        assert result.chart_config.y_axis == "sales"
        
        # Verify LLM was called with enhanced messages
        mock_agent.llm_structured.ainvoke.assert_called_once()
        called_messages = mock_agent.llm_structured.ainvoke.call_args[0][0]
        assert len(called_messages) >= 2  # System prompt + user message
        assert isinstance(called_messages[0], SystemMessage)
    
    @pytest.mark.asyncio
    async def test_get_structured_response_no_visualization(self, mock_agent):
        """Test _get_structured_response when visualization is not needed."""
        query_result = {
            "data": [{"status": "success"}]
        }
        
        expected_response = StructuredAgentResponse(
            content="Operation completed successfully",
            should_visualize=False,
            chart_config=None,
            reasoning="Single status message, no data to visualize"
        )
        
        mock_agent.llm_structured.ainvoke.return_value = expected_response
        
        messages = [HumanMessage(content="Check database status")]
        result = await mock_agent._get_structured_response(messages, query_result)
        
        assert result.should_visualize is False
        assert result.chart_config is None
    
    @pytest.mark.asyncio
    async def test_get_structured_response_error_handling(self, mock_agent):
        """Test error handling in _get_structured_response."""
        mock_agent.llm_structured.ainvoke.side_effect = Exception("LLM error")
        
        messages = [HumanMessage(content="Test message")]
        result = await mock_agent._get_structured_response(messages, None)
        
        # Should return default response on error
        assert result.should_visualize is False
        assert result.chart_config is None
        assert "Error" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_handle_visualization_with_config(self, mock_agent):
        """Test _handle_visualization_with_config method."""
        query_result = {
            "data": [{"x": 1, "y": 10}, {"x": 2, "y": 20}]
        }
        
        chart_config = {
            "chart_type": "line",
            "title": "Test Chart",
            "x_axis": "x",
            "y_axis": "y"
        }
        
        # Mock graph visualization tool response
        mock_agent.graph_viz_tool.arun = AsyncMock(return_value={
            "status": "success",
            "chart_type": "line",
            "graph_data": {"type": "line", "data": []}
        })
        
        result = await mock_agent._handle_visualization_with_config(
            query_result,
            chart_config,
            [],
            "test_thread"
        )
        
        assert result is not None
        assert result["type"] == "line"
        
        # Verify tool was called with correct parameters
        mock_agent.graph_viz_tool.arun.assert_called_once_with(
            query_results=query_result,
            context=[],
            thread_id="test_thread",
            chart_config=chart_config
        )
    
    @pytest.mark.asyncio
    async def test_invoke_with_query_tracking_structured(self, mock_agent):
        """Test full invoke_with_query_tracking with structured output."""
        # Setup mocks
        mock_agent._prepare_messages_for_thread = AsyncMock(
            return_value=[HumanMessage(content="Show sales data")]
        )
        
        mock_agent.agent.ainvoke = AsyncMock(return_value={
            "messages": [
                HumanMessage(content="Show sales data"),
                AIMessage(content="Here's the sales data")
            ]
        })
        
        mock_agent._process_agent_response_messages = Mock(
            return_value=("Here's the sales data", [], [])
        )
        
        mock_agent._extract_query_results = Mock(return_value={
            "data": [{"product": "A", "sales": 100}]
        })
        
        # Mock structured response
        structured_resp = StructuredAgentResponse(
            content="Sales data",
            should_visualize=True,
            chart_config=ChartConfig(
                chart_type=ChartType.BAR,
                title="Sales",
                x_axis="product",
                y_axis="sales"
            )
        )
        
        mock_agent._get_structured_response = AsyncMock(
            return_value=structured_resp
        )
        
        mock_agent._handle_visualization_with_config = AsyncMock(
            return_value={"type": "bar", "data": []}
        )
        
        # Execute
        result = await mock_agent.invoke_with_query_tracking(
            "Show sales data",
            "test_thread"
        )
        
        # Verify
        assert result["response"] == "Here's the sales data"
        assert result["query_result"] is not None
        assert result["graph"] is not None
        assert result["graph"]["type"] == "bar"
        
        # Verify structured response was used
        mock_agent._get_structured_response.assert_called_once()
        mock_agent._handle_visualization_with_config.assert_called_once()


class TestGraphVisualizationIntegration:
    """Test integration with graph visualization module."""
    
    @pytest.mark.asyncio
    async def test_analyze_and_generate_graph_with_config(self):
        """Test analyze_and_generate_graph with structured config."""
        from src.moba_agent.graph_visualization import analyze_and_generate_graph
        
        query_result = {
            "rows": [
                {"category": "A", "value": 10},
                {"category": "B", "value": 20},
                {"category": "C", "value": 30}
            ],
            "columns": ["category", "value"]
        }
        
        chart_config = {
            "chart_type": "bar",
            "title": "Category Values",
            "x_axis": "category",
            "y_axis": "value"
        }
        
        with patch('src.moba_agent.graph_visualization.transform_to_chart_data') as mock_transform:
            mock_transform.return_value = {
                "type": "bar",
                "data": {"labels": ["A", "B", "C"], "values": [10, 20, 30]}
            }
            
            with patch('src.moba_agent.graph_visualization.validate_graph_data') as mock_validate:
                mock_validate.return_value = True
                
                result = await analyze_and_generate_graph(
                    query_result,
                    chart_config=chart_config
                )
                
                assert result is not None
                assert result["type"] == "bar"
                assert "data" in result
                
                # Verify transform was called with config
                mock_transform.assert_called_once()
                call_args = mock_transform.call_args[0]
                assert call_args[2] == "bar"  # chart_type
                assert call_args[3]["x_axis"] == "category"
                assert call_args[3]["y_axis"] == "value"
    
    @pytest.mark.asyncio
    async def test_analyze_and_generate_graph_fallback(self):
        """Test fallback when no config provided."""
        from src.moba_agent.graph_visualization import analyze_and_generate_graph
        
        query_result = {
            "rows": [
                {"date": "2024-01-01", "value": 10},
                {"date": "2024-01-02", "value": 20}
            ],
            "columns": ["date", "value"]
        }
        
        with patch('src.moba_agent.graph_visualization._get_fallback_recommendation') as mock_fallback:
            mock_fallback.return_value = {
                "chart_type": "line",
                "config": {
                    "x_axis": "date",
                    "y_axis": "value",
                    "title": "Time Series Data",
                    "color_field": None
                }
            }
            
            with patch('src.moba_agent.graph_visualization.transform_to_chart_data') as mock_transform:
                mock_transform.return_value = {"type": "line", "data": {}}
                
                with patch('src.moba_agent.graph_visualization.validate_graph_data') as mock_validate:
                    mock_validate.return_value = True
                    
                    result = await analyze_and_generate_graph(
                        query_result,
                        chart_config=None  # No config provided
                    )
                    
                    assert result is not None
                    mock_fallback.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])