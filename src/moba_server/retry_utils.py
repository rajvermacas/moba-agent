"""
Retry utilities with exponential backoff for handling rate limits and API failures.
"""

import asyncio
import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Type, Union, List
from openai import RateLimitError, APIError
from httpx import HTTPStatusError

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given retry attempt.
        
        Args:
            attempt: The retry attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        if attempt < 0:
            return 0.0
        
        # Calculate exponential backoff
        delay = min(
            self.initial_delay * (self.backoff_factor ** attempt),
            self.max_delay
        )
        
        # Add jitter to prevent thundering herd
        if self.jitter:
            # Add random jitter between 50% and 100% of calculated delay
            jitter_factor = 0.5 + (random.random() * 0.5)
            delay = delay * jitter_factor
        
        return delay


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        error: Exception to check
        
    Returns:
        True if the error should be retried
    """
    # OpenAI SDK rate limit errors
    if isinstance(error, RateLimitError):
        return True
    
    # OpenAI API errors that might be temporary
    if isinstance(error, APIError):
        # Check for specific status codes that are retryable
        if hasattr(error, 'status_code'):
            retryable_status_codes = {429, 500, 502, 503, 504}
            return error.status_code in retryable_status_codes
    
    # HTTP errors from httpx
    if isinstance(error, HTTPStatusError):
        retryable_status_codes = {429, 500, 502, 503, 504}
        return error.response.status_code in retryable_status_codes
    
    # Connection and timeout errors
    error_types = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )
    
    return isinstance(error, error_types)


def extract_retry_after(error: Exception) -> Optional[float]:
    """
    Extract Retry-After header value from error if available.
    
    Args:
        error: Exception that may contain retry information
        
    Returns:
        Retry delay in seconds, or None if not available
    """
    # Check OpenAI SDK errors
    if hasattr(error, 'response') and error.response:
        headers = getattr(error.response, 'headers', {})
        retry_after = headers.get('retry-after') or headers.get('Retry-After')
        
        if retry_after:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
    
    # Check httpx errors
    if isinstance(error, HTTPStatusError):
        retry_after = error.response.headers.get('retry-after')
        if retry_after:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
    
    return None


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Optional[List[Type[Exception]]] = None
):
    """
    Decorator to add exponential backoff retry logic to async functions.
    
    Args:
        config: Retry configuration. Uses default if None.
        retryable_exceptions: List of exception types to retry on.
                             If None, uses default retryable errors.
    
    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(config.max_retries + 1):  # +1 for initial attempt
                try:
                    return await func(*args, **kwargs)
                    
                except Exception as error:
                    last_error = error
                    
                    # Check if this error should be retried
                    should_retry = (
                        retryable_exceptions is None and is_retryable_error(error)
                    ) or (
                        retryable_exceptions is not None and 
                        isinstance(error, tuple(retryable_exceptions))
                    )
                    
                    # Don't retry on last attempt or non-retryable errors
                    if attempt >= config.max_retries or not should_retry:
                        logger.error(
                            f"Function {func.__name__} failed after {attempt + 1} attempts: {error}"
                        )
                        raise error
                    
                    # Calculate delay for this attempt
                    delay = config.calculate_delay(attempt)
                    
                    # Check for server-specified retry delay
                    server_delay = extract_retry_after(error)
                    if server_delay is not None:
                        # Use server-specified delay, but cap it at max_delay
                        delay = min(server_delay, config.max_delay)
                        logger.info(
                            f"Using server-specified retry delay: {delay}s"
                        )
                    
                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}/{config.max_retries + 1}: "
                        f"{error}. Retrying in {delay:.2f}s..."
                    )
                    
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            if last_error:
                raise last_error
            else:
                raise RuntimeError(f"Function {func.__name__} failed after all retries")
        
        return wrapper
    return decorator


class RetryableClient:
    """
    Base class for clients that need retry functionality.
    """
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.retry_config = retry_config or RetryConfig()
        
    async def execute_with_retry(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
        """
        @retry_with_backoff(self.retry_config)
        async def wrapper():
            return await func(*args, **kwargs)
        
        return await wrapper()


def log_retry_metrics(func_name: str, attempt: int, error: Exception, delay: float):
    """
    Log retry metrics for monitoring.
    
    Args:
        func_name: Name of the function being retried
        attempt: Current attempt number
        error: The error that caused the retry
        delay: Delay before next retry
    """
    logger.info(
        f"RETRY_METRICS: {func_name} attempt={attempt} "
        f"error_type={type(error).__name__} delay={delay:.2f}s"
    )