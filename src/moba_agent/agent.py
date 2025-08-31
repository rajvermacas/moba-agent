"""
MCP Agent Core with Gemini 2.5 Flash and LangGraph
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import RetryPolicy
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from .config import Config
from .resources import ResourceHandler
from .tools import ToolHandler
from .graph_visualization_tool import GraphVisualizationTool
from .schemas import StructuredAgentResponse
from .constants import (
    QUERY_TOOL_PATTERN, 
    AGENT_RECURSION_LIMIT,
    AGENT_SYSTEM_PROMPT,
    VISUALIZATION_SYSTEM_PROMPT
)
# Import native tools from native_tools package
from .native_tools.gitlab import GitLabIssueTool
# Import and apply Gemini patch for finish_reason enum issue
# from .gemini_patch import apply_gemini_patch


class AgentState(MessagesState):
    """Custom state that includes visualization data"""
    graph_data: Optional[Dict[str, Any]] = None
    query_result: Optional[Dict[str, Any]] = None


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
        
        # Apply Gemini patch for finish_reason enum issue
        # if apply_gemini_patch():
        #     self.logger.info("Applied Gemini finish_reason patch successfully")
        # else:
        #     self.logger.warning("Failed to apply Gemini patch, errors may occur with unrecognized enum values")
        
        # Initialize components
        self.mcp_client = None
        self.llm = None
        self.agent = None
        
        # MODIFICATION 1: Add separate lists for MCP and native tools
        # Why: Allows tracking of different tool types for proper handling
        self.mcp_tools = []      # Tools loaded from MCP server
        self.native_tools = []   # Native Python tools (e.g., GitLab)
        self.all_tools = []      # Combined list of all tools
        
        # Legacy support - keep 'tools' as alias to 'all_tools'
        self.tools = self.all_tools
        
        self.checkpointer = MemorySaver()
        
        # Initialize handlers
        self.resource_handler = ResourceHandler(self.config)
        self.tool_handler = ToolHandler(self.config)
        
        # Initialize graph visualization tool (will be set after agent init)
        self.graph_viz_tool = None
        
        # Track initialization state
        self._initialized = False
        
        # Track which threads have had resources injected
        self._thread_resources_injected: Dict[str, bool] = {}
    
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
            self.llm_for_visualization = base_llm.with_structured_output(
                StructuredAgentResponse
            )
            
            # Keep base LLM for agent use (will bind tools later)
            self.llm = base_llm
            
            self.logger.info(f"Gemini LLM initialized with model: {self.config.agent_model}")
            self.logger.info("Structured output configured for visualization responses")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini LLM: {e}")
            raise
    
    async def _load_tools(self):
        """Load tools from MCP server and native tools"""
        self.logger.debug("Loading tools from MCP server")
        
        try:
            # EXISTING CODE: Load MCP tools as before
            self.mcp_tools = await self.mcp_client.get_tools()
            tool_count = len(self.mcp_tools) if self.mcp_tools else 0
            self.logger.info(f"Loaded {tool_count} MCP tools")
            
            if self.mcp_tools:
                tool_names = [tool.name if hasattr(tool, 'name') else str(tool) 
                             for tool in self.mcp_tools]
                self.logger.debug(f"Available MCP tools: {tool_names}")
                # DEBUG: Check specifically for execute_query_mherb
                mherb_tools = [t for t in tool_names if 'mherb' in str(t).lower()]
                self.logger.debug(f"[DEBUG] MHerb related tools: {mherb_tools}")
            
        except Exception as e:
            self.logger.error(f"Failed to load MCP tools: {e}")
            self.logger.warning("Continuing with no MCP tools")
            self.mcp_tools = []
        
        # MODIFICATION 2: Add native tools loading
        # Why: Loads GitLab and other native tools when environment is configured
        self._load_native_tools()
        
        # MODIFICATION 3: Combine all tools into single list
        # Why: Provides unified access to all tools regardless of type
        self.all_tools = self.mcp_tools + self.native_tools
        total_count = len(self.all_tools)
        self.logger.info(f"Total tools available: {total_count}")
        
        # Update legacy 'tools' reference
        self.tools = self.all_tools
    
    def _load_native_tools(self):
        """Load native Python tools based on environment configuration"""
        # NEW METHOD: Initializes native tools
        # Why: Separates native tool loading logic for maintainability
        self.native_tools = []
        
        # Load GitLab tool if token is available from config
        if self.config.gitlab_token:
            try:
                # Create GitLab tool instance with token from config
                gitlab_tool = GitLabIssueTool(
                    access_token=self.config.gitlab_token,
                    logger=self.logger
                )
                self.native_tools.append(gitlab_tool)
                self.logger.info("Loaded GitLab issue creation tool")
            except Exception as e:
                self.logger.error(f"Failed to load GitLab tool: {e}")
        else:
            self.logger.debug("GitLab token not found in configuration, skipping GitLab tool")
        
        # Log summary of loaded native tools
        native_count = len(self.native_tools)
        self.logger.info(f"Loaded {native_count} native tools")
        
        if self.native_tools:
            tool_names = [tool.name for tool in self.native_tools]
            self.logger.debug(f"Available native tools: {tool_names}")
    
    def _extract_latest_query_result(self, messages: List) -> Optional[Dict[str, Any]]:
        """
        Extract the latest query result that comes after the most recent HumanMessage.
        
        Args:
            messages: List of messages from the conversation
            
        Returns:
            The query result dict if found, None otherwise
        """
        query_result = None
        query_tool_pattern = re.compile(QUERY_TOOL_PATTERN)
        
        # Find the index of the latest HumanMessage
        latest_human_msg_index = -1
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                latest_human_msg_index = i
                break
        
        # If we found a HumanMessage, look for ToolMessages after it
        if latest_human_msg_index >= 0:
            for i in range(latest_human_msg_index + 1, len(messages)):
                msg = messages[i]
                if isinstance(msg, ToolMessage) and query_tool_pattern.match(msg.name):
                    # Skip error messages
                    if hasattr(msg, 'status') and msg.status == 'error':
                        continue
                    try:
                        result = json.loads(msg.content)
                        if result.get("rows") and len(result["rows"]) > 0:
                            query_result = result
                            # Continue to get the last query result after HumanMessage
                    except (json.JSONDecodeError, TypeError):
                        pass
        
        if query_result:
            self.logger.info("Query result captured successfully (after latest HumanMessage)")
        
        return query_result
    
    async def _visualization_node(self, state: AgentState) -> AgentState:
        """
        Analyze conversation and query results for visualization needs.
        
        This node:
        1. Examines the conversation history
        2. Analyzes any query results from tool messages
        3. Makes structured decisions about visualization
        4. Appends a visualization instruction message if needed
        """
        # Log memory access for debugging
        self.logger.debug(f"[MEMORY_ACCESS] Agent: visualization_node, Action: analyzing")
        
        # Prepare enhanced messages with system context
        messages = state["messages"]
        enhanced_messages = [SystemMessage(content=VISUALIZATION_SYSTEM_PROMPT)] + messages
        
        # Extract query result that comes after the latest HumanMessage
        query_result = self._extract_latest_query_result(messages)
        
        # Add query result context if available
        if query_result:
            result_summary = self._format_query_result_summary(query_result)
            enhanced_messages.append(SystemMessage(content=result_summary))
        
            try:
                # Invoke structured LLM for visualization decision
                structured_response = await self.llm_for_visualization.ainvoke(enhanced_messages)
                
                # Log decision
                self.logger.info(f"Visualization decision - Should visualize: {structured_response.should_visualize}")
                if structured_response.should_visualize and structured_response.chart_config:
                    self.logger.info(f"Chart type selected: {structured_response.chart_config.chart_type}")
                    
                    # Format user-friendly response
                    viz_config = structured_response.chart_config.model_dump()
                    response = f"I've created a {structured_response.chart_config.chart_type} chart "
                    if structured_response.chart_config.title:
                        response += f"titled '{structured_response.chart_config.title}' "
                    response += "to visualize the data. "
                    response += structured_response.content if structured_response.content else "The chart shows the query results clearly."
                    
                    # Generate the actual visualization
                    graph_data = None
                    if query_result and self.graph_viz_tool:
                        try:
                            graph_data = await self._handle_visualization_with_config(
                                query_result,
                                viz_config,
                                "default"
                            )
                            self.logger.info("Visualization generated successfully")
                        except Exception as e:
                            self.logger.error(f"Visualization generation failed: {e}")
                    
                    # Return complete message with visualization data in state
                    return {
                        "messages": [AIMessage(content=response)],
                        "graph_data": graph_data,
                        "query_result": query_result
                    }
                else:
                    # No visualization needed, just return the content
                    return {"messages": [AIMessage(content=structured_response.content)]}
                
            except Exception as e:
                self.logger.error(f"Visualization node failed: {e}", exc_info=True)
                # Return error message
                return {"messages": [AIMessage(content="I encountered an error while analyzing visualization needs.")]}
            finally:
                self.logger.debug(f"[MEMORY_COMPLETE] Agent: visualization_node")
    
    def _format_query_result_summary(self, query_result: Dict[str, Any]) -> str:
        """Format query result summary for context"""
        result_summary = "\nDatabase Query Result Summary:\n"
        result_summary += f"- Rows returned: {len(query_result.get('rows', []))}\n"
        if query_result.get('rows'):
            result_summary += f"- Columns: {list(query_result['rows'][0].keys())}\n"
            result_summary += f"- Sample rows: {query_result['rows'][:3]}\n"
        return result_summary
    
    async def _create_agent(self):
        """Create custom agent with visualization capabilities"""
        self.logger.debug("Creating custom agent with visualization node")
        
        try:
            # CRITICAL: Bind tools to the LLM so it knows how to use them
            if self.all_tools:
                self.llm = self.llm.bind_tools(self.all_tools)
                self.logger.info(f"Bound {len(self.all_tools)} tools to LLM")
            
            # Create retry policy for tool execution (3 attempts)
            retry_policy = RetryPolicy(max_attempts=3)
            
            workflow = StateGraph(AgentState)
            
            # Create tool node using all available tools
            if self.all_tools:
                tool_node = ToolNode(self.all_tools)
            else:
                # Create a dummy tool node for consistency
                tool_node = lambda state: state
            
            # Create simple agent node - just LLM invocation
            async def agent_node(state: AgentState):
                """Main agent reasoning node - simple LLM invocation with tools"""
                messages = state["messages"]
                
                # DEBUG: Log the tools available to the agent
                self.logger.debug(f"[DEBUG] Agent invoking LLM with {len(self.all_tools)} tools available")
                if self.all_tools:
                    tool_names = [getattr(t, 'name', str(t)) for t in self.all_tools[:5]]  # Show first 5
                    self.logger.debug(f"[DEBUG] Sample tools: {tool_names}")
                    # Check specifically for execute_query tools
                    query_tools = [getattr(t, 'name', str(t)) for t in self.all_tools if 'execute_query' in str(getattr(t, 'name', str(t))).lower()]
                    self.logger.debug(f"[DEBUG] Query execution tools available: {query_tools}")
                
                # DEBUG: Log message content to understand what agent sees
                last_human_msg = None
                for msg in reversed(messages):
                    if isinstance(msg, HumanMessage):
                        last_human_msg = msg.content[:200]
                        break
                self.logger.debug(f"[DEBUG] Last user message: {last_human_msg}")
                
                response = await self.llm.ainvoke(messages)
                
                # DEBUG: Log what the agent decided
                self.logger.debug(f"[DEBUG] Agent response type: {type(response)}")
                if hasattr(response, 'tool_calls'):
                    self.logger.debug(f"[DEBUG] Agent tool_calls: {response.tool_calls}")
                if hasattr(response, 'content'):
                    self.logger.debug(f"[DEBUG] Agent content preview: {response.content[:200] if response.content else 'None'}")
                
                return {
                    "messages": [response],
                    "graph_data": None,
                    "query_result": None
                }
            
            # Define routing logic  
            def route_after_agent(state: AgentState) -> str:
                """Route after agent - check if we need tools or visualization"""
                last_message = state["messages"][-1]
                
                # Check for tool calls first
                if isinstance(last_message, AIMessage):
                    # Standard tools_condition check
                    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                        self.logger.debug(f"[DEBUG] Routing to tools - found {len(last_message.tool_calls)} tool calls")
                        for tc in last_message.tool_calls:
                            self.logger.debug(f"[DEBUG] Tool call: {tc.get('name', 'unknown')} with args: {tc.get('args', {})}") 
                        return "tools"
                    else:
                        self.logger.debug(f"[DEBUG] No tool calls in AIMessage")
                
                # After tools, check if we need visualization
                query_tool_pattern = re.compile(QUERY_TOOL_PATTERN)
                for msg in reversed(state["messages"][-10:] if len(state["messages"]) > 10 else state["messages"]):
                    if isinstance(msg, ToolMessage) and query_tool_pattern.match(msg.name):
                        # Skip error messages
                        if hasattr(msg, 'status') and msg.status == 'error':
                            continue
                        # Check if this is a fresh query result (not already visualized)
                        # Look for any viz message after this tool message
                        tool_msg_idx = state["messages"].index(msg)
                        has_viz_after = any(
                            isinstance(m, AIMessage) and m.additional_kwargs.get("should_visualize")
                            for m in state["messages"][tool_msg_idx:]
                        )
                        if not has_viz_after:
                            try:
                                result = json.loads(msg.content)
                                if result.get("rows") and len(result["rows"]) > 0:
                                    self.logger.debug("[DEBUG] Found query result, routing to visualization")
                                    return "visualize"
                            except (json.JSONDecodeError, TypeError):
                                pass
                
                return "end"  # Conversation complete
            
            # Add all nodes
            workflow.add_node("agent", agent_node)
            if self.all_tools:
                workflow.add_node("tools", tool_node, retry=retry_policy)
            workflow.add_node("visualize", self._visualization_node)
            
            # Set up edges - following the pattern: Agent -> Tools -> Agent -> Viz -> End
            workflow.set_entry_point("agent")
            
            # Tools always go back to agent
            if self.all_tools:
                workflow.add_edge("tools", "agent")
            
            # Visualization goes directly to end
            workflow.add_edge("visualize", END)
            
            # Agent routing logic
            workflow.add_conditional_edges(
                "agent", 
                route_after_agent,
                {
                    "tools": "tools",           # Execute tools
                    "visualize": "visualize",   # Generate visualization
                    "end": END                  # Complete conversation
                }
            )
            
            # Compile with checkpointer and recursion limit
            self.agent = workflow.compile(
                checkpointer=self.checkpointer,
                interrupt_before=[],
                interrupt_after=[]
            ).with_config(
                recursion_limit=AGENT_RECURSION_LIMIT  # Prevent infinite loops
            )
            
            self.logger.info(f"Custom agent created with recursion limit: {AGENT_RECURSION_LIMIT}")
            if self.all_tools:
                self.logger.info(f"Agent has {len(self.all_tools)} tools available")
            
        except Exception as e:
            self.logger.error(f"Failed to create custom agent: {e}", exc_info=True)
            raise
    
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
    
    
    # ============================================================================
    # Visualization Methods
    # ============================================================================
    
    async def _handle_visualization_with_config(
        self,
        query_result: Dict,
        chart_config: Dict,
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
    
    # ============================================================================
    # Main Public Method
    # ============================================================================
    
    async def _prepare_messages(self, message: str, thread_id: str) -> List:
        """
        Prepare messages for agent invocation.
        
        Args:
            message: User message to process
            thread_id: Thread ID for conversation context
            
        Returns:
            List of messages with system prompt and resources context if needed
        """
        messages = []
        
        # Check if this is the first message for this thread
        if thread_id not in self._thread_resources_injected:
            # Always add the main system prompt at the beginning of a thread
            system_prompt = SystemMessage(content=AGENT_SYSTEM_PROMPT)
            messages.append(system_prompt)

            # Inject resources context after system prompt
            resources_context = await self._format_resources_context()
            if resources_context:
                messages.append(resources_context)
                self.logger.info(f"Injected MCP resources context for thread: {thread_id}")
            
            # Mark thread as having resources injected
            self._thread_resources_injected[thread_id] = True
        
        # Add the user message
        messages.append(HumanMessage(content=message))
        
        return messages
    
    async def invoke(self, message: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        Invoke the agent with a message.
        
        Args:
            message: User message to process
            thread_id: Thread ID for conversation context (default: "default")
            
        Returns:
            Dict containing:
                - response: Agent response text (from last AIMessage)
                - query_result: Database query result if any execute_query_* tool was called
                - graph: Visualization data if generated (optional)
        """
        if not self._initialized:
            await self.initialize()
        
        self.logger.debug(f"Invoking agent with message: {message[:100]}...")
        
        try:
            # Prepare messages with system prompt and resources
            messages = await self._prepare_messages(message, thread_id)
            
            config = {"configurable": {"thread_id": thread_id}}
            
            response = await self.agent.ainvoke(
                {"messages": messages},
                config=config
            )
            
            # Extract the response from state and messages
            result = {
                "response": "",
                "query_result": response.get("query_result"),  # From state
                "graph": response.get("graph_data")  # From state
            }
            
            # Get the last AI message as response text
            all_messages = response.get("messages", [])
            for msg in reversed(all_messages):
                if isinstance(msg, AIMessage):
                    result["response"] = msg.content
                    break
            
            # If query_result wasn't set in state, extract from tool messages
            # if not result["query_result"]:
            #     query_tool_pattern = re.compile(QUERY_TOOL_PATTERN)
            #     for msg in reversed(all_messages):
            #         if isinstance(msg, ToolMessage) and query_tool_pattern.match(msg.name):
            #             if not (hasattr(msg, 'status') and msg.status == 'error'):
            #                 try:
            #                     result["query_result"] = json.loads(msg.content)
            #                     break
            #                 except (json.JSONDecodeError, TypeError):
            #                     pass
            
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
            # Create user message
            messages = [HumanMessage(content=message)]
            
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
