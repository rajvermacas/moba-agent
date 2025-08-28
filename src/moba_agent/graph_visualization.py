"""
Graph Visualization Module for Query Results

This module orchestrates the graph visualization pipeline for database query results,
using intelligent LLM-based analysis to select appropriate chart types.
"""

import logging
import re
import json
import time
from functools import wraps
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage

from .graph_utils import (
    is_suitable_for_visualization,
    analyze_data_characteristics
)
from .chart_transformers import transform_to_chart_data
from .graph_validators import validate_graph_data


# ============================================================================
# Logging Infrastructure
# ============================================================================

class GraphVisualizationLogger:
    """Specialized logger for graph visualization operations."""
    
    def __init__(self):
        self.logger = logging.getLogger("moba_agent.graph_viz")
        
    def log_analysis_start(self, query_result: Dict) -> None:
        """Log start of graph analysis."""
        rows_count = len(query_result.get("rows", []))
        columns_count = len(query_result.get("columns", []))
        
        self.logger.info(
            f"Starting graph analysis for query result: "
            f"{rows_count} rows, {columns_count} columns"
        )
        
    def log_suitability_check(self, suitable: bool, reason: str = None) -> None:
        """Log data suitability determination."""
        if suitable:
            self.logger.info("Data determined suitable for visualization")
        else:
            self.logger.info(f"Data not suitable for visualization: {reason}")
            
    def log_data_analysis(self, analysis: Dict) -> None:
        """Log detailed data characteristics."""
        self.logger.debug(f"Data analysis complete: {json.dumps(analysis, indent=2)}")
        
        # Log key insights
        self.logger.info(
            f"Data characteristics: "
            f"{len(analysis['numeric_columns'])} numeric, "
            f"{len(analysis['categorical_columns'])} categorical, "
            f"{len(analysis['date_columns'])} date columns"
        )
        
    def log_llm_prompt(self, prompt: str) -> None:
        """Log LLM analysis prompt (truncated)."""
        truncated = prompt[:200] + "..." if len(prompt) > 200 else prompt
        self.logger.debug(f"LLM analysis prompt: {truncated}")
        
    def log_llm_response(self, response: str, recommendation: Dict) -> None:
        """Log LLM recommendation."""
        self.logger.info(
            f"LLM recommended {recommendation['chart_type']} chart: "
            f"{recommendation['reasoning'][:100]}..."
        )
        self.logger.debug(f"Full LLM response: {response}")
        
    def log_transformation_start(self, chart_type: str, config: Dict) -> None:
        """Log start of data transformation."""
        self.logger.info(f"Transforming data for {chart_type} chart")
        self.logger.debug(f"Transformation config: {config}")
        
    def log_transformation_complete(self, chart_data: Dict) -> None:
        """Log successful data transformation."""
        data_points = len(chart_data.get("data", []))
        self.logger.info(f"Data transformation complete: {data_points} data points")
        
    def log_validation_result(self, valid: bool, chart_type: str) -> None:
        """Log validation results."""
        if valid:
            self.logger.info(f"Generated {chart_type} chart data passed validation")
        else:
            self.logger.error(f"Generated {chart_type} chart data failed validation")
            
    def log_error(self, operation: str, error: Exception) -> None:
        """Log errors with context."""
        self.logger.error(f"Graph visualization error in {operation}: {str(error)}", exc_info=True)
        
    def log_fallback(self, reason: str) -> None:
        """Log fallback to default behavior."""
        self.logger.warning(f"Using fallback chart recommendation: {reason}")


def log_performance_metrics(func):
    """Decorator to log performance metrics for graph operations."""
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        operation_name = func.__name__
        
        logger = logging.getLogger(__name__)
        logger.debug(f"Starting {operation_name}")
        
        try:
            result = await func(*args, **kwargs)
            
            duration = time.time() - start_time
            logger.info(f"{operation_name} completed in {duration:.3f}s")
            
            # Log additional metrics
            if isinstance(result, dict) and "data" in result:
                data_points = len(result["data"])
                logger.debug(f"{operation_name} processed {data_points} data points")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{operation_name} failed after {duration:.3f}s: {str(e)}")
            raise
    
    return wrapper


def safe_graph_generation(func):
    """Decorator to safely handle graph generation errors."""
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(__name__)
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Graph generation error: {e}", exc_info=True)
            # Always return None for graph failures
            # Don't let graph generation break the main chat flow
            return None
    
    return wrapper


# ============================================================================
# LLM Integration Functions
# ============================================================================



def _get_fallback_recommendation(data_analysis: Dict) -> Dict[str, Any]:
    """
    Provide a fallback chart recommendation based on simple heuristics.
    """
    logger = logging.getLogger(__name__)
    logger.info("Using fallback chart recommendation")
    
    # Simple heuristics for chart selection
    if data_analysis["date_columns"] and data_analysis["numeric_columns"]:
        # Time series data - use line chart
        return {
            "chart_type": "line",
            "reasoning": "Time series data detected - line chart is suitable for showing trends over time",
            "config": {
                "x_axis": data_analysis["date_columns"][0],
                "y_axis": data_analysis["numeric_columns"][0],
                "title": "Time Series Data",
                "color_field": None
            }
        }
    elif data_analysis["categorical_columns"] and data_analysis["numeric_columns"]:
        cat_col = data_analysis["categorical_columns"][0]
        unique_count = data_analysis["unique_counts"].get(cat_col, 100)
        
        if unique_count <= 8:
            # Few categories - use pie chart
            return {
                "chart_type": "pie",
                "reasoning": f"Categorical data with {unique_count} categories - pie chart shows distribution",
                "config": {
                    "x_axis": cat_col,
                    "y_axis": data_analysis["numeric_columns"][0],
                    "title": "Category Distribution",
                    "color_field": None
                }
            }
        else:
            # Many categories - use bar chart
            return {
                "chart_type": "bar",
                "reasoning": f"Categorical comparison data - bar chart is suitable",
                "config": {
                    "x_axis": cat_col,
                    "y_axis": data_analysis["numeric_columns"][0],
                    "title": "Category Comparison",
                    "color_field": None
                }
            }
    elif len(data_analysis["numeric_columns"]) >= 2:
        # Multiple numeric columns - use scatter plot
        return {
            "chart_type": "scatter",
            "reasoning": "Multiple numeric columns - scatter plot shows relationships",
            "config": {
                "x_axis": data_analysis["numeric_columns"][0],
                "y_axis": data_analysis["numeric_columns"][1],
                "title": "Numeric Correlation",
                "color_field": None
            }
        }
    else:
        # Default to bar chart
        all_cols = data_analysis["categorical_columns"] + data_analysis["date_columns"] + data_analysis["numeric_columns"]
        if len(all_cols) >= 2:
            return {
                "chart_type": "bar",
                "reasoning": "Default visualization for available data",
                "config": {
                    "x_axis": all_cols[0],
                    "y_axis": all_cols[1],
                    "title": "Data Visualization",
                    "color_field": None
                }
            }
        else:
            return None


# ============================================================================
# Main Graph Generation Function
# ============================================================================

@safe_graph_generation
@log_performance_metrics
async def analyze_and_generate_graph(
    query_result: Dict[str, Any],
    chart_config: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """
    Analyze query result and generate graph data with structured configuration.
    
    This simplified version uses the structured chart configuration directly
    from the agent's structured response, eliminating the need for LLM prompts
    and text parsing.
    
    Args:
        query_result: Raw query result from execute_query_* tool
        chart_config: Structured chart configuration from agent's response
        
    Returns:
        Graph data dict or None if not suitable for visualization
    """
    viz_logger = GraphVisualizationLogger()
    logger = logging.getLogger(__name__)
    
    viz_logger.log_analysis_start(query_result)
    
    # Step 1: Extract and validate data
    rows = query_result.get("rows", [])
    columns = query_result.get("columns", [])
    
    if not is_suitable_for_visualization(rows, columns):
        viz_logger.log_suitability_check(False, "Data validation failed")
        return None
    
    viz_logger.log_suitability_check(True)
    
    # Step 2: Analyze data characteristics (for fallback if needed)
    data_analysis = analyze_data_characteristics(rows, columns)
    viz_logger.log_data_analysis(data_analysis)
    
    # Step 3: Use provided config or generate fallback
    if chart_config and "chart_type" in chart_config:
        logger.info(f"Using structured chart config: {chart_config.get('chart_type')}")
        chart_recommendation = {
            "chart_type": chart_config.get("chart_type"),
            "config": {
                "x_axis": chart_config.get("x_axis"),
                "y_axis": chart_config.get("y_axis"),
                "title": chart_config.get("title", "Data Visualization"),
                "color_field": chart_config.get("group_by") or chart_config.get("filters", {}).get("color_field")
            }
        }
    else:
        # Fallback to heuristic-based recommendation
        logger.info("No structured config provided, using fallback recommendation")
        chart_recommendation = _get_fallback_recommendation(data_analysis)
    
    # Step 4: Transform data to chart format
    viz_logger.log_transformation_start(
        chart_recommendation["chart_type"],
        chart_recommendation["config"]
    )
    
    try:
        graph_data = transform_to_chart_data(
            rows,
            columns,
            chart_recommendation["chart_type"],
            chart_recommendation["config"]
        )
        
        viz_logger.log_transformation_complete(graph_data)
        
        # Step 5: Validate and return
        if validate_graph_data(graph_data):
            viz_logger.log_validation_result(True, chart_recommendation["chart_type"])
            return graph_data
        else:
            viz_logger.log_validation_result(False, chart_recommendation["chart_type"])
            return None
            
    except Exception as e:
        viz_logger.log_error("transform_to_chart_data", e)
        return None