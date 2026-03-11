from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/api/job_templates", tags=["job_templates"])


@router.get("", response_model=list[schemas.JobTemplateRead])
def list_job_templates(project_id: int | None = None, db: Session = Depends(get_db)):
    if project_id is not None:
        return list(crud.get_job_templates_by_project(db, project_id))
    return []


@router.get("/{id}", response_model=schemas.JobTemplateRead)
def get_job_template(id: int, db: Session = Depends(get_db)):
    jt = crud.get_job_template(db, id)
    if not jt:
        raise HTTPException(status_code=404, detail="Job template not found")
    return jt


@router.post("", response_model=schemas.JobTemplateRead)
def create_job_template(data: schemas.JobTemplateCreate, db: Session = Depends(get_db)):
    if not crud.get_project(db, data.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if data.inventory_id and not crud.get_inventory(db, data.inventory_id):
        raise HTTPException(status_code=404, detail="Inventory not found")
    if data.credential_id and not crud.get_credential(db, data.credential_id):
        raise HTTPException(status_code=404, detail="Credential not found")
    return crud.create_job_template(db, data)


@router.patch("/{id}", response_model=schemas.JobTemplateRead)
def update_job_template(id: int, data: schemas.JobTemplateUpdate, db: Session = Depends(get_db)):
    jt = crud.update_job_template(db, id, data)
    if not jt:
        raise HTTPException(status_code=404, detail="Job template not found")
    return jt


@router.delete("/{id}", status_code=204)
def delete_job_template(id: int, db: Session = Depends(get_db)):
    if not crud.delete_job_template(db, id):
        raise HTTPException(status_code=404, detail="Job template not found")
