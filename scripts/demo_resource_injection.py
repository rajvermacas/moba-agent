#!/usr/bin/env python3
"""
Demo script showcasing MCP resource injection feature

This script demonstrates how the agent automatically injects
MCP resources information into the LLM context on the first
message of each conversation thread.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.langgraph_agent_mcp.agent import MCPAgent
from src.langgraph_agent_mcp.config import Config


async def demo_resource_injection():
    """Demonstrate resource injection feature"""
    
    # Setup logging to see injection messages
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 70)
    print("MCP Resource Injection Demo")
    print("Enhanced: Now with full resource content fetching!")
    print("=" * 70)
    print()
    
    try:
        # Initialize agent
        print("Initializing MCP Agent...")
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        print("Agent initialized successfully!")
        print()
        
        # Check available resources and their content
        print("Fetching all resources with content...")
        resources_with_content = await agent.resource_handler.get_all_resources(max_content_size=500)
        
        if resources_with_content:
            print(f"Found {len(resources_with_content)} available MCP resources:")
            successful_fetches = sum(1 for r in resources_with_content if r.get('fetch_status') == 'success')
            print(f"Successfully fetched content for {successful_fetches}/{len(resources_with_content)} resources")
            print()
            
            for resource in resources_with_content[:2]:  # Show first 2 resources
                print(f"  Resource: {resource.get('name', 'Unnamed')}")
                print(f"    URI: {resource.get('uri', 'Unknown URI')}")
                print(f"    Type: {resource.get('mimeType', 'Unknown')}")
                print(f"    Status: {resource.get('fetch_status', 'unknown')}")
                
                if resource.get('fetch_status') == 'success' and resource.get('content'):
                    content_preview = resource['content'][:100] if len(resource['content']) > 100 else resource['content']
                    print(f"    Content Preview: {content_preview}...")
                elif resource.get('fetch_status') == 'failed':
                    print(f"    Error: {resource.get('fetch_error', 'Unknown error')}")
                print()
            
            if len(resources_with_content) > 2:
                print(f"  ... and {len(resources_with_content) - 2} more resources")
        else:
            print("No MCP resources available. Resources would be injected if available.")
        print()
        
        # Demonstrate first message with resource injection
        print("-" * 60)
        print("THREAD 1: First Message (Resources will be injected)")
        print("-" * 60)
        
        response1 = await agent.invoke(
            "Hello! Can you tell me what resources you have access to?",
            thread_id="demo_thread_1"
        )
        print(f"Response: {response1[:200]}...")
        print()
        
        # Demonstrate second message in same thread (no injection)
        print("-" * 60)
        print("THREAD 1: Second Message (No resource injection)")
        print("-" * 60)
        
        response2 = await agent.invoke(
            "Thanks! What can you help me with?",
            thread_id="demo_thread_1"
        )
        print(f"Response: {response2[:200]}...")
        print()
        
        # Demonstrate new thread (resources injected again)
        print("-" * 60)
        print("THREAD 2: First Message (Resources will be injected)")
        print("-" * 60)
        
        response3 = await agent.invoke(
            "Hi there! I'm starting a new conversation.",
            thread_id="demo_thread_2"
        )
        print(f"Response: {response3[:200]}...")
        print()
        
        # Show thread tracking
        print("-" * 60)
        print("Resource Injection Tracking:")
        print("-" * 60)
        print(f"Threads with injected resources: {list(agent._thread_resources_injected.keys())}")
        print()
        
        # Demonstrate streaming with resource injection
        print("-" * 60)
        print("THREAD 3: Streaming with Resource Injection")
        print("-" * 60)
        
        print("Streaming response chunks:")
        chunk_count = 0
        async for chunk in agent.stream(
            "Can you list the resources available to you?",
            thread_id="demo_thread_3"
        ):
            chunk_count += 1
            if chunk_count <= 3:  # Show first 3 chunks
                print(f"  Chunk {chunk_count}: {str(chunk)[:100]}...")
        print(f"  ... received {chunk_count} total chunks")
        print()
        
        # Final status
        print("=" * 70)
        print("Demo Complete!")
        print("=" * 70)
        print()
        print("Key Features Demonstrated:")
        print("✓ Resources automatically fetched with full content")
        print("✓ Content injected into LLM context on first message")
        print("✓ No duplicate injection on subsequent messages in same thread")
        print("✓ Each new thread gets fresh resource context with content")
        print("✓ Works with both invoke() and stream() methods")
        print("✓ Parallel fetching for better performance")
        print("✓ Graceful handling of fetch failures and missing resources")
        
    except Exception as e:
        print(f"Error during demo: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        if 'agent' in locals():
            await agent.close()
            print("\nAgent closed successfully.")


async def main():
    """Main entry point"""
    print("Starting MCP Resource Injection Demo...")
    print()
    
    # Check for required environment variables
    if not os.getenv('GOOGLE_API_KEY'):
        print("ERROR: GOOGLE_API_KEY environment variable not set")
        print("Please set it before running the demo:")
        print("  export GOOGLE_API_KEY='your-api-key'")
        return
    
    if not os.getenv('MCP_SERVER_URL'):
        print("WARNING: MCP_SERVER_URL environment variable not set")
        print("Using default: http://localhost:3000/mcp")
        print()
    
    await demo_resource_injection()


if __name__ == "__main__":
    asyncio.run(main())