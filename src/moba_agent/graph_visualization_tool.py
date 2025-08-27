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
from langchain_core.messages import HumanMessage


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
        self.memory = []  # Will be replaced with actual memory implementation
        self.logger = logging.getLogger(__name__)
        self.config = agent.config if hasattr(agent, 'config') else {}
        
        self.logger.info("GraphVisualizationTool initialized with agent reference")
    
    def add_to_memory(self, entry: Dict[str, Any]) -> None:
        """
        Add an entry to the agent's memory.
        
        Args:
            entry: Memory entry with role, content, and metadata
        """
        # For now, append to internal memory list
        # This will be integrated with actual agent memory
        self.memory.append(entry)
        self.logger.debug(f"Added memory entry: {entry.get('role')}, type: {entry.get('metadata', {}).get('type')}")
    
    async def arun(self, query_results: str, context: List = None) -> Dict[str, Any]:
        """
        Generate graph visualization using agent's LLM instance.
        
        Args:
            query_results: Query results to visualize (string or dict)
            context: Conversation context (list of messages)
            
        Returns:
            Dict with graph_id, explanation, and status
        """
        try:
            self.logger.info("Starting graph visualization generation")
            
            # Pre-execution memory marker
            self.add_to_memory({
                "role": "assistant",
                "content": "Generating visualization...",
                "metadata": {
                    "tool_invoke": "graph_visualization",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # Import existing functions from graph_visualization module
            from .graph_visualization import (
                _build_chart_analysis_prompt,
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
            
            # Build prompt for chart recommendation
            sample_rows = rows[:5] if len(rows) >= 5 else rows
            prompt = _build_chart_analysis_prompt(
                data_analysis,
                query_data.get("query", ""),
                sample_rows
            )
            
            self.logger.debug(f"Generated chart analysis prompt (length: {len(prompt)})")
            
            # Use agent's LLM (replaces direct invocation from lines 228-229)
            self.logger.info("Invoking agent's LLM for chart recommendation")
            llm_response = await self.llm.ainvoke(
                [HumanMessage(content=prompt)],
                config=self.config if isinstance(self.config, dict) else {}
            )
            
            response_text = llm_response.content
            self.logger.debug(f"LLM response received (length: {len(response_text)})")
            
            # Parse LLM response to get chart recommendation
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                self.logger.warning("No JSON found in LLM response, using fallback")
                chart_recommendation = _get_fallback_recommendation(data_analysis)
            else:
                try:
                    chart_recommendation = json.loads(json_match.group())
                    self.logger.info(f"LLM recommended {chart_recommendation['chart_type']} chart")
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse LLM JSON: {e}, using fallback")
                    chart_recommendation = _get_fallback_recommendation(data_analysis)
            
            if not chart_recommendation:
                raise ValueError("Could not determine appropriate chart type")
            
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
            
            # Post-execution memory update
            explanation = chart_recommendation.get("reasoning", "Graph visualization created")
            self.add_to_memory({
                "role": "tool",
                "content": explanation,
                "metadata": {
                    "type": "visualization",
                    "graph_ref": graph_id,
                    "chart_type": chart_recommendation["chart_type"],
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            self.logger.info(f"Graph visualization completed successfully: {graph_id}")
            
            return {
                "graph_id": graph_id,
                "graph_data": graph_data,
                "explanation": explanation,
                "chart_type": chart_recommendation["chart_type"],
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Visualization failed: {e}", exc_info=True)
            
            # Add error to memory
            self.add_to_memory({
                "role": "tool",
                "content": "Error occurred while creating graph",
                "metadata": {
                    "type": "viz_error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            return {
                "explanation": "Error occurred while creating graph",
                "error": str(e),
                "status": "error"
            }