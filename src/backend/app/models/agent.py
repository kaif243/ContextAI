"""Agent models for agentic AI feature."""

from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, JSON, ForeignKey, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AgentTask(BaseModel):
    """Agent task model for tracking agentic AI tasks."""

    __tablename__ = "agent_tasks"
    __table_args__ = (Index("ix_task_status", "status"), Index("ix_task_created", "created_at"))

    # Task info
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Task content
    request: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending, running, completed, failed, cancelled

    # Results
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Progress
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Approval
    approval_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    approval_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # pending, approved, rejected
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    steps: Mapped[list["AgentStep"]] = relationship(
        "AgentStep", back_populates="task", cascade="all, delete-orphan", order_by="AgentStep.step_number"
    )

    def __repr__(self) -> str:
        return f"<AgentTask(id={self.id}, status={self.status}, request={self.request[:50]})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "status": self.status,
            "request": self.request,
            "plan": self.plan,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "approval_required": self.approval_required,
            "approval_status": self.approval_status,
            "steps": [step.to_dict() for step in self.steps] if self.steps else [],
        }


class AgentStep(BaseModel):
    """Agent step model for tracking individual agent steps."""

    __tablename__ = "agent_steps"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Step info
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending, running, completed, failed

    # Input/Output
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Error handling
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Approval
    requires_approval: Mapped[bool] = mapped_column(default=False, nullable=False)
    approval_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # pending, approved, rejected

    # Relationships
    task: Mapped["AgentTask"] = relationship("AgentTask", back_populates="steps")

    def __repr__(self) -> str:
        return f"<AgentStep(id={self.id}, task_id={self.task_id}, action={self.action}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "step_number": self.step_number,
            "action": self.action,
            "tool": self.tool,
            "status": self.status,
            "input": self.input_data,
            "output": self.output_data,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
