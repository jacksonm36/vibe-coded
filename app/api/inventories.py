from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/api/inventories", tags=["inventories"])


@router.get("", response_model=list[schemas.InventoryRead])
def list_inventories(project_id: int | None = None, db: Session = Depends(get_db)):
    if project_id is not None:
        return list(crud.get_inventories_by_project(db, project_id))
    return []


@router.get("/{id}", response_model=schemas.InventoryRead)
def get_inventory(id: int, db: Session = Depends(get_db)):
    inv = crud.get_inventory(db, id)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inv


@router.post("", response_model=schemas.InventoryRead)
def create_inventory(data: schemas.InventoryCreate, db: Session = Depends(get_db)):
    if not crud.get_project(db, data.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return crud.create_inventory(db, data)


@router.patch("/{id}", response_model=schemas.InventoryRead)
def update_inventory(id: int, data: schemas.InventoryUpdate, db: Session = Depends(get_db)):
    inv = crud.update_inventory(db, id, data)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inv


@router.delete("/{id}", status_code=204)
def delete_inventory(id: int, db: Session = Depends(get_db)):
    if not crud.delete_inventory(db, id):
        raise HTTPException(status_code=404, detail="Inventory not found")
