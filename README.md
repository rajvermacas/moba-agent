# MOBA Agent - Integrated MCP & REST API Server

A powerful LangGraph agent that integrates with MCP (Model Context Protocol) servers using Google's Gemini 2.5 Flash as the LLM brain, with an integrated REST API server providing OpenAI-compatible endpoints.

## 🚀 Key Features

### Core Agent Features
- 🤖 **Gemini 2.5 Flash Integration**: Uses Google's latest Gemini model for intelligent responses
- 🔌 **Multi-MCP Server Support**: Connects to multiple MCP servers simultaneously
- 🛠️ **Dynamic Tool Discovery**: Automatically discovers and uses tools from MCP servers
- 📚 **Resource Management**: Lists and fetches resources from MCP servers
- 🎯 **Automatic Resource Context Injection**: Automatically injects available MCP resources into the LLM context
- 💬 **Interactive Chat**: Provides both standard and streaming chat interfaces
- 🔄 **Stateful Conversations**: Maintains conversation context with checkpointing

### REST API Server Features
- 🌐 **OpenAI-Compatible API**: Full compatibility with OpenAI chat completions format
- 🔒 **Zero Code Duplication**: Single implementation for all MCP/LLM logic
- ⚡ **Direct Integration**: No network overhead between components
- 🎨 **CORS Support**: Ready for React/web frontend integration
- 📊 **Health & Status Endpoints**: Monitor system health and MCP connections
- 🧪 **Integration Testing**: Built-in test endpoints

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              REST API Client                     │
└────────────────┬─────────────────────────────────┘
                 │ HTTP/REST
                 ▼
┌─────────────────────────────────────────────────┐
│            moba_server (FastAPI)                 │
│  ┌──────────────────────────────────────────┐   │
│  │  Endpoints (all paths preserved):        │   │
│  │  • POST /chat/completions                │   │
│  │  • GET /health                           │   │
│  │  • GET /models                           │   │
│  │  • GET /mcp/status                       │   │
│  │  • GET /debug/agent                      │   │
│  └──────────────────────────────────────────┘   │
│                      │                           │
│                      ▼                           │
│  ┌──────────────────────────────────────────┐   │
│  │       ChatCompletionHandler              │   │
│  │    (Delegates to MCPAgent)               │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────┬────────────────────────────┘
                      │ Direct Library Import
                      ▼
┌─────────────────────────────────────────────────┐
│            moba_agent (MCPAgent)                 │
│  ┌──────────────────────────────────────────┐   │
│  │      Gemini 2.5 Flash LLM                │   │
│  └──────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────┐   │
│  │      LangGraph StateGraph                │   │
│  └──────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────┐   │
│  │      Multi-MCP Client Support            │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────┬────────────────────────────┘
                      │ MCP Protocol
                      ▼
         ┌────────────────────────┐
         │    MCP Servers          │
         │  - Tools               │
         │  - Resources           │
         └────────────────────────┘
```

## 📦 Installation

### Prerequisites

- Python 3.9 or higher
- Google API Key for Gemini
- MCP server(s) configured in `mcp_servers.json`

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/moba-agent.git
cd moba-agent
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
# Edit .env and add your Google API key
```

## ⚙️ Configuration

### Environment Variables (.env)

```env
# ===================================
# MOBA Agent Configuration
# ===================================

# Google Gemini API Key (Required)
GOOGLE_API_KEY=your_google_api_key_here

# MCP Server Configuration
MCP_CONFIG_FILE=mcp_servers.json

# Agent Configuration
AGENT_MODEL=gemini-2.5-flash
AGENT_TEMPERATURE=0.1
AGENT_MAX_TOKENS=4096

# ===================================
# FastAPI Server Configuration
# ===================================

# Server Host and Port
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8001

# CORS Configuration
ALLOW_CORS=true

# Logging
LOG_LEVEL=INFO
```

### MCP Servers Configuration (mcp_servers.json)

```json
{
  "servers": {
    "mherb": {
      "transport": "sse",
      "url": "http://localhost:8000/sse"
    },
    "fetch": {
      "transport": "stdio",
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

## 🚀 Usage

### Running the REST API Server

```bash
# Start the FastAPI server
python -m src.moba_server.main

# Or use uvicorn directly
uvicorn src.moba_server.main:app --host 0.0.0.0 --port 8001
```

The server will be available at `http://localhost:8001`

### API Endpoints

#### Chat Completions (OpenAI-Compatible)
```bash
curl -X POST http://localhost:8001/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "How many customers are in the database?"}
    ]
  }'
```

#### Health Check
```bash
curl http://localhost:8001/health
```

#### List Models
```bash
curl http://localhost:8001/models
```

#### MCP Status
```bash
curl http://localhost:8001/mcp/status
```

### Interactive CLI Mode

```bash
# Run the agent in interactive mode
python scripts/run_agent.py

# With streaming responses
python scripts/run_agent.py --stream
```

### Python API

```python
import asyncio
from moba_agent import MCPAgent, Config

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
    
    # Clean up
    await agent.close()

asyncio.run(main())
```

## 📁 Project Structure

```
moba-agent/
├── src/
│   ├── moba_agent/              # Core agent implementation
│   │   ├── __init__.py
│   │   ├── agent.py            # MCPAgent class
│   │   ├── config.py           # Configuration management
│   │   ├── resources.py        # Resource handler
│   │   ├── tools.py            # Tool handler
│   │   └── main.py             # Interactive CLI
│   └── moba_server/            # REST API server
│       ├── __init__.py
│       ├── main.py             # FastAPI application
│       ├── chat_handler.py     # Chat completion handler (uses MCPAgent)
│       ├── config.py           # Server configuration
│       └── models.py           # Request/response models
├── scripts/
│   ├── run_agent.py           # Interactive chat
│   ├── test_integration.py    # Integration tests
│   └── ...                    # Other utility scripts
├── tests/                      # Test suite
├── mcp_servers.json           # MCP server configuration
├── pyproject.toml             # Project configuration
├── .env.example               # Environment template
└── README.md                  # This file
```

## 🧪 Testing

### Run Tests
```bash
pytest tests/
```

### Test Integration
```bash
python scripts/test_integration.py
```

### Test Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

## 🔄 Migration from Separate Services

This project consolidates what were previously separate services:
- **Before**: Separate `moba_server` with duplicate MCP/LLM code
- **After**: Single codebase with `moba_agent` as the core, `moba_server` as REST wrapper

### Benefits of Integration:
- ✅ **Zero code duplication** - Single implementation of MCP/LLM logic
- ✅ **No network overhead** - Direct library imports instead of service calls
- ✅ **Simplified debugging** - Single process, clear stack traces
- ✅ **Easier deployment** - One application to deploy and manage
- ✅ **100% API compatibility** - All endpoints preserve exact paths

## 🐛 Troubleshooting

### Connection Issues

1. Verify MCP servers are running:
```bash
curl http://localhost:8000/sse
```

2. Check server logs:
```bash
tail -f logs/fastapi_server.log
```

3. Test with debug endpoint:
```bash
curl http://localhost:8001/debug/agent
```

### Google API Key Issues

1. Ensure your API key is valid
2. Check that Gemini API is enabled in Google Cloud Console
3. Verify the key in `.env` file

### Common Errors

- **"MCPAgent not initialized"**: Check your Google API key
- **"Event loop is closed"**: Normal on shutdown, can be ignored
- **CORS errors**: Ensure `ALLOW_CORS=true` in `.env`

## 📝 API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Powered by [Google Gemini](https://deepmind.google/technologies/gemini/)
- Implements [Model Context Protocol](https://modelcontextprotocol.io/)
- REST API by [FastAPI](https://fastapi.tiangolo.com/)

## API Payload
/chat/completions  
{
  "messages": [
    {
      "role": "user",
      "content": "Hi how are you?"
    }
  ],
  "max_tokens": 2000,
  "temperature": 0.7
}
