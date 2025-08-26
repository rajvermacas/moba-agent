"""
MCP Agent Core with Gemini 2.5 Flash and LangGraph
"""

import logging
import json
from typing import Dict, Any, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .config import Config
from .resources import ResourceHandler
from .tools import ToolHandler


class MCPAgent:
    """LangGraph Agent with MCP Integration using Gemini 2.5 Flash"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize MCP Agent
        
        Args:
            config: Configuration object, if None will create default
        """
        self.config = config or Config()
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing MCP Agent with Gemini 2.5 Flash")
        
        # Initialize components
        self.mcp_client = None
        self.llm = None
        self.agent = None
        self.tools = []
        self.checkpointer = MemorySaver()
        
        # Initialize handlers
        self.resource_handler = ResourceHandler(self.config)
        self.tool_handler = ToolHandler(self.config)
        
        # Track initialization state
        self._initialized = False
        
        # Track which threads have had resources injected
        self._thread_resources_injected = {}
    
    async def initialize(self):
        """Initialize the agent asynchronously"""
        if self._initialized:
            self.logger.debug("Agent already initialized")
            return
        
        try:
            self.logger.info("Starting agent initialization")
            
            # Initialize MCP client
            await self._initialize_mcp_client()
            
            # Initialize Gemini LLM
            self._initialize_llm()
            
            # Get tools from MCP server
            await self._load_tools()
            
            # Create LangGraph agent
            await self._create_agent()
            
            self._initialized = True
            self.logger.info("Agent initialization completed successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {e}", exc_info=True)
            raise
    
    async def _initialize_mcp_client(self):
        """Initialize MultiServerMCPClient"""
        self.logger.debug("Initializing MCP client")
        
        try:
            server_config = self.config.get_mcp_server_config()
            self.mcp_client = MultiServerMCPClient(server_config)
            
            # Set client for handlers
            self.resource_handler.set_client(self.mcp_client)
            self.tool_handler.set_client(self.mcp_client)
            
            server_names = [server['name'] for server in self.config.mcp_servers]
            self.logger.info(f"MCP client initialized with {len(server_names)} servers: {', '.join(server_names)}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP client: {e}")
            raise
    
    def _initialize_llm(self):
        """Initialize Gemini LLM"""
        self.logger.debug("Initializing Gemini LLM")
        
        try:
            gemini_config = self.config.get_gemini_config()
            self.llm = ChatGoogleGenerativeAI(**gemini_config)
            self.logger.info(f"Gemini LLM initialized with model: {self.config.agent_model}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini LLM: {e}")
            raise
    
    async def _load_tools(self):
        """Load tools from MCP server"""
        self.logger.debug("Loading tools from MCP server")
        
        try:
            self.tools = await self.mcp_client.get_tools()
            tool_count = len(self.tools) if self.tools else 0
            self.logger.info(f"Loaded {tool_count} tools from MCP server")
            
            if self.tools:
                tool_names = [tool.name if hasattr(tool, 'name') else str(tool) for tool in self.tools]
                self.logger.debug(f"Available tools: {tool_names}")
            
        except Exception as e:
            self.logger.error(f"Failed to load tools: {e}")
            self.logger.warning("Continuing with no tools")
            self.tools = []
    
    async def _create_agent(self):
        """Create LangGraph agent with MCP tools"""
        self.logger.debug("Creating LangGraph agent")
        
        try:
            if self.tools:
                # Create agent with tools
                self.agent = create_react_agent(
                    self.llm,
                    self.tools,
                    prompt=self.config.system_prompt,
                    checkpointer=self.checkpointer
                )
                self.logger.info("Created ReAct agent with MCP tools and system prompt")
            else:
                # Create simple agent without tools
                self.agent = self._create_simple_agent()
                self.logger.info("Created simple agent without tools")
            
        except Exception as e:
            self.logger.error(f"Failed to create agent: {e}")
            raise
    
    def _create_simple_agent(self):
        """Create a simple agent without tools"""
        def call_model(state: MessagesState):
            """Call the LLM model"""
            try:
                response = self.llm.invoke(state["messages"])
                return {"messages": [response]}
            except AttributeError as e:
                # Handle the 'int' object has no attribute 'name' error
                # This is a known issue with langchain_google_genai finish_reason
                self.logger.warning(f"Caught AttributeError in LLM invoke (likely finish_reason issue): {e}")
                
                # Try to extract the response content if it exists
                # The error occurs during response processing, but the content might still be available
                try:
                    # Attempt to get partial response if available
                    if hasattr(e, '__context__') and hasattr(e.__context__, 'args'):
                        self.logger.debug(f"Error context: {e.__context__}")
                    
                    # Return an error message as fallback
                    from langchain_core.messages import AIMessage
                    error_msg = AIMessage(content="I encountered an issue processing the response. Please try again.")
                    return {"messages": [error_msg]}
                except Exception as inner_e:
                    self.logger.error(f"Failed to handle AttributeError gracefully: {inner_e}")
                    raise
        
        # Build state graph
        builder = StateGraph(MessagesState)
        builder.add_node("model", call_model)
        builder.add_edge(START, "model")
        
        return builder.compile(checkpointer=self.checkpointer)
    
    async def _format_resources_context(self) -> Optional[SystemMessage]:
        """
        Format available MCP resources into a SystemMessage for context
        
        Returns:
            SystemMessage with resources information AND their content
        """
        try:
            # Use get_all_resources to fetch both metadata and content
            # Set to None for unlimited content size at POC level
            resources = await self.resource_handler.get_all_resources(max_content_size=None)
            
            if not resources:
                self.logger.debug("No MCP resources available to inject")
                return None
            
            # Format resources into a readable context with their content
            context_lines = ["Available MCP Resources with Content:"]
            context_lines.append("=" * 70)
            
            for resource in resources:
                uri = resource.get('uri', 'Unknown')
                name = resource.get('name', 'Unnamed Resource')
                description = resource.get('description', 'No description available')
                mime_type = resource.get('mimeType', 'Unknown type')
                content = resource.get('content')
                fetch_status = resource.get('fetch_status', 'unknown')
                
                context_lines.append(f"\n• Resource: {name}")
                context_lines.append(f"  URI: {uri}")
                context_lines.append(f"  Type: {mime_type}")
                context_lines.append(f"  Description: {description}")
                
                # Include the actual content if successfully fetched
                if fetch_status == 'success' and content:
                    context_lines.append(f"  Status: Successfully fetched")
                    context_lines.append(f"  Content:")
                    # Indent the content for better readability
                    content_lines = content.split('\n')
                    # Show ALL lines - no truncation for POC
                    for line in content_lines:
                        context_lines.append(f"    {line}")
                elif fetch_status == 'failed':
                    error = resource.get('fetch_error', 'Unknown error')
                    context_lines.append(f"  Status: Failed to fetch - {error}")
                elif fetch_status == 'no_uri':
                    context_lines.append(f"  Status: No URI available for fetching")
                else:
                    context_lines.append(f"  Status: Content not available")
                
                context_lines.append("")  # Add blank line between resources
            
            context_lines.append("=" * 70)
            context_lines.append("You have access to the above resources with their content. Use this information to provide more informed and contextual responses.")
            
            context_text = "\n".join(context_lines)
            
            # Count successful fetches
            successful_fetches = sum(1 for r in resources if r.get('fetch_status') == 'success')
            self.logger.info(f"Formatted {len(resources)} resources for context injection ({successful_fetches} with content)")
            
            return SystemMessage(content=context_text)
            
        except Exception as e:
            self.logger.error(f"Failed to format resources context: {e}", exc_info=True)
            return None
    
    async def invoke(self, message: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        Invoke the agent with a message
        
        Args:
            message: User message
            thread_id: Thread ID for conversation context
            
        Returns:
            Dict containing:
                - content: Agent response text
                - tool_results: Any structured data from tool calls
        """
        if not self._initialized:
            await self.initialize()
        
        self.logger.debug(f"Invoking agent with message: {message[:100]}...")
        
        try:
            # Prepare messages list
            messages = []
            
            # Check if this is the first message for this thread
            if thread_id not in self._thread_resources_injected:
                # Inject resources context on first message
                resources_context = await self._format_resources_context()
                if resources_context:
                    messages.append(resources_context)
                    self.logger.info(f"Injected MCP resources context for thread: {thread_id}")
                
                # Mark thread as having resources injected
                self._thread_resources_injected[thread_id] = True
            
            # Add the user message
            input_message = HumanMessage(content=message)
            messages.append(input_message)
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # Invoke agent
            response = await self.agent.ainvoke(
                {"messages": messages},
                config=config
            )
            
            # Extract response and tool results
            result_content = ""
            tool_results = []
            
            if response and "messages" in response:
                # Look through all messages for tool results and AI response
                from langchain_core.messages import ToolMessage
                
                for msg in response["messages"]:
                    # Check for tool messages that might contain query results
                    if isinstance(msg, ToolMessage):
                        try:
                            # Parse tool content if it's a string containing JSON
                            if isinstance(msg.content, str):
                                import json
                                # Try to parse as JSON
                                if msg.content.strip().startswith('{'):
                                    tool_data = json.loads(msg.content)
                                    tool_results.append({
                                        "tool_name": msg.name if hasattr(msg, 'name') else "unknown",
                                        "data": tool_data
                                    })
                                    self.logger.debug(f"Found tool result from {msg.name if hasattr(msg, 'name') else 'unknown'}: {str(tool_data)[:200]}...")
                            elif isinstance(msg.content, dict):
                                tool_results.append({
                                    "tool_name": msg.name if hasattr(msg, 'name') else "unknown", 
                                    "data": msg.content
                                })
                                self.logger.debug(f"Found tool result dict from {msg.name if hasattr(msg, 'name') else 'unknown'}")
                        except json.JSONDecodeError:
                            # Not JSON, skip
                            pass
                        except Exception as e:
                            self.logger.warning(f"Error processing tool message: {e}")
                    
                    # Get the final AI message content
                    elif isinstance(msg, AIMessage):
                        # Handle both string and list content
                        if isinstance(msg.content, list):
                            result_content = "\n".join(str(item) for item in msg.content)
                        elif isinstance(msg.content, str):
                            result_content = msg.content
                        else:
                            result_content = str(msg.content)
                
                # If no AI message found, use the last message
                if not result_content:
                    last_message = response["messages"][-1]
                    if isinstance(last_message, AIMessage):
                        # Handle both string and list content
                        if isinstance(last_message.content, list):
                            result_content = "\n".join(str(item) for item in last_message.content)
                        elif isinstance(last_message.content, str):
                            result_content = last_message.content
                        else:
                            result_content = str(last_message.content)
                    else:
                        result_content = str(last_message)
            else:
                result_content = str(response)
            
            # Build response structure
            result = {
                "content": result_content,
                "tool_results": tool_results
            }
            
            # Safe logging of content
            content_preview = result_content[:100] if isinstance(result_content, str) else str(result_content)[:100]
            self.logger.debug(f"Agent response: {content_preview}...")
            if tool_results:
                self.logger.info(f"Found {len(tool_results)} tool results in response")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to invoke agent: {e}", exc_info=True)
            raise
    
    async def stream(self, message: str, thread_id: str = "default"):
        """
        Stream agent responses
        
        Args:
            message: User message
            thread_id: Thread ID for conversation context
            
        Yields:
            Agent response chunks
        """
        if not self._initialized:
            await self.initialize()
        
        self.logger.debug(f"Streaming agent response for: {message[:100]}...")
        
        try:
            # Prepare messages list
            messages = []
            
            # Check if this is the first message for this thread
            if thread_id not in self._thread_resources_injected:
                # Inject resources context on first message
                resources_context = await self._format_resources_context()
                if resources_context:
                    messages.append(resources_context)
                    self.logger.info(f"Injected MCP resources context for thread: {thread_id}")
                
                # Mark thread as having resources injected
                self._thread_resources_injected[thread_id] = True
            
            # Add the user message
            input_message = HumanMessage(content=message)
            messages.append(input_message)
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # Stream from agent
            async for chunk in self.agent.astream(
                {"messages": messages},
                config=config
            ):
                if chunk:
                    self.logger.debug(f"Stream chunk: {str(chunk)[:100]}...")
                    yield chunk
                    
        except Exception as e:
            self.logger.error(f"Failed to stream response: {e}", exc_info=True)
            raise
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available MCP tools"""
        if not self._initialized:
            await self.initialize()
        
        return await self.tool_handler.list_tools()
    
    async def get_available_resources(self) -> List[Dict[str, Any]]:
        """Get list of available MCP resources"""
        if not self._initialized:
            await self.initialize()
        
        return await self.resource_handler.list_resources()
    
    async def fetch_resource(self, resource_uri: str) -> Any:
        """
        Fetch a specific MCP resource
        
        Args:
            resource_uri: URI of the resource to fetch
            
        Returns:
            Resource content
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.resource_handler.fetch_resource(resource_uri)
    
    async def close(self):
        """Close the agent and cleanup resources"""
        self.logger.info("Closing MCP agent")
        
        if self.mcp_client:
            # Close MCP client sessions if needed
            pass
        
        self._initialized = False
        self.logger.info("Agent closed successfully")