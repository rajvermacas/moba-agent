"""
Validation Functions for Graph Visualization

This module contains functions to validate graph data structures
for different chart types.
"""

import logging
from typing import Dict, Any, List


logger = logging.getLogger(__name__)


def validate_graph_data(graph_data: Dict[str, Any]) -> bool:
    """
    Validate generated graph data structure.
    
    Ensures the graph data is properly formatted for frontend consumption.
    """
    try:
        # Check required fields
        required_fields = ["data", "chart_type", "title"]
        for field in required_fields:
            if field not in graph_data:
                logger.error(f"Missing required graph field: {field}")
                return False
        
        # Validate data array
        data = graph_data["data"]
        if not isinstance(data, list) or len(data) == 0:
            logger.error("Graph data must be a non-empty list")
            return False
        
        # Check data structure based on chart type
        chart_type = graph_data["chart_type"]
        return _validate_chart_specific_data(data, chart_type)
        
    except Exception as e:
        logger.error(f"Graph data validation error: {e}")
        return False


def _validate_chart_specific_data(data: List[Dict], chart_type: str) -> bool:
    """Validate data structure for specific chart types."""
    validators = {
        "bar": _validate_bar_data,
        "line": _validate_line_data,
        "pie": _validate_pie_data,
        "scatter": _validate_scatter_data,
        "area": _validate_area_data,
        "heatmap": _validate_heatmap_data
    }
    
    validator = validators.get(chart_type)
    if not validator:
        logger.error(f"No validator for chart type: {chart_type}")
        return False
    
    return validator(data)


def _validate_bar_data(data: List[Dict]) -> bool:
    """Validate bar chart data format."""
    required_keys = {"name", "value"}
    for item in data:
        if not isinstance(item, dict):
            return False
        if not required_keys.issubset(item.keys()):
            return False
        if not isinstance(item.get("value"), (int, float)):
            return False
    
    return True


def _validate_line_data(data: List[Dict]) -> bool:
    """Validate line chart data format."""
    required_keys = {"x", "y"}
    for item in data:
        if not isinstance(item, dict):
            return False
        if not required_keys.issubset(item.keys()):
            return False
        if not isinstance(item.get("y"), (int, float)):
            return False
    
    return True


def _validate_pie_data(data: List[Dict]) -> bool:
    """Validate pie chart data format."""
    if len(data) > 8:
        logger.warning(f"Pie chart has {len(data)} slices, may be too many for readability")
    
    required_keys = {"name", "value"}
    total_value = 0
    
    for item in data:
        if not isinstance(item, dict):
            return False
        if not required_keys.issubset(item.keys()):
            return False
        
        value = item.get("value")
        if not isinstance(value, (int, float)) or value < 0:
            return False
        
        total_value += value
    
    if total_value <= 0:
        logger.error("Pie chart total value must be positive")
        return False
    
    return True


def _validate_scatter_data(data: List[Dict]) -> bool:
    """Validate scatter chart data format."""
    required_keys = {"x", "y"}
    for item in data:
        if not isinstance(item, dict):
            return False
        if not required_keys.issubset(item.keys()):
            return False
        if not isinstance(item.get("x"), (int, float)):
            return False
        if not isinstance(item.get("y"), (int, float)):
            return False
    
    return True


def _validate_area_data(data: List[Dict]) -> bool:
    """Validate area chart data format."""
    # Same as line chart
    return _validate_line_data(data)


def _validate_heatmap_data(data: List[Dict]) -> bool:
    """Validate heatmap data format."""
    required_keys = {"x", "y", "value"}
    for item in data:
        if not isinstance(item, dict):
            return False
        if not required_keys.issubset(item.keys()):
            return False
        if not isinstance(item.get("value"), (int, float)):
            return False
    
    return True