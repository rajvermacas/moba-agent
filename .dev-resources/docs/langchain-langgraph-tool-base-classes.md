# LangChain and LangGraph Tool Base Classes Reference

## Overview
This document provides comprehensive information about the available parent tool classes in LangChain and LangGraph libraries that can be used for creating native tools. These base classes provide the foundation for integrating custom tools with LangChain/LangGraph agents.

**Version Information**: Based on latest LangChain and LangGraph documentation as of January 2025
**Official Documentation**: 
- LangChain: https://python.langchain.com/docs/how_to/custom_tools
- LangGraph: https://langchain-ai.github.io/langgraph/how-tos/tool-calling/

---

## LangChain Tool Base Classes

### 1. BaseTool (Recommended for Complex Custom Tools)

**Purpose**: The foundational base class for all tools in LangChain. Provides the most control and flexibility for custom tool implementations.

**Key Features**:
- Supports both synchronous (`_run`) and asynchronous (`_arun`) execution
- Built-in error handling with `handle_tool_error` parameter
- Support for direct return to user with `return_direct` parameter
- Pydantic-based argument schema validation
- Automatic tool call ID management

**Core API**:
```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Type

class MyCustomTool(BaseTool):
    name: str = "my_custom_tool"
    description: str = "Description of what the tool does"
    args_schema: Optional[Type[BaseModel]] = None  # Optional Pydantic schema
    return_direct: bool = False  # Whether to return result directly to user
    handle_tool_error: bool = False  # Whether to handle errors gracefully
    
    def _run(self, *args, **kwargs) -> str:
        """Synchronous implementation (required)"""
        pass
    
    async def _arun(self, *args, **kwargs) -> str:
        """Asynchronous implementation (optional)"""
        pass
```

**Example Implementation**:
```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Type

class CalculatorInput(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")

class CustomCalculatorTool(BaseTool):
    name: str = "Calculator"
    description: str = "Useful for when you need to answer questions about math"
    args_schema: Optional[Type[BaseModel]] = CalculatorInput
    return_direct: bool = True

    def _run(self, a: int, b: int) -> str:
        """Synchronous multiplication"""
        return str(a * b)

    async def _arun(self, a: int, b: int) -> str:
        """Asynchronous multiplication"""
        return self._run(a, b)
```

### 2. StructuredTool (Recommended for Function-Based Tools)

**Purpose**: A subclass of BaseTool that allows creating tools from Python functions with structured arguments using Pydantic models.

**Key Features**:
- Create tools directly from functions
- Automatic schema inference from function signatures
- Support for both sync and async functions
- Simpler than BaseTool for function-based tools

**Core API**:
```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# Method 1: From function with explicit schema
class CalculatorInput(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

calculator = StructuredTool.from_function(
    func=multiply,
    name="Calculator",
    description="Multiply numbers",
    args_schema=CalculatorInput,
    return_direct=True,
)

# Method 2: With async function
async def amultiply(a: int, b: int) -> int:
    """Multiply two numbers asynchronously."""
    return a * b

calculator_async = StructuredTool.from_function(
    func=multiply,
    coroutine=amultiply,
    name="AsyncCalculator",
    description="Multiply numbers with async support"
)
```

### 3. Tool (Legacy, Simple Use Cases)

**Purpose**: Legacy tool class for simple function wrapping. Less recommended than BaseTool or StructuredTool.

**Core API**:
```python
from langchain_core.tools import Tool

def simple_function(query: str) -> str:
    return f"Result for: {query}"

tool = Tool(
    name="Simple Tool",
    description="A simple tool example",
    func=simple_function,
    return_direct=False
)
```

### 4. @tool Decorator (Recommended for Simple Functions)

**Purpose**: The simplest way to create tools from functions using a decorator approach.

**Key Features**:
- Minimal boilerplate code
- Automatic schema inference from function signatures and docstrings
- Support for Google-style docstring parsing
- Can specify custom names and descriptions

**Examples**:
```python
from langchain_core.tools import tool

# Basic usage
@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

# With custom name and description
@tool("multiply_tool")
def multiply_named(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

# With docstring parsing
@tool(parse_docstring=True)
def advanced_multiply(a: int, b: int) -> int:
    """Multiply two numbers with detailed documentation.
    
    Args:
        a: The first number to multiply
        b: The second number to multiply
    """
    return a * b

# With return_direct
@tool(return_direct=True)
def direct_multiply(a: int, b: int) -> int:
    """Multiply two numbers and return directly."""
    return a * b
```

---

## LangGraph Tool Integration Classes

### 1. ToolNode (Primary Tool Executor for LangGraph)

**Purpose**: The main class for executing tools within LangGraph workflows. Not a base class to inherit from, but the primary way to integrate tools into LangGraph agents.

**Key Features**:
- Executes multiple tools concurrently
- Built-in error handling with customizable messages
- Support for both sync and async tools
- Automatic state management for MessagesState

**Usage**:
```python
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.messages import AIMessage

@tool
def get_weather(location: str) -> str:
    """Get current weather for a location."""
    return f"Weather in {location}: Sunny, 72°F"

# Create ToolNode
tool_node = ToolNode([get_weather])

# Use in LangGraph
from langgraph.graph import StateGraph, MessagesState

def should_continue(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]
    return "tools" if last_message.tool_calls else "end"

graph_builder = StateGraph(MessagesState)
graph_builder.add_node("tools", tool_node)
```

**Error Handling Options**:
```python
# Default error handling (enabled)
tool_node = ToolNode([multiply])

# Disable error handling
tool_node = ToolNode([multiply], handle_tool_errors=False)

# Custom error message
tool_node = ToolNode(
    [multiply], 
    handle_tool_errors="Custom error message for tool failures"
)
```

### 2. ValidationNode (Tool Validation)

**Purpose**: Validates tool calls against Pydantic schemas without executing them. Useful for extraction and structured output use cases.

**Usage**:
```python
from langgraph.prebuilt import ValidationNode
from pydantic import BaseModel, field_validator

class SelectNumber(BaseModel):
    a: int

    @field_validator("a")
    def a_must_be_meaningful(cls, v):
        if v != 37:
            raise ValueError("Only 37 is allowed")
        return v

validation_node = ValidationNode([SelectNumber])
```

---

## Architectural Hierarchy and Relationships

### Inheritance Hierarchy
```
RunnableCallable (LangChain Core)
├── BaseTool (langchain_core.tools.base)
│   ├── StructuredTool (langchain_core.tools.structured)
│   └── Tool (langchain_core.tools)
└── ToolNode (langgraph.prebuilt.tool_node) - Not for inheritance, but for execution
```

### When to Use Each Class

| Class | Use Case | Complexity | Recommended For |
|-------|----------|------------|-----------------|
| `@tool` decorator | Simple function tools | Low | Quick prototypes, simple functions |
| `StructuredTool` | Function-based tools with schemas | Low-Medium | Converting existing functions to tools |
| `BaseTool` | Complex custom tools | High | Full control, complex logic, custom behavior |
| `ToolNode` | LangGraph integration | Medium | Executing tools in LangGraph workflows |
| `ValidationNode` | Schema validation | Medium | Structured output validation |

---

## Integration Patterns for Native Tool Development

### 1. Basic Native Tool Pattern
```python
from langchain_core.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field

class MyNativeToolInput(BaseModel):
    query: str = Field(description="The query to process")
    options: Optional[dict] = Field(default=None, description="Optional parameters")

class MyNativeTool(BaseTool):
    name: str = "my_native_tool"
    description: str = "A native tool for specific functionality"
    args_schema: Type[BaseModel] = MyNativeToolInput
    
    def _run(self, query: str, options: Optional[dict] = None) -> str:
        """Implement your native tool logic here"""
        # Your custom implementation
        return f"Processed: {query} with options: {options}"
```

### 2. LangGraph Integration Pattern
```python
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START, END

# Create your tools
native_tool = MyNativeTool()
tools = [native_tool]

# Create ToolNode for LangGraph
tool_node = ToolNode(tools)

# Build graph
def should_continue(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]
    return "tools" if last_message.tool_calls else END

graph = StateGraph(MessagesState) \
    .add_node("agent", call_model) \
    .add_node("tools", tool_node) \
    .add_conditional_edges("agent", should_continue, ["tools", END]) \
    .add_edge("tools", "agent") \
    .add_edge(START, "agent") \
    .compile()
```

### 3. Advanced State Management Pattern
```python
from langgraph.types import Command
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

@tool
def stateful_tool(
    input_data: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Tool that updates graph state"""
    # Process input
    result = process_input(input_data)
    
    # Return Command to update state
    return Command(update={
        "custom_state_key": result,
        "messages": [
            ToolMessage(
                content=f"Processed: {result}",
                tool_call_id=tool_call_id
            )
        ]
    })
```

---

## Best Practices and Recommendations

### 1. Recommended Approach for Native Tools
For most native tool implementations, **inherit from `BaseTool`**:
- Provides maximum control and flexibility
- Built-in error handling and validation
- Easy to test and debug
- Supports both sync and async operations
- Integrates seamlessly with both LangChain and LangGraph

### 2. Error Handling
Always implement proper error handling:
```python
class RobustNativeTool(BaseTool):
    name: str = "robust_tool"
    description: str = "A tool with proper error handling"
    handle_tool_error: bool = True  # Enable built-in error handling
    
    def _run(self, input_data: str) -> str:
        try:
            # Your tool logic here
            result = perform_operation(input_data)
            return result
        except Exception as e:
            # Log the error appropriately
            logger.error(f"Tool execution failed: {e}")
            raise  # Let BaseTool handle the error response
```

### 3. Testing Strategy
Create comprehensive tests for your tools:
```python
def test_native_tool():
    tool = MyNativeTool()
    
    # Test direct invocation
    result = tool.invoke({"query": "test", "options": {"key": "value"}})
    assert "Processed: test" in result
    
    # Test with tool call format
    tool_call = {
        "type": "tool_call",
        "id": "test_id",
        "args": {"query": "test"}
    }
    tool_message = tool.invoke(tool_call)
    assert tool_message.tool_call_id == "test_id"
```

---

## Migration Notes

### From Other Tool Frameworks
- **From custom implementations**: Inherit from `BaseTool` for maximum compatibility
- **From function-based tools**: Use `@tool` decorator or `StructuredTool.from_function()`
- **For LangGraph integration**: Always use `ToolNode` for tool execution in workflows

### Common Pitfalls to Avoid
1. **Don't inherit from `ToolNode`** - it's for execution, not inheritance
2. **Always define `_run` method** when inheriting from `BaseTool`
3. **Use Pydantic models** for `args_schema` to ensure proper validation
4. **Handle both sync and async cases** if your tool will be used in async contexts

---

## Related Documentation Links
- [LangChain Custom Tools Guide](https://python.langchain.com/docs/how_to/custom_tools)
- [LangGraph Tool Calling](https://langchain-ai.github.io/langgraph/how-tos/tool-calling/)
- [BaseTool API Reference](https://python.langchain.com/api_reference/core/tools/langchain_core.tools.base.BaseTool.html)
- [StructuredTool API Reference](https://python.langchain.com/api_reference/core/tools/langchain_core.tools.structured.StructuredTool.html)

---

*Generated on: January 2025*
*Documentation Version: Based on latest LangChain and LangGraph releases*