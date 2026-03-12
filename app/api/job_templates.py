from datetime import datetime
from zoneinfo import ZoneInfo

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/api/job_templates", tags=["job_templates"])


def _next_run_iso(jt) -> str | None:
    if not jt.schedule_enabled or not (jt.schedule_cron or "").strip():
        return None
    try:
        tz_name = (jt.schedule_tz or "UTC").strip()
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    try:
        now_utc = datetime.utcnow()
        now_in_tz = now_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        now_naive = now_in_tz.replace(tzinfo=None)
        c = croniter(jt.schedule_cron.strip(), now_naive)
        next_run_naive = c.get_next(datetime)
        next_run_aware = next_run_naive.replace(tzinfo=tz)
        return next_run_aware.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


@router.get("", response_model=list[schemas.JobTemplateRead])
def list_job_templates(project_id: int | None = None, db: Session = Depends(get_db)):
    if project_id is not None:
        return list(crud.get_job_templates_by_project(db, project_id))
    return []


@router.get("/{id}/next_run")
def get_next_run(id: int, db: Session = Depends(get_db)):
    jt = crud.get_job_template(db, id)
    if not jt:
        raise HTTPException(status_code=404, detail="Job template not found")
    return {"next_run": _next_run_iso(jt)}


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
