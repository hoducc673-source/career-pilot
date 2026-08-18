from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

from .models import CareerProfile
from .resume_parser import build_resume_evidence


MAX_RESUME_BYTES = 5 * 1024 * 1024


def load_starting_profile(root: Path) -> Tuple[CareerProfile, str]:
    """Load a private local profile when present, otherwise the public demo profile."""

    candidates = (
        (root / "data/private/profile.json", "本地私密画像"),
        (root / "samples/profile.example.json", "公开示例画像"),
    )
    for path, label in candidates:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return CareerProfile.from_dict(raw), label
    raise FileNotFoundError("找不到可用画像：请创建 data/private/profile.json 或保留示例画像")


def build_profile(
    *,
    major: str,
    graduation_cohort: str,
    education_level: str,
    target_cities: List[str],
    primary_direction: str,
    secondary_direction: str,
    internship_days_per_week: int,
    internship_duration_months_min: int,
    rag_experience: str,
    scores: Dict[str, int],
) -> CareerProfile:
    return CareerProfile.from_dict(
        {
            "major": major,
            "graduation_cohort": graduation_cohort,
            "education_level": education_level,
            "target_cities": target_cities,
            "primary_direction": primary_direction,
            "secondary_direction": secondary_direction,
            "internship_days_per_week": internship_days_per_week,
            "internship_duration_months_min": internship_duration_months_min,
            "rag_experience": rag_experience,
            "scores": scores,
        }
    )


def parse_uploaded_resume(content: bytes) -> Dict[str, object]:
    """Parse a DOCX in an ephemeral directory without retaining its original name."""

    if not content:
        raise ValueError("上传的简历为空")
    if len(content) > MAX_RESUME_BYTES:
        raise ValueError("简历文件不能超过 5 MB")
    with tempfile.TemporaryDirectory(prefix="careerpilot-resume-") as temp_dir:
        resume_path = Path(temp_dir) / "resume.docx"
        resume_path.write_bytes(content)
        return build_resume_evidence(resume_path)


def find_job(jobs: List[Dict[str, object]], job_id: str) -> Dict[str, object]:
    for job in jobs:
        if job.get("id") == job_id:
            return job
    raise ValueError(f"没有找到岗位：{job_id}")
