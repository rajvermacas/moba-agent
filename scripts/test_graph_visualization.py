#!/usr/bin/env python3
"""
Test script for graph visualization feature.
Tests the graph generation with various query results.
"""

import asyncio
import json
import logging
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from moba_agent.graph_visualization import analyze_and_generate_graph
from moba_agent.graph_utils import (
    is_suitable_for_visualization,
    analyze_data_characteristics
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test data samples
TEST_QUERY_RESULTS = [
    # 1. Time series data - should generate line chart
    {
        "query": "SELECT date, revenue FROM sales ORDER BY date",
        "rows": [
            {"date": "2024-01-01", "revenue": 10000},
            {"date": "2024-01-02", "revenue": 12000},
            {"date": "2024-01-03", "revenue": 11500},
            {"date": "2024-01-04", "revenue": 13000},
            {"date": "2024-01-05", "revenue": 14500},
        ],
        "columns": ["date", "revenue"],
        "row_count": 5
    },
    
    # 2. Category comparison - should generate bar chart
    {
        "query": "SELECT category, total_sales FROM product_sales",
        "rows": [
            {"category": "Electronics", "total_sales": 50000},
            {"category": "Clothing", "total_sales": 35000},
            {"category": "Books", "total_sales": 20000},
            {"category": "Sports", "total_sales": 15000},
            {"category": "Toys", "total_sales": 10000},
        ],
        "columns": ["category", "total_sales"],
        "row_count": 5
    },
    
    # 3. Distribution data - should generate pie chart
    {
        "query": "SELECT department, employee_count FROM company_structure",
        "rows": [
            {"department": "Engineering", "employee_count": 120},
            {"department": "Sales", "employee_count": 80},
            {"department": "Marketing", "employee_count": 40},
            {"department": "HR", "employee_count": 20},
            {"department": "Finance", "employee_count": 30},
        ],
        "columns": ["department", "employee_count"],
        "row_count": 5
    },
    
    # 4. Correlation data - should generate scatter plot
    {
        "query": "SELECT age, salary FROM employees",
        "rows": [
            {"age": 25, "salary": 45000},
            {"age": 30, "salary": 55000},
            {"age": 35, "salary": 65000},
            {"age": 40, "salary": 75000},
            {"age": 28, "salary": 50000},
            {"age": 33, "salary": 60000},
            {"age": 45, "salary": 85000},
            {"age": 27, "salary": 48000},
        ],
        "columns": ["age", "salary"],
        "row_count": 8
    },
    
    # 5. Unsuitable data - too few rows
    {
        "query": "SELECT * FROM test_table",
        "rows": [
            {"id": 1, "name": "Test"},
        ],
        "columns": ["id", "name"],
        "row_count": 1
    },
    
    # 6. Unsuitable data - no numeric columns
    {
        "query": "SELECT name, email, address FROM users",
        "rows": [
            {"name": "John", "email": "john@example.com", "address": "123 Main St"},
            {"name": "Jane", "email": "jane@example.com", "address": "456 Oak Ave"},
            {"name": "Bob", "email": "bob@example.com", "address": "789 Pine Rd"},
        ],
        "columns": ["name", "email", "address"],
        "row_count": 3
    }
]


async def test_graph_generation():
    """Test graph generation for various query results."""
    
    for i, query_result in enumerate(TEST_QUERY_RESULTS, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Test {i}: {query_result['query'][:50]}")
        logger.info(f"{'='*60}")
        
        # Test suitability check
        rows = query_result["rows"]
        columns = query_result["columns"]
        
        is_suitable = is_suitable_for_visualization(rows, columns)
        logger.info(f"Suitable for visualization: {is_suitable}")
        
        if is_suitable:
            # Test data analysis
            analysis = analyze_data_characteristics(rows, columns)
            logger.info(f"Data characteristics:")
            logger.info(f"  - Numeric columns: {analysis['numeric_columns']}")
            logger.info(f"  - Categorical columns: {analysis['categorical_columns']}")
            logger.info(f"  - Date columns: {analysis['date_columns']}")
            logger.info(f"  - Unique counts: {analysis['unique_counts']}")
            
            # Test graph generation (without LLM, will use fallback)
            graph = await analyze_and_generate_graph(query_result, llm=None)
            
            if graph:
                logger.info(f"Generated graph:")
                logger.info(f"  - Chart type: {graph['chart_type']}")
                logger.info(f"  - Data points: {len(graph['data'])}")
                logger.info(f"  - Title: {graph.get('title', 'N/A')}")
                
                # Show sample data point
                if graph['data']:
                    logger.info(f"  - Sample data point: {json.dumps(graph['data'][0], indent=2)}")
            else:
                logger.warning("No graph generated despite suitable data")
        else:
            logger.info("Data not suitable for visualization (expected)")


async def test_integration():
    """Test the full integration flow."""
    logger.info("\n" + "="*60)
    logger.info("Testing Full Integration Flow")
    logger.info("="*60)
    
    # Simulate a query result from MCP tools
    mock_query_result = {
        "query": "SELECT month, sales, costs FROM monthly_performance",
        "rows": [
            {"month": "Jan-2024", "sales": 100000, "costs": 60000},
            {"month": "Feb-2024", "sales": 110000, "costs": 65000},
            {"month": "Mar-2024", "sales": 120000, "costs": 70000},
            {"month": "Apr-2024", "sales": 115000, "costs": 68000},
            {"month": "May-2024", "sales": 130000, "costs": 75000},
            {"month": "Jun-2024", "sales": 140000, "costs": 80000},
        ],
        "columns": ["month", "sales", "costs"],
        "row_count": 6
    }
    
    logger.info(f"Testing with query: {mock_query_result['query']}")
    logger.info(f"Rows: {mock_query_result['row_count']}, Columns: {len(mock_query_result['columns'])}")
    
    # Generate graph
    graph_data = await analyze_and_generate_graph(mock_query_result, llm=None)
    
    if graph_data:
        logger.info("\nGraph Generation SUCCESSFUL!")
        logger.info(f"Chart type: {graph_data['chart_type']}")
        logger.info(f"Data points: {len(graph_data['data'])}")
        logger.info("\nFull graph data structure:")
        logger.info(json.dumps(graph_data, indent=2))
    else:
        logger.error("Graph generation failed!")


def main():
    """Main test runner."""
    logger.info("Starting Graph Visualization Tests")
    
    # Run tests
    asyncio.run(test_graph_generation())
    asyncio.run(test_integration())
    
    logger.info("\n" + "="*60)
    logger.info("All tests completed!")
    logger.info("="*60)


if __name__ == "__main__":
    main()