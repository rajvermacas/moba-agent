# LangGraph Return Values and Output Control Guide

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition, create_react_agent
from langgraph.types import RetryPolicy
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from typing import Annotated

# =============================================================================
# WHAT agent.invoke() RETURNS
# =============================================================================

@tool
def calculator(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        result = eval(expression.replace("x", "*"))
        return f"Result: {result}"
    except Exception as e:
        raise Exception(f"Calculation failed: {expression}")

def agent_node(state: MessagesState):
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash").bind_tools([calculator])
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def create_basic_agent():
    retry_policy = RetryPolicy(max_attempts=3)
    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode([calculator]), retry_policy=retry_policy)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile()

# Example usage showing what is returned
def demonstrate_basic_return():
    agent = create_basic_agent()
    
    result = agent.invoke({
        "messages": [HumanMessage(content="What is 15 + 27?")]
    })
    
    print("=== FULL RESULT ===")
    print(f"Type: {type(result)}")
    print(f"Keys: {result.keys()}")
    print(f"Number of messages: {len(result['messages'])}")
    
    print("\n=== ALL MESSAGES ===")
    for i, msg in enumerate(result["messages"]):
        print(f"Message {i}: {type(msg).__name__} - {msg.content[:100]}")
    
    print("\n=== FINAL RESPONSE ===")
    final_response = result["messages"][-1].content
    print(final_response)
    
    return result

# =============================================================================
# METHOD 1: USING PREBUILT AGENT WITH response_format
# =============================================================================

class CalculationResponse(BaseModel):
    """Structured response for calculations"""
    question: str = Field(description="The original math question")
    calculation: str = Field(description="The calculation performed")
    answer: float = Field(description="The numeric answer")
    explanation: str = Field(description="Brief explanation of the solution")

def create_structured_agent_prebuilt():
    """Create agent that returns structured output using response_format"""
    agent = create_react_agent(
        model="gemini-2.5-flash",
        tools=[calculator],
        prompt="You are a helpful math assistant. Always show your work.",
        response_format=CalculationResponse  # This creates structured output!
    )
    return agent

def demonstrate_structured_prebuilt():
    agent = create_structured_agent_prebuilt()
    
    result = agent.invoke({
        "messages": [HumanMessage(content="What is 15 + 27?")]
    })
    
    print("=== STRUCTURED RESPONSE (Prebuilt) ===")
    print(f"Messages: {len(result['messages'])} messages")
    print(f"Final message: {result['messages'][-1].content}")
    
    # The structured response is accessible via 'structured_response' key
    if 'structured_response' in result:
        structured = result['structured_response']
        print(f"\nStructured Response Type: {type(structured)}")
        print(f"Question: {structured.question}")
        print(f"Calculation: {structured.calculation}")
        print(f"Answer: {structured.answer}")
        print(f"Explanation: {structured.explanation}")
    
    return result

# =============================================================================
# METHOD 2: CUSTOM STATE FOR STRUCTURED RESPONSES
# =============================================================================

class CustomAgentState(MessagesState):
    """Custom state that includes structured output field"""
    calculation_result: CalculationResponse = None
    final_answer: str = ""

def create_structured_agent_custom():
    """Create agent with custom state that includes structured fields"""
    
    def agent_node(state: CustomAgentState):
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash").bind_tools([calculator])
        response = llm.invoke(state["messages"])
        return {"messages": [response]}
    
    def format_response_node(state: CustomAgentState):
        """Final node that creates structured output"""
        messages = state["messages"]
        
        # Extract information from the conversation
        user_question = next((msg.content for msg in messages if hasattr(msg, 'content') and '?' in str(msg.content)), "Unknown question")
        
        # Find calculation result
        calc_result = None
        for msg in reversed(messages):
            if hasattr(msg, 'content') and 'Result:' in str(msg.content):
                try:
                    calc_result = float(msg.content.split('Result:')[1].strip())
                    break
                except:
                    pass
        
        # Create structured response
        structured_result = CalculationResponse(
            question=user_question,
            calculation="15 + 27",
            answer=calc_result if calc_result else 0.0,
            explanation=f"Added 15 and 27 to get {calc_result}"
        )
        
        return {
            "calculation_result": structured_result,
            "final_answer": f"The answer is {calc_result}"
        }
    
    def should_format_response(state: CustomAgentState):
        """Decide whether to format response or continue with tools"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # If the last message has tool calls, go to tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        
        # If we have a calculation result, format the response
        if any('Result:' in str(msg.content) for msg in messages if hasattr(msg, 'content')):
            return "format"
        
        return END
    
    # Build the graph
    builder = StateGraph(CustomAgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode([calculator]))
    builder.add_node("format", format_response_node)
    
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_format_response, {
        "tools": "tools",
        "format": "format",
        END: END
    })
    builder.add_edge("tools", "agent")
    builder.add_edge("format", END)
    
    return builder.compile()

def demonstrate_custom_structured():
    agent = create_structured_agent_custom()
    
    result = agent.invoke({
        "messages": [HumanMessage(content="What is 15 + 27?")]
    })
    
    print("=== CUSTOM STRUCTURED RESPONSE ===")
    print(f"Keys in result: {result.keys()}")
    print(f"Messages: {len(result['messages'])}")
    print(f"Final answer: {result.get('final_answer', 'N/A')}")
    
    if result.get('calculation_result'):
        calc = result['calculation_result']
        print(f"\nStructured Calculation Result:")
        print(f"  Question: {calc.question}")
        print(f"  Calculation: {calc.calculation}")
        print(f"  Answer: {calc.answer}")
        print(f"  Explanation: {calc.explanation}")
    
    return result

# =============================================================================
# METHOD 3: RETURN ONLY STRUCTURED DATA (No Messages)
# =============================================================================

class StructuredOnlyState(TypedDict):
    """State that only contains structured data, no messages"""
    input_query: str
    result: CalculationResponse

def create_structured_only_agent():
    """Agent that returns only structured data, no message history"""
    
    def process_query(state: StructuredOnlyState):
        # Use LLM to process the query
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash").bind_tools([calculator])
        
        # Create temporary messages for processing
        temp_messages = [HumanMessage(content=state["input_query"])]
        
        # Get initial response
        response = llm.invoke(temp_messages)
        temp_messages.append(response)
        
        # If there are tool calls, execute them
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_node = ToolNode([calculator])
            tool_result = tool_node.invoke({"messages": temp_messages})
            temp_messages.extend(tool_result["messages"])
            
            # Get final response
            final_response = llm.invoke(temp_messages)
            temp_messages.append(final_response)
        
        # Extract the calculation result
        calc_result = None
        for msg in temp_messages:
            if hasattr(msg, 'content') and 'Result:' in str(msg.content):
                try:
                    calc_result = float(msg.content.split('Result:')[1].strip())
                    break
                except:
                    pass
        
        # Return structured result only
        structured_result = CalculationResponse(
            question=state["input_query"],
            calculation="Mathematical calculation",
            answer=calc_result if calc_result else 0.0,
            explanation=f"Calculated result: {calc_result}"
        )
        
        return {"result": structured_result}
    
    builder = StateGraph(StructuredOnlyState)
    builder.add_node("process", process_query)
    builder.add_edge(START, "process")
    builder.add_edge("process", END)
    
    return builder.compile()

def demonstrate_structured_only():
    agent = create_structured_only_agent()
    
    result = agent.invoke({
        "input_query": "What is 15 + 27?"
    })
    
    print("=== STRUCTURED-ONLY RESPONSE ===")
    print(f"Keys in result: {result.keys()}")
    print(f"Input query: {result['input_query']}")
    
    calc_result = result['result']
    print(f"\nCalculation Result:")
    print(f"  Question: {calc_result.question}")
    print(f"  Answer: {calc_result.answer}")
    print(f"  Explanation: {calc_result.explanation}")
    
    return result

# =============================================================================
# EXAMPLES AND USAGE
# =============================================================================

if __name__ == "__main__":
    print("LangGraph Return Values and Output Control Examples")
    print("=" * 60)
    
    # Example 1: Basic agent (returns MessagesState)
    print("\n1. BASIC AGENT RETURN:")
    # demonstrate_basic_return()
    
    # Example 2: Prebuilt agent with structured output
    print("\n2. PREBUILT STRUCTURED AGENT:")
    # demonstrate_structured_prebuilt()
    
    # Example 3: Custom state with structured fields
    print("\n3. CUSTOM STRUCTURED STATE:")
    # demonstrate_custom_structured()
    
    # Example 4: Structured-only output (no messages)
    print("\n4. STRUCTURED-ONLY OUTPUT:")
    # demonstrate_structured_only()
    
    print("\nUncomment the demonstration functions to run examples!")