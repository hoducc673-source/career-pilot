from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_app_renders_core_tabs_without_exception(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(
            [tab.label for tab in app.tabs],
            ["方向探索", "岗位雷达", "简历匹配", "知识问答"],
        )
        self.assertIn(
            "费用保护：本会话剩余 3 次模型请求；服务器每日总上限 12 次。",
            [caption.value for caption in app.caption],
        )


if __name__ == "__main__":
    unittest.main()
