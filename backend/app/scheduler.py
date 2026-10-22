from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from croniter import croniter
from sqlalchemy import select
from app.database import async_session_maker
from app.models import Block, TaskChain
from app.runner import run_blocks

scheduler = AsyncIOScheduler()


async def run_scheduled_chains():
    now = datetime.now()
    window_start = now - timedelta(minutes=1)

    async with async_session_maker() as session:
        result = await session.execute(
            select(TaskChain).where(
                TaskChain.is_active == True,
                TaskChain.schedule.is_not(None),
            )
        )
        for chain in result.scalars():
            schedule = chain.schedule
            if schedule is None:
                continue
            try:
                next_fire = croniter(schedule, window_start).get_next(datetime)
            except (ValueError, KeyError):
                continue
            if next_fire > now:
                continue

            blocks_result = await session.execute(
                select(Block).where(Block.chain_id ==
                                    chain.id).order_by(Block.position)
            )
            blocks = list(blocks_result.scalars().all())
            if not blocks:
                continue
            await run_blocks(chain.id, blocks, session, extra_log="Запуск по расписанию")


def start_scheduler():
    scheduler.add_job(
        run_scheduled_chains, "interval", seconds=60,
        id="scheduled_chains", max_instances=1,
    )
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
