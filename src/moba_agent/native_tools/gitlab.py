"""GitLab issue creation tool for MOBA Agent."""

from urllib.parse import urlparse
from typing import Dict, Any, Optional, Type
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
    
    # Override class fields
    name: str = "create_gitlab_issue"
    description: str = "Create a new issue in a GitLab project"
    args_schema: Type[BaseModel] = GitLabIssueParams
    
    # GitLab-specific fields (inherited from NativeTool)
    access_token: str = Field(..., exclude=True)
    logger: Any = Field(..., exclude=True)
    
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
        # Run synchronous gitlab operation in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, gl_project.issues.create, issue_data)
    
    def _run(
        self,
        project_url: str,
        title: str,
        description: str,
        labels: Optional[list] = None,
        assignee: Optional[str] = None,
        milestone: Optional[str] = None
    ) -> str:
        """
        Synchronous execution (required by BaseTool but not preferred).
        Delegates to async version.
        """
        # For sync execution, we need to run the async version
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If there's already a running loop, we can't use run_until_complete
                raise RuntimeError("Cannot run sync version in an async context. Use the async version instead.")
            return loop.run_until_complete(
                self._arun(
                    project_url=project_url,
                    title=title,
                    description=description,
                    labels=labels,
                    assignee=assignee,
                    milestone=milestone
                )
            )
        except RuntimeError:
            # Fallback for when we can't run async
            raise NotImplementedError("This tool requires async execution. Use the async version.")
    
    async def _arun(
        self,
        project_url: str,
        title: str,
        description: str,
        labels: Optional[list] = None,
        assignee: Optional[str] = None,
        milestone: Optional[str] = None
    ) -> str:
        """
        Create a GitLab issue asynchronously.
        
        Args:
            project_url: Full GitLab project URL
            title: Issue title
            description: Issue description  
            labels: Optional list of labels
            assignee: Optional assignee username
            milestone: Optional milestone title
            
        Returns:
            The URL of the created issue
            
        Raises:
            Exception: If issue creation fails
        """
        try:
            # Extract GitLab instance URL and project path
            parsed = urlparse(project_url)
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
                'title': title,
                'description': description
            }
            
            # Add optional fields
            if labels:
                issue_data['labels'] = labels
            if assignee:
                issue_data['assignee_id'] = assignee
            if milestone:
                issue_data['milestone_id'] = milestone
            
            # Create issue with retry
            self.logger.info(f"Creating GitLab issue: {title}")
            issue = await self._create_issue_with_retry(project, issue_data)
            
            issue_url = issue.web_url
            self.logger.info(f"Successfully created GitLab issue: {issue_url}")
            
            return issue_url
            
        except Exception as e:
            error_msg = f"Failed to create GitLab issue: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)