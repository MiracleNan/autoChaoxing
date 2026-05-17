# -*- coding: utf-8 -*-
"""
Task manager: wraps study logic into a web-managed service.
Supports start / stop / progress via a singleton.
"""
import enum
import threading
import time
import traceback
from queue import PriorityQueue, Empty
from typing import Any, Callable

from api.base import Account, Chaoxing, StudyResult
from api.answer import Tiku
from api.logger import logger
from api.notification import Notification

from main import ChapterResult, ChapterTask, process_chapter


class TaskStatus(str, enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    DONE = "done"
    ERROR = "error"
    STOPPED = "stopped"


class ProgressSnapshot:
    """Serializable progress state for one study task."""

    def __init__(self, task_id: str, course_title: str, total: int):
        self.task_id = task_id
        self.status = TaskStatus.RUNNING
        self.course_title = course_title
        self.total_chapters = total
        self.completed_chapters = 0
        self.failed_chapters = 0
        self.skipped_chapters = 0
        self.current_chapter = ""
        self.errors: list[str] = []
        self.started_at = time.time()
        self.ended_at = 0.0

    def to_dict(self) -> dict[str, Any]:
        elapsed = round(
            (self.ended_at if self.ended_at > 0 else time.time()) - self.started_at, 1
        )
        return {
            "task_id": self.task_id,
            "status": self.status,
            "course_title": self.course_title,
            "total_chapters": self.total_chapters,
            "completed_chapters": self.completed_chapters,
            "failed_chapters": self.failed_chapters,
            "skipped_chapters": self.skipped_chapters,
            "current_chapter": self.current_chapter,
            "errors": list(self.errors[-20:]),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "elapsed": elapsed,
        }


class TaskManager:
    _instance: "TaskManager | None" = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._snapshots: dict[str, ProgressSnapshot] = {}
                    inst._stop_events: dict[str, threading.Event] = {}
                    inst._threads: dict[str, threading.Thread] = {}
                    inst._event_cond = threading.Condition()
                    cls._instance = inst
        return cls._instance

    # ---- public API ----

    def start_task(
        self,
        course: dict[str, Any],
        common_config: dict[str, Any],
        tiku_config: dict[str, Any] | None = None,
        notification_config: dict[str, Any] | None = None,
    ) -> str:
        task_id = f"{course['courseId']}_{int(time.time())}"

        # Build chaoxing
        account = Account(
            common_config.get("username", ""),
            common_config.get("password", ""),
        )
        tiku = Tiku()
        tiku.config_set(tiku_config or {})
        tiku = tiku.get_tiku_from_config()
        tiku.init_tiku()

        query_delay = (tiku_config or {}).get("delay", 0)
        chaoxing = Chaoxing(account=account, tiku=tiku, query_delay=query_delay)

        use_cookies = common_config.get("use_cookies", False)
        login_result = chaoxing.login(login_with_cookies=use_cookies)
        if not login_result.get("status"):
            raise RuntimeError(login_result.get("msg", "登录失败"))

        stop_event = threading.Event()
        self._stop_events[task_id] = stop_event

        # Pre-create snapshot before starting thread
        snap = ProgressSnapshot(task_id=task_id, course_title=course.get("title", ""), total=0)
        self._snapshots[task_id] = snap
        self._notify()

        speed = min(2.0, max(1.0, float(common_config.get("speed", 1.0))))
        config = {
            "speed": speed,
            "jobs": int(common_config.get("jobs", 4)),
            "notopen_action": common_config.get("notopen_action", "retry"),
        }

        notification = Notification()
        notification.config_set(notification_config or {})
        notification = notification.get_notification_from_config()
        notification.init_notification()

        t = threading.Thread(
            target=self._run,
            args=(task_id, chaoxing, course, config, notification, stop_event),
            daemon=True,
        )
        self._threads[task_id] = t
        t.start()
        return task_id

    def stop_task(self, task_id: str) -> bool:
        evt = self._stop_events.get(task_id)
        if evt:
            evt.set()
            snap = self._snapshots.get(task_id)
            if snap and snap.status == TaskStatus.RUNNING:
                snap.status = TaskStatus.STOPPING
                self._notify()
            return True
        return False

    def get_progress(self, task_id: str) -> dict[str, Any] | None:
        snap = self._snapshots.get(task_id)
        return snap.to_dict() if snap else None

    def get_all_progress(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._snapshots.values()]

    def get_active_task(self) -> dict[str, Any] | None:
        for s in self._snapshots.values():
            if s.status in (TaskStatus.RUNNING, TaskStatus.STOPPING):
                return s.to_dict()
        return None

    def wait_for_events(self, timeout: float = 30.0) -> list[dict[str, Any]]:
        with self._event_cond:
            self._event_cond.wait(timeout=timeout)
        return self.get_all_progress()

    # ---- internals ----

    def _notify(self):
        with self._event_cond:
            self._event_cond.notify_all()

    def _run(
        self,
        task_id: str,
        chaoxing: Chaoxing,
        course: dict[str, Any],
        config: dict,
        notification: Notification,
        stop_event: threading.Event,
    ):
        snap = self._snapshots[task_id]
        try:
            point_list = chaoxing.get_course_point(
                course["courseId"], course["clazzId"], course["cpi"]
            )
            points = point_list.get("points", [])
            snap.total_chapters = len(points)
            self._notify()

            max_tries = 5
            retry_queue: list[ChapterTask] = []

            tasks = [ChapterTask(point=pt, index=i) for i, pt in enumerate(points)]

            for task in tasks:
                if stop_event.is_set():
                    snap.status = TaskStatus.STOPPED
                    snap.current_chapter = ""
                    self._notify()
                    notification.send(f"SuperStar: 课程 {course.get('title', '')} 已停止")
                    return

                snap.current_chapter = task.point.get("title", "")
                self._notify()

                result = self._process_one(chaoxing, course, task, config["speed"])

                match result:
                    case ChapterResult.SUCCESS:
                        snap.completed_chapters += 1
                    case ChapterResult.NOT_OPEN:
                        if config["notopen_action"] == "continue":
                            snap.skipped_chapters += 1
                            snap.errors.append(f"跳过未开放: {task.point.get('title', '')}")
                        else:
                            # Put into retry list
                            task.tries += 1
                            if task.tries < max_tries:
                                retry_queue.append(task)
                            else:
                                snap.skipped_chapters += 1
                                snap.errors.append(f"未开放章节放弃: {task.point.get('title', '')}")
                    case ChapterResult.ERROR:
                        task.tries += 1
                        if task.tries < max_tries:
                            retry_queue.append(task)
                        else:
                            snap.failed_chapters += 1
                            snap.errors.append(f"章节失败: {task.point.get('title', '')}")

                self._notify()

            # Process retries
            for task in retry_queue:
                if stop_event.is_set():
                    snap.status = TaskStatus.STOPPED
                    self._notify()
                    notification.send(f"SuperStar: 课程 {course.get('title', '')} 已停止")
                    return

                snap.current_chapter = f"[重试] {task.point.get('title', '')}"
                self._notify()

                result = self._process_one(chaoxing, course, task, config["speed"])

                match result:
                    case ChapterResult.SUCCESS:
                        snap.completed_chapters += 1
                    case _:
                        snap.failed_chapters += 1
                        snap.errors.append(f"重试仍失败: {task.point.get('title', '')}")

                self._notify()

            if stop_event.is_set():
                snap.status = TaskStatus.STOPPED
            else:
                snap.status = TaskStatus.DONE
                notification.send(
                    f"SuperStar: 课程 {course.get('title', '')} 学习完成 "
                    f"(完成 {snap.completed_chapters}/{snap.total_chapters})"
                )

        except Exception as e:
            snap.status = TaskStatus.ERROR
            snap.errors.append(f"任务异常: {e}")
            logger.exception(f"Task {task_id} failed")
            try:
                notification.send(f"SuperStar: 课程 {course.get('title', '')} 出错: {e}")
            except Exception:
                pass
        finally:
            snap.ended_at = time.time()
            snap.current_chapter = ""
            self._stop_events.pop(task_id, None)
            self._threads.pop(task_id, None)
            self._notify()

    def _process_one(
        self,
        chaoxing: Chaoxing,
        course: dict[str, Any],
        task: ChapterTask,
        speed: float,
    ) -> ChapterResult:
        """Process a single chapter, suppressing tqdm noise."""
        try:
            return process_chapter(chaoxing, course, task.point, speed)
        except Exception as e:
            logger.error(f"Chapter {task.point.get('title', '')} exception: {e}")
            return ChapterResult.ERROR
