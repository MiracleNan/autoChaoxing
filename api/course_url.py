from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlparse


@dataclass(frozen=True)
class ParsedCourseUrl:
    course_id: str | None
    clazz_id: str | None
    cpi: str | None
    missing: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing

    def as_course_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.course_id:
            params["courseId"] = self.course_id
        if self.clazz_id:
            params["clazzId"] = self.clazz_id
        if self.cpi:
            params["cpi"] = self.cpi
        return params


def parse_course_url(value: str) -> ParsedCourseUrl:
    query_items = _extract_query_items(value)

    course_id = _first_param(query_items, "courseid", "courseId")
    clazz_id = _first_param(query_items, "clazzid", "clazzId")
    cpi = _first_param(query_items, "cpi")

    missing = []
    if not course_id:
        missing.append("courseId")
    if not clazz_id:
        missing.append("clazzId")
    if not cpi:
        missing.append("cpi")

    return ParsedCourseUrl(
        course_id=course_id,
        clazz_id=clazz_id,
        cpi=cpi,
        missing=tuple(missing),
    )


def match_course(parsed: ParsedCourseUrl, courses: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not parsed.is_complete:
        return None

    for course in courses:
        if (
            str(course.get("courseId", "")) == parsed.course_id
            and str(course.get("clazzId", "")) == parsed.clazz_id
            and str(course.get("cpi", "")) == parsed.cpi
        ):
            return course

    return None


def _extract_query_items(value: str) -> list[tuple[str, str]]:
    text = value.strip()
    if not text:
        return []

    parsed = urlparse(text)
    query_parts: list[str] = []

    if parsed.query:
        query_parts.append(parsed.query)

    if parsed.fragment:
        fragment = urlparse(parsed.fragment)
        query_parts.append(fragment.query or parsed.fragment)

    if not query_parts and "=" in text:
        query_parts.append(text.split("?", 1)[-1])

    items: list[tuple[str, str]] = []
    for query in query_parts:
        items.extend(parse_qsl(query, keep_blank_values=True))
    return items


def _first_param(query_items: list[tuple[str, str]], *names: str) -> str | None:
    wanted = {name.lower() for name in names}
    for key, value in query_items:
        if key.lower() in wanted and value.strip():
            return value.strip()
    return None
