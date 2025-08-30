"""Base class for all native tools in MOBA Agent."""

from langchain_core.tools import BaseTool
from pydantic import Field
from typing import Any, Optional, Type
from pydantic import BaseModel


class NativeTool(BaseTool):
    """Base class for all native tools inheriting from LangChain's BaseTool"""
    
    # These fields will be overridden by subclasses
    name: str = Field(default="native_tool", description="The name of the tool")
    description: str = Field(default="A native tool", description="Description of what the tool does")
    args_schema: Optional[Type[BaseModel]] = None
    
    # Additional fields for native tools
    access_token: Optional[str] = Field(default=None, exclude=True)
    logger: Optional[Any] = Field(default=None, exclude=True)
    
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Synchronous execution of the tool.
        This is a required abstract method from BaseTool.
        By default, we'll raise NotImplementedError since we prefer async.
        """
        raise NotImplementedError("This tool only supports async execution. Use _arun instead.")
    
    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """
        Asynchronous execution of the tool.
        Subclasses should override this method.
        """
        raise NotImplementedError("Subclasses must implement _arun method")