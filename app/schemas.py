"""Pydantic schemas for API."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CredentialKind(str, Enum):
    ssh = "ssh"
    vault = "vault"
    password = "password"
    git = "git"


# Project
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    git_url: Optional[str] = Field(None, max_length=512)
    git_branch: Optional[str] = Field(None, max_length=64)
    git_credential_id: Optional[int] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    git_url: Optional[str] = Field(None, max_length=512)
    git_branch: Optional[str] = Field(None, max_length=64)
    git_credential_id: Optional[int] = None


class ProjectRead(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Inventory
class InventoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    content: str = ""


class InventoryCreate(InventoryBase):
    project_id: int


class InventoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    content: Optional[str] = None


class InventoryRead(InventoryBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Credential (never return secret in read)
# kind: ssh = SSH key, password = SSH password, vault = Ansible vault, git = Git HTTPS token
class CredentialBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: CredentialKind = CredentialKind.ssh
    extra: str = ""


class CredentialCreate(CredentialBase):
    project_id: int
    secret: str  # plaintext; server encrypts before storing


class CredentialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    kind: Optional[CredentialKind] = None
    extra: Optional[str] = None
    secret: Optional[str] = None


class CredentialRead(CredentialBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Job template
class JobTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    playbook_path: str = Field(..., min_length=1, max_length=512)
    inventory_id: Optional[int] = None
    credential_id: Optional[int] = None
    extra_vars: str = ""


class JobTemplateCreate(JobTemplateBase):
    project_id: int


class JobTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    playbook_path: Optional[str] = Field(None, min_length=1, max_length=512)
    inventory_id: Optional[int] = None
    credential_id: Optional[int] = None
    extra_vars: Optional[str] = None


class JobTemplateRead(JobTemplateBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Job
class JobLaunch(BaseModel):
    job_template_id: int
    extra_vars_override: str = ""


class JobRead(BaseModel):
    id: int
    project_id: int
    job_template_id: Optional[int]
    status: str
    playbook_path: str
    extra_vars: str
    output_log: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class JobListSummary(BaseModel):
    id: int
    project_id: int
    job_template_id: Optional[int]
    status: str
    playbook_path: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
