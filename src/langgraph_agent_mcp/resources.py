"""
Resource Handler for MCP Resources
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient


class ResourceHandler:
    """Handler for MCP resources - no caching, fresh fetch on each request"""
    
    def __init__(self, config):
        """
        Initialize Resource Handler
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.mcp_client = None
        self.server_name = config.mcp_server_name
    
    def set_client(self, mcp_client: MultiServerMCPClient):
        """
        Set the MCP client
        
        Args:
            mcp_client: MultiServerMCPClient instance
        """
        self.mcp_client = mcp_client
        self.logger.debug("MCP client set for ResourceHandler")
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources from MCP server
        
        Returns:
            List of resource descriptions
        """
        self.logger.debug("Listing MCP resources")
        
        if not self.mcp_client:
            self.logger.error("MCP client not initialized")
            return []
        
        try:
            # Get session for the server
            async with self.mcp_client.session(self.server_name) as session:
                # List available resources
                resources_response = await session.list_resources()
                
                if hasattr(resources_response, 'resources'):
                    resources = resources_response.resources
                else:
                    resources = resources_response if isinstance(resources_response, list) else []
                
                resource_count = len(resources)
                self.logger.info(f"Found {resource_count} resources")
                
                # Format resources for return
                formatted_resources = []
                for resource in resources:
                    formatted = self._format_resource(resource)
                    formatted_resources.append(formatted)
                    self.logger.debug(f"Resource: {formatted['uri']} - {formatted.get('name', 'N/A')}")
                
                return formatted_resources
                
        except Exception as e:
            self.logger.error(f"Failed to list resources: {e}", exc_info=True)
            return []
    
    async def fetch_resource(self, resource_uri: str) -> Any:
        """
        Fetch a specific resource from MCP server
        
        Args:
            resource_uri: URI of the resource to fetch
            
        Returns:
            Resource content (no caching)
        """
        self.logger.debug(f"Fetching resource: {resource_uri}")
        
        if not self.mcp_client:
            self.logger.error("MCP client not initialized")
            return None
        
        try:
            # Get session for the server
            async with self.mcp_client.session(self.server_name) as session:
                # Fetch the resource
                resource_response = await session.read_resource(resource_uri)
                
                # Extract content
                if hasattr(resource_response, 'contents'):
                    contents = resource_response.contents
                elif hasattr(resource_response, 'content'):
                    contents = resource_response.content
                else:
                    contents = resource_response
                
                self.logger.info(f"Successfully fetched resource: {resource_uri}")
                
                # Process contents based on type
                if isinstance(contents, list):
                    # Multiple content items
                    processed_contents = []
                    for item in contents:
                        processed_item = self._process_content_item(item)
                        processed_contents.append(processed_item)
                    return processed_contents
                else:
                    # Single content item
                    return self._process_content_item(contents)
                
        except Exception as e:
            self.logger.error(f"Failed to fetch resource {resource_uri}: {e}", exc_info=True)
            return None
    
    def _format_resource(self, resource: Any) -> Dict[str, Any]:
        """
        Format a resource for consistent output
        
        Args:
            resource: Raw resource object
            
        Returns:
            Formatted resource dictionary
        """
        formatted = {}
        
        # Extract common fields
        if hasattr(resource, 'uri'):
            formatted['uri'] = resource.uri
        elif isinstance(resource, dict) and 'uri' in resource:
            formatted['uri'] = resource['uri']
        else:
            formatted['uri'] = str(resource)
        
        if hasattr(resource, 'name'):
            formatted['name'] = resource.name
        elif isinstance(resource, dict) and 'name' in resource:
            formatted['name'] = resource['name']
        
        if hasattr(resource, 'description'):
            formatted['description'] = resource.description
        elif isinstance(resource, dict) and 'description' in resource:
            formatted['description'] = resource['description']
        
        if hasattr(resource, 'mimeType'):
            formatted['mimeType'] = resource.mimeType
        elif isinstance(resource, dict) and 'mimeType' in resource:
            formatted['mimeType'] = resource['mimeType']
        
        return formatted
    
    def _process_content_item(self, content: Any) -> Dict[str, Any]:
        """
        Process a single content item
        
        Args:
            content: Raw content item
            
        Returns:
            Processed content dictionary
        """
        processed = {}
        
        # Handle different content types
        if hasattr(content, 'uri'):
            processed['uri'] = content.uri
        
        if hasattr(content, 'mimeType'):
            processed['mimeType'] = content.mimeType
        elif hasattr(content, 'type'):
            processed['mimeType'] = content.type
        
        if hasattr(content, 'text'):
            processed['text'] = content.text
        elif hasattr(content, 'data'):
            processed['data'] = content.data
        elif isinstance(content, str):
            processed['text'] = content
        else:
            # Store raw content
            processed['raw'] = content
        
        self.logger.debug(f"Processed content item with keys: {processed.keys()}")
        
        return processed
    
    async def get_resource_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a resource by name
        
        Args:
            name: Name of the resource
            
        Returns:
            Resource information or None if not found
        """
        self.logger.debug(f"Looking for resource by name: {name}")
        
        resources = await self.list_resources()
        
        for resource in resources:
            if resource.get('name') == name:
                self.logger.info(f"Found resource: {name}")
                return resource
        
        self.logger.warning(f"Resource not found: {name}")
        return None