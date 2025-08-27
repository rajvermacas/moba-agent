# Graph Visualization Integration with Agent Framework

## Executive Summary

This document outlines the architectural approach for integrating the graph visualization functionality into the main agent framework to ensure unified context management and consistent LLM invocation patterns.

## Problem Statement

Currently, the graph visualization module (`graph_visualization.py`) makes direct LLM calls independent of the main agent framework. This causes:
- Loss of conversation context when LLM calls are made outside the agent
- Inconsistent state management across different parts of the application
- The agent being unaware of visualization-related interactions

## Solution Overview

Consolidate all LLM calls through the agent framework by creating a `GraphVisualizationTool` that:
- Reuses existing graph generation functions
- Leverages the agent's LLM instance
- Maintains full conversation context
- Updates agent memory with visualization events

## Architecture Decisions

### 1. Core Principles

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Invocation Strategy** | Consolidate through agent | Ensures consistent context and state awareness |
| **Message Context** | Inherit full conversation history | Maintains coherent responses |
| **Configuration** | Inherit with override capability | Flexibility while maintaining defaults |
| **Error Handling** | Graceful degradation | Continue conversation even if visualization fails |
| **Tool Pattern** | Custom tool class | Clean separation of concerns |
| **Execution Model** | Sequential | Simpler state management for POC phase |
| **State Persistence** | Within agent's memory | Unified state management |

### 2. Implementation Approach

| Aspect | Decision | Details |
|--------|----------|---------|
| **Tool Trigger** | Deterministic flag-based | LLM sets flag, agent invokes tool manually |
| **Memory Granularity** | Reference + explanation only | Avoid storing raw graph data in memory |
| **Response Streaming** | Not required | Complete response needed before rendering |
| **Caching** | No caching | Fresh generation for each request |
| **Rollback Plan** | None required | POC phase - fail completely if issues arise |

## Technical Architecture

### Component Interaction Flow

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────┐
│     User     │────▶│      Agent      │────▶│  execute_query Tool  │
└──────────────┘     └─────────────────┘     └──────────────────────┘
                              │                         │
                              │                         ▼
                              │               ┌────────────────────────┐
                              │               │ _get_chart_recommendation │
                              │               └────────────────────────┘
                              │                         │
                              │                    [viz_needed flag]
                              │                         │
                              ▼                         ▼
                     ┌─────────────────┐      ┌──────────────────────┐
                     │   Agent Memory  │◀─────│ GraphVisualizationTool │
                     └─────────────────┘      └──────────────────────┘
                              │                         │
                              │                    [Uses Agent's LLM]
                              │                         │
                              ▼                         ▼
                     ┌─────────────────┐      ┌──────────────────────┐
                     │    Response     │      │   Existing Functions  │
                     └─────────────────┘      │ - generate_graph_prompt│
                                              │ - parse_graph_response │
                                              │ - create_graph        │
                                              └──────────────────────┘
```

### Integration Algorithm

```python
INITIALIZATION:
1. Create GraphVisualizationTool class:
   - Store reference to agent's LLM instance
   - Store reference to agent's memory
   - Configure with agent's settings

2. Register tool during agent initialization

RUNTIME FLOW:
1. User message → Agent
2. Agent → execute_query tool (if needed)
3. execute_query → _get_chart_recommendation()
4. IF visualization_needed flag is True:
   a. Add marker to memory: {type: "tool_start", tool: "graph_viz"}
   b. Agent manually invokes GraphVisualizationTool
   c. Tool uses agent's LLM (replaces direct invocation at lines 228-229)
   d. Tool generates graph using existing functions
   e. Update memory with reference + explanation
   f. Return structured response
5. ELSE:
   Continue normal flow
6. ON ERROR:
   - Log detailed error
   - Add error marker to memory
   - Return "Error occurred while creating graph"
   - Continue conversation

7. Agent continues with enriched context
```

## Implementation Details

### 1. GraphVisualizationTool Class

```python
class GraphVisualizationTool:
    """
    Tool for generating graph visualizations using the agent's LLM.
    Maintains context and updates agent memory.
    """
    
    def __init__(self, agent):
        self.agent = agent
        self.llm = agent.llm  # Reference, not new instance
        self.memory = agent.memory
        
    async def arun(self, query_results: str, context: List) -> Dict:
        try:
            # Pre-execution memory marker
            self.memory.add_message({
                "role": "assistant",
                "content": "Generating visualization...",
                "metadata": {"tool_invoke": "graph_visualization"}
            })
            
            # Reuse existing function
            prompt = generate_graph_prompt(query_results)
            
            # Use agent's LLM (replaces lines 228-229)
            llm_response = await self.llm.ainvoke(
                [HumanMessage(content=prompt)],
                config=self.agent.config
            )
            
            # Parse and create using existing functions
            graph_data = parse_graph_response(llm_response.content)
            graph_id = create_graph(graph_data)
            
            # Post-execution memory update
            self.memory.add_message({
                "role": "tool",
                "content": llm_response.content,
                "metadata": {
                    "type": "visualization",
                    "graph_ref": graph_id,
                    "timestamp": datetime.now()
                }
            })
            
            return {
                "graph_id": graph_id,
                "explanation": llm_response.content,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Visualization failed: {e}")
            self.memory.add_message({
                "role": "tool",
                "content": "Error occurred while creating graph",
                "metadata": {"type": "viz_error", "error": str(e)}
            })
            return {
                "explanation": "Error occurred while creating graph",
                "status": "error"
            }
```

### 2. Modified Agent Integration (agent.py)

```python
# Around lines 336-339 in agent.py
response = await self.agent.ainvoke(
    {"messages": messages},
    config=config
)

# NEW: Check for visualization flag
if self._check_visualization_needed(response):
    viz_tool = self.graph_viz_tool  # Initialized in __init__
    viz_result = await viz_tool.arun(
        query_results=response.metadata.get('query_results'),
        context=messages
    )
    # Memory already updated within tool
```

### 3. Modified Chart Recommendation Response

```python
async def _get_chart_recommendation(prompt: str, llm) -> Dict[str, Any]:
    # ... existing logic ...
    
    return {
        "visualization_needed": True,  # Deterministic flag
        "chart_type": "graph",
        "reasoning": llm_response,
        "query_results": results  # Pass along for tool
    }
```

## Memory Management

### Memory Entry Structure

```python
# Pre-invocation marker
{
    "role": "assistant",
    "content": "Generating visualization...",
    "metadata": {
        "tool_invoke": "graph_visualization",
        "timestamp": "2025-08-27T10:00:00Z"
    }
}

# Post-success entry
{
    "role": "tool",
    "content": "Graph shows 5 entities with 8 relationships...",
    "metadata": {
        "type": "visualization",
        "graph_ref": "graph_12345",
        "status": "success",
        "timestamp": "2025-08-27T10:00:02Z"
    }
}

# Error entry
{
    "role": "tool",
    "content": "Error occurred while creating graph",
    "metadata": {
        "type": "viz_error",
        "error": "Parsing failed: Invalid JSON",
        "timestamp": "2025-08-27T10:00:01Z"
    }
}
```

## Code Reuse Strategy

### Functions to Preserve As-Is
- `generate_graph_prompt()` - Prompt generation logic
- `parse_graph_response()` - Response parsing logic
- `create_graph()` - Graph creation and rendering
- `execute_query` tool - Query execution logic
- `_get_chart_recommendation()` - Decision logic (with minor flag addition)

### New Components Required
1. `GraphVisualizationTool` class (~50 lines)
2. Memory update helpers (~10 lines)
3. Flag detection in agent (~5 lines)

### Components to Modify
- `graph_visualization.py`: Remove direct LLM call (lines 228-229)
- `agent.py`: Add tool registration and invocation logic

## Error Handling Strategy

```
1. Try visualization generation
2. ON SUCCESS:
   - Update memory with reference
   - Return graph_id and explanation
3. ON FAILURE:
   - Log full error with stack trace
   - Update memory with error marker
   - Return user-friendly error message
   - Continue conversation without blocking
```

## Testing Approach

### Unit Tests
```python
def test_graph_viz_tool_success():
    # Mock agent, LLM, and memory
    # Assert tool returns correct structure
    # Verify memory updated twice

def test_graph_viz_tool_failure():
    # Mock LLM to raise exception
    # Assert graceful error handling
    # Verify error logged and memory updated

def test_deterministic_triggering():
    # Mock execute_query response with flag
    # Assert tool invoked automatically
    # Verify no LangChain tool selection
```

### Integration Tests
```python
def test_full_flow_with_visualization():
    # User query requiring visualization
    # Assert agent → execute_query → tool → response
    # Verify context maintained throughout

def test_multiple_visualizations():
    # Multiple queries requiring graphs
    # Assert memory contains all references
    # Verify no context loss between calls
```

## Migration Steps

1. **Phase 1: Tool Creation**
   - Implement GraphVisualizationTool class
   - Add unit tests for tool

2. **Phase 2: Agent Integration**
   - Register tool in agent initialization
   - Add flag detection logic
   - Update memory management

3. **Phase 3: Cleanup**
   - Remove direct LLM invocation from graph_visualization.py
   - Update _get_chart_recommendation to return flag
   - Add integration tests

4. **Phase 4: Validation**
   - Test end-to-end flow
   - Verify context preservation
   - Confirm error resilience

## Benefits of This Architecture

1. **Unified Context**: All LLM interactions tracked in agent memory
2. **Consistent Configuration**: Single source of LLM settings
3. **Better Debugging**: Complete interaction history in one place
4. **Error Resilience**: Failures don't break conversation flow
5. **Minimal Changes**: Maximum code reuse, minimal refactoring
6. **Clear Separation**: Tool encapsulates visualization logic
7. **Deterministic Control**: No ambiguity in when visualization occurs

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Performance overhead | Acceptable for POC; optimize later if needed |
| Memory growth | Store references only, not raw data |
| Tool failure | Graceful degradation with error message |
| Complex debugging | Comprehensive logging at each step |

## Conclusion

This architecture provides a clean, maintainable approach to integrating graph visualization with the agent framework while:
- Preserving existing functionality
- Maintaining full context awareness
- Ensuring error resilience
- Minimizing code changes
- Setting foundation for future enhancements

The deterministic triggering based on LLM recommendations ensures the system remains predictable while leveraging the intelligence of the language model for decision-making.