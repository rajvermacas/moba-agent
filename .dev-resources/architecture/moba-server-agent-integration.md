# MOBA Server-Agent Integration Architecture

## Executive Summary

This document outlines the architectural approach for integrating `moba_server` and `moba_agent` to eliminate code duplication and create a clean separation of concerns. The REST server functionality remains in `moba_server` while all LLM and MCP capabilities are consolidated in `moba_agent`.

## Current State Analysis

### Problem Statement
- **Duplication**: Both `moba_server` and `moba_agent` have MCP client and LLM management code
- **Maintenance overhead**: Two codebases implementing similar functionality
- **Inconsistency risk**: Features may diverge between implementations

### Existing Architecture

#### moba_agent
- **Core Class**: `MCPAgent` - Fully-featured MCP and LLM integration
- **Capabilities**:
  - MCP client management
  - LLM initialization and configuration
  - Tool and resource handling
  - Streaming support
  - Session management

#### moba_server
- **Current Components**:
  - REST API endpoints
  - chat_handler
  - mcp_aggregator (to be removed)
  - llm_manager (to be removed)
  - Authentication/middleware

## Proposed Architecture: Lean Library Integration

### Design Philosophy
- **Simplicity First**: Direct import over network calls
- **Minimal Changes**: Leverage existing code
- **Zero Overhead**: No serialization or network latency
- **Single Deployment**: Easier to manage and debug

### Architecture Diagram

```
┌─────────────────┐
│   REST Client   │
└────────┬────────┘
         │ HTTP/WebSocket
         ▼
┌─────────────────────────────┐
│       moba_server           │
├─────────────────────────────┤
│ • FastAPI Application       │
│ • REST Endpoints            │
│ • Authentication            │
│ • CORS/Rate Limiting        │
│ • Request Validation        │
│ • chat_handler (modified)   │
└─────────┬───────────────────┘
          │ Direct Import
          ▼
┌─────────────────────────────┐
│       moba_agent            │
├─────────────────────────────┤
│ • MCPAgent Class            │
│ • MCP Client Management     │
│ • LLM Integration           │
│ • Tools/Resources           │
│ • Config Management         │
└─────────────────────────────┘
```

### Implementation Algorithm

#### Step 1: Prepare moba_agent as a Library
```python
# No changes needed - moba_agent already structured as a package
# Ensure pyproject.toml has proper package configuration
```

#### Step 2: Modify moba_server Dependencies
```toml
# In moba_server's pyproject.toml
[dependencies]
moba-agent = { path = "../moba-agent" }  # For development
# Or for production: moba-agent = "^1.0.0"
```

#### Step 3: Update chat_handler
```python
# moba_server/handlers/chat_handler.py
from moba_agent import MCPAgent
from moba_agent.config import MCPConfig

class ChatHandler:
    def __init__(self):
        # Initialize MCPAgent with config
        config = MCPConfig.from_env()
        self.agent = MCPAgent(config)
        self.agent.initialize()
    
    async def handle_chat(self, message: str, thread_id: str):
        # Direct delegation to MCPAgent
        response = await self.agent.invoke(
            message=message,
            thread_id=thread_id
        )
        return response
    
    async def handle_stream(self, message: str, thread_id: str):
        # Stream responses
        async for chunk in self.agent.stream(
            message=message,
            thread_id=thread_id
        ):
            yield chunk
```

#### Step 4: Remove Redundant Code from moba_server
Files/modules to delete:
- `mcp_aggregator/` - entire module
- `llm_manager/` - entire module  
- Any MCP client initialization code
- Any LLM configuration code
- Duplicate tool/resource handling

#### Step 5: Keep in moba_server
Retain these components:
- FastAPI application setup
- REST endpoint definitions
- Authentication middleware
- CORS configuration
- Rate limiting
- Request/response models
- Error handling
- Logging configuration

## Detailed Implementation Plan

### Phase 1: Setup (Day 1)
1. **Update Dependencies**
   - Add moba_agent to moba_server requirements
   - Test import resolution
   - Verify no circular dependencies

2. **Configuration Alignment**
   - Ensure environment variables are compatible
   - Merge any moba_server-specific configs into moba_agent

### Phase 2: Integration (Day 2-3)
1. **Modify chat_handler**
   ```python
   # Before
   from moba_server.mcp_aggregator import MCPAggregator
   from moba_server.llm_manager import LLMManager
   
   # After  
   from moba_agent import MCPAgent
   ```

2. **Update Endpoints**
   - `/chat` - delegate to `agent.invoke()`
   - `/stream` - delegate to `agent.stream()`
   - `/tools` - delegate to `agent.get_available_tools()`
   - `/resources` - delegate to `agent.get_available_resources()`

3. **Session Management**
   - Use MCPAgent's built-in session handling
   - Map REST session tokens to agent thread_ids

### Phase 3: Cleanup (Day 4)
1. **Delete Redundant Code**
   - Remove mcp_aggregator module
   - Remove llm_manager module
   - Clean up unused imports
   - Delete redundant configuration files

2. **Update Tests**
   - Mock MCPAgent in moba_server tests
   - Ensure integration tests pass
   - Update documentation

### Phase 4: Validation (Day 5)
1. **Testing**
   - Unit tests for modified handlers
   - Integration tests for end-to-end flow
   - Performance testing
   - Load testing

2. **Documentation**
   - Update API documentation
   - Update deployment guides
   - Create migration guide

## Configuration Management

### Environment Variables
```bash
# Shared configuration (used by both)
LLM_API_KEY=xxx
LLM_MODEL=gpt-4
MCP_SERVERS_CONFIG=./mcp_servers.json

# moba_server specific
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
CORS_ORIGINS=["*"]
RATE_LIMIT=100/minute

# moba_agent specific (if needed)
AGENT_MEMORY_TYPE=sqlite
AGENT_CHECKPOINTER_PATH=./checkpoints
```

### Config Loading Strategy
```python
# moba_server startup
def create_app():
    # Load server config
    server_config = load_server_config()
    
    # Initialize agent with its config
    agent_config = MCPConfig.from_env()
    agent = MCPAgent(agent_config)
    
    # Inject into handlers
    chat_handler = ChatHandler(agent)
    
    # Setup routes
    setup_routes(app, chat_handler)
```

## Benefits of This Approach

### Immediate Benefits
1. **Zero Network Overhead**: No HTTP/gRPC calls between services
2. **Simplified Debugging**: Single process, easier stack traces
3. **Reduced Complexity**: No serialization/deserialization
4. **Faster Development**: Changes immediately reflected

### Long-term Benefits
1. **Code Reuse**: Single implementation of MCP/LLM logic
2. **Consistency**: One source of truth for agent behavior
3. **Maintainability**: Updates in one place
4. **Testing**: Easier to mock and test

## Migration Path

### Current State
```
moba_server/
├── handlers/
│   ├── chat_handler.py (uses mcp_aggregator)
├── mcp_aggregator/
│   ├── __init__.py
│   ├── client.py
│   └── manager.py
├── llm_manager/
│   ├── __init__.py
│   └── manager.py
└── main.py
```

### Target State
```
moba_server/
├── handlers/
│   ├── chat_handler.py (uses moba_agent.MCPAgent)
├── main.py
└── requirements.txt (includes moba_agent)

[mcp_aggregator and llm_manager deleted]
```

## Implementation Checklist

- [ ] Update moba_server dependencies
- [ ] Modify chat_handler to use MCPAgent
- [ ] Update all REST endpoints
- [ ] Delete mcp_aggregator module
- [ ] Delete llm_manager module
- [ ] Update configuration management
- [ ] Modify unit tests
- [ ] Run integration tests
- [ ] Update documentation

## Success Metrics

1. **Code Reduction**: >30% less code in moba_server
2. **Performance**: No degradation in response time
3. **Reliability**: Same or better error rates
4. **Maintainability**: Single place for MCP/LLM updates
5. **Developer Experience**: Simpler debugging and testing

## Conclusion

The lean library integration approach provides the optimal balance of simplicity, performance, and maintainability. It eliminates code duplication while keeping the architecture straightforward and debuggable. This approach allows for future evolution to microservices if needed, without over-engineering the current solution.

The key principle: **Start simple, evolve as needed.**