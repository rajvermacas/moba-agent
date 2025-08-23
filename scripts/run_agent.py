#!/usr/bin/env python3
"""
Run the MCP Agent with interactive chat
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.moba_agent.main import MCPAgentApp


async def main():
    """Main entry point"""
    print("Starting MCP Agent with Gemini 2.5 Flash...")
    
    app = MCPAgentApp()
    
    try:
        # Check for streaming mode
        if '--stream' in sys.argv:
            print("Running in streaming mode...")
            await app.run_stream()
        else:
            print("Running in interactive mode...")
            await app.run_interactive()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())