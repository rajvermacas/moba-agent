"""
Integration tests for Graph Visualization with Agent Framework
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.moba_agent.agent import MCPAgent
from src.moba_agent.graph_visualization_tool import GraphVisualizationTool
from src.moba_agent.config import Config


class TestGraphVisualizationIntegration:
    """Integration tests for full graph visualization flow"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        config = Mock(spec=Config)
        config.agent_model = "gemini-2.5-flash"
        config.get_gemini_config = Mock(return_value={
            "model": "gemini-2.5-flash",
            "temperature": 0.1
        })
        config.get_mcp_server_config = Mock(return_value={})
        config.mcp_servers = []
        return config
    
    @pytest.fixture
    def mock_query_result(self):
        """Sample query result that needs visualization"""
        return {
            "rows": [
                {"month": "Jan", "sales": 1000, "region": "North"},
                {"month": "Feb", "sales": 1200, "region": "North"},
                {"month": "Mar", "sales": 1100, "region": "North"},
                {"month": "Jan", "sales": 800, "region": "South"},
                {"month": "Feb", "sales": 900, "region": "South"},
                {"month": "Mar", "sales": 950, "region": "South"},
            ],
            "columns": ["month", "sales", "region"],
            "query": "SELECT month, sales, region FROM monthly_sales"
        }
    
    @pytest.mark.asyncio
    async def test_full_flow_with_visualization(self, mock_config, mock_query_result):
        """Test complete flow: user query → execute_query → tool → response"""
        
        # Create agent with mocked components
        agent = MCPAgent(config=mock_config)
        
        # Mock MCP client and tools
        with patch.object(agent, '_initialize_mcp_client', new_callable=AsyncMock):
            with patch.object(agent, '_load_tools', new_callable=AsyncMock):
                # Mock LLM
                mock_llm = AsyncMock()
                mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=json.dumps({
                    "chart_type": "line",
                    "reasoning": "Line chart shows trends over time",
                    "config": {
                        "x_axis": "month",
                        "y_axis": "sales",
                        "title": "Monthly Sales Trend",
                        "color_field": "region"
                    }
                })))
                
                with patch.object(agent, '_initialize_llm'):
                    agent.llm = mock_llm
                    
                    # Mock agent creation
                    mock_agent_instance = AsyncMock()
                    mock_agent_instance.ainvoke = AsyncMock(return_value={
                        "messages": [
                            HumanMessage(content="Show me monthly sales"),
                            AIMessage(content="Executing query..."),
                            ToolMessage(
                                content=json.dumps(mock_query_result),
                                name="execute_query_sales",
                                tool_call_id="call_execute_query_sales"
                            ),
                            AIMessage(content="Here are the monthly sales results. [VISUALIZE=TRUE] The chart shows clear trends in the data.")
                        ]
                    })
                    
                    with patch.object(agent, '_create_agent', new_callable=AsyncMock):
                        agent.agent = mock_agent_instance
                        
                        # Initialize agent
                        await agent.initialize()
                        
                        # Verify GraphVisualizationTool was created
                        assert agent.graph_viz_tool is not None
                        assert isinstance(agent.graph_viz_tool, GraphVisualizationTool)
                        
                        # Test query with visualization
                        result = await agent.invoke_with_query_tracking(
                            "Show me monthly sales",
                            thread_id="test_thread"
                        )
                        
                        # Verify response structure
                        assert "response" in result
                        assert "query_result" in result
                        assert result["query_result"] == mock_query_result
                        
                        # Verify graph was generated via tool
                        if "graph" in result and result["graph"]:
                            assert "data" in result["graph"]
                            assert "chart_type" in result["graph"]
                            assert result["graph"]["chart_type"] == "line"
                        
                        # Verify context maintained throughout
                        assert agent.llm.ainvoke.called
    
    @pytest.mark.asyncio
    async def test_multiple_visualizations(self, mock_config):
        """Test multiple queries requiring graphs with memory tracking"""
        
        agent = MCPAgent(config=mock_config)
        
        # Create mock components
        with patch.object(agent, '_initialize_mcp_client', new_callable=AsyncMock):
            with patch.object(agent, '_load_tools', new_callable=AsyncMock):
                with patch.object(agent, '_initialize_llm'):
                    with patch.object(agent, '_create_agent', new_callable=AsyncMock):
                        agent.llm = AsyncMock()
                        agent.agent = AsyncMock()
                        
                        await agent.initialize()
                        
                        # Create tool and track memory
                        tool = agent.graph_viz_tool
                        
                        # First visualization
                        query_result1 = {
                            "rows": [{"x": 1, "y": 10}],
                            "columns": ["x", "y"]
                        }
                        
                        agent.llm.ainvoke.return_value = AIMessage(content=json.dumps({
                            "chart_type": "scatter",
                            "reasoning": "Scatter plot for correlation",
                            "config": {"x_axis": "x", "y_axis": "y", "title": "Test 1", "color_field": None}
                        }))
                        
                        result1 = await tool.arun(query_result1)
                        assert result1["status"] == "success"
                        
                        # Second visualization
                        query_result2 = {
                            "rows": [{"category": "A", "count": 5}],
                            "columns": ["category", "count"]
                        }
                        
                        agent.llm.ainvoke.return_value = AIMessage(content=json.dumps({
                            "chart_type": "pie",
                            "reasoning": "Pie chart for distribution",
                            "config": {"x_axis": "category", "y_axis": "count", "title": "Test 2", "color_field": None}
                        }))
                        
                        result2 = await tool.arun(query_result2)
                        assert result2["status"] == "success"
                        
                        # Verify memory contains all references
                        assert len(tool.memory) >= 4  # At least 2 pre + 2 post markers
                        
                        # Verify no context loss between calls
                        viz_entries = [m for m in tool.memory if m.get("metadata", {}).get("type") == "visualization"]
                        assert len(viz_entries) == 2
                        assert all("graph_ref" in entry["metadata"] for entry in viz_entries)
    
    @pytest.mark.asyncio
    async def test_error_resilience(self, mock_config):
        """Test that visualization failures don't break conversation flow"""
        
        agent = MCPAgent(config=mock_config)
        
        with patch.object(agent, '_initialize_mcp_client', new_callable=AsyncMock):
            with patch.object(agent, '_load_tools', new_callable=AsyncMock):
                with patch.object(agent, '_initialize_llm'):
                    with patch.object(agent, '_create_agent', new_callable=AsyncMock):
                        # Create agent with failing LLM
                        agent.llm = AsyncMock()
                        agent.llm.ainvoke.side_effect = Exception("LLM failure")
                        
                        mock_agent_response = {
                            "messages": [
                                HumanMessage(content="Show data"),
                                ToolMessage(
                                    content=json.dumps({"rows": [{"a": 1}], "columns": ["a"]}),
                                    name="execute_query_test",
                                    tool_call_id="call_123"
                                ),
                                AIMessage(content="Here is your data")
                            ]
                        }
                        agent.agent = AsyncMock()
                        agent.agent.ainvoke.return_value = mock_agent_response
                        
                        await agent.initialize()
                        
                        # Query should succeed even if visualization fails
                        result = await agent.invoke_with_query_tracking(
                            "Show data",
                            thread_id="error_test"
                        )
                        
                        # Conversation should continue
                        assert result["response"] == "Here is your data"
                        assert result["query_result"] is not None
                        # Graph should be None or error state
                        assert result.get("graph") is None or result["graph"].get("status") == "error"
    
    @pytest.mark.asyncio 
    async def test_deterministic_triggering(self, mock_config):
        """Test that visualization is triggered deterministically by flag"""
        from src.moba_agent.graph_visualization import analyze_and_generate_graph
        
        # Mock query result
        query_result = {
            "rows": [{"a": 1, "b": 2}],
            "columns": ["a", "b"],
            "query": "SELECT a, b FROM test"
        }
        
        # Call analyze_and_generate_graph
        with patch('src.moba_agent.graph_visualization.is_suitable_for_visualization', return_value=True):
            with patch('src.moba_agent.graph_visualization.analyze_data_characteristics', return_value={
                "row_count": 1,
                "numeric_columns": ["a", "b"],
                "categorical_columns": [],
                "date_columns": [],
                "unique_counts": {}
            }):
                result = await analyze_and_generate_graph(query_result, llm=None)
                
                # Should return metadata with visualization_needed flag
                assert result is not None
                assert result["visualization_needed"] == True
                assert "prompt" in result
                assert result["query_results"] == query_result
    
    @pytest.mark.asyncio
    async def test_no_langchain_tool_selection(self, mock_config):
        """Verify manual invocation instead of LangChain tool selection"""
        
        agent = MCPAgent(config=mock_config)
        
        with patch.object(agent, '_initialize_mcp_client', new_callable=AsyncMock):
            with patch.object(agent, '_load_tools', new_callable=AsyncMock) as mock_load:
                # Verify GraphVisualizationTool is NOT in the tools list
                mock_load.return_value = []  # No tools from MCP
                
                with patch.object(agent, '_initialize_llm'):
                    with patch.object(agent, '_create_agent', new_callable=AsyncMock):
                        agent.llm = AsyncMock()
                        agent.agent = AsyncMock()
                        
                        await agent.initialize()
                        
                        # GraphVisualizationTool should be created separately
                        assert agent.graph_viz_tool is not None
                        
                        # It should NOT be in the agent's tools list
                        assert agent.graph_viz_tool not in agent.tools
                        
                        # Tool is invoked manually in query_with_result_tracking
                        # not through LangChain's tool selection
                        assert hasattr(agent, 'graph_viz_tool')
                        assert callable(agent.graph_viz_tool.arun)


class TestMemoryManagement:
    """Test memory management and context preservation"""
    
    @pytest.mark.asyncio
    async def test_memory_updates_tracked(self):
        """Test that all visualization events are tracked in memory"""
        mock_agent = Mock()
        mock_agent.llm = AsyncMock()
        mock_agent.config = {}
        
        tool = GraphVisualizationTool(mock_agent)
        
        # Mock successful LLM response
        mock_agent.llm.ainvoke.return_value = AIMessage(content=json.dumps({
            "chart_type": "bar",
            "reasoning": "Test reasoning",
            "config": {"x_axis": "x", "y_axis": "y", "title": "Test", "color_field": None}
        }))
        
        query_result = {
            "rows": [{"x": "A", "y": 10}],
            "columns": ["x", "y"]
        }
        
        await tool.arun(query_result)
        
        # Check memory entries
        assert len(tool.memory) >= 2
        
        # Pre-invocation marker
        pre_marker = tool.memory[0]
        assert pre_marker["role"] == "assistant"
        assert pre_marker["metadata"]["tool_invoke"] == "graph_visualization"
        
        # Post-execution entry
        post_entry = tool.memory[1]
        assert post_entry["role"] == "tool"
        assert post_entry["metadata"]["type"] == "visualization"
        assert "graph_ref" in post_entry["metadata"]
        assert "timestamp" in post_entry["metadata"]
    
    @pytest.mark.asyncio
    async def test_error_logged_to_memory(self):
        """Test that errors are properly logged to memory"""
        mock_agent = Mock()
        mock_agent.llm = AsyncMock()
        mock_agent.config = {}
        
        tool = GraphVisualizationTool(mock_agent)
        
        # Make LLM fail
        mock_agent.llm.ainvoke.side_effect = ValueError("Test error")
        
        result = await tool.arun({"rows": [], "columns": []})
        
        # Check error in result
        assert result["status"] == "error"
        
        # Check error logged to memory
        error_entries = [m for m in tool.memory if m.get("metadata", {}).get("type") == "viz_error"]
        assert len(error_entries) == 1
        assert "Test error" in error_entries[0]["metadata"]["error"]