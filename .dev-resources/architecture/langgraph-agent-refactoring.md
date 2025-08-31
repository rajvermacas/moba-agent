# LangGraph Agent Architecture Refactoring

## Executive Summary

This document outlines the refactored architecture for the MOBA LangGraph agent, transitioning from a monolithic agent_node to a specialized multi-node architecture with clear separation of concerns.

## Problem Statement

### Current State Issues
- **Bloated agent_node**: Single node handling tool selection, validation, visualization decisions, and response formatting
- **Token Inefficiency**: Full ToolMessages (including large database results) passed to LLM, causing 2-4x token usage
- **Context Overflow Risk**: Database queries with 100s of rows risk exceeding 128K token limits  
- **Mixed Responsibilities**: agent_node violates Single Responsibility Principle
- **Performance Degradation**: LLM processes unnecessary raw data affecting accuracy

### Target State Goals
- **Clear Separation**: Each node has single, well-defined responsibility
- **Token Optimization**: 60-70% reduction in token usage via message filtering
- **Improved Maintainability**: Easier to debug, test, and extend
- **Better User Experience**: Consistent, well-formatted responses via dedicated summarizer

## Architecture Overview

### Node Graph Structure

```
Current State:
agent_node → ToolNode → agent_node → visualization_node → agent_node → END

Target State:
agent_node → ToolNode → agent_node → visualization_node → summarizer_node → END
                            ↓
                           END
```

### Core Components

#### 1. ExtendedAgentState
```python
class ExtendedAgentState(MessagesState):
    """Enhanced state for passing data between nodes"""
    
    # Core message storage
    messages: List[BaseMessage]
    
    # Thread management
    thread_id: str
    
    # Tool execution tracking
    tool_error_counts: Dict[str, int]  # Track consecutive errors per tool
    tool_results: Optional[Dict]       # Latest tool execution results
    
    # Query and visualization
    query_result: Optional[Dict]       # Database query results
    visualization_decision: Optional[StructuredAgentResponse]
    visualization_formatted: bool = False
    
    # Summary context
    summary_context: Optional[str]     # Context for summarizer node
```

## Algorithm Sketch

### Flow Sequences

#### Sequence 1: Query Tool with Visualization
```
Human → agent_node → ToolNode → agent_node → visualization_node → summarizer_node → END
```

#### Sequence 2: Non-Query Tool
```
Human → agent_node → ToolNode → agent_node → END
```

#### Sequence 3: No Tool Required
```
Human → agent_node → END
```

### Node Specifications

#### 1. AGENT_NODE

**Input:**
- Last 10 HumanMessages from conversation history
- Filtered messages (SystemMessages, AIMessages, small ToolMessages)
- Current state with tool_error_counts

**Process:**
1. Filter messages to reduce token usage:
   - Remove large ToolMessages (>2K chars)
   - Summarize query results to metadata only
   - Keep error messages for retry logic
2. Identify user intent
3. Select appropriate tool(s) if needed
4. Generate tool arguments
5. Validate tool results (success/error)
6. Track consecutive tool errors

**Output:**
- AIMessage with tool_calls OR
- AIMessage with direct response OR
- AIMessage with error handling

**Routes to:**
- `tools`: When tool calls are needed
- `visualization_node`: When execute_query_* succeeds
- `END`: When no tools needed or non-query tools complete

**Message Filtering Implementation:**

File: `src/moba_agent/message_utils.py` (new file)

```python
import re
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from .constants import QUERY_TOOL_PATTERN

def filter_messages_for_agent(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Filter messages for agent_node to reduce token usage.
    
    Strategy:
    1. Always include first 2 SystemMessages
    2. Find last 10th HumanMessage and include all messages from there
    3. Apply filtering rules to ToolMessages based on size
    """
    if not messages:
        return []
    
    filtered = []
    query_tool_regex = re.compile(QUERY_TOOL_PATTERN)
    
    # Step 1: Always include first 2 SystemMessages
    system_count = 0
    for msg in messages:
        if isinstance(msg, SystemMessage) and system_count < 2:
            filtered.append(msg)
            system_count += 1
            if system_count >= 2:
                break
    
    # Step 2: Find index of 10th last HumanMessage
    human_indices = []
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            human_indices.append(i)
    
    # Determine starting index (from 10th last HumanMessage or start)
    start_index = 0
    if len(human_indices) > 10:
        # Get the 10th last human message index
        start_index = human_indices[-10]
    elif human_indices:
        # If less than 10 human messages, start from first
        start_index = human_indices[0]
    
    # Step 3: Process messages from start_index
    for i in range(start_index, len(messages)):
        msg = messages[i]
        
        # Skip if already added as initial SystemMessage
        if isinstance(msg, SystemMessage) and msg in filtered[:2]:
            continue
        
        # Include Human and AI messages directly
        if isinstance(msg, (HumanMessage, AIMessage, SystemMessage)):
            filtered.append(msg)
        
        # Filter ToolMessages based on size and type
        elif isinstance(msg, ToolMessage):
            # Always keep error messages
            if hasattr(msg, 'status') and msg.status == 'error':
                filtered.append(msg)
            
            # Check if it's a query tool result
            elif query_tool_regex.match(getattr(msg, 'name', '')):
                # Summarize large query results (>2000 chars)
                if len(msg.content) > 2000:
                    summary = create_query_result_summary(msg)
                    filtered.append(AIMessage(content=summary))
                else:
                    filtered.append(msg)
            
            # For non-query tools, include if under 2000 chars
            elif len(msg.content) < 2000:
                filtered.append(msg)
            else:
                # Summarize large non-query tool results
                summary = f"Tool {msg.name} result (truncated): {msg.content[:2000]}..."
                filtered.append(AIMessage(content=summary))
    
    return filtered

def create_query_result_summary(tool_msg: ToolMessage) -> str:
    """
    Create a summary of query results for token optimization.
    
    File: src/moba_agent/message_utils.py
    """
    import json
    
    try:
        result = json.loads(tool_msg.content)
        row_count = len(result.get('rows', []))
        columns = list(result['rows'][0].keys()) if result.get('rows') else []
        
        summary = f"Query tool '{tool_msg.name}' executed successfully:\n"
        summary += f"- Rows returned: {row_count}\n"
        if columns:
            summary += f"- Columns: {', '.join(columns[:10])}"
            if len(columns) > 10:
                summary += f" (and {len(columns)-10} more)"
        
        return summary
    except:
        return f"Query tool '{tool_msg.name}' returned {len(tool_msg.content)} chars of data"

def filter_messages_for_summarizer(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Filter messages for summarizer_node - from last HumanMessage to end.
    
    File: src/moba_agent/message_utils.py
    """
    # Find last HumanMessage index
    last_human_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_idx = i
            break
    
    # Return messages from last HumanMessage onwards
    if last_human_idx >= 0:
        return messages[last_human_idx:]
    
    # If no HumanMessage found, return last 5 messages as fallback
    return messages[-5:] if len(messages) > 5 else messages
```

#### 2. TOOL_NODE (Existing)

**Input:**
- Tool calls from agent_node

**Process:**
- Execute requested tools
- Return results as ToolMessage

**Output:**
- ToolMessage with results or errors

**Routes to:**
- `agent_node`: Always (for validation)

#### 3. VISUALIZATION_NODE

**Input:**
- query_result from state
- Relevant conversation context

**Process:**
1. Analyze query result structure
2. Determine if visualization is appropriate
3. Select optimal chart type
4. Generate chart configuration

**Output:**
- Updates state.visualization_decision with:
  - should_visualize: bool
  - chart_config: Optional[ChartConfig]
  - reasoning: str

**Routes to:**
- `summarizer_node`: Always

#### 4. SUMMARIZER_NODE (New)

**Input:**
- Messages from last HumanMessage onwards
- tool_results from state
- visualization_decision from state
- query_result from state (if applicable)

**Process:**
1. Extract messages scope (last HumanMessage to end)
2. Analyze tool results for key insights
3. Incorporate visualization decision
4. Format user-friendly response
5. Handle visualization failures gracefully

**Output:**
- AIMessage with formatted final response

**Routes to:**
- `END`: Always

**Implementation:**
```python
async def summarizer_node(state: ExtendedAgentState) -> ExtendedAgentState:
    """Summarize results and format final response"""
    
    # Extract messages from last HumanMessage
    messages = state["messages"]
    last_human_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_idx = i
            break
    
    relevant_messages = messages[last_human_idx:] if last_human_idx >= 0 else messages
    
    # Prepare context for summarization
    system_prompt = """
    You are a helpful assistant that summarizes results clearly.
    Based on the conversation and any tool results:
    1. Extract key insights from the data
    2. Format a clear, concise response
    3. Mention visualizations if created
    4. Handle any errors gracefully
    """
    
    enhanced_messages = [SystemMessage(content=system_prompt)] + relevant_messages
    
    # Add visualization context
    if state.get("visualization_decision"):
        viz = state["visualization_decision"]
        if viz.should_visualize and viz.chart_config:
            viz_context = f"Visualization created: {viz.chart_config.chart_type} chart"
            enhanced_messages.append(SystemMessage(content=viz_context))
        elif viz.should_visualize:
            enhanced_messages.append(SystemMessage(content="Visualization failed to generate"))
    
    # Generate summary
    response = await state["llm"].ainvoke(enhanced_messages)
    
    return {"messages": [response]}
```

### Routing Logic

File: `src/moba_agent/routing.py` (new file)

```python
import re
from typing import Dict, Any
from langchain_core.messages import AIMessage, ToolMessage
from .constants import QUERY_TOOL_PATTERN

def route_after_agent(state: Dict[str, Any]) -> str:
    """
    Determine routing after agent_node.
    
    File: src/moba_agent/routing.py
    
    Returns:
        - "tools": If agent wants to call tools
        - "visualize": If query tool was just executed successfully
        - "end": If conversation is complete
    """
    query_tool_regex = re.compile(QUERY_TOOL_PATTERN)
    last_message = state["messages"][-1]
    
    # Check for tool calls
    if isinstance(last_message, AIMessage):
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
    
    # Check if we need visualization (after query tool)
    if not state.get("visualization_decision"):
        # Look for recent query tool execution
        for msg in reversed(state["messages"][-5:]):
            if isinstance(msg, ToolMessage):
                # Use regex pattern from constants
                if query_tool_regex.match(getattr(msg, 'name', '')):
                    # Only route to visualization if tool succeeded
                    if not (hasattr(msg, 'status') and msg.status == 'error'):
                        return "visualize"
    
    return "end"

def route_after_tools(state: Dict[str, Any]) -> str:
    """
    Route after tool execution.
    
    File: src/moba_agent/routing.py
    
    Returns:
        - "agent": Always returns to agent for validation
    """
    return "agent"

def route_after_visualization(state: Dict[str, Any]) -> str:
    """
    Route after visualization node.
    
    File: src/moba_agent/routing.py
    
    Returns:
        - "summarize": Always routes to summarizer
    """
    return "summarize"

def route_after_summarizer(state: Dict[str, Any]) -> str:
    """
    Route after summarizer node.
    
    File: src/moba_agent/routing.py
    
    Returns:
        - "end": Always completes the conversation
    """
    return "end"
```

## Key Design Decisions

### 1. State Management
- **Decision**: Use ExtendedAgentState with dedicated fields
- **Rationale**: Clear data flow, easier debugging, type safety
- **Alternative Considered**: Message enrichment pattern
- **Trade-off**: Slightly more memory usage for cleaner architecture

### 2. Message Filtering Strategy
- **Decision**: Hybrid approach - filter large results, keep errors
- **Rationale**: 60-70% token reduction while maintaining functionality
- **Implementation**: Size-based filtering with tool-type awareness

### 3. Context Preservation
- **Agent_node**: Last 10 HumanMessages + filtered content
- **Visualization_node**: Query results from state
- **Summarizer_node**: Last HumanMessage to end (current iteration scope)

### 4. Error Handling
- **Visualization Failure**: Summarizer mentions "couldn't generate graph"
- **Summarizer Failure**: Fast fail, no rollback
- **Tool Errors**: Retry logic remains in agent_node (max 3 attempts)

### 5. Performance Considerations
- **Sequential Processing**: No parallelization for predictability
- **LLM Calls**: Maximum 3 per request (agent, visualization, summarizer)
- **Token Optimization**: 60-70% reduction via message filtering

## File Organization

### New Files to Create

1. **`src/moba_agent/message_utils.py`**
   - `filter_messages_for_agent()`: Message filtering for agent_node
   - `filter_messages_for_summarizer()`: Message filtering for summarizer_node
   - `create_query_result_summary()`: Summarize large query results

2. **`src/moba_agent/routing.py`**
   - `route_after_agent()`: Routing logic after agent_node
   - `route_after_tools()`: Routing logic after tool execution
   - `route_after_visualization()`: Routing logic after visualization
   - `route_after_summarizer()`: Routing logic after summarizer

3. **`src/moba_agent/nodes.py`** (optional - or keep in agent.py)
   - `summarizer_node()`: New summarizer node implementation
   - Refactored `agent_node()`: Cleaned up agent logic

### Modified Files

1. **`src/moba_agent/agent.py`**
   - Import new modules (message_utils, routing)
   - Refactor `agent_node()` to use message filtering
   - Add `summarizer_node()` 
   - Update `_create_agent()` to use new routing functions
   - Modify workflow edges for new architecture

2. **`src/moba_agent/schemas.py`**
   - Update `ExtendedAgentState` with new fields:
     - `tool_results`
     - `summary_context`
     - Keep existing visualization fields

3. **`src/moba_agent/constants.py`**
   - Already contains `QUERY_TOOL_PATTERN`
   - Add any new constants as needed

## Implementation Plan

### Phase 1: State Schema Update
1. Update ExtendedAgentState with new fields
2. Add message filtering utilities
3. Create state management helpers

### Phase 2: Node Refactoring
1. Refactor agent_node to remove visualization logic
2. Implement message filtering in agent_node
3. Create summarizer_node
4. Update visualization_node routing

### Phase 3: Workflow Update
1. Update graph edges and routing logic
2. Implement conditional routing functions
3. Test edge cases

### Phase 4: Testing & Optimization
1. Integration tests for all flow patterns
2. Performance benchmarking
3. Token usage analysis
4. Error scenario testing

## Success Metrics

1. **Token Usage**: 60-70% reduction in average token consumption
2. **Response Quality**: Consistent, well-formatted responses
3. **Error Handling**: Graceful degradation on failures
4. **Maintainability**: Clear separation of concerns
5. **Performance**: <3 second average response time

## Risk Mitigation

### Risk 1: Increased Latency
- **Mitigation**: Monitor LLM call times, optimize prompts
- **Fallback**: Direct routing for time-sensitive queries

### Risk 2: Context Loss
- **Mitigation**: Careful message filtering, preserve critical context
- **Monitoring**: Log filtered vs original message sizes

### Risk 3: Summarizer Failures
- **Mitigation**: Robust error handling, fallback to raw response
- **Testing**: Comprehensive failure scenario tests

## Testing Strategy

### Unit Tests
- Message filtering logic
- Routing decisions
- State mutations

### Integration Tests
1. Query → Visualization → Summary flow
2. Non-query tool flow
3. No-tool conversation flow
4. Error handling scenarios

### Performance Tests
- Token usage comparison
- Response time benchmarks
- Memory usage profiling

## Conclusion

This refactored architecture provides:
- **Clear separation of concerns** with specialized nodes
- **Significant token optimization** via intelligent message filtering
- **Improved maintainability** through single-responsibility design
- **Better user experience** with consistent response formatting

The architecture maintains backward compatibility while providing a foundation for future enhancements such as parallel processing, caching, and advanced visualization capabilities.