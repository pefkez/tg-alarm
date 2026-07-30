import asyncio, logging, json, os, threading, time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

SCHEDULE_FILE = "alarm_schedule.json"


class AlarmScheduler:
    def __init__(self):
        self.schedules = []
        self._running = False
        self._thread = None
        self._on_alarm: Callable = None

    def set_callback(self, cb: Callable):
        self._on_alarm = cb

    def load(self):
        if Path(SCHEDULE_FILE).exists():
            try:
                with open(SCHEDULE_FILE) as f:
                    self.schedules = json.load(f)
            except Exception as e:
                logger.error(f"Schedule load error: {e}")
                self.schedules = []

    def save(self):
        try:
            with open(SCHEDULE_FILE, 'w') as f:
                json.dump(self.schedules, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Schedule save error: {e}")

    def add(self, schedule: dict):
        schedule['id'] = str(int(time.time()))
        self.schedules.append(schedule)
        self.save()
        return schedule['id']

    def remove(self, schedule_id: str):
        self.schedules = [s for s in self.schedules if s.get('id') != schedule_id]
        self.save()

    def list(self):
        return self.schedules

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            now = datetime.now()
            for sched in self.schedules[:]:
                if not sched.get('enabled', True):
                    continue
                alarm_time_str = sched.get('time')
                days = sched.get('days', [])
                if not alarm_time_str:
                    continue

                try:
                    alarm_time = datetime.strptime(alarm_time_str, "%H:%M").time()
                    if now.time().hour == alarm_time.hour and now.time().minute == alarm_time.minute:
                        if now.weekday() in days or not days:
                            if self._on_alarm:
                                threading.Thread(
                                    target=self._on_alarm,
                                    args=(sched,),
                                    daemon=True
                                ).start()
                            if sched.get('once', False):
                                self.remove(sched['id'])
                except ValueError:
                    continue
            time.sleep(30)
