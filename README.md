# LangGraph Agent with MCP Integration

A powerful LangGraph agent that integrates with MCP (Model Context Protocol) servers using Google's Gemini 2.5 Flash as the LLM brain. This agent can discover and use tools and resources from any MCP server via SSE/Streamable HTTP protocol.

## Features

- 🤖 **Gemini 2.5 Flash Integration**: Uses Google's latest Gemini model for intelligent responses
- 🔌 **MCP Server Integration**: Connects to MCP servers via SSE/Streamable HTTP protocol
- 🛠️ **Dynamic Tool Discovery**: Automatically discovers and uses tools from MCP servers
- 📚 **Resource Management**: Lists and fetches resources from MCP servers
- 💬 **Interactive Chat**: Provides both standard and streaming chat interfaces
- 🔄 **Stateful Conversations**: Maintains conversation context with checkpointing
- 📊 **Comprehensive Logging**: Detailed logging for debugging and monitoring
- 🧪 **Well-Tested**: Includes comprehensive unit tests

## Architecture

```
┌─────────────────────────────────────────┐
│         LangGraph Agent                  │
│  ┌────────────────────────────────┐     │
│  │    Gemini 2.5 Flash LLM        │     │
│  └────────────────────────────────┘     │
│              ▲                           │
│              │                           │
│  ┌────────────────────────────────┐     │
│  │    LangGraph StateGraph         │     │
│  └────────────────────────────────┘     │
│              ▲                           │
│              │                           │
│  ┌────────────────────────────────┐     │
│  │  MultiServerMCPClient           │     │
│  └────────────────────────────────┘     │
└─────────────▲───────────────────────────┘
              │
              │ SSE/Streamable HTTP
              │
    ┌─────────▼───────────────┐
    │    MCP Server            │
    │  - Tools                 │
    │  - Resources             │
    └──────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.9 or higher
- Google API Key for Gemini
- Running MCP server at localhost:8000 (or custom URL)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/langgraph-agent-mcp.git
cd langgraph-agent-mcp
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
# or using poetry
poetry install
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your Google API key and MCP server URL
```

## Configuration

Create a `.env` file with the following variables:

```env
# Google Gemini API Key (required)
GOOGLE_API_KEY=your_google_api_key_here

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000/mcp
MCP_SERVER_NAME=mcp_server
MCP_TRANSPORT=streamable_http  # or "sse"

# Agent Configuration
AGENT_MODEL=gemini-2.5-flash
AGENT_TEMPERATURE=0.1
AGENT_MAX_TOKENS=4096

# Logging
LOG_LEVEL=DEBUG

# SSE Reconnection Settings
SSE_RECONNECT_ENABLED=true
SSE_RECONNECT_MAX_ATTEMPTS=5
SSE_RECONNECT_DELAY_MS=1000
```

## Usage

### Interactive Chat

Run the agent in interactive mode:

```bash
python scripts/run_agent.py
```

Or with streaming responses:

```bash
python scripts/run_agent.py --stream
```

### Available Commands

In interactive mode, you can use these commands:

- `help` - Show available commands
- `tools` - List available MCP tools
- `resources` - List available MCP resources
- `resource <uri>` - Fetch a specific resource
- `clear` - Clear conversation history
- `quit` - Exit the application

### Python API

```python
import asyncio
from src.langgraph_agent_mcp import MCPAgent, Config

async def main():
    # Initialize agent
    config = Config()
    agent = MCPAgent(config)
    await agent.initialize()
    
    # Send a message
    response = await agent.invoke("What tools do you have available?")
    print(response)
    
    # Get available tools
    tools = await agent.get_available_tools()
    for tool in tools:
        print(f"Tool: {tool['name']} - {tool.get('description', 'N/A')}")
    
    # Get available resources
    resources = await agent.get_available_resources()
    for resource in resources:
        print(f"Resource: {resource['uri']} - {resource.get('name', 'N/A')}")
    
    # Fetch a specific resource
    content = await agent.fetch_resource("resource://example")
    print(content)
    
    # Clean up
    await agent.close()

asyncio.run(main())
```

### Streaming Responses

```python
async def stream_example():
    config = Config()
    agent = MCPAgent(config)
    await agent.initialize()
    
    # Stream responses
    async for chunk in agent.stream("Tell me about the available tools"):
        print(chunk, end="", flush=True)
    
    await agent.close()

asyncio.run(stream_example())
```

## Example Scripts

The `scripts/` directory contains several example scripts:

- **run_agent.py** - Main interactive chat application
- **list_tools.py** - List all available MCP tools
- **list_resources.py** - List all available MCP resources
- **fetch_resources.py** - Interactive resource fetcher
- **test_connection.py** - Test MCP server connectivity
- **demo_tool_execution.py** - Demonstrate tool execution

### Testing Connection

Before running the agent, test your MCP server connection:

```bash
python scripts/test_connection.py
```

### Listing Tools

View all available tools from the MCP server:

```bash
python scripts/list_tools.py
```

### Listing Resources

View all available resources:

```bash
python scripts/list_resources.py
```

## MCP Server Setup

This agent requires an MCP server running with SSE/Streamable HTTP transport. Here's a simple example MCP server:

```python
# example_mcp_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Example Server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b

if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8000)
```

Run the server:

```bash
python example_mcp_server.py
```

## Testing

Run the test suite:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest tests/ --cov=src/langgraph_agent_mcp --cov-report=html
```

## Project Structure

```
langgraph-agent-mcp/
├── src/
│   └── langgraph_agent_mcp/
│       ├── __init__.py         # Package initialization
│       ├── agent.py            # Main MCPAgent class
│       ├── config.py           # Configuration management
│       ├── resources.py        # Resource handler
│       ├── tools.py            # Tool handler
│       └── main.py             # Interactive application
├── scripts/
│   ├── run_agent.py           # Main entry point
│   ├── list_tools.py          # Tool listing script
│   ├── list_resources.py      # Resource listing script
│   ├── fetch_resources.py     # Resource fetcher
│   ├── test_connection.py     # Connection tester
│   └── demo_tool_execution.py # Tool execution demo
├── tests/
│   ├── test_config.py         # Configuration tests
│   ├── test_agent.py          # Agent tests
│   ├── test_resources.py      # Resource handler tests
│   └── test_tools.py          # Tool handler tests
├── pyproject.toml             # Project configuration
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore file
└── README.md                  # This file
```

## Key Components

### MCPAgent

The main agent class that:
- Initializes connection to MCP server
- Sets up Gemini 2.5 Flash as the LLM
- Creates LangGraph agent with discovered tools
- Handles conversations with state management

### MultiServerMCPClient

Uses the official `langchain_mcp_adapters` library to:
- Connect to MCP servers via SSE/Streamable HTTP
- Discover and load tools dynamically
- Handle reconnection and error recovery

### ResourceHandler

Manages MCP resources:
- Lists available resources
- Fetches resource content on demand
- No caching - always fresh data

### ToolHandler

Manages MCP tools:
- Discovers available tools
- Formats tool descriptions
- Executes tools with proper error handling

## Troubleshooting

### Connection Issues

If you can't connect to the MCP server:

1. Verify the server is running:
```bash
curl http://localhost:8000/mcp
```

2. Check the connection:
```bash
python scripts/test_connection.py
```

3. Verify environment variables:
```bash
echo $MCP_SERVER_URL
```

### Google API Key Issues

1. Ensure your API key is valid
2. Check that Gemini API is enabled in Google Cloud Console
3. Verify the key has proper permissions

### Tool Execution Issues

1. Check that tools are properly exposed by the MCP server
2. Verify tool parameters match expected schema
3. Check logs for detailed error messages

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Uses [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- Powered by [Google Gemini](https://deepmind.google/technologies/gemini/)
- Implements [Model Context Protocol](https://modelcontextprotocol.io/)

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the documentation and examples