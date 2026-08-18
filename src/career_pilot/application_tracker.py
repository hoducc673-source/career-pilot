from __future__ import annotations

import csv
import io
import re
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence


MAX_CSV_BYTES = 1_000_000
STATUS_ORDER = ("saved", "preparing", "applied", "interview", "offer", "closed")
STATUS_LABELS = {
    "saved": "收藏",
    "preparing": "准备中",
    "applied": "已投递",
    "interview": "面试中",
    "offer": "Offer",
    "closed": "已结束",
}
STATUS_ALIASES = {label: value for value, label in STATUS_LABELS.items()}
CSV_FIELDS = (
    "id",
    "company",
    "title",
    "city",
    "status",
    "deadline",
    "next_action",
    "resume_version",
    "source_url",
    "notes",
    "created_at",
    "updated_at",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: object, field: str, *, required: bool = False, limit: int = 500) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field} 不能为空")
    if len(text) > limit:
        raise ValueError(f"{field} 不能超过 {limit} 个字符")
    return text


def _iso_date(value: object, field: str) -> str:
    text = _text(value, field, limit=10)
    if not text:
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD 格式") from error


def _source_url(value: object) -> str:
    url = _text(value, "source_url", limit=1_000)
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        raise ValueError("source_url 必须以 http:// 或 https:// 开头")
    return url


def validate_application(raw: Dict[str, object]) -> Dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("投递记录必须是对象")
    status_raw = _text(raw.get("status", "saved"), "status", required=True, limit=20)
    status = STATUS_ALIASES.get(status_raw, status_raw)
    if status not in STATUS_ORDER:
        raise ValueError(f"未知投递状态：{status_raw}")

    record_id = _text(raw.get("id"), "id", limit=64)
    if not record_id:
        record_id = "app-" + uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", record_id):
        raise ValueError("id 格式不合法")

    now = _now_iso()
    return {
        "id": record_id,
        "company": _text(raw.get("company"), "company", required=True, limit=120),
        "title": _text(raw.get("title"), "title", required=True, limit=160),
        "city": _text(raw.get("city"), "city", limit=80),
        "status": status,
        "deadline": _iso_date(raw.get("deadline"), "deadline"),
        "next_action": _text(raw.get("next_action"), "next_action", limit=300),
        "resume_version": _text(raw.get("resume_version"), "resume_version", limit=120),
        "source_url": _source_url(raw.get("source_url")),
        "notes": _text(raw.get("notes"), "notes", limit=2_000),
        "created_at": _text(raw.get("created_at"), "created_at", limit=64) or now,
        "updated_at": now,
    }


def create_application(
    *,
    company: str,
    title: str,
    city: str = "",
    status: str = "saved",
    deadline: str = "",
    next_action: str = "",
    resume_version: str = "",
    source_url: str = "",
    notes: str = "",
) -> Dict[str, str]:
    return validate_application(
        {
            "company": company,
            "title": title,
            "city": city,
            "status": status,
            "deadline": deadline,
            "next_action": next_action,
            "resume_version": resume_version,
            "source_url": source_url,
            "notes": notes,
        }
    )


def application_from_job(job: Dict[str, object]) -> Dict[str, str]:
    cities = job.get("cities", [])
    city = "、".join(str(item) for item in cities) if isinstance(cities, list) else str(cities)
    return create_application(
        company=str(job.get("company", "")),
        title=str(job.get("title", "")),
        city=city,
        source_url=str(job.get("source_url", "")),
        next_action="核验投递截止时间，并针对 JD 定制简历。",
    )


def find_duplicate(records: Sequence[Dict[str, str]], candidate: Dict[str, str]) -> Optional[str]:
    identity = (
        candidate["company"].casefold(),
        candidate["title"].casefold(),
        candidate["city"].casefold(),
    )
    for record in records:
        if record.get("status") == "closed":
            continue
        existing = (
            str(record.get("company", "")).casefold(),
            str(record.get("title", "")).casefold(),
            str(record.get("city", "")).casefold(),
        )
        if existing == identity:
            return str(record.get("id", ""))
    return None


def upsert_application(
    records: Sequence[Dict[str, str]], candidate: Dict[str, object]
) -> List[Dict[str, str]]:
    validated = validate_application(candidate)
    result: List[Dict[str, str]] = []
    replaced = False
    for record in records:
        if record.get("id") == validated["id"]:
            validated["created_at"] = str(record.get("created_at", validated["created_at"]))
            result.append(validated)
            replaced = True
        else:
            result.append(dict(record))
    if not replaced:
        result.append(validated)
    return result


def remove_application(records: Sequence[Dict[str, str]], record_id: str) -> List[Dict[str, str]]:
    return [dict(record) for record in records if record.get("id") != record_id]


def summarize_applications(
    records: Sequence[Dict[str, str]], *, today: Optional[date] = None
) -> Dict[str, int]:
    current = today or date.today()
    counts = Counter(str(record.get("status", "")) for record in records)
    overdue = 0
    due_soon = 0
    for record in records:
        deadline_raw = str(record.get("deadline", ""))
        if not deadline_raw or record.get("status") in {"offer", "closed"}:
            continue
        try:
            deadline = date.fromisoformat(deadline_raw)
        except ValueError:
            continue
        if deadline < current:
            overdue += 1
        elif deadline <= current + timedelta(days=7):
            due_soon += 1
    return {
        "total": len(records),
        "active": sum(counts[status] for status in ("saved", "preparing", "applied", "interview")),
        "interview": counts["interview"],
        "offer": counts["offer"],
        "overdue": overdue,
        "due_soon": due_soon,
        **{status: counts[status] for status in STATUS_ORDER},
    }


def _safe_csv_cell(value: str) -> str:
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def applications_to_csv(records: Sequence[Dict[str, str]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        validated = validate_application(dict(record))
        validated["created_at"] = str(record.get("created_at", validated["created_at"]))
        validated["updated_at"] = str(record.get("updated_at", validated["updated_at"]))
        writer.writerow({key: _safe_csv_cell(validated[key]) for key in CSV_FIELDS})
    return "\ufeff" + output.getvalue()


def applications_from_csv(payload: bytes) -> List[Dict[str, str]]:
    if len(payload) > MAX_CSV_BYTES:
        raise ValueError("CSV 超过 1 MB，请删除无关行后重试")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV 必须是 UTF-8 编码") from error
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV 缺少表头")
    missing = {"company", "title", "status"} - set(reader.fieldnames)
    if missing:
        raise ValueError(f"CSV 缺少字段：{sorted(missing)}")

    records: List[Dict[str, str]] = []
    seen_ids = set()
    for index, raw in enumerate(reader, start=2):
        if not any(str(value or "").strip() for value in raw.values()):
            continue
        try:
            record = validate_application({key: raw.get(key, "") for key in CSV_FIELDS})
        except ValueError as error:
            raise ValueError(f"CSV 第 {index} 行：{error}") from error
        if record["id"] in seen_ids:
            raise ValueError(f"CSV 第 {index} 行的 id 重复")
        seen_ids.add(record["id"])
        record["created_at"] = str(raw.get("created_at", "")).strip() or record["created_at"]
        record["updated_at"] = str(raw.get("updated_at", "")).strip() or record["updated_at"]
        records.append(record)
    return records
