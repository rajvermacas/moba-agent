# Constants for MOBA Agent project

# GitLab Configuration
GITLAB_DEFAULT_PROJECT_URL = "https://gitlab.com/your-org/test-project"  # Default project URL if not specified

# Retry Configuration for Tools
TOOL_MAX_RETRIES = 3
TOOL_INITIAL_DELAY = 1.0  # seconds
TOOL_MAX_DELAY = 30.0
TOOL_EXPONENTIAL_FACTOR = 2

# Tool Patterns
QUERY_TOOL_PATTERN = r"^execute_query_.*$"  # Pattern to identify database query tools from MCP servers

# Agent Configuration
AGENT_RECURSION_LIMIT = 15  # Maximum number of agent-tool cycles (prevents infinite loops)
AGENT_MAX_CONSECUTIVE_TOOL_ERRORS = 3  # Stop retrying after this many consecutive errors for the same tool