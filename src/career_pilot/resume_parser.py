from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_PARAGRAPH = f"{{{W_NS}}}p"
W_TEXT = f"{{{W_NS}}}t"

SECTION_HEADINGS = {
    "教育背景",
    "实习经历",
    "项目经历",
    "技能掌握",
    "校园经历",
    "获奖经历",
}


@dataclass(frozen=True)
class ResumeEvidence:
    evidence_id: str
    text: str
    kind: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "text": self.text,
            "kind": self.kind,
        }


def _nearest_paragraph(
    element: ET.Element, parent_map: Dict[ET.Element, ET.Element]
) -> Optional[ET.Element]:
    current = parent_map.get(element)
    while current is not None:
        if current.tag == W_PARAGRAPH:
            return current
        current = parent_map.get(current)
    return None


def _normalize_text(text: str) -> str:
    return re.sub(r"[\s\u00a0]+", " ", text).strip()


def _is_private_header(text: str) -> bool:
    if text == "候选人":
        return True
    if "电话：" in text or "邮箱：" in text:
        return True
    return False


def extract_docx_paragraphs(path: Path) -> List[str]:
    """Extract visible paragraph text from a DOCX, including text boxes.

    Word may nest text-box paragraphs inside a drawing paragraph. Each text node is
    assigned only to its nearest paragraph, which prevents an entire text box from
    being duplicated as one giant outer paragraph.
    """

    if path.suffix.lower() != ".docx":
        raise ValueError("简历文件必须是 .docx")
    if not path.exists():
        raise FileNotFoundError(f"找不到简历文件：{path}")

    with zipfile.ZipFile(path) as archive:
        try:
            document_xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError("DOCX 中缺少 word/document.xml") from exc

    root = ET.fromstring(document_xml)
    parent_map = {child: parent for parent in root.iter() for child in parent}

    paragraphs: List[str] = []
    seen = set()
    for paragraph in root.iter(W_PARAGRAPH):
        segments = [
            node.text or ""
            for node in paragraph.iter(W_TEXT)
            if _nearest_paragraph(node, parent_map) is paragraph
        ]
        text = _normalize_text("".join(segments))
        if not text or _is_private_header(text) or text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)
    return paragraphs


def build_resume_evidence(path: Path) -> Dict[str, object]:
    paragraphs = extract_docx_paragraphs(path)
    evidence = [
        ResumeEvidence(
            evidence_id=f"R{index:03d}",
            text=text,
            kind="section_heading" if text in SECTION_HEADINGS else "resume_text",
        )
        for index, text in enumerate(paragraphs, start=1)
    ]
    return {
        "schema_version": 1,
        "source_file": path.name,
        "privacy_status": "sanitized",
        "evidence_count": len(evidence),
        "evidence": [item.to_dict() for item in evidence],
    }


def save_resume_evidence(path: Path, output: Path) -> Dict[str, object]:
    payload = build_resume_evidence(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
