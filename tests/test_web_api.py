import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app import create_app
from api.config import GlobalConst as gc


class FakeChaoxing:
    login_result = {"status": True, "msg": "ok"}
    valid_cookies = True
    courses = []
    chapters = {"hasLocked": False, "points": []}

    def __init__(self, account):
        self.account = account

    @classmethod
    def reset(cls):
        cls.login_result = {"status": True, "msg": "ok"}
        cls.valid_cookies = True
        cls.courses = []
        cls.chapters = {"hasLocked": False, "points": []}

    def login(self, login_with_cookies=False):
        return self.__class__.login_result

    def _validate_cookie_session(self):
        return self.__class__.valid_cookies

    def get_course_list(self):
        return list(self.__class__.courses)

    def get_course_point(self, course_id, clazz_id, cpi):
        return self.__class__.chapters


class TaskApiTest(unittest.TestCase):
    def setUp(self):
        FakeChaoxing.reset()
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_cookie_path = gc.COOKIES_PATH
        gc.COOKIES_PATH = str(Path(self.tempdir.name) / "cookies.txt")
        # Create a config.ini
        Path(self.tempdir.name, "config.ini").write_text(
            "[common]\nusername=test\npassword=pass\nspeed=1\njobs=2\nnotopen_action=retry\n",
            encoding="utf8",
        )
        self.app = create_app(chaoxing_factory=FakeChaoxing)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        gc.COOKIES_PATH = self.old_cookie_path
        self.tempdir.cleanup()

    def write_cookie_file(self):
        Path(gc.COOKIES_PATH).write_text("_uid=1;fid=2", encoding="utf8")

    def test_task_status_empty(self):
        resp = self.client.get("/task/status")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])

    def test_task_start_without_cookies(self):
        resp = self.client.post("/task/start", data={
            "courseId": "1", "clazzId": "2", "cpi": "3"
        })
        self.assertEqual(resp.status_code, 401)

    def test_task_start_missing_params(self):
        self.write_cookie_file()
        resp = self.client.post("/task/start", data={"courseId": "1"})
        self.assertEqual(resp.status_code, 400)

    def test_task_stop_without_active(self):
        resp = self.client.post("/task/stop")
        self.assertEqual(resp.status_code, 404)

    def test_task_progress_sse(self):
        resp = self.client.get("/task/progress")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/event-stream", resp.content_type)


class ConfigApiTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tempdir.name) / "config.ini"
        self.config_path.write_text(
            "[common]\nusername = test\npassword = pass\nspeed = 1\n\n"
            "[tiku]\nprovider = TikuYanxi\n\n"
            "[notification]\nprovider =\n",
            encoding="utf8",
        )
        self.old_cookie_path = gc.COOKIES_PATH
        gc.COOKIES_PATH = str(Path(self.tempdir.name) / "cookies.txt")

        # Patch ConfigManager to use our temp config
        with patch("api.config_manager.CONFIG_PATH", str(self.config_path)):
            from app import create_app
            self.app = create_app(chaoxing_factory=FakeChaoxing)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        gc.COOKIES_PATH = self.old_cookie_path
        self.tempdir.cleanup()

    def test_config_schema(self):
        resp = self.client.get("/config/schema")
        self.assertEqual(resp.status_code, 200)
        schema = resp.get_json()
        self.assertIn("common", schema)
        self.assertIn("tiku", schema)
        self.assertIn("notification", schema)

    def test_config_read_section(self):
        resp = self.client.get("/config/tiku")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("provider"), "TikuYanxi")

    def test_config_read_unknown(self):
        resp = self.client.get("/config/unknown")
        self.assertEqual(resp.status_code, 404)

    def test_config_save_section(self):
        resp = self.client.post("/config/tiku",
                                json={"provider": "AI", "endpoint": "https://api.test.com/v1"},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json().get("ok"))

        # Verify saved
        resp2 = self.client.get("/config/tiku")
        self.assertEqual(resp2.get_json().get("provider"), "AI")

    def test_config_save_filters_unknown_keys(self):
        resp = self.client.post("/config/common",
                                json={"username": "new", "evil_key": "hack"},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)

        resp2 = self.client.get("/config/common")
        data = resp2.get_json()
        self.assertEqual(data.get("username"), "new")
        self.assertNotIn("evil_key", data)


if __name__ == "__main__":
    unittest.main()
