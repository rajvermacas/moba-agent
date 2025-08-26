# Important points to be always loaded in context
- Use context7 mcp tool extensively.
- Use sub agents extensively whenever possible to get the task done in a separate context.
- moba_agent has LLM and MCP integrations
- moba_server has rest server api endpoints
- This project is a backend whereas frontend is located at /root/projects/moba/moba-ui/

# Full Application Architecture - The Big Picture
- A react chatbot on the UI talks to
- A python fastapi backend (this project) talks to 
    - Multiple MCP servers to get their resources and tools
    - And there is a Google Gemini LLM 2.5 flash