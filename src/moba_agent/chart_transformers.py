"""
Chart Transformation Functions for Graph Visualization

This module contains functions to transform raw query data into
chart-specific formats compatible with Recharts components.
"""

import logging
import time
from typing import Dict, Any, List
from .graph_utils import _is_numeric, _is_date_like, _parse_date_value


logger = logging.getLogger(__name__)


def _transform_bar_chart(rows: List[Dict], columns: List[str], config: Dict) -> Dict[str, Any]:
    """
    Transform data for Recharts BarChart component.
    
    Expected Recharts format:
    {
        "data": [
            {"name": "Category A", "value": 100, "color": "#8884d8"},
            {"name": "Category B", "value": 200, "color": "#82ca9d"}
        ],
        "x_key": "name",
        "y_key": "value",
        "title": "Chart Title"
    }
    """
    x_col = config["x_axis"]
    y_col = config["y_axis"]
    
    if x_col not in columns or y_col not in columns:
        raise ValueError(f"Columns {x_col}/{y_col} not found in data")
    
    # Transform rows to chart data
    chart_data = []
    colors = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300", "#00ff88", "#ff0088", "#8800ff", "#ffaa00"]
    
    for i, row in enumerate(rows[:20]):  # Limit to 20 bars for readability
        x_val = row.get(x_col, "Unknown")
        y_val = row.get(y_col, 0)
        
        # Convert y value to numeric
        try:
            y_numeric = float(y_val) if y_val is not None else 0
        except (ValueError, TypeError):
            y_numeric = 0
        
        chart_data.append({
            "name": str(x_val),
            "value": y_numeric,
            "color": colors[i % len(colors)]
        })
    
    logger.debug(f"Transformed bar chart with {len(chart_data)} bars")
    
    return {
        "data": chart_data,
        "x_key": "name",
        "y_key": "value",
        "title": config.get("title", "Bar Chart"),
        "x_label": x_col,
        "y_label": y_col
    }


def _transform_line_chart(rows: List[Dict], columns: List[str], config: Dict) -> Dict[str, Any]:
    """
    Transform data for Recharts LineChart component.
    
    Expected format:
    {
        "data": [
            {"x": "2023-01", "y": 100},
            {"x": "2023-02", "y": 150}
        ],
        "x_key": "x",
        "y_key": "y",
        "title": "Line Chart"
    }
    """
    x_col = config["x_axis"]
    y_col = config["y_axis"]
    
    # Sort by x column if it's date-like
    sorted_rows = rows
    if any(_is_date_like(row.get(x_col)) for row in rows[:3]):
        try:
            sorted_rows = sorted(rows, key=lambda r: _parse_date_value(r.get(x_col, "")))
        except (ValueError, TypeError, AttributeError):
            pass  # Keep original order if sorting fails
    
    chart_data = []
    for row in sorted_rows[:100]:  # Limit for performance
        x_val = row.get(x_col)
        y_val = row.get(y_col)
        
        # Convert to appropriate format
        try:
            y_numeric = float(y_val) if y_val is not None else 0
        except (ValueError, TypeError):
            y_numeric = 0
            
        chart_data.append({
            "x": str(x_val) if x_val is not None else "Unknown",
            "y": y_numeric
        })
    
    logger.debug(f"Transformed line chart with {len(chart_data)} points")
    
    return {
        "data": chart_data,
        "x_key": "x",
        "y_key": "y",
        "title": config.get("title", "Line Chart"),
        "x_label": x_col,
        "y_label": y_col,
        "stroke": "#8884d8"
    }


def _transform_pie_chart(rows: List[Dict], columns: List[str], config: Dict) -> Dict[str, Any]:
    """
    Transform data for Recharts PieChart component.
    
    Expected format:
    {
        "data": [
            {"name": "Category A", "value": 100, "fill": "#8884d8"},
            {"name": "Category B", "value": 200, "fill": "#82ca9d"}
        ],
        "name_key": "name",
        "value_key": "value"
    }
    """
    category_col = config["x_axis"]  # Category column
    value_col = config["y_axis"]     # Value column
    
    # Aggregate data by category
    category_totals = {}
    for row in rows:
        category = str(row.get(category_col, "Unknown"))
        value = row.get(value_col, 0)
        
        try:
            numeric_value = float(value) if value is not None else 0
        except (ValueError, TypeError):
            numeric_value = 1  # Count instead of sum for non-numeric
        
        category_totals[category] = category_totals.get(category, 0) + numeric_value
    
    # Limit to top 8 categories
    top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:8]
    
    colors = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300", "#00ff88", "#ff0088", "#8800ff", "#ffaa00"]
    
    chart_data = []
    for i, (category, value) in enumerate(top_categories):
        chart_data.append({
            "name": category,
            "value": value,
            "fill": colors[i % len(colors)]
        })
    
    logger.debug(f"Transformed pie chart with {len(chart_data)} slices")
    
    return {
        "data": chart_data,
        "name_key": "name",
        "value_key": "value",
        "title": config.get("title", "Pie Chart")
    }


def _transform_scatter_chart(rows: List[Dict], columns: List[str], config: Dict) -> Dict[str, Any]:
    """Transform data for Recharts ScatterChart component."""
    x_col = config["x_axis"]
    y_col = config["y_axis"]
    
    chart_data = []
    for row in rows[:200]:  # Limit points for performance
        x_val = row.get(x_col)
        y_val = row.get(y_col)
        
        try:
            x_numeric = float(x_val) if x_val is not None else 0
            y_numeric = float(y_val) if y_val is not None else 0
        except (ValueError, TypeError):
            continue  # Skip non-numeric points
        
        chart_data.append({
            "x": x_numeric,
            "y": y_numeric
        })
    
    logger.debug(f"Transformed scatter chart with {len(chart_data)} points")
    
    return {
        "data": chart_data,
        "x_key": "x",
        "y_key": "y",
        "title": config.get("title", "Scatter Chart"),
        "x_label": x_col,
        "y_label": y_col,
        "fill": "#8884d8"
    }


def _transform_area_chart(rows: List[Dict], columns: List[str], config: Dict) -> Dict[str, Any]:
    """
    Transform data for Recharts AreaChart component.
    Similar to line chart but with fill area.
    """
    # Use line chart transformation as base
    line_data = _transform_line_chart(rows, columns, config)
    
    # Add area-specific properties
    line_data.update({
        "fill": "#8884d8",
        "fillOpacity": 0.3,
        "stroke": "#8884d8"
    })
    
    logger.debug(f"Transformed area chart with {len(line_data.get('data', []))} points")
    
    return line_data


def _transform_heatmap_chart(rows: List[Dict], columns: List[str], config: Dict) -> Dict[str, Any]:
    """
    Transform data for a custom heatmap visualization.
    
    Expected format for heatmap:
    {
        "data": [
            {"x": "Category1", "y": "Group1", "value": 10},
            {"x": "Category2", "y": "Group1", "value": 15}
        ],
        "x_key": "x",
        "y_key": "y",
        "value_key": "value"
    }
    """
    x_col = config["x_axis"]
    y_col = config["y_axis"]
    
    # Find a numeric column for values
    value_col = None
    for col in columns:
        if col not in [x_col, y_col]:
            sample_values = [row.get(col) for row in rows[:3]]
            if all(_is_numeric(v) for v in sample_values if v is not None):
                value_col = col
                break
    
    if not value_col:
        raise ValueError("No numeric column found for heatmap values")
    
    chart_data = []
    for row in rows[:100]:  # Limit for performance
        x_val = str(row.get(x_col, "Unknown"))
        y_val = str(row.get(y_col, "Unknown"))
        value = row.get(value_col, 0)
        
        try:
            numeric_value = float(value) if value is not None else 0
        except (ValueError, TypeError):
            numeric_value = 0
        
        chart_data.append({
            "x": x_val,
            "y": y_val,
            "value": numeric_value
        })
    
    logger.debug(f"Transformed heatmap with {len(chart_data)} cells")
    
    return {
        "data": chart_data,
        "x_key": "x",
        "y_key": "y",
        "value_key": "value",
        "title": config.get("title", "Heatmap"),
        "x_label": x_col,
        "y_label": y_col,
        "value_label": value_col
    }


def transform_to_chart_data(
    rows: List[Dict],
    columns: List[str],
    chart_type: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Transform raw query data into Recharts-compatible format.
    """
    transformers = {
        "bar": _transform_bar_chart,
        "line": _transform_line_chart,
        "pie": _transform_pie_chart,
        "scatter": _transform_scatter_chart,
        "area": _transform_area_chart,
        "heatmap": _transform_heatmap_chart
    }
    
    transformer = transformers.get(chart_type)
    if not transformer:
        raise ValueError(f"Unsupported chart type: {chart_type}")
    
    try:
        logger.info(f"Transforming data for {chart_type} chart")
        chart_data = transformer(rows, columns, config)
        
        # Add metadata
        chart_data.update({
            "chart_type": chart_type,
            "data_source": "database_query",
            "generated_at": int(time.time()),
            "total_records": len(rows)
        })
        
        return chart_data
        
    except Exception as e:
        logger.error(f"Failed to transform data for {chart_type}: {e}")
        raise