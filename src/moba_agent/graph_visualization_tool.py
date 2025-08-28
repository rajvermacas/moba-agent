"""
Graph Visualization Tool for Agent Framework

This tool integrates graph visualization into the agent framework,
ensuring unified context management and consistent LLM invocation patterns.
"""

import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, List
# HumanMessage import no longer needed - removed LLM invocation


class GraphVisualizationTool:
    """
    Tool for generating graph visualizations using the agent's LLM.
    Maintains context and updates agent memory.
    """
    
    def __init__(self, agent):
        """
        Initialize the GraphVisualizationTool with agent reference.
        
        Args:
            agent: MCPAgent instance providing LLM and memory access
        """
        self.agent = agent
        self.llm = agent.llm  # Reference, not new instance
        # Memory is managed through agent's thread state, not locally
        self.logger = logging.getLogger(__name__)
        self.config = agent.config if hasattr(agent, 'config') else {}
        
        self.logger.info("GraphVisualizationTool initialized with agent reference")
    
    def add_to_memory(self, entry: Dict[str, Any]) -> None:
        """
        Add an entry to the agent's memory.
        
        Note: In the current implementation, memory entries are added as metadata
        to the visualization results that are returned to the agent. The agent
        then incorporates these into the thread's message history automatically.
        
        Args:
            entry: Memory entry with role, content, and metadata
        """
        # Memory is handled through the return values and metadata
        # The agent automatically adds tool results to thread state
        self.logger.debug(f"Memory entry prepared: {entry.get('role')}, type: {entry.get('metadata', {}).get('type')}")
    
    async def arun(self, query_results: str, context: List = None, thread_id: str = None, chart_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate graph visualization using provided configuration.
        
        Args:
            query_results: Query results to visualize (string or dict)
            context: Conversation context (list of messages)
            thread_id: Thread ID for accessing conversation history
            chart_config: Chart configuration from agent (optional)
            
        Returns:
            Dict with graph_id, explanation, status, and metadata for memory
        """
        try:
            self.logger.info("Starting graph visualization generation")
            
            # Pre-execution metadata (will be included in return value)
            pre_execution_meta = {
                "tool_invoke": "graph_visualization",
                "timestamp": datetime.now().isoformat(),
                "thread_id": thread_id
            }
            self.logger.debug(f"Starting visualization with metadata: {pre_execution_meta}")
            
            # Import existing functions from graph_visualization module
            from .graph_visualization import (
                analyze_data_characteristics,
                _get_fallback_recommendation,
                transform_to_chart_data,
                validate_graph_data
            )
            
            # Parse query results if string
            if isinstance(query_results, str):
                try:
                    query_data = json.loads(query_results)
                except json.JSONDecodeError:
                    query_data = {"rows": [], "columns": []}
            else:
                query_data = query_results
            
            # Extract data from query results
            rows = query_data.get("rows", [])
            columns = query_data.get("columns", [])
            
            # Analyze data characteristics
            data_analysis = analyze_data_characteristics(rows, columns)
            self.logger.info(f"Data analysis complete: {len(rows)} rows, {len(columns)} columns")
            
            # Use provided chart configuration or generate fallback
            if chart_config:
                # Use the configuration provided by the agent
                self.logger.info(f"Using agent-provided chart configuration: {chart_config}")
                chart_recommendation = {
                    "chart_type": chart_config.get("chart_type", "bar"),
                    "config": {
                        "x_axis": chart_config.get("x_axis"),
                        "y_axis": chart_config.get("y_axis"),
                        "title": chart_config.get("title", "Data Visualization"),
                        "color_field": chart_config.get("color_field")
                    },
                    "reasoning": f"Agent determined {chart_config.get('chart_type', 'bar')} chart is best for this data"
                }
            else:
                # Fallback to heuristics-based recommendation
                self.logger.info("No chart configuration provided, using heuristics")
                chart_recommendation = _get_fallback_recommendation(data_analysis)
                
                if not chart_recommendation:
                    # Last resort: basic bar chart
                    chart_recommendation = {
                        "chart_type": "bar",
                        "config": {
                            "x_axis": columns[0] if columns else "x",
                            "y_axis": columns[1] if len(columns) > 1 else "y",
                            "title": "Data Visualization",
                            "color_field": None
                        },
                        "reasoning": "Default bar chart visualization"
                    }
            
            self.logger.info(f"Chart type determined: {chart_recommendation['chart_type']}")
            
            # Transform data to chart format
            graph_data = transform_to_chart_data(
                rows,
                columns,
                chart_recommendation["chart_type"],
                chart_recommendation["config"]
            )
            
            # Validate graph data
            if not validate_graph_data(graph_data):
                raise ValueError("Generated graph data failed validation")
            
            # Generate graph ID (simplified for now)
            import hashlib
            graph_id = f"graph_{hashlib.md5(json.dumps(graph_data).encode()).hexdigest()[:8]}"
            
            # Post-execution metadata
            explanation = chart_recommendation.get("reasoning", "Graph visualization created")
            visualization_metadata = {
                "type": "visualization",
                "graph_ref": graph_id,
                "chart_type": chart_recommendation["chart_type"],
                "timestamp": datetime.now().isoformat(),
                "thread_id": thread_id,
                "pre_execution": pre_execution_meta
            }
            
            self.logger.info(f"Graph visualization completed successfully: {graph_id}")
            
            return {
                "graph_id": graph_id,
                "graph_data": graph_data,
                "explanation": explanation,
                "chart_type": chart_recommendation["chart_type"],
                "status": "success",
                "metadata": visualization_metadata  # This will be stored in thread state
            }
            
        except Exception as e:
            self.logger.error(f"Visualization failed: {e}", exc_info=True)
            
            # Error metadata
            error_metadata = {
                "type": "viz_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "thread_id": thread_id
            }
            
            return {
                "explanation": "Error occurred while creating graph",
                "error": str(e),
                "status": "error",
                "metadata": error_metadata  # This will be stored in thread state
            }