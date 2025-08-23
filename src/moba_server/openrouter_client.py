"""
OpenRouter client integration using OpenAI SDK.
"""

import logging
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import OpenAI, RateLimitError, APIError
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from .config import config
from .models import ChatMessage, ChatCompletionResponse, ChatCompletionStreamResponse, Choice, StreamChoice, Usage
from .retry_utils import RetryConfig, retry_with_backoff, is_retryable_error

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for interacting with OpenRouter API using OpenAI SDK."""
    
    def __init__(self):
        """Initialize OpenRouter client."""
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.openrouter_api_key,
        )
        self.model = config.openrouter_model
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        
        # Initialize retry configuration
        self.retry_config = RetryConfig(
            max_retries=config.max_retries,
            initial_delay=config.initial_retry_delay,
            max_delay=config.max_retry_delay,
            backoff_factor=config.retry_backoff_factor
        )
        
        logger.info(f"Initialized OpenRouter client with model: {self.model}")
        logger.info(f"Retry config: max_retries={self.retry_config.max_retries}, "
                   f"initial_delay={self.retry_config.initial_delay}s")
    
    def _prepare_messages(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        """Convert ChatMessage objects to OpenAI format."""
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                **({"name": msg.name} if msg.name else {})
            }
            for msg in messages
        ]
    
    def _create_headers(self) -> Dict[str, str]:
        """Create headers for OpenRouter requests."""
        headers = {}
        if config.site_url:
            headers["HTTP-Referer"] = config.site_url
        if config.site_name:
            headers["X-Title"] = config.site_name
        return headers
    
    async def create_chat_completion(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Create a chat completion using OpenRouter with retry logic.
        
        Args:
            messages: List of chat messages
            model: Model to use (defaults to configured model)
            max_tokens: Maximum tokens (defaults to configured value)
            temperature: Temperature (defaults to configured value)
            stream: Whether to stream response
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletionResponse object
        """
        # Prepare parameters
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature
        
        # Convert messages to OpenAI format
        openai_messages = self._prepare_messages(messages)
        
        logger.info(f"Creating chat completion with model: {model}")
        logger.debug(f"Messages: {openai_messages}")
        
        # Use retry decorator for the API call
        @retry_with_backoff(self.retry_config)
        async def _make_api_call():
            try:
                # Create completion
                completion = self.client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=stream,
                    extra_headers=self._create_headers(),
                    **kwargs
                )
                
                if stream:
                    # Handle streaming response
                    return self._handle_streaming_response(completion, model)
                else:
                    # Handle regular response
                    return self._convert_completion_response(completion, model)
                    
            except RateLimitError as e:
                logger.warning(f"Rate limit error: {e}")
                raise
            except APIError as e:
                logger.warning(f"API error: {e}")
                # Check if it's a retryable error
                if hasattr(e, 'status_code') and e.status_code in {429, 500, 502, 503, 504}:
                    raise
                else:
                    # Non-retryable API error, don't retry
                    logger.error(f"Non-retryable API error: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error creating chat completion: {str(e)}")
                # Only retry if it's a known retryable error
                if is_retryable_error(e):
                    raise
                else:
                    # Don't retry unknown errors
                    raise
        
        return await _make_api_call()
    
    def _convert_completion_response(
        self,
        completion: ChatCompletion,
        model: str
    ) -> ChatCompletionResponse:
        """Convert OpenAI ChatCompletion to our response format with defensive programming."""
        if completion is None:
            raise ValueError("Completion response is None")
        
        choices = []
        completion_choices = getattr(completion, 'choices', None)
        if completion_choices:
            for i, choice in enumerate(completion_choices):
                if choice is None:
                    logger.warning(f"Choice {i} is None, skipping")
                    continue
                
                choice_message = getattr(choice, 'message', None)
                if choice_message is None:
                    logger.warning(f"Choice {i} message is None, using empty message")
                    chat_message = ChatMessage(role="assistant", content="")
                else:
                    # Safely extract message content
                    message_role = getattr(choice_message, 'role', 'assistant')
                    message_content = getattr(choice_message, 'content', None) or ""
                    
                    chat_message = ChatMessage(
                        role=message_role,
                        content=message_content
                    )
                
                finish_reason = getattr(choice, 'finish_reason', None)
                choices.append(Choice(
                    index=i,
                    message=chat_message,
                    finish_reason=finish_reason
                ))
        
        # Handle usage information safely
        usage = None
        completion_usage = getattr(completion, 'usage', None)
        if completion_usage:
            usage = Usage(
                prompt_tokens=getattr(completion_usage, 'prompt_tokens', 0),
                completion_tokens=getattr(completion_usage, 'completion_tokens', 0),
                total_tokens=getattr(completion_usage, 'total_tokens', 0)
            )
        
        # Safely extract other fields
        completion_id = getattr(completion, 'id', f"chatcmpl-{int(time.time())}")
        completion_created = getattr(completion, 'created', int(time.time()))
        
        return ChatCompletionResponse(
            id=completion_id,
            created=completion_created,
            model=model,
            choices=choices,
            usage=usage
        )
    
    async def _handle_streaming_response(
        self,
        completion_stream: AsyncGenerator[ChatCompletionChunk, None],
        model: str
    ) -> AsyncGenerator[ChatCompletionStreamResponse, None]:
        """Handle streaming chat completion response."""
        completion_id = None
        created_timestamp = int(time.time())
        
        async for chunk in completion_stream:
            if completion_id is None:
                completion_id = chunk.id
                
            choices = []
            for i, choice in enumerate(chunk.choices):
                delta = {}
                if choice.delta.role:
                    delta["role"] = choice.delta.role
                if choice.delta.content:
                    delta["content"] = choice.delta.content
                
                choices.append(StreamChoice(
                    index=i,
                    delta=delta,
                    finish_reason=choice.finish_reason
                ))
            
            yield ChatCompletionStreamResponse(
                id=completion_id or f"chatcmpl-{int(time.time())}",
                created=created_timestamp,
                model=model,
                choices=choices
            )
    
    async def create_completion_with_mcp_context(
        self,
        messages: List[ChatMessage],
        mcp_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Create a chat completion with additional MCP context.
        
        Args:
            messages: List of chat messages
            mcp_context: Additional context from MCP server
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletionResponse object
        """
        enhanced_messages = messages.copy()
        
        # Add MCP context as system message if provided
        if mcp_context:
            context_content = self._format_mcp_context(mcp_context)
            if context_content:
                system_message = ChatMessage(
                    role="system",
                    content=context_content
                )
                # Insert system message at the beginning or after existing system messages
                insert_index = 0
                for i, msg in enumerate(enhanced_messages):
                    if msg.role != "system":
                        insert_index = i
                        break
                else:
                    insert_index = len(enhanced_messages)
                
                enhanced_messages.insert(insert_index, system_message)
        
        return await self.create_chat_completion(enhanced_messages, **kwargs)
    
    def _format_mcp_context(self, mcp_context: Dict[str, Any]) -> str:
        """Format MCP context for inclusion in chat completion."""
        context_parts = []
        
        if "database_metadata" in mcp_context:
            metadata = mcp_context["database_metadata"]
            context_parts.append("Available database information:")
            context_parts.append(f"Database: {metadata.get('database_path', 'Unknown')}")
            
            if "tables" in metadata:
                context_parts.append("Tables and their structure:")
                for table_name, table_info in metadata["tables"].items():
                    context_parts.append(f"- {table_name}:")
                    if "columns" in table_info:
                        columns_data = table_info["columns"]
                        if isinstance(columns_data, dict):
                            columns = ", ".join(columns_data.keys())
                        elif isinstance(columns_data, list):
                            # Ensure all items in the list are strings
                            columns = ", ".join([str(col) for col in columns_data])
                        else:
                            columns = "Unknown"
                        context_parts.append(f"  Columns: {columns}")
                    if "row_count" in table_info:
                        context_parts.append(f"  Rows: {table_info['row_count']}")
        
        if "query_results" in mcp_context:
            results = mcp_context["query_results"]
            if results.get("success") and results.get("data"):
                context_parts.append(f"Query returned {len(results['data'])} rows:")
                # Include first few rows as examples
                for i, row in enumerate(results["data"][:3]):
                    row_str = str(row) if not isinstance(row, dict) else ", ".join([f"{k}: {v}" for k, v in row.items()])
                    context_parts.append(f"Row {i+1}: {row_str}")
                if len(results["data"]) > 3:
                    context_parts.append(f"... and {len(results['data']) - 3} more rows")
        
        if "available_tools" in mcp_context:
            tools = mcp_context["available_tools"]
            context_parts.append("Available database tools:")
            for tool in tools:
                context_parts.append(f"- {tool.get('name')}: {tool.get('description')}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    async def test_connection(self) -> bool:
        """Test the connection to OpenRouter API with retry logic."""
        try:
            test_messages = [ChatMessage(role="user", content="Hello")]
            response = await self.create_chat_completion(
                messages=test_messages,
                max_tokens=10
            )
            
            # Validate response structure
            if response and response.choices and len(response.choices) > 0:
                logger.info("OpenRouter connection test successful")
                return True
            else:
                logger.error("OpenRouter connection test failed: Invalid response structure")
                return False
                
        except Exception as e:
            logger.error(f"OpenRouter connection test failed: {str(e)}")
            return False