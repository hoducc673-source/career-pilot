import tempfile
import unittest
import zipfile
from pathlib import Path

from career_pilot.resume_parser import build_resume_evidence, extract_docx_paragraphs


DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>候选人</w:t></w:r></w:p>
    <w:p><w:r><w:t>电话：＊＊＊＊丨邮箱：＊＊＊＊</w:t></w:r></w:p>
    <w:p>
      <w:r><w:t>外层</w:t></w:r>
      <w:r><w:drawing><w:p><w:r><w:t>项目经历</w:t></w:r></w:p></w:drawing></w:r>
    </w:p>
    <w:p><w:r><w:t>Python</w:t></w:r></w:p>
    <w:p><w:r><w:t>Python</w:t></w:r></w:p>
  </w:body>
</w:document>
"""


class ResumeParserTests(unittest.TestCase):
    def _make_docx(self, directory: str) -> Path:
        path = Path(directory) / "resume.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", DOCUMENT_XML)
        return path

    def test_extracts_nested_text_box_without_outer_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._make_docx(directory)
            self.assertEqual(
                extract_docx_paragraphs(path),
                ["外层", "项目经历", "Python"],
            )

    def test_builds_stable_evidence_ids_and_filters_private_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._make_docx(directory)
            payload = build_resume_evidence(path)
            self.assertEqual(payload["privacy_status"], "sanitized")
            self.assertEqual(payload["evidence_count"], 3)
            self.assertEqual(payload["evidence"][0]["evidence_id"], "R001")
            self.assertEqual(payload["evidence"][1]["kind"], "section_heading")


if __name__ == "__main__":
    unittest.main()
