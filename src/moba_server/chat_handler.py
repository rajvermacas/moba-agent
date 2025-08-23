"""
Chat completion handler that uses MCPAgent from moba_agent.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from uuid import uuid4

from .models import (
    ChatMessage, ChatCompletionRequest, ChatCompletionResponse, 
    MessageRole, Choice
)
from moba_agent import MCPAgent
from moba_agent.config import Config

logger = logging.getLogger(__name__)


class ChatCompletionHandler:
    """Handles chat completions using MCPAgent."""
    
    def __init__(self):
        """Initialize the chat completion handler with MCPAgent."""
        self.agent = None
        self._init_task = None
        logger.info("Initialized chat completion handler with MCPAgent")
    
    async def initialize(self):
        """Initialize the MCPAgent asynchronously."""
        if self.agent is None:
            logger.info("Initializing MCPAgent")
            try:
                # Create config from environment
                config = Config()
                
                # Create and initialize MCPAgent
                self.agent = MCPAgent(config)
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
        request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Process chat completion request using MCPAgent.
        
        Args:
            request: Chat completion request
            
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
            
            # Use a thread_id based on the conversation (could be session-based in production)
            # For now, use a default thread_id
            thread_id = "default"
            
            logger.info(f"Invoking MCPAgent with message: {message_content[:100]}...")
            
            # Call MCPAgent
            response_content = await self.agent.invoke(
                message=message_content,
                thread_id=thread_id
            )
            
            # Create response in OpenAI format
            response = ChatCompletionResponse(
                id=f"chatcmpl-{uuid4()}",
                created=int(time.time()),
                model=request.model,  # Default model from MCPAgent
                choices=[Choice(
                    index=0,
                    message=ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=response_content
                    ),
                    finish_reason="stop"
                )]
            )
            
            logger.info("Successfully processed chat completion with MCPAgent")
            return response
            
        except Exception as e:
            logger.error(f"Error processing chat completion: {str(e)}")
            
            # Return error response in OpenAI format
            error_message = f"I encountered an error processing your request: {str(e)}"
            
            error_response = ChatCompletionResponse(
                id=f"chatcmpl-error-{uuid4()}",
                created=int(time.time()),
                model=request.model or "gemini-2.5-flash",
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