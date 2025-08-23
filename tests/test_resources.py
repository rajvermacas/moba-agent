"""
Tests for Resource Handler
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from src.moba_agent.resources import ResourceHandler
from src.moba_agent.config import Config


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
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
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
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
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
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
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
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
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
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
        resource_handler.set_client(mock_mcp_client)
        
        # Test finding resource
        resource = await resource_handler.get_resource_by_name("Target Resource")
        
        assert resource is not None
        assert resource['name'] == "Target Resource"
        assert resource['uri'] == "resource://test1"
        
        # Test not finding resource
        resource = await resource_handler.get_resource_by_name("Nonexistent")
        assert resource is None
    
    @pytest.mark.asyncio
    async def test_get_all_resources(self, resource_handler, mock_mcp_client, mock_session):
        """Test getting all resources with content"""
        # Setup mock resources
        mock_resource1 = Mock()
        mock_resource1.uri = "resource://test1"
        mock_resource1.name = "Test Resource 1"
        mock_resource1.description = "Description 1"
        mock_resource1.mimeType = "text/plain"
        
        mock_resource2 = Mock()
        mock_resource2.uri = "resource://test2"
        mock_resource2.name = "Test Resource 2"
        mock_resource2.mimeType = "application/json"
        
        mock_resources_response = Mock()
        mock_resources_response.resources = [mock_resource1, mock_resource2]
        
        # Setup mock content for resources
        mock_content1 = Mock(spec=['text', 'mimeType'])
        mock_content1.text = "Content for resource 1"
        mock_response1 = Mock()
        mock_response1.contents = mock_content1
        
        mock_content2 = Mock(spec=['data', 'mimeType'])
        mock_content2.data = {"key": "value"}
        mock_response2 = Mock()
        mock_response2.contents = mock_content2
        
        # Setup session mocks
        mock_session.list_resources = AsyncMock(return_value=mock_resources_response)
        mock_session.read_resource = AsyncMock(side_effect=[mock_response1, mock_response2])
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
        resource_handler.set_client(mock_mcp_client)
        
        # Test
        # Test with no truncation for POC
        resources = await resource_handler.get_all_resources(max_content_size=None)
        
        assert len(resources) == 2
        
        # Check first resource
        assert resources[0]['uri'] == "resource://test1"
        assert resources[0]['name'] == "Test Resource 1"
        assert resources[0]['content'] == "Content for resource 1"
        assert resources[0]['fetch_status'] == "success"
        
        # Check second resource
        assert resources[1]['uri'] == "resource://test2"
        assert resources[1]['name'] == "Test Resource 2"
        assert '"key": "value"' in resources[1]['content']  # JSON formatted
        assert resources[1]['fetch_status'] == "success"
    
    @pytest.mark.asyncio
    async def test_get_all_resources_with_failures(self, resource_handler, mock_mcp_client, mock_session):
        """Test getting all resources with some fetch failures"""
        # Setup mock resources
        mock_resource1 = Mock()
        mock_resource1.uri = "resource://test1"
        mock_resource1.name = "Test Resource 1"
        
        mock_resource2 = Mock()
        mock_resource2.uri = "resource://test2"
        mock_resource2.name = "Test Resource 2"
        
        mock_resource3 = Mock()
        # Resource without URI
        mock_resource3.name = "No URI Resource"
        
        mock_resources_response = Mock()
        mock_resources_response.resources = [mock_resource1, mock_resource2, mock_resource3]
        
        # Setup mock content - first succeeds, second fails
        mock_content1 = Mock(spec=['text'])
        mock_content1.text = "Success content"
        mock_response1 = Mock()
        mock_response1.contents = mock_content1
        
        # Setup session mocks
        mock_session.list_resources = AsyncMock(return_value=mock_resources_response)
        mock_session.read_resource = AsyncMock(side_effect=[
            mock_response1,
            Exception("Failed to fetch")
        ])
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
        resource_handler.set_client(mock_mcp_client)
        
        # Test
        resources = await resource_handler.get_all_resources()
        
        assert len(resources) == 3
        
        # First resource should succeed
        assert resources[0]['fetch_status'] == "success"
        assert resources[0]['content'] == "Success content"
        
        # Second resource should fail
        assert resources[1]['fetch_status'] == "failed"
        assert resources[1]['content'] is None
        assert "Failed to fetch" in resources[1]['fetch_error']
        
        # Third resource has no URI
        assert resources[2]['fetch_status'] == "no_uri"
        assert resources[2]['content'] is None
    
    @pytest.mark.asyncio
    async def test_get_all_resources_empty(self, resource_handler, mock_mcp_client, mock_session):
        """Test getting all resources when none available"""
        mock_resources_response = Mock()
        mock_resources_response.resources = []
        
        mock_session.list_resources = AsyncMock(return_value=mock_resources_response)
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
        resource_handler.set_client(mock_mcp_client)
        
        resources = await resource_handler.get_all_resources()
        
        assert resources == []
    
    @pytest.mark.asyncio
    async def test_get_all_resources_no_truncation(self, resource_handler, mock_mcp_client, mock_session):
        """Test that content is NOT truncated when max_content_size is None"""
        # Setup mock resource with large content
        mock_resource = Mock()
        mock_resource.uri = "resource://large"
        mock_resource.name = "Large Resource"
        
        mock_resources_response = Mock()
        mock_resources_response.resources = [mock_resource]
        
        # Create large content
        large_text = "x" * 10000  # 10000 chars
        mock_content = Mock()
        mock_content.text = large_text
        mock_response = Mock()
        mock_response.contents = mock_content
        
        mock_session.list_resources = AsyncMock(return_value=mock_resources_response)
        mock_session.read_resource = AsyncMock(return_value=mock_response)
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
        resource_handler.set_client(mock_mcp_client)
        
        # Test with None max_content_size (unlimited)
        resources = await resource_handler.get_all_resources(max_content_size=None)
        
        assert len(resources) == 1
        assert resources[0]['content'] == large_text  # Should NOT be truncated
        assert "truncated" not in resources[0]['content']
        assert resources[0]['fetch_status'] == "success"
    
    @pytest.mark.asyncio
    async def test_get_all_resources_with_truncation(self, resource_handler, mock_mcp_client, mock_session):
        """Test that content IS truncated when max_content_size is specified"""
        # Setup mock resource with large content
        mock_resource = Mock()
        mock_resource.uri = "resource://large"
        mock_resource.name = "Large Resource"
        
        mock_resources_response = Mock()
        mock_resources_response.resources = [mock_resource]
        
        # Create large content
        large_text = "x" * 200  # 200 chars
        mock_content = Mock()
        mock_content.text = large_text
        mock_response = Mock()
        mock_response.contents = mock_content
        
        mock_session.list_resources = AsyncMock(return_value=mock_resources_response)
        mock_session.read_resource = AsyncMock(return_value=mock_response)
        
        # Create async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_mcp_client.session = Mock(return_value=async_context)
        
        resource_handler.set_client(mock_mcp_client)
        
        # Test with small max_content_size
        resources = await resource_handler.get_all_resources(max_content_size=50)
        
        assert len(resources) == 1
        assert len(resources[0]['content']) > 50  # Should be truncated with message
        assert "truncated at 50 chars" in resources[0]['content']
        assert resources[0]['fetch_status'] == "success"