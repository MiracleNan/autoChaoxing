import tempfile
import unittest
from pathlib import Path

from app import create_app
from api.config import GlobalConst as gc


class FakeChaoxing:
    login_result = {"status": True, "msg": "ok"}
    valid_cookies = True
    courses = []
    chapters = {"hasLocked": False, "points": []}
    login_calls = []
    validate_calls = 0
    fetch_courses_error = None
    fetch_chapters_error = None
    chapter_calls = []

    def __init__(self, account):
        self.account = account

    @classmethod
    def reset(cls):
        cls.login_result = {"status": True, "msg": "ok"}
        cls.valid_cookies = True
        cls.courses = []
        cls.chapters = {"hasLocked": False, "points": []}
        cls.login_calls = []
        cls.validate_calls = 0
        cls.fetch_courses_error = None
        cls.fetch_chapters_error = None
        cls.chapter_calls = []

    def login(self, login_with_cookies=False):
        self.__class__.login_calls.append(
            (self.account.username, self.account.password, login_with_cookies)
        )
        return self.__class__.login_result

    def _validate_cookie_session(self):
        self.__class__.validate_calls += 1
        return self.__class__.valid_cookies

    def get_course_list(self):
        if self.__class__.fetch_courses_error:
            raise self.__class__.fetch_courses_error
        return list(self.__class__.courses)

    def get_course_point(self, course_id, clazz_id, cpi):
        if self.__class__.fetch_chapters_error:
            raise self.__class__.fetch_chapters_error
        self.__class__.chapter_calls.append((course_id, clazz_id, cpi))
        return self.__class__.chapters


class WebAppTest(unittest.TestCase):
    def setUp(self):
        FakeChaoxing.reset()
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_cookie_path = gc.COOKIES_PATH
        gc.COOKIES_PATH = str(Path(self.tempdir.name) / "cookies.txt")
        self.app = create_app(chaoxing_factory=FakeChaoxing)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        gc.COOKIES_PATH = self.old_cookie_path
        self.tempdir.cleanup()

    def write_cookie_file(self):
        Path(gc.COOKIES_PATH).write_text("_uid=1;fid=2", encoding="utf8")

    def test_index_shows_login_without_cookies(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("SuperStar Local", response.get_data(as_text=True))
        self.assertIn("登录密码", response.get_data(as_text=True))

    def test_index_shows_dashboard_with_valid_cookies(self):
        self.write_cookie_file()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("课程列表", response.get_data(as_text=True))
        self.assertEqual(FakeChaoxing.validate_calls, 1)

    def test_login_uses_password_only_for_current_request(self):
        response = self.client.post(
            "/login",
            data={"username": "user-a", "password": "secret-password"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(FakeChaoxing.login_calls, [("user-a", "secret-password", False)])

    def test_login_error_does_not_echo_password(self):
        FakeChaoxing.login_result = {"status": False, "msg": "账号或密码错误"}

        response = self.client.post(
            "/login",
            data={"username": "user-a", "password": "secret-password"},
        )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 401)
        self.assertIn("账号或密码错误", body)
        self.assertNotIn("secret-password", body)

    def test_courses_fetches_and_caches_course_list(self):
        self.write_cookie_file()
        FakeChaoxing.courses = [
            {"title": "课程 A", "teacher": "Teacher", "courseId": "1", "clazzId": "2", "cpi": "3"}
        ]

        response = self.client.get("/courses")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("课程 A", body)
        self.assertIn("章节", body)
        self.assertEqual(self.app.config["COURSE_CACHE"], FakeChaoxing.courses)

    def test_courses_requires_valid_cookies(self):
        self.write_cookie_file()
        FakeChaoxing.valid_cookies = False

        response = self.client.get("/courses")

        self.assertEqual(response.status_code, 401)
        self.assertIn("登录状态已失效", response.get_data(as_text=True))

    def test_parse_course_url_matches_cached_course(self):
        self.app.config["COURSE_CACHE"] = [
            {"title": "课程 B", "teacher": "T", "courseId": "10", "clazzId": "20", "cpi": "30"}
        ]

        response = self.client.post(
            "/courses/parse-url",
            data={"course_url": "https://example.com/?courseid=10&clazzid=20&cpi=30"},
        )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("已匹配到课程：课程 B", body)
        self.assertIn("10", body)

    def test_parse_course_url_reports_missing_params(self):
        response = self.client.post(
            "/courses/parse-url",
            data={"course_url": "https://example.com/?courseid=10"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("缺少参数：clazzId, cpi", response.get_data(as_text=True))

    def test_course_chapters_fetches_read_only_chapter_list(self):
        self.write_cookie_file()
        self.app.config["COURSE_CACHE"] = [
            {"title": "课程 C", "teacher": "T", "courseId": "1", "clazzId": "2", "cpi": "3"}
        ]
        FakeChaoxing.chapters = {
            "hasLocked": True,
            "points": [
                {"title": "第一章", "jobCount": "2", "has_finished": True, "need_unlock": False},
                {"title": "第二章", "jobCount": "1", "has_finished": False, "need_unlock": True},
            ],
        }

        response = self.client.get("/courses/chapters?courseId=1&clazzId=2&cpi=3")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeChaoxing.chapter_calls, [("1", "2", "3")])
        self.assertIn("课程 C", body)
        self.assertIn("第一章", body)
        self.assertIn("已完成", body)
        self.assertIn("需解锁", body)

    def test_course_chapters_requires_complete_params(self):
        self.write_cookie_file()

        response = self.client.get("/courses/chapters?courseId=1")

        self.assertEqual(response.status_code, 400)
        self.assertIn("缺少课程参数：clazzId, cpi", response.get_data(as_text=True))

    def test_course_chapters_requires_valid_cookies(self):
        self.write_cookie_file()
        FakeChaoxing.valid_cookies = False

        response = self.client.get("/courses/chapters?courseId=1&clazzId=2&cpi=3")

        self.assertEqual(response.status_code, 401)
        self.assertIn("登录状态已失效", response.get_data(as_text=True))

    def test_webui_does_not_expose_course_automation_routes(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}

        self.assertNotIn("/courses/run", rules)
        self.assertNotIn("/courses/study", rules)


if __name__ == "__main__":
    unittest.main()
