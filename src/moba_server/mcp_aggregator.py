"""
Minimal Multi-MCP Client Aggregator

A simple aggregator class that connects to multiple MCP servers,
namespaces their tools, and routes calls appropriately.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters

logger = logging.getLogger(__name__)


class MCPAggregator:
    """Aggregates multiple MCP server connections and routes tool calls."""
    
    def __init__(self, config_path: str = "mcp_servers_config.json"):
        """Initialize aggregator with configuration file path."""
        self.config_path = Path(config_path)
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.exit_stack = AsyncExitStack()
        self.config: Dict[str, Any] = {}
        
        logger.info(f"Initializing MCP Aggregator with config: {self.config_path}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect_all()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect_all()
    
    async def connect_all(self):
        """Connect to all configured MCP servers."""
        logger.info("Starting connection to all MCP servers")
        
        # Load configuration
        if not self.config_path.exists():
            logger.error(f"Configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        
        logger.info(f"Loaded configuration for {len(self.config.get('servers', {}))} servers")
        
        # Connect to each server
        for server_name, server_config in self.config.get('servers', {}).items():
            try:
                logger.info(f"Connecting to server: {server_name}")
                await self._connect_server(server_name, server_config)
                logger.info(f"Successfully connected to {server_name}")
            except Exception as e:
                logger.error(f"Failed to connect to {server_name}: {e}")
                # Continue with other servers even if one fails
    
    async def _connect_server(self, server_name: str, config: Dict[str, Any]):
        """Connect to a single MCP server based on its configuration."""
        transport = config.get('transport')
        
        logger.debug(f"Connecting to {server_name} with transport: {transport}")
        
        if transport == 'sse':
            # Connect via SSE
            endpoint = config.get('endpoint')
            if not endpoint:
                raise ValueError(f"SSE transport requires 'endpoint' for {server_name}")
            
            logger.debug(f"Creating SSE connection to {endpoint}")
            sse_transport = await self.exit_stack.enter_async_context(
                sse_client(endpoint)
            )
            read, write = sse_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
        elif transport == 'stdio':
            # Connect via stdio
            command = config.get('command')
            if not command:
                raise ValueError(f"stdio transport requires 'command' for {server_name}")
            
            logger.debug(f"Creating stdio connection with command: {command}")
            server_params = StdioServerParameters(
                command=command[0] if isinstance(command, list) else command,
                args=command[1:] if isinstance(command, list) and len(command) > 1 else [],
                env=None
            )
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
        else:
            raise ValueError(f"Unknown transport type: {transport} for {server_name}")
        
        # Initialize session
        logger.debug(f"Initializing session for {server_name}")
        await session.initialize()
        
        # Store session
        self.sessions[server_name] = session
        
        # Discover and store tools with namespacing
        logger.debug(f"Discovering tools for {server_name}")
        tools_response = await session.list_tools()
        
        for tool in tools_response.tools:
            namespaced_name = f"{server_name}.{tool.name}"
            self.tools[namespaced_name] = {
                'server': server_name,
                'original_name': tool.name,
                'description': tool.description if hasattr(tool, 'description') else None
            }
            logger.debug(f"Registered tool: {namespaced_name}")
        
        logger.info(f"Registered {len(tools_response.tools)} tools from {server_name}")
        
        # Discover and store resources with namespacing
        logger.debug(f"Discovering resources for {server_name}")
        try:
            resources_response = await session.list_resources()
            
            for resource in resources_response.resources:
                # Check if the URI already has a scheme
                original_uri = str(resource.uri)
                if '://' in original_uri:
                    # Keep the original URI, just add server prefix for namespacing
                    namespaced_uri = f"{server_name}.{original_uri}"
                else:
                    # Add server as scheme
                    namespaced_uri = f"{server_name}://{original_uri}"
                    
                self.resources[namespaced_uri] = {
                    'server': server_name,
                    'original_uri': original_uri,
                    'name': resource.name if hasattr(resource, 'name') else None,
                    'description': resource.description if hasattr(resource, 'description') else None
                }
                logger.debug(f"Registered resource: {namespaced_uri}")
            
            logger.info(f"Registered {len(resources_response.resources)} resources from {server_name}")
        except Exception as e:
            logger.warning(f"Could not list resources for {server_name}: {e}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a tool on the appropriate server."""
        logger.info(f"Calling tool: {tool_name} with arguments: {arguments}")
        
        if '.' not in tool_name:
            logger.error(f"Tool name must be in format 'server.tool': {tool_name}")
            raise ValueError(f"Tool name must be in format 'server.tool': {tool_name}")
        
        # Split server and tool name
        server_name, actual_tool = tool_name.split('.', 1)
        
        if server_name not in self.sessions:
            logger.error(f"Unknown server: {server_name}")
            raise ValueError(f"Unknown server: {server_name}")
        
        # Get session and call tool
        session = self.sessions[server_name]
        
        logger.debug(f"Routing tool call to {server_name}: {actual_tool}")
        result = await session.call_tool(actual_tool, arguments or {})
        
        logger.info(f"Tool call completed: {tool_name}")
        return result
    
    def list_tools(self) -> List[str]:
        """List all available tools from all servers."""
        logger.debug(f"Listing {len(self.tools)} total tools")
        return list(self.tools.keys())
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific tool."""
        return self.tools.get(tool_name)
    
    async def read_resource(self, resource_uri: str) -> Any:
        """Read a resource from the appropriate server."""
        logger.info(f"Reading resource: {resource_uri}")
        
        # Check if this is a namespaced resource (server.scheme://path or server://path)
        if '.' in resource_uri and '://' in resource_uri:
            # Format: server.scheme://path
            server_name = resource_uri.split('.')[0]
            original_uri = '.'.join(resource_uri.split('.')[1:])
        elif '://' in resource_uri and not any(resource_uri.startswith(s + '.') for s in self.sessions.keys()):
            # Try direct resource URI for backward compatibility
            for server_name, session in self.sessions.items():
                try:
                    from mcp.types import AnyUrl
                    result = await session.read_resource(AnyUrl(resource_uri))
                    logger.info(f"Successfully read resource from {server_name}")
                    return result
                except Exception as e:
                    logger.debug(f"Failed to read resource from {server_name}: {e}")
            raise ValueError(f"Could not read resource: {resource_uri}")
        else:
            # Legacy format: server://path (shouldn't happen with new format)
            server_name = resource_uri.split('://')[0]
            original_uri = '://'.join(resource_uri.split('://')[1:])
        
        if server_name not in self.sessions:
            logger.error(f"Unknown server: {server_name}")
            raise ValueError(f"Unknown server: {server_name}")
        
        # Get session and read resource
        session = self.sessions[server_name]
        
        logger.debug(f"Reading resource from {server_name}: {original_uri}")
        from mcp.types import AnyUrl
        result = await session.read_resource(AnyUrl(original_uri))
        
        logger.info(f"Resource read completed: {resource_uri}")
        return result
    
    def list_resources(self) -> List[str]:
        """List all available resources from all servers."""
        logger.debug(f"Listing {len(self.resources)} total resources")
        return list(self.resources.keys())
    
    def get_resource_info(self, resource_uri: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific resource."""
        return self.resources.get(resource_uri)
    
    async def read_all_resources(self) -> Dict[str, Any]:
        """
        Read all available resources from all servers.
        
        Returns:
            Dictionary mapping resource URIs to their content
        """
        logger.info(f"Reading all {len(self.resources)} available resources")
        all_resources_data = {}
        
        for resource_uri in self.resources.keys():
            try:
                logger.debug(f"Attempting to read resource: {resource_uri}")
                result = await self.read_resource(resource_uri)
                
                if result and hasattr(result, 'contents'):
                    # Extract content based on type
                    content = None
                    if result.contents:
                        # Handle text content
                        if hasattr(result.contents[0], 'text'):
                            content_text = result.contents[0].text
                            # Try to parse as JSON
                            try:
                                import json
                                content = json.loads(content_text)
                                logger.debug(f"Successfully parsed JSON content for {resource_uri}")
                            except json.JSONDecodeError:
                                # Keep as text if not JSON
                                content = content_text
                                logger.debug(f"Kept text content for {resource_uri}")
                        # Handle other content types if needed
                        else:
                            content = str(result.contents[0])
                            logger.debug(f"Converted content to string for {resource_uri}")
                    
                    if content:
                        all_resources_data[resource_uri] = content
                        logger.info(f"Successfully read resource: {resource_uri}")
                else:
                    logger.warning(f"Resource {resource_uri} returned empty or invalid result")
                    
            except Exception as e:
                logger.debug(f"Could not read resource {resource_uri}: {e}")
                # Continue with other resources
                
        logger.info(f"Successfully read {len(all_resources_data)} out of {len(self.resources)} resources")
        return all_resources_data
    
    async def disconnect_all(self):
        """Disconnect from all MCP servers."""
        logger.info("Disconnecting from all MCP servers")
        await self.exit_stack.aclose()
        self.sessions.clear()
        self.tools.clear()
        self.resources.clear()
        logger.info("All MCP servers disconnected")