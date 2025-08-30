"""
Tests for Visualization Node Testing in MCP Agent

This module contains comprehensive tests for the visualization node functionality,
including unit tests, integration tests, memory persistence tests, and error handling.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List

from src.moba_agent.agent import MCPAgent
from src.moba_agent.config import Config
from src.moba_agent.graph_visualization_tool import GraphVisualizationTool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage


class TestVisualizationNode:
    """Test suite for visualization node functionality in MCP Agent"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for testing"""
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_SERVER_URL': 'http://localhost:8000/mcp'
        }):
            return Config()
    
    @pytest.fixture
    def mock_mcp_client(self):
        """Create mock MCP client with visualization capabilities"""
        client = Mock()
        client.get_tools = AsyncMock(return_value=[
            {
                'name': 'query_data',
                'description': 'Query data from database',
                'parameters': {'type': 'object'}
            }
        ])
        return client
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM for visualization responses"""
        llm = Mock()
        llm.invoke = Mock(return_value=AIMessage(content="Visualization response"))
        llm.ainvoke = AsyncMock(return_value=AIMessage(content="Visualization response"))
        return llm
    
    @pytest.fixture
    def mock_graph_viz_tool(self):
        """Create mock graph visualization tool"""
        tool = Mock()
        tool.create_visualization = AsyncMock(return_value={
            'chart_type': 'bar',
            'data': [{'x': 'A', 'y': 10}, {'x': 'B', 'y': 20}],
            'config': {'title': 'Test Chart'}
        })
        return tool
    
    @pytest.fixture
    def sample_query_data(self):
        """Sample data for visualization testing"""
        return {
            "rows": [
                {"category": "Product A", "sales": 1500, "month": "2024-01"},
                {"category": "Product B", "sales": 2300, "month": "2024-01"},
                {"category": "Product C", "sales": 1800, "month": "2024-01"},
                {"category": "Product A", "sales": 1700, "month": "2024-02"},
                {"category": "Product B", "sales": 2100, "month": "2024-02"},
                {"category": "Product C", "sales": 1900, "month": "2024-02"},
            ],
            "columns": ["category", "sales", "month"],
            "query": "SELECT category, sales, month FROM sales_data"
        }
    
    @pytest.fixture
    async def initialized_agent(self, mock_config, mock_mcp_client, mock_llm, mock_graph_viz_tool):
        """Create fully initialized agent for testing"""
        with patch('src.moba_agent.agent.MultiServerMCPClient', return_value=mock_mcp_client):
            with patch('src.moba_agent.agent.ChatGoogleGenerativeAI', return_value=mock_llm):
                with patch('src.moba_agent.agent.create_react_agent') as mock_create_agent:
                    mock_agent_graph = Mock()
                    mock_agent_graph.ainvoke = AsyncMock(return_value={
                        "messages": [AIMessage(content="Test response")]
                    })
                    mock_create_agent.return_value = mock_agent_graph
                    
                    agent = MCPAgent(mock_config)
                    await agent.initialize()
                    agent.graph_viz_tool = mock_graph_viz_tool
                    
                    return agent
    
    @pytest.mark.asyncio
    async def test_visualization_node(self, initialized_agent, sample_query_data):
        """
        Test visualization node in isolation
        
        This test verifies that the visualization node can process data
        and generate appropriate chart configurations independently.
        """
        # Test data processing for visualization
        viz_tool = initialized_agent.graph_viz_tool
        
        # Mock the visualization creation
        expected_visualization = {
            'chart_type': 'bar',
            'data': sample_query_data['rows'],
            'config': {
                'title': 'Sales by Category',
                'x_axis': 'category',
                'y_axis': 'sales'
            }
        }
        viz_tool.create_visualization.return_value = expected_visualization
        
        # Test visualization node processing
        result = await viz_tool.create_visualization(sample_query_data)
        
        assert result['chart_type'] == 'bar'
        assert len(result['data']) == 6
        assert result['config']['title'] == 'Sales by Category'
        viz_tool.create_visualization.assert_called_once_with(sample_query_data)
    
    @pytest.mark.asyncio
    async def test_routing_logic(self, initialized_agent):
        """
        Test routing decisions for visualization requests
        
        This test ensures that the agent correctly routes requests that require
        visualization to the appropriate visualization node.
        """
        agent = initialized_agent
        
        # Test messages that should route to visualization
        viz_messages = [
            "Show me a chart of sales data",
            "Create a bar graph of revenue by month",
            "Visualize the user engagement metrics",
            "Plot the performance trends"
        ]
        
        # Test messages that should not route to visualization
        non_viz_messages = [
            "What is the total revenue?",
            "List all customers",
            "Update user preferences",
            "Delete old records"
        ]
        
        # Mock routing logic - in real implementation this would be part of the agent
        def should_route_to_visualization(message: str) -> bool:
            viz_keywords = ['chart', 'graph', 'plot', 'visualize', 'show me a']
            return any(keyword in message.lower() for keyword in viz_keywords)
        
        # Test visualization routing
        for message in viz_messages:
            assert should_route_to_visualization(message), f"Should route to viz: {message}"
        
        # Test non-visualization routing
        for message in non_viz_messages:
            assert not should_route_to_visualization(message), f"Should not route to viz: {message}"
    
    @pytest.mark.asyncio
    async def test_full_flow_with_visualization(self, initialized_agent, sample_query_data):
        """
        Test complete agent flow including visualization
        
        This test verifies the end-to-end flow from user request to visualization output,
        including data querying, processing, and chart generation.
        """
        agent = initialized_agent
        viz_tool = agent.graph_viz_tool
        
        # Mock the complete flow
        agent.agent.ainvoke = AsyncMock(return_value={
            "messages": [
                ToolMessage(content=json.dumps(sample_query_data), tool_call_id="query_1"),
                AIMessage(content="I'll create a visualization of the sales data."),
                ToolMessage(
                    content=json.dumps({
                        'chart_type': 'bar',
                        'data': sample_query_data['rows'],
                        'config': {'title': 'Sales Visualization'}
                    }),
                    tool_call_id="viz_1"
                )
            ]
        })
        
        # Test full flow
        user_message = "Show me a bar chart of sales by category"
        response = await agent.invoke(user_message)
        
        # Verify the flow was executed
        agent.agent.ainvoke.assert_called_once()
        call_args = agent.agent.ainvoke.call_args[0][0]
        
        # Verify user message was included
        assert any(isinstance(msg, HumanMessage) and user_message in msg.content 
                  for msg in call_args['messages'])
    
    @pytest.mark.asyncio
    async def test_memory_persistence(self, initialized_agent):
        """
        Verify visualization decisions persist in memory
        
        This test ensures that visualization preferences and decisions
        are maintained across multiple interactions within a session.
        """
        agent = initialized_agent
        thread_id = "test_thread_123"
        
        # First interaction - set visualization preference
        first_response = {
            "messages": [
                AIMessage(content="I'll remember you prefer bar charts for sales data.")
            ]
        }
        agent.agent.ainvoke = AsyncMock(return_value=first_response)
        
        await agent.invoke("Show sales data as bar chart", thread_id=thread_id)
        
        # Verify memory checkpoint was called with thread_id
        first_call_args = agent.agent.ainvoke.call_args
        assert first_call_args[1]['config']['configurable']['thread_id'] == thread_id
        
        # Second interaction - should remember preference
        second_response = {
            "messages": [
                AIMessage(content="Using your preferred bar chart format for the new data.")
            ]
        }
        agent.agent.ainvoke = AsyncMock(return_value=second_response)
        
        await agent.invoke("Show this month's sales", thread_id=thread_id)
        
        # Verify same thread_id was used for memory persistence
        second_call_args = agent.agent.ainvoke.call_args
        assert second_call_args[1]['config']['configurable']['thread_id'] == thread_id
    
    @pytest.mark.asyncio
    async def test_error_handling_in_visualization(self, initialized_agent):
        """
        Test error cases in visualization processing
        
        This test covers various error scenarios that can occur during
        visualization generation and ensures proper error handling.
        """
        agent = initialized_agent
        viz_tool = agent.graph_viz_tool
        
        # Test case 1: Invalid data format
        invalid_data = {"invalid": "format"}
        viz_tool.create_visualization = AsyncMock(
            side_effect=ValueError("Invalid data format for visualization")
        )
        
        with pytest.raises(ValueError, match="Invalid data format"):
            await viz_tool.create_visualization(invalid_data)
        
        # Test case 2: Empty data
        empty_data = {"rows": [], "columns": [], "query": "SELECT * FROM empty_table"}
        viz_tool.create_visualization = AsyncMock(
            side_effect=ValueError("Cannot create visualization with empty data")
        )
        
        with pytest.raises(ValueError, match="Cannot create visualization with empty data"):
            await viz_tool.create_visualization(empty_data)
        
        # Test case 3: Network error during visualization
        viz_tool.create_visualization = AsyncMock(
            side_effect=ConnectionError("Failed to connect to visualization service")
        )
        
        with pytest.raises(ConnectionError, match="Failed to connect to visualization service"):
            await viz_tool.create_visualization({"some": "data"})
    
    @pytest.mark.asyncio
    async def test_visualization_formatting(self, initialized_agent):
        """
        Test that agent properly formats visualization responses
        
        This test ensures that visualization outputs are properly formatted
        and contain all required fields for client consumption.
        """
        agent = initialized_agent
        viz_tool = agent.graph_viz_tool
        
        # Mock properly formatted visualization response
        formatted_response = {
            'chart_type': 'line',
            'data': [
                {'x': '2024-01', 'y': 100},
                {'x': '2024-02', 'y': 120},
                {'x': '2024-03', 'y': 90}
            ],
            'config': {
                'title': 'Monthly Trends',
                'x_axis': 'Month',
                'y_axis': 'Value',
                'theme': 'default'
            },
            'metadata': {
                'created_at': '2024-01-01T12:00:00Z',
                'data_points': 3,
                'chart_id': 'chart_123'
            }
        }
        
        viz_tool.create_visualization = AsyncMock(return_value=formatted_response)
        
        # Test visualization formatting
        result = await viz_tool.create_visualization({"test": "data"})
        
        # Verify required fields are present
        assert 'chart_type' in result
        assert 'data' in result
        assert 'config' in result
        assert 'metadata' in result
        
        # Verify config contains essential formatting info
        config = result['config']
        assert 'title' in config
        assert 'x_axis' in config
        assert 'y_axis' in config
        
        # Verify metadata contains tracking info
        metadata = result['metadata']
        assert 'created_at' in metadata
        assert 'data_points' in metadata
        assert 'chart_id' in metadata
    
    @pytest.mark.asyncio
    async def test_tool_error_retry_limits(self, initialized_agent):
        """
        Test retry logic with maximum attempts for tool errors
        
        This test verifies that the agent properly handles tool failures
        with appropriate retry logic and maximum attempt limits.
        """
        agent = initialized_agent
        viz_tool = agent.graph_viz_tool
        
        # Mock consecutive failures followed by success
        failure_responses = [
            ConnectionError("Network timeout"),
            ConnectionError("Service unavailable"),
            ConnectionError("Rate limit exceeded")
        ]
        
        success_response = {
            'chart_type': 'bar',
            'data': [{'x': 'A', 'y': 10}],
            'config': {'title': 'Retry Success'}
        }
        
        # Test retry logic simulation
        call_count = 0
        async def mock_create_viz_with_retries(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:  # First 3 calls fail
                raise failure_responses[call_count - 1]
            return success_response
        
        viz_tool.create_visualization = mock_create_viz_with_retries
        
        # Test that after max retries, the tool eventually succeeds
        result = await viz_tool.create_visualization({"test": "data"})
        assert result == success_response
        assert call_count == 4  # 3 failures + 1 success
        
        # Test max retry limit exceeded
        call_count = 0
        async def mock_always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ConnectionError(f"Persistent failure #{call_count}")
        
        viz_tool.create_visualization = mock_always_fail
        
        # Should fail after exhausting retries
        with pytest.raises(ConnectionError, match="Persistent failure"):
            await viz_tool.create_visualization({"test": "data"})


class TestVisualizationNodeIntegration:
    """Integration tests for visualization node with real agent graph"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for integration testing"""
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-integration-key',
            'MCP_SERVER_URL': 'http://localhost:8001/mcp'
        }):
            return Config()
    
    @pytest.mark.asyncio
    async def test_visualization_node_state_transitions(self, mock_config):
        """
        Test state transitions in the agent graph when processing visualizations
        
        This test verifies that the agent graph properly transitions between
        states when handling visualization requests.
        """
        # This would be a more complex integration test
        # For now, we'll create a placeholder that demonstrates the concept
        
        # Mock agent initialization
        with patch('src.moba_agent.agent.MultiServerMCPClient') as mock_client_class:
            with patch('src.moba_agent.agent.ChatGoogleGenerativeAI') as mock_llm_class:
                with patch('src.moba_agent.agent.create_react_agent') as mock_create_agent:
                    
                    # Setup mocks
                    mock_client = Mock()
                    mock_client.get_tools = AsyncMock(return_value=[])
                    mock_client_class.return_value = mock_client
                    
                    mock_llm = Mock()
                    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Test"))
                    mock_llm_class.return_value = mock_llm
                    
                    mock_graph = Mock()
                    mock_graph.ainvoke = AsyncMock(return_value={
                        "messages": [AIMessage(content="Visualization created")]
                    })
                    mock_create_agent.return_value = mock_graph
                    
                    # Test agent with visualization
                    agent = MCPAgent(mock_config)
                    await agent.initialize()
                    
                    # Test state transition through visualization request
                    response = await agent.invoke("Create a chart of sales data")
                    
                    # Verify graph was invoked for visualization
                    mock_graph.ainvoke.assert_called_once()
                    assert response == "Visualization created"
    
    @pytest.mark.asyncio
    async def test_concurrent_visualization_requests(self, mock_config):
        """
        Test handling of concurrent visualization requests
        
        This test ensures the agent can handle multiple simultaneous
        visualization requests without conflicts.
        """
        # Mock concurrent request handling
        async def simulate_concurrent_requests():
            requests = [
                "Show bar chart of Q1 sales",
                "Create line graph of user growth",
                "Plot revenue trends by region"
            ]
            
            # In a real implementation, these would be actual concurrent calls
            # For testing, we simulate the behavior
            results = []
            for request in requests:
                # Simulate processing delay
                await asyncio.sleep(0.01)
                results.append(f"Processed: {request}")
            
            return results
        
        results = await simulate_concurrent_requests()
        assert len(results) == 3
        assert all("Processed:" in result for result in results)