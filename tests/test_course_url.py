import unittest

from api.course_url import match_course, parse_course_url


class CourseUrlTest(unittest.TestCase):
    def test_parse_course_url_query_params(self):
        parsed = parse_course_url(
            "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse"
            "?courseid=100&clazzid=200&cpi=300&ut=s"
        )

        self.assertTrue(parsed.is_complete)
        self.assertEqual(parsed.course_id, "100")
        self.assertEqual(parsed.clazz_id, "200")
        self.assertEqual(parsed.cpi, "300")

    def test_parse_course_url_case_insensitive_keys(self):
        parsed = parse_course_url("courseId=abc&clazzId=def&CPI=ghi")

        self.assertTrue(parsed.is_complete)
        self.assertEqual(parsed.as_course_params(), {
            "courseId": "abc",
            "clazzId": "def",
            "cpi": "ghi",
        })

    def test_parse_course_url_reports_missing_params(self):
        parsed = parse_course_url("https://example.com/?courseid=100")

        self.assertFalse(parsed.is_complete)
        self.assertEqual(parsed.missing, ("clazzId", "cpi"))

    def test_parse_course_url_from_fragment(self):
        parsed = parse_course_url("https://example.com/#/course?courseid=1&clazzid=2&cpi=3")

        self.assertTrue(parsed.is_complete)
        self.assertEqual(parsed.course_id, "1")
        self.assertEqual(parsed.clazz_id, "2")
        self.assertEqual(parsed.cpi, "3")

    def test_match_course_requires_all_params(self):
        parsed = parse_course_url("courseid=1&clazzid=2&cpi=3")
        courses = [
            {"title": "A", "courseId": "1", "clazzId": "9", "cpi": "3"},
            {"title": "B", "courseId": "1", "clazzId": "2", "cpi": "3"},
        ]

        self.assertEqual(match_course(parsed, courses)["title"], "B")


if __name__ == "__main__":
    unittest.main()
