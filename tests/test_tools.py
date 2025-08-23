"""
Tests for Tool Handler
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, MagicMock
from src.moba_agent.tools import ToolHandler
from src.moba_agent.config import Config


class TestToolHandler:
    """Test Tool Handler class"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        config = Mock()
        config.mcp_server_name = "test_server"
        return config
    
    @pytest.fixture
    def tool_handler(self, mock_config):
        """Create tool handler instance"""
        return ToolHandler(mock_config)
    
    @pytest.fixture
    def mock_mcp_client(self):
        """Create mock MCP client"""
        client = Mock()
        return client
    
    @pytest.fixture
    def mock_tools(self):
        """Create mock tools"""
        tool1 = Mock()
        tool1.name = "add"
        tool1.description = "Add two numbers"
        tool1.__name__ = "add"
        
        tool2 = Mock()
        tool2.name = "multiply"
        tool2.description = "Multiply two numbers"
        tool2.__name__ = "multiply"
        
        return [tool1, tool2]
    
    @pytest.mark.asyncio
    async def test_list_tools(self, tool_handler, mock_mcp_client, mock_tools):
        """Test listing tools"""
        mock_mcp_client.get_tools = AsyncMock(return_value=mock_tools)
        tool_handler.set_client(mock_mcp_client)
        
        tools = await tool_handler.list_tools()
        
        assert len(tools) == 2
        assert tools[0]['name'] == "add"
        assert tools[0]['description'] == "Add two numbers"
        assert tools[1]['name'] == "multiply"
        mock_mcp_client.get_tools.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_tools_no_client(self, tool_handler):
        """Test listing tools without client"""
        tools = await tool_handler.list_tools()
        assert tools == []
    
    @pytest.mark.asyncio
    async def test_list_tools_error(self, tool_handler, mock_mcp_client):
        """Test listing tools with error"""
        mock_mcp_client.get_tools = AsyncMock(side_effect=Exception("Test error"))
        tool_handler.set_client(mock_mcp_client)
        
        tools = await tool_handler.list_tools()
        assert tools == []
    
    @pytest.mark.asyncio
    async def test_list_tools_empty(self, tool_handler, mock_mcp_client):
        """Test listing tools when none available"""
        mock_mcp_client.get_tools = AsyncMock(return_value=None)
        tool_handler.set_client(mock_mcp_client)
        
        tools = await tool_handler.list_tools()
        assert tools == []
    
    def test_format_tool(self, tool_handler):
        """Test formatting a tool"""
        # Test with name attribute
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool description"
        mock_tool.args_schema = Mock()
        mock_tool.args_schema.schema = Mock(return_value={"type": "object"})
        
        formatted = tool_handler._format_tool(mock_tool)
        
        assert formatted['name'] == "test_tool"
        assert formatted['description'] == "Test tool description"
        assert formatted['parameters'] == {"type": "object"}
        assert 'type' in formatted
        
        # Test with __name__ attribute
        mock_tool2 = Mock()
        mock_tool2.__name__ = "function_tool"
        mock_tool2.__doc__ = "Function documentation"
        
        formatted = tool_handler._format_tool(mock_tool2)
        
        assert formatted['name'] == "function_tool"
        assert formatted['description'] == "Function documentation"
    
    def test_format_schema(self, tool_handler):
        """Test formatting schema objects"""
        # Test with Pydantic-like schema
        mock_schema = Mock()
        mock_schema.schema = Mock(return_value={"properties": {"a": "int"}})
        
        formatted = tool_handler._format_schema(mock_schema)
        assert formatted == {"properties": {"a": "int"}}
        
        # Test with dict method
        mock_schema2 = Mock()
        mock_schema2.dict = Mock(return_value={"type": "string"})
        
        formatted = tool_handler._format_schema(mock_schema2)
        assert formatted == {"type": "string"}
        
        # Test with dictionary
        formatted = tool_handler._format_schema({"already": "dict"})
        assert formatted == {"already": "dict"}
        
        # Test with other object
        formatted = tool_handler._format_schema("some string")
        assert formatted == {"description": "some string"}
    
    @pytest.mark.asyncio
    async def test_execute_tool(self, tool_handler, mock_mcp_client):
        """Test executing a tool"""
        # Create callable mock tool
        mock_tool = AsyncMock(return_value={"result": 5})
        mock_tool.name = "add"
        
        mock_mcp_client.get_tools = AsyncMock(return_value=[mock_tool])
        tool_handler.set_client(mock_mcp_client)
        
        result = await tool_handler.execute_tool("add", {"a": 2, "b": 3})
        
        assert result == {"result": 5}
        mock_tool.assert_called_once_with(a=2, b=3)
    
    @pytest.mark.asyncio
    async def test_execute_tool_no_args(self, tool_handler, mock_mcp_client):
        """Test executing a tool without arguments"""
        mock_tool = AsyncMock(return_value={"status": "ok"})
        mock_tool.name = "status"
        
        mock_mcp_client.get_tools = AsyncMock(return_value=[mock_tool])
        tool_handler.set_client(mock_mcp_client)
        
        result = await tool_handler.execute_tool("status", {})
        
        assert result == {"status": "ok"}
        mock_tool.assert_called_once_with()
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, tool_handler, mock_mcp_client):
        """Test executing non-existent tool"""
        mock_mcp_client.get_tools = AsyncMock(return_value=[])
        tool_handler.set_client(mock_mcp_client)
        
        result = await tool_handler.execute_tool("nonexistent", {})
        
        assert "error" in result
        assert "Tool not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_no_client(self, tool_handler):
        """Test executing tool without client"""
        result = await tool_handler.execute_tool("test", {})
        
        assert "error" in result
        assert "MCP client not initialized" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_invoke(self, tool_handler, mock_mcp_client):
        """Test executing tool with ainvoke method"""
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.ainvoke = AsyncMock(return_value={"invoked": True})
        
        mock_mcp_client.get_tools = AsyncMock(return_value=[mock_tool])
        tool_handler.set_client(mock_mcp_client)
        
        result = await tool_handler.execute_tool("test_tool", {"param": "value"})
        
        assert result == {"invoked": True}
        mock_tool.ainvoke.assert_called_once_with({"param": "value"})
    
    @pytest.mark.asyncio
    async def test_get_tool_by_name(self, tool_handler, mock_mcp_client, mock_tools):
        """Test getting tool by name"""
        mock_mcp_client.get_tools = AsyncMock(return_value=mock_tools)
        tool_handler.set_client(mock_mcp_client)
        
        tool = await tool_handler.get_tool_by_name("add")
        
        assert tool is not None
        assert tool.name == "add"
        
        # Test not finding tool
        tool = await tool_handler.get_tool_by_name("nonexistent")
        assert tool is None
    
    @pytest.mark.asyncio
    async def test_get_tool_by_name_no_client(self, tool_handler):
        """Test getting tool by name without client"""
        tool = await tool_handler.get_tool_by_name("test")
        assert tool is None
    
    def test_format_tool_result(self, tool_handler):
        """Test formatting tool results"""
        # Test error result
        result = tool_handler.format_tool_result({"error": "Something went wrong"})
        assert "❌ Error: Something went wrong" in result
        
        # Test dictionary result
        result = tool_handler.format_tool_result({"data": "value"})
        formatted = json.loads(result)
        assert formatted["data"] == "value"
        
        # Test string result
        result = tool_handler.format_tool_result("Simple string")
        assert result == "Simple string"
        
        # Test other types
        result = tool_handler.format_tool_result(42)
        assert result == "42"