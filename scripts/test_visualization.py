#!/usr/bin/env python
"""
Test script for data visualization features
"""

import asyncio
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.moba_agent.visualization import DataVisualizationAnalyzer
from src.moba_agent.data_transformer import DataTransformer


def test_visualization_analyzer():
    """Test the visualization analyzer with sample data"""
    print("\n=== Testing Visualization Analyzer ===")
    
    analyzer = DataVisualizationAnalyzer()
    
    # Test 1: Time series data
    query_result_1 = {
        "columns": ["date", "revenue", "profit"],
        "rows": [
            {"date": "2024-01-01", "revenue": 10000, "profit": 2000},
            {"date": "2024-01-02", "revenue": 12000, "profit": 2500},
            {"date": "2024-01-03", "revenue": 15000, "profit": 3200},
            {"date": "2024-01-04", "revenue": 11000, "profit": 2100},
            {"date": "2024-01-05", "revenue": 13000, "profit": 2800}
        ],
        "row_count": 5,
        "query": "SELECT date, revenue, profit FROM sales"
    }
    
    viz_spec_1 = analyzer.analyze_query_result(query_result_1)
    print(f"\nTest 1 - Time Series Data:")
    print(f"  Recommended Chart: {viz_spec_1['chart_type']}")
    print(f"  Column Types: {viz_spec_1['column_types']}")
    print(f"  Alternatives: {viz_spec_1['alternatives']}")
    assert viz_spec_1['chart_type'] == 'line', "Should recommend line chart for time series"
    
    # Test 2: Categorical data
    query_result_2 = {
        "columns": ["category", "count"],
        "rows": [
            {"category": "Electronics", "count": 150},
            {"category": "Clothing", "count": 230},
            {"category": "Books", "count": 80},
            {"category": "Home", "count": 120},
            {"category": "Sports", "count": 95}
        ],
        "row_count": 5,
        "query": "SELECT category, count FROM products"
    }
    
    viz_spec_2 = analyzer.analyze_query_result(query_result_2)
    print(f"\nTest 2 - Categorical Data:")
    print(f"  Recommended Chart: {viz_spec_2['chart_type']}")
    print(f"  Column Types: {viz_spec_2['column_types']}")
    assert viz_spec_2['chart_type'] in ['bar', 'pie'], "Should recommend bar or pie chart for categories"
    
    # Test 3: Numeric scatter data
    query_result_3 = {
        "columns": ["height", "weight", "age"],
        "rows": [
            {"height": 170, "weight": 70, "age": 25},
            {"height": 180, "weight": 85, "age": 30},
            {"height": 165, "weight": 60, "age": 22},
            {"height": 175, "weight": 75, "age": 28},
            {"height": 185, "weight": 90, "age": 35}
        ],
        "row_count": 5,
        "query": "SELECT height, weight, age FROM users"
    }
    
    viz_spec_3 = analyzer.analyze_query_result(query_result_3)
    print(f"\nTest 3 - Numeric Data:")
    print(f"  Recommended Chart: {viz_spec_3['chart_type']}")
    print(f"  Column Types: {viz_spec_3['column_types']}")
    assert viz_spec_3['chart_type'] == 'scatter', "Should recommend scatter plot for numeric columns"
    
    print("\n✅ All visualization analyzer tests passed!")


def test_data_transformer():
    """Test the data transformer with various chart types"""
    print("\n=== Testing Data Transformer ===")
    
    transformer = DataTransformer()
    
    # Test 1: Bar chart transformation
    query_result = {
        "columns": ["category", "value"],
        "rows": [
            {"category": "A", "value": 10},
            {"category": "B", "value": 20},
            {"category": "C", "value": 15}
        ],
        "row_count": 3
    }
    
    config = {
        "xAxis": {"field": "category"},
        "yAxis": {"fields": ["value"]}
    }
    
    transformed = transformer.transform_for_chart(query_result, "bar", config)
    print(f"\nTest 1 - Bar Chart Transformation:")
    print(f"  Categories: {transformed.get('categories', [])}")
    print(f"  Data points: {len(transformed.get('data', []))}")
    assert 'data' in transformed, "Should have transformed data"
    
    # Test 2: Pie chart transformation
    pie_data = transformer.transform_for_chart(query_result, "pie", {
        "labels": {"field": "category"},
        "values": {"field": "value"}
    })
    print(f"\nTest 2 - Pie Chart Transformation:")
    print(f"  Slices: {len(pie_data.get('slices', []))}")
    print(f"  Total: {pie_data.get('total', 0)}")
    assert 'slices' in pie_data, "Should have pie slices"
    assert pie_data['total'] == 45, "Total should be sum of values"
    
    # Test 3: Line chart transformation
    time_series = {
        "columns": ["date", "value1", "value2"],
        "rows": [
            {"date": "2024-01-01", "value1": 10, "value2": 20},
            {"date": "2024-01-02", "value1": 15, "value2": 25},
            {"date": "2024-01-03", "value1": 12, "value2": 22}
        ],
        "row_count": 3
    }
    
    line_config = {
        "xAxis": {"field": "date"},
        "yAxis": {"fields": ["value1", "value2"]}
    }
    
    line_data = transformer.transform_for_chart(time_series, "line", line_config)
    print(f"\nTest 3 - Line Chart Transformation:")
    print(f"  Series count: {len(line_data.get('series', []))}")
    print(f"  Points per series: {len(line_data['series'][0]['data']) if line_data.get('series') else 0}")
    assert len(line_data.get('series', [])) == 2, "Should have two series"
    
    print("\n✅ All data transformer tests passed!")


def test_integration():
    """Test the integration of analyzer and transformer"""
    print("\n=== Testing Integration ===")
    
    analyzer = DataVisualizationAnalyzer()
    transformer = DataTransformer()
    
    # Sample multi-series data
    query_result = {
        "columns": ["month", "sales", "expenses", "profit"],
        "rows": [
            {"month": "Jan", "sales": 10000, "expenses": 7000, "profit": 3000},
            {"month": "Feb", "sales": 12000, "expenses": 8000, "profit": 4000},
            {"month": "Mar", "sales": 15000, "expenses": 9000, "profit": 6000},
            {"month": "Apr", "sales": 11000, "expenses": 7500, "profit": 3500}
        ],
        "row_count": 4,
        "query": "SELECT month, sales, expenses, profit FROM financials"
    }
    
    # Analyze
    viz_spec = analyzer.analyze_query_result(query_result)
    print(f"\nAnalysis Result:")
    print(f"  Recommended: {viz_spec['chart_type']}")
    print(f"  Config: {json.dumps(viz_spec['config'], indent=2)}")
    
    # Transform
    chart_data = transformer.transform_for_chart(
        query_result,
        viz_spec['chart_type'],
        viz_spec['config']
    )
    
    print(f"\nTransformation Result:")
    print(f"  Data type: {chart_data.get('type', 'unknown')}")
    if 'series' in chart_data and isinstance(chart_data['series'], list):
        print(f"  Series count: {len(chart_data['series'])}")
        for i, series in enumerate(chart_data['series']):
            if isinstance(series, dict) and 'name' in series and 'data' in series:
                print(f"    - {series['name']}: {len(series['data'])} points")
            elif isinstance(series, str):
                print(f"    - Series {i+1}: {series}")
    elif 'data' in chart_data:
        print(f"  Data points: {len(chart_data['data'])}")
    
    print("\n✅ Integration test passed!")


def main():
    """Main test runner"""
    print("=" * 50)
    print("DATA VISUALIZATION TEST SUITE")
    print("=" * 50)
    
    try:
        test_visualization_analyzer()
        test_data_transformer()
        test_integration()
        
        print("\n" + "=" * 50)
        print("✨ ALL TESTS PASSED SUCCESSFULLY! ✨")
        print("=" * 50)
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())