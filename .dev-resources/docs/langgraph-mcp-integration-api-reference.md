# LangGraph MCP Integration API Reference

## Overview

This reference provides comprehensive documentation for integrating Model Context Protocol (MCP) servers with LangGraph agents using Gemini 2.5 Flash. This integration enables LangGraph agents to access tools, resources, and prompts from multiple MCP servers through standardized interfaces.

**Version Information:**
- langchain-mcp-adapters: ^0.1.0
- langgraph: ^0.2.0  
- langchain-google-genai: ^2.0.0
- mcp: Latest (1.9.1+ recommended)

**Documentation Generated:** 2025-08-23  
**API Version:** Current as of MCP Specification 2025-03-26

## Installation & Setup

### Required Dependencies

```bash
pip install langchain-mcp-adapters langgraph langchain-google-genai google-generativeai mcp
```

### Environment Variables

```bash
# Google AI API Key (required)
GOOGLE_API_KEY=your_google_api_key_here

# Agent Configuration (optional)
AGENT_MODEL=gemini-2.5-flash
AGENT_TEMPERATURE=0.1
AGENT_MAX_TOKENS=4096

# MCP Server Configuration (optional)
MCP_SERVER_URL=http://localhost:8000/sse
MCP_SERVER_NAME=your_mcp_server_name
MCP_TRANSPORT=streamable_http
```

## Core Libraries

---

## 1. langchain-mcp-adapters

### MultiServerMCPClient

**Purpose:** Client for connecting to multiple MCP servers and loading LangChain-compatible tools, prompts, and resources.

#### Class Signature

```python
class MultiServerMCPClient:
    def __init__(self, connections: dict[str, Connection] | None = None) -> None
```

#### Connection Configuration

```python
# Connection configuration structure
connections = {
    "server_name": {
        "transport": "stdio" | "streamable_http" | "sse",
        
        # For stdio transport
        "command": "python",
        "args": ["/path/to/server.py"],
        
        # For HTTP transports
        "url": "http://localhost:8000/mcp",
        
        # Optional headers (streamable_http and sse only)
        "headers": {
            "Authorization": "Bearer TOKEN",
            "X-Custom-Header": "value"
        }
    }
}
```

#### Key Methods

**get_tools() - Load All Tools**
```python
async def get_tools(self, server_name: str | None = None) -> list[BaseTool]
```
- **Parameters:** 
  - `server_name` (optional): Specific server name, if None returns tools from all servers
- **Returns:** List of LangChain-compatible BaseTool objects
- **Note:** Creates a new session for each tool call

**session() - Explicit Session Management**
```python
async def session(
    self, 
    server_name: str, 
    auto_initialize: bool = True
) -> AsyncIterator[ClientSession]
```
- **Parameters:**
  - `server_name`: Name of the server to connect to
  - `auto_initialize`: Whether to automatically initialize the session
- **Yields:** Initialized ClientSession
- **Usage:** Context manager for explicit session control

**get_resources() - Load Resources**
```python
async def get_resources(
    self,
    server_name: str,
    uris: str | list[str] | None = None
) -> list[Blob]
```
- **Parameters:**
  - `server_name`: Name of the server to get resources from
  - `uris`: Optional specific resource URIs to load
- **Returns:** List of LangChain Blob objects

**get_prompt() - Load Prompts**
```python
async def get_prompt(self, server_name: str, name: str, arguments: dict[str, Any] | None = None)
```
- **Parameters:**
  - `server_name`: Server name
  - `name`: Prompt name
  - `arguments`: Optional prompt arguments

#### Configuration Examples

**Multiple Servers (Mixed Transports):**
```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "math": {
        "transport": "stdio",
        "command": "python",
        "args": ["/absolute/path/to/math_server.py"]
    },
    "weather": {
        "transport": "streamable_http",
        "url": "http://localhost:8000/mcp",
        "headers": {
            "Authorization": "Bearer YOUR_TOKEN"
        }
    },
    "legacy_server": {
        "transport": "sse",
        "url": "http://localhost:9000/sse"
    }
})

# Get all tools from all servers
tools = await client.get_tools()

# Get tools from specific server
math_tools = await client.get_tools("math")
```

**Explicit Session Management:**
```python
from langchain_mcp_adapters.tools import load_mcp_tools

async with client.session("math") as session:
    tools = await load_mcp_tools(session)
    # Session remains active for multiple operations
    response = await session.call_tool("add", {"a": 3, "b": 5})
```

#### Error Handling

```python
try:
    tools = await client.get_tools()
except ValueError as e:
    # Server name not found in connections
    print(f"Server configuration error: {e}")
except Exception as e:
    # Connection or communication errors
    print(f"MCP connection error: {e}")
```

---

## 2. MCP Protocol (mcp library)

### Core Transport Options

#### Streamable HTTP Transport (Recommended)

**Purpose:** Modern HTTP-based transport with bi-directional communication and automatic connection upgrades.

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://localhost:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

**Key Features:**
- Single endpoint for all communication
- Automatic HTTP to SSE upgrades for streaming
- Bi-directional communication support
- Production-ready with better reliability

#### SSE Transport (Deprecated)

**Status:** Deprecated as of MCP specification 2025-03-26. Use Streamable HTTP instead.

```python
from mcp.client.sse import sse_client

# Deprecated - use streamable_http instead
async with sse_client("http://localhost:8000/sse") as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
```

#### Stdio Transport

**Purpose:** Direct process communication, ideal for local servers.

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["/path/to/server.py"],
    env={"CUSTOM_VAR": "value"}
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

### ClientSession

**Purpose:** High-level interface for MCP protocol communication.

#### Key Methods

**initialize() - Session Initialization**
```python
async def initialize() -> None
```
- Must be called after creating the session
- Establishes protocol handshake
- Required before any other operations

**list_tools() - Discover Tools**
```python
async def list_tools() -> ListToolsResult
```
- **Returns:** Object with `.tools` attribute containing list of available tools
- Tools have `.name`, `.description`, and `.inputSchema` attributes

**call_tool() - Execute Tools**
```python
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult
```
- **Parameters:**
  - `name`: Tool name from list_tools()
  - `arguments`: Dictionary of tool arguments matching inputSchema
- **Returns:** Tool execution result with `.content` attribute

**list_resources() - Discover Resources**
```python
async def list_resources() -> ListResourcesResult
```
- **Returns:** Available resources (excludes dynamic resources)

**read_resource() - Fetch Resource**
```python
async def read_resource(uri: str) -> ReadResourceResult
```
- **Parameters:**
  - `uri`: Resource URI from list_resources()

### Message Format and Communication Patterns

**Request-Response Pattern:**
```python
# Tool call example
request = {
    "jsonrpc": "2.0",
    "id": "unique_id",
    "method": "tools/call",
    "params": {
        "name": "tool_name",
        "arguments": {"param": "value"}
    }
}

response = {
    "jsonrpc": "2.0",
    "id": "unique_id",
    "result": {
        "content": [{"type": "text", "text": "Tool result"}]
    }
}
```

**Error Handling:**
```python
try:
    result = await session.call_tool("unknown_tool", {})
except Exception as e:
    # Handle tool execution errors
    print(f"Tool execution failed: {e}")
```

---

## 3. LangGraph Integration

### create_react_agent Function

**Purpose:** Pre-built ReAct agent with MCP tools integration.

#### Function Signature

```python
def create_react_agent(
    llm: BaseLLM,
    tools: Sequence[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
    prompt: ChatPromptTemplate | None = None,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    debug: bool = False
) -> CompiledGraph
```

#### Basic Usage with MCP Tools

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

# Initialize components
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)
client = MultiServerMCPClient({
    "math": {
        "transport": "stdio",
        "command": "python",
        "args": ["/path/to/math_server.py"]
    }
})

# Create agent
tools = await client.get_tools()
agent = create_react_agent(llm, tools)

# Execute query
response = await agent.ainvoke({
    "messages": [{"role": "user", "content": "Calculate 15 * 23"}]
})
```

### StateGraph for Custom Agent Architectures

**Purpose:** Build custom agent workflows with full control over state and execution flow.

#### Core Components

**StateGraph with MessagesState:**
```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition

# Define model function
async def call_model(state: MessagesState):
    response = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}

# Build graph
builder = StateGraph(MessagesState)
builder.add_node("model", call_model)
builder.add_node("tools", ToolNode(tools))

# Add edges
builder.add_edge(START, "model")
builder.add_conditional_edges(
    "model",
    tools_condition,  # Routes to "tools" or END
    {"tools": "tools", END: END}
)
builder.add_edge("tools", "model")

# Compile
graph = builder.compile(checkpointer=checkpointer)
```

**ToolNode Integration:**
```python
from langgraph.prebuilt import ToolNode, InjectedState, InjectedStore

# Basic ToolNode
tool_node = ToolNode(tools)

# ToolNode with state injection
@tool
def stateful_tool(
    query: str,
    state: Annotated[MessagesState, InjectedState()]
) -> str:
    # Access graph state within tool
    message_count = len(state["messages"])
    return f"Processed query: {query}, Messages: {message_count}"
```

**tools_condition Function:**
```python
from langgraph.prebuilt import tools_condition

def should_continue(state: MessagesState):
    # Custom logic or use built-in tools_condition
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return END
```

### Checkpointing and Memory Management

**Memory Saver (In-Memory):**
```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
agent = create_react_agent(llm, tools, checkpointer=checkpointer)

# Use with conversation threads
config = {"configurable": {"thread_id": "conversation_1"}}
response = await agent.ainvoke({"messages": [message]}, config=config)
```

**Custom Checkpointer:**
```python
from langgraph.checkpoint.base import BaseCheckpointSaver

class CustomCheckpointer(BaseCheckpointSaver):
    # Implement custom persistence logic
    async def aget_tuple(self, config):
        # Load checkpoint from database
        pass
    
    async def aput(self, config, checkpoint, metadata):
        # Save checkpoint to database
        pass
```

---

## 4. langchain-google-genai (Gemini Integration)

### ChatGoogleGenerativeAI

**Purpose:** LangChain integration for Google's Gemini models with comprehensive configuration options.

#### Class Initialization

```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.1,
    max_tokens=4096,
    max_retries=2,
    timeout=60,
    google_api_key="your-api-key",  # or set GOOGLE_API_KEY env var
    convert_system_message_to_human=True,  # Handle system messages
    safety_settings=None,  # Custom safety settings
    client_options=None    # Additional client options
)
```

#### Configuration Parameters

**Model Selection:**
- `gemini-2.5-flash`: Latest fast model (recommended)
- `gemini-2.0-flash-exp`: Experimental features
- `gemini-1.5-pro`: Higher capability model
- `gemini-1.5-flash`: Balanced performance

**Core Parameters:**
- `temperature` (float, 0-1): Controls randomness, 0 = deterministic
- `max_tokens` (int): Maximum tokens in response, default 64 if unset
- `max_retries` (int): Number of retry attempts on failure
- `timeout` (float): Request timeout in seconds

**Advanced Configuration:**
```python
from google.ai.generativelanguage_v1beta.types import HarmCategory, HarmBlockThreshold

safety_settings = [
    {
        "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
        "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }
]

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    safety_settings=safety_settings,
    convert_system_message_to_human=True
)
```

#### Usage Patterns

**Basic Chat:**
```python
from langchain_core.messages import HumanMessage, SystemMessage

messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Explain quantum computing briefly.")
]

response = await llm.ainvoke(messages)
print(response.content)
```

**Tool Binding:**
```python
from pydantic import BaseModel, Field

class CalculatorTool(BaseModel):
    """Perform mathematical calculations"""
    expression: str = Field(description="Mathematical expression to evaluate")

llm_with_tools = llm.bind_tools([CalculatorTool])
response = await llm_with_tools.ainvoke([
    HumanMessage(content="Calculate 15 * 23 + 7")
])

# Access tool calls
if response.tool_calls:
    for tool_call in response.tool_calls:
        print(f"Tool: {tool_call['name']}, Args: {tool_call['args']}")
```

**Streaming:**
```python
async for chunk in llm.astream(messages):
    print(chunk.content, end="", flush=True)
```

**Structured Output:**
```python
from pydantic import BaseModel

class AnalysisResult(BaseModel):
    summary: str
    key_points: list[str]
    confidence: float

structured_llm = llm.with_structured_output(AnalysisResult)
result = await structured_llm.ainvoke([
    HumanMessage(content="Analyze the benefits of renewable energy")
])
print(result.summary)  # Guaranteed to be AnalysisResult object
```

### Context Caching (Advanced)

**Purpose:** Store and reuse large content (documents, images) for faster processing across multiple requests.

```python
from google import genai
from google.genai import types

# Upload and cache content
client = genai.Client()
file = client.files.upload(file="./large_document.pdf")

# Wait for processing
import time
while file.state.name == 'PROCESSING':
    time.sleep(2)
    file = client.files.get(name=file.name)

# Create cache
cache = client.caches.create(
    model='gemini-2.5-flash',
    config=types.CreateCachedContentConfig(
        display_name='Document Cache',
        system_instruction='Analyze the uploaded document and answer questions.',
        contents=[file],
        ttl="300s"  # 5 minute TTL
    )
)

# Use cached content
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    cached_content=cache.name
)
```

### Google Search Integration

**Purpose:** Enable Gemini 2.5 models to search the web for current information.

```python
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
response = await llm.ainvoke(
    "What's the latest news about renewable energy?",
    tools=[GenAITool(google_search={})]
)
```

---

## Complete Integration Examples

### Example 1: Basic MCP Agent with Gemini

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

async def main():
    # Initialize Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        max_tokens=2048
    )
    
    # Setup MCP client
    client = MultiServerMCPClient({
        "calculator": {
            "transport": "stdio",
            "command": "python",
            "args": ["/path/to/calculator_server.py"]
        }
    })
    
    # Create agent
    tools = await client.get_tools()
    agent = create_react_agent(llm, tools)
    
    # Run query
    response = await agent.ainvoke({
        "messages": [{"role": "user", "content": "Calculate the square root of 144"}]
    })
    
    print(response["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 2: Custom StateGraph with Multiple MCP Servers

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI

async def create_multi_server_agent():
    # Initialize model
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.2,
        max_tokens=4096
    )
    
    # Setup multiple MCP servers
    client = MultiServerMCPClient({
        "math": {
            "transport": "stdio",
            "command": "python",
            "args": ["/path/to/math_server.py"]
        },
        "weather": {
            "transport": "streamable_http",
            "url": "http://localhost:8000/mcp",
            "headers": {"API-Key": "your-weather-api-key"}
        },
        "files": {
            "transport": "streamable_http", 
            "url": "http://localhost:8001/mcp"
        }
    })
    
    # Get tools and bind to model
    tools = await client.get_tools()
    llm_with_tools = llm.bind_tools(tools)
    
    # Create tool node
    tool_node = ToolNode(tools)
    
    # Define state functions
    async def call_model(state: MessagesState):
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}
    
    def should_continue(state: MessagesState):
        return tools_condition(state)
    
    # Build graph
    builder = StateGraph(MessagesState)
    builder.add_node("model", call_model)
    builder.add_node("tools", tool_node)
    
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", should_continue)
    builder.add_edge("tools", "model")
    
    # Add memory
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    
    return graph

async def main():
    agent = await create_multi_server_agent()
    
    config = {"configurable": {"thread_id": "multi_server_demo"}}
    
    # Test multi-server capabilities
    queries = [
        "What's 15 * 23 + 42?",  # math server
        "What's the weather in New York?",  # weather server
        "List the files in the current directory"  # files server
    ]
    
    for query in queries:
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": query}]
        }, config=config)
        
        print(f"Q: {query}")
        print(f"A: {response['messages'][-1].content}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 3: Production-Ready Agent with Error Handling

```python
import asyncio
import logging
from typing import Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductionMCPAgent:
    def __init__(self, config: dict):
        self.config = config
        self.llm: Optional[ChatGoogleGenerativeAI] = None
        self.client: Optional[MultiServerMCPClient] = None
        self.agent = None
        self.checkpointer = MemorySaver()
    
    async def initialize(self):
        """Initialize all components with error handling"""
        try:
            # Initialize Gemini
            self.llm = ChatGoogleGenerativeAI(
                model=self.config.get("model", "gemini-2.5-flash"),
                temperature=self.config.get("temperature", 0.1),
                max_tokens=self.config.get("max_tokens", 4096),
                max_retries=self.config.get("max_retries", 3)
            )
            logger.info("Gemini model initialized")
            
            # Initialize MCP client
            self.client = MultiServerMCPClient(self.config["mcp_servers"])
            logger.info(f"MCP client configured for {len(self.config['mcp_servers'])} servers")
            
            # Load tools
            tools = await self.client.get_tools()
            logger.info(f"Loaded {len(tools)} tools from MCP servers")
            
            # Create agent
            self.agent = create_react_agent(
                self.llm, 
                tools, 
                checkpointer=self.checkpointer
            )
            logger.info("Agent created successfully")
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            raise
    
    async def process_query(
        self, 
        query: str, 
        thread_id: str = "default",
        max_retries: int = 3
    ) -> str:
        """Process query with retry logic"""
        for attempt in range(max_retries):
            try:
                config = {"configurable": {"thread_id": thread_id}}
                response = await self.agent.ainvoke({
                    "messages": [{"role": "user", "content": query}]
                }, config=config)
                
                result = response["messages"][-1].content
                logger.info(f"Query processed successfully (attempt {attempt + 1})")
                return result
                
            except Exception as e:
                logger.warning(f"Query processing failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Query processing failed after {max_retries} attempts")
                    raise
                await asyncio.sleep(1)  # Brief delay before retry
    
    async def get_server_status(self) -> dict:
        """Check status of all MCP servers"""
        status = {}
        for server_name in self.config["mcp_servers"].keys():
            try:
                async with self.client.session(server_name) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    status[server_name] = {
                        "status": "healthy",
                        "tools": len(tools.tools) if tools.tools else 0
                    }
            except Exception as e:
                status[server_name] = {
                    "status": "error",
                    "error": str(e)
                }
        return status

async def main():
    config = {
        "model": "gemini-2.5-flash",
        "temperature": 0.1,
        "max_tokens": 4096,
        "max_retries": 3,
        "mcp_servers": {
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": ["/path/to/math_server.py"]
            },
            "weather": {
                "transport": "streamable_http",
                "url": "http://localhost:8000/mcp",
                "headers": {"Authorization": "Bearer YOUR_TOKEN"}
            }
        }
    }
    
    agent = ProductionMCPAgent(config)
    
    try:
        await agent.initialize()
        
        # Check server health
        status = await agent.get_server_status()
        logger.info(f"Server status: {status}")
        
        # Process queries
        queries = [
            "Calculate the factorial of 5",
            "What's the weather forecast for tomorrow?",
            "What tools do you have available?"
        ]
        
        for query in queries:
            try:
                result = await agent.process_query(query, thread_id="prod_demo")
                print(f"Q: {query}")
                print(f"A: {result}\n")
            except Exception as e:
                print(f"Failed to process query '{query}': {e}\n")
                
    except Exception as e:
        logger.error(f"Application failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
```

---

## Error Handling and Best Practices

### Common Error Scenarios

**1. Connection Errors**
```python
try:
    tools = await client.get_tools()
except ConnectionError:
    logger.error("Failed to connect to MCP server")
    # Implement fallback or retry logic
except TimeoutError:
    logger.error("MCP server connection timeout")
    # Handle timeout gracefully
```

**2. Tool Execution Errors**
```python
# ToolNode automatically handles tool errors
# Errors are returned as ToolMessage with error status
# Custom error handling in tools:
@tool
def safe_calculation(expression: str) -> str:
    try:
        result = eval(expression)  # Don't do this in production!
        return f"Result: {result}"
    except Exception as e:
        return f"Calculation error: {str(e)}"
```

**3. Model Errors**
```python
try:
    response = await llm.ainvoke(messages)
except Exception as e:
    logger.error(f"Gemini model error: {e}")
    # Implement retry logic or fallback model
```

### Performance Considerations

**1. Connection Pooling**
- Use `session()` context manager for multiple operations
- Reuse MultiServerMCPClient instances
- Implement connection health checks

**2. Tool Optimization**
- Tools in ToolNode run in parallel by default
- Use dependency injection for shared resources
- Implement timeout handling for long-running tools

**3. Memory Management**
- Use appropriate checkpointer for conversation persistence
- Implement cleanup for long-running agents
- Monitor memory usage with large context caches

### Security Best Practices

**1. API Key Management**
```python
import os
from dotenv import load_dotenv

load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable required")
```

**2. Input Validation**
```python
@tool
def secure_file_read(filepath: str) -> str:
    # Validate filepath to prevent directory traversal
    if ".." in filepath or filepath.startswith("/"):
        return "Error: Invalid file path"
    # Additional security checks...
```

**3. Transport Security**
- Use HTTPS for streamable_http transport
- Implement proper authentication headers
- Validate server certificates

### Version-Specific Requirements

**MCP Protocol:**
- MCP 1.9.1+ required for FastMCP `tools` parameter
- Streamable HTTP preferred over SSE (deprecated)
- Stdio transport most stable for local servers

**LangGraph:**
- v0.2.0+ required for latest ToolNode features
- State injection requires recent versions
- Checkpointing API stable from v0.1.15+

**Gemini Models:**
- gemini-2.5-flash: Latest and recommended
- Context caching requires google-genai >= 0.8.0
- Tool calling stable across all 1.5+ models

---

## Additional Resources

### Official Documentation
- [Model Context Protocol Specification](https://modelcontextprotocol.io/introduction)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain MCP Adapters GitHub](https://github.com/langchain-ai/langchain-mcp-adapters)
- [Google Gemini API Documentation](https://ai.google.dev/gemini-api/docs)

### Community Resources
- [MCP Server Examples](https://github.com/modelcontextprotocol/servers)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [LangGraph Tutorials](https://langchain-ai.github.io/langgraph/tutorials/)

### Support Channels
- [LangChain Discord](https://discord.gg/langchain)
- [MCP GitHub Discussions](https://github.com/modelcontextprotocol/specification/discussions)
- [Google AI Developer Community](https://developers.googleblog.com/2024/12/gemini-20-flash-thinking-now-available.html)

---

*This reference was generated on 2025-08-23 and reflects the current state of the APIs. Always check official documentation for the latest updates and changes.*