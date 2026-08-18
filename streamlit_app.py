from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from career_pilot.config import load_env_file
from career_pilot.deepseek_client import DeepSeekClient, DeepSeekError, DeepSeekSettings
from career_pilot.engine import explore
from career_pilot.jd_analyzer import demo_analysis
from career_pilot.job_catalog import load_catalog
from career_pilot.models import CareerProfile, DIMENSION_LABELS
from career_pilot.rag_answerer import answer_with_model
from career_pilot.rag_index import LexicalRetriever, build_knowledge_base
from career_pilot.report_renderer import (
    CONFIDENCE_LABELS,
    DECISION_LABELS,
    HARD_STATUS_LABELS,
    render_match_report,
)
from career_pilot.resume_matcher import match_with_model
from career_pilot.usage_guard import DailyUsageGuard, UsageLimitError
from career_pilot.web_support import build_profile, load_starting_profile, parse_uploaded_resume


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "data/jobs/seed_jobs.json"
REPO_URL = "https://github.com/hoducc673-source/career-pilot"

ROLE_LABELS = {
    "data_analysis": "数据分析",
    "product": "产品",
    "operations": "运营",
}
RAG_LABELS = {
    "unknown": "待确认",
    "none": "暂无",
    "learning": "学习中",
    "project": "做过项目",
    "work": "工作经验",
}
RAG_VALUES = {label: value for value, label in RAG_LABELS.items()}
DEFAULT_SESSION_API_LIMIT = 3
DEFAULT_DAILY_API_LIMIT = 12
SESSION_USAGE_KEY = "deepseek_requests_used"


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --ink: #112D3D;
          --muted: #5C7180;
          --fog: #F4F7F9;
          --panel: #FFFFFF;
          --line: #C9D5DD;
          --signal: #E9653B;
          --sea: #176B87;
          --mint: #BFDCCF;
        }
        .stApp {
          background-color: var(--fog);
          background-image:
            linear-gradient(rgba(17,45,61,.035) 1px, transparent 1px),
            linear-gradient(90deg, rgba(17,45,61,.035) 1px, transparent 1px);
          background-size: 28px 28px;
          color: var(--ink);
        }
        .block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
        h1, h2, h3 { color: var(--ink); letter-spacing: -.025em; }
        h1, h2 { font-family: "Songti SC", "STSong", serif; }
        code { font-family: "SFMono-Regular", Menlo, monospace; }
        .cp-kicker, .cp-route-label, .cp-stat-label {
          font-family: "Avenir Next", Avenir, "Helvetica Neue", Arial, sans-serif;
          font-weight: 650;
        }
        .cp-hero {
          border-top: 5px solid var(--signal);
          border-bottom: 1px solid var(--line);
          padding: 1.8rem 0 1.45rem;
          margin-bottom: 1.1rem;
        }
        .cp-kicker {
          color: var(--sea); font-size: .72rem; letter-spacing: .14em;
          text-transform: uppercase; margin-bottom: .7rem;
        }
        .cp-title {
          font-family: "Songti SC", "STSong", serif;
          font-size: clamp(2.55rem, 7vw, 5.6rem);
          line-height: .98; letter-spacing: -.06em; margin: 0;
        }
        .cp-title em { color: var(--signal); font-style: normal; }
        .cp-subtitle { max-width: 720px; color: var(--muted); font-size: 1.03rem; margin-top: 1rem; }
        .cp-route {
          display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
          border: 1px solid var(--line); background: rgba(255,255,255,.76);
          margin: 1rem 0 1.6rem;
        }
        .cp-route-step { padding: .9rem 1rem; border-right: 1px solid var(--line); min-height: 82px; }
        .cp-route-step:last-child { border-right: 0; }
        .cp-route-label { color: var(--signal); font-size: .68rem; letter-spacing: .1em; }
        .cp-route-value { color: var(--ink); font-weight: 650; margin-top: .35rem; }
        .cp-card {
          background: rgba(255,255,255,.88); border: 1px solid var(--line);
          border-radius: 3px; padding: 1rem 1.1rem; margin: .55rem 0;
          box-shadow: 0 10px 30px rgba(17,45,61,.045);
        }
        .cp-card.signal { border-left: 4px solid var(--signal); }
        .cp-card.sea { border-left: 4px solid var(--sea); }
        .cp-card-title { font-weight: 700; color: var(--ink); }
        .cp-card-copy { color: var(--muted); margin-top: .35rem; }
        .cp-badge {
          display: inline-block; padding: .18rem .48rem; border: 1px solid var(--line);
          border-radius: 99px; font-size: .75rem; margin-right: .32rem;
          color: var(--sea); background: white;
        }
        .cp-privacy {
          background: #E8F2ED; border: 1px solid #BFDCCF; padding: .85rem 1rem;
          color: #244D3D; margin: .7rem 0 1rem;
        }
        .cp-source {
          border-left: 2px solid var(--sea); padding: .35rem .8rem; margin: .65rem 0;
          color: var(--muted); font-size: .9rem;
        }
        div[data-testid="stMetric"] {
          background: rgba(255,255,255,.84); border: 1px solid var(--line); padding: .75rem;
        }
        div[data-testid="stTabs"] button { font-weight: 650; }
        .stButton > button, .stDownloadButton > button { border-radius: 2px; min-height: 2.8rem; }
        .stButton > button[kind="primary"] { background: var(--signal); border-color: var(--signal); }
        a { color: var(--sea); }
        @media (max-width: 760px) {
          .cp-route { grid-template-columns: 1fr 1fr; }
          .cp-route-step:nth-child(2) { border-right: 0; }
          .cp-route-step:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
          .cp-title { letter-spacing: -.04em; }
        }
        @media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def load_jobs() -> List[Dict[str, object]]:
    return load_catalog(CATALOG_PATH)


@st.cache_resource
def load_retriever() -> LexicalRetriever:
    return LexicalRetriever(build_knowledge_base(ROOT))


def model_is_configured() -> bool:
    try:
        load_env_file(ROOT / ".env")
    except ValueError:
        return False
    try:
        for key in (
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_BASE_URL",
            "DEEPSEEK_MODEL",
            "PUBLIC_SESSION_API_LIMIT",
            "PUBLIC_DAILY_API_LIMIT",
        ):
            if key in st.secrets and not os.environ.get(key):
                os.environ[key] = str(st.secrets[key])
    except StreamlitSecretNotFoundError:
        pass
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def _positive_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 1 else default


def session_api_limit() -> int:
    model_is_configured()
    return _positive_env_int("PUBLIC_SESSION_API_LIMIT", DEFAULT_SESSION_API_LIMIT)


def daily_api_limit() -> int:
    model_is_configured()
    return _positive_env_int("PUBLIC_DAILY_API_LIMIT", DEFAULT_DAILY_API_LIMIT)


@st.cache_resource
def get_daily_usage_guard(limit: int) -> DailyUsageGuard:
    return DailyUsageGuard(limit)


def reserve_model_request() -> None:
    session_limit = session_api_limit()
    session_used = int(st.session_state.get(SESSION_USAGE_KEY, 0))
    if session_used >= session_limit:
        raise UsageLimitError(
            f"本次浏览器会话的 {session_limit} 次 DeepSeek 请求已用完；"
            "离线方向探索、岗位雷达和本地检索仍可继续使用。"
        )
    reservation = get_daily_usage_guard(daily_api_limit()).reserve()
    if not reservation.allowed:
        raise UsageLimitError(
            "公开演示今天的 DeepSeek 总额度已用完；请明天再试，离线功能不受影响。"
        )
    st.session_state[SESSION_USAGE_KEY] = session_used + 1


class GuardedDeepSeekClient:
    def __init__(self, delegate: DeepSeekClient):
        self.delegate = delegate

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, object]:
        reserve_model_request()
        return self.delegate.generate_json(system_prompt, user_prompt)


def get_client() -> GuardedDeepSeekClient:
    return GuardedDeepSeekClient(DeepSeekClient(DeepSeekSettings.from_env()))


def profile_controls(starting: CareerProfile, source_label: str) -> CareerProfile:
    with st.sidebar:
        st.markdown("### 候选人画像")
        st.caption(f"当前来源：{source_label}。修改只保留在本次网页会话。")
        major = st.text_input("专业", value=starting.major)
        graduation = st.text_input("毕业年份", value=starting.graduation_cohort)
        education = st.selectbox(
            "学历",
            ["本科", "硕士", "博士", "专科"],
            index=["本科", "硕士", "博士", "专科"].index(starting.education_level)
            if starting.education_level in {"本科", "硕士", "博士", "专科"}
            else 0,
        )
        cities = st.multiselect(
            "目标城市",
            ["青岛", "上海", "北京", "杭州", "深圳", "广州"],
            default=[city for city in starting.target_cities if city in {"青岛", "上海", "北京", "杭州", "深圳", "广州"}],
        )
        days = st.slider("每周可实习天数", 0, 7, starting.internship_days_per_week)
        months = st.number_input(
            "最短连续实习月数", min_value=0, max_value=24,
            value=starting.internship_duration_months_min, step=1,
        )
        rag_label = st.selectbox(
            "RAG 经历",
            list(RAG_VALUES),
            index=list(RAG_VALUES).index(RAG_LABELS.get(starting.rag_experience, "待确认")),
        )
        with st.expander("能力自评（1–5）"):
            scores = {
                key: st.slider(label, 1, 5, starting.scores[key], key=f"score_{key}")
                for key, label in DIMENSION_LABELS.items()
            }
        st.divider()
        st.caption("模型固定使用 DeepSeek V4 Pro；只有点击生成按钮才会产生 API 请求。")
        st.success("DeepSeek 已配置" if model_is_configured() else "当前仅可使用离线功能")
        session_limit = session_api_limit()
        session_used = int(st.session_state.get(SESSION_USAGE_KEY, 0))
        st.caption(
            f"费用保护：本会话剩余 {max(0, session_limit - session_used)} 次模型请求；"
            f"服务器每日总上限 {daily_api_limit()} 次。"
        )
        st.markdown(f"[查看项目源码]({REPO_URL})")

    return build_profile(
        major=major,
        graduation_cohort=graduation,
        education_level=education,
        target_cities=cities,
        primary_direction=starting.primary_direction,
        secondary_direction=starting.secondary_direction,
        internship_days_per_week=days,
        internship_duration_months_min=int(months),
        rag_experience=RAG_VALUES[rag_label],
        scores=scores,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="cp-hero">
          <div class="cp-kicker">CareerPilot / Evidence-first career agent</div>
          <h1 class="cp-title">先找证据，<br><em>再做判断。</em></h1>
          <p class="cp-subtitle">
            面向应届生的求职智能体。它不会替你编经历，而是把职业画像、真实 JD、
            脱敏简历和知识库原文连成一条可追踪的证据航线。
          </p>
        </section>
        <div class="cp-route" aria-label="证据处理流程">
          <div class="cp-route-step"><div class="cp-route-label">01 / PROFILE</div><div class="cp-route-value">候选人画像</div></div>
          <div class="cp-route-step"><div class="cp-route-label">02 / JOB</div><div class="cp-route-value">真实岗位要求</div></div>
          <div class="cp-route-step"><div class="cp-route-label">03 / EVIDENCE</div><div class="cp-route-value">简历与检索原文</div></div>
          <div class="cp-route-step"><div class="cp-route-label">04 / DECISION</div><div class="cp-route-value">带引用的行动建议</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_direction_tab(profile: CareerProfile) -> None:
    st.subheader("职业方向探索")
    st.caption("分数只用于方向排序，不代表录用概率。修改左侧画像后，结果会立即更新。")
    results = explore(profile, limit=3)
    columns = st.columns(3)
    for index, (column, result) in enumerate(zip(columns, results), start=1):
        with column:
            st.metric(f"候选方向 {index}", f"{result.score}/100")
            st.markdown(
                f'<div class="cp-card signal"><div class="cp-card-title">{result.name}</div>'
                f'<div class="cp-card-copy">{result.experiment}</div></div>',
                unsafe_allow_html=True,
            )
            with st.expander("查看依据与风险"):
                st.markdown("**支持证据**")
                for item in result.reasons:
                    st.write(f"- {item}")
                st.markdown("**待验证风险**")
                for item in result.risks:
                    st.write(f"- {item}")


def render_job_tab(profile: CareerProfile, jobs: List[Dict[str, object]]) -> None:
    st.subheader("岗位雷达")
    left, right = st.columns([1, 1])
    with left:
        family_label = st.selectbox("岗位方向", ["全部", "数据分析", "产品", "运营"])
    with right:
        city = st.selectbox("城市", ["全部", "青岛", "上海", "北京", "杭州"])

    family_value = {label: value for value, label in ROLE_LABELS.items()}.get(family_label)
    filtered = [
        job for job in jobs
        if (family_value is None or job["role_family"] == family_value)
        and (city == "全部" or city in job["cities"])
    ]
    st.caption(f"找到 {len(filtered)} 个岗位。岗位信息来自公开页面快照，投递前仍需打开来源复核。")
    if not filtered:
        st.info("当前筛选条件下没有岗位，请更换方向或城市。")
        return

    labels = {f"{job['company']}｜{job['title']}｜{'、'.join(job['cities'])}": job for job in filtered}
    selected_label = st.selectbox("选择岗位", list(labels))
    job = labels[selected_label]
    analysis = demo_analysis(profile, job)

    col1, col2, col3 = st.columns(3)
    col1.metric("离线初筛", DECISION_LABELS.get(str(analysis["decision"]), str(analysis["decision"])))
    col2.metric("岗位族", ROLE_LABELS.get(str(job["role_family"]), str(job["role_family"])))
    col3.metric("来源状态", "已记录" if job["source_status"] == "page_available" else str(job["source_status"]))

    st.markdown(f"**职责**　{'　/　'.join(job['responsibilities'])}")
    st.markdown("**岗位要求**")
    for requirement in job["requirements"]:
        st.write(f"- {requirement}")

    st.markdown("**硬门槛基线**")
    for item in analysis["hard_requirements"]:
        status = HARD_STATUS_LABELS.get(str(item["status"]), str(item["status"]))
        st.markdown(
            f'<div class="cp-card sea"><span class="cp-badge">{status}</span>'
            f'<span class="cp-card-title">{item["requirement"]}</span>'
            f'<div class="cp-card-copy">证据：{"、".join(item["evidence_refs"])}</div></div>',
            unsafe_allow_html=True,
        )
    st.link_button("打开岗位来源", str(job["source_url"]))


def render_match_tab(profile: CareerProfile, jobs: List[Dict[str, object]]) -> None:
    st.subheader("简历 × 岗位证据匹配")
    st.markdown(
        '<div class="cp-privacy"><strong>隐私检查点</strong>　文件只在临时目录解析，不写入项目；'
        '但点击“生成匹配报告”后，提取出的脱敏文本会发送给 DeepSeek。</div>',
        unsafe_allow_html=True,
    )
    labels = {f"{job['company']}｜{job['title']}｜{'、'.join(job['cities'])}": job for job in jobs}
    selected = st.selectbox("目标岗位", list(labels), key="match_job")
    job = labels[selected]
    uploaded = st.file_uploader("上传脱敏 DOCX 简历（不超过 5 MB）", type=["docx"])
    resume_payload = None
    if uploaded is not None:
        try:
            resume_payload = parse_uploaded_resume(uploaded.getvalue())
            st.success(f"本地解析完成：提取 {resume_payload['evidence_count']} 条证据，文件未持久化保存。")
            with st.expander("预览将发送的脱敏文本"):
                for item in resume_payload["evidence"]:
                    st.write(f"`resume.{item['evidence_id']}`　{item['text']}")
        except (OSError, ValueError) as error:
            st.error(f"简历解析失败：{error}")

    consent = st.checkbox("我确认这是脱敏简历，并同意将上述文本发送给 DeepSeek 生成报告。")
    can_run = resume_payload is not None and consent and model_is_configured()
    if st.button("生成匹配报告", type="primary", disabled=not can_run, use_container_width=True):
        try:
            with st.spinner("正在核对硬门槛、匹配证据与表达风险……"):
                match = match_with_model(profile, job, resume_payload, get_client())
                report = render_match_report(match, profile, job, resume_payload)
            st.session_state["latest_match_report"] = report
            st.session_state["latest_match_summary"] = match
            st.session_state["latest_match_job_id"] = str(job["id"])
        except UsageLimitError as error:
            st.warning(str(error))
        except DeepSeekError as error:
            st.error("DeepSeek 服务调用失败，请检查网络、API Key 或账户余额后重试。")
            with st.expander("查看技术详情"):
                st.code(str(error))
        except ValueError as error:
            st.error("模型已经响应，但回答未通过证据校验；本次没有生成或保存不可靠报告。")
            with st.expander("查看技术详情"):
                st.code(str(error))

    if not model_is_configured():
        st.info("尚未配置 DeepSeek API Key；可先体验其他三个离线功能。")
    elif uploaded is None:
        st.caption("上传脱敏简历后才能生成报告。")
    elif not consent:
        st.caption("勾选隐私确认后才能调用模型。")

    report = st.session_state.get("latest_match_report")
    summary = st.session_state.get("latest_match_summary")
    report_matches_job = st.session_state.get("latest_match_job_id") == str(job["id"])
    if report and summary and report_matches_job:
        st.divider()
        decision = DECISION_LABELS.get(str(summary["decision"]), str(summary["decision"]))
        confidence = CONFIDENCE_LABELS.get(str(summary["confidence"]), str(summary["confidence"]))
        c1, c2 = st.columns(2)
        c1.metric("申请建议", decision)
        c2.metric("证据置信度", confidence)
        st.markdown(report)
        st.download_button(
            "下载 Markdown 报告", report,
            file_name="careerpilot-match-report.md", mime="text/markdown",
            use_container_width=True,
        )


def render_rag_tab() -> None:
    st.subheader("知识库问答")
    st.caption("系统先检索公开项目文档，再让模型只依据命中原文回答。")
    question = st.text_input("你的问题", value="哪些内容属于硬门槛？")
    top_k = st.slider("检索片段数", 1, 6, 4)
    mode = st.radio(
        "回答方式",
        ["只看检索原文（免费）", "DeepSeek 带引用回答"],
        horizontal=True,
    )
    if st.button("开始检索", type="primary", use_container_width=True, key="rag_run"):
        try:
            results = load_retriever().search(question, top_k=top_k)
            st.session_state["rag_results"] = results
            st.session_state["rag_answer"] = None
            if mode == "DeepSeek 带引用回答":
                if not model_is_configured():
                    st.warning("尚未配置 DeepSeek API Key，已返回本地检索结果。")
                else:
                    with st.spinner("正在依据检索原文生成带引用答案……"):
                        st.session_state["rag_answer"] = answer_with_model(question, results, get_client())
        except UsageLimitError as error:
            st.warning(str(error))
        except (OSError, UnicodeError, ValueError, DeepSeekError) as error:
            st.error(f"问答失败：{error}")

    answer = st.session_state.get("rag_answer")
    results = st.session_state.get("rag_results", [])
    if answer:
        with st.container(border=True):
            st.markdown("**回答**")
            st.markdown(str(answer["answer"]))
    if results:
        st.markdown("#### 检索原文")
        for result in results:
            with st.container(border=True):
                st.markdown(f"**[{result.chunk.chunk_id}] {result.chunk.heading}**")
                st.write(result.chunk.text)
                st.caption(f"{result.chunk.source} · score {result.score:.3f}")
    elif "rag_results" in st.session_state:
        st.info("知识库没有找到相关片段；系统不会调用模型猜测答案。")


def main() -> None:
    st.set_page_config(
        page_title="CareerPilot｜证据驱动求职智能体",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_theme()
    try:
        starting_profile, source_label = load_starting_profile(ROOT)
        profile = profile_controls(starting_profile, source_label)
        jobs = load_jobs()
    except (OSError, ValueError) as error:
        st.error(f"启动失败：{error}")
        st.stop()

    render_hero()
    direction_tab, job_tab, match_tab, rag_tab = st.tabs(
        ["方向探索", "岗位雷达", "简历匹配", "知识问答"]
    )
    with direction_tab:
        render_direction_tab(profile)
    with job_tab:
        render_job_tab(profile, jobs)
    with match_tab:
        render_match_tab(profile, jobs)
    with rag_tab:
        render_rag_tab()

    st.divider()
    st.caption("CareerPilot 提供证据整理与行动建议，不代表录用概率；所有简历修改与投递行为均需本人确认。")


if __name__ == "__main__":
    main()
