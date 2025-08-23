"""
Tests for MCP Agent
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.langgraph_agent_mcp.agent import MCPAgent
from src.langgraph_agent_mcp.config import Config
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class TestMCPAgent:
    """Test MCP Agent class"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_SERVER_URL': 'http://localhost:8000/mcp'
        }):
            return Config()
    
    @pytest.fixture
    def mock_mcp_client(self):
        """Create mock MCP client"""
        client = Mock()
        client.get_tools = AsyncMock(return_value=[])
        return client
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM"""
        llm = Mock()
        llm.invoke = Mock(return_value=AIMessage(content="Test response"))
        llm.ainvoke = AsyncMock(return_value=AIMessage(content="Test response"))
        return llm
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_config):
        """Test agent initialization"""
        agent = MCPAgent(mock_config)
        
        assert agent.config == mock_config
        assert agent.mcp_client is None
        assert agent.llm is None
        assert agent.agent is None
        assert agent.tools == []
        assert agent._initialized == False
    
    @pytest.mark.asyncio
    async def test_agent_initialize(self, mock_config, mock_mcp_client, mock_llm):
        """Test agent initialization process"""
        with patch('src.langgraph_agent_mcp.agent.MultiServerMCPClient', return_value=mock_mcp_client):
            with patch('src.langgraph_agent_mcp.agent.ChatGoogleGenerativeAI', return_value=mock_llm):
                with patch('src.langgraph_agent_mcp.agent.create_react_agent') as mock_create_agent:
                    mock_create_agent.return_value = Mock()
                    
                    agent = MCPAgent(mock_config)
                    await agent.initialize()
                    
                    assert agent._initialized == True
                    assert agent.mcp_client == mock_mcp_client
                    assert agent.llm == mock_llm
                    mock_mcp_client.get_tools.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_initialize_twice(self, mock_config):
        """Test that agent doesn't reinitialize if already initialized"""
        agent = MCPAgent(mock_config)
        agent._initialized = True
        
        with patch.object(agent, '_initialize_mcp_client') as mock_init:
            await agent.initialize()
            mock_init.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_agent_invoke(self, mock_config):
        """Test agent invoke method"""
        agent = MCPAgent(mock_config)
        
        # Mock the agent's compiled graph
        mock_graph = Mock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="Test response")]
        })
        agent.agent = mock_graph
        agent._initialized = True
        
        response = await agent.invoke("Test message")
        
        assert response == "Test response"
        mock_graph.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_invoke_not_initialized(self, mock_config, mock_mcp_client, mock_llm):
        """Test agent invoke initializes if not initialized"""
        with patch('src.langgraph_agent_mcp.agent.MultiServerMCPClient', return_value=mock_mcp_client):
            with patch('src.langgraph_agent_mcp.agent.ChatGoogleGenerativeAI', return_value=mock_llm):
                with patch('src.langgraph_agent_mcp.agent.create_react_agent') as mock_create_agent:
                    mock_graph = Mock()
                    mock_graph.ainvoke = AsyncMock(return_value={
                        "messages": [AIMessage(content="Test response")]
                    })
                    mock_create_agent.return_value = mock_graph
                    
                    agent = MCPAgent(mock_config)
                    response = await agent.invoke("Test message")
                    
                    assert agent._initialized == True
                    assert response == "Test response"
    
    @pytest.mark.asyncio
    async def test_agent_stream(self, mock_config):
        """Test agent stream method"""
        agent = MCPAgent(mock_config)
        
        # Mock the agent's compiled graph
        async def mock_stream(*args, **kwargs):
            yield {"messages": [AIMessage(content="Part 1")]}
            yield {"messages": [AIMessage(content="Part 2")]}
        
        mock_graph = Mock()
        mock_graph.astream = mock_stream
        agent.agent = mock_graph
        agent._initialized = True
        
        chunks = []
        async for chunk in agent.stream("Test message"):
            chunks.append(chunk)
        
        assert len(chunks) == 2
    
    @pytest.mark.asyncio
    async def test_get_available_tools(self, mock_config):
        """Test getting available tools"""
        agent = MCPAgent(mock_config)
        agent._initialized = True
        
        mock_tool_handler = Mock()
        mock_tool_handler.list_tools = AsyncMock(return_value=[
            {"name": "tool1", "description": "Test tool 1"},
            {"name": "tool2", "description": "Test tool 2"}
        ])
        agent.tool_handler = mock_tool_handler
        
        tools = await agent.get_available_tools()
        
        assert len(tools) == 2
        assert tools[0]["name"] == "tool1"
        mock_tool_handler.list_tools.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_available_resources(self, mock_config):
        """Test getting available resources"""
        agent = MCPAgent(mock_config)
        agent._initialized = True
        
        mock_resource_handler = Mock()
        mock_resource_handler.list_resources = AsyncMock(return_value=[
            {"uri": "resource1", "name": "Resource 1"},
            {"uri": "resource2", "name": "Resource 2"}
        ])
        agent.resource_handler = mock_resource_handler
        
        resources = await agent.get_available_resources()
        
        assert len(resources) == 2
        assert resources[0]["uri"] == "resource1"
        mock_resource_handler.list_resources.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_resource(self, mock_config):
        """Test fetching a resource"""
        agent = MCPAgent(mock_config)
        agent._initialized = True
        
        mock_resource_handler = Mock()
        mock_resource_handler.fetch_resource = AsyncMock(return_value={
            "text": "Resource content"
        })
        agent.resource_handler = mock_resource_handler
        
        content = await agent.fetch_resource("test://resource")
        
        assert content["text"] == "Resource content"
        mock_resource_handler.fetch_resource.assert_called_once_with("test://resource")
    
    @pytest.mark.asyncio
    async def test_close(self, mock_config):
        """Test closing the agent"""
        agent = MCPAgent(mock_config)
        agent._initialized = True
        
        await agent.close()
        
        assert agent._initialized == False
    
    @pytest.mark.asyncio
    async def test_create_simple_agent(self, mock_config, mock_llm):
        """Test creating simple agent without tools"""
        agent = MCPAgent(mock_config)
        agent.llm = mock_llm
        
        simple_agent = agent._create_simple_agent()
        
        assert simple_agent is not None
    
    @pytest.mark.asyncio
    async def test_resource_injection_on_first_message(self, mock_config):
        """Test that resources are injected on first message"""
        agent = MCPAgent(mock_config)
        
        # Mock the resource handler to return sample resources with content
        mock_resource_handler = Mock()
        mock_resource_handler.get_all_resources = AsyncMock(return_value=[
            {
                "uri": "resource1", 
                "name": "Test Resource 1", 
                "description": "Test description 1", 
                "mimeType": "text/plain",
                "content": "This is the content of resource 1",
                "fetch_status": "success"
            },
            {
                "uri": "resource2", 
                "name": "Test Resource 2", 
                "description": "Test description 2", 
                "mimeType": "application/json",
                "content": '{"key": "value"}',
                "fetch_status": "success"
            }
        ])
        agent.resource_handler = mock_resource_handler
        
        # Mock the agent's compiled graph
        mock_graph = Mock()
        invoked_messages = None
        
        async def capture_invoke(input_dict, config):
            nonlocal invoked_messages
            invoked_messages = input_dict["messages"]
            return {"messages": [AIMessage(content="Test response")]}
        
        mock_graph.ainvoke = AsyncMock(side_effect=capture_invoke)
        agent.agent = mock_graph
        agent._initialized = True
        
        # First invocation - should inject resources
        response = await agent.invoke("Test message", thread_id="test_thread")
        
        assert response == "Test response"
        assert len(invoked_messages) == 2
        assert isinstance(invoked_messages[0], SystemMessage)
        assert "Available MCP Resources with Content:" in invoked_messages[0].content
        assert "Test Resource 1" in invoked_messages[0].content
        assert "Test Resource 2" in invoked_messages[0].content
        assert isinstance(invoked_messages[1], HumanMessage)
        assert invoked_messages[1].content == "Test message"
        assert "test_thread" in agent._thread_resources_injected
    
    @pytest.mark.asyncio
    async def test_no_resource_injection_on_subsequent_messages(self, mock_config):
        """Test that resources are NOT injected on subsequent messages"""
        agent = MCPAgent(mock_config)
        
        # Mock the resource handler
        mock_resource_handler = Mock()
        mock_resource_handler.get_all_resources = AsyncMock(return_value=[
            {
                "uri": "resource1", 
                "name": "Test Resource 1",
                "content": "Test content",
                "fetch_status": "success"
            }
        ])
        agent.resource_handler = mock_resource_handler
        
        # Mock the agent's compiled graph
        mock_graph = Mock()
        invoked_messages = None
        
        async def capture_invoke(input_dict, config):
            nonlocal invoked_messages
            invoked_messages = input_dict["messages"]
            return {"messages": [AIMessage(content="Test response")]}
        
        mock_graph.ainvoke = AsyncMock(side_effect=capture_invoke)
        agent.agent = mock_graph
        agent._initialized = True
        
        # First invocation - should inject resources
        await agent.invoke("First message", thread_id="test_thread")
        assert len(invoked_messages) == 2
        assert isinstance(invoked_messages[0], SystemMessage)
        
        # Second invocation - should NOT inject resources
        await agent.invoke("Second message", thread_id="test_thread")
        assert len(invoked_messages) == 1
        assert isinstance(invoked_messages[0], HumanMessage)
        assert invoked_messages[0].content == "Second message"
    
    @pytest.mark.asyncio
    async def test_no_resource_injection_when_no_resources(self, mock_config):
        """Test handling when no resources are available"""
        agent = MCPAgent(mock_config)
        
        # Mock the resource handler to return empty list
        mock_resource_handler = Mock()
        mock_resource_handler.get_all_resources = AsyncMock(return_value=[])
        agent.resource_handler = mock_resource_handler
        
        # Mock the agent's compiled graph
        mock_graph = Mock()
        invoked_messages = None
        
        async def capture_invoke(input_dict, config):
            nonlocal invoked_messages
            invoked_messages = input_dict["messages"]
            return {"messages": [AIMessage(content="Test response")]}
        
        mock_graph.ainvoke = AsyncMock(side_effect=capture_invoke)
        agent.agent = mock_graph
        agent._initialized = True
        
        # Invocation - should not inject resources when none available
        response = await agent.invoke("Test message", thread_id="test_thread")
        
        assert response == "Test response"
        assert len(invoked_messages) == 1
        assert isinstance(invoked_messages[0], HumanMessage)
        assert invoked_messages[0].content == "Test message"
        assert "test_thread" in agent._thread_resources_injected
    
    @pytest.mark.asyncio
    async def test_resource_injection_error_handling(self, mock_config):
        """Test error handling when resource fetching fails"""
        agent = MCPAgent(mock_config)
        
        # Mock the resource handler to raise an exception
        mock_resource_handler = Mock()
        mock_resource_handler.get_all_resources = AsyncMock(side_effect=Exception("Failed to fetch resources"))
        agent.resource_handler = mock_resource_handler
        
        # Mock the agent's compiled graph
        mock_graph = Mock()
        invoked_messages = None
        
        async def capture_invoke(input_dict, config):
            nonlocal invoked_messages
            invoked_messages = input_dict["messages"]
            return {"messages": [AIMessage(content="Test response")]}
        
        mock_graph.ainvoke = AsyncMock(side_effect=capture_invoke)
        agent.agent = mock_graph
        agent._initialized = True
        
        # Invocation - should handle error gracefully
        response = await agent.invoke("Test message", thread_id="test_thread")
        
        assert response == "Test response"
        assert len(invoked_messages) == 1
        assert isinstance(invoked_messages[0], HumanMessage)
        assert invoked_messages[0].content == "Test message"
        assert "test_thread" in agent._thread_resources_injected
    
    @pytest.mark.asyncio
    async def test_resource_injection_in_stream(self, mock_config):
        """Test that resources are injected in stream method"""
        agent = MCPAgent(mock_config)
        
        # Mock the resource handler
        mock_resource_handler = Mock()
        mock_resource_handler.get_all_resources = AsyncMock(return_value=[
            {
                "uri": "resource1", 
                "name": "Test Resource 1",
                "content": "Test content",
                "fetch_status": "success"
            }
        ])
        agent.resource_handler = mock_resource_handler
        
        # Mock the agent's compiled graph
        streamed_messages = None
        
        async def capture_stream(input_dict, config):
            nonlocal streamed_messages
            streamed_messages = input_dict["messages"]
            yield {"messages": [AIMessage(content="Part 1")]}
            yield {"messages": [AIMessage(content="Part 2")]}
        
        mock_graph = Mock()
        mock_graph.astream = capture_stream
        agent.agent = mock_graph
        agent._initialized = True
        
        # Stream - should inject resources
        chunks = []
        async for chunk in agent.stream("Test message", thread_id="stream_thread"):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert len(streamed_messages) == 2
        assert isinstance(streamed_messages[0], SystemMessage)
        assert "Available MCP Resources:" in streamed_messages[0].content
        assert isinstance(streamed_messages[1], HumanMessage)
        assert streamed_messages[1].content == "Test message"
        assert "stream_thread" in agent._thread_resources_injected