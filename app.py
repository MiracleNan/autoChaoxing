# -*- coding: utf-8 -*-
"""
SuperStar Local — Flask web application.

Routes:
  /                    dashboard (login or main)
  /login               POST  login
  /logout              POST  logout
  /courses             GET   course list (htmx partial)
  /courses/chapters    GET   chapter list (htmx partial)
  /courses/parse-url   POST  parse course URL (htmx partial)
  /task/start          POST  start study task
  /task/stop           POST  stop study task
  /task/progress       GET   SSE progress stream
  /task/status         GET   current task status (JSON)
  /config              GET   config editor page
  /config/schema       GET   field schema (JSON)
  /config/<section>    GET   read section / POST  save section
"""
import json
import os
import time
from pathlib import Path
from typing import Callable

from flask import Flask, Response, render_template, redirect, request, url_for, jsonify

from api.base import Account, Chaoxing, SessionManager
from api.config import GlobalConst as gc
from api.config_manager import ConfigManager
from api.course_url import match_course, parse_course_url
from api.logger import logger
from api.task_manager import TaskManager

ChaoxingFactory = Callable[[Account], Chaoxing]


def create_app(chaoxing_factory: ChaoxingFactory | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        CHAOXING_FACTORY=chaoxing_factory or (lambda account: Chaoxing(account=account)),
        COURSE_CACHE=[],
    )

    cfg_mgr = ConfigManager()
    cfg_mgr.ensure_template()
    task_mgr = TaskManager()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_chaoxing(username: str = "", password: str = "") -> Chaoxing:
        factory: ChaoxingFactory = app.config["CHAOXING_FACTORY"]
        return factory(Account(username, password))

    def _course_from_request() -> dict[str, str]:
        course_id = request.args.get("courseId", "").strip()
        clazz_id = request.args.get("clazzId", "").strip()
        cpi = request.args.get("cpi", "").strip()
        for course in app.config.get("COURSE_CACHE", []):
            if (
                str(course.get("courseId", "")) == course_id
                and str(course.get("clazzId", "")) == clazz_id
                and str(course.get("cpi", "")) == cpi
            ):
                return {
                    "title": str(course.get("title", "")),
                    "teacher": str(course.get("teacher", "")),
                    "courseId": course_id,
                    "clazzId": clazz_id,
                    "cpi": cpi,
                }
        return {
            "title": request.args.get("title", "").strip(),
            "teacher": request.args.get("teacher", "").strip(),
            "courseId": course_id,
            "clazzId": clazz_id,
            "cpi": cpi,
        }

    def _has_valid_cookies() -> bool:
        if not Path(gc.COOKIES_PATH).exists():
            return False
        try:
            SessionManager.update_cookies()
            return _build_chaoxing()._validate_cookie_session()
        except Exception as exc:
            logger.debug("Cookie validation failed: {}", exc)
            return False

    def _clear_local_session() -> None:
        Path(gc.COOKIES_PATH).unlink(missing_ok=True)
        SessionManager.get_session().cookies.clear()
        app.config["COURSE_CACHE"] = []

    def _get_common_config() -> dict:
        """Read [common] from config.ini, merging with defaults."""
        raw = cfg_mgr.read_section("common")
        return {
            "username": raw.get("username", "").strip(),
            "password": raw.get("password", "").strip(),
            "use_cookies": raw.get("use_cookies", "false").lower() in ("true", "1", "yes"),
            "course_list": [c.strip() for c in raw.get("course_list", "").split(",") if c.strip()],
            "speed": min(2.0, max(1.0, float(raw.get("speed", "1")))),
            "jobs": max(1, int(raw.get("jobs", "4"))),
            "notopen_action": raw.get("notopen_action", "retry"),
        }

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    @app.get("/")
    def index():
        active = task_mgr.get_active_task()
        if _has_valid_cookies():
            return render_template("dashboard.html", active_task=active)
        return render_template("login.html")

    @app.post("/login")
    def login():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("login.html", error="请输入账号和密码。"), 400

        chaoxing = _build_chaoxing(username, password)
        try:
            result = chaoxing.login(login_with_cookies=False)
        except Exception:
            logger.exception("WebUI login failed")
            return render_template("login.html", error="登录请求失败，请稍后重试。"), 502

        if not result.get("status"):
            return render_template("login.html", error=result.get("msg") or "登录失败。"), 401

        # Save credentials to config.ini for task_manager to use
        cfg_mgr.write_section("common", {
            "username": username,
            "password": password,
            "use_cookies": "false",
            "course_list": "",
            "speed": "1",
            "jobs": "4",
            "notopen_action": "retry",
        })

        return redirect(url_for("index"))

    @app.post("/logout")
    def logout():
        _clear_local_session()
        return redirect(url_for("index"))

    # ------------------------------------------------------------------
    # Course API (htmx partials)
    # ------------------------------------------------------------------

    @app.get("/courses")
    def courses():
        if not _has_valid_cookies():
            return render_template("_courses.html", error="登录状态已失效，请重新登录。", courses=[]), 401
        try:
            course_list = _build_chaoxing().get_course_list()
        except Exception:
            logger.exception("Failed to fetch course list")
            return render_template("_courses.html", error="课程列表读取失败，请稍后重试。", courses=[]), 502
        app.config["COURSE_CACHE"] = course_list
        return render_template("_courses.html", courses=course_list)

    @app.get("/courses/chapters")
    def course_chapters():
        if not _has_valid_cookies():
            return render_template("_chapters.html", error="登录状态已失效，请重新登录。"), 401
        course = _course_from_request()
        missing = [n for n in ("courseId", "clazzId", "cpi") if not course.get(n)]
        if missing:
            return render_template("_chapters.html", error=f"缺少课程参数：{', '.join(missing)}。"), 400
        try:
            point_list = _build_chaoxing().get_course_point(
                course["courseId"], course["clazzId"], course["cpi"],
            )
        except Exception:
            logger.exception("Failed to fetch chapters")
            return render_template("_chapters.html", error="章节列表读取失败。"), 502
        return render_template(
            "_chapters.html", course=course,
            points=point_list.get("points", []),
            has_locked=point_list.get("hasLocked", False),
        )

    @app.post("/courses/parse-url")
    def parse_course_url_route():
        source_url = request.form.get("course_url", "").strip()
        parsed = parse_course_url(source_url)
        if not parsed.is_complete:
            return render_template("_course_url_result.html", error=f"缺少参数：{', '.join(parsed.missing)}。")
        matched = match_course(parsed, app.config.get("COURSE_CACHE", []))
        return render_template("_course_url_result.html", parsed=parsed, matched=matched)

    # ------------------------------------------------------------------
    # Task control
    # ------------------------------------------------------------------

    @app.post("/task/start")
    def task_start():
        if not _has_valid_cookies():
            return jsonify({"error": "登录状态已失效"}), 401

        if task_mgr.get_active_task():
            return jsonify({"error": "已有任务在运行，请先停止或等待完成"}), 409

        course_id = request.form.get("courseId", "").strip()
        clazz_id = request.form.get("clazzId", "").strip()
        cpi = request.form.get("cpi", "").strip()
        if not all([course_id, clazz_id, cpi]):
            return jsonify({"error": "缺少课程参数"}), 400

        # Find course in cache
        course = None
        for c in app.config.get("COURSE_CACHE", []):
            if (str(c.get("courseId")) == course_id
                    and str(c.get("clazzId")) == clazz_id
                    and str(c.get("cpi")) == cpi):
                course = c
                break
        if not course:
            return jsonify({"error": "未找到课程，请先刷新课程列表"}), 404

        common_config = _get_common_config()
        tiku_config = cfg_mgr.read_section("tiku")
        notification_config = cfg_mgr.read_section("notification")

        try:
            task_id = task_mgr.start_task(course, common_config, tiku_config, notification_config)
        except Exception as e:
            logger.exception("Failed to start task")
            return jsonify({"error": str(e)}), 500

        return jsonify({"task_id": task_id, "course_title": course.get("title", "")})

    @app.post("/task/stop")
    def task_stop():
        active = task_mgr.get_active_task()
        if not active:
            return jsonify({"error": "没有运行中的任务"}), 404
        task_mgr.stop_task(active["task_id"])
        return jsonify({"ok": True})

    @app.get("/task/status")
    def task_status():
        return jsonify(task_mgr.get_all_progress())

    @app.get("/task/progress")
    def task_progress():
        """SSE endpoint for real-time progress."""
        def generate():
            yield "data: {}\n\n"
            while True:
                events = task_mgr.wait_for_events(timeout=5.0)
                if events:
                    yield f"data: {json.dumps(events, ensure_ascii=False)}\n\n"
                else:
                    yield ": keepalive\n\n"

        return Response(generate(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ------------------------------------------------------------------
    # Config editor
    # ------------------------------------------------------------------

    @app.get("/config")
    def config_page():
        if not _has_valid_cookies():
            return redirect(url_for("index"))
        schema = cfg_mgr.get_schema()
        data = cfg_mgr.read_all()
        return render_template("config.html", schema=schema, data=data)

    @app.get("/config/schema")
    def config_schema():
        return jsonify(cfg_mgr.get_schema())

    @app.get("/config/<section>")
    def config_read(section):
        if section not in ("common", "tiku", "notification"):
            return jsonify({"error": "未知配置节"}), 404
        return jsonify(cfg_mgr.read_section(section))

    @app.post("/config/<section>")
    def config_save(section):
        if section not in ("common", "tiku", "notification"):
            return jsonify({"error": "未知配置节"}), 404
        data = request.get_json(silent=True) or {}
        schema = cfg_mgr.get_schema()
        known_keys = {f["key"] for f in schema.get(section, [])}
        filtered = {k: str(v) for k, v in data.items() if k in known_keys}
        cfg_mgr.write_section(section, filtered)
        return jsonify({"ok": True})

    @app.post("/config/test-llm")
    def config_test_llm():
        """Test AI / SiliconFlow LLM connection with current config."""
        from api.answer import Tiku
        tiku_config = cfg_mgr.read_section("tiku")
        provider = tiku_config.get("provider", "")
        if not any(p.strip() in ("AI", "SiliconFlow") for p in provider.split(",")):
            return jsonify({"ok": False, "error": "当前题库未配置 AI 或 SiliconFlow"})
        try:
            tiku = Tiku()
            tiku.config_set(tiku_config)
            tiku = tiku.get_tiku_from_config()
            tiku.init_tiku()
            ok = tiku.check_llm_connection()
            return jsonify({"ok": ok, "error": "" if ok else "连接测试失败"})
        except Exception as e:
            logger.exception("LLM test failed")
            return jsonify({"ok": False, "error": str(e)})

    return app


if __name__ == "__main__":
    host = os.environ.get("SUPERSTAR_HOST", "127.0.0.1")
    port = int(os.environ.get("SUPERSTAR_PORT", "5000"))
    debug = os.environ.get("SUPERSTAR_DEBUG") == "1"
    create_app().run(host=host, port=port, debug=debug, threaded=True)
