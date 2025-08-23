"""
Tool Handler for MCP Tools
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
import json


class ToolHandler:
    """Handler for MCP tools"""
    
    def __init__(self, config):
        """
        Initialize Tool Handler
        
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
        self.logger.debug("MCP client set for ToolHandler")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools from MCP server
        
        Returns:
            List of tool descriptions
        """
        self.logger.debug("Listing MCP tools")
        
        if not self.mcp_client:
            self.logger.error("MCP client not initialized")
            return []
        
        try:
            # Get tools from MCP client
            tools = await self.mcp_client.get_tools()
            
            if not tools:
                self.logger.warning("No tools available from MCP server")
                return []
            
            tool_count = len(tools)
            self.logger.info(f"Found {tool_count} tools")
            
            # Format tools for display
            formatted_tools = []
            for tool in tools:
                formatted = self._format_tool(tool)
                formatted_tools.append(formatted)
                self.logger.debug(f"Tool: {formatted['name']} - {formatted.get('description', 'N/A')}")
            
            return formatted_tools
            
        except Exception as e:
            self.logger.error(f"Failed to list tools: {e}", exc_info=True)
            return []
    
    def _format_tool(self, tool: Any) -> Dict[str, Any]:
        """
        Format a tool for consistent output
        
        Args:
            tool: Raw tool object
            
        Returns:
            Formatted tool dictionary
        """
        formatted = {}
        
        # Extract tool name
        if hasattr(tool, 'name'):
            formatted['name'] = tool.name
        elif hasattr(tool, '__name__'):
            formatted['name'] = tool.__name__
        else:
            formatted['name'] = str(tool)
        
        # Extract description
        if hasattr(tool, 'description'):
            formatted['description'] = tool.description
        elif hasattr(tool, '__doc__'):
            formatted['description'] = tool.__doc__
        
        # Extract parameters/schema
        if hasattr(tool, 'args_schema'):
            formatted['parameters'] = self._format_schema(tool.args_schema)
        elif hasattr(tool, 'input_schema'):
            formatted['parameters'] = self._format_schema(tool.input_schema)
        elif hasattr(tool, 'parameters'):
            formatted['parameters'] = tool.parameters
        
        # Add tool type
        formatted['type'] = type(tool).__name__
        
        return formatted
    
    def _format_schema(self, schema: Any) -> Dict[str, Any]:
        """
        Format a schema object
        
        Args:
            schema: Schema object
            
        Returns:
            Formatted schema dictionary
        """
        if hasattr(schema, 'schema'):
            # Pydantic model
            return schema.schema()
        elif hasattr(schema, 'dict'):
            # Has dict method
            return schema.dict()
        elif isinstance(schema, dict):
            # Already a dictionary
            return schema
        else:
            # Convert to string representation
            return {"description": str(schema)}
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a specific tool
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments for the tool
            
        Returns:
            Tool execution result
        """
        self.logger.debug(f"Executing tool: {tool_name} with arguments: {arguments}")
        
        if not self.mcp_client:
            self.logger.error("MCP client not initialized")
            return {"error": "MCP client not initialized"}
        
        try:
            # Get tools
            tools = await self.mcp_client.get_tools()
            
            # Find the specific tool
            target_tool = None
            for tool in tools:
                if hasattr(tool, 'name') and tool.name == tool_name:
                    target_tool = tool
                    break
                elif hasattr(tool, '__name__') and tool.__name__ == tool_name:
                    target_tool = tool
                    break
            
            if not target_tool:
                error_msg = f"Tool not found: {tool_name}"
                self.logger.error(error_msg)
                return {"error": error_msg}
            
            # Execute the tool
            self.logger.info(f"Executing tool: {tool_name}")
            
            # Tools from MCP are callable
            if callable(target_tool):
                result = await target_tool(**arguments) if arguments else await target_tool()
            else:
                # Try to invoke if it has an invoke method
                if hasattr(target_tool, 'ainvoke'):
                    result = await target_tool.ainvoke(arguments)
                elif hasattr(target_tool, 'invoke'):
                    result = target_tool.invoke(arguments)
                else:
                    result = {"error": f"Tool {tool_name} is not callable"}
            
            self.logger.info(f"Tool {tool_name} executed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Failed to execute tool {tool_name}: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
    
    async def get_tool_by_name(self, name: str) -> Optional[Any]:
        """
        Get a tool by name
        
        Args:
            name: Name of the tool
            
        Returns:
            Tool object or None if not found
        """
        self.logger.debug(f"Looking for tool by name: {name}")
        
        if not self.mcp_client:
            self.logger.error("MCP client not initialized")
            return None
        
        try:
            tools = await self.mcp_client.get_tools()
            
            for tool in tools:
                if hasattr(tool, 'name') and tool.name == name:
                    self.logger.info(f"Found tool: {name}")
                    return tool
                elif hasattr(tool, '__name__') and tool.__name__ == name:
                    self.logger.info(f"Found tool: {name}")
                    return tool
            
            self.logger.warning(f"Tool not found: {name}")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get tool {name}: {e}", exc_info=True)
            return None
    
    def format_tool_result(self, result: Any) -> str:
        """
        Format tool execution result for display
        
        Args:
            result: Tool execution result
            
        Returns:
            Formatted result string
        """
        if isinstance(result, dict):
            if "error" in result:
                return f"❌ Error: {result['error']}"
            else:
                return json.dumps(result, indent=2)
        elif isinstance(result, str):
            return result
        else:
            return str(result)