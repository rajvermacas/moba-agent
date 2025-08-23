"""
Main FastAPI application for chat completions with OpenRouter and MCP integration.
"""

import logging
import time
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import config
from .models import (
    ChatCompletionRequest, ChatCompletionResponse, 
    ErrorResponse, HealthResponse, ErrorDetail
)
from .chat_handler import chat_handler

# Ensure logs directory exists
log_dir = config.log_dir
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, "moba_server.log")

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=log_file_path,
    filemode='a'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting FastAPI server for Talk2Tables")
    logger.info("Using MCPAgent with Gemini for LLM and MCP integration")
    
    # Initialize chat handler with MCPAgent
    try:
        await chat_handler.initialize()
        logger.info("✓ MCPAgent initialized successfully")
        
        # Get available tools and resources
        if chat_handler.agent:
            tools = await chat_handler.get_available_tools()
            resources = await chat_handler.get_available_resources()
            logger.info(f"Available tools: {len(tools)}")
            logger.info(f"Available resources: {len(resources)}")
        
        logger.info("✓ MCPAgent connection successful")
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI server")
    try:
        if chat_handler.agent:
            await chat_handler.agent.close()
            logger.info("MCPAgent disconnected")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="Talk2Tables FastAPI Server",
    description="Chat completions API with database query capabilities via MCP",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
if config.allow_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                message="Internal server error",
                type="internal_error",
                code="500"
            )
        ).dict()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Ensure aggregator is initialized
        await chat_handler.ensure_initialized()
        
        # Test MCP connection - check if agent is initialized
        mcp_status = "disconnected"
        if chat_handler.agent:
            mcp_status = "connected"
        
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            timestamp=int(time.time()),
            mcp_server_status=mcp_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service unhealthy"
        )


@app.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(request: ChatCompletionRequest):
    """
    Create a chat completion with database query capabilities.
    
    This endpoint provides OpenAI-compatible chat completions enhanced with
    database query capabilities through MCP server integration.
    """
    try:
        logger.info(f"Received chat completion request with {len(request.messages)} messages")
        
        # Validate request
        if not request.messages:
            raise HTTPException(
                status_code=400,
                detail="Messages array cannot be empty"
            )
        
        # Process the chat completion
        response = await chat_handler.process_chat_completion(request)
        
        logger.info(f"Successfully processed chat completion request, response={response}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat completion: {str(e)}"
        )


@app.get("/models")
async def list_models():
    """List available models (OpenAI-compatible endpoint)."""
    model_id = "gemini-2.0-flash-exp"
    owned_by = "google"
    
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": owned_by,
                "permission": [],
                "root": model_id,
                "parent": None
            }
        ]
    }


@app.get("/mcp/status")
async def mcp_status():
    """Get MCP server status and capabilities."""
    try:
        # Ensure aggregator is initialized
        await chat_handler.ensure_initialized()
        
        # Check connection status
        connected = chat_handler.agent is not None
        
        if not connected:
            return {
                "connected": False,
                "error": "MCPAgent not initialized"
            }
        
        # Get capabilities from MCPAgent
        tools = await chat_handler.get_available_tools()
        resources = await chat_handler.get_available_resources()
        tool_names = [t.get('name', '') for t in tools]
        resource_uris = [r.get('uri', '') for r in resources]
        servers = list(set(r.get('server', 'default') for r in resources))
        
        # Fetch resource data
        all_resources_data = {}
        metadata = {}
        
        try:
            logger.debug("Fetching all resources for status endpoint...")
            
            # Fetch each resource
            for resource in resources:
                resource_uri = resource.get('uri', '')
                try:
                    content = await chat_handler.agent.fetch_resource(resource_uri)
                    all_resources_data[resource_uri] = content
                    
                    # Extract metadata if found
                    if "metadata" in resource_uri.lower() and isinstance(content, dict):
                        metadata = content
                        logger.debug(f"Found metadata in resource: {resource_uri}")
                except Exception as e:
                    logger.error(f"Could not fetch resource {resource_uri}: {e}")
            
            logger.info(f"Status endpoint fetched {len(all_resources_data)} resources")
            
        except Exception as e:
            logger.error(f"Could not fetch resources: {e}")
        
        # Build detailed resource information
        resources_info = []
        for resource in resources:
            resources_info.append({
                "uri": resource.get('uri', ''),
                "server": resource.get('server', 'unknown'),
                "name": resource.get('name', ''),
                "description": resource.get('description', ''),
                "has_data": resource.get('uri', '') in all_resources_data
            })
        
        return {
            "connected": True,
            "servers": servers,
            "tools": tool_names,
            "resources": resources_info,
            "resources_data": all_resources_data,
            "database_metadata": metadata
        }
        
    except Exception as e:
        logger.error(f"Error getting MCP status: {str(e)}")
        return {
            "connected": False,
            "error": str(e)
        }

@app.get("/debug/agent")
async def debug_agent():
    """Debug endpoint to check agent status and available tools."""
    try:
        await chat_handler.ensure_initialized()
        
        # Get agent status
        has_agent = chat_handler.agent is not None
        
        tools_info = []
        mcp_tools = []
        mcp_servers = []
        
        if has_agent:
            # Get tools from MCPAgent
            tools = await chat_handler.get_available_tools()
            for tool in tools:
                tools_info.append({
                    "name": tool.get('name', ''),
                    "description": tool.get('description', '')[:200] + "..." if len(tool.get('description', '')) > 200 else tool.get('description', '')
                })
            mcp_tools = [t.get('name', '') for t in tools]
            
            # Get resources to determine servers
            resources = await chat_handler.get_available_resources()
            mcp_servers = list(set(r.get('server', 'default') for r in resources))
        
        return {
            "agent_initialized": has_agent,
            "tools_available": len(tools_info) > 0,
            "tools_count": len(tools_info),
            "tools": tools_info,
            "mcp_connected": has_agent,
            "mcp_servers": mcp_servers,
            "mcp_tools": mcp_tools,
            "llm_provider": "gemini",
            "llm_available": has_agent
        }
        
    except Exception as e:
        logger.error(f"Debug agent error: {str(e)}")
        logger.exception("Full trace:")
        return {"error": str(e)}


@app.get("/test/integration")
async def test_integration():
    """Test the integration between OpenRouter and MCP."""
    try:
        results = await chat_handler.test_integration()
        return results
    except Exception as e:
        logger.error(f"Integration test failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Integration test failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Talk2Tables FastAPI Server",
        "version": "0.1.0",
        "description": "Chat completions API with database query capabilities",
        "endpoints": {
            "chat_completions": "/chat/completions",
            "health": "/health",
            "models": "/models",
            "mcp_status": "/mcp/status",
            "integration_test": "/test/integration"
        },
        "documentation": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {config.fastapi_host}:{config.fastapi_port}")
    uvicorn.run(
        "moba_server.main:app",
        host=config.fastapi_host,
        port=config.fastapi_port,
        reload=False,
        log_level=config.log_level.lower()
    )