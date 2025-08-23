"""
Tests for MCP Agent
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.langgraph_agent_mcp.agent import MCPAgent
from src.langgraph_agent_mcp.config import Config
from langchain_core.messages import HumanMessage, AIMessage


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