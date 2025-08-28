# Google Gemini 2.5 Flash Structured Output Reference

## Overview

Google Gemini 2.5 Flash provides comprehensive structured output capabilities that enable developers to receive responses in predictable, parseable formats instead of free-form text. This feature is essential for building robust AI applications that require reliable data extraction and processing.

**Key Features:**
- JSON schema enforcement with Pydantic model support
- Enum-based response constraints
- OpenAPI 3.0 compatible schema definitions
- Seamless LangGraph integration for agent workflows
- Support for both simple and complex nested structures

**Version Information:**
- Available on: Gemini 2.5 Flash, Gemini 2.5 Pro, Gemini 1.5 Pro, Gemini 1.5 Flash
- API Support: Google AI Studio, Vertex AI
- Documentation Date: August 2025

**Official Documentation Links:**
- [Structured Output - Gemini API](https://ai.google.dev/gemini-api/docs/structured-output)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [LangGraph Integration Examples](https://github.com/google-gemini/gemini-fullstack-langgraph-quickstart)

## Installation & Setup

### Python SDK Installation

```bash
pip install google-genai
# For LangGraph integration
pip install langgraph langchain-google-genai
# For Pydantic models
pip install pydantic
```

### Environment Configuration

```bash
export GEMINI_API_KEY="your_api_key_here"
```

Or create a `.env` file:
```bash
GEMINI_API_KEY=your_api_key_here
```

### Client Initialization

```python
from google import genai
import os

# Initialize client with API key
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Or let it auto-detect from environment
client = genai.Client()
```

## Authentication

### API Key Setup

1. **Obtain API Key**: Visit [Google AI Studio](https://aistudio.google.com) to generate your API key
2. **Set Environment Variable**: 
   ```bash
   export GEMINI_API_KEY="your_key_here"
   ```
3. **Security Best Practices**:
   - Never hardcode API keys in source code
   - Use environment variables or secure credential storage
   - Rotate keys regularly
   - Restrict key permissions to necessary scopes only

## Core Structured Output Methods

### 1. JSON Schema with Pydantic Models

The most robust approach using type-safe Pydantic models:

```python
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List

class Recipe(BaseModel):
    recipe_name: str
    ingredients: List[str]
    cooking_time_minutes: int
    difficulty_level: str

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Give me a recipe for chocolate chip cookies",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Recipe,
    ),
)

# Access parsed response
recipe_data = response.parsed  # Returns Recipe instance
print(f"Recipe: {recipe_data.recipe_name}")
```

### 2. Dictionary-Based JSON Schema

For simpler use cases without Pydantic:

```python
from google import genai
from google.genai import types

client = genai.Client()

# Define schema as dictionary
country_schema = {
    'type': 'OBJECT',
    'properties': {
        'name': {'type': 'STRING'},
        'population': {'type': 'INTEGER'},
        'capital': {'type': 'STRING'},
        'continent': {'type': 'STRING'},
    },
    'required': ['name', 'population', 'capital', 'continent']
}

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='Give me information about Japan',
    config=types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=country_schema,
    ),
)

print(response.text)  # JSON string
```

### 3. Enum-Based Response Constraints

For responses that must be one of predefined options:

```python
from google import genai
from enum import Enum

class MusicGenre(Enum):
    ROCK = "Rock"
    JAZZ = "Jazz"
    CLASSICAL = "Classical"
    ELECTRONIC = "Electronic"
    HIP_HOP = "Hip Hop"

client = genai.Client()

# JSON enum response
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='What genre is Beethoven's Symphony No. 9?',
    config={
        'response_mime_type': 'application/json',
        'response_schema': MusicGenre,
    },
)

# Text enum response
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='What genre is Beethoven's Symphony No. 9?',
    config={
        'response_mime_type': 'text/x.enum',
        'response_schema': MusicGenre,
    },
)
```

## LangGraph Integration

### Basic LangGraph Setup with Structured Output

```python
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, MessagesState

class SearchQuery(BaseModel):
    """Search query with metadata"""
    query: str = Field(..., description="The search query")
    intent: str = Field(..., description="User intent behind the query")
    priority: int = Field(..., description="Priority from 1-10")

def generate_search_queries(state: MessagesState):
    """Generate structured search queries"""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7
    )
    
    structured_llm = llm.with_structured_output(SearchQuery)
    
    result = structured_llm.invoke(
        "Generate a search query about renewable energy trends"
    )
    
    return {"messages": [result]}

# Build graph
graph = StateGraph(MessagesState)
graph.add_node("generate_queries", generate_search_queries)
graph.set_entry_point("generate_queries")
graph.set_finish_point("generate_queries")

app = graph.compile()
```

### Advanced LangGraph Agent with Reflection

```python
from pydantic import BaseModel
from typing import List
from langgraph.graph import StateGraph

class ResearchState(BaseModel):
    question: str
    queries: List[str] = []
    results: List[str] = []
    summary: str = ""
    is_complete: bool = False
    iteration_count: int = 0

class QueryGeneration(BaseModel):
    queries: List[str]
    reasoning: str

class ReflectionOutput(BaseModel):
    is_sufficient: bool
    gaps_identified: List[str]
    follow_up_queries: List[str]
    confidence_score: int

def query_generation_node(state: ResearchState):
    """Generate search queries using structured output"""
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    structured_llm = llm.with_structured_output(QueryGeneration)
    
    prompt = f"""
    Research Topic: {state.question}
    Previous Queries: {state.queries}
    
    Generate 3 new search queries to research this topic comprehensively.
    """
    
    result = structured_llm.invoke(prompt)
    
    return ResearchState(
        **state.dict(),
        queries=state.queries + result.queries
    )

def reflection_node(state: ResearchState):
    """Reflect on research completeness using structured output"""
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    structured_llm = llm.with_structured_output(ReflectionOutput)
    
    prompt = f"""
    Research Question: {state.question}
    Current Summary: {state.summary}
    Queries Executed: {len(state.queries)}
    
    Evaluate if the research is complete and identify any gaps.
    """
    
    result = structured_llm.invoke(prompt)
    
    return ResearchState(
        **state.dict(),
        is_complete=result.is_sufficient,
        iteration_count=state.iteration_count + 1
    )

# Build research agent
def build_research_agent():
    graph = StateGraph(ResearchState)
    
    graph.add_node("generate_queries", query_generation_node)
    graph.add_node("reflect", reflection_node)
    
    graph.set_entry_point("generate_queries")
    graph.add_edge("generate_queries", "reflect")
    
    # Conditional edge based on completeness
    def should_continue(state: ResearchState):
        if state.is_complete or state.iteration_count >= 3:
            return "END"
        return "generate_queries"
    
    graph.add_conditional_edges(
        "reflect",
        should_continue,
        {"generate_queries": "generate_queries", "END": "__end__"}
    )
    
    return graph.compile()
```

## Code Examples

### Basic Usage Patterns

#### Simple Text Classification

```python
from google import genai
from enum import Enum

class Sentiment(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="I love this new smartphone! The camera is amazing.",
    config={
        'response_mime_type': 'text/x.enum',
        'response_schema': Sentiment,
    },
)

print(response.text)  # "positive"
```

#### Data Extraction from Text

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class ContactInfo(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None

class EventInfo(BaseModel):
    title: str
    date: str
    location: str
    attendees: List[ContactInfo]

client = genai.Client()
email_content = """
Subject: Q4 Strategy Meeting

Hi everyone,

Our Q4 strategy meeting is scheduled for December 15th, 2024 at the San Francisco office.

Attendees:
- John Smith (john@company.com, 555-1234) from TechCorp
- Sarah Johnson (sarah.j@startup.io) from InnovateNow
- Mike Wilson (mike@consult.biz, 555-5678) from ConsultingPlus

Best regards,
Team Lead
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"Extract event and contact information from this email:\n{email_content}",
    config={
        'response_mime_type': 'application/json',
        'response_schema': EventInfo,
    },
)

event_data = response.parsed
print(f"Event: {event_data.title}")
print(f"Attendees: {len(event_data.attendees)}")
```

#### Complex Nested Structures

```python
from pydantic import BaseModel
from typing import List, Dict, Optional
from enum import Enum

class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TaskStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

class Assignee(BaseModel):
    name: str
    email: str
    role: str

class Task(BaseModel):
    id: str
    title: str
    description: str
    priority: Priority
    status: TaskStatus
    assignee: Optional[Assignee] = None
    estimated_hours: int
    tags: List[str] = []

class ProjectPlan(BaseModel):
    project_name: str
    description: str
    start_date: str
    end_date: str
    tasks: List[Task]
    budget: int

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="""Create a project plan for developing a mobile app for a restaurant.
    Include at least 5 tasks with different priorities and assignees.
    The project should take 3 months and have a budget of $50,000.""",
    config={
        'response_mime_type': 'application/json',
        'response_schema': ProjectPlan,
    },
)

project = response.parsed
print(f"Project: {project.project_name}")
print(f"Tasks: {len(project.tasks)}")
for task in project.tasks:
    print(f"- {task.title} ({task.priority.value})")
```

### Advanced Patterns

#### Function Call Results with Structured Output

```python
from pydantic import BaseModel
from typing import List
import json

class WeatherData(BaseModel):
    temperature: float
    humidity: int
    condition: str
    wind_speed: float

class WeatherAnalysis(BaseModel):
    current_weather: WeatherData
    analysis: str
    recommendations: List[str]

# Simulate function call result
weather_function_result = {
    "temperature": 22.5,
    "humidity": 65,
    "condition": "partly cloudy",
    "wind_speed": 8.3
}

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"""
    Based on this weather data: {json.dumps(weather_function_result)}
    
    Provide an analysis and recommendations for outdoor activities.
    """,
    config={
        'response_mime_type': 'application/json',
        'response_schema': WeatherAnalysis,
    },
)

analysis = response.parsed
print(f"Temperature: {analysis.current_weather.temperature}°C")
print(f"Analysis: {analysis.analysis}")
print("Recommendations:")
for rec in analysis.recommendations:
    print(f"- {rec}")
```

#### Multi-Step Workflow with State Management

```python
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class ProcessingStage(Enum):
    INPUT_VALIDATION = "input_validation"
    DATA_EXTRACTION = "data_extraction"
    ANALYSIS = "analysis"
    REPORT_GENERATION = "report_generation"
    COMPLETE = "complete"

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []

class ExtractionResult(BaseModel):
    entities: List[str]
    key_phrases: List[str]
    sentiment_score: float

class AnalysisResult(BaseModel):
    summary: str
    insights: List[str]
    confidence_score: float

class WorkflowState(BaseModel):
    stage: ProcessingStage
    input_data: str
    validation: Optional[ValidationResult] = None
    extraction: Optional[ExtractionResult] = None
    analysis: Optional[AnalysisResult] = None
    final_report: Optional[str] = None

def process_workflow(input_text: str):
    client = genai.Client()
    state = WorkflowState(
        stage=ProcessingStage.INPUT_VALIDATION,
        input_data=input_text
    )
    
    # Step 1: Validation
    validation_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Validate this text for analysis: {input_text}",
        config={
            'response_mime_type': 'application/json',
            'response_schema': ValidationResult,
        },
    )
    state.validation = validation_response.parsed
    
    if not state.validation.is_valid:
        return state
    
    # Step 2: Extraction
    state.stage = ProcessingStage.DATA_EXTRACTION
    extraction_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Extract entities, key phrases, and sentiment from: {input_text}",
        config={
            'response_mime_type': 'application/json',
            'response_schema': ExtractionResult,
        },
    )
    state.extraction = extraction_response.parsed
    
    # Step 3: Analysis
    state.stage = ProcessingStage.ANALYSIS
    analysis_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"""
        Analyze this extracted data:
        Entities: {state.extraction.entities}
        Key Phrases: {state.extraction.key_phrases}
        Sentiment: {state.extraction.sentiment_score}
        """,
        config={
            'response_mime_type': 'application/json',
            'response_schema': AnalysisResult,
        },
    )
    state.analysis = analysis_response.parsed
    state.stage = ProcessingStage.COMPLETE
    
    return state

# Usage
result = process_workflow("The new product launch was incredibly successful, exceeding all expectations.")
print(f"Stage: {result.stage.value}")
print(f"Analysis: {result.analysis.summary if result.analysis else 'Not completed'}")
```

## Error Handling

### Common Error Patterns

```python
from google import genai
from google.genai.types import GenerateContentConfig
from pydantic import BaseModel, ValidationError
import json

class SafeResponse(BaseModel):
    success: bool
    data: dict = {}
    error_message: str = ""

def safe_structured_generation(prompt: str, schema_class: BaseModel, model: str = "gemini-2.5-flash"):
    """Wrapper for safe structured output generation with error handling"""
    client = genai.Client()
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=schema_class,
            ),
        )
        
        # Validate the response
        if hasattr(response, 'parsed'):
            return SafeResponse(success=True, data=response.parsed.dict())
        else:
            # Fallback to JSON parsing
            parsed_data = json.loads(response.text)
            validated_data = schema_class(**parsed_data)
            return SafeResponse(success=True, data=validated_data.dict())
            
    except ValidationError as e:
        return SafeResponse(
            success=False,
            error_message=f"Validation error: {str(e)}"
        )
    except json.JSONDecodeError as e:
        return SafeResponse(
            success=False,
            error_message=f"JSON parsing error: {str(e)}"
        )
    except Exception as e:
        return SafeResponse(
            success=False,
            error_message=f"Generation error: {str(e)}"
        )

# Usage with error handling
class ProductInfo(BaseModel):
    name: str
    price: float
    category: str

result = safe_structured_generation(
    "Tell me about the latest iPhone",
    ProductInfo
)

if result.success:
    print("Success:", result.data)
else:
    print("Error:", result.error_message)
```

### Retry Logic with Exponential Backoff

```python
import time
import random
from typing import Type, Optional

def structured_generation_with_retry(
    prompt: str,
    schema_class: Type[BaseModel],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    model: str = "gemini-2.5-flash"
) -> Optional[BaseModel]:
    """Generate structured output with retry logic"""
    
    client = genai.Client()
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=schema_class,
                ),
            )
            
            return response.parsed
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            
            delay = initial_delay * (backoff_factor ** attempt)
            jitter = random.uniform(0.1, 0.5)
            sleep_time = delay + jitter
            
            print(f"Attempt {attempt + 1} failed: {e}")
            print(f"Retrying in {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
    
    return None
```

## Best Practices

### 1. Schema Design

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import Enum

class OptimizedSchema(BaseModel):
    """Example of well-designed schema for structured output"""
    
    # Use descriptive field names
    product_name: str = Field(..., description="Name of the product")
    
    # Provide constraints and validation
    price: float = Field(..., gt=0, description="Product price in USD")
    
    # Use enums for constrained choices
    category: str = Field(..., description="Product category")
    
    # Make optional fields truly optional
    description: Optional[str] = Field(None, max_length=500)
    
    # Use lists sparingly and with limits
    tags: List[str] = Field(default=[], max_items=10)
    
    @validator('tags')
    def validate_tags(cls, v):
        return [tag.strip().lower() for tag in v if tag.strip()]
    
    class Config:
        # Provide examples for better model understanding
        schema_extra = {
            "example": {
                "product_name": "Wireless Headphones",
                "price": 199.99,
                "category": "Electronics",
                "description": "High-quality wireless headphones with noise cancellation",
                "tags": ["wireless", "audio", "premium"]
            }
        }
```

### 2. Prompt Engineering for Structured Output

```python
def create_structured_prompt(task_description: str, schema_class: BaseModel, examples: List[dict] = None) -> str:
    """Create optimized prompts for structured output"""
    
    prompt = f"""
Task: {task_description}

Output Requirements:
- Respond ONLY with valid JSON
- Follow the exact schema structure
- Include all required fields
- Use appropriate data types

Schema Structure:
{schema_class.schema_json(indent=2)}
"""
    
    if examples:
        prompt += "\n\nExamples:\n"
        for i, example in enumerate(examples, 1):
            prompt += f"\nExample {i}:\n{json.dumps(example, indent=2)}\n"
    
    prompt += "\n\nYour response:"
    
    return prompt

# Usage
class EmailClassification(BaseModel):
    category: str
    urgency_level: int = Field(..., ge=1, le=5)
    action_required: bool
    summary: str

prompt = create_structured_prompt(
    "Classify this email and determine required actions",
    EmailClassification,
    examples=[
        {
            "category": "customer_support",
            "urgency_level": 3,
            "action_required": True,
            "summary": "Customer reporting billing issue"
        }
    ]
)
```

### 3. Performance Optimization

```python
class OptimizedStructuredClient:
    """Optimized client for structured output operations"""
    
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model = model
        self.schema_cache = {}
    
    def generate_with_schema(
        self,
        prompt: str,
        schema_class: Type[BaseModel],
        temperature: float = 0.3,
        cache_schema: bool = True
    ) -> BaseModel:
        """Generate structured output with optimized settings"""
        
        # Use lower temperature for more consistent structured output
        config = GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=schema_class,
            temperature=temperature,
            max_output_tokens=2048,  # Reasonable limit for structured output
        )
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        
        return response.parsed
    
    def batch_generate(
        self,
        prompts: List[str],
        schema_class: Type[BaseModel]
    ) -> List[BaseModel]:
        """Process multiple prompts efficiently"""
        results = []
        
        for prompt in prompts:
            try:
                result = self.generate_with_schema(prompt, schema_class)
                results.append(result)
            except Exception as e:
                print(f"Error processing prompt: {e}")
                results.append(None)
        
        return results

# Usage
client = OptimizedStructuredClient()
results = client.batch_generate(
    ["Analyze sentiment of: Great product!", "Analyze sentiment of: Terrible service"],
    SentimentAnalysis
)
```

### 4. Testing Strategies

```python
import pytest
from pydantic import BaseModel
from typing import List

class TestStructuredOutput:
    """Test suite for structured output functionality"""
    
    @pytest.fixture
    def client(self):
        return genai.Client()
    
    def test_simple_schema_validation(self, client):
        """Test basic schema validation"""
        
        class SimpleResponse(BaseModel):
            answer: str
            confidence: float
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="What is 2+2? Rate your confidence 0-1.",
            config={
                'response_mime_type': 'application/json',
                'response_schema': SimpleResponse,
            },
        )
        
        assert hasattr(response, 'parsed')
        assert isinstance(response.parsed.answer, str)
        assert 0 <= response.parsed.confidence <= 1
    
    def test_enum_constraints(self, client):
        """Test enum constraint enforcement"""
        
        class Color(Enum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="What color is the sky?",
            config={
                'response_mime_type': 'text/x.enum',
                'response_schema': Color,
            },
        )
        
        assert response.text in [color.value for color in Color]
    
    def test_complex_nested_structure(self, client):
        """Test complex nested structures"""
        
        class Address(BaseModel):
            street: str
            city: str
            country: str
        
        class Person(BaseModel):
            name: str
            age: int
            address: Address
            hobbies: List[str]
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Create a person profile for John Smith, age 30, living in New York.",
            config={
                'response_mime_type': 'application/json',
                'response_schema': Person,
            },
        )
        
        person = response.parsed
        assert person.name
        assert person.age > 0
        assert person.address.city
        assert isinstance(person.hobbies, list)

# Run tests
# pytest test_structured_output.py -v
```

## Limitations and Considerations

### 1. Schema Complexity Limitations

**Problem**: Complex schemas can result in `InvalidArgument: 400` errors.

**Causes**:
- Long property names
- Extensive array length limits
- Enums with many values
- Objects with numerous optional properties
- Deep nesting levels

**Solutions**:
```python
# ❌ Problematic schema
class ProblematicSchema(BaseModel):
    very_long_property_name_that_exceeds_reasonable_limits: str
    huge_enum_field: Literal[
        "option1", "option2", "option3", ..., "option100"  # Too many options
    ]
    deeply_nested_object: Dict[str, Dict[str, Dict[str, str]]]  # Too deep
    
# ✅ Optimized schema
class OptimizedSchema(BaseModel):
    title: str
    category: Literal["A", "B", "C"]  # Limit enum options
    metadata: Dict[str, str]  # Flatten structure
```

### 2. Token Limit Impact

**Issue**: Response schema size counts toward input token limits.

**Best Practices**:
```python
# ❌ Wasteful token usage
class VerboseSchema(BaseModel):
    """This is a very detailed description of what this schema does and how to use it..."""
    field_with_long_description: str = Field(..., description="This field contains...")
    
# ✅ Token-efficient schema
class EfficientSchema(BaseModel):
    title: str
    content: str = Field(..., max_length=1000)
```

### 3. Performance Considerations

**Benchmarks** (based on community testing):
- **Unstructured output**: ~97% accuracy on complex tasks
- **Structured output**: ~86% accuracy on same tasks
- **Performance trade-off**: Structure reliability vs. raw performance

**Mitigation Strategies**:
```python
# Use appropriate temperature settings
config = GenerateContentConfig(
    response_mime_type='application/json',
    response_schema=schema_class,
    temperature=0.1,  # Lower temperature for better structure adherence
)
```

### 4. Model-Specific Issues

**Gemini 2.0 Flash Known Issues**:
- Value repetition until token limit reached
- Missing required fields in some cases
- Key ordering not preserved in Python SDK

**Workarounds**:
```python
def validate_and_retry(response, schema_class, max_retries=2):
    """Validate response and retry if needed"""
    for attempt in range(max_retries):
        try:
            if hasattr(response, 'parsed'):
                return response.parsed
            else:
                # Manual validation
                data = json.loads(response.text)
                return schema_class(**data)
        except Exception as e:
            if attempt < max_retries - 1:
                # Retry with different temperature or prompt
                continue
            raise e
```

### 5. Property Ordering Issues

**Problem**: Key order not preserved, breaking chain-of-thought reasoning.

**Solution**:
```python
from google.genai.types import Schema

# Use manual schema definition with property_ordering
manual_schema = Schema(
    type="OBJECT",
    properties={
        "reasoning": Schema(type="STRING"),
        "answer": Schema(type="STRING"),
    },
    property_ordering=["reasoning", "answer"],  # Explicit ordering
    required=["reasoning", "answer"]
)
```

### 6. Recursive Reference Limitations

**Constraints**:
- Only allowed as values of non-required object properties
- Unrolled to finite depth based on schema size

**Example**:
```python
# ❌ Invalid recursive reference
class InvalidNode(BaseModel):
    value: str
    child: Optional['InvalidNode']  # Required recursive reference not allowed

# ✅ Valid recursive reference  
class ValidNode(BaseModel):
    value: str
    children: Optional[List['ValidNode']] = None  # Optional recursive reference
```

### 7. Regional Availability

**Limitation**: Gemini 1.5 models not available in new projects without prior usage after April 29, 2025.

**Alternatives**:
- Use Gemini 2.5 Flash or Pro models
- Request access through Google Cloud console
- Migrate existing projects with usage history

## Troubleshooting Guide

### Common Issues and Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **Schema Too Complex** | `InvalidArgument: 400` error | Simplify schema, reduce nesting, limit enum values |
| **Token Limit Exceeded** | Truncated responses | Reduce schema size, use shorter field names |
| **Invalid JSON Response** | JSON parsing errors | Lower temperature, improve prompt clarity |
| **Missing Required Fields** | Validation errors | Add field descriptions, provide examples |
| **Inconsistent Output** | Variable response structure | Use stricter schema, add constraints |
| **Performance Degradation** | Slow response times | Use Gemini 2.5 Flash, optimize schema |

### Debugging Techniques

```python
def debug_structured_output(prompt: str, schema_class: BaseModel):
    """Debug helper for structured output issues"""
    client = genai.Client()
    
    print("=== DEBUGGING STRUCTURED OUTPUT ===")
    print(f"Prompt length: {len(prompt)} characters")
    print(f"Schema: {schema_class.__name__}")
    
    # Check schema JSON representation
    try:
        schema_json = schema_class.schema_json(indent=2)
        print(f"Schema JSON size: {len(schema_json)} characters")
        print("Schema structure:")
        print(schema_json[:500] + "..." if len(schema_json) > 500 else schema_json)
    except Exception as e:
        print(f"Schema serialization error: {e}")
        return
    
    # Test generation
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': schema_class,
            },
        )
        
        print("\n=== RESPONSE ===")
        print(f"Response type: {type(response)}")
        print(f"Has parsed attribute: {hasattr(response, 'parsed')}")
        
        if hasattr(response, 'parsed'):
            print("Parsed successfully!")
            print(f"Parsed type: {type(response.parsed)}")
            print(f"Parsed data: {response.parsed}")
        else:
            print("Raw response text:")
            print(response.text)
            
    except Exception as e:
        print(f"\n=== ERROR ===")
        print(f"Error type: {type(e)}")
        print(f"Error message: {e}")

# Usage
class DebugSchema(BaseModel):
    name: str
    value: int

debug_structured_output("Create a test object", DebugSchema)
```

## Additional Resources

### Official Documentation
- [Gemini API Structured Output Guide](https://ai.google.dev/gemini-api/docs/structured-output)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [OpenAPI 3.0 Schema Specification](https://spec.openapis.org/oas/v3.0.3#schema-object)

### Community Resources
- [Gemini Cookbook - Structured Output Examples](https://github.com/google-gemini/cookbook)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

### GitHub Repositories
- [Gemini Fullstack LangGraph Quickstart](https://github.com/google-gemini/gemini-fullstack-langgraph-quickstart)
- [Google GenAI Python SDK](https://github.com/googleapis/python-genai)

### Support Channels
- [Google AI Community Forum](https://discuss.ai.google.dev/c/gemini-api/)
- [GitHub Issues for SDK](https://github.com/googleapis/python-genai/issues)
- [Google Cloud Support](https://cloud.google.com/support) (for Vertex AI)

---

*Documentation created on: August 28, 2025*  
*SDK Version: google-genai (latest)*  
*API Version: Gemini 2.5 Flash*