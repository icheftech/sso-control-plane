"""Kill Switches API Router

Provides REST endpoints for managing kill switches = critical safety controls
that can immediately halt or degrade system operations.

Add Phase 4: Critical Controls API

NIST AI RMF Mapping:
- GOVERN-1.2: Organizational governance structures  
- GOVERN-4.1: AI system operation constraints
- MANAGE-2.1: Risk-based decision making

Compliance:
- SOC 2 CC7.2: System monitoring and control
- ISO 27001: Incident response procedures
"""

from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.database import get_db
from ..db.models.kill_switch import KillSwitch, KillSwitchMode


router = APIRouter(prefix="/kill-switches", tags=["kill-switches"])


@router.get("/", response_model=List)
async def list_kill_switches(
    mode: Optional[KillSwitchMode] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List all kill switches with optional mode filtering.
    
    Kill switches are checked FIRST in enforcement gates.
    HARD_STOP blocks all operations. DEGRADE limits writes.
    
    CRITICAL: Test impact before activating production switches.
    """
    query = select(KillSwitch).where(KillSwitch.is_active == True)
    
    if mode:
        query = query.where(KillSwitch.mode == mode)
    
    query = query.order_by(KillSwitch.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_kill_switch(
    switch_data: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new kill switch.
    
    CRITICAL: Document justification for new switches.
    Requires approval for production environments.
    """
    switch = KillSwitch(**switch_data)
    db.add(switch)
    await db.commit()
    await db.refresh(switch)
    return switch


@router.get("/{switch_id}")
async def get_kill_switch(
    switch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific kill switch by ID.
    """
    result = await db.execute(
        select(KillSwitch).where(KillSwitch.id == switch_id)
    )
    switch = result.scalars().first()
    
    if not switch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kill switch {switch_id} not found",
        )
    
    return switch


@router.put("/{switch_id}")
async def update_kill_switch(
    switch_id: UUID,
    update_data: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Update kill switch configuration.
    
    Mode changes (HARD_STOP/DEGRADE) require testing.
    """
    result = await db.execute(
        select(KillSwitch).where(KillSwitch.id == switch_id)
    )
    switch = result.scalars().first()
    
    if not switch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kill switch {switch_id} not found",
        )
    
    # Update fields
    for field, value in update_data.items():
        setattr(switch, field, value)
    
    await db.commit()
    await db.refresh(switch)
    
    return switch


@router.delete("/{switch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_kill_switch(
    switch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate a kill switch (soft delete).
    
    Deactivated switches are no longer evaluated during
    enforcement gate checks.
    
    CRITICAL: Document reason for deactivation.
    """
    result = await db.execute(
        select(KillSwitch).where(KillSwitch.id == switch_id)
    )
    switch = result.scalars().first()
    
    if not switch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kill switch {switch_id} not found",
        )
    
    switch.is_active = False
    await db.commit()
    
    return None


@router.post("/{switch_id}/activate", status_code=status.HTTP_200_OK)
async def activate_kill_switch(
    switch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Activate a kill switch.
    
    CRITICAL: Activating a HARD_STOP switch will block ALL operations.
    Ensure proper communication before activation.
    """
    result = await db.execute(
        select(KillSwitch).where(KillSwitch.id == switch_id)
    )
    switch = result.scalars().first()
    
    if not switch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kill switch {switch_id} not found",
        )
    
    switch.is_active = True
    await db.commit()
    await db.refresh(switch)
    
    return switch
