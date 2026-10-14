from unittest.mock import MagicMock

from openjarvis.scheduler.delivery import NotificationOutbox
from openjarvis.scheduler.scheduler import TaskScheduler
from openjarvis.scheduler.store import SchedulerStore


def test_failed_delivery_survives_restart_and_retries_without_repeating_success(
    tmp_path,
):
    path = tmp_path / "delivery.json"
    queue = NotificationOutbox(path)
    queue.enqueue("run:1", "telegram", "123", "Generic reminder")
    queue.drain(lambda *args: False, now=0)
    assert queue.records()[0]["status"] == "pending"
    restarted = NotificationOutbox(path)
    send = MagicMock(return_value=True)
    restarted.drain(send, now=100)
    restarted.enqueue("run:1", "telegram", "123", "Generic reminder")
    restarted.drain(send, now=200)
    assert send.call_count == 1
    assert restarted.records()[0]["status"] == "delivered"


def test_deterministic_reminder_does_not_invoke_model(tmp_path):
    system = MagicMock()
    store = SchedulerStore(tmp_path / "tasks.db")
    scheduler = TaskScheduler(store, system)
    task = scheduler.create_task(
        "Take a break",
        "once",
        "2099-01-01T00:00:00+00:00",
        metadata={"action": "reminder"},
    )
    scheduler.run_task(task.id)
    system.ask.assert_not_called()
    assert store.get_run_logs(task.id)[0]["result"] == "Take a break"
    scheduler.stop()
    store.close()
