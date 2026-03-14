"""Clients router — POST /clients, GET /clients, DELETE /clients/{id}."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import clients as crud
from app.database.database import get_db
from app.database.schemas import ClientCreate, ClientResponse
from app.services.journal_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    client = await crud.create_client(db, data)
    await log_action(
        db,
        action="create_client",
        entity="client",
        entity_id=client.id,
        details=f"name={client.name}",
    )
    return ClientResponse.model_validate(client)


@router.get("", response_model=List[ClientResponse])
async def list_clients(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> List[ClientResponse]:
    clients = await crud.get_clients(db, skip=skip, limit=limit)
    return [ClientResponse.model_validate(c) for c in clients]


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await crud.delete_client(db, client_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    await log_action(
        db,
        action="delete_client",
        entity="client",
        entity_id=client_id,
    )
