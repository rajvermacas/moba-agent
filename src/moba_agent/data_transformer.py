"""
Data Transformer for Chart Visualizations

This module transforms query result data into formats suitable for different chart types.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
import json


class DataTransformer:
    """
    Transforms query result data for various chart visualizations
    """
    
    def __init__(self):
        """Initialize the data transformer"""
        self.logger = logging.getLogger(__name__)
        
        # Aggregation functions
        self.aggregation_functions = {
            'sum': lambda values: sum(float(v) for v in values if v is not None),
            'avg': lambda values: sum(float(v) for v in values if v is not None) / len([v for v in values if v is not None]),
            'count': lambda values: len(values),
            'min': lambda values: min(float(v) for v in values if v is not None),
            'max': lambda values: max(float(v) for v in values if v is not None)
        }
        
        self.logger.info("DataTransformer initialized")
    
    def transform_for_chart(self, query_result: Dict[str, Any], chart_type: str, 
                           config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform query result data based on chart type
        
        Args:
            query_result: Original query result with columns and rows
            chart_type: Type of chart to transform for
            config: Chart configuration with axis mappings
            
        Returns:
            Transformed data suitable for the chart type
        """
        try:
            self.logger.info(f"Transforming data for {chart_type} chart")
            
            if not query_result or 'rows' not in query_result:
                self.logger.warning("No data to transform")
                return {"data": [], "type": chart_type}
            
            # Route to appropriate transformation method
            if chart_type in ["line", "scatter", "area"]:
                return self._format_xy_data(query_result, config)
            elif chart_type in ["bar", "grouped-bar", "stacked-bar"]:
                return self._format_categorical_data(query_result, config, chart_type)
            elif chart_type == "pie":
                return self._format_pie_data(query_result, config)
            elif chart_type == "heatmap":
                return self._format_matrix_data(query_result, config)
            else:
                # Return original data for table or unknown types
                return {
                    "data": query_result['rows'],
                    "columns": query_result['columns'],
                    "type": chart_type
                }
                
        except Exception as e:
            self.logger.error(f"Error transforming data: {e}", exc_info=True)
            return {"data": query_result.get('rows', []), "type": chart_type}
    
    def _format_xy_data(self, query_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format data for XY charts (line, scatter, area)
        
        Args:
            query_result: Original query result
            config: Chart configuration
            
        Returns:
            Formatted XY data
        """
        rows = query_result['rows']
        
        # Extract axis fields from config
        x_field = config.get('xAxis', {}).get('field', query_result['columns'][0])
        y_fields = config.get('yAxis', {}).get('fields', [query_result['columns'][1]])
        
        # Ensure y_fields is a list
        if isinstance(y_fields, str):
            y_fields = [y_fields]
        
        # Create series data for each y field
        series = []
        for y_field in y_fields:
            serie_data = []
            for row in rows:
                x_value = row.get(x_field)
                y_value = row.get(y_field)
                
                # Handle numeric conversion
                try:
                    if y_value is not None:
                        y_value = float(y_value)
                except (ValueError, TypeError):
                    pass
                
                serie_data.append({
                    'x': x_value,
                    'y': y_value,
                    'label': str(x_value)
                })
            
            series.append({
                'name': y_field,
                'data': serie_data
            })
        
        return {
            'series': series,
            'xAxis': x_field,
            'yAxis': y_fields,
            'type': 'xy'
        }
    
    def _format_categorical_data(self, query_result: Dict[str, Any], config: Dict[str, Any], 
                                chart_type: str) -> Dict[str, Any]:
        """
        Format data for categorical charts (bar, grouped-bar, stacked-bar)
        
        Args:
            query_result: Original query result
            config: Chart configuration
            chart_type: Specific bar chart type
            
        Returns:
            Formatted categorical data
        """
        rows = query_result['rows']
        
        # Extract fields from config
        category_field = config.get('xAxis', {}).get('field', query_result['columns'][0])
        value_fields = config.get('yAxis', {}).get('fields', [query_result['columns'][1]])
        
        # Ensure value_fields is a list
        if isinstance(value_fields, str):
            value_fields = [value_fields]
        
        # Group data by category
        grouped_data = defaultdict(lambda: defaultdict(list))
        categories = []
        
        for row in rows:
            category = str(row.get(category_field, 'Unknown'))
            if category not in categories:
                categories.append(category)
            
            for value_field in value_fields:
                value = row.get(value_field)
                try:
                    value = float(value) if value is not None else 0
                except (ValueError, TypeError):
                    value = 0
                grouped_data[category][value_field].append(value)
        
        # Aggregate values
        formatted_data = []
        for category in categories:
            data_point = {'category': category}
            for value_field in value_fields:
                values = grouped_data[category][value_field]
                # Sum values for each category (can be configured for other aggregations)
                data_point[value_field] = sum(values) if values else 0
            formatted_data.append(data_point)
        
        # Format for different bar chart types
        if chart_type == "stacked-bar":
            # Add stack information
            for i, value_field in enumerate(value_fields):
                for data_point in formatted_data:
                    data_point[f'{value_field}_stack'] = 'stack1'
        
        return {
            'data': formatted_data,
            'categories': categories,
            'series': value_fields,
            'type': 'categorical',
            'chartType': chart_type
        }
    
    def _format_pie_data(self, query_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format data for pie charts
        
        Args:
            query_result: Original query result
            config: Chart configuration
            
        Returns:
            Formatted pie chart data
        """
        rows = query_result['rows']
        
        # Extract fields from config
        label_field = config.get('labels', {}).get('field', query_result['columns'][0])
        value_field = config.get('values', {}).get('field', query_result['columns'][1])
        
        # Aggregate values by label
        pie_data = defaultdict(float)
        for row in rows:
            label = str(row.get(label_field, 'Unknown'))
            value = row.get(value_field, 0)
            try:
                value = float(value)
            except (ValueError, TypeError):
                value = 0
            pie_data[label] += value
        
        # Calculate total and percentages
        total = sum(pie_data.values())
        
        # Format as array of slices
        slices = []
        for label, value in pie_data.items():
            percentage = (value / total * 100) if total > 0 else 0
            slices.append({
                'label': label,
                'value': value,
                'percentage': round(percentage, 2)
            })
        
        # Sort by value descending
        slices.sort(key=lambda x: x['value'], reverse=True)
        
        # Limit to top 10 slices, group others
        if len(slices) > 10:
            top_slices = slices[:9]
            others_value = sum(s['value'] for s in slices[9:])
            others_percentage = (others_value / total * 100) if total > 0 else 0
            top_slices.append({
                'label': 'Others',
                'value': others_value,
                'percentage': round(others_percentage, 2)
            })
            slices = top_slices
        
        return {
            'slices': slices,
            'total': total,
            'type': 'pie'
        }
    
    def _format_matrix_data(self, query_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format data for heatmap/matrix visualizations
        
        Args:
            query_result: Original query result
            config: Chart configuration
            
        Returns:
            Formatted matrix data
        """
        rows = query_result['rows']
        
        # Extract fields from config
        x_field = config.get('xAxis', {}).get('field', query_result['columns'][0])
        y_field = config.get('yAxis', {}).get('field', query_result['columns'][1])
        value_field = config.get('value', {}).get('field', query_result['columns'][2] if len(query_result['columns']) > 2 else query_result['columns'][0])
        
        # Create pivot table
        x_labels = []
        y_labels = []
        matrix_data = defaultdict(lambda: defaultdict(float))
        
        for row in rows:
            x_val = str(row.get(x_field, 'Unknown'))
            y_val = str(row.get(y_field, 'Unknown'))
            value = row.get(value_field, 0)
            
            try:
                value = float(value)
            except (ValueError, TypeError):
                value = 0
            
            if x_val not in x_labels:
                x_labels.append(x_val)
            if y_val not in y_labels:
                y_labels.append(y_val)
            
            matrix_data[y_val][x_val] += value
        
        # Convert to 2D array format
        matrix = []
        for y in y_labels:
            row = []
            for x in x_labels:
                row.append(matrix_data[y][x])
            matrix.append(row)
        
        # Find min and max for color scaling
        all_values = [val for row in matrix for val in row]
        min_value = min(all_values) if all_values else 0
        max_value = max(all_values) if all_values else 1
        
        return {
            'xLabels': x_labels,
            'yLabels': y_labels,
            'matrix': matrix,
            'minValue': min_value,
            'maxValue': max_value,
            'type': 'matrix'
        }
    
    def pivot_data(self, rows: List[Dict], row_field: str, column_field: str, 
                   value_field: str, aggregation: str = 'sum') -> Dict[str, Any]:
        """
        Create a pivot table from row data
        
        Args:
            rows: List of data rows
            row_field: Field to use for rows
            column_field: Field to use for columns
            value_field: Field to aggregate
            aggregation: Aggregation function ('sum', 'avg', 'count', 'min', 'max')
            
        Returns:
            Pivot table data
        """
        pivot = defaultdict(lambda: defaultdict(list))
        row_labels = []
        column_labels = []
        
        # Collect values
        for row in rows:
            row_val = str(row.get(row_field, 'Unknown'))
            col_val = str(row.get(column_field, 'Unknown'))
            value = row.get(value_field)
            
            if row_val not in row_labels:
                row_labels.append(row_val)
            if col_val not in column_labels:
                column_labels.append(col_val)
            
            if value is not None:
                pivot[row_val][col_val].append(value)
        
        # Apply aggregation
        agg_func = self.aggregation_functions.get(aggregation, self.aggregation_functions['sum'])
        result = []
        
        for row_label in row_labels:
            row_data = {'_row': row_label}
            for col_label in column_labels:
                values = pivot[row_label][col_label]
                if values:
                    row_data[col_label] = agg_func(values)
                else:
                    row_data[col_label] = None
            result.append(row_data)
        
        return {
            'data': result,
            'rowField': row_field,
            'columnLabels': column_labels,
            'aggregation': aggregation
        }
    
    def aggregate_data(self, rows: List[Dict], group_by: str, metrics: List[Tuple[str, str]]) -> List[Dict]:
        """
        Aggregate data by a grouping field
        
        Args:
            rows: List of data rows
            group_by: Field to group by
            metrics: List of tuples (field, aggregation)
            
        Returns:
            Aggregated data
        """
        grouped = defaultdict(lambda: defaultdict(list))
        
        # Collect values by group
        for row in rows:
            group = str(row.get(group_by, 'Unknown'))
            for field, _ in metrics:
                value = row.get(field)
                if value is not None:
                    grouped[group][field].append(value)
        
        # Apply aggregations
        result = []
        for group, values_dict in grouped.items():
            row_data = {group_by: group}
            for field, agg_type in metrics:
                values = values_dict.get(field, [])
                if values:
                    agg_func = self.aggregation_functions.get(agg_type, self.aggregation_functions['sum'])
                    row_data[f'{field}_{agg_type}'] = agg_func(values)
                else:
                    row_data[f'{field}_{agg_type}'] = None
            result.append(row_data)
        
        return result