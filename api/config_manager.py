# -*- coding: utf-8 -*-
"""
Config manager: read / write config.ini for the web UI.
Wraps configparser with schema-aware helpers so the frontend
can render labeled form fields instead of raw ini sections.
"""
import configparser
import os
from pathlib import Path
from typing import Any

CONFIG_PATH = os.environ.get("SUPERSTAR_CONFIG", "config.ini")

# Field definitions: (key, label, type, default, placeholder, group)
# type: "text" | "password" | "number" | "select" | "toggle"
COMMON_FIELDS: list[dict[str, Any]] = [
    {"key": "username", "label": "手机号账号", "type": "text", "placeholder": "手机号"},
    {"key": "password", "label": "登录密码", "type": "password", "placeholder": "密码"},
    {"key": "use_cookies", "label": "使用 Cookie 登录", "type": "toggle", "default": "false"},
    {"key": "course_list", "label": "课程 ID 列表", "type": "text", "placeholder": "逗号分隔，留空则全部"},
    {"key": "speed", "label": "播放倍速", "type": "number", "default": "1", "min": 1, "max": 2, "step": 0.1},
    {"key": "jobs", "label": "并行章节数", "type": "number", "default": "4", "min": 1, "max": 16},
    {"key": "notopen_action", "label": "未开放章节", "type": "select", "default": "retry",
     "options": [{"value": "retry", "text": "重试"}, {"value": "continue", "text": "跳过"}]},
]

TIKU_PROVIDER_OPTIONS = [
    {"value": "", "text": "不使用题库"},
    {"value": "TikuYanxi", "text": "言溪题库"},
    {"value": "TikuLike", "text": "LIKE 知识库"},
    {"value": "TikuAdapter", "text": "TikuAdapter"},
    {"value": "AI", "text": "AI 大模型 (OpenAI 兼容)"},
    {"value": "SiliconFlow", "text": "硅基流动 SiliconFlow"},
    {"value": "TikuGo", "text": "GO 题 / 网课小工具"},
]

TIKU_FIELDS: list[dict[str, Any]] = [
    {"key": "provider", "label": "题库", "type": "select", "default": "TikuYanxi",
     "options": TIKU_PROVIDER_OPTIONS,
     "help": "支持多题库回退，用逗号分隔，如 TikuGo,TikuYanxi"},
    {"key": "submit", "label": "自动提交答题", "type": "toggle", "default": "false"},
    {"key": "cover_rate", "label": "最低题库覆盖率", "type": "number", "default": "0.9", "min": 0, "max": 1, "step": 0.05},
    {"key": "delay", "label": "搜题间隔 (秒)", "type": "number", "default": "1.0", "min": 0, "max": 30, "step": 0.5},
    {"key": "check_llm_connection", "label": "启动时检查大模型连接", "type": "toggle", "default": "true"},
    {"key": "tokens", "label": "题库 Token", "type": "text", "placeholder": "言溪 / LIKE Token，逗号分隔"},
    # TikuAdapter
    {"key": "url", "label": "TikuAdapter URL", "type": "text", "placeholder": "http://...", "group": "TikuAdapter"},
    # TikuGo
    {"key": "go_authorization", "label": "GO 题 Token", "type": "text", "group": "TikuGo"},
    {"key": "go_min_interval", "label": "GO 题最小间隔 (秒)", "type": "number", "default": "1.0", "group": "TikuGo"},
    {"key": "go_retry_times", "label": "GO 题重试次数", "type": "number", "default": "3", "group": "TikuGo"},
    {"key": "go_retry_backoff", "label": "GO 题重试退避", "type": "number", "default": "1.2", "group": "TikuGo"},
    # LIKE
    {"key": "likeapi_search", "label": "LIKE 联网搜索", "type": "toggle", "default": "false", "group": "LIKE"},
    {"key": "likeapi_vision", "label": "LIKE 视觉能力", "type": "toggle", "default": "true", "group": "LIKE"},
    {"key": "likeapi_model", "label": "LIKE 模型", "type": "text", "default": "glm-4.5-air", "group": "LIKE"},
    {"key": "likeapi_retry", "label": "LIKE 自动重试", "type": "toggle", "default": "true", "group": "LIKE"},
    {"key": "likeapi_retry_times", "label": "LIKE 重试次数", "type": "number", "default": "3", "group": "LIKE"},
    # AI (OpenAI-compatible)
    {"key": "endpoint", "label": "API Endpoint", "type": "text", "placeholder": "https://api.example.com/v1", "group": "AI"},
    {"key": "key", "label": "API Key", "type": "password", "group": "AI"},
    {"key": "model", "label": "模型名称", "type": "text", "placeholder": "gpt-4o-mini", "group": "AI"},
    {"key": "min_interval_seconds", "label": "请求间隔 (秒)", "type": "number", "default": "3", "group": "AI"},
    {"key": "http_proxy", "label": "HTTP 代理", "type": "text", "placeholder": "http://...", "group": "AI"},
    # SiliconFlow
    {"key": "siliconflow_key", "label": "SiliconFlow Key", "type": "password", "group": "SiliconFlow"},
    {"key": "siliconflow_model", "label": "SiliconFlow 模型", "type": "text", "default": "deepseek-ai/DeepSeek-R1", "group": "SiliconFlow"},
    {"key": "siliconflow_endpoint", "label": "SiliconFlow Endpoint", "type": "text",
     "default": "https://api.siliconflow.cn/v1/chat/completions", "group": "SiliconFlow"},
    # Judgement
    {"key": "true_list", "label": "判断题-正确关键词", "type": "text", "default": "正确,对,√,是"},
    {"key": "false_list", "label": "判断题-错误关键词", "type": "text", "default": "错误,错,×,否,不对,不正确"},
]

NOTIFICATION_FIELDS: list[dict[str, Any]] = [
    {"key": "provider", "label": "通知服务", "type": "select", "default": "",
     "options": [
         {"value": "", "text": "不使用通知"},
         {"value": "ServerChan", "text": "Server 酱"},
         {"value": "Qmsg", "text": "Qmsg 酱"},
         {"value": "Bark", "text": "Bark (iOS)"},
         {"value": "Telegram", "text": "Telegram Bot"},
     ]},
    {"key": "url", "label": "推送 URL", "type": "text", "placeholder": "完整推送地址"},
    {"key": "tg_chat_id", "label": "Telegram Chat ID", "type": "text", "group": "Telegram"},
]


class ConfigManager:
    """Read / write config.ini with schema awareness."""

    def __init__(self, path: str | None = None):
        self.path = Path(path or CONFIG_PATH)

    def exists(self) -> bool:
        return self.path.exists()

    def ensure_template(self):
        """Copy config_template.ini if config.ini doesn't exist."""
        if self.path.exists():
            return
        template = self.path.parent / "config_template.ini"
        if template.exists():
            self.path.write_text(template.read_text(encoding="utf8"), encoding="utf8")

    def read_all(self) -> dict[str, dict[str, str]]:
        """Read all sections as {section: {key: value}}."""
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(str(self.path), encoding="utf8")
        result: dict[str, dict[str, str]] = {}
        for section in cfg.sections():
            result[section] = dict(cfg.items(section))
        return result

    def read_section(self, section: str) -> dict[str, str]:
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(str(self.path), encoding="utf8")
        if cfg.has_section(section):
            return dict(cfg.items(section))
        return {}

    def write_section(self, section: str, data: dict[str, str]):
        """Write a single section, preserving other sections."""
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(str(self.path), encoding="utf8")
        if not cfg.has_section(section):
            cfg.add_section(section)
        for key, value in data.items():
            cfg.set(section, key, str(value))
        with open(self.path, "w", encoding="utf8") as f:
            cfg.write(f)

    def write_all(self, sections: dict[str, dict[str, str]]):
        cfg = configparser.ConfigParser(interpolation=None)
        for section, values in sections.items():
            cfg.add_section(section)
            for key, value in values.items():
                cfg.set(section, key, str(value))
        with open(self.path, "w", encoding="utf8") as f:
            cfg.write(f)

    def get_schema(self) -> dict[str, Any]:
        """Return field schemas for the frontend."""
        return {
            "common": COMMON_FIELDS,
            "tiku": TIKU_FIELDS,
            "notification": NOTIFICATION_FIELDS,
        }
