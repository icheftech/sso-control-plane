"""Workflows API Router
CRUD operations for Workflow management (NIST MAP)
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.workflow import Workflow

# Create router
router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
)


@router.get("/", response_model=List[dict])
async def list_workflows(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all workflows with optional filtering."""
    query = db.query(Workflow)
    
    if is_active is not None:
        query = query.filter(Workflow.is_active == is_active)
    
    workflows = query.offset(skip).limit(limit).all()
    return [wf.to_dict() for wf in workflows]


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    name: str,
    description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new workflow."""
    workflow = Workflow(
        name=name,
        description=description,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow.to_dict()


@router.get("/{workflow_id}", response_model=dict)
async def get_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific workflow by ID."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )
    return workflow.to_dict()


@router.put("/{workflow_id}", response_model=dict)
async def update_workflow(
    workflow_id: UUID,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Update a workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )
    
    if name is not None:
        workflow.name = name
    if description is not None:
        workflow.description = description
    if is_active is not None:
        workflow.is_active = is_active
    
    db.commit()
    db.refresh(workflow)
    return workflow.to_dict()


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db)
):
    """Deactivate a workflow (soft delete)."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )
    
    workflow.is_active = False
    db.commit()
    return None
