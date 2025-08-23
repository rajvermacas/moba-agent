# Multi-MCP Server Configuration

This document describes how to configure multiple MCP (Model Context Protocol) servers for the LangGraph Agent.

## Overview

The LangGraph Agent now supports configuring multiple MCP servers through a JSON configuration file. This allows you to:
- Connect to multiple MCP servers simultaneously
- Use different transport protocols (SSE, stdio, HTTP, WebSocket)
- Enable/disable servers without code changes
- Use environment variable substitution for sensitive data

## Configuration File

By default, the agent looks for `mcp_servers.json` in the project root. You can override this with the `MCP_CONFIG_FILE` environment variable.

### Basic Structure

```json
{
  "mcp_servers": [
    {
      "name": "server_name",
      "transport": "transport_type",
      "enabled": true,
      // transport-specific configuration
    }
  ]
}
```

## Transport Types

### SSE (Server-Sent Events)

```json
{
  "name": "sse_server",
  "transport": "sse",
  "url": "http://localhost:8000/sse",
  "enabled": true,
  "reconnect": {
    "enabled": true,
    "max_attempts": 5,
    "delay_ms": 1000
  }
}
```

### STDIO (Standard Input/Output)

```json
{
  "name": "stdio_server",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem"],
  "env": {
    "CUSTOM_VAR": "value"
  },
  "enabled": true
}
```

### HTTP

```json
{
  "name": "http_server",
  "transport": "http",
  "url": "http://localhost:9000/api",
  "headers": {
    "Authorization": "Bearer token"
  },
  "enabled": true
}
```

### WebSocket

```json
{
  "name": "websocket_server",
  "transport": "websocket",
  "url": "ws://localhost:8080/ws",
  "enabled": true
}
```

## Environment Variable Substitution

Use `${VARIABLE_NAME}` syntax to substitute environment variables:

```json
{
  "name": "github_server",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_TOKEN": "${GITHUB_TOKEN}"
  },
  "enabled": true
}
```

## Enabling/Disabling Servers

Set `"enabled": false` to disable a server without removing its configuration:

```json
{
  "name": "disabled_server",
  "transport": "sse",
  "url": "http://localhost:8000/sse",
  "enabled": false
}
```

## Backward Compatibility

If no JSON configuration file is found, the system falls back to environment variables:
- `MCP_SERVER_URL`
- `MCP_SERVER_NAME`
- `MCP_TRANSPORT`
- `SSE_RECONNECT_ENABLED`
- `SSE_RECONNECT_MAX_ATTEMPTS`
- `SSE_RECONNECT_DELAY_MS`

## Examples

See `mcp_servers.example.json` for a comprehensive example with various server types.

### Minimal Configuration

```json
{
  "mcp_servers": [
    {
      "name": "my_server",
      "transport": "sse",
      "url": "http://localhost:8000/sse",
      "enabled": true
    }
  ]
}
```

### Multiple Servers

```json
{
  "mcp_servers": [
    {
      "name": "main_server",
      "transport": "sse",
      "url": "http://localhost:8000/sse",
      "enabled": true
    },
    {
      "name": "filesystem",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem"],
      "enabled": true
    },
    {
      "name": "database",
      "transport": "http",
      "url": "http://db-server:9000/api",
      "enabled": true
    }
  ]
}
```

## Testing Configuration

Use the test script to verify your configuration:

```bash
python scripts/test_multi_mcp_config.py
```

This will:
1. Load and validate your JSON configuration
2. Display all loaded MCP servers
3. Show the configuration that will be passed to MultiServerMCPClient
4. Test fallback to environment variables

## Troubleshooting

### Common Issues

1. **JSON Parse Error**: Ensure your JSON is valid (no trailing commas, proper quotes)
2. **Missing Required Fields**: Each server needs `name` and `transport` at minimum
3. **Environment Variables Not Substituted**: Check that the variables are set in your environment
4. **Server Not Loading**: Verify `enabled` is set to `true`

### Validation Errors

The configuration validates:
- Required fields based on transport type
- SSE/HTTP servers need `url`
- STDIO servers need `command`
- All servers need `name` and `transport`

### Logging

Set `LOG_LEVEL=DEBUG` to see detailed configuration loading information:

```bash
LOG_LEVEL=DEBUG python scripts/run_agent.py
```