# GitLab Tool Integration Architecture

## Overview
This document outlines the architecture for integrating a native GitLab issue creation tool into the MOBA Agent alongside existing MCP tools.

## Architecture Decision Record

### Core Decisions

1. **Tool Type**: Native Python tool (not MCP)
2. **Integration Pattern**: Parallel lists alongside MCP tools
3. **Library**: `python-gitlab` (official, battle-tested)
4. **Configuration**: Environment variables for credentials, constants for defaults

## System Architecture

### Tool Loading Strategy

```python
class Agent:
    def __init__(self):
        self.mcp_tools = []      # Tools from MCP server
        self.native_tools = []   # Native Python tools
        self.all_tools = []      # Combined list
    
    async def _load_tools(self):
        # Load MCP tools
        self.mcp_tools = await self.mcp_client.get_tools()
        
        # Load native tools
        self._load_native_tools()
        
        # Combine all tools
        self.all_tools = self.mcp_tools + self.native_tools
```

### File Structure

```
src/moba_agent/
├── agent.py              # Modified to load native tools
├── constants.py          # Configuration constants
└── tools/
    ├── __init__.py
    ├── base.py          # Base tool interface
    └── gitlab.py        # GitLab tool implementation
```

## GitLab Tool Implementation

### Environment Variables

```bash
# Only the access token is needed in environment
MOBA_GITLAB_TOKEN=glpat-xxxxxxxxxxxxx
```

### Constants Configuration

```python
# src/moba_agent/constants.py

# GitLab Test Configuration
GITLAB_DEFAULT_PROJECT_URL = "https://gitlab.com/your-org/test-project"  # For testing

# Retry Configuration
TOOL_MAX_RETRIES = 3
TOOL_INITIAL_DELAY = 1.0  # seconds
TOOL_MAX_DELAY = 30.0
TOOL_EXPONENTIAL_FACTOR = 2
```

### Base Tool Interface

Following LangGraph-inspired patterns:

```python
# src/moba_agent/tools/base.py
from pydantic import BaseModel
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

class NativeTool(ABC):
    """Base class for all native tools"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with given parameters.
        
        Returns:
            Dict with keys:
            - success: bool
            - result: Any (tool-specific result)
            - error: Optional[str] (error message if failed)
        """
        pass
```

### GitLab Tool Implementation

```python
# src/moba_agent/tools/gitlab.py
from urllib.parse import urlparse
from typing import Dict, Any, Optional
import gitlab
from pydantic import BaseModel, Field
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import NativeTool
from ..constants import (
    TOOL_MAX_RETRIES,
    TOOL_INITIAL_DELAY,
    TOOL_MAX_DELAY,
    TOOL_EXPONENTIAL_FACTOR
)

class GitLabIssueParams(BaseModel):
    """Parameters for creating a GitLab issue"""
    project_url: str = Field(description="Full GitLab project URL")
    title: str = Field(description="Issue title")
    description: str = Field(description="Issue description")
    labels: Optional[list] = Field(default=None, description="Issue labels")
    assignee: Optional[str] = Field(default=None, description="Assignee username")
    milestone: Optional[str] = Field(default=None, description="Milestone title")

class GitLabIssueTool(NativeTool):
    """Tool for creating GitLab issues"""
    
    def __init__(self, access_token: str, logger):
        super().__init__(
            name="create_gitlab_issue",
            description="Create a new issue in a GitLab project"
        )
        self.access_token = access_token
        self.logger = logger
        self.args_schema = GitLabIssueParams
    
    @retry(
        stop=stop_after_attempt(TOOL_MAX_RETRIES),
        wait=wait_exponential(
            multiplier=TOOL_EXPONENTIAL_FACTOR,
            min=TOOL_INITIAL_DELAY,
            max=TOOL_MAX_DELAY
        )
    )
    async def _create_issue_with_retry(self, gl_project, issue_data):
        """Create issue with retry logic"""
        return gl_project.issues.create(issue_data)
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a GitLab issue.
        
        Returns:
            Dict with keys:
            - success: bool
            - result: str (issue URL if successful)
            - error: str (error message if failed)
        """
        try:
            # Validate parameters
            validated_params = GitLabIssueParams(**params)
            
            # Extract GitLab instance URL and project path
            parsed = urlparse(validated_params.project_url)
            gitlab_url = f"{parsed.scheme}://{parsed.netloc}"
            project_path = parsed.path.strip("/")
            
            self.logger.debug(f"Creating issue in GitLab instance: {gitlab_url}")
            self.logger.debug(f"Project path: {project_path}")
            
            # Initialize GitLab client
            gl = gitlab.Gitlab(gitlab_url, private_token=self.access_token)
            
            # Get project
            project = gl.projects.get(project_path)
            
            # Prepare issue data
            issue_data = {
                'title': validated_params.title,
                'description': validated_params.description
            }
            
            # Add optional fields
            if validated_params.labels:
                issue_data['labels'] = validated_params.labels
            if validated_params.assignee:
                issue_data['assignee_id'] = validated_params.assignee
            if validated_params.milestone:
                issue_data['milestone_id'] = validated_params.milestone
            
            # Create issue with retry
            self.logger.info(f"Creating GitLab issue: {validated_params.title}")
            issue = await self._create_issue_with_retry(project, issue_data)
            
            issue_url = issue.web_url
            self.logger.info(f"Successfully created GitLab issue: {issue_url}")
            
            return {
                "success": True,
                "result": issue_url,
                "error": None
            }
            
        except Exception as e:
            error_msg = f"Failed to create GitLab issue: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "result": None,
                "error": error_msg
            }
```


## LangGraph Integration

### Converting Native Tools to LangChain Format

To work with LangGraph's `create_react_agent`, we need to wrap our native tools:

```python
# src/moba_agent/tools/langgraph_adapter.py
from langchain_core.tools import tool
from typing import Dict, Any
import asyncio

def create_langgraph_tool(native_tool):
    """Convert a native tool to LangGraph-compatible format"""
    
    @tool
    async def wrapped_tool(**kwargs) -> str:
        # Get the docstring from the native tool
        __doc__ = f"{native_tool.description}"
        
        # Execute using native tool's execute method
        result = await native_tool.execute(kwargs)
        
        if result["success"]:
            return result["result"]
        else:
            raise Exception(result["error"])
    
    # Set the proper name and description
    wrapped_tool.__name__ = native_tool.name
    wrapped_tool.name = native_tool.name
    wrapped_tool.description = native_tool.description
    
    # Add args_schema if available
    if hasattr(native_tool, 'args_schema'):
        wrapped_tool.args_schema = native_tool.args_schema
    
    return wrapped_tool
```

### Complete Agent Integration

The following shows all modifications needed to the Agent class to support native tools alongside MCP tools:

```python
# src/moba_agent/agent.py
import os
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from .tools.gitlab import GitLabIssueTool
from .tools.langgraph_adapter import create_langgraph_tool
from .constants import GITLAB_DEFAULT_PROJECT_URL

class Agent:
    def __init__(self):
        """Initialize agent with empty tool lists"""
        # MODIFICATION 1: Add separate lists for MCP and native tools
        # Why: Allows tracking of different tool types for proper handling
        self.mcp_tools = []      # Tools loaded from MCP server
        self.native_tools = []   # Native Python tools (e.g., GitLab)
        self.all_tools = []      # Combined list of all tools
        
        # ... existing initialization code ...
    
    async def _load_tools(self):
        """Load tools from MCP server and native tools"""
        self.logger.debug("Loading tools from MCP server")
        
        try:
            # EXISTING CODE: Load MCP tools as before
            self.mcp_tools = await self.mcp_client.get_tools()
            tool_count = len(self.mcp_tools) if self.mcp_tools else 0
            self.logger.info(f"Loaded {tool_count} MCP tools")
            
            if self.mcp_tools:
                tool_names = [tool.name if hasattr(tool, 'name') else str(tool) 
                             for tool in self.mcp_tools]
                self.logger.debug(f"Available MCP tools: {tool_names}")
            
        except Exception as e:
            self.logger.error(f"Failed to load MCP tools: {e}")
            self.logger.warning("Continuing with no MCP tools")
            self.mcp_tools = []
        
        # MODIFICATION 2: Add native tools loading
        # Why: Loads GitLab and other native tools when environment is configured
        self._load_native_tools()
        
        # MODIFICATION 3: Combine all tools into single list
        # Why: Provides unified access to all tools regardless of type
        self.all_tools = self.mcp_tools + self.native_tools
        total_count = len(self.all_tools)
        self.logger.info(f"Total tools available: {total_count}")
    
    def _load_native_tools(self):
        """Load native Python tools based on environment configuration"""
        # NEW METHOD: Initializes native tools
        # Why: Separates native tool loading logic for maintainability
        self.native_tools = []
        
        # Load GitLab tool if token is available
        gitlab_token = os.getenv("MOBA_GITLAB_TOKEN")
        if gitlab_token:
            try:
                # Create GitLab tool instance with token from environment
                gitlab_tool = GitLabIssueTool(
                    access_token=gitlab_token,
                    logger=self.logger
                )
                self.native_tools.append(gitlab_tool)
                self.logger.info("Loaded GitLab issue creation tool")
            except Exception as e:
                self.logger.error(f"Failed to load GitLab tool: {e}")
        else:
            self.logger.debug("GitLab token not found, skipping GitLab tool")
        
        # Log summary of loaded native tools
        native_count = len(self.native_tools)
        self.logger.info(f"Loaded {native_count} native tools")
        
        if self.native_tools:
            tool_names = [tool.name for tool in self.native_tools]
            self.logger.debug(f"Available native tools: {tool_names}")
    
    def _prepare_tools_for_langgraph(self):
        """Convert all tools to LangGraph-compatible format"""
        # NEW METHOD: Prepares tools for LangGraph integration
        # Why: LangGraph requires tools in specific format (LangChain @tool decorator)
        langgraph_tools = []
        
        # Convert native tools to LangGraph format
        # Why: Native tools use custom execute() method, need wrapping for LangGraph
        for native_tool in self.native_tools:
            lg_tool = create_langgraph_tool(native_tool)
            langgraph_tools.append(lg_tool)
            self.logger.debug(f"Converted native tool: {native_tool.name}")
        
        # Add MCP tools directly (already compatible)
        # Why: MCP tools already implement required interface
        langgraph_tools.extend(self.mcp_tools)
        
        return langgraph_tools
    
    def create_langgraph_agent(self):
        """Create a LangGraph ReAct agent with all available tools"""
        # NEW METHOD: Creates LangGraph agent instance
        # Why: Provides standard ReAct agent with all tools integrated
        
        # Convert tools to LangGraph format
        langgraph_tools = self._prepare_tools_for_langgraph()
        
        # Create agent with all tools
        # Why: Pass tools list directly for simplicity, LangGraph handles internally
        agent = create_react_agent(
            model=self.llm,  # Your existing LLM instance
            tools=langgraph_tools  # Combined list of all tools
        )
        
        self.logger.info(f"Created LangGraph agent with {len(langgraph_tools)} tools")
        return agent
```

## Error Handling Strategy

Following LangGraph best practices:

1. **Structured Error Response**: All tools return standardized error format
2. **Automatic Retries**: Built into GitLab tool with exponential backoff
3. **Logging**: Comprehensive logging at all levels
4. **No Validation**: As requested, no pre-validation of project existence or permissions
5. **Error Propagation**: Errors returned to agent for decision making

## Testing Strategy

### Real Server Testing
- No mocking or simulation
- Uses actual GitLab server with provided credentials
- Default test project URL in constants file
- Real issues created during testing

### Test Configuration
```python
# During testing, can override project URL
test_params = {
    "project_url": GITLAB_DEFAULT_PROJECT_URL,  # From constants
    "title": "Test Issue",
    "description": "Test description"
}
```

## Future Extensibility

### Adding New Native Tools

1. Create new tool class inheriting from `NativeTool`
2. Implement `execute` method with standard response format
3. Add tool initialization in `_load_native_tools`
4. Tool automatically available in `self.all_tools`

### Tool Registration Pattern
Currently using explicit registration (Option A from our discussion):
- Simple and clear
- Easy to control which tools are loaded
- No magic or auto-discovery

## Dependencies

Add to `pyproject.toml`:
```toml
[tool.poetry.dependencies]
python-gitlab = "^4.4.0"
tenacity = "^8.2.3"
```

## Security Considerations

1. **Access Token**: Stored in environment variable, never in code
2. **Permissions**: Using `api` scope as decided
3. **No Caching**: No credential or project metadata caching
4. **Audit Trail**: All operations logged through existing logger

## Summary

This architecture provides:
- Clean separation between MCP and native tools
- Standardized tool interface following LangGraph patterns
- Robust error handling with retries
- Simple, explicit tool registration
- Real server testing capability
- Easy extensibility for future tools