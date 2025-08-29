"""
Pydantic schemas for structured LLM responses.

This module defines the structured output schemas for the LLM to eliminate
text-based parsing and provide type-safe responses.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class ChartType(str, Enum):
    """Supported chart types for visualization."""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    AREA = "area"
    HISTOGRAM = "histogram"
    HEATMAP = "heatmap"
    BOX = "box"
    SUNBURST = "sunburst"
    TREEMAP = "treemap"
    FUNNEL = "funnel"
    WATERFALL = "waterfall"
    RADAR = "radar"
    GAUGE = "gauge"
    TABLE = "table"


class ChartConfig(BaseModel):
    """Configuration for chart visualization."""
    chart_type: ChartType = Field(
        description="Type of chart to generate based on data characteristics"
    )
    title: Optional[str] = Field(
        default=None,
        description="Chart title describing what the visualization represents"
    )
    x_axis: Optional[str] = Field(
        default=None,
        description="Column name to use for X-axis"
    )
    y_axis: Optional[str] = Field(
        default=None,
        description="Column name to use for Y-axis"
    )
    group_by: Optional[str] = Field(
        default=None,
        description="Column to group data by for multi-series charts"
    )
    aggregation: Optional[str] = Field(
        default=None,
        description="Aggregation method (sum, avg, count, etc.)"
    )
    filters: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional filters or parameters for chart generation"
    )


class QueryMetadata(BaseModel):
    """Metadata about database query execution."""
    query_executed: bool = Field(
        default=False,
        description="Whether a database query was executed"
    )
    query_type: Optional[str] = Field(
        default=None,
        description="Type of query (SELECT, INSERT, UPDATE, etc.)"
    )
    rows_affected: Optional[int] = Field(
        default=None,
        description="Number of rows returned or affected by the query"
    )
    columns: Optional[List[str]] = Field(
        default=None,
        description="List of column names in the result set"
    )


class StructuredAgentResponse(BaseModel):
    """
    Structured response from the LLM agent.
    
    This schema ensures the LLM provides all necessary information
    in a structured format, eliminating the need for text parsing.
    """
    content: str = Field(
        description="The main response text to show to the user"
    )
    should_visualize: bool = Field(
        default=False,
        description="Whether the query results should be visualized"
    )
    chart_config: Optional[ChartConfig] = Field(
        default=None,
        description="Chart configuration if visualization is needed"
    )
    query_metadata: Optional[QueryMetadata] = Field(
        default=None,
        description="Metadata about any database query executed"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Agent's reasoning for visualization decision and chart selection"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "content": "Here are the top 10 products by revenue.",
                "should_visualize": True,
                "chart_config": {
                    "chart_type": "bar",
                    "title": "Top 10 Products by Revenue",
                    "x_axis": "product_name",
                    "y_axis": "total_revenue",
                    "aggregation": "sum"
                },
                "query_metadata": {
                    "query_executed": True,
                    "query_type": "SELECT",
                    "rows_affected": 10,
                    "columns": ["product_name", "total_revenue"]
                },
                "reasoning": "Bar chart is ideal for comparing discrete categories"
            }
        }
    }