import asyncio, logging, threading, time, random

logger = logging.getLogger(__name__)


class GroupAlarmManager:
    def __init__(self, on_target_reply: callable = None):
        self.groups = {}
        self._on_reply = on_target_reply

    def create_group(self, group_id: str, targets: list):
        self.groups[group_id] = {
            "targets": targets,
            "replied": set(),
            "running": False,
            "stop_event": threading.Event()
        }
        return group_id

    def start_group(self, group_id: str, alarm_func: callable):
        group = self.groups.get(group_id)
        if not group:
            return

        group["running"] = True
        group["stop_event"].clear()
        group["replied"] = set()

        def alarm_worker():
            while group["running"] and not group["stop_event"].is_set():
                for target in group["targets"]:
                    if target in group["replied"]:
                        continue
                    if group["stop_event"].is_set():
                        break
                    alarm_func(target)
                    time.sleep(random.randint(3, 8))
            group["running"] = False

        threading.Thread(target=alarm_worker, daemon=True).start()

    def mark_replied(self, group_id: str, target: str):
        group = self.groups.get(group_id)
        if not group:
            return
        group["replied"].add(target)

        if self._on_reply:
            self._on_reply(group_id, target)

        if len(group["replied"]) >= len(group["targets"]):
            group["running"] = False
            group["stop_event"].set()

    def stop_group(self, group_id: str):
        group = self.groups.get(group_id)
        if group:
            group["running"] = False
            group["stop_event"].set()

    def group_status(self, group_id: str):
        group = self.groups.get(group_id)
        if not group:
            return None
        return {
            "targets": group["targets"],
            "replied": list(group["replied"]),
            "pending": [t for t in group["targets"] if t not in group["replied"]],
            "running": group["running"]
        }
