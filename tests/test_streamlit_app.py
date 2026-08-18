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
            ["方向探索", "岗位雷达", "简历匹配", "投递看板", "知识问答"],
        )
        self.assertIn(
            "费用保护：本会话剩余 3 次模型请求；服务器每日总上限 12 次。",
            [caption.value for caption in app.caption],
        )

    def test_custom_jd_entry_is_available_without_model_call(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()
        source_radio = next(item for item in app.radio if item.label == "岗位来源")
        source_radio.set_value("粘贴新 JD").run()

        self.assertEqual(list(app.exception), [])
        self.assertIn("粘贴招聘 JD", [item.label for item in app.text_area])
        self.assertIn("本地解析这份 JD", [item.label for item in app.button])

    def test_parsed_custom_jd_joins_match_job_options(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()
        next(item for item in app.radio if item.label == "岗位来源").set_value("粘贴新 JD").run()
        jd = """
        公司：测试科技
        岗位：数据分析实习生
        工作地点：上海
        岗位职责：
        1. 整理业务数据并输出分析报告
        任职要求：
        1. 2029届本科及以上
        2. 每周至少4天，连续3个月以上
        """
        next(item for item in app.text_area if item.label == "粘贴招聘 JD").set_value(jd)
        next(item for item in app.button if item.label == "本地解析这份 JD").click().run()

        self.assertEqual(list(app.exception), [])
        target = next(item for item in app.selectbox if item.label == "目标岗位")
        self.assertTrue(any(str(option).startswith("本次 JD｜测试科技") for option in target.options))
        self.assertTrue(str(target.value).startswith("本次 JD｜测试科技"))

    def test_job_can_be_added_to_application_tracker(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()
        next(item for item in app.button if item.label == "加入看板").click().run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(any("已将岗位加入收藏阶段" in item.value for item in app.success))
        self.assertTrue(any(item.label.startswith("收藏 ｜ 中瑞集团") for item in app.expander))


if __name__ == "__main__":
    unittest.main()
