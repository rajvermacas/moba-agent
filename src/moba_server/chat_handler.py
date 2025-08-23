"""
Chat completion handler that orchestrates OpenRouter LLM and MCP database queries.
"""

import asyncio
import logging
import re
import time
import json
from typing import List, Dict, Any, Optional, Tuple, TypedDict
from uuid import uuid4

from langchain.tools import Tool
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage

from .models import (
    ChatMessage, ChatCompletionRequest, ChatCompletionResponse, 
    MessageRole, MCPQueryResult
)
from .llm_manager import llm_manager
from .mcp_aggregator import MCPAggregator

logger = logging.getLogger(__name__)


class ChatCompletionHandler:
    """Handles chat completions with database query capabilities."""
    
    def __init__(self):
        """Initialize the chat completion handler."""
        self.llm_client = llm_manager
        self.mcp_aggregator = None
        self._init_task = None
        
        logger.info("Initialized chat completion handler with LLM-based decision system")
    
    async def initialize(self):
        """Initialize the MCP aggregator asynchronously."""
        if self.mcp_aggregator is None:
            logger.info("Initializing MCP aggregator")
            # Use absolute path for config file
            import os
            config_path = os.path.join(os.path.dirname(__file__), "mcp_servers_config.json")
            self.mcp_aggregator = MCPAggregator(config_path)
            await self.mcp_aggregator.connect_all()
            logger.info("MCP aggregator initialized successfully")
    
    async def ensure_initialized(self):
        """Ensure the handler is initialized before use."""
        if self.mcp_aggregator is None:
            if self._init_task is None:
                self._init_task = asyncio.create_task(self.initialize())
            await self._init_task
    
    async def _build_resource_catalog(self) -> Dict[str, Any]:
        """
        Build comprehensive resource catalog from all MCP servers.
        Resources are passed as-is to LLM for intelligent decision making.
        NO hardcoded domain logic or pattern matching!
        """
        logger.info("Building resource catalog from all MCP servers")
        catalog = {}
        
        try:
            # Get all resources (this method already exists)
            all_resources = await self.mcp_aggregator.read_all_resources()
            
            if not all_resources:
                logger.warning("No resources found from any MCP server")
                return catalog
            
            # Process each resource
            for resource_uri, content in all_resources.items():
                # Parse server name from URI format
                server_name = 'default'
                for server in self.mcp_aggregator.sessions.keys():
                    if resource_uri.startswith(f"{server}."):
                        server_name = server
                        break
                
                if server_name not in catalog:
                    catalog[server_name] = {
                        "resources": {},
                        "server_name": server_name
                    }
                
                # Store resources as-is, no processing or categorization
                catalog[server_name]["resources"][resource_uri] = content
                logger.debug(f"Added resource {resource_uri} to catalog for server {server_name}")
            
            logger.info(f"Built catalog with {len(all_resources)} resources from {len(catalog)} servers")
            
        except Exception as e:
            logger.error(f"Error building resource catalog: {str(e)}")
            logger.exception("Full error trace:")
        
        return catalog
    
    async def _extract_schema_info(self) -> Dict[str, Any]:
        """Extract database schema information from MCP resources dynamically."""
        schema_info = {
            "tables": [],
            "relationships": [],
            "sample_queries": [],
            "example_queries": []
        }
        
        try:
            all_resources = await self.mcp_aggregator.read_all_resources()
            
            for resource_uri, content in all_resources.items():
                # Check if this is a metadata resource
                if 'metadata' in resource_uri.lower():
                    # The content is already parsed by read_all_resources
                    # It comes from contents[0].text and is JSON parsed
                    if isinstance(content, dict) and 'tables' in content:
                        # Extract table names
                        schema_info["tables"] = list(content.get('tables', {}).keys())
                        
                        # Extract relationships
                        schema_info["relationships"] = content.get('relationships', [])
                        
                        # Extract example analytical queries
                        schema_info["example_queries"] = content.get('example_analytical_queries', [])
                        
                        # Extract sample queries from each table
                        for table_name, table_info in content.get('tables', {}).items():
                            if 'sample_queries' in table_info:
                                schema_info["sample_queries"].extend(table_info['sample_queries'])
                        
                        logger.info(f"Extracted schema with {len(schema_info['tables'])} tables: {', '.join(schema_info['tables'])}")
                        logger.debug(f"Full schema info extracted:\n{json.dumps(schema_info, indent=2)[:1500]}...")
                        break
                        
        except Exception as e:
            logger.error(f"Error extracting schema: {str(e)}")
            logger.exception("Full error trace:")
        
        logger.info(f"Schema extraction completed - tables: {schema_info['tables']}")
        return schema_info
    
    async def _create_langchain_tools(self) -> List[Tool]:
        """
        Convert MCP tools to LangChain tools with FULL resource context.
        NO domain logic - let LLM decide based on resources!
        """
        logger.info("Creating LangChain tools from MCP tools")
        tools = []
        
        try:
            # Get all resources for context
            all_resources = await self.mcp_aggregator.read_all_resources()
            logger.info(f"Fetched {len(all_resources)} resources for tool context")
            
            # Create a tool for each MCP tool
            for tool_name in self.mcp_aggregator.list_tools():
                tool_info = self.mcp_aggregator.get_tool_info(tool_name)
                
                # Extract server name from tool
                server_name = tool_name.split('.')[0] if '.' in tool_name else 'default'
                
                # Get all resources for this server
                server_resources = {
                    uri: content 
                    for uri, content in all_resources.items() 
                    if uri.startswith(f"{server_name}.")
                }
                
                # Create rich description with ALL resource information
                resource_json = json.dumps(server_resources, indent=2)
                # Truncate for token limits if needed
                if len(resource_json) > 2000:
                    resource_json = resource_json[:2000] + "\n... [truncated]"
                
                description = f"""Tool: {tool_name}
Server: {server_name}
Base Description: {tool_info.get('description', 'MCP tool') if tool_info else 'MCP tool'}

Available Resources for this tool:
{resource_json}

The LLM should analyze these resources to understand what data this tool can access.
Use this tool when the user's query relates to the data described in these resources."""
                
                logger.info(f"Created tool description for {tool_name}")
                logger.debug(f"Tool description content (first 500 chars):\n{description[:500]}...")
                logger.debug(f"Resource JSON content (first 1000 chars):\n{resource_json[:1000]}...")
                
                logger.debug(f"Creating LangChain tool for {tool_name}")
                
                # Create the async function that will call the MCP tool
                async def create_tool_func(tool_name=tool_name):
                    async def execute_tool(query: str = None, **kwargs):
                        """Generic execution - no assumptions about tool type!"""
                        # Combine query with other kwargs if present
                        if query:
                            kwargs['query'] = query
                        logger.info(f"Executing tool {tool_name} with args: {kwargs}")
                        try:
                            result = await self.mcp_aggregator.call_tool(tool_name, kwargs)
                            formatted = self._format_mcp_tool_result(result)
                            logger.info(f"Tool {tool_name} execution completed successfully")
                            return formatted
                        except Exception as e:
                            logger.error(f"Error executing tool {tool_name}: {str(e)}")
                            return f"Error executing tool: {str(e)}"
                    return execute_tool
                
                # Create the tool with the async function
                tool_func = await create_tool_func(tool_name)
                
                # Create Tool instance
                # Need to capture tool_func in closure properly
                def make_sync_func(async_func):
                    def sync_wrapper(**kwargs):
                        return asyncio.run(async_func(**kwargs))
                    return sync_wrapper
                
                tool = Tool(
                    name=tool_name.replace('.', '_'),  # Replace dots for compatibility
                    description=description,
                    func=make_sync_func(tool_func),
                    coroutine=tool_func
                )
                
                tools.append(tool)
                logger.debug(f"Added tool {tool_name} to LangChain tools")
            
            logger.info(f"Created {len(tools)} LangChain tools")
            
        except Exception as e:
            logger.error(f"Error creating LangChain tools: {str(e)}")
            logger.exception("Full error trace:")
        
        return tools
    
    def _format_mcp_tool_result(self, result: Any) -> str:
        """Format any MCP result for LLM consumption."""
        logger.debug(f"Formatting MCP result of type: {type(result)}")
        
        try:
            if hasattr(result, 'content'):
                # Handle MCP CallToolResult
                if result.content and hasattr(result.content[0], 'text'):
                    text_content = result.content[0].text
                    # Try to parse as JSON for better formatting
                    try:
                        data = json.loads(text_content)
                        formatted = json.dumps(data, indent=2)
                        logger.debug("Formatted MCP result as JSON")
                        return formatted
                    except json.JSONDecodeError:
                        logger.debug("MCP result is plain text")
                        return text_content
                return str(result.content)
            elif isinstance(result, dict):
                formatted = json.dumps(result, indent=2)
                logger.debug("Formatted dict result as JSON")
                return formatted
            else:
                logger.debug("Returning string representation of result")
                return str(result)
        except Exception as e:
            logger.error(f"Error formatting result: {str(e)}")
            return str(result)
    
    class GraphState(TypedDict):
        """State for the LangGraph workflow."""
        messages: List[BaseMessage]
        tool_result: Optional[str]
        final_answer: str
        retry_count: int
        last_error: Optional[str]
        intermediate_steps: List[Dict]
    
    async def _call_tool_node(self, state: GraphState) -> GraphState:
        """Execute appropriate MCP tool based on user query with retry logic."""
        
        # Ensure tools are available
        if not hasattr(self, 'tools') or not self.tools:
            logger.error("Tools not initialized in _call_tool_node")
            state["tool_result"] = None
            state["last_error"] = "Tools not initialized"
            state["retry_count"] = 3  # Skip retries
            return state
        
        # Get user's last message
        user_message = state["messages"][-1].content if state["messages"] else ""
        
        # Extract schema info (reuse existing method)
        schema_info = await self._extract_schema_info()
        
        # Initialize retry count if not present
        if "retry_count" not in state:
            state["retry_count"] = 0
        
        # Log the attempt
        logger.info(f"Tool execution attempt {state['retry_count'] + 1}/3 for query: {user_message[:100]}...")
        
        # Generate SQL query directly based on user message
        query_prompt = f"""
        Convert the following user question into a SQL query for the database.
        
        User Question: {user_message}
        Available Tables: {', '.join(schema_info.get('tables', []))}
        
        Return ONLY the SQL query, nothing else. For example:
        SELECT COUNT(*) FROM customers
        
        Do not include any explanation or markdown formatting.
        """
        
        # Add retry context if this is a retry
        if state["retry_count"] > 0 and state.get("last_error"):
            query_prompt += f"\n\nPrevious query failed with: {state['last_error']}\nPlease adjust your query."
        
        logger.debug(f"Requesting SQL query from LLM (attempt {state['retry_count'] + 1})")
        
        # Call LLM to generate SQL query
        response = await self.llm_client.create_chat_completion(
            messages=[
                ChatMessage(role=MessageRole.SYSTEM, content=query_prompt),
                ChatMessage(role=MessageRole.USER, content=user_message)
            ],
            temperature=0.1,
            max_tokens=200
        )
        
        # Check if response is valid
        if not response or not response.choices or not response.choices[0].message:
            raise ValueError("No response from LLM")
        
        # Get the SQL query directly
        query = response.choices[0].message.content
        logger.info(f"Generated SQL query: {query}")
        
        if not query:
            raise ValueError("Empty query from LLM")
        
        # Clean up the query (remove any markdown or extra text)
        query = query.strip()
        if query.startswith("```"):
            # Remove markdown code blocks
            lines = query.split("\n")
            query = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:])
            query = query.strip()
        
        # Execute with the first available tool (should be mherb_execute_query)
        try:
            # Find the execute_query tool
            tool_name = None
            for tool in self.tools:
                if "execute_query" in tool.name or "mherb" in tool.name:
                    tool_name = tool.name
                    break
            
            if not tool_name:
                # Use the first tool if no specific one found
                tool_name = self.tools[0].name if self.tools else None
            
            if not tool_name:
                raise ValueError("No tools available")
            
            logger.info(f"Using tool: {tool_name}")
            logger.debug(f"Executing query: {query}")
            
            # Find and execute the tool
            tool_executed = False
            for tool in self.tools:
                if tool.name == tool_name:
                    logger.info(f"Executing tool {tool.name} with query: {query[:100]}...")
                    result = await tool.coroutine(query=query)
                    state["tool_result"] = result
                    tool_executed = True
                    logger.info(f"Tool execution successful, result length: {len(str(result))}")
                    break
            
            if not tool_executed:
                raise ValueError(f"Tool {tool_name} not found in available tools")
                
        except Exception as e:
            logger.error(f"Tool execution failed (attempt {state['retry_count'] + 1}): {e}")
            state["tool_result"] = None
            state["last_error"] = str(e)
            state["retry_count"] += 1
            
            # If we haven't exceeded retry limit, the graph will retry
            if state["retry_count"] < 3:
                logger.info(f"Will retry tool execution (attempt {state['retry_count'] + 1}/3)")
        
        return state
    
    async def _generate_answer_node(self, state: GraphState) -> GraphState:
        """Generate final answer based on tool results."""
        
        user_message = state["messages"][-1].content if state["messages"] else ""
        tool_result = state.get("tool_result", None)
        
        # Log the intermediate steps for debugging
        state["intermediate_steps"].append({
            "node": "generate_answer",
            "tool_result_received": bool(tool_result),
            "retry_count": state.get("retry_count", 0)
        })
        
        logger.info(f"Generating final answer. Tool result available: {bool(tool_result)}")
        logger.debug(f"Intermediate steps so far: {state['intermediate_steps']}")
        
        if tool_result:
            # Format successful result
            prompt = f"""
            User asked: {user_message}
            
            Query result:
            {tool_result}
            
            Provide a clear, formatted answer to the user's question.
            """
            logger.info("Formatting successful query results")
        else:
            # Handle no results after retries
            prompt = f"""
            User asked: {user_message}
            
            No data was found after {state.get('retry_count', 0)} attempts.
            Last error: {state.get('last_error', 'No specific error')}
            
            Provide a helpful response explaining what might have gone wrong.
            """
            logger.warning(f"No results after {state.get('retry_count', 0)} attempts")
        
        # Generate response
        logger.debug("Calling LLM to generate final response")
        response = await self.llm_client.create_chat_completion(
            messages=[
                ChatMessage(role=MessageRole.USER, content=prompt)
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        state["final_answer"] = response.choices[0].message.content
        
        # Final logging
        logger.info(f"Graph execution complete. Total steps: {len(state['intermediate_steps'])}")
        logger.debug(f"Complete execution trace: {json.dumps(state['intermediate_steps'], indent=2)}")
        
        return state
    
    async def _initialize_graph(self):
        """Initialize LangGraph with 2 nodes and retry logic."""
        logger.info("Initializing LangGraph workflow")
        
        try:
            # Keep existing tool creation logic
            self.tools = await self._create_langchain_tools()
            logger.info(f"Created {len(self.tools)} tools for LangGraph")
            
            if not self.tools:
                logger.warning("No tools available for graph")
                return
            
            # Define the graph
            workflow = StateGraph(self.GraphState)
            
            # Add nodes
            workflow.add_node("call_tool", self._call_tool_node)
            workflow.add_node("generate_answer", self._generate_answer_node)
            
            # Add conditional edge for retry logic
            def should_retry(state: self.GraphState) -> str:
                """Determine if we should retry or proceed to answer generation."""
                if state.get("tool_result") is None and state.get("retry_count", 0) < 3:
                    logger.info(f"Tool failed, retrying (attempt {state.get('retry_count', 0) + 1}/3)")
                    return "call_tool"  # Retry
                else:
                    logger.info("Proceeding to answer generation")
                    return "generate_answer"  # Proceed to answer
            
            # Set entry point
            workflow.set_entry_point("call_tool")
            
            # Add conditional routing from call_tool
            workflow.add_conditional_edges(
                "call_tool",
                should_retry,
                {
                    "call_tool": "call_tool",  # Loop back for retry
                    "generate_answer": "generate_answer"  # Proceed to answer
                }
            )
            
            # Add edge from generate_answer to END
            workflow.add_edge("generate_answer", END)
            
            # Compile
            self.graph = workflow.compile()
            logger.info("LangGraph workflow compiled successfully")
            
        except Exception as e:
            logger.error(f"Error initializing graph: {str(e)}")
            logger.exception("Full error trace:")
            self.graph = None
    
    def _convert_to_langchain_messages(self, messages: List[ChatMessage]) -> List:
        """Convert ChatMessage list to LangChain message format for chat history."""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        lc_messages = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=msg.content))
            elif msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=msg.content))
        
        return lc_messages
    
    def _transform_mcp_result_to_query_result(self, mcp_result: Any) -> Optional[MCPQueryResult]:
        """
        Transform MCP CallToolResult to MCPQueryResult format.
        
        Args:
            mcp_result: Raw result from MCP call_tool
            
        Returns:
            MCPQueryResult object or None if transformation fails
        """
        try:
            logger.debug(f"Transforming MCP result of type: {type(mcp_result)}")
            
            # Check if it's already an MCPQueryResult
            if isinstance(mcp_result, MCPQueryResult):
                logger.debug("Result is already MCPQueryResult")
                return mcp_result
            
            # Handle CallToolResult from MCP
            if hasattr(mcp_result, 'content') and mcp_result.content:
                logger.debug("Processing CallToolResult with content")
                
                # Extract the JSON from TextContent
                text_content = mcp_result.content[0]
                if hasattr(text_content, 'text'):
                    # Parse the JSON string
                    data_json = json.loads(text_content.text)
                    logger.debug(f"Parsed JSON with keys: {data_json.keys()}")
                    
                    # Create MCPQueryResult
                    result = MCPQueryResult(
                        success=not getattr(mcp_result, 'isError', False),
                        data=data_json.get('rows', []),
                        columns=data_json.get('columns', []),
                        row_count=data_json.get('row_count', len(data_json.get('rows', []))),
                        error=None if not getattr(mcp_result, 'isError', False) else "Query execution failed"
                    )
                    
                    logger.info(f"Successfully transformed to MCPQueryResult with {result.row_count} rows")
                    return result
            
            # Handle structuredContent directly if available
            elif hasattr(mcp_result, 'structuredContent') and mcp_result.structuredContent:
                logger.debug("Processing CallToolResult with structuredContent")
                
                structured = mcp_result.structuredContent
                result = MCPQueryResult(
                    success=not getattr(mcp_result, 'isError', False),
                    data=structured.get('rows', []),
                    columns=structured.get('columns', []),
                    row_count=structured.get('row_count', len(structured.get('rows', []))),
                    error=None if not getattr(mcp_result, 'isError', False) else "Query execution failed"
                )
                
                logger.info(f"Successfully transformed from structuredContent with {result.row_count} rows")
                return result
            
            # If it's a dict-like object, try to use it directly
            elif isinstance(mcp_result, dict):
                logger.debug("Processing dict-like result")
                
                result = MCPQueryResult(
                    success=mcp_result.get('success', True),
                    data=mcp_result.get('data') or mcp_result.get('rows', []),
                    columns=mcp_result.get('columns', []),
                    row_count=mcp_result.get('row_count', len(mcp_result.get('data', []))),
                    error=mcp_result.get('error')
                )
                
                logger.info(f"Successfully transformed dict to MCPQueryResult")
                return result
            
            # Fallback: log warning and return None
            logger.warning(f"Could not transform MCP result of type {type(mcp_result)}")
            logger.debug(f"Result attributes: {dir(mcp_result) if mcp_result else 'None'}")
            return None
            
        except Exception as e:
            logger.error(f"Error transforming MCP result: {str(e)}")
            logger.debug(f"Failed result: {mcp_result}")
            return None
    
    async def process_chat_completion(
        self,
        request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Process chat using LangChain agent with resource-aware tools.
        
        Args:
            request: Chat completion request
            
        Returns:
            Chat completion response
        """
        try:
            # Ensure initialization
            await self.ensure_initialized()
            
            logger.info(f"Processing chat completion with {len(request.messages)} messages using LangGraph")
            
            # Initialize graph if not already done
            if not hasattr(self, 'graph') or self.graph is None:
                logger.info("Graph not initialized, initializing now")
                await self._initialize_graph()
                
                # If still no graph (no tools available), fall back to simple LLM response
                if not self.graph:
                    logger.warning("No graph available (no tools), falling back to simple LLM response")
                    return await self.llm_client.create_chat_completion(
                        messages=request.messages,
                        model=request.model,
                        max_tokens=request.max_tokens,
                        temperature=request.temperature,
                        stream=request.stream if request.stream is not None else False
                    )
            
            # Get user message
            user_message = self._get_latest_user_message(request.messages)
            if not user_message:
                raise ValueError("No user message found in request")
            
            logger.info(f"Processing user message: {user_message.content[:100]}...")
            
            # Convert all messages to LangChain format for the graph
            chat_history = self._convert_to_langchain_messages(request.messages)
            logger.debug(f"Including {len(chat_history)} messages in chat history")
            
            # Log start of graph execution
            logger.info(f"Starting LangGraph execution for query: {user_message.content[:100]}...")
            
            try:
                # Execute graph with retry logic built-in
                result = await self.graph.ainvoke({
                    "messages": chat_history,
                    "tool_result": None,
                    "final_answer": "",
                    "retry_count": 0,
                    "last_error": None,
                    "intermediate_steps": []
                })
                
                # Log completion
                logger.info("LangGraph execution completed successfully")
                logger.debug(f"Final intermediate steps: {json.dumps(result.get('intermediate_steps', []), indent=2)}")
                
                # Create response (reuse existing response creation logic)
                from .models import Choice
                response = ChatCompletionResponse(
                    id=f"chatcmpl-{uuid4()}",
                    created=int(time.time()),
                    model=request.model or self.llm_client._get_model_name(),
                    choices=[Choice(
                        index=0,
                        message=ChatMessage(
                            role=MessageRole.ASSISTANT,
                            content=result["final_answer"]
                        ),
                        finish_reason="stop"
                    )]
                )
                
                logger.info("Successfully processed chat completion with LangGraph")
                return response
                
            except Exception as graph_error:
                error_str = str(graph_error)
                logger.error(f"Graph execution error: {error_str}")
                
                # Check for specific Gemini errors
                if "invalid_api_key" in error_str.lower() or "401" in error_str:
                    logger.error("Gemini API key authentication failed")
                    # Provide user-friendly error message
                    error_msg = (
                        "Authentication failed with Gemini API. Please check that your "
                        "GEMINI_API_KEY is valid and active. You can get a key from: "
                        "https://ai.google.dev/gemini-api/docs/api-key"
                    )
                    
                    # Return error response in chat format
                    from .models import Choice
                    from .config import config
                    error_response = ChatCompletionResponse(
                        id=f"chatcmpl-{uuid4()}",
                        created=int(time.time()),
                        model=request.model or config.gemini_model,
                        choices=[Choice(
                            index=0,
                            message=ChatMessage(
                                role=MessageRole.ASSISTANT,
                                content=error_msg
                            ),
                            finish_reason="stop"
                        )]
                    )
                    return error_response
                
                # For other errors, log and fall back
                logger.exception("Full agent error trace:")
                
                # Fall back to simple LLM response on agent error
                logger.info("Falling back to simple LLM response due to agent error")
                return await self.llm_client.create_chat_completion(
                    messages=request.messages,
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    stream=request.stream if request.stream is not None else False
                )
            
        except Exception as e:
            logger.error(f"Error processing chat completion: {str(e)}")
            
            # Check if it's a rate limit error and provide appropriate response
            error_message = "I apologize, but I encountered an error processing your request."
            
            if "rate limit" in str(e).lower() or "429" in str(e) or "resourceexhausted" in str(e).lower() or "quota" in str(e).lower():
                error_message = ("I'm currently experiencing high demand and need to wait a moment before "
                               "processing your request. Please try again in a few seconds.")
            elif "timeout" in str(e).lower():
                error_message = ("Your request took too long to process. Please try again with a "
                               "simpler question or try again later.")
            elif "api" in str(e).lower():
                error_message = ("I'm having trouble connecting to the AI service. Please try again "
                               "in a moment.")
            else:
                error_message = f"I encountered an unexpected error: {str(e)}"
            
            # Return error response in OpenAI format
            from .models import Choice
            
            # Get the default model name from the LLM manager
            default_model = self.llm_client._get_model_name()
            
            error_response = ChatCompletionResponse(
                id=f"chatcmpl-error-{uuid4()}",
                created=int(time.time()),
                model=request.model or default_model,
                choices=[Choice(
                    index=0,
                    message=ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=error_message
                    ),
                    finish_reason="error"
                )]
            )
            return error_response
    
    def _get_latest_user_message(self, messages: List[ChatMessage]) -> Optional[ChatMessage]:
        """Get the latest user message from the conversation."""
        for message in reversed(messages):
            if message.role == MessageRole.USER:
                return message
        return None
    
    # DEPRECATED: The following methods are no longer used with LangChain agent implementation
    # They are kept here temporarily for reference and potential rollback
    '''
    async def _get_mcp_resources(self) -> Dict[str, Any]:
        """
        Get MCP resources fresh on every call (no caching).
        
        Returns:
            Dictionary containing database metadata and available resources
        """
        try:
            # Ensure aggregator is initialized
            await self.ensure_initialized()
            
            logger.info("Fetching fresh MCP resources (no caching)")
            
            # Fetch fresh resources
            resources = {}
            
            # Dynamically read all available resources
            try:
                logger.debug("Fetching all available resources dynamically...")
                all_resources = await self.mcp_aggregator.read_all_resources()
                
                # Process and categorize resources
                for resource_uri, content in all_resources.items():
                    logger.debug(f"Processing resource: {resource_uri}")
                    
                    # Check for metadata resources
                    if "metadata" in resource_uri.lower():
                        resources["database_metadata"] = content
                        if isinstance(content, dict):
                            table_count = len(content.get('tables', {}))
                            logger.info(f"Found metadata resource with {table_count} tables")
                            logger.debug(f"Tables: {list(content.get('tables', {}).keys())}")
                    
                    # Store all resources for context
                    # Remove server prefix for cleaner keys
                    clean_uri = resource_uri
                    for server_name in self.mcp_aggregator.sessions.keys():
                        if resource_uri.startswith(f"{server_name}."):
                            clean_uri = resource_uri[len(f"{server_name}."):]
                            break
                    
                    resources[f"resource_{clean_uri}"] = content
                
                # Ensure we have at least empty metadata if none found
                if "database_metadata" not in resources:
                    logger.warning("No metadata resource found in any server")
                    resources["database_metadata"] = {"tables": {}}
                    
                logger.info(f"Successfully fetched {len(all_resources)} resources from all servers")
                
            except Exception as e:
                logger.error(f"Error fetching resources dynamically: {str(e)}")
                # Fallback to empty resources
                resources["database_metadata"] = {"tables": {}}
            
            # Get available resources list
            try:
                logger.debug("Getting list of available resources...")
                resource_list = self.mcp_aggregator.list_resources()
                resources["available_resources"] = []
                
                for resource_uri in resource_list:
                    resource_info = self.mcp_aggregator.get_resource_info(resource_uri)
                    if resource_info:
                        resources["available_resources"].append({
                            "uri": resource_uri,
                            "name": resource_info.get('name', resource_uri),
                            "description": resource_info.get('description', ''),
                            "server": resource_info.get('server', 'unknown')
                        })
                
                logger.info(f"Listed {len(resources['available_resources'])} available resources")
            except Exception as e:
                logger.debug(f"Could not list resources: {str(e)}")
                resources["available_resources"] = []
            
            # Get available tools from aggregator
            try:
                logger.debug("Fetching available tools...")
                tools = self.mcp_aggregator.list_tools()
                resources["available_tools"] = [
                    {"name": tool, "info": self.mcp_aggregator.get_tool_info(tool)}
                    for tool in tools
                ]
                logger.info(f"Successfully fetched {len(tools)} available tools")
                for tool_data in resources["available_tools"]:
                    logger.debug(f"Tool: {tool_data['name']}")
            except Exception as e:
                logger.error(f"Failed to fetch tool list: {str(e)}")
                resources["available_tools"] = []
            
            logger.info(f"Completed fetching MCP resources: {len(resources)} resource types")
            
            return resources
            
        except Exception as e:
            logger.error(f"Critical error fetching MCP resources: {str(e)}")
            # Return empty resources on error
            return {
                "database_metadata": {},
                "available_resources": [],
                "available_tools": []
            }
    
    async def _needs_database_query_llm(self, content: str, resources: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Use LLM to determine if a message needs database access.
        
        Args:
            content: Message content to analyze
            resources: MCP resources for context
            
        Returns:
            Tuple of (needs_database, reasoning)
        """
        try:
            logger.info("Using LLM to determine database query need")
            
            # Prepare the decision prompt
            system_prompt = """You are a database query decision system. Analyze the user's query and the available database resources to determine if database access is needed.

Available Database Resources:
{}

Tables and Columns:
{}

Your task:
1. Analyze if the user's query requires database access
2. Consider the available tables and data
3. Return a JSON response with your decision

Response format:
{{
    "needs_database": true/false,
    "reasoning": "Brief explanation of your decision",
    "confidence": "high/medium/low"
}}""".format(
                json.dumps(resources.get("available_resources", []), indent=2),
                json.dumps(resources.get("database_metadata", {}).get("tables", {}), indent=2)
            )
            
            user_prompt = f"User Query: {content}\n\nDoes this query require database access?"
            
            # Create messages for LLM
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_prompt)
            ]
            
            logger.debug("Sending decision request to LLM")
            
            # Call LLM for decision
            response = await self.llm_client.create_chat_completion(
                messages=messages,
                model=None,  # Use default model
                max_tokens=200,
                temperature=0.1  # Low temperature for consistent decisions
            )
            
            # Parse response
            if response.choices and response.choices[0].message:
                response_content = response.choices[0].message.content
                logger.debug(f"LLM decision response: {response_content}")
                
                try:
                    # Try to parse as JSON
                    decision_data = json.loads(response_content)
                    needs_database = decision_data.get("needs_database", False)
                    reasoning = decision_data.get("reasoning", "No reasoning provided")
                    confidence = decision_data.get("confidence", "unknown")
                    
                    logger.info(f"LLM decision: needs_database={needs_database}, confidence={confidence}")
                    logger.debug(f"LLM reasoning: {reasoning}")
                    
                    return needs_database, reasoning
                    
                except json.JSONDecodeError:
                    # Fallback: Look for yes/no in response
                    logger.warning("Could not parse LLM response as JSON, using text analysis")
                    response_lower = response_content.lower()
                    needs_database = "yes" in response_lower or "true" in response_lower
                    return needs_database, response_content
            
            logger.warning("No valid response from LLM")
            return False, "No response from LLM"
            
        except Exception as e:
            logger.error(f"Error in LLM decision making: {str(e)}")
            return False, f"Error: {str(e)}"
    
    async def _needs_database_query(self, content: str) -> bool:
        """
        Determine if a message needs database access using LLM.
        
        Args:
            content: Message content to analyze
            
        Returns:
            True if database access is likely needed
        """
        logger.info(f"Analyzing if database query is needed for: {content[:100]}...")
        
        try:
            # First, get MCP resources for context
            logger.debug("Fetching MCP resources for decision context")
            resources = await self._get_mcp_resources()
            
            # Use LLM-based decision
            logger.info("Using LLM to determine database query need")
            needs_db, reasoning = await self._needs_database_query_llm(content, resources)
            
            # Log the decision
            logger.info(f"LLM decision: needs_database={needs_db}")
            logger.debug(f"LLM reasoning: {reasoning}")
            
            # If LLM says no but there's an explicit SQL query, override
            if not needs_db and self._extract_sql_query(content):
                logger.info("Override: Found explicit SQL query despite LLM decision")
                return True
            
            return needs_db
            
        except Exception as e:
            logger.error(f"LLM decision failed with error: {str(e)}")
            logger.warning("Defaulting to no database access due to LLM failure")
            
            # Default to no database access if LLM fails
            return False
    
    def _extract_sql_query(self, content: str) -> Optional[str]:
        """
        Extract explicit SQL query from message content.
        Only looks for SQL in code blocks or when explicitly marked.
        
        Args:
            content: Message content
            
        Returns:
            SQL query if found, None otherwise
        """
        logger.debug("Checking for explicit SQL queries in code blocks")
        
        # Look for SQL in markdown code blocks
        # Pattern 1: ```sql ... ```
        sql_block_match = re.search(r'```sql\s*(.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
        if sql_block_match:
            query = sql_block_match.group(1).strip()
            if query:
                logger.info(f"Found SQL in code block: {query[:50]}...")
                return query
        
        # Pattern 2: ``` SELECT ... ```  
        select_block_match = re.search(r'```\s*(SELECT.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
        if select_block_match:
            query = select_block_match.group(1).strip()
            if query:
                logger.info(f"Found SELECT query in code block: {query[:50]}...")
                return query
        
        # Pattern 3: Inline code with SQL
        inline_sql_match = re.search(r'`(SELECT[^`]+)`', content, re.IGNORECASE)
        if inline_sql_match:
            query = inline_sql_match.group(1).strip()
            if query:
                logger.info(f"Found inline SQL query: {query[:50]}...")
                return query
        
        logger.debug("No explicit SQL queries found in code blocks")
        return None
    
    async def _suggest_sql_query(
        self,
        user_question: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Use LLM to suggest an appropriate SQL query for the user's question.
        
        Args:
            user_question: The user's question
            metadata: Database metadata
            
        Returns:
            Suggested SQL query or None
        """
        if not metadata:
            return None
        
        try:
            # Create a prompt for SQL generation
            system_prompt = self._create_sql_generation_prompt(metadata)
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(
                    role=MessageRole.USER,
                    content=f"Generate a SQL query to answer this question: {user_question}"
                )
            ]
            
            response = await self.llm_client.create_chat_completion(
                messages=messages,
                max_tokens=200,
                temperature=0.1  # Low temperature for more deterministic SQL
            )
            
            if (response and 
                hasattr(response, 'choices') and 
                response.choices and 
                len(response.choices) > 0 and
                response.choices[0] and
                hasattr(response.choices[0], 'message') and
                response.choices[0].message and
                hasattr(response.choices[0].message, 'content') and
                response.choices[0].message.content):
                sql_content = response.choices[0].message.content.strip()
                
                # Extract SQL from the response
                query = self._extract_sql_from_response(sql_content)
                if query:
                    logger.info(f"LLM suggested query: {query}")
                    return query
            
        except Exception as e:
            logger.error(f"Error generating SQL suggestion: {str(e)}")
        
        return None
    
    def _create_sql_generation_prompt(self, metadata: Dict[str, Any]) -> str:
        """Create a prompt for SQL query generation."""
        prompt_parts = [
            "You are a SQL expert. Generate appropriate SELECT queries for the given database.",
            "Database information:",
        ]
        
        if "tables" in metadata:
            prompt_parts.append("Available tables:")
            for table_name, table_info in metadata["tables"].items():
                prompt_parts.append(f"- {table_name}")
                if "columns" in table_info:
                    columns_data = table_info["columns"]
                    if isinstance(columns_data, dict):
                        columns = list(columns_data.keys())
                    elif isinstance(columns_data, list):
                        # Ensure all items in the list are strings
                        columns = [str(col) for col in columns_data]
                    else:
                        columns = []
                    prompt_parts.append(f"  Columns: {', '.join(columns)}")
        
        prompt_parts.extend([
            "",
            "Rules:",
            "- Only generate SELECT statements",
            "- Use proper SQL syntax",
            "- Include only the SQL query in your response",
            "- Do not include explanations or markdown formatting",
            "- Limit results with LIMIT clause when appropriate"
        ])
        
        return "\n".join(prompt_parts)
    
    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """Extract SQL query from LLM response."""
        # Remove common formatting
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith('```'):
            lines = response.split('\n')
            if len(lines) > 2:
                response = '\n'.join(lines[1:-1])
        
        # Remove trailing semicolon and whitespace
        response = response.strip().rstrip(';').strip()
        
        # Check if it looks like a valid SELECT statement
        if response.upper().startswith('SELECT'):
            return response
        
        return None
    '''
    # END DEPRECATED METHODS
    
    async def test_integration(self) -> Dict[str, Any]:
        """
        Test the integration between OpenRouter and MCP.
        
        Returns:
            Test results
        """
        results = {
            "llm_connection": False,
            "mcp_connection": False,
            "integration_test": False,
            "errors": []
        }
        
        try:
            # Ensure aggregator is initialized
            await self.ensure_initialized()
            
            # Test LLM connection
            results["llm_connection"] = await self.llm_client.test_connection()
            
            # Test MCP connection (check if aggregator has any connected servers)
            results["mcp_connection"] = len(self.mcp_aggregator.sessions) > 0
            
            # Test full integration
            if results["llm_connection"] and results["mcp_connection"]:
                test_request = ChatCompletionRequest(
                    messages=[
                        ChatMessage(
                            role=MessageRole.USER,
                            content="How many customers are in the database?"
                        )
                    ]
                )
                
                response = await self.process_chat_completion(test_request)
                if (response and 
                    hasattr(response, 'choices') and 
                    response.choices and 
                    len(response.choices) > 0 and
                    response.choices[0] and
                    hasattr(response.choices[0], 'message') and
                    response.choices[0].message and
                    hasattr(response.choices[0].message, 'content') and
                    response.choices[0].message.content):
                    results["integration_test"] = True
                    results["test_response"] = response.choices[0].message.content
            
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Integration test error: {str(e)}")
        
        return results


# Global chat handler instance
chat_handler = ChatCompletionHandler()