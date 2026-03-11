from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


@router.get("", response_model=list[schemas.CredentialRead])
def list_credentials(project_id: int | None = None, db: Session = Depends(get_db)):
    if project_id is not None:
        return list(crud.get_credentials_by_project(db, project_id))
    return []


@router.get("/{id}", response_model=schemas.CredentialRead)
def get_credential(id: int, db: Session = Depends(get_db)):
    c = crud.get_credential(db, id)
    if not c:
        raise HTTPException(status_code=404, detail="Credential not found")
    return c


@router.post("", response_model=schemas.CredentialRead)
def create_credential(data: schemas.CredentialCreate, db: Session = Depends(get_db)):
    if not crud.get_project(db, data.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return crud.create_credential(db, data)


@router.patch("/{id}", response_model=schemas.CredentialRead)
def update_credential(id: int, data: schemas.CredentialUpdate, db: Session = Depends(get_db)):
    c = crud.update_credential(db, id, data)
    if not c:
        raise HTTPException(status_code=404, detail="Credential not found")
    return c


@router.delete("/{id}", status_code=204)
def delete_credential(id: int, db: Session = Depends(get_db)):
    if not crud.delete_credential(db, id):
        raise HTTPException(status_code=404, detail="Credential not found")
