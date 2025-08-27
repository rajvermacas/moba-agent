"""
Utility Functions for Graph Visualization

This module contains helper functions for data type detection
and analysis used across the graph visualization system.
"""

import re
import logging
from datetime import datetime
from typing import Any, Optional, List, Dict


logger = logging.getLogger(__name__)


def _is_numeric(value: Any) -> bool:
    """Check if a value is numeric."""
    if value is None:
        return False
    try:
        float(str(value))
        return True
    except (ValueError, TypeError):
        return False


def _is_date_like(value: Any) -> bool:
    """Check if a value appears to be date/time related."""
    if value is None:
        return False
    
    value_str = str(value).lower()
    
    # Common date patterns
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
        r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, value_str):
            return True
    
    # Check for timestamp
    if _is_numeric(value):
        num_val = float(value)
        # Unix timestamp range (year 2000 to 2050)
        if 946684800 <= num_val <= 2524608000:
            return True
    
    # Check for date keywords - be more restrictive to avoid false positives
    date_keywords = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    month_pattern = r'\b(' + '|'.join(date_keywords) + r')\b'
    
    if re.search(month_pattern, value_str):
        return True
    
    # Check for year pattern (but not just any 4-digit number)
    if re.search(r'\b20[0-9]{2}\b', value_str) or re.search(r'\b19[0-9]{2}\b', value_str):
        # Additional check - should have other date components
        if any(kw in value_str for kw in ['-', '/', 'jan', 'feb', 'mar']):
            return True
    
    return False


def _parse_date_value(value: Any) -> Optional[datetime]:
    """Attempt to parse a date value."""
    if value is None:
        return None
    
    try:
        from dateutil import parser
        return parser.parse(str(value))
    except (ImportError, ValueError, TypeError, AttributeError):
        # Try unix timestamp
        if _is_numeric(value):
            try:
                return datetime.fromtimestamp(float(value))
            except (ValueError, OSError):
                pass
    
    return None


def is_suitable_for_visualization(rows: List[Dict], columns: List[str]) -> bool:
    """
    Check if query result is suitable for visualization.
    
    Criteria:
    - Must have at least 2 rows of data
    - Must have at least 2 columns
    - At least one column must be numeric or temporal
    - Row count should be reasonable (2-1000 rows)
    """
    if not rows or len(rows) < 2:
        logger.debug("Insufficient data rows for visualization")
        return False
    
    if not columns or len(columns) < 2:
        logger.debug("Insufficient columns for visualization")
        return False
    
    if len(rows) > 1000:
        logger.debug("Too many rows for effective visualization")
        return False
    
    # Check for at least one numeric or date column
    has_numeric_or_date = False
    for row in rows[:3]:  # Check first 3 rows
        for col in columns:
            value = row.get(col)
            if _is_numeric(value) or _is_date_like(value):
                has_numeric_or_date = True
                break
        if has_numeric_or_date:
            break
    
    if not has_numeric_or_date:
        logger.debug("No numeric or date columns found")
        return False
    
    logger.info(f"Data suitable for visualization: {len(rows)} rows, {len(columns)} columns")
    return True


def analyze_data_characteristics(rows: List[Dict], columns: List[str]) -> Dict[str, Any]:
    """
    Analyze the characteristics of the data to inform chart selection.
    
    Returns:
        Dict containing:
        - numeric_columns: List of numeric column names
        - categorical_columns: List of categorical column names
        - date_columns: List of date/time column names
        - row_count: Number of data rows
        - value_ranges: Min/max for numeric columns
        - unique_counts: Count of unique values per column
    """
    analysis = {
        "numeric_columns": [],
        "categorical_columns": [],
        "date_columns": [],
        "row_count": len(rows),
        "value_ranges": {},
        "unique_counts": {}
    }
    
    for col in columns:
        values = [row.get(col) for row in rows if row.get(col) is not None]
        if not values:
            continue
            
        analysis["unique_counts"][col] = len(set(str(v) for v in values))
        
        # Classify column type
        if all(_is_numeric(v) for v in values):
            analysis["numeric_columns"].append(col)
            numeric_vals = [float(v) for v in values]
            analysis["value_ranges"][col] = {
                "min": min(numeric_vals),
                "max": max(numeric_vals),
                "mean": sum(numeric_vals) / len(numeric_vals)
            }
        elif any(_is_date_like(v) for v in values):
            analysis["date_columns"].append(col)
        else:
            analysis["categorical_columns"].append(col)
    
    logger.debug(f"Data analysis: {analysis}")
    return analysis