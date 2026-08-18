# CareerPilot：职业探索与求职智能体

这是一个面向应届生的职业探索与求职辅助项目。项目已经跑通离线职业探索、真实 JD 数据和 DeepSeek 结构化分析，目前进入“简历证据匹配”阶段。

## 当前能做什么

- 读取一份职业偏好问卷
- 对 6 类候选方向进行透明评分
- 给出支持证据、待验证风险和 7 天小实验
- 全程离线运行，不上传个人信息

当前结果是“探索建议”，不是职业测评结论。它的用途是缩小搜索范围，并指导你用真实任务验证方向。

## 第一次运行

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

1. 参考 `samples/profile.example.json` 填写本地私密问卷
2. 运行离线探索报告
3. 人工确认最值得验证的 2～3 个方向
4. 检查已经收集的真实 JD 种子数据
5. 接入大模型，完成 JD 提取与简历证据匹配

详细需求见 `docs/PROJECT_BRIEF.md`，路线见 `docs/ROADMAP.md`。

## 隐私与密钥

- 不要把真实 API Key 写进代码、聊天记录或 Git
- `.env`、真实简历和本地数据库默认不提交
- 开发阶段优先使用脱敏简历
- 项目将保持模型供应商可替换，不依赖单一平台

## 计划使用的模型接口

由于项目主要在中国大陆使用，模型阶段计划优先接入 DeepSeek API。默认仍为 `demo`，只有在 `.env` 中显式配置后才会产生 API 请求。首个在线版本使用结构化输出处理 JD，不会自动投递或执行外部写操作。
