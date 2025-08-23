"""
LangChain-based LLM manager for multi-provider support (OpenRouter, Google Gemini).
"""

import logging
import time
from typing import List, Dict, Any, Optional
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.exceptions import LangChainException

from .config import config
from .models import (
    ChatMessage, ChatCompletionResponse, Choice, Usage, MessageRole
)
from .retry_utils import RetryConfig, retry_with_backoff, is_retryable_error

logger = logging.getLogger(__name__)


class LLMManager:
    """Manages LLM providers using LangChain for unified interface."""
    
    def __init__(self):
        """Initialize LLM manager with configured provider."""
        self.provider = config.llm_provider
        self.llm = self._initialize_llm()
        
        # Initialize retry configuration
        self.retry_config = RetryConfig(
            max_retries=config.max_retries,
            initial_delay=config.initial_retry_delay,
            max_delay=config.max_retry_delay,
            backoff_factor=config.retry_backoff_factor
        )
        
        logger.info(f"Initialized LLM manager with provider: {self.provider}")
        logger.info(f"Model: {self._get_model_name()}")
        logger.info(f"Retry config: max_retries={self.retry_config.max_retries}")
    
    def _initialize_llm(self) -> BaseChatModel:
        """Initialize the appropriate LLM based on configuration."""
        if self.provider == "openrouter":
            return ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=config.openrouter_api_key,
                model=config.openrouter_model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.llm_request_timeout,  # Configurable timeout
                max_retries=0,  # We handle retries ourselves
                # OpenRouter-specific headers
                model_kwargs={
                    "extra_headers": self._create_openrouter_headers()
                }
            )
        elif self.provider == "gemini":
            return ChatGoogleGenerativeAI(
                google_api_key=config.gemini_api_key,
                model=config.gemini_model,
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
                timeout=config.llm_request_timeout,  # Configurable timeout
                max_retries=0,  # We handle retries ourselves
                disable_streaming=True,  # CRITICAL: Disable streaming to prevent infinite loops with tool calling
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _get_model_name(self) -> str:
        """Get the model name for the current provider."""
        if self.provider == "openrouter":
            return config.openrouter_model
        elif self.provider == "gemini":
            return config.gemini_model
        else:
            return "unknown"
    
    def _create_openrouter_headers(self) -> Dict[str, str]:
        """Create headers for OpenRouter requests."""
        headers = {}
        if config.site_url:
            headers["HTTP-Referer"] = config.site_url
        if config.site_name:
            headers["X-Title"] = config.site_name
        return headers
    
    def _convert_messages_to_langchain(self, messages: List[ChatMessage]) -> List[BaseMessage]:
        """Convert our ChatMessage format to LangChain messages."""
        lc_messages = []
        
        for msg in messages:
            content = msg.content
            
            if msg.role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=content))
            elif msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=content))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=content))
            else:
                # Default to human message for unknown roles
                logger.warning(f"Unknown message role: {msg.role}, treating as user message")
                lc_messages.append(HumanMessage(content=content))
        
        return lc_messages
    
    def _convert_response_to_chat_completion(
        self, 
        response: AIMessage, 
        model: str,
        input_messages: List[ChatMessage]
    ) -> ChatCompletionResponse:
        """Convert LangChain response to our ChatCompletionResponse format."""
        
        # Create chat message from response
        chat_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response.content
        )
        
        # Create choice
        choice = Choice(
            index=0,
            message=chat_message,
            finish_reason="stop"  # LangChain doesn't always provide finish reason
        )
        
        # Create usage information (if available)
        usage = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage_data = response.usage_metadata
            usage = Usage(
                prompt_tokens=getattr(usage_data, 'input_tokens', 0),
                completion_tokens=getattr(usage_data, 'output_tokens', 0),
                total_tokens=getattr(usage_data, 'total_tokens', 0)
            )
        
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid4()}",
            created=int(time.time()),
            model=model,
            choices=[choice],
            usage=usage
        )
    
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
        Create a chat completion using the configured LLM provider.
        
        Args:
            messages: List of chat messages
            model: Model to use (ignored, uses configured model)
            max_tokens: Maximum tokens (ignored, uses configured value)
            temperature: Temperature (ignored, uses configured value)
            stream: Whether to stream response (not yet supported)
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletionResponse object
        """
        model_name = self._get_model_name()
        
        logger.info(f"Creating chat completion with {self.provider} provider")
        logger.debug(f"Input messages: {len(messages)}")
        
        if stream:
            logger.warning("Streaming not yet implemented, falling back to regular completion")
        
        # Convert messages to LangChain format
        lc_messages = self._convert_messages_to_langchain(messages)
        
        # Use retry decorator for the API call
        @retry_with_backoff(self.retry_config)
        async def _make_api_call():
            try:
                # Invoke the LLM
                response = await self.llm.ainvoke(lc_messages)
                
                # Convert response to our format
                return self._convert_response_to_chat_completion(
                    response, model_name, messages
                )
                
            except LangChainException as e:
                logger.warning(f"LangChain error: {e}")
                # Check if it's a retryable error
                if "rate limit" in str(e).lower() or "429" in str(e):
                    raise  # Let retry logic handle it
                elif "timeout" in str(e).lower():
                    raise  # Let retry logic handle it
                else:
                    # Non-retryable error
                    logger.error(f"Non-retryable LangChain error: {e}")
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
                    role=MessageRole.SYSTEM,
                    content=context_content
                )
                # Insert system message at the beginning or after existing system messages
                insert_index = 0
                for i, msg in enumerate(enhanced_messages):
                    if msg.role != MessageRole.SYSTEM:
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
        """Test the connection to the configured LLM provider."""
        try:
            test_messages = [ChatMessage(role=MessageRole.USER, content="Hello")]
            response = await self.create_chat_completion(
                messages=test_messages
            )
            
            # Validate response structure
            if response and response.choices and len(response.choices) > 0:
                logger.info(f"{self.provider} connection test successful")
                return True
            else:
                logger.error(f"{self.provider} connection test failed: Invalid response structure")
                return False
                
        except Exception as e:
            logger.error(f"{self.provider} connection test failed: {str(e)}")
            return False
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider."""
        return {
            "provider": self.provider,
            "model": self._get_model_name(),
            "temperature": config.temperature,
            "max_tokens": config.max_tokens
        }


# Global LLM manager instance
llm_manager = LLMManager()