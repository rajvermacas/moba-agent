"""
Tests for Resource Handler
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from src.langgraph_agent_mcp.resources import ResourceHandler
from src.langgraph_agent_mcp.config import Config


class TestResourceHandler:
    """Test Resource Handler class"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        config = Mock()
        config.mcp_server_name = "test_server"
        return config
    
    @pytest.fixture
    def resource_handler(self, mock_config):
        """Create resource handler instance"""
        return ResourceHandler(mock_config)
    
    @pytest.fixture
    def mock_mcp_client(self):
        """Create mock MCP client"""
        client = Mock()
        return client
    
    @pytest.fixture
    def mock_session(self):
        """Create mock session"""
        session = AsyncMock()
        return session
    
    @pytest.mark.asyncio
    async def test_list_resources(self, resource_handler, mock_mcp_client, mock_session):
        """Test listing resources"""
        # Setup mock resources
        mock_resource1 = Mock()
        mock_resource1.uri = "resource://test1"
        mock_resource1.name = "Test Resource 1"
        mock_resource1.description = "Description 1"
        
        mock_resource2 = Mock()
        mock_resource2.uri = "resource://test2"
        mock_resource2.name = "Test Resource 2"
        
        mock_response = Mock()
        mock_response.resources = [mock_resource1, mock_resource2]
        
        mock_session.list_resources = AsyncMock(return_value=mock_response)
        mock_mcp_client.session = AsyncMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        resource_handler.set_client(mock_mcp_client)
        
        # Test
        resources = await resource_handler.list_resources()
        
        assert len(resources) == 2
        assert resources[0]['uri'] == "resource://test1"
        assert resources[0]['name'] == "Test Resource 1"
        assert resources[1]['uri'] == "resource://test2"
    
    @pytest.mark.asyncio
    async def test_list_resources_no_client(self, resource_handler):
        """Test listing resources without client"""
        resources = await resource_handler.list_resources()
        assert resources == []
    
    @pytest.mark.asyncio
    async def test_list_resources_error(self, resource_handler, mock_mcp_client, mock_session):
        """Test listing resources with error"""
        mock_session.list_resources = AsyncMock(side_effect=Exception("Test error"))
        mock_mcp_client.session = AsyncMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        resource_handler.set_client(mock_mcp_client)
        
        resources = await resource_handler.list_resources()
        assert resources == []
    
    @pytest.mark.asyncio
    async def test_fetch_resource(self, resource_handler, mock_mcp_client, mock_session):
        """Test fetching a resource"""
        # Setup mock response
        mock_content = Mock()
        mock_content.text = "Resource content text"
        
        mock_response = Mock()
        mock_response.contents = [mock_content]
        
        mock_session.read_resource = AsyncMock(return_value=mock_response)
        mock_mcp_client.session = AsyncMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        resource_handler.set_client(mock_mcp_client)
        
        # Test
        content = await resource_handler.fetch_resource("resource://test")
        
        assert isinstance(content, list)
        assert len(content) == 1
        assert content[0]['text'] == "Resource content text"
    
    @pytest.mark.asyncio
    async def test_fetch_resource_no_client(self, resource_handler):
        """Test fetching resource without client"""
        content = await resource_handler.fetch_resource("resource://test")
        assert content is None
    
    @pytest.mark.asyncio
    async def test_fetch_resource_error(self, resource_handler, mock_mcp_client, mock_session):
        """Test fetching resource with error"""
        mock_session.read_resource = AsyncMock(side_effect=Exception("Test error"))
        mock_mcp_client.session = AsyncMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        resource_handler.set_client(mock_mcp_client)
        
        content = await resource_handler.fetch_resource("resource://test")
        assert content is None
    
    def test_format_resource(self, resource_handler):
        """Test formatting a resource"""
        # Test with object attributes
        mock_resource = Mock()
        mock_resource.uri = "resource://test"
        mock_resource.name = "Test Resource"
        mock_resource.description = "Test Description"
        mock_resource.mimeType = "text/plain"
        
        formatted = resource_handler._format_resource(mock_resource)
        
        assert formatted['uri'] == "resource://test"
        assert formatted['name'] == "Test Resource"
        assert formatted['description'] == "Test Description"
        assert formatted['mimeType'] == "text/plain"
        
        # Test with dictionary
        dict_resource = {
            'uri': 'resource://dict',
            'name': 'Dict Resource'
        }
        
        formatted = resource_handler._format_resource(dict_resource)
        
        assert formatted['uri'] == "resource://dict"
        assert formatted['name'] == "Dict Resource"
    
    def test_process_content_item(self, resource_handler):
        """Test processing content items"""
        # Test with text content
        mock_content = Mock()
        mock_content.text = "Test text"
        mock_content.mimeType = "text/plain"
        
        processed = resource_handler._process_content_item(mock_content)
        
        assert processed['text'] == "Test text"
        assert processed['mimeType'] == "text/plain"
        
        # Test with string content
        processed = resource_handler._process_content_item("Simple string")
        assert processed['text'] == "Simple string"
        
        # Test with data content
        mock_data_content = Mock()
        mock_data_content.data = {"key": "value"}
        
        processed = resource_handler._process_content_item(mock_data_content)
        assert processed['data'] == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_get_resource_by_name(self, resource_handler, mock_mcp_client, mock_session):
        """Test getting resource by name"""
        # Setup mock resources
        mock_resource1 = Mock()
        mock_resource1.uri = "resource://test1"
        mock_resource1.name = "Target Resource"
        
        mock_resource2 = Mock()
        mock_resource2.uri = "resource://test2"
        mock_resource2.name = "Other Resource"
        
        mock_response = Mock()
        mock_response.resources = [mock_resource1, mock_resource2]
        
        mock_session.list_resources = AsyncMock(return_value=mock_response)
        mock_mcp_client.session = AsyncMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        resource_handler.set_client(mock_mcp_client)
        
        # Test finding resource
        resource = await resource_handler.get_resource_by_name("Target Resource")
        
        assert resource is not None
        assert resource['name'] == "Target Resource"
        assert resource['uri'] == "resource://test1"
        
        # Test not finding resource
        resource = await resource_handler.get_resource_by_name("Nonexistent")
        assert resource is None