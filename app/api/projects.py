import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas, git_support

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_to_read(p):
    """Build ProjectRead from ORM, ensuring optional fields are serializable."""
    return schemas.ProjectRead(
        id=p.id,
        name=p.name,
        description=p.description or "",
        git_url=p.git_url,
        git_branch=p.git_branch,
        git_credential_id=p.git_credential_id,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=list[schemas.ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    return [_project_to_read(p) for p in crud.get_projects(db)]


@router.get("/{id}", response_model=schemas.ProjectRead)
def get_project(id: int, db: Session = Depends(get_db)):
    p = crud.get_project(db, id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_read(p)


@router.post("", response_model=schemas.ProjectRead)
def create_project(data: schemas.ProjectCreate, db: Session = Depends(get_db)):
    try:
        p = crud.create_project(db, data)
        return _project_to_read(p)
    except Exception as e:
        logger.exception("create_project failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{id}", response_model=schemas.ProjectRead)
def update_project(id: int, data: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    try:
        p = crud.update_project(db, id, data)
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        return _project_to_read(p)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("update_project failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{id}", status_code=204)
def delete_project(id: int, db: Session = Depends(get_db)):
    if not crud.delete_project(db, id):
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{id}/pull")
def pull_project(id: int, db: Session = Depends(get_db)):
    """
    Pull (clone or update) the project's Git repo from GitHub/Git and return
    the list of playbook paths found in the repo.
    """
    p = crud.get_project(db, id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if not p.git_url or not p.git_url.strip():
        raise HTTPException(
            status_code=400,
            detail="Project has no Git URL. Set Git repo URL in project settings.",
        )
    ssh_key = None
    https_token = None
    if p.git_credential_id:
        cred = crud.get_credential(db, p.git_credential_id)
        if cred:
            secret = crud.get_credential_secret(db, p.git_credential_id)
            if cred.kind == "ssh" and secret:
                ssh_key = secret
            elif cred.kind == "git" and secret:
                https_token = secret
    try:
        repo_path = git_support.clone_or_pull(
            project_id=p.id,
            git_url=p.git_url,
            branch=p.git_branch or "main",
            ssh_private_key=ssh_key,
            https_token=https_token,
        )
        playbooks = git_support.list_playbooks_in_repo(repo_path)
        return {"ok": True, "message": "Pulled successfully.", "playbooks": playbooks}
    except Exception as e:
        logger.exception("pull_project failed")
        raise HTTPException(status_code=400, detail=f"Pull failed: {e}") from e
