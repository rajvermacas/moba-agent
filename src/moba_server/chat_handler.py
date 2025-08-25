"""
Chat completion handler that uses MCPAgent from moba_agent.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Set
from uuid import uuid4

from .models import (
    ChatMessage, ChatCompletionRequest, ChatCompletionResponse, 
    MessageRole, Choice, MCPQueryResult, VisualizationSpec
)
from moba_agent import MCPAgent
from moba_agent.config import Config
from moba_agent.visualization import DataVisualizationAnalyzer
from moba_agent.data_transformer import DataTransformer

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
        # Visualization components
        self.visualization_analyzer = DataVisualizationAnalyzer()
        self.data_transformer = DataTransformer()
        logger.info("Initialized chat completion handler with MCPAgent and visualization support")
    
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
            # TODO: Consider how to pass full conversation history
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
            
            # Call MCPAgent
            response_content = await self.agent.invoke(
                message=message_content,
                thread_id=thread_id
            )
            
            # Check for query results and process visualization
            query_result = None
            visualization = None
            
            if isinstance(response_content, str):
                # Detect if response contains a query result
                detected_result = self._detect_query_result(response_content)
                if detected_result:
                    # Process visualization
                    visualization = self._process_visualization(detected_result)
                    
                    # Create MCPQueryResult
                    query_result = MCPQueryResult(
                        success=True,
                        data=detected_result.get('rows', []),
                        columns=detected_result.get('columns', []),
                        row_count=detected_result.get('row_count', len(detected_result.get('rows', []))),
                        query=detected_result.get('query', ''),
                        visualization=visualization
                    )
                    logger.info("Query result detected and visualization processed")
            
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
            
            # Build choice with optional visualization
            choice_data = {
                "index": 0,
                "message": ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=response_content
                ),
                "finish_reason": "stop"
            }
            
            # Add query result if detected
            if query_result:
                choice_data["query_result"] = query_result
            
            # Add visualization if processed
            if visualization:
                choice_data["visualization"] = visualization
            
            response = ChatCompletionResponse(
                id=f"chatcmpl-{uuid4()}",
                created=int(time.time()),
                model=model_name,
                choices=[Choice(**choice_data)]
            )
            
            logger.info("Successfully processed chat completion with MCPAgent")
            return response
            
        except Exception as e:
            logger.error(f"Error processing chat completion: {str(e)}")
            
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
    
    def _detect_query_result(self, response_content: str) -> Optional[Dict[str, Any]]:
        """
        Detect if response contains a query result from execute_query_mherb.
        
        Args:
            response_content: The response content from MCPAgent
            
        Returns:
            Query result dictionary if found, None otherwise
        """
        try:
            # Check if response mentions query execution
            if "execute_query" not in response_content.lower() and "query result" not in response_content.lower():
                return None
            
            # Try to extract JSON from response
            import re
            import json
            
            # Look for JSON pattern with columns and rows
            json_patterns = [
                r'\{[^{}]*"columns"[^{}]*"rows"[^{}]*\}',
                r'\{[^}]*"data"[^}]*"columns"[^}]*\}'
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response_content, re.DOTALL)
                for match in matches:
                    try:
                        # Clean up the match
                        cleaned = match.replace('\n', ' ').strip()
                        query_result = json.loads(cleaned)
                        
                        # Validate structure
                        if 'columns' in query_result and 'rows' in query_result:
                            logger.info(f"Detected query result with {len(query_result.get('rows', []))} rows")
                            return query_result
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting query result: {e}")
            return None
    
    def _process_visualization(self, query_result: Dict[str, Any]) -> Optional[VisualizationSpec]:
        """
        Process query result to generate visualization specification.
        
        Args:
            query_result: Query result dictionary with columns and rows
            
        Returns:
            VisualizationSpec if successful, None otherwise
        """
        try:
            logger.info("Processing visualization for query result")
            
            # Analyze query result
            viz_spec = self.visualization_analyzer.analyze_query_result(query_result)
            
            # Transform data for visualization
            if viz_spec and 'chart_type' in viz_spec:
                chart_data = self.data_transformer.transform_for_chart(
                    query_result,
                    viz_spec['chart_type'],
                    viz_spec.get('config', {})
                )
                
                # Update viz_spec with transformed data
                viz_spec['data'] = chart_data
            
            logger.info(f"Generated {viz_spec.get('chart_type', 'unknown')} visualization")
            
            # Convert to VisualizationSpec model
            return VisualizationSpec(
                chart_type=viz_spec.get('chart_type', 'table'),
                recommended=viz_spec.get('recommended', True),
                alternatives=viz_spec.get('alternatives', []),
                column_types=viz_spec.get('column_types', {}),
                config=viz_spec.get('config', {}),
                data=viz_spec.get('data'),
                metadata=viz_spec.get('metadata')
            )
            
        except Exception as e:
            logger.error(f"Error processing visualization: {e}")
            return None
    
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