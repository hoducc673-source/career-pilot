# CareerPilot：职业探索与求职智能体

这是一个面向应届生的职业探索与求职辅助项目。项目已经跑通离线职业探索、真实 JD 数据、DeepSeek 结构化分析、简历证据匹配和本地知识库 RAG，并提供可交互网页界面。

## 当前能做什么

- 读取一份职业偏好问卷
- 对 6 类候选方向进行透明评分
- 给出支持证据、待验证风险和 7 天小实验
- 浏览 11 个真实岗位样本并识别硬门槛
- 临时解析脱敏 DOCX 简历，生成证据匹配报告
- 从本地知识库检索原文，生成经过引用校验的回答
- 离线功能不产生 API 请求；模型功能只在用户主动点击后调用 DeepSeek

当前结果是“探索建议”，不是职业测评结论。它的用途是缩小搜索范围，并指导你用真实任务验证方向。

## 第一次运行

### 网页版（推荐）

创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

启动网页：

```bash
.venv/bin/streamlit run streamlit_app.py
```

网页版包含职业方向探索、真实岗位筛选、脱敏简历匹配和带引用知识库问答。简历文件只在临时目录解析；只有在用户明确勾选确认后，脱敏文本才会发送给 DeepSeek。

### 命令行

在本项目目录打开终端，执行：

```bash
PYTHONPATH=src python3 -m career_pilot.cli --profile samples/profile.example.json
```

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

检查真实 JD 种子数据集：

```bash
PYTHONPATH=src python3 -m career_pilot.jobs_cli --catalog data/jobs/seed_jobs.json
```

离线分析一个真实岗位：

```bash
PYTHONPATH=src python3 -m career_pilot.jd_cli \
  --job-id alibaba-beijing-shanghai-pm-intern \
  --provider demo
```

接入 DeepSeek 前，请按 `docs/DEEPSEEK_SETUP.md` 在本地配置 Key，绝不要把 Key 发到聊天或提交到 Git。

导入一份脱敏 DOCX 简历：

```bash
PYTHONPATH=src python3 -m career_pilot.resume_cli \
  --resume data/private/resumes/候选人-脱敏简历.docx \
  --output data/private/resume_evidence.json
```

使用 DeepSeek V4 Pro 进行简历—JD 证据匹配：

```bash
PYTHONPATH=src python3 -m career_pilot.match_cli \
  --job-id xiaohongshu-beijing-shanghai-ai-pm-intern \
  --output data/private/matches/xiaohongshu-ai-pm.json
```

把匹配 JSON 转成可读 Markdown 报告：

```bash
PYTHONPATH=src python3 -m career_pilot.report_cli \
  --match data/private/matches/xiaohongshu-ai-pm-v8.json \
  --output reports/xiaohongshu-ai-pm-readable.md
```

运行不调用 API 的安全评测：

```bash
PYTHONPATH=src python3 -m career_pilot.eval_cli \
  --output evals/runs/latest_resume_match_eval.json
```

运行 RAG 第一阶段的本地检索（不调用 API）：

```bash
PYTHONPATH=src python3 -m career_pilot.rag_cli \
  --question "哪些内容属于硬门槛？"
```

使用 DeepSeek V4 Pro 基于检索片段生成带引用答案：

```bash
PYTHONPATH=src python3 -m career_pilot.rag_cli \
  --question "哪些内容属于硬门槛？" \
  --provider deepseek \
  --output reports/rag_hard_requirements_answer.json
```

运行 RAG 离线检索评测：

```bash
PYTHONPATH=src python3 -m career_pilot.rag_eval_cli \
  --output evals/runs/latest_rag_retrieval_eval.json
```

## 下一步

1. 将网页分支合并到 `main`
2. 按[部署清单](docs/STREAMLIT_DEPLOYMENT.md)在 Streamlit Community Cloud 配置托管密钥
3. 部署一个招聘者可直接打开的公开演示版本
4. 增加用户反馈和失败案例，继续扩充评测集

详细需求见 `docs/PROJECT_BRIEF.md`，路线见 `docs/ROADMAP.md`。

## 隐私与密钥

- 不要把真实 API Key 写进代码、聊天记录或 Git
- `.env`、真实简历和本地数据库默认不提交
- 开发阶段优先使用脱敏简历
- 项目将保持模型供应商可替换，不依赖单一平台

## 模型接口

项目主要在中国大陆使用，因此模型功能接入 DeepSeek API，当前模型配置为 `deepseek-v4-pro` 且关闭思考模式。没有 `.env` 时，方向探索、岗位浏览和本地检索仍可使用；系统不会自动投递、修改简历或执行外部写操作。
