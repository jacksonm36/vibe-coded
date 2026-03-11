import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas, runners, git_support

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _resolve_playbook_path_and_credentials(db: Session, jt, inv_content: str, extra: str):
    """Resolve playbook path (Git sync if needed) and credential secrets for SSH/vault."""
    project = crud.get_project(db, jt.project_id)
    playbook_path = jt.playbook_path
    repo_path = None

    if project and project.git_url:
        ssh_key = None
        https_token = None
        if project.git_credential_id:
            cred = crud.get_credential(db, project.git_credential_id)
            if cred:
                secret = crud.get_credential_secret(db, project.git_credential_id)
                if cred.kind == "ssh" and secret:
                    ssh_key = secret
                elif cred.kind == "git" and secret:
                    https_token = secret
        try:
            repo_path = git_support.clone_or_pull(
                project_id=project.id,
                git_url=project.git_url,
                branch=project.git_branch or "main",
                ssh_private_key=ssh_key,
                https_token=https_token,
            )
            # Playbook path is relative to repo root.
            # Resolve to absolute path and verify it stays inside the repo.
            candidate = (repo_path / playbook_path.lstrip("/\\")).resolve()
            repo_abs = repo_path.resolve()
            if not candidate.is_relative_to(repo_abs):
                raise ValueError(
                    "Playbook path escapes the repository directory."
                )
            playbook_path = str(candidate)
        except Exception as e:
            raise RuntimeError(f"Git sync failed: {e}") from e

    if not os.path.isabs(playbook_path):
        playbook_path = os.path.abspath(playbook_path)

    ssh_key = None
    ssh_password = None
    vault_pass = None
    if jt.credential_id:
        cred = crud.get_credential(db, jt.credential_id)
        if cred:
            secret = crud.get_credential_secret(db, jt.credential_id)
            if cred.kind == "ssh" and secret:
                ssh_key = secret
            elif cred.kind == "password" and secret:
                ssh_password = secret
            elif cred.kind == "vault" and secret:
                vault_pass = secret

    return playbook_path, inv_content, extra, ssh_key, ssh_password, vault_pass


@router.get("", response_model=list[schemas.JobListSummary])
def list_jobs(project_id: int | None = None, limit: int = 100, db: Session = Depends(get_db)):
    if project_id is not None:
        return list(crud.get_jobs_by_project(db, project_id, limit=limit))
    return list(crud.get_recent_jobs(db, limit=limit))


@router.get("/{id}", response_model=schemas.JobRead)
def get_job(id: int, db: Session = Depends(get_db)):
    j = crud.get_job(db, id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    return j


@router.post("/launch", response_model=schemas.JobRead)
def launch_job(data: schemas.JobLaunch, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    jt = crud.get_job_template(db, data.job_template_id)
    if not jt:
        raise HTTPException(status_code=404, detail="Job template not found")
    inv_content = ""
    if jt.inventory_id:
        inv = crud.get_inventory(db, jt.inventory_id)
        inv_content = inv.content if inv else ""
    extra = data.extra_vars_override.strip() or (jt.extra_vars or "")

    try:
        playbook_path, inv_content, extra, ssh_key, ssh_password, vault_pass = _resolve_playbook_path_and_credentials(
            db, jt, inv_content, extra
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job = crud.create_job(
        db,
        project_id=jt.project_id,
        job_template_id=jt.id,
        playbook_path=playbook_path,
        inventory_content=inv_content,
        extra_vars=extra,
        status="pending",
    )

    def run():
        from app.database import SessionLocal
        db2 = SessionLocal()
        try:
            # Resolve path and credentials again in worker (Git sync, etc.)
            jt2 = crud.get_job_template(db2, jt.id)
            if not jt2:
                return
            inv_content2 = inv_content
            extra2 = extra
            try:
                playbook_path2, inv_content2, extra2, ssh_key2, ssh_password2, vault_pass2 = _resolve_playbook_path_and_credentials(
                    db2, jt2, inv_content2, extra2
                )
            except Exception as e:
                crud.update_job_status(db2, job.id, "failed", f"Setup failed: {e}")
                return
            runners.run_playbook(
                db2,
                job_id=job.id,
                playbook_path=playbook_path2,
                inventory_content=inv_content2,
                extra_vars=extra2,
                credential_ssh_key=ssh_key2,
                credential_ssh_password=ssh_password2,
                credential_vault_password=vault_pass2,
            )
        finally:
            db2.close()

    background_tasks.add_task(run)
    return job
