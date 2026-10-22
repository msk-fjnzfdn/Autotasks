from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from croniter import croniter
from datetime import datetime, timezone
import asyncio
from app.runner import run_blocks, run_blocks_background
from app.blocks import BLOCKS, BlockError
from app.database import get_session
from app.deps import get_current_user
from app.models import Block, ChainRun, TaskChain, User


router = APIRouter(prefix="/chains", tags=["chains"])


class ChainCreate(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True
    schedule: str | None = None


class ChainResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    owner_id: int | None
    schedule: str | None

    class Config:
        from_attributes = True


class BlockCreate(BaseModel):
    type: str
    name: str = Field(min_length=1, max_length=100)
    params: dict = {}
    position: int = 0


class BlockUpdate(BaseModel):
    name: str | None = None
    params: dict | None = None
    position: int | None = None


class BlockRead(BlockCreate):
    id: int

    class Config:
        from_attributes = True


class RunRead(BaseModel):
    id: int
    chain_id: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    logs: list = []

    class Config:
        from_attributes = True


class BlockTestIn(BaseModel):
    input: dict = {}


class ChainFull(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True
    schedule: str | None = None


class ChainImportIn(BaseModel):
    chain: ChainFull
    blocks: list[BlockCreate]


class ChainUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    schedule: str | None = None
    is_active: bool | None = None


async def _get_own_chain(chain_id: int, user: User, session: AsyncSession) -> TaskChain:
    result = await session.execute(
        select(TaskChain).where(
            TaskChain.id == chain_id,
            TaskChain.owner_id == user.id,
        )
    )
    chain = result.scalar_one_or_none()
    if chain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Цепочка не найдена")
    return chain


@router.post("/", response_model=ChainResponse, status_code=status.HTTP_201_CREATED)
async def create_chain(
    chain_in: ChainCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    new_chain = TaskChain(
        name=chain_in.name,
        description=chain_in.description,
        is_active=chain_in.is_active,
        owner_id=user.id,
    )
    session.add(new_chain)
    await session.commit()
    await session.refresh(new_chain)
    return new_chain


@router.get("/", response_model=list[ChainResponse])
async def list_chains(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(TaskChain).where(
            TaskChain.owner_id == user.id)
    )
    return result.scalars().all()


@router.get("/{chain_id}", response_model=ChainResponse)
async def get_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _get_own_chain(chain_id, user, session)


@router.delete("/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chain = await _get_own_chain(chain_id, user, session)
    await session.delete(chain)
    await session.commit()


@router.patch("/{chain_id}", response_model=ChainResponse)
async def update_chain(
    chain_id: int,
    chain_in: ChainUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chain = await _get_own_chain(chain_id, user, session)
    if chain_in.schedule is not None:
        try:
            croniter(chain_in.schedule)
        except (ValueError, KeyError):
            raise HTTPException(400, detail="Некорректное cron-выражение")

    for key, value in chain_in.model_dump(exclude_unset=True).items():
        setattr(chain, key, value)
    await session.commit()
    await session.refresh(chain)
    return chain


@router.get("/blocks/catalog")
async def block_catalog():
    return [
        {
            "type": block_type,
            "title": spec.title,
            "description": spec.description,
            "params": spec.params,
        }
        for block_type, spec in BLOCKS.items()
    ]


@router.post("/{chain_id}/blocks", response_model=BlockRead, status_code=status.HTTP_201_CREATED)
async def add_block(
    chain_id: int,
    block_in: BlockCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_own_chain(chain_id, user, session)
    if block_in.type not in BLOCKS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неизвестный тип блока «{block_in.type}»",
        )
    block = Block(chain_id=chain_id, **block_in.model_dump())
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block


@router.patch("/{chain_id}/blocks/{block_id}", response_model=BlockRead)
async def update_block(
    chain_id: int,
    block_id: int,
    block_in: BlockUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_own_chain(chain_id, user, session)
    result = await session.execute(
        select(Block).where(Block.id == block_id, Block.chain_id == chain_id)
    )
    block = result.scalar_one_or_none()
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Блок не найден")

    for key, value in block_in.model_dump(exclude_unset=True).items():
        setattr(block, key, value)
    await session.commit()
    await session.refresh(block)
    return block


@router.delete("/{chain_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    chain_id: int,
    block_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_own_chain(chain_id, user, session)
    result = await session.execute(
        select(Block).where(Block.id == block_id, Block.chain_id == chain_id)
    )
    block = result.scalar_one_or_none()
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Блок не найден")
    await session.delete(block)
    await session.commit()


@router.get("/{chain_id}/blocks", response_model=list[BlockRead])
async def list_blocks(
    chain_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_own_chain(chain_id, user, session)
    result = await session.execute(
        select(Block).where(Block.chain_id ==
                            chain_id).order_by(Block.position)
    )
    return result.scalars().all()


@router.post("/{chain_id}/run")
async def run_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chain = await _get_own_chain(chain_id, user, session)
    if not chain.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Цепочка неактивна")

    result = await session.execute(
        select(Block).where(Block.chain_id ==
                            chain_id).order_by(Block.position)
    )
    blocks = list(result.scalars().all())
    if not blocks:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "В цепочке нет блоков")

    run = ChainRun(chain_id=chain_id, status="running",
                   started_at=datetime.now(timezone.utc), logs=[])
    session.add(run)
    await session.commit()
    await session.refresh(run)

    asyncio.create_task(run_blocks_background(run.id, chain_id))
    return {"run_id": run.id}


@router.get("/{chain_id}/runs", response_model=list[RunRead])
async def list_runs(
    chain_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_own_chain(chain_id, user, session)
    result = await session.execute(
        select(ChainRun)
        .where(ChainRun.chain_id == chain_id)
        .order_by(ChainRun.started_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/{chain_id}/runs/{run_id}", response_model=RunRead)
async def get_run(
    chain_id: int,
    run_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_own_chain(chain_id, user, session)
    result = await session.execute(
        select(ChainRun).where(ChainRun.id ==
                               run_id, ChainRun.chain_id == chain_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запуск не найден")
    return run

#на будущее (надо влепить в фронт эти функции экспорта и импорта)
@router.post("/import", response_model=ChainResponse, status_code=status.HTTP_201_CREATED)
async def import_chain(
    payload: ChainImportIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    for block_in in payload.blocks:
        if block_in.type not in BLOCKS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неизвестный тип блока «{block_in.type}»",
            )

    chain = TaskChain(owner_id=user.id, **payload.chain.model_dump())
    session.add(chain)
    for block_in in payload.blocks:
        session.add(Block(chain_id=chain.id, **block_in.model_dump()))

    await session.commit()
    await session.refresh(chain)
    return chain


@router.get("/{chain_id}/export")
async def export_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chain = await _get_own_chain(chain_id, user, session)
    result = await session.execute(
        select(Block).where(Block.chain_id ==
                            chain_id).order_by(Block.position)
    )
    return {
        "chain": {
            "name": chain.name,
            "description": chain.description,
            "is_active": chain.is_active,
            "schedule": chain.schedule,
        },
        "blocks": [
            {"type": b.type, "name": b.name,
                "params": b.params or {}, "position": b.position}
            for b in result.scalars().all()
        ],
    }


@router.post("/{chain_id}/blocks/{block_id}/test")
async def test_block(
    chain_id: int,
    block_id: int,
    payload: BlockTestIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_own_chain(chain_id, user, session)
    result = await session.execute(
        select(Block).where(Block.id == block_id, Block.chain_id == chain_id)
    )
    block = result.scalar_one_or_none()
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Блок не найден")

    spec = BLOCKS.get(block.type)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный тип блока")

    try:
        output = await spec.run(block.params or {}, dict(payload.input))
        return {"output": output}
    except BlockError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ошибка выполнения: {e}")
