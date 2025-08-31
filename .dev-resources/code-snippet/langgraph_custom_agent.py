from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import RetryPolicy

# Tool
@tool
def calculator(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        result = eval(expression.replace("x", "*"))
        return f"Result: {result}"
    except Exception as e:
        raise Exception(f"Calculation failed: {expression}")

# Agent node
def agent_node(state: MessagesState):
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash").bind_tools([calculator])
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# Create agent
def create_agent():
    # Retry 3 times for any error
    retry_policy = RetryPolicy(max_attempts=3)
    
    builder = StateGraph(MessagesState)
    
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode([calculator]), retry_policy=retry_policy)
    
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    
    return builder.compile()

# Usage
if __name__ == "__main__":
    agent = create_agent()
    
    result = agent.invoke({
        "messages": [HumanMessage(content="What is 15 + 27?")]
    })
    
    print(result["messages"][-1].content)