# Graph Visualization Frontend Integration Guide

## Overview of Backend Changes

The backend has been enhanced to automatically generate graph visualization data when database queries return structured data suitable for charts. This enhancement maintains complete backward compatibility while adding powerful visualization capabilities.

### Key Backend Enhancements
1. **Automatic Graph Generation**: Query results are analyzed for visualization potential using AI
2. **Multi-Chart Support**: Supports 6 chart types (bar, line, pie, scatter, area, heatmap)
3. **Intelligent Chart Selection**: Uses LLM analysis to choose optimal chart type
4. **Recharts Compatibility**: All data is formatted for seamless Recharts integration
5. **Zero Breaking Changes**: Existing API contracts remain unchanged

### Backend Integration Points
- **MCPAgent**: Enhanced `invoke_with_query_tracking` method now generates graph data
- **Chat Handler**: Passes through graph data in responses
- **Response Model**: `Choice` model includes new optional `graph` field
- **Validation**: Comprehensive validation ensures reliable graph data

## Complete API Response Schema Changes

### Enhanced Chat Completion Response

The chat completion response maintains the existing structure with one addition - an optional `graph` field in each choice:

```typescript
interface ChatCompletionResponse {
  id: string;
  object: "chat.completion";
  created: number;
  model: string;
  choices: Choice[];
  usage?: Usage;
}

interface Choice {
  index: number;
  message: ChatMessage;
  finish_reason: string | null;
  query_result?: MCPQueryResult | null;
  graph?: GraphData | null;  // NEW: Optional graph data
}

interface GraphData {
  chart_type: "bar" | "line" | "pie" | "scatter" | "area" | "heatmap";
  data: ChartDataPoint[];
  title: string;
  x_key?: string;
  y_key?: string;
  x_label?: string;
  y_label?: string;
  generated_at: number;
  total_records: number;
  
  // Chart-specific properties
  name_key?: string;      // For pie charts
  value_key?: string;     // For pie charts
  fill?: string;          // For area/scatter charts
  fillOpacity?: number;   // For area charts
  stroke?: string;        // For line/area charts
  value_label?: string;   // For heatmaps
}

type ChartDataPoint = 
  | BarChartDataPoint 
  | LineChartDataPoint 
  | PieChartDataPoint 
  | ScatterChartDataPoint
  | AreaChartDataPoint 
  | HeatmapDataPoint;
```

### Backward Compatibility Guarantee

```typescript
// EXISTING: This continues to work unchanged
const response: ChatCompletionResponse = await fetch('/chat/completions', {
  method: 'POST',
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'How many users do we have?' }]
  })
}).then(r => r.json());

const message = response.choices[0].message.content;
const queryResult = response.choices[0].query_result;

// NEW: Optionally access graph data
const graphData = response.choices[0].graph; // Will be null if no visualization generated
```

## Chart Data Formats

### Bar Chart Data Format

```typescript
interface BarChartData extends GraphData {
  chart_type: "bar";
  data: BarChartDataPoint[];
  x_key: "name";
  y_key: "value";
}

interface BarChartDataPoint {
  name: string;          // Category label
  value: number;         // Numeric value
  color?: string;        // Bar color (optional)
}
```

**Example Response:**
```json
{
  "chart_type": "bar",
  "data": [
    { "name": "Electronics", "value": 25000, "color": "#8884d8" },
    { "name": "Clothing", "value": 18000, "color": "#82ca9d" },
    { "name": "Books", "value": 12000, "color": "#ffc658" }
  ],
  "x_key": "name",
  "y_key": "value",
  "title": "Sales by Category",
  "x_label": "Category",
  "y_label": "Sales ($)"
}
```

### Line Chart Data Format

```typescript
interface LineChartData extends GraphData {
  chart_type: "line";
  data: LineChartDataPoint[];
  x_key: "x";
  y_key: "y";
  stroke?: string;
}

interface LineChartDataPoint {
  x: string | number;    // X-axis value (date, category, or number)
  y: number;             // Y-axis numeric value
}
```

**Example Response:**
```json
{
  "chart_type": "line",
  "data": [
    { "x": "2023-01", "y": 1200 },
    { "x": "2023-02", "y": 1350 },
    { "x": "2023-03", "y": 1100 },
    { "x": "2023-04", "y": 1450 }
  ],
  "x_key": "x",
  "y_key": "y", 
  "title": "Monthly Revenue Trend",
  "x_label": "Month",
  "y_label": "Revenue ($)",
  "stroke": "#8884d8"
}
```

### Pie Chart Data Format

```typescript
interface PieChartData extends GraphData {
  chart_type: "pie";
  data: PieChartDataPoint[];
  name_key: "name";
  value_key: "value";
}

interface PieChartDataPoint {
  name: string;          // Slice label
  value: number;         // Slice value
  fill: string;          // Slice color
}
```

**Example Response:**
```json
{
  "chart_type": "pie",
  "data": [
    { "name": "Desktop", "value": 45, "fill": "#8884d8" },
    { "name": "Mobile", "value": 35, "fill": "#82ca9d" },
    { "name": "Tablet", "value": 20, "fill": "#ffc658" }
  ],
  "name_key": "name",
  "value_key": "value",
  "title": "Traffic by Device Type"
}
```

### Scatter Chart Data Format

```typescript
interface ScatterChartData extends GraphData {
  chart_type: "scatter";
  data: ScatterChartDataPoint[];
  x_key: "x";
  y_key: "y";
  fill?: string;
}

interface ScatterChartDataPoint {
  x: number;             // X-axis numeric value
  y: number;             // Y-axis numeric value
}
```

**Example Response:**
```json
{
  "chart_type": "scatter",
  "data": [
    { "x": 23, "y": 45000 },
    { "x": 28, "y": 52000 },
    { "x": 35, "y": 58000 },
    { "x": 42, "y": 65000 }
  ],
  "x_key": "x",
  "y_key": "y",
  "title": "Salary vs Age Correlation",
  "x_label": "Age",
  "y_label": "Salary ($)",
  "fill": "#8884d8"
}
```

### Area Chart Data Format

```typescript
interface AreaChartData extends GraphData {
  chart_type: "area";
  data: AreaChartDataPoint[];
  x_key: "x";
  y_key: "y";
  fill?: string;
  fillOpacity?: number;
  stroke?: string;
}

interface AreaChartDataPoint {
  x: string | number;    // X-axis value
  y: number;             // Y-axis numeric value
}
```

**Example Response:**
```json
{
  "chart_type": "area",
  "data": [
    { "x": "Q1", "y": 120000 },
    { "x": "Q2", "y": 135000 },
    { "x": "Q3", "y": 148000 },
    { "x": "Q4", "y": 162000 }
  ],
  "x_key": "x",
  "y_key": "y",
  "title": "Quarterly Revenue Growth",
  "x_label": "Quarter",
  "y_label": "Revenue ($)",
  "fill": "#8884d8",
  "fillOpacity": 0.3,
  "stroke": "#8884d8"
}
```

### Heatmap Data Format

```typescript
interface HeatmapData extends GraphData {
  chart_type: "heatmap";
  data: HeatmapDataPoint[];
  x_key: "x";
  y_key: "y";
  value_key: "value";
  value_label?: string;
}

interface HeatmapDataPoint {
  x: string;             // X-axis category
  y: string;             // Y-axis category
  value: number;         // Intensity value
}
```

**Example Response:**
```json
{
  "chart_type": "heatmap",
  "data": [
    { "x": "Monday", "y": "Morning", "value": 85 },
    { "x": "Monday", "y": "Afternoon", "value": 72 },
    { "x": "Monday", "y": "Evening", "value": 45 },
    { "x": "Tuesday", "y": "Morning", "value": 88 },
    { "x": "Tuesday", "y": "Afternoon", "value": 79 },
    { "x": "Tuesday", "y": "Evening", "value": 52 }
  ],
  "x_key": "x",
  "y_key": "y",
  "value_key": "value",
  "title": "Website Traffic Heatmap",
  "x_label": "Day",
  "y_label": "Time Period",
  "value_label": "Visitors"
}
```

## Complete API Response Examples

### Bar Chart Example
**Query**: "Show me sales by product category"

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "gemini-2.5-flash",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Here's the sales breakdown by product category:\n\nElectronics: $25,000\nClothing: $18,000\nBooks: $12,000\nHome & Garden: $8,500\nSports: $6,200\n\nElectronics is clearly our top-performing category, generating significantly more revenue than the others."
      },
      "finish_reason": "stop",
      "query_result": {
        "success": true,
        "data": [
          { "category": "Electronics", "total_sales": 25000 },
          { "category": "Clothing", "total_sales": 18000 },
          { "category": "Books", "total_sales": 12000 },
          { "category": "Home & Garden", "total_sales": 8500 },
          { "category": "Sports", "total_sales": 6200 }
        ],
        "columns": ["category", "total_sales"],
        "row_count": 5,
        "query": "SELECT category, SUM(sales_amount) as total_sales FROM sales GROUP BY category ORDER BY total_sales DESC"
      },
      "graph": {
        "chart_type": "bar",
        "data": [
          { "name": "Electronics", "value": 25000, "color": "#8884d8" },
          { "name": "Clothing", "value": 18000, "color": "#82ca9d" },
          { "name": "Books", "value": 12000, "color": "#ffc658" },
          { "name": "Home & Garden", "value": 8500, "color": "#ff7300" },
          { "name": "Sports", "value": 6200, "color": "#00ff88" }
        ],
        "x_key": "name",
        "y_key": "value",
        "title": "Sales by Product Category",
        "x_label": "Category",
        "y_label": "Sales ($)",
        "generated_at": 1700000000,
        "total_records": 5
      }
    }
  ]
}
```

### Line Chart Example
**Query**: "Show me monthly revenue for the last 6 months"

```json
{
  "choices": [
    {
      "message": {
        "content": "Here's your monthly revenue trend for the last 6 months:\n\nJune: $142,000\nJuly: $138,000\nAugust: $155,000\nSeptember: $168,000\nOctober: $172,000\nNovember: $165,000\n\nOverall, there's a positive growth trend with October being the peak month."
      },
      "graph": {
        "chart_type": "line",
        "data": [
          { "x": "2023-06", "y": 142000 },
          { "x": "2023-07", "y": 138000 },
          { "x": "2023-08", "y": 155000 },
          { "x": "2023-09", "y": 168000 },
          { "x": "2023-10", "y": 172000 },
          { "x": "2023-11", "y": 165000 }
        ],
        "x_key": "x",
        "y_key": "y",
        "title": "Monthly Revenue Trend",
        "x_label": "Month",
        "y_label": "Revenue ($)",
        "stroke": "#8884d8",
        "generated_at": 1700000000,
        "total_records": 6
      }
    }
  ]
}
```

### Pie Chart Example
**Query**: "What's the breakdown of customer types?"

```json
{
  "choices": [
    {
      "message": {
        "content": "Here's your customer type distribution:\n\nPremium: 35% (245 customers)\nStandard: 45% (315 customers)\nBasic: 20% (140 customers)\n\nStandard customers make up nearly half of your customer base."
      },
      "graph": {
        "chart_type": "pie",
        "data": [
          { "name": "Premium", "value": 245, "fill": "#8884d8" },
          { "name": "Standard", "value": 315, "fill": "#82ca9d" },
          { "name": "Basic", "value": 140, "fill": "#ffc658" }
        ],
        "name_key": "name",
        "value_key": "value", 
        "title": "Customer Distribution by Type",
        "generated_at": 1700000000,
        "total_records": 3
      }
    }
  ]
}
```

### Scatter Chart Example
**Query**: "Show correlation between customer age and lifetime value"

```json
{
  "choices": [
    {
      "message": {
        "content": "Here's the relationship between customer age and lifetime value. There appears to be a positive correlation - older customers tend to have higher lifetime values."
      },
      "graph": {
        "chart_type": "scatter",
        "data": [
          { "x": 25, "y": 1200 },
          { "x": 32, "y": 2100 },
          { "x": 28, "y": 1650 },
          { "x": 45, "y": 3200 },
          { "x": 38, "y": 2800 },
          { "x": 52, "y": 3800 }
        ],
        "x_key": "x",
        "y_key": "y",
        "title": "Customer Age vs Lifetime Value",
        "x_label": "Age",
        "y_label": "Lifetime Value ($)",
        "fill": "#8884d8",
        "generated_at": 1700000000,
        "total_records": 147
      }
    }
  ]
}
```

### Area Chart Example
**Query**: "Show quarterly growth in user signups"

```json
{
  "choices": [
    {
      "message": {
        "content": "Here's your quarterly user signup growth:\n\nQ1 2023: 1,250 signups\nQ2 2023: 1,420 signups\nQ3 2023: 1,680 signups\nQ4 2023: 1,890 signups\n\nYou're showing consistent quarter-over-quarter growth in user acquisition."
      },
      "graph": {
        "chart_type": "area",
        "data": [
          { "x": "Q1 2023", "y": 1250 },
          { "x": "Q2 2023", "y": 1420 },
          { "x": "Q3 2023", "y": 1680 },
          { "x": "Q4 2023", "y": 1890 }
        ],
        "x_key": "x",
        "y_key": "y",
        "title": "Quarterly User Signup Growth",
        "x_label": "Quarter",
        "y_label": "New Signups",
        "fill": "#8884d8",
        "fillOpacity": 0.3,
        "stroke": "#8884d8",
        "generated_at": 1700000000,
        "total_records": 4
      }
    }
  ]
}
```

### Heatmap Example
**Query**: "Show website traffic intensity by day and hour"

```json
{
  "choices": [
    {
      "message": {
        "content": "Here's your website traffic pattern showing intensity by day of week and time period. Peak traffic appears to be on Tuesday and Wednesday during business hours."
      },
      "graph": {
        "chart_type": "heatmap",
        "data": [
          { "x": "Monday", "y": "Morning", "value": 85 },
          { "x": "Monday", "y": "Afternoon", "value": 72 },
          { "x": "Monday", "y": "Evening", "value": 45 },
          { "x": "Tuesday", "y": "Morning", "value": 95 },
          { "x": "Tuesday", "y": "Afternoon", "value": 88 },
          { "x": "Tuesday", "y": "Evening", "value": 52 },
          { "x": "Wednesday", "y": "Morning", "value": 92 },
          { "x": "Wednesday", "y": "Afternoon", "value": 85 },
          { "x": "Wednesday", "y": "Evening", "value": 48 }
        ],
        "x_key": "x",
        "y_key": "y",
        "value_key": "value",
        "title": "Website Traffic Heatmap",
        "x_label": "Day",
        "y_label": "Time Period", 
        "value_label": "Visitors",
        "generated_at": 1700000000,
        "total_records": 21
      }
    }
  ]
}
```

## Handling Null Graph Responses

### Detection and Handling

Graph data will be `null` when:
- **Non-query messages**: "Hello, how are you?" 
- **Insufficient data**: Query returns < 2 rows
- **Non-numeric data**: Only text columns, no numbers to visualize
- **Too much data**: Query returns > 1000 rows (performance limit)
- **Analysis failure**: LLM unable to determine optimal chart type
- **Generation errors**: Technical errors in graph generation (logged but not exposed)

**Example of non-graph response:**
```json
{
  "choices": [
    {
      "message": {
        "content": "Hello! I'm here to help you analyze your data. You can ask me questions about your database, and I'll provide both answers and visualizations when appropriate."
      },
      "graph": null
    }
  ]
}
```

### Frontend Response Handling Pattern

```typescript
interface ChatResponse {
  choices: Array<{
    message: { content: string };
    query_result?: any;
    graph?: GraphData | null;
  }>;
}

const handleChatResponse = (response: ChatResponse) => {
  const choice = response.choices[0];
  const message = choice.message.content;
  const queryResult = choice.query_result;
  const graphData = choice.graph;
  
  // Always display the message
  displayMessage(message);
  
  // Display query result table if available
  if (queryResult && queryResult.success) {
    displayQueryResultTable(queryResult);
  }
  
  // Display graph if available
  if (graphData) {
    displayChart(graphData);
  }
  
  // Note: No special handling needed for null graph
  // The UI simply doesn't show a chart when graph is null
};
```

## Integration Guidelines

### Required Type Definitions

```typescript
// types/chat.ts
export interface ChatChoice {
  index: number;
  message: {
    role: 'assistant' | 'user' | 'system';
    content: string;
  };
  finish_reason: string | null;
  query_result?: QueryResult | null;
  graph?: GraphData | null;  // ADD THIS LINE
}

export interface GraphData {
  chart_type: 'bar' | 'line' | 'pie' | 'scatter' | 'area' | 'heatmap';
  data: any[];
  title: string;
  x_key?: string;
  y_key?: string;
  name_key?: string;
  value_key?: string;
  x_label?: string;
  y_label?: string;
  fill?: string;
  fillOpacity?: number;
  stroke?: string;
  value_label?: string;
  generated_at: number;
  total_records: number;
}
```

### Chart Rendering Requirements

#### Bar Charts
- Use `data`, `x_key` ("name"), `y_key` ("value")
- Each data point has `name`, `value`, optional `color`

#### Line Charts  
- Use `data`, `x_key` ("x"), `y_key` ("y")
- Each data point has `x`, `y`
- Optional `stroke` property for line color

#### Pie Charts
- Use `data`, `name_key` ("name"), `value_key` ("value") 
- Each data point has `name`, `value`, `fill`

#### Scatter Charts
- Use `data`, `x_key` ("x"), `y_key` ("y")
- Each data point has `x`, `y` (both numeric)
- Optional `fill` property for dot color

#### Area Charts
- Same as line charts but with `fill`, `fillOpacity`, `stroke` properties
- Use `data`, `x_key` ("x"), `y_key` ("y")

#### Heatmaps  
- Use `data`, `x_key` ("x"), `y_key` ("y"), `value_key` ("value")
- Each data point has `x`, `y`, `value`
- Custom implementation required (not built into Recharts)

### Error Handling Requirements

1. **Validation**: Validate graph data structure before rendering
2. **Graceful Degradation**: Show error message if chart fails to render
3. **Loading States**: Display loading indicator while processing
4. **Fallback**: Continue showing text response and query results even if chart fails

### Performance Considerations

- Charts are pre-limited by backend (bar: 20 points, line: 100, pie: 8 slices, etc.)
- Use responsive containers for proper sizing
- Implement lazy loading for chart components if needed
- Consider virtualization for large datasets in tables

## Summary

This API contract provides:

1. **Complete backward compatibility** - Existing API usage unchanged
2. **Rich data formats** - Six chart types with comprehensive metadata
3. **Flexible integration** - Optional graph field allows progressive enhancement
4. **Production-ready** - Includes error scenarios, validation, and performance limits
5. **Clear patterns** - Consistent data structures across all chart types

The frontend can implement chart visualization by checking for the presence of the `graph` field and rendering the appropriate chart type based on the provided data format and metadata.