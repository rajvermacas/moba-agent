#!/usr/bin/env python3
"""
Test script to verify moba_server endpoints work correctly after integration.
"""

import asyncio
import json
from src.moba_server.main import app
from src.moba_server.chat_handler import chat_handler
from src.moba_server.models import ChatCompletionRequest, ChatMessage, MessageRole


async def test_endpoints():
    """Test all endpoints to ensure they work correctly."""
    
    print("Testing moba_server endpoints after MCPAgent integration...\n")
    
    # Test 1: Root endpoint
    print("1. Testing GET / endpoint...")
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert data["endpoints"]["chat_completions"] == "/chat/completions"
    print("   ✓ Root endpoint works correctly\n")
    
    # Test 2: Health endpoint
    print("2. Testing GET /health endpoint...")
    # We need to run this async since it initializes the handler
    
    # Initialize handler first
    await chat_handler.ensure_initialized()
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "mcp_server_status" in data
    print(f"   ✓ Health endpoint works - Status: {data['mcp_server_status']}\n")
    
    # Test 3: Models endpoint
    print("3. Testing GET /models endpoint...")
    response = client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) > 0
    assert data["data"][0]["owned_by"] == "google"
    print(f"   ✓ Models endpoint works - Model: {data['data'][0]['id']}\n")
    
    # Test 4: MCP Status endpoint
    print("4. Testing GET /mcp/status endpoint...")
    response = client.get("/mcp/status")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data
    if data["connected"]:
        print(f"   ✓ MCP status endpoint works - Connected to {len(data.get('servers', []))} servers\n")
    else:
        print(f"   ✓ MCP status endpoint works - Not connected (expected if no MCP servers running)\n")
    
    # Test 5: Debug Agent endpoint
    print("5. Testing GET /debug/agent endpoint...")
    response = client.get("/debug/agent")
    assert response.status_code == 200
    data = response.json()
    assert "agent_initialized" in data
    assert "tools_count" in data
    print(f"   ✓ Debug endpoint works - Agent initialized: {data['agent_initialized']}, Tools: {data['tools_count']}\n")
    
    # Test 6: Chat Completions endpoint (the main one!)
    print("6. Testing POST /chat/completions endpoint...")
    request_data = {
        "messages": [
            {"role": "user", "content": "Hello, can you help me?"}
        ]
    }
    response = client.post("/chat/completions", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert "message" in data["choices"][0]
    assert data["choices"][0]["message"]["role"] == "assistant"
    print(f"   ✓ Chat completions endpoint works!\n")
    print(f"   Response: {data['choices'][0]['message']['content'][:100]}...\n")
    
    # Test 7: Integration Test endpoint
    print("7. Testing GET /test/integration endpoint...")
    response = client.get("/test/integration")
    assert response.status_code == 200
    data = response.json()
    assert "agent_initialized" in data
    print(f"   ✓ Integration test endpoint works - Results: {json.dumps(data, indent=2)}\n")
    
    print("=" * 50)
    print("✅ ALL ENDPOINTS WORKING CORRECTLY!")
    print("The integration of moba_server with MCPAgent is successful.")
    print("All endpoints maintain their exact paths and functionality.")
    print("=" * 50)


if __name__ == "__main__":
    print("Starting endpoint verification...\n")
    asyncio.run(test_endpoints())