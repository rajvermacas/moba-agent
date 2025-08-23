#!/usr/bin/env python3
"""
Demonstrate tool execution with the MCP Agent
"""

import asyncio
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.moba_agent import MCPAgent, Config


async def demo_tool_execution():
    """Demonstrate executing MCP tools via the agent"""
    print("MCP Tool Execution Demo")
    print("="*60)
    
    try:
        # Initialize agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Get available tools
        tools = await agent.get_available_tools()
        
        if not tools:
            print("No tools available from MCP server")
            return
        
        print(f"Found {len(tools)} tools available\n")
        
        # Show ALL tools - no truncation for POC
        print("Available tools:")
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool['name']}")
        
        print("\n" + "-"*60)
        
        # Example queries that might use tools
        example_queries = [
            "What tools do you have available?",
            "Can you help me with a calculation?",
            "What's the current date and time?",
            "Can you search for information?",
        ]
        
        print("\nExample queries to test tool usage:")
        for i, query in enumerate(example_queries, 1):
            print(f"  {i}. {query}")
        
        print("\n" + "-"*60)
        
        # Interactive tool testing
        print("\nEnter a query to test tool execution (or 'quit' to exit):")
        
        while True:
            query = input("\n👤 Query: ").strip()
            
            if query.lower() == 'quit':
                break
            
            if not query:
                continue
            
            print("\n🤖 Agent processing with tools...")
            print("-"*40)
            
            # Execute query
            response = await agent.invoke(query)
            
            print("\n📝 Response:")
            print(response)
            
            print("\n" + "-"*60)
        
        # Close agent
        await agent.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


async def demo_specific_tool():
    """Demonstrate executing a specific tool directly"""
    print("\nDirect Tool Execution Demo")
    print("="*60)
    
    try:
        # Initialize agent
        config = Config()
        agent = MCPAgent(config)
        await agent.initialize()
        
        # Get tool handler
        tool_handler = agent.tool_handler
        
        # List tools
        tools = await tool_handler.list_tools()
        
        if not tools:
            print("No tools available")
            return
        
        print(f"\nSelect a tool to execute (1-{len(tools)}):")
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool['name']}")
        
        # Get user selection
        try:
            selection = int(input("\nSelect tool number: ")) - 1
            if 0 <= selection < len(tools):
                selected_tool = tools[selection]
                print(f"\nSelected: {selected_tool['name']}")
                
                # Get parameters if needed
                if selected_tool.get('parameters'):
                    print("\nTool parameters:")
                    print(json.dumps(selected_tool['parameters'], indent=2))
                    
                    print("\nEnter parameters as JSON (or empty for no params):")
                    param_input = input("Parameters: ").strip()
                    
                    if param_input:
                        try:
                            params = json.loads(param_input)
                        except json.JSONDecodeError:
                            print("Invalid JSON, using empty parameters")
                            params = {}
                    else:
                        params = {}
                else:
                    params = {}
                
                # Execute tool
                print(f"\nExecuting {selected_tool['name']}...")
                result = await tool_handler.execute_tool(selected_tool['name'], params)
                
                print("\n📊 Result:")
                formatted_result = tool_handler.format_tool_result(result)
                print(formatted_result)
                
            else:
                print("Invalid selection")
                
        except ValueError:
            print("Invalid input")
        
        # Close agent
        await agent.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


async def main():
    """Main entry point"""
    print("MCP Tool Execution Demo")
    print("\nSelect demo mode:")
    print("1. Test tool execution via agent queries")
    print("2. Execute a specific tool directly")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        await demo_tool_execution()
    elif choice == "2":
        await demo_specific_tool()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())