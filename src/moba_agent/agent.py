"""
MCP Agent Core with Gemini 2.5 Flash and LangGraph
"""

import logging
import re
import json
import time
from datetime import datetime
from functools import wraps
from typing import Dict, Any, List, Optional, Union, Tuple
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage
from .config import Config
from .resources import ResourceHandler
from .tools import ToolHandler
from .graph_visualization_tool import GraphVisualizationTool
from .schemas import StructuredAgentResponse, ChartConfig, QueryMetadata


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
        """Initialize Gemini LLM with structured output"""
        self.logger.debug("Initializing Gemini LLM with structured output")
        
        try:
            gemini_config = self.config.get_gemini_config()
            base_llm = ChatGoogleGenerativeAI(**gemini_config)
            
            # Configure structured output for visualization responses
            self.llm_structured = base_llm.with_structured_output(
                StructuredAgentResponse
            )
            
            # Keep base LLM for agent use (tools need unstructured)
            self.llm = base_llm
            
            self.logger.info(f"Gemini LLM initialized with model: {self.config.agent_model}")
            self.logger.info("Structured output configured for visualization responses")
            
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

    # ============================================================================
    # Message Preparation Methods
    # ============================================================================
    
    
    async def _prepare_messages_for_thread(self, message: str, thread_id: str) -> List[BaseMessage]:
        """
        Prepare messages list for agent invocation, including thread-specific setup.
        
        Args:
            message: User message to process
            thread_id: Thread identifier for conversation context
            
        Returns:
            List of messages ready for agent invocation
        """
        self.logger.debug(f"Preparing messages for thread: {thread_id}")
        messages = []
        
        # Check if this is the first message for this thread
        if thread_id not in self._thread_resources_injected:
            # Note: Visualization decisions are now handled via structured output
            # No need for text-based marker instructions anymore
            
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
        
        return messages
    
    # ============================================================================
    # Response Processing Methods
    # ============================================================================
    
    def _extract_ai_messages(self, messages: List[Any]) -> List[AIMessage]:
        """
        Extract all AIMessage instances from response messages.
        
        Args:
            messages: List of messages from agent response
            
        Returns:
            List of AIMessage instances
        """
        ai_messages = []
        
        for msg in messages:
            if isinstance(msg, AIMessage):
                ai_messages.append(msg)
                self.logger.debug(
                    f"Found AIMessage with content: {msg.content[:100] if msg.content else 'None'}..."
                )
        
        return ai_messages
    
    def _parse_tool_message_for_query(self, msg: ToolMessage) -> Optional[Dict]:
        """
        Parse a tool message to extract query results if it's from a query tool.
        
        Args:
            msg: ToolMessage to parse
            
        Returns:
            Query result dict if found, None otherwise
        """
        query_pattern = re.compile(r'^execute_query_.*$')
        
        # Extract tool name
        tool_name = getattr(msg, 'name', '')
        if not tool_name:
            # Try to get tool name from tool_call_id
            tool_call_id = getattr(msg, 'tool_call_id', '')
            if tool_call_id:
                parts = tool_call_id.split('_')
                if len(parts) >= 3 and parts[0] == 'call':
                    tool_name = '_'.join(parts[1:])
        
        self.logger.debug(f"Found ToolMessage with tool_name: '{tool_name}'")
        
        # Check if this is a query tool
        if query_pattern.match(tool_name):
            self.logger.info(f"Found query tool result: {tool_name}")
            try:
                # Parse the tool result
                content = msg.content
                if isinstance(content, str):
                    tool_result = json.loads(content)
                else:
                    tool_result = content
                
                # Ensure tool_result is a dict with rows
                if isinstance(tool_result, dict):
                    rows_count = len(tool_result.get('rows', []))
                    self.logger.info(f"Captured query result with {rows_count} rows")
                    return tool_result
                else:
                    self.logger.warning(f"Tool result is not a dict: {type(tool_result)}")
                    return None
                
            except (json.JSONDecodeError, AttributeError) as e:
                self.logger.warning(f"Failed to parse tool result from {tool_name}: {e}")
        
        return None
    
    def _extract_query_results(self, messages: List[Any]) -> Optional[Dict]:
        """
        Extract database query results from tool messages.
        
        Args:
            messages: List of messages from agent response
            
        Returns:
            Last query result found, or None
        """
        query_result = None
        
        for msg in messages:
            if isinstance(msg, ToolMessage):
                result = self._parse_tool_message_for_query(msg)
                if result:
                    # Store the last query result (overwrite if multiple queries)
                    query_result = result
        
        if query_result:
            self.logger.info("Query result captured successfully")
        
        return query_result
    
    def _process_agent_response_messages(self, response: Dict) -> Tuple[str, List[Any], List[AIMessage]]:
        """
        Process response messages from agent to extract content and messages.
        
        Args:
            response: Agent response dict
            
        Returns:
            Tuple of (response_text, all_messages, ai_messages)
        """
        if not response or "messages" not in response:
            self.logger.warning("No messages found in response, using string representation")
            return str(response), [], []
        
        all_messages = response["messages"]
        self.logger.debug(f"Processing {len(all_messages)} messages from agent response")
        
        # Extract AI messages
        ai_messages = self._extract_ai_messages(all_messages)
        
        # Get response text from the LAST AIMessage
        if ai_messages:
            last_ai_message = ai_messages[-1]
            response_text = last_ai_message.content or ""
            self.logger.debug(f"Using last AIMessage content as response: {response_text[:100]}...")
        else:
            response_text = str(response)
            self.logger.warning("No AIMessage found, using string representation of response")
        
        return response_text, all_messages, ai_messages
    
    # ============================================================================
    # Visualization Methods
    # ============================================================================
    
    async def _handle_visualization_with_config(
        self,
        query_result: Dict,
        chart_config: Dict,
        all_messages: List[Any],
        thread_id: str
    ) -> Optional[Dict]:
        """
        Handle visualization with a specific chart configuration.
        
        This simplified method uses the structured chart config directly
        without needing to parse text or make additional LLM calls.
        
        Args:
            query_result: Database query result
            chart_config: Chart configuration from structured response
            all_messages: All messages from response
            thread_id: Thread identifier
            
        Returns:
            Graph data if visualization was generated, None otherwise
        """
        try:
            self.logger.info(f"Generating {chart_config.get('chart_type')} visualization")
            
            # Try using GraphVisualizationTool first if available
            if self.graph_viz_tool:
                try:
                    viz_result = await self.graph_viz_tool.arun(
                        query_results=query_result,
                        context=all_messages,
                        thread_id=thread_id,
                        chart_config=chart_config
                    )
                    
                    if viz_result["status"] == "success":
                        self.logger.info(f"Generated {viz_result['chart_type']} chart via tool")
                        return viz_result["graph_data"]
                    else:
                        self.logger.warning(f"Graph visualization tool returned error: {viz_result.get('error')}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to invoke graph visualization tool: {e}", exc_info=True)
            
            # Fallback to direct graph generation
            from .graph_visualization import analyze_and_generate_graph
            
            graph_data = await analyze_and_generate_graph(
                query_result,
                chart_config=chart_config
            )
            
            if graph_data:
                self.logger.info(f"Generated visualization successfully")
                return graph_data
            else:
                self.logger.warning("No graph data generated")
                return None
                
        except Exception as e:
            self.logger.error(f"Visualization generation failed: {e}", exc_info=True)
            return None
    
    async def _get_structured_response(
        self,
        messages: List[BaseMessage],
        query_result: Optional[Dict] = None
    ) -> StructuredAgentResponse:
        """
        Get a structured response from the LLM for visualization decisions.
        
        This method invokes the LLM with structured output to get clear decisions
        about visualization needs and chart configurations.
        
        Args:
            messages: Conversation history
            query_result: Database query result if available
            
        Returns:
            StructuredAgentResponse with visualization decisions
        """
        try:
            # Build a focused prompt for structured response
            system_prompt = """
            Analyze the conversation and any database query results to determine:
            1. Whether visualization is needed (should_visualize)
            2. If yes, what chart configuration to use (chart_config)
            3. Provide reasoning for your decisions
            
            Consider visualization when:
            - Query results contain aggregated data
            - User explicitly asks for charts/graphs/visualization
            - Data shows trends, comparisons, or distributions
            - Results would be clearer in visual format
            - Try to always provide visualization (Mandatory)
            
            Choose appropriate chart types based on data characteristics:
            - Bar/Column: Categorical comparisons
            - Line: Trends over time
            - Pie: Part-to-whole relationships
            - Scatter: Correlations
            - Heatmap: Matrix data
            - Table: Detailed records
            """
            
            # Add system message for context
            enhanced_messages = [SystemMessage(content=system_prompt)] + messages
            
            # If we have query results, add them to context
            if query_result:
                result_summary = f"\nDatabase Query Result Summary:\n"
                result_summary += f"- Rows returned: {len(query_result.get('rows', []))}\n"
                if query_result.get('rows'):
                    result_summary += f"- Columns: {list(query_result['rows'][0].keys())}\n"
                    result_summary += f"- Sample rows: {query_result['rows'][:3]}\n"
                enhanced_messages.append(SystemMessage(content=result_summary))
            
            # Get structured response from LLM
            self.logger.debug("Invoking LLM for structured visualization response")
            structured_response = await self.llm_structured.ainvoke(enhanced_messages)
            
            self.logger.info(f"Structured response - Visualize: {structured_response.should_visualize}")
            if structured_response.should_visualize and structured_response.chart_config:
                self.logger.info(f"Chart type selected: {structured_response.chart_config.chart_type}")
            
            return structured_response
            
        except Exception as e:
            self.logger.error(f"Failed to get structured response: {e}", exc_info=True)
            # Return default response on error
            return StructuredAgentResponse(
                content="",
                should_visualize=False,
                chart_config=None,
                query_metadata=None,
                reasoning="Error getting structured response"
            )
    
    # ============================================================================
    # Main Public Method
    # ============================================================================
    
    async def invoke_with_query_tracking(self, message: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        Invoke the agent with a message and track database query results.
        
        This method coordinates the entire agent invocation pipeline including
        message preparation, agent execution, response processing, and optional
        visualization generation.
        
        Args:
            message: User message to process
            thread_id: Thread ID for conversation context (default: "default")
            
        Returns:
            Dict containing:
                - response: Agent response text (from last AIMessage)
                - query_result: Database query result if any execute_query_* tool was called
                - graph: Visualization data if generated (optional)
                
        Raises:
            Exception: If agent invocation fails
        """
        if not self._initialized:
            await self.initialize()
        
        self.logger.debug(f"Invoking agent with query tracking for message: {message[:100]}...")
        
        try:
            # Step 1: Prepare messages for the thread
            messages = await self._prepare_messages_for_thread(message, thread_id)
            
            # Step 2: Invoke the agent
            config = {"configurable": {"thread_id": thread_id}}
            response = await self.agent.ainvoke(
                {"messages": messages},
                config=config
            )
            
            # Step 3: Initialize result structure
            result = {
                "response": "",
                "query_result": None,
                "graph": None
            }
            
            # Step 4: Process agent response
            response_text, all_messages, ai_messages = self._process_agent_response_messages(response)
            result["response"] = response_text
            
            # Step 5: Extract query results if present
            query_result = self._extract_query_results(all_messages)
            if query_result:
                result["query_result"] = query_result
                
                # Step 6: Get structured response for visualization decisions
                structured_resp = await self._get_structured_response(
                    messages=all_messages,
                    query_result=query_result
                )
                
                # Step 7: Handle visualization if structured response indicates need
                if structured_resp.should_visualize and structured_resp.chart_config:
                    self.logger.info(
                        f"Structured response indicates visualization needed: "
                        f"{structured_resp.chart_config.chart_type}"
                    )
                    
                    # Convert Pydantic model to dict for compatibility
                    chart_config_dict = structured_resp.chart_config.model_dump()
                    
                    # Generate visualization
                    graph_data = await self._handle_visualization_with_config(
                        query_result,
                        chart_config_dict,
                        all_messages,
                        thread_id
                    )
                    if graph_data:
                        result["graph"] = graph_data
                else:
                    self.logger.info("Structured response: No visualization needed")
            
            self.logger.debug(
                f"Agent response with query tracking completed. "
                f"Query result present: {result['query_result'] is not None}, "
                f"Graph present: {result.get('graph') is not None}"
            )
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
