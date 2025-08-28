#!/usr/bin/env python3
"""
Test script for dynamic visualization decision based on agent's context.

Tests that visualizations are only created when appropriate based on:
1. User's explicit request
2. Agent's response suggesting visualization would be helpful
3. Nature of the data
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.moba_agent.agent import MCPAgent
from src.moba_agent.config import Config
from unittest.mock import Mock, AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_scenario(agent, message: str, agent_response: str, expected_viz: bool):
    """
    Test a specific scenario with mocked agent response.
    
    Args:
        agent: MCPAgent instance
        message: User's message
        agent_response: Mocked agent response
        expected_viz: Whether visualization should be triggered
    """
    print(f"\n{'='*60}")
    print(f"Testing: {message}")
    print(f"Expected visualization: {expected_viz}")
    print(f"Agent response: {agent_response[:100]}...")
    
    # Mock query result
    mock_query_result = {
        "rows": [
            {"month": "Jan", "sales": 1000},
            {"month": "Feb", "sales": 1200},
            {"month": "Mar", "sales": 1100}
        ],
        "columns": ["month", "sales"],
        "query": "SELECT month, sales FROM monthly_sales"
    }
    
    # Mock agent response
    mock_agent_response = {
        "messages": [
            HumanMessage(content=message),
            AIMessage(content="Executing query..."),
            ToolMessage(
                content=json.dumps(mock_query_result),
                name="execute_query_sales",
                tool_call_id="call_execute_query_sales"
            ),
            AIMessage(content=agent_response)
        ]
    }
    
    with patch.object(agent.agent, 'ainvoke', return_value=mock_agent_response):
        result = await agent.invoke_with_query_tracking(message, thread_id=f"test_{message[:10]}")
        
        # Check if visualization was triggered
        viz_triggered = result.get("graph") is not None
        
        print(f"Visualization triggered: {viz_triggered}")
        print(f"Result: {'✓ PASS' if viz_triggered == expected_viz else '✗ FAIL'}")
        
        if viz_triggered != expected_viz:
            print(f"ERROR: Expected {expected_viz}, got {viz_triggered}")
            return False
        
        return True

async def main():
    """Run all test scenarios"""
    print("="*60)
    print("Dynamic Visualization Decision Testing")
    print("="*60)
    
    # Create agent with mocked components
    config = Config()
    agent = MCPAgent(config=config)
    
    # Mock initialization
    with patch.object(agent, '_initialize_mcp_client', new_callable=AsyncMock):
        with patch.object(agent, '_load_tools', new_callable=AsyncMock):
            with patch.object(agent, '_initialize_llm'):
                with patch.object(agent, '_create_agent', new_callable=AsyncMock):
                    agent.llm = AsyncMock()
                    agent.agent = AsyncMock()
                    
                    # Mock LLM for GraphVisualizationTool
                    agent.llm.ainvoke.return_value = AIMessage(content=json.dumps({
                        "chart_type": "line",
                        "reasoning": "Line chart for time series",
                        "config": {
                            "x_axis": "month",
                            "y_axis": "sales",
                            "title": "Monthly Sales",
                            "color_field": None
                        }
                    }))
                    
                    await agent.initialize()
                    
                    # Test scenarios
                    test_cases = [
                        # (user_message, agent_response, should_visualize)
                        (
                            "Show me a chart of monthly sales",
                            "Here's a chart showing the monthly sales trends. [VISUALIZE=TRUE] The visualization clearly shows the pattern in your data.",
                            True  # Explicit visualization request with marker
                        ),
                        (
                            "List all sales data",
                            "Here are all the sales records from the database. The data shows sales for January through March.",
                            False  # Simple data listing, no marker
                        ),
                        (
                            "What are the sales trends?",
                            "Looking at the sales data, I can see an upward trend from January to February, followed by a slight decline in March. [VISUALIZE=TRUE] A trend chart would help visualize this pattern.",
                            True  # Agent includes marker for trend visualization
                        ),
                        (
                            "Get me the sales numbers",
                            "The sales numbers are: January: 1000, February: 1200, March: 1100.",
                            False  # Just numbers, no marker
                        ),
                        (
                            "Visualize the monthly performance",
                            "I'll create a visualization of the monthly performance. [VISUALIZE=TRUE] The graph shows clear patterns in the data.",
                            True  # Explicit visualization request with marker
                        ),
                        (
                            "How many sales in February?",
                            "In February, there were 1200 sales.",
                            False  # Simple query answer, no marker
                        ),
                        (
                            "Compare sales across months",
                            "Comparing the sales across months, we can see interesting patterns. [VISUALIZE=TRUE] A comparison chart would help illustrate these differences.",
                            True  # Agent includes marker for comparison
                        ),
                        (
                            "Export sales data",
                            "The sales data has been prepared for export. All records are included.",
                            False  # Export request, no visualization marker
                        ),
                        (
                            "Show the data distribution",
                            "The data shows various values across categories. The distribution appears to be skewed.",
                            False  # No marker even though mentions distribution - agent decided viz not needed
                        ),
                        (
                            "Create a graph",
                            "Creating a graph for you. [VISUALIZE=TRUE] This will help you understand the data relationships.",
                            True  # Explicit user request with marker
                        )
                    ]
                    
                    results = []
                    for user_msg, agent_resp, expected in test_cases:
                        success = await test_scenario(agent, user_msg, agent_resp, expected)
                        results.append((user_msg[:30], success))
                    
                    # Summary
                    print("\n" + "="*60)
                    print("Test Summary")
                    print("="*60)
                    
                    passed = sum(1 for _, success in results if success)
                    total = len(results)
                    
                    for msg, success in results:
                        status = "✓ PASS" if success else "✗ FAIL"
                        print(f"{status}: {msg}...")
                    
                    print(f"\nTotal: {passed}/{total} tests passed")
                    
                    if passed == total:
                        print("\n✓ All tests passed! Visualization decision is working correctly.")
                    else:
                        print(f"\n✗ {total - passed} tests failed. Check the logic.")
                    
                    return 0 if passed == total else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)