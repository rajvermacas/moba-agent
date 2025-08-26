"""
Main application for LangGraph MCP Agent
"""

import asyncio
import logging
import sys
from typing import Optional
from .agent import MCPAgent
from .config import Config


class MCPAgentApp:
    """Main application class for MCP Agent"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the application
        
        Args:
            config: Configuration object
        """
        self.config = config or Config()
        self.logger = logging.getLogger(__name__)
        self.agent = MCPAgent(self.config)
        self.running = False
    
    async def start(self):
        """Start the application"""
        self.logger.info("Starting MCP Agent Application")
        
        try:
            # Initialize agent
            await self.agent.initialize()
            self.running = True
            
            # Display welcome message
            self._display_welcome()
            
            # Display available tools and resources
            await self._display_capabilities()
            
        except Exception as e:
            self.logger.error(f"Failed to start application: {e}")
            raise
    
    def _display_welcome(self):
        """Display welcome message"""
        print("\n" + "="*60)
        print("🤖 LangGraph MCP Agent with Gemini 2.5 Flash")
        print("="*60)
        server_names = [server['name'] for server in self.config.mcp_servers]
        print(f"Connected to {len(server_names)} MCP Servers: {', '.join(server_names)}")
        print(f"Using model: {self.config.agent_model}")
        print("="*60)
    
    async def _display_capabilities(self):
        """Display available tools and resources"""
        try:
            # Get tools
            tools = await self.agent.get_available_tools()
            print(f"\n📦 Available Tools ({len(tools)}):")
            if tools:
                for tool in tools:
                    print(f"  • {tool['name']}: {tool.get('description', 'No description')}")
            else:
                print("  No tools available")
            
            # Get resources
            resources = await self.agent.get_available_resources()
            print(f"\n📚 Available Resources ({len(resources)}):")
            if resources:
                # Show ALL resources - no truncation for POC
                for resource in resources:
                    print(f"  • {resource['uri']}: {resource.get('name', 'Unnamed')}")
            else:
                print("  No resources available")
            
            print("\n" + "-"*60)
            
        except Exception as e:
            self.logger.error(f"Failed to display capabilities: {e}")
    
    async def run_interactive(self):
        """Run interactive chat session"""
        if not self.running:
            await self.start()
        
        print("\n💬 Interactive Chat Mode")
        print("Type 'help' for commands, 'quit' to exit\n")
        
        thread_id = f"session_{asyncio.get_event_loop().time()}"
        
        while self.running:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() == 'quit':
                    break
                elif user_input.lower() == 'help':
                    self._display_help()
                    continue
                elif user_input.lower() == 'tools':
                    await self._list_tools()
                    continue
                elif user_input.lower() == 'resources':
                    await self._list_resources()
                    continue
                elif user_input.lower().startswith('resource '):
                    uri = user_input[9:].strip()
                    await self._fetch_resource(uri)
                    continue
                elif user_input.lower() == 'clear':
                    thread_id = f"session_{asyncio.get_event_loop().time()}"
                    print("✅ Conversation cleared")
                    continue
                
                # Send to agent
                print("\n🤖 Agent: ", end="", flush=True)
                
                # Get response
                response = await self.agent.invoke(user_input, thread_id)
                # Handle new response format
                if isinstance(response, dict):
                    print(response.get("content", ""))
                    # Optionally log tool results for debugging
                    if response.get("tool_results"):
                        self.logger.debug(f"Tool results: {response['tool_results']}")
                else:
                    print(response)
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Error in interactive session: {e}")
                print(f"\n❌ Error: {e}")
    
    async def run_stream(self):
        """Run with streaming responses"""
        if not self.running:
            await self.start()
        
        print("\n💬 Streaming Chat Mode")
        print("Type 'help' for commands, 'quit' to exit\n")
        
        thread_id = f"stream_{asyncio.get_event_loop().time()}"
        
        while self.running:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() == 'quit':
                    break
                elif user_input.lower() == 'help':
                    self._display_help()
                    continue
                elif user_input.lower() == 'clear':
                    thread_id = f"stream_{asyncio.get_event_loop().time()}"
                    print("✅ Conversation cleared")
                    continue
                
                # Stream from agent
                print("\n🤖 Agent: ", end="", flush=True)
                
                async for chunk in self.agent.stream(user_input, thread_id):
                    # Process and display chunk
                    if isinstance(chunk, dict):
                        if "messages" in chunk:
                            messages = chunk["messages"]
                            if messages:
                                last_message = messages[-1]
                                if hasattr(last_message, 'content'):
                                    print(last_message.content, end="", flush=True)
                    else:
                        print(chunk, end="", flush=True)
                
                print()  # New line after stream
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Error in streaming session: {e}")
                print(f"\n❌ Error: {e}")
    
    def _display_help(self):
        """Display help information"""
        print("\n📖 Available Commands:")
        print("  help      - Show this help message")
        print("  tools     - List available MCP tools")
        print("  resources - List available MCP resources")
        print("  resource <uri> - Fetch a specific resource")
        print("  clear     - Clear conversation history")
        print("  quit      - Exit the application")
    
    async def _list_tools(self):
        """List available tools"""
        try:
            tools = await self.agent.get_available_tools()
            print(f"\n📦 Available Tools ({len(tools)}):")
            for i, tool in enumerate(tools, 1):
                print(f"\n{i}. {tool['name']}")
                if tool.get('description'):
                    print(f"   Description: {tool['description']}")
                if tool.get('parameters'):
                    print(f"   Parameters: {tool['parameters']}")
        except Exception as e:
            print(f"❌ Failed to list tools: {e}")
    
    async def _list_resources(self):
        """List available resources"""
        try:
            resources = await self.agent.get_available_resources()
            print(f"\n📚 Available Resources ({len(resources)}):")
            for i, resource in enumerate(resources, 1):
                print(f"\n{i}. {resource['uri']}")
                if resource.get('name'):
                    print(f"   Name: {resource['name']}")
                if resource.get('description'):
                    print(f"   Description: {resource['description']}")
                if resource.get('mimeType'):
                    print(f"   Type: {resource['mimeType']}")
        except Exception as e:
            print(f"❌ Failed to list resources: {e}")
    
    async def _fetch_resource(self, uri: str):
        """Fetch and display a resource"""
        try:
            print(f"\n📥 Fetching resource: {uri}")
            content = await self.agent.fetch_resource(uri)
            
            if content:
                print("\n📄 Resource Content:")
                if isinstance(content, list):
                    for item in content:
                        print(f"\n{item}")
                else:
                    print(content)
            else:
                print("❌ Resource not found or empty")
                
        except Exception as e:
            print(f"❌ Failed to fetch resource: {e}")
    
    async def stop(self):
        """Stop the application"""
        self.logger.info("Stopping MCP Agent Application")
        self.running = False
        
        if self.agent:
            await self.agent.close()
        
        print("\n👋 Goodbye!")


async def main():
    """Main entry point"""
    app = MCPAgentApp()
    
    try:
        # Check for command line arguments
        if len(sys.argv) > 1 and sys.argv[1] == '--stream':
            await app.run_stream()
        else:
            await app.run_interactive()
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())