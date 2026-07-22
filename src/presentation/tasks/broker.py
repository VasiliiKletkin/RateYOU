"""taskiq broker + scheduler, run as their own processes.

Two entry points, both defined here and both needing the task module passed
explicitly so their labels get registered:

    taskiq worker    src.presentation.tasks.broker:broker    src.presentation.tasks.broadcast
    taskiq scheduler src.presentation.tasks.broker:scheduler src.presentation.tasks.broadcast

Broadcasts live outside the bot process on purpose: sending to thousands of
chats is slow and rate-limited, and it must not stall the event loop that
answers live updates.
"""

import logging

from dishka import make_async_container
from dishka.integrations.taskiq import setup_dishka
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from src.infrastructure.config import get_settings
from src.infrastructure.observability import init_sentry
from src.presentation.di import all_providers

settings = get_settings()
logging.basicConfig(level=settings.log_level.value)
init_sentry(settings, component="tasks")

broker = ListQueueBroker(settings.redis.dsn).with_result_backend(
    RedisAsyncResultBackend(settings.redis.dsn)
)

# Schedules are declared as `schedule=[...]` labels on the tasks themselves,
# so adding a job means editing one decorator rather than a central table.
scheduler = TaskiqScheduler(broker=broker, sources=[LabelScheduleSource(broker)])

# Same providers as the bot: tasks reuse the very same use cases, and dishka
# opens a REQUEST scope (fresh session + UoW) around every task run.
container = make_async_container(*all_providers())
setup_dishka(container, broker)
