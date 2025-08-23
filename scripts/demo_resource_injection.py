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
    
    print("=" * 60)
    print("MCP Resource Injection Demo")
    print("=" * 60)
    print()
    
    try:
        # Initialize agent
        print("Initializing MCP Agent...")
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        print("Agent initialized successfully!")
        print()
        
        # Check available resources
        resources = await agent.get_available_resources()
        if resources:
            print(f"Found {len(resources)} available MCP resources:")
            for resource in resources[:3]:  # Show first 3 resources
                print(f"  - {resource.get('name', 'Unnamed')}: {resource.get('uri', 'Unknown URI')}")
            if len(resources) > 3:
                print(f"  ... and {len(resources) - 3} more resources")
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
        print("=" * 60)
        print("Demo Complete!")
        print("=" * 60)
        print()
        print("Key Features Demonstrated:")
        print("✓ Resources automatically injected on first message per thread")
        print("✓ No duplicate injection on subsequent messages in same thread")
        print("✓ Each new thread gets fresh resource context")
        print("✓ Works with both invoke() and stream() methods")
        print("✓ Graceful handling when no resources available")
        
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