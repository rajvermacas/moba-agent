"""
MCP Agent Core with Gemini 2.5 Flash and LangGraph
"""

import logging
import re
import json
import time
from datetime import datetime
from functools import wraps
from typing import Dict, Any, List, Optional, Union
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from .config import Config
from .resources import ResourceHandler
from .tools import ToolHandler
from .graph_visualization_tool import GraphVisualizationTool


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
        
        # Initialize graph visualization tool (will be set after agent init)
        self.graph_viz_tool = None
        
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
            
            # Initialize GraphVisualizationTool after agent creation
            self.graph_viz_tool = GraphVisualizationTool(self)
            self.logger.info("GraphVisualizationTool initialized")
            
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
                    checkpointer=self.checkpointer
                )
                self.logger.info("Created ReAct agent with MCP tools")
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
            response = self.llm.invoke(state["messages"])
            return {"messages": [response]}
        
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
    
    async def invoke(self, message: str, thread_id: str = "default") -> str:
        """
        Invoke the agent with a message
        
        Args:
            message: User message
            thread_id: Thread ID for conversation context
            
        Returns:
            Agent response
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
            
            # Extract response
            if response and "messages" in response:
                last_message = response["messages"][-1]
                if isinstance(last_message, AIMessage):
                    result = last_message.content
                else:
                    result = str(last_message)
            else:
                result = str(response)
            
            self.logger.debug(f"Agent response: {result[:100]}...")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to invoke agent: {e}", exc_info=True)
            raise

    async def invoke_with_query_tracking(self, message: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        Invoke the agent with a message and track database query results
        
        Args:
            message: User message
            thread_id: Thread ID for conversation context
            
        Returns:
            Dict containing:
                - response: Agent response text (from last AIMessage)
                - query_result: Database query result if any execute_query_* tool was called
        """
        if not self._initialized:
            await self.initialize()
        
        self.logger.debug(f"Invoking agent with query tracking for message: {message[:100]}...")
        
        try:
            # Prepare messages list
            messages = []
            
            # Check if this is the first message for this thread
            if thread_id not in self._thread_resources_injected:
                # Add system instruction for visualization marker and configuration
                viz_instruction = SystemMessage(content=(
                    "When you execute a database query and return results, analyze whether a visual chart or graph "
                    "would help the user understand the data better. If you determine that visualization would be "
                    "helpful (e.g., for trends, comparisons, distributions, or when the user explicitly requests it), "
                    "include the exact marker [VISUALIZE=TRUE] somewhere in your response. "
                    "When you include [VISUALIZE=TRUE], also analyze the data and provide [CHART_CONFIG={...}] with a JSON configuration "
                    "specifying: chart_type (bar, line, pie, scatter, heatmap, etc.), x_axis (column name), y_axis (column name), "
                    "title (descriptive title), and optionally color_field (for grouping). "
                    "Example: [VISUALIZE=TRUE] [CHART_CONFIG={\"chart_type\":\"line\",\"x_axis\":\"date\",\"y_axis\":\"sales\",\"title\":\"Monthly Sales Trend\",\"color_field\":\"region\"}]. "
                    "Choose chart_type based on data: line for time series, bar for comparisons, pie for proportions, scatter for correlations."
                ))
                messages.append(viz_instruction)
                
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
            
            # Initialize result dict
            result = {
                "response": "",
                "query_result": None,
                "graph": None  # NEW: Add graph field
            }
            
            # Process response messages
            if response and "messages" in response:
                all_messages = response["messages"]
                self.logger.debug(f"Processing {len(all_messages)} messages from agent response")
                
                # Collect all AIMessages and ToolMessages
                ai_messages = []
                query_result = None
                query_pattern = re.compile(r'^execute_query_.*$')
                
                for msg in all_messages:
                    self.logger.debug(f"Processing message type: {type(msg).__name__}")
                    
                    if isinstance(msg, AIMessage):
                        ai_messages.append(msg)
                        self.logger.debug(f"Found AIMessage with content: {msg.content[:100] if msg.content else 'None'}...")
                    
                    elif isinstance(msg, ToolMessage):
                        # Check if this is a query tool
                        tool_name = getattr(msg, 'name', '')
                        if not tool_name:
                            # Try to get tool name from tool_call_id or other attributes
                            tool_call_id = getattr(msg, 'tool_call_id', '')
                            if tool_call_id:
                                # Extract tool name from tool_call_id if possible
                                parts = tool_call_id.split('_')
                                if len(parts) >= 3 and parts[0] == 'call':
                                    tool_name = '_'.join(parts[1:])
                        
                        self.logger.debug(f"Found ToolMessage with tool_name: '{tool_name}'")
                        
                        if query_pattern.match(tool_name):
                            self.logger.info(f"Found query tool result: {tool_name}")
                            try:
                                # Parse the tool result
                                content = msg.content
                                if isinstance(content, str):
                                    tool_result = json.loads(content)
                                else:
                                    tool_result = content
                                
                                # Store the last query result (overwrite if multiple queries)
                                query_result = tool_result
                                self.logger.info(f"Captured query result with {len(tool_result.get('rows', []))} rows")
                                
                            except (json.JSONDecodeError, AttributeError) as e:
                                self.logger.warning(f"Failed to parse tool result from {tool_name}: {e}")
                
                # Get response text from the LAST AIMessage
                if ai_messages:
                    last_ai_message = ai_messages[-1]
                    result["response"] = last_ai_message.content or ""
                    self.logger.debug(f"Using last AIMessage content as response: {result['response'][:100]}...")
                else:
                    # Fallback to string representation
                    result["response"] = str(response)
                    self.logger.warning("No AIMessage found, using string representation of response")
                
                # Set query result if found
                if query_result:
                    result["query_result"] = query_result
                    self.logger.info("Query result captured successfully")
                    
                    # NEW: Check for visualization need and invoke GraphVisualizationTool
                    try:
                        # Determine if visualization is needed based on agent's response
                        should_visualize = False
                        chart_config = None
                        
                        # Check agent's response for explicit visualization marker and configuration
                        if ai_messages:
                            last_ai_response = ai_messages[-1].content or ""
                            
                            # Look for explicit [VISUALIZE=TRUE] marker from agent
                            if "[VISUALIZE=TRUE]" in last_ai_response:
                                self.logger.info("Agent explicitly indicated visualization is needed with [VISUALIZE=TRUE] marker")
                                should_visualize = True
                                
                                # Extract chart configuration if provided
                                config_match = re.search(r'\[CHART_CONFIG=(.*?)\]', last_ai_response)
                                if config_match:
                                    try:
                                        chart_config = json.loads(config_match.group(1))
                                        self.logger.info(f"Extracted chart configuration: {chart_config}")
                                    except json.JSONDecodeError as e:
                                        self.logger.warning(f"Failed to parse CHART_CONFIG JSON: {e}")
                                        chart_config = None
                            # Backward compatibility: Also check for explicit user request
                            elif message:
                                message_lower = message.lower()
                                explicit_viz_keywords = ['show me a chart', 'show me a graph', 'visualize', 
                                                        'plot', 'create a graph', 'create a chart', 
                                                        'display chart', 'display graph']
                                if any(keyword in message_lower for keyword in explicit_viz_keywords):
                                    self.logger.info("User explicitly requested visualization")
                                    should_visualize = True
                        
                        # Only proceed with visualization if needed
                        if should_visualize:
                            self.logger.info("Visualization determined to be needed - analyzing query result")
                            from .graph_visualization import analyze_and_generate_graph
                            
                            # Get chart metadata with should_visualize flag and configuration
                            chart_metadata = await analyze_and_generate_graph(
                                query_result=query_result,
                                should_visualize=should_visualize,
                                llm=self.llm,
                                chart_config=chart_config
                            )
                        else:
                            self.logger.info("Visualization not needed for this query result")
                            chart_metadata = None
                        
                        # Check if visualization is needed (deterministic flag)
                        if chart_metadata and chart_metadata.get("visualization_needed"):
                            self.logger.info("Visualization needed flag is True - invoking GraphVisualizationTool")
                            
                            # Manually invoke GraphVisualizationTool
                            if self.graph_viz_tool:
                                viz_result = await self.graph_viz_tool.arun(
                                    query_results=query_result,
                                    context=all_messages,
                                    thread_id=thread_id,
                                    chart_config=chart_config or chart_metadata.get("chart_config")
                                )
                                
                                if viz_result["status"] == "success":
                                    result["graph"] = viz_result["graph_data"]
                                    self.logger.info(f"Generated {viz_result['chart_type']} chart via tool")
                                else:
                                    self.logger.warning(f"Graph visualization tool returned error: {viz_result.get('error')}")
                            else:
                                self.logger.warning("GraphVisualizationTool not initialized")
                        else:
                            self.logger.info("Query result not suitable for visualization")
                            
                    except Exception as e:
                        self.logger.error(f"Graph generation failed: {e}", exc_info=True)
                        # Continue without graph - don't fail the entire request
                
            else:
                result["response"] = str(response)
                self.logger.warning("No messages found in response, using string representation")
            
            self.logger.debug(f"Agent response with query tracking completed. Query result present: {result['query_result'] is not None}, Graph present: {result.get('graph') is not None}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to invoke agent with query tracking: {e}", exc_info=True)
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
