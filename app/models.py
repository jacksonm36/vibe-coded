"""SQLAlchemy models for Ansible UI."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    git_url = Column(String(512), nullable=True, index=False)  # Git/GitHub repo URL
    git_branch = Column(String(64), nullable=True, default="main")
    git_credential_id = Column(Integer, ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    inventories = relationship("Inventory", back_populates="project", cascade="all, delete-orphan")
    # Use project_id for "credentials belonging to this project"; git_credential_id is a separate FK
    credentials = relationship(
        "Credential",
        back_populates="project",
        cascade="all, delete-orphan",
        foreign_keys="[Credential.project_id]",
    )
    job_templates = relationship("JobTemplate", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")


class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    content = Column(Text, nullable=False, default="")  # INI or YAML inventory
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    project = relationship("Project", back_populates="inventories")


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    kind = Column(String(32), nullable=False, default="ssh")  # ssh, vault, password, git
    # Encrypted payload (key material or vault password)
    secret_encrypted = Column(Text, nullable=True)
    extra = Column(Text, default="")  # JSON: username, become, etc.
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    project = relationship(
        "Project",
        back_populates="credentials",
        foreign_keys="[Credential.project_id]",
    )


class JobTemplate(Base):
    __tablename__ = "job_templates"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    playbook_path = Column(String(512), nullable=False)  # path on server or relative to project
    inventory_id = Column(Integer, ForeignKey("inventories.id", ondelete="RESTRICT"), nullable=True, index=True)
    credential_id = Column(Integer, ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True, index=True)
    extra_vars = Column(Text, default="")  # YAML or JSON
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    project = relationship("Project", back_populates="job_templates")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    job_template_id = Column(Integer, ForeignKey("job_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="pending")  # pending, running, success, failed
    playbook_path = Column(String(512), nullable=False)
    inventory_content = Column(Text, default="")  # snapshot at run time
    extra_vars = Column(Text, default="")
    output_log = Column(Text, default="")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    project = relationship("Project", back_populates="jobs")
