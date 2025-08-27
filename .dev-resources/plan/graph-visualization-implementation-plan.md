# Graph Visualization Implementation Plan

## Core Requirements in My Own Words

You need me to implement an automatic graph visualization system that:
1. **Intercepts database query results** from the existing chat completion flow
2. **Intelligently analyzes** the data to determine if it's chart-worthy
3. **Uses the LLM** to select the best chart type based on actual data samples
4. **Transforms the data** into Recharts-compatible format for frontend consumption
5. **Gracefully handles all errors** without breaking the main chat flow

## Specific Requirements & Actions

### 1. **Enhance Response Models**
   - **What**: Add optional `graph` field to Choice model
   - **How**: Modify `src/moba_server/models.py` to include graph field
   - **Why**: Maintains backward compatibility while enabling graph data

### 2. **Create Data Analysis Foundation**
   - **What**: Build utility functions to analyze data types
   - **How**: Implement `_is_numeric()`, `_is_date_like()`, `_parse_date_value()`
   - **Why**: Need to classify columns for intelligent chart selection

### 3. **Implement Suitability Detection**
   - **What**: Check if query results can be visualized
   - **How**: Verify 2+ rows, 2+ columns, numeric/temporal data, reasonable size (2-1000 rows)
   - **Why**: Prevent attempting visualization on unsuitable data

### 4. **Build LLM Chart Recommendation**
   - **What**: Use Gemini to analyze actual data samples and recommend charts
   - **How**: Create prompts with data characteristics, sample rows, and get JSON response
   - **Why**: Leverage AI for intelligent chart type selection

### 5. **Create Chart Transformers**
   - **What**: Convert raw SQL data to Recharts format
   - **How**: Individual functions for bar, line, pie, scatter, area, heatmap
   - **Why**: Frontend needs specific data structure per chart type

### 6. **Integrate into Main Flow**
   - **What**: Enhance `invoke_with_query_tracking()` method
   - **How**: Add graph generation after query result extraction
   - **Why**: Seamlessly add visualization without breaking existing functionality

### 7. **Implement Comprehensive Logging**
   - **What**: Log every step of the visualization pipeline
   - **How**: Create GraphVisualizationLogger with detailed logging methods
   - **Why**: Production debugging and monitoring

## Implementation Steps in Logical Order

### Phase 1: Foundation (Independent)
1. Update Choice model with graph field
2. Create basic utility functions
3. Set up logging infrastructure

### Phase 2: Analysis Layer (Depends on Phase 1)
1. Implement `is_suitable_for_visualization()`
2. Create `analyze_data_characteristics()`
3. Build validation functions

### Phase 3: Transformation Layer (Can parallel with Phase 2)
1. Create all 6 chart transformer functions
2. Build dispatcher function
3. Add chart-specific validators

### Phase 4: LLM Integration (Depends on Phase 2)
1. Build prompt generation
2. Implement LLM call with JSON extraction
3. Add fallback heuristics

### Phase 5: Main Integration (Depends on all above)
1. Enhance `invoke_with_query_tracking()` in agent.py
2. Update ChatCompletionHandler to pass graph data
3. Add error handling decorators

## Sub-Agent Strategy

Since you've specified NOT to use requirement-analyzer or impact-analyzer (as the document contains all needed information), I will:
- **Use feature-completion-reviewer** at the end to ensure no TODOs or incomplete implementations remain
- Work directly based on the architecture document

## Parallel vs Sequential Work

**Can be done in parallel:**
- All 6 chart transformation functions (independent of each other)
- Utility functions and validators
- Logging infrastructure
- Model updates

**Must be done sequentially:**
1. First: Create foundation utilities and models
2. Then: Build analysis and suitability checks
3. Then: Implement LLM integration
4. Finally: Wire everything into main flow

## Complete TODO List

```
□ 1. Update Models
   □ Add graph field to Choice in models.py
   □ Create optional GraphData model

□ 2. Create Utility Functions
   □ _is_numeric()
   □ _is_date_like()  
   □ _parse_date_value()

□ 3. Implement Data Analysis
   □ is_suitable_for_visualization()
   □ analyze_data_characteristics()

□ 4. Build Chart Transformers
   □ _transform_bar_chart()
   □ _transform_line_chart()
   □ _transform_pie_chart()
   □ _transform_scatter_chart()
   □ _transform_area_chart()
   □ _transform_heatmap_chart()
   □ transform_to_chart_data() dispatcher

□ 5. Implement LLM Integration
   □ _build_chart_analysis_prompt()
   □ _get_chart_recommendation()
   □ _process_llm_response()
   □ _validate_recommendation()
   □ _get_fallback_recommendation()

□ 6. Create Validators
   □ validate_graph_data()
   □ _validate_chart_specific_data()
   □ Individual chart validators (6 total)

□ 7. Build Logging Infrastructure
   □ GraphVisualizationLogger class
   □ log_performance_metrics decorator
   □ safe_graph_generation decorator

□ 8. Integrate into Main Flow
   □ Enhance invoke_with_query_tracking() in agent.py
   □ Create analyze_and_generate_graph() method
   □ Update ChatCompletionHandler in chat_handler.py

□ 9. Testing & Validation
   □ Test with various query results
   □ Verify backward compatibility
   □ Test error scenarios

□ 10. Final Review
   □ Run feature-completion-reviewer agent
   □ Ensure no TODOs remain
   □ Verify all logging in place
```

## Key Implementation Notes

- **Lean approach**: All functions added directly to existing files (agent.py, models.py, chat_handler.py)
- **No new modules**: Everything integrated into existing structure
- **Graceful failures**: Graph generation errors never break main chat flow
- **Performance limits**: Bar (20), Line (100), Pie (8), Scatter (200) data points
- **LLM reuse**: Use existing Gemini instance from agent

The implementation will detect query results, analyze them with the LLM, transform to Recharts format, and seamlessly add graph data to responses while maintaining full backward compatibility.

**Shall I proceed with this implementation plan?**