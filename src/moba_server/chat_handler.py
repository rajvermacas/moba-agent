"""
Chat completion handler that uses MCPAgent from moba_agent.
"""

import logging
import time
import json
from typing import List, Dict, Any, Optional, Set
from uuid import uuid4

from .models import (
    ChatMessage, ChatCompletionRequest, ChatCompletionResponse, 
    MessageRole, Choice, MCPQueryResult
)
from moba_agent import MCPAgent
from moba_agent.config import Config

logger = logging.getLogger(__name__)


class ChatCompletionHandler:
    """Handles chat completions using MCPAgent."""
    
    def __init__(self):
        """Initialize the chat completion handler with MCPAgent."""
        self.agent = None
        self.config = None
        self._init_task = None
        # Session management
        self._active_sessions: Set[str] = set()
        self._session_counter = 0
        logger.info("Initialized chat completion handler with MCPAgent")
    
    async def initialize(self):
        """Initialize the MCPAgent asynchronously."""
        if self.agent is None:
            logger.info("Initializing MCPAgent")
            try:
                # Create config from environment
                self.config = Config()
                
                # Create and initialize MCPAgent
                self.agent = MCPAgent(self.config)
                await self.agent.initialize()
                
                logger.info("MCPAgent initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize MCPAgent: {str(e)}")
                raise
    
    async def ensure_initialized(self):
        """Ensure the handler is initialized before use."""
        if self.agent is None:
            await self.initialize()
    
    async def process_chat_completion(
        self,
        request: ChatCompletionRequest,
        thread_id: Optional[str] = None
    ) -> ChatCompletionResponse:
        """
        Process chat completion request using MCPAgent.
        
        Args:
            request: Chat completion request
            thread_id: Optional thread ID for session management. If not provided, creates a new session.
            
        Returns:
            Chat completion response
        """
        try:
            # Ensure agent is initialized
            await self.ensure_initialized()
            
            logger.info(f"Processing chat completion with {len(request.messages)} messages")
            
            # Get the latest user message
            user_message = self._get_latest_user_message(request.messages)
            if not user_message:
                raise ValueError("No user message found in request")
            
            # Convert full conversation to a single prompt if needed
            # MCPAgent expects a single message string
            # For now, we'll just use the latest user message
            # Note: Using single-message approach for simplicity
            # Full conversation history support can be added if needed
            message_content = user_message.content
            
            # Generate or use provided thread_id for session management
            if thread_id is None:
                # Generate a new thread_id for this session
                thread_id = self._generate_thread_id()
                logger.info(f"Created new session with thread_id: {thread_id}")
            elif thread_id not in self._active_sessions:
                # Register existing thread_id
                self._active_sessions.add(thread_id)
                logger.info(f"Registered existing thread_id: {thread_id}")
            
            logger.info(f"Invoking MCPAgent with message: {message_content[:100]}...")
            
            # Call MCPAgent with query tracking
            agent_result = await self.agent.invoke(
                message=message_content,
                thread_id=thread_id
            )
            
            # Extract response, query result, AND graph data
            raw_response = agent_result.get("response", "")
            
            # Fix: Ensure response_content is always a string for ChatMessage validation
            if isinstance(raw_response, list):
                # If response is a list, join it into a string
                response_content = " ".join(str(item) for item in raw_response if item)
                if not response_content:  # If all items were empty
                    response_content = "I've processed your request."
            elif isinstance(raw_response, str):
                response_content = raw_response
            else:
                # Handle any other types by converting to string
                response_content = str(raw_response) if raw_response else "I've processed your request."
            raw_query_result = agent_result.get("query_result")
            graph_data = agent_result.get("graph")  # NEW: Extract graph data
            
            # Transform query result to UI-expected format
            transformed_query_result = None
            if raw_query_result:
                logger.info("Transforming raw query result to UI format")
                try:
                    # Transform MCP query result format to UI format
                    transformed_query_result = MCPQueryResult(
                        success=True,
                        data=raw_query_result.get("rows", []),  # Rename 'rows' to 'data'
                        columns=raw_query_result.get("columns", []),
                        row_count=raw_query_result.get("row_count", 0),
                        query=raw_query_result.get("query", ""),
                        # execution_time=0  # Optional field, set to 0 for now
                    )
                    logger.info(f"Successfully transformed query result with {len(raw_query_result.get('rows', []))} rows")
                except Exception as e:
                    logger.error(f"Failed to transform query result: {e}")
                    # Create error result
                    transformed_query_result = MCPQueryResult(
                        success=False,
                        error=f"Failed to transform query result: {str(e)}"
                    )
            
            # Create response in OpenAI format
            # Get model with fallback
            model_name = request.model
            logger.debug(f"Request model: {request.model}")
            logger.debug(f"Config available: {self.config is not None}")
            if self.config:
                logger.debug(f"Config agent_model: {self.config.agent_model}")
            
            if not model_name and self.config:
                model_name = self.config.agent_model
            if not model_name:
                # This shouldn't happen if config is properly initialized
                logger.warning("No model specified and config not available, using default")
                model_name = "gemini-2.5-flash"  # Emergency fallback
            
            logger.info(f"Using model: {model_name}")
            response = ChatCompletionResponse(
                id=f"chatcmpl-{uuid4()}",
                created=int(time.time()),
                model=model_name,
                choices=[Choice(
                    index=0,
                    message=ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=response_content
                    ),
                    finish_reason="stop",
                    query_result=transformed_query_result,
                    graph=graph_data  # NEW: Include graph data
                )]
            )
            
            if graph_data:
                logger.info(f"Response includes {graph_data['chart_type']} graph with {len(graph_data['data'])} data points")
            
            logger.info("Successfully processed chat completion with MCPAgent")
            return response
            
        except Exception as e:
            logger.error(f"Error processing chat completion: {str(e)}")
            logger.exception(e)
            
            # Return error response in OpenAI format
            error_message = f"I encountered an error processing your request: {str(e)}"
            
            # Get model with fallback
            model_name = request.model
            if not model_name and self.config:
                model_name = self.config.agent_model
            if not model_name:
                model_name = "gemini-2.5-flash"  # Final fallback
            
            error_response = ChatCompletionResponse(
                id=f"chatcmpl-error-{uuid4()}",
                created=int(time.time()),
                model=model_name,
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
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from MCPAgent."""
        await self.ensure_initialized()
        return await self.agent.get_available_tools()
    
    async def get_available_resources(self) -> List[Dict[str, Any]]:
        """Get available resources from MCPAgent."""
        await self.ensure_initialized()
        return await self.agent.get_available_resources()
    
    def _generate_thread_id(self) -> str:
        """Generate a unique thread ID for a new session."""
        self._session_counter += 1
        thread_id = f"session_{self._session_counter}_{uuid4().hex[:8]}"
        self._active_sessions.add(thread_id)
        return thread_id
    
    async def clear_session(self, thread_id: str) -> Dict[str, Any]:
        """
        Clear a specific chat session.
        
        Args:
            thread_id: The thread ID of the session to clear
            
        Returns:
            Dictionary with clear operation status
        """
        try:
            # Ensure agent is initialized
            await self.ensure_initialized()
            
            logger.info(f"Clearing session for thread_id: {thread_id}")
            
            # Check if thread_id exists
            if thread_id not in self._active_sessions:
                logger.warning(f"Thread ID {thread_id} not found in active sessions")
                return {
                    "success": False,
                    "message": f"Session with thread_id '{thread_id}' not found",
                    "thread_id": thread_id
                }
            
            # Clear the thread's resource injection tracking in MCPAgent
            if hasattr(self.agent, '_thread_resources_injected'):
                if thread_id in self.agent._thread_resources_injected:
                    del self.agent._thread_resources_injected[thread_id]
                    logger.info(f"Cleared resource injection tracking for thread_id: {thread_id}")
            
            # Note: LangGraph's MemorySaver doesn't provide a direct clear method per thread
            # The conversation history will be overwritten when a new conversation starts
            # For a complete clear, we would need to implement a custom checkpointer
            
            # Remove from active sessions
            self._active_sessions.discard(thread_id)
            
            logger.info(f"Successfully cleared session for thread_id: {thread_id}")
            return {
                "success": True,
                "message": f"Session cleared successfully",
                "thread_id": thread_id,
                "cleared_components": ["resource_injection", "active_session"]
            }
            
        except Exception as e:
            logger.error(f"Error clearing session for thread_id {thread_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Error clearing session: {str(e)}",
                "thread_id": thread_id
            }
    
    async def create_new_session(self) -> Dict[str, Any]:
        """
        Create a new chat session with a unique thread ID.
        
        Returns:
            Dictionary with new session information
        """
        try:
            # Ensure agent is initialized
            await self.ensure_initialized()
            
            # Generate new thread_id
            thread_id = self._generate_thread_id()
            
            logger.info(f"Created new session with thread_id: {thread_id}")
            return {
                "success": True,
                "thread_id": thread_id,
                "message": "New session created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating new session: {str(e)}")
            return {
                "success": False,
                "message": f"Error creating new session: {str(e)}"
            }
    
    async def get_active_sessions(self) -> Dict[str, Any]:
        """
        Get list of all active session thread IDs.
        
        Returns:
            Dictionary with active sessions information
        """
        try:
            return {
                "success": True,
                "active_sessions": list(self._active_sessions),
                "session_count": len(self._active_sessions)
            }
        except Exception as e:
            logger.error(f"Error getting active sessions: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting active sessions: {str(e)}"
            }
    
    async def test_integration(self) -> Dict[str, Any]:
        """
        Test the integration with MCPAgent.
        
        Returns:
            Test results
        """
        results = {
            "agent_initialized": False,
            "tools_available": False,
            "resources_available": False,
            "integration_test": False,
            "errors": []
        }
        
        try:
            # Ensure agent is initialized
            await self.ensure_initialized()
            results["agent_initialized"] = True
            
            # Check tools
            tools = await self.agent.get_available_tools()
            results["tools_available"] = len(tools) > 0
            results["tool_count"] = len(tools)
            
            # Check resources
            resources = await self.agent.get_available_resources()
            results["resources_available"] = len(resources) > 0
            results["resource_count"] = len(resources)
            
            # Test full integration
            if results["agent_initialized"]:
                test_request = ChatCompletionRequest(
                    messages=[
                        ChatMessage(
                            role=MessageRole.USER,
                            content="How many customers are in the database?"
                        )
                    ]
                )
                
                response = await self.process_chat_completion(test_request)
                if response and response.choices and response.choices[0].message.content:
                    results["integration_test"] = True
                    results["test_response"] = response.choices[0].message.content
            
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Integration test error: {str(e)}")
        
        return results


# Global chat handler instance
chat_handler = ChatCompletionHandler()