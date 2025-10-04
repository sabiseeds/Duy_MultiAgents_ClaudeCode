"""
Pydantic models for the Multi-Agent Task Execution System.
Defines all data structures used across services.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCapability(str, Enum):
    """Agent specialization capabilities"""
    DATA_ANALYSIS = "data_analysis"
    WEB_SCRAPING = "web_scraping"
    CODE_GENERATION = "code_generation"
    FILE_PROCESSING = "file_processing"
    DATABASE_OPERATIONS = "database_operations"
    API_INTEGRATION = "api_integration"


class SubTask(BaseModel):
    """Individual unit of work within a task"""
    id: str = Field(default_factory=lambda: f"subtask_{uuid.uuid4().hex[:12]}")
    description: str = Field(..., min_length=10, max_length=1000)
    required_capabilities: List[AgentCapability] = Field(..., min_length=1)
    dependencies: List[str] = Field(default_factory=list)
    priority: int = Field(default=5, ge=0, le=10)
    estimated_duration: Optional[int] = Field(default=None, gt=0)
    input_data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('dependencies')
    @classmethod
    def validate_no_self_dependency(cls, v, info):
        """Ensure subtask doesn't depend on itself"""
        if hasattr(info, 'data') and info.data.get('id') in v:
            raise ValueError("Subtask cannot depend on itself")
        return v


class Task(BaseModel):
    """User-submitted work request"""
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:16]}")
    user_id: str = Field(default="default_user")
    description: str = Field(..., min_length=10, max_length=5000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.PENDING
    subtasks: Optional[List[SubTask]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @field_validator('updated_at')
    @classmethod
    def validate_updated_after_created(cls, v, info):
        """Ensure updated_at >= created_at"""
        if hasattr(info, 'data') and info.data.get('created_at'):
            created = info.data['created_at']
            if v < created:
                raise ValueError("updated_at must be >= created_at")
        return v


class SubTaskResult(BaseModel):
    """Output from completed subtask execution"""
    task_id: str
    subtask_id: str
    agent_id: str
    status: TaskStatus
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = Field(..., gt=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('output')
    @classmethod
    def validate_completed_has_output(cls, v, info):
        """If status is completed, output must be non-null"""
        if hasattr(info, 'data'):
            status = info.data.get('status')
            if status == TaskStatus.COMPLETED and v is None:
                raise ValueError("Completed subtask must have output")
        return v

    @field_validator('error')
    @classmethod
    def validate_failed_has_error(cls, v, info):
        """If status is failed, error must be non-null"""
        if hasattr(info, 'data'):
            status = info.data.get('status')
            if status == TaskStatus.FAILED and v is None:
                raise ValueError("Failed subtask must have error message")
        return v


class AgentStatus(BaseModel):
    """Agent health and availability status"""
    agent_id: str
    port: int = Field(..., ge=8001, le=8005)
    is_available: bool = True
    current_task: Optional[str] = None
    capabilities: List[AgentCapability] = Field(..., min_length=1)
    cpu_usage: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_usage: float = Field(default=0.0, ge=0.0, le=100.0)
    tasks_completed: int = Field(default=0, ge=0)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)


class TaskExecutionRequest(BaseModel):
    """Request to execute a subtask on an agent"""
    task_id: str
    subtask: SubTask
    task_context: Dict[str, Any] = Field(default_factory=dict)


class AdministrativeDivision(BaseModel):
    """Administrative division data model for geographical entities"""
    id: str = Field(..., description="Unique identifier for the division")
    name: str = Field(..., min_length=1, max_length=255, description="Official name of the division")
    name_local: Optional[str] = Field(None, max_length=255, description="Local language name")
    type: str = Field(..., description="Type of division (country, state, province, city, etc.)")
    iso_code: Optional[str] = Field(None, max_length=10, description="ISO code if applicable")
    parent_id: Optional[str] = Field(None, description="Parent division ID for hierarchical structure")
    level: int = Field(..., ge=0, le=10, description="Administrative level (0=country, 1=state, etc.)")
    population: Optional[int] = Field(None, ge=0, description="Population count")
    area_km2: Optional[float] = Field(None, ge=0, description="Area in square kilometers")
    capital: Optional[str] = Field(None, max_length=255, description="Capital city if applicable")
    timezone: Optional[str] = Field(None, max_length=50, description="Primary timezone")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude coordinate")
    bbox_north: Optional[float] = Field(None, ge=-90, le=90, description="Bounding box north")
    bbox_south: Optional[float] = Field(None, ge=-90, le=90, description="Bounding box south")
    bbox_east: Optional[float] = Field(None, ge=-180, le=180, description="Bounding box east")
    bbox_west: Optional[float] = Field(None, ge=-180, le=180, description="Bounding box west")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DivisionQueryRequest(BaseModel):
    """Request for querying administrative divisions"""
    query_type: str = Field(..., description="Type of query (by_name, by_code, by_parent, by_level, nearby)")
    search_term: Optional[str] = Field(None, description="Search term for name-based queries")
    iso_code: Optional[str] = Field(None, description="ISO code for code-based queries")
    parent_id: Optional[str] = Field(None, description="Parent ID for hierarchical queries")
    level: Optional[int] = Field(None, ge=0, le=10, description="Administrative level filter")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude for proximity queries")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude for proximity queries")
    radius_km: Optional[float] = Field(None, gt=0, description="Search radius in kilometers")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of results")


class DivisionQueryResult(BaseModel):
    """Result of administrative division query"""
    divisions: List[AdministrativeDivision]
    total_count: int = Field(..., ge=0, description="Total number of matching divisions")
    query_time_ms: float = Field(..., gt=0, description="Query execution time in milliseconds")
    source: str = Field(..., description="Data source (database, api, cache)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Query metadata")
