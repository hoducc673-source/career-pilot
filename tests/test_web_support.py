from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from career_pilot.web_support import (
    MAX_RESUME_BYTES,
    build_profile,
    find_job,
    load_starting_profile,
    parse_uploaded_resume,
)


class WebSupportTests(unittest.TestCase):
    def test_loads_private_profile_before_public_example(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "samples").mkdir()
            (root / "data/private").mkdir(parents=True)
            base = {
                "graduation_cohort": "2029",
                "education_level": "本科",
                "target_cities": ["青岛"],
                "internship_days_per_week": 5,
                "internship_duration_months_min": 3,
                "rag_experience": "project",
                "scores": {
                    "analysis": 3,
                    "communication": 4,
                    "detail": 3,
                    "coding": 5,
                    "research": 3,
                    "sales": 4,
                    "uncertainty": 3,
                },
            }
            (root / "samples/profile.example.json").write_text(
                json.dumps({"major": "示例专业", **base}), encoding="utf-8"
            )
            (root / "data/private/profile.json").write_text(
                json.dumps({"major": "金融学", **base}), encoding="utf-8"
            )
            profile, source = load_starting_profile(root)
            self.assertEqual(profile.major, "金融学")
            self.assertEqual(source, "本地私密画像")

    def test_build_profile_validates_scores(self):
        with self.assertRaisesRegex(ValueError, "analysis"):
            build_profile(
                major="金融学",
                graduation_cohort="2029",
                education_level="本科",
                target_cities=["青岛"],
                primary_direction="unknown",
                secondary_direction="unknown",
                internship_days_per_week=5,
                internship_duration_months_min=3,
                rag_experience="project",
                scores={
                    "analysis": 6,
                    "communication": 4,
                    "detail": 3,
                    "coding": 5,
                    "research": 3,
                    "sales": 4,
                    "uncertainty": 3,
                },
            )

    def test_uploaded_resume_uses_neutral_temporary_filename(self):
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>项目经历</w:t></w:r></w:p></w:body>
        </w:document>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)
            payload = parse_uploaded_resume(path.read_bytes())
        self.assertEqual(payload["source_file"], "resume.docx")
        self.assertEqual(payload["evidence_count"], 1)

    def test_rejects_oversized_resume_before_parsing(self):
        with self.assertRaisesRegex(ValueError, "5 MB"):
            parse_uploaded_resume(b"x" * (MAX_RESUME_BYTES + 1))

    def test_find_job_rejects_unknown_id(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            find_job([{"id": "known"}], "missing")


if __name__ == "__main__":
    unittest.main()
