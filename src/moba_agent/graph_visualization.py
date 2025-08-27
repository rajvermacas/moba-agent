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

def _build_chart_analysis_prompt(data_analysis: Dict, original_query: str, sample_rows: List[Dict]) -> str:
    """
    Build prompt for LLM to analyze data and recommend chart type.
    Includes actual data samples for better analysis.
    """
    
    # Format sample data for display
    sample_data_str = "\n".join([
        json.dumps(row, indent=2) for row in sample_rows[:5]
    ])
    
    prompt = f"""
Analyze this database query result to recommend the best chart visualization:

ORIGINAL QUERY: {original_query}

DATA CHARACTERISTICS:
- Total rows: {data_analysis['row_count']}
- Numeric columns: {data_analysis['numeric_columns']}
- Categorical columns: {data_analysis['categorical_columns']}
- Date columns: {data_analysis['date_columns']}
- Unique value counts: {data_analysis['unique_counts']}

VALUE RANGES:
{json.dumps(data_analysis.get('value_ranges', {}), indent=2)}

SAMPLE DATA (first 5 rows):
{sample_data_str}

TASK: Recommend the single best chart type and configuration based on the actual data structure and values shown above.

AVAILABLE CHART TYPES:
- bar: Compare categorical data values
- line: Show trends over time or ordered categories
- pie: Show parts of a whole (max 8 categories)
- scatter: Show relationship between two numeric variables
- area: Show cumulative values or trends with filled area
- heatmap: Show correlation or intensity across two dimensions

RESPONSE FORMAT (JSON only):
{{
  "chart_type": "bar|line|pie|scatter|area|heatmap",
  "reasoning": "Why this chart type is optimal for this data",
  "config": {{
    "x_axis": "column_name",
    "y_axis": "column_name",
    "title": "Descriptive chart title",
    "color_field": "column_name_or_null"
  }}
}}

Requirements:
- Choose the most informative visualization for the data
- Ensure x_axis and y_axis reference actual column names from the sample data
- Create a descriptive title related to the original query
- For pie charts, use categorical column with <8 unique values
- For time series, prefer line or area charts
- Consider the business context from the original query and actual data values
"""
    return prompt.strip()


async def _get_chart_recommendation(prompt: str, llm) -> Dict[str, Any]:
    """
    Get chart recommendation from LLM.
    
    Uses the provided Gemini LLM instance.
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Use provided LLM instance for consistency
        if llm:
            llm_response = await llm.ainvoke([HumanMessage(content=prompt)])
            response_text = llm_response.content
        else:
            raise Exception("LLM not available for chart analysis")
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in LLM response")
        
        recommendation = json.loads(json_match.group())
        
        # Validate recommendation structure
        required_fields = ["chart_type", "reasoning", "config"]
        if not all(field in recommendation for field in required_fields):
            raise ValueError("Incomplete recommendation from LLM")
        
        config = recommendation["config"]
        if not all(field in config for field in ["x_axis", "y_axis", "title"]):
            raise ValueError("Incomplete config in recommendation")
        
        logger.info(f"LLM recommended {recommendation['chart_type']} chart: {recommendation['reasoning']}")
        return recommendation
        
    except Exception as e:
        logger.error(f"Failed to get chart recommendation: {e}")
        # Return None to trigger fallback
        return None


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
    llm=None
) -> Optional[Dict[str, Any]]:
    """
    Analyze query result and generate graph data if visualization is beneficial.
    
    Args:
        query_result: Raw query result from execute_query_* tool
        llm: LLM instance for chart type recommendation
        
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
    
    # Step 2: Analyze data characteristics
    data_analysis = analyze_data_characteristics(rows, columns)
    viz_logger.log_data_analysis(data_analysis)
    
    # Step 3: Get chart recommendation
    sample_rows = rows[:5] if len(rows) >= 5 else rows
    chart_prompt = _build_chart_analysis_prompt(
        data_analysis,
        query_result.get("query", ""),
        sample_rows
    )
    
    viz_logger.log_llm_prompt(chart_prompt)
    
    # Get recommendation from LLM or fallback
    chart_recommendation = None
    if llm:
        chart_recommendation = await _get_chart_recommendation(chart_prompt, llm)
    
    if not chart_recommendation:
        viz_logger.log_fallback("LLM recommendation failed or unavailable")
        chart_recommendation = _get_fallback_recommendation(data_analysis)
        
    if not chart_recommendation:
        logger.warning("Could not determine appropriate chart type")
        return None
    
    viz_logger.log_llm_response("", chart_recommendation)
    
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