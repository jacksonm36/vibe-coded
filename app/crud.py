"""CRUD helpers using SQLAlchemy."""
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app import models, schemas, secrets as sec


def get_project(db: Session, id: int) -> Optional[models.Project]:
    return db.query(models.Project).filter(models.Project.id == id).first()


def get_projects(db: Session) -> Sequence[models.Project]:
    return db.query(models.Project).order_by(models.Project.name).all()


def create_project(db: Session, data: schemas.ProjectCreate) -> models.Project:
    p = models.Project(
        name=data.name,
        description=data.description or "",
        git_url=data.git_url or None,
        git_branch=data.git_branch or "main",
        git_credential_id=data.git_credential_id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def update_project(db: Session, id: int, data: schemas.ProjectUpdate) -> Optional[models.Project]:
    p = get_project(db, id)
    if not p:
        return None
    if data.name is not None:
        p.name = data.name
    if data.description is not None:
        p.description = data.description
    if hasattr(data, "git_url") and data.git_url is not None:
        p.git_url = data.git_url or None
    if hasattr(data, "git_branch") and data.git_branch is not None:
        p.git_branch = data.git_branch or "main"
    if hasattr(data, "git_credential_id"):
        p.git_credential_id = data.git_credential_id
    db.commit()
    db.refresh(p)
    return p


def delete_project(db: Session, id: int) -> bool:
    p = get_project(db, id)
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


# Inventories
def get_inventory(db: Session, id: int) -> Optional[models.Inventory]:
    return db.query(models.Inventory).filter(models.Inventory.id == id).first()


def get_inventories_by_project(db: Session, project_id: int) -> Sequence[models.Inventory]:
    return db.query(models.Inventory).filter(models.Inventory.project_id == project_id).order_by(models.Inventory.name).all()


def create_inventory(db: Session, data: schemas.InventoryCreate) -> models.Inventory:
    inv = models.Inventory(
        project_id=data.project_id,
        name=data.name,
        description=data.description or "",
        content=data.content or "",
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def update_inventory(db: Session, id: int, data: schemas.InventoryUpdate) -> Optional[models.Inventory]:
    inv = get_inventory(db, id)
    if not inv:
        return None
    if data.name is not None:
        inv.name = data.name
    if data.description is not None:
        inv.description = data.description
    if data.content is not None:
        inv.content = data.content
    db.commit()
    db.refresh(inv)
    return inv


def delete_inventory(db: Session, id: int) -> bool:
    inv = get_inventory(db, id)
    if not inv:
        return False
    db.delete(inv)
    db.commit()
    return True


# Credentials
def get_credential(db: Session, id: int) -> Optional[models.Credential]:
    return db.query(models.Credential).filter(models.Credential.id == id).first()


def get_credentials_by_project(db: Session, project_id: int) -> Sequence[models.Credential]:
    return db.query(models.Credential).filter(models.Credential.project_id == project_id).order_by(models.Credential.name).all()


def create_credential(db: Session, data: schemas.CredentialCreate) -> models.Credential:
    enc = sec.encrypt_secret(data.secret) if data.secret else ""
    c = models.Credential(
        project_id=data.project_id,
        name=data.name,
        kind=data.kind,
        secret_encrypted=enc,
        extra=data.extra or "",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def update_credential(db: Session, id: int, data: schemas.CredentialUpdate) -> Optional[models.Credential]:
    c = get_credential(db, id)
    if not c:
        return None
    if data.name is not None:
        c.name = data.name
    if data.kind is not None:
        c.kind = data.kind
    if data.extra is not None:
        c.extra = data.extra
    if data.secret is not None:
        c.secret_encrypted = sec.encrypt_secret(data.secret)
    db.commit()
    db.refresh(c)
    return c


def get_credential_secret(db: Session, id: int) -> Optional[str]:
    c = get_credential(db, id)
    if not c or not c.secret_encrypted:
        return None
    return sec.decrypt_secret(c.secret_encrypted)


def delete_credential(db: Session, id: int) -> bool:
    c = get_credential(db, id)
    if not c:
        return False
    db.delete(c)
    db.commit()
    return True


# Job templates
def get_job_template(db: Session, id: int) -> Optional[models.JobTemplate]:
    return db.query(models.JobTemplate).filter(models.JobTemplate.id == id).first()


def get_job_templates_by_project(db: Session, project_id: int) -> Sequence[models.JobTemplate]:
    return db.query(models.JobTemplate).filter(models.JobTemplate.project_id == project_id).order_by(models.JobTemplate.name).all()


def create_job_template(db: Session, data: schemas.JobTemplateCreate) -> models.JobTemplate:
    jt = models.JobTemplate(
        project_id=data.project_id,
        name=data.name,
        description=data.description or "",
        playbook_path=data.playbook_path,
        inventory_id=data.inventory_id,
        credential_id=data.credential_id,
        extra_vars=data.extra_vars or "",
    )
    db.add(jt)
    db.commit()
    db.refresh(jt)
    return jt


def update_job_template(db: Session, id: int, data: schemas.JobTemplateUpdate) -> Optional[models.JobTemplate]:
    jt = get_job_template(db, id)
    if not jt:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(jt, k, v)
    db.commit()
    db.refresh(jt)
    return jt


def delete_job_template(db: Session, id: int) -> bool:
    jt = get_job_template(db, id)
    if not jt:
        return False
    db.delete(jt)
    db.commit()
    return True


# Jobs
def get_job(db: Session, id: int) -> Optional[models.Job]:
    return db.query(models.Job).filter(models.Job.id == id).first()


def get_jobs_by_project(db: Session, project_id: int, limit: int = 100) -> Sequence[models.Job]:
    return db.query(models.Job).filter(models.Job.project_id == project_id).order_by(models.Job.created_at.desc()).limit(limit).all()


def get_recent_jobs(db: Session, limit: int = 50) -> Sequence[models.Job]:
    return db.query(models.Job).order_by(models.Job.created_at.desc()).limit(limit).all()


def create_job(
    db: Session,
    project_id: int,
    job_template_id: Optional[int],
    playbook_path: str,
    inventory_content: str,
    extra_vars: str,
    status: str = "pending",
) -> models.Job:
    j = models.Job(
        project_id=project_id,
        job_template_id=job_template_id,
        status=status,
        playbook_path=playbook_path,
        inventory_content=inventory_content,
        extra_vars=extra_vars or "",
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


def update_job_status(db: Session, id: int, status: str, output_log: str = None) -> Optional[models.Job]:
    j = get_job(db, id)
    if not j:
        return None
    j.status = status
    if output_log is not None:
        j.output_log = output_log
    from datetime import datetime, timezone
    if status == "running" and not j.started_at:
        j.started_at = datetime.now(timezone.utc)
    if status in ("success", "failed"):
        j.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(j)
    return j


def delete_job(db: Session, id: int) -> bool:
    j = get_job(db, id)
    if not j:
        return False
    db.delete(j)
    db.commit()
    return True
