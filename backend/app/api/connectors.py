"""Connectors API Router

Provides REST endpoints for managing external system connectors.
Connectors enable secure integrations with external services while maintaining
credential management and connection lifecycle.

NIST AI RMF Mapping:
- MAP-1.2: External system dependency mapping
- GOVERN-5.1: Third-party risk management
- MANAGE-4.1: Integration security controls

Compliance:
- SOC 2 CC6.7: Third-party management
- ISO 27001: Supplier relationships
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models.connector import Connector, ConnectorType
from pydantic import BaseModel, Field


router = APIRouter(tags=["connectors"])


class ConnectorBase(BaseModel):
    """Base connector schema."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    connector_type: ConnectorType
    endpoint_url: str = Field(..., min_length=1)
    requires_auth: bool = True
    config: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class ConnectorCreate(ConnectorBase):
    """Schema for creating connectors."""
    # Credentials should NEVER be in response, only on create
    credentials: Optional[dict] = Field(None, description="Encrypted in DB")


class ConnectorUpdate(BaseModel):
    """Schema for updating connectors."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    endpoint_url: Optional[str] = None
    requires_auth: Optional[bool] = None
    config: Optional[dict] = None
    metadata: Optional[dict] = None
    credentials: Optional[dict] = Field(None, description="Encrypted in DB")


class ConnectorResponse(ConnectorBase):
    """Schema for connector responses (credentials excluded)."""
    id: UUID
    is_active: bool
    # Credentials intentionally excluded from response

    class Config:
        from_attributes = True


@router.get("/connectors", response_model=List[ConnectorResponse])
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    connector_type: Optional[ConnectorType] = None,
    requires_auth: Optional[bool] = None,
    search: Optional[str] = None,
    is_active: bool = True,
):
    """
    List all connectors with filtering.
    
    SECURITY: Credentials are never returned in list/get responses.
    """
    query = select(Connector).where(Connector.is_active == is_active)
    
    if connector_type:
        query = query.where(Connector.connector_type == connector_type)
    
    if requires_auth is not None:
        query = query.where(Connector.requires_auth == requires_auth)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Connector.name.ilike(search_pattern),
                Connector.description.ilike(search_pattern),
            )
        )
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    connectors = result.scalars().all()
    
    return connectors


@router.post("/connectors", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    connector_data: ConnectorCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new connector.
    
    SECURITY: Credentials are encrypted before storage.
    Never logged or exposed in responses.
    """
    # Check duplicate name
    existing = await db.execute(
        select(Connector).where(
            Connector.name == connector_data.name,
            Connector.is_active == True,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connector '{connector_data.name}' already exists",
        )
    
    connector = Connector(**connector_data.model_dump())
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    
    return connector


@router.get("/connectors/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve connector details (credentials excluded)."""
    result = await db.execute(
        select(Connector).where(Connector.id == connector_id)
    )
    connector = result.scalars().first()
    
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )
    
    return connector


@router.put("/connectors/{connector_id}", response_model=ConnectorResponse)
async def update_connector(
    connector_id: UUID,
    connector_data: ConnectorUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update connector configuration."""
    result = await db.execute(
        select(Connector).where(Connector.id == connector_id)
    )
    connector = result.scalars().first()
    
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )
    
    update_data = connector_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(connector, field, value)
    
    await db.commit()
    await db.refresh(connector)
    
    return connector


@router.delete("/connectors/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_connector(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate a connector (soft delete).
    
    CRITICAL: Verify no active workflows depend on this connector.
    Credentials remain encrypted in DB for audit trail.
    """
    result = await db.execute(
        select(Connector).where(Connector.id == connector_id)
    )
    connector = result.scalars().first()
    
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )
    
    connector.is_active = False
    await db.commit()
    
    return None
