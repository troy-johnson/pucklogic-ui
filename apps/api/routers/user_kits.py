from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user, get_db
from models.schemas import UserKitCreate, UserKitOut

router = APIRouter(prefix="/user-kits", tags=["user-kits"])


@router.get("", response_model=list[UserKitOut])
async def list_user_kits(
    user: dict[str, Any] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> list[UserKitOut]:
    """Return all saved weight kits belonging to the authenticated user."""
    result = (
        db.table("user_kits")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return [UserKitOut(**row) for row in result.data]


@router.post("", response_model=UserKitOut, status_code=201)
async def create_user_kit(
    kit: UserKitCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> UserKitOut:
    """Save a new named weight configuration for the authenticated user."""
    result = (
        db.table("user_kits")
        .insert(
            {
                "user_id": user["id"],
                "name": kit.name,
                "season": kit.season,
                "weights": kit.weights,
            }
        )
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create kit")
    return UserKitOut(**result.data[0])


@router.delete("/{kit_id}", status_code=204)
async def delete_user_kit(
    kit_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> None:
    """Delete a saved kit. Only the owning user may delete their own kits."""
    result = (
        db.table("user_kits")
        .delete()
        .eq("id", kit_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Kit not found")
