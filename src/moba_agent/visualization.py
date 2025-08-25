"""
Data Visualization Analyzer for QueryResult structures

This module analyzes database query results and generates visualization specifications
for optimal chart rendering.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import re
from datetime import datetime
import json


class ColumnType(Enum):
    """Enumeration of detected column data types"""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    TEXT = "text"


class DataVisualizationAnalyzer:
    """
    Analyzes query results and recommends appropriate visualizations
    """
    
    def __init__(self):
        """Initialize the visualization analyzer"""
        self.logger = logging.getLogger(__name__)
        
        # Supported chart types
        self.supported_chart_types = [
            "bar", "line", "pie", "scatter", "area", 
            "stacked-bar", "grouped-bar", "heatmap", "table"
        ]
        
        # Patterns for type detection
        self.numeric_pattern = re.compile(r'^-?\d+(\.\d+)?$')
        self.datetime_patterns = [
            re.compile(r'^\d{4}-\d{2}-\d{2}'),  # ISO date
            re.compile(r'^\d{2}/\d{2}/\d{4}'),  # US date
            re.compile(r'^\d{2}-\d{2}-\d{4}'),  # EU date
        ]
        self.boolean_values = {
            'true', 'false', 'yes', 'no', '1', '0', 
            't', 'f', 'y', 'n', 'on', 'off'
        }
        
        self.logger.info("DataVisualizationAnalyzer initialized")
    
    def analyze_query_result(self, query_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a query result and generate visualization specifications
        
        Args:
            query_result: Dict with columns, rows, row_count, and optional query
            
        Returns:
            VisualizationSpec dictionary with chart recommendations
        """
        try:
            self.logger.info(f"Analyzing query result with {query_result.get('row_count', 0)} rows")
            
            # Validate required fields
            if not query_result or 'columns' not in query_result or 'rows' not in query_result:
                self.logger.warning("Invalid query result structure")
                return self._default_visualization_spec()
            
            columns = query_result['columns']
            rows = query_result['rows']
            row_count = query_result.get('row_count', len(rows))
            
            # Detect column types
            column_types = self.detect_column_types(columns, rows)
            self.logger.debug(f"Detected column types: {column_types}")
            
            # Recommend chart type
            recommended_chart = self.recommend_chart_type(column_types, row_count)
            self.logger.info(f"Recommended chart type: {recommended_chart}")
            
            # Get alternative chart types
            alternatives = self.get_alternative_charts(column_types, row_count, recommended_chart)
            
            # Generate chart configuration
            chart_config = self.generate_chart_config(recommended_chart, query_result, column_types)
            
            # Create visualization spec
            visualization_spec = {
                "chart_type": recommended_chart,
                "recommended": True,
                "alternatives": alternatives,
                "column_types": column_types,
                "config": chart_config,
                "data": query_result,  # Include original data
                "metadata": {
                    "row_count": row_count,
                    "column_count": len(columns),
                    "query": query_result.get('query', '')
                }
            }
            
            return visualization_spec
            
        except Exception as e:
            self.logger.error(f"Error analyzing query result: {e}", exc_info=True)
            return self._default_visualization_spec()
    
    def detect_column_types(self, columns: List[str], rows: List[Dict]) -> Dict[str, str]:
        """
        Detect the data type of each column
        
        Args:
            columns: List of column names
            rows: List of row dictionaries
            
        Returns:
            Dictionary mapping column names to detected types
        """
        column_types = {}
        
        for column in columns:
            # Sample values from the column (up to 100 rows)
            sample_values = []
            for i, row in enumerate(rows[:100]):
                if column in row and row[column] is not None:
                    sample_values.append(str(row[column]))
            
            # Detect type based on sample values
            detected_type = self._detect_single_column_type(sample_values)
            column_types[column] = detected_type
            
            self.logger.debug(f"Column '{column}' detected as {detected_type}")
        
        return column_types
    
    def _detect_single_column_type(self, values: List[str]) -> str:
        """
        Detect the type of a single column based on sample values
        
        Args:
            values: List of sample values as strings
            
        Returns:
            Detected column type
        """
        if not values:
            return ColumnType.TEXT.value
        
        # Check for numeric first (strict check)
        if all(self.numeric_pattern.match(v) for v in values):
            return ColumnType.NUMERIC.value
        
        # Check for datetime
        for pattern in self.datetime_patterns:
            if all(pattern.match(v) for v in values):
                return ColumnType.DATETIME.value
        
        # Check for boolean
        if all(v.lower() in self.boolean_values for v in values):
            return ColumnType.BOOLEAN.value
        
        # Check for categorical (limited unique values)
        unique_values = set(values)
        # More lenient check for categorical - if we have few unique values relative to total
        # OR if it looks like category names (short strings)
        if (len(unique_values) <= 20 and len(unique_values) <= len(values) * 0.7) or \
           (len(unique_values) <= 10 and all(len(v) <= 50 for v in values)):
            return ColumnType.CATEGORICAL.value
        
        # Default to text
        return ColumnType.TEXT.value
    
    def recommend_chart_type(self, column_types: Dict[str, str], row_count: int) -> str:
        """
        Recommend the best chart type based on column types and data characteristics
        
        Args:
            column_types: Dictionary of column names to types
            row_count: Number of rows in the result
            
        Returns:
            Recommended chart type string
        """
        # Count column types
        type_counts = {
            ColumnType.NUMERIC.value: 0,
            ColumnType.CATEGORICAL.value: 0,
            ColumnType.DATETIME.value: 0,
            ColumnType.BOOLEAN.value: 0,
            ColumnType.TEXT.value: 0
        }
        
        for col_type in column_types.values():
            type_counts[col_type] += 1
        
        numeric_count = type_counts[ColumnType.NUMERIC.value]
        categorical_count = type_counts[ColumnType.CATEGORICAL.value]
        datetime_count = type_counts[ColumnType.DATETIME.value]
        boolean_count = type_counts[ColumnType.BOOLEAN.value]
        
        # Time series detection
        if datetime_count >= 1 and numeric_count >= 1:
            return "line"
        
        # Bar chart for categorical + numeric
        if categorical_count == 1 and numeric_count >= 1 and row_count <= 50:
            if numeric_count > 1:
                return "grouped-bar"
            return "bar"
        
        # Pie chart for small categorical datasets
        if categorical_count == 1 and numeric_count == 1 and row_count <= 10:
            return "pie"
        
        # Scatter plot for two numeric columns
        if numeric_count >= 2 and row_count <= 1000:
            return "scatter"
        
        # Heatmap for two categorical + one numeric
        if categorical_count >= 2 and numeric_count >= 1 and row_count <= 100:
            return "heatmap"
        
        # Area chart for time series with multiple metrics
        if datetime_count >= 1 and numeric_count > 1:
            return "area"
        
        # Stacked bar for categorical with multiple numeric
        if categorical_count >= 1 and numeric_count > 1 and row_count <= 30:
            return "stacked-bar"
        
        # Default to table for complex or large datasets
        return "table"
    
    def get_alternative_charts(self, column_types: Dict[str, str], row_count: int, 
                              recommended: str) -> List[str]:
        """
        Get alternative chart types that could work with the data
        
        Args:
            column_types: Dictionary of column names to types
            row_count: Number of rows
            recommended: Already recommended chart type
            
        Returns:
            List of alternative chart types
        """
        alternatives = []
        
        # Count column types
        numeric_cols = [col for col, t in column_types.items() if t == ColumnType.NUMERIC.value]
        categorical_cols = [col for col, t in column_types.items() if t == ColumnType.CATEGORICAL.value]
        datetime_cols = [col for col, t in column_types.items() if t == ColumnType.DATETIME.value]
        
        # Always include table as an option
        if recommended != "table":
            alternatives.append("table")
        
        # Bar chart alternatives
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            if recommended != "bar":
                alternatives.append("bar")
            if len(numeric_cols) > 1 and recommended != "grouped-bar":
                alternatives.append("grouped-bar")
            if len(numeric_cols) > 1 and recommended != "stacked-bar":
                alternatives.append("stacked-bar")
        
        # Line chart alternatives
        if (len(datetime_cols) >= 1 or len(numeric_cols) >= 1) and recommended != "line":
            alternatives.append("line")
        
        # Pie chart alternative
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1 and row_count <= 15:
            if recommended != "pie":
                alternatives.append("pie")
        
        # Scatter plot alternative
        if len(numeric_cols) >= 2 and recommended != "scatter":
            alternatives.append("scatter")
        
        # Area chart alternative
        if len(datetime_cols) >= 1 and len(numeric_cols) >= 1 and recommended != "area":
            alternatives.append("area")
        
        return alternatives[:4]  # Limit to 4 alternatives
    
    def generate_chart_config(self, chart_type: str, query_result: Dict[str, Any], 
                            column_types: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate chart configuration based on type and data
        
        Args:
            chart_type: Type of chart to configure
            query_result: Original query result
            column_types: Detected column types
            
        Returns:
            Chart configuration dictionary
        """
        config = {
            "type": chart_type,
            "responsive": True,
            "maintainAspectRatio": False
        }
        
        # Extract columns by type
        numeric_cols = [col for col, t in column_types.items() if t == ColumnType.NUMERIC.value]
        categorical_cols = [col for col, t in column_types.items() if t == ColumnType.CATEGORICAL.value]
        datetime_cols = [col for col, t in column_types.items() if t == ColumnType.DATETIME.value]
        
        # Configure based on chart type
        if chart_type == "line":
            config["xAxis"] = {
                "field": datetime_cols[0] if datetime_cols else numeric_cols[0] if numeric_cols else query_result['columns'][0],
                "type": "category" if not datetime_cols else "time"
            }
            config["yAxis"] = {
                "fields": numeric_cols[:3] if numeric_cols else [query_result['columns'][1]],
                "type": "value"
            }
            
        elif chart_type in ["bar", "grouped-bar", "stacked-bar"]:
            config["xAxis"] = {
                "field": categorical_cols[0] if categorical_cols else query_result['columns'][0],
                "type": "category"
            }
            config["yAxis"] = {
                "fields": numeric_cols[:3] if numeric_cols else [query_result['columns'][1]],
                "type": "value"
            }
            if chart_type == "stacked-bar":
                config["stack"] = True
            elif chart_type == "grouped-bar":
                config["grouped"] = True
                
        elif chart_type == "pie":
            config["labels"] = {
                "field": categorical_cols[0] if categorical_cols else query_result['columns'][0]
            }
            config["values"] = {
                "field": numeric_cols[0] if numeric_cols else query_result['columns'][1]
            }
            
        elif chart_type == "scatter":
            config["xAxis"] = {
                "field": numeric_cols[0] if len(numeric_cols) > 0 else query_result['columns'][0],
                "type": "value"
            }
            config["yAxis"] = {
                "field": numeric_cols[1] if len(numeric_cols) > 1 else query_result['columns'][1],
                "type": "value"
            }
            
        elif chart_type == "area":
            config["xAxis"] = {
                "field": datetime_cols[0] if datetime_cols else numeric_cols[0] if numeric_cols else query_result['columns'][0],
                "type": "category" if not datetime_cols else "time"
            }
            config["yAxis"] = {
                "fields": numeric_cols[:3] if numeric_cols else [query_result['columns'][1]],
                "type": "value"
            }
            config["fill"] = True
            
        elif chart_type == "heatmap":
            config["xAxis"] = {
                "field": categorical_cols[0] if len(categorical_cols) > 0 else query_result['columns'][0],
                "type": "category"
            }
            config["yAxis"] = {
                "field": categorical_cols[1] if len(categorical_cols) > 1 else query_result['columns'][1],
                "type": "category"
            }
            config["value"] = {
                "field": numeric_cols[0] if numeric_cols else query_result['columns'][2]
            }
        
        return config
    
    def _default_visualization_spec(self) -> Dict[str, Any]:
        """
        Return a default visualization spec for fallback
        
        Returns:
            Default visualization specification
        """
        return {
            "chart_type": "table",
            "recommended": True,
            "alternatives": [],
            "column_types": {},
            "config": {
                "type": "table",
                "responsive": True
            },
            "data": {},
            "metadata": {
                "row_count": 0,
                "column_count": 0,
                "query": ""
            }
        }