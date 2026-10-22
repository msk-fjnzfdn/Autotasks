from datetime import datetime, timezone
from typing import Any
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.blocks import BLOCKS, BlockError
from app.database import async_session_maker
from app.models import Block, ChainRun


async def run_blocks(
    chain_id: int,
    blocks: list[Block],
    session: AsyncSession,
    extra_log: str | None = None,
) -> ChainRun:
    run = ChainRun(chain_id=chain_id, status="running", logs=[])
    if extra_log:
        run.logs.append({"time": _now(), "block": "—",
                        "level": "info", "message": extra_log})

    context: dict[str, Any] = {}

    for block_row in sorted(blocks, key=lambda b: b.position):
        spec = BLOCKS.get(block_row.type)
        if spec is None:
            run.logs.append(_entry(block_row.name, "error",
                            f"Неизвестный тип блока «{block_row.type}»"))
            run.status = "failed"
            break
        try:
            output = await spec.run(block_row.params or {}, context)
            context.update(output)
            message = spec.title + \
                (f": {output.get('status_code')}" if "status_code" in output else "")
            if block_row.type == "log_message":
                message = block_row.params.get("message", "")
            run.logs.append(_entry(block_row.name, "info", message))
        except BlockError as e:
            run.logs.append(_entry(block_row.name, "error", str(e)))
            run.status = "failed"
            break
        except Exception as e:
            run.logs.append(_entry(block_row.name, "error",
                            f"Ошибка выполнения: {e}"))
            run.status = "failed"
            break
    else:
        run.status = "success"

    run.finished_at = datetime.now(timezone.utc)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _entry(block_name: str, level: str, message: str) -> dict:
    return {"time": _now(), "block": block_name, "level": level, "message": message}


def _fmt(value):
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


async def run_blocks_background(run_id: int, chain_id: int):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ChainRun).where(ChainRun.id == run_id)
        )
        run: ChainRun = result.scalar_one()
        blocks = list((await session.execute(
            select(Block).where(Block.chain_id ==
                                chain_id).order_by(Block.position)
        )).scalars().all())

        logs: list[dict[str, Any]] = list(run.logs or [])
        context = {}
        status = "success"

        for block in blocks:
            spec = BLOCKS.get(block.type)
            if spec is None:
                logs.append({
                    "time": _now(),
                    "block_id": block.id,
                    "block": block.name,
                    "stage": "error",
                    "level": "error",
                    "message": f"Неизвестный тип блока «{block.type}»",
                })
                status = "failed"
                run.logs = list(logs)
                await session.commit()
                break
            logs.append({
                "time": _now(),
                "block_id": block.id,
                "block": block.name,
                "stage": "start",
                "level": "info",
                "message": "выполняется…",
            })
            run.logs = list(logs)
            await session.commit()

            try:
                output = await spec.run(block.params or {}, dict(context))
                context = output if output is not None else {}
                logs.append({
                    "time": _now(),
                    "block_id": block.id,
                    "block": block.name,
                    "stage": "done",
                    "level": "info",
                    "message": _fmt(output),
                })
            except BlockError as e:
                logs.append({
                    "time": _now(),
                    "block_id": block.id,
                    "block": block.name,
                    "stage": "error",
                    "level": "error",
                    "message": str(e),
                })
                status = "failed"
            except Exception as e:
                logs.append({
                    "time": _now(),
                    "block_id": block.id,
                    "block": block.name,
                    "stage": "error",
                    "level": "error",
                    "message": f"Ошибка выполнения: {e}",
                })
                status = "failed"

            run.logs = list(logs)
            await session.commit()
            if status == "failed":
                break

        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        await session.commit()
