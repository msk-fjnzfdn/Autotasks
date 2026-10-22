from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, String, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime, timezone
from sqlalchemy.sql import func
from app.database import Base
import enum


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(str, enum.Enum):
    HTTP_REQUEST = "http_request"
    FILE_PROCESS = "file_process"
    DATABASE_QUERY = "database_query"
    CONDITION = "condition"
    NOTIFICATION = "notification"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

    chains = relationship("TaskChain", back_populates="owner")


class TaskChain(Base):
    __tablename__ = "task_chains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Text] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule: Mapped[str | None] = mapped_column(String, nullable=True)

    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="chains")

    nodes = relationship("TaskNode", back_populates="chain",
                         cascade="all, delete-orphan")
    runs = relationship("TaskRun", back_populates="chain")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        onupdate=func.now(), nullable=True)


class TaskNode(Base):
    __tablename__ = "task_nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_type = Column(Enum(NodeType), nullable=False)
    name = Column(String(100), nullable=False)
    config_json = Column(Text, nullable=True)

    chain_id = Column(Integer, ForeignKey(
        "task_chains.id", ondelete="CASCADE"), nullable=False)
    chain = relationship("TaskChain", back_populates="nodes")

    next_node_id = Column(Integer, ForeignKey("task_nodes.id"), nullable=True)
    next_node = relationship("TaskNode", remote_side=[id], uselist=False)

    order_index = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TaskRun(Base):
    __tablename__ = "task_runs"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    chain_id = Column(Integer, ForeignKey("task_chains.id"), nullable=False)
    chain = relationship("TaskChain", back_populates="runs")

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    chain_id: Mapped[int] = mapped_column(
        ForeignKey("task_chains.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)


class ChainRun(Base):
    __tablename__ = "chain_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    chain_id: Mapped[int] = mapped_column(
        ForeignKey("task_chains.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    logs: Mapped[list] = mapped_column(JSON, default=list)
