# Streamlit Community Cloud 部署清单

## 1. 部署坐标

- GitHub 仓库：`hoducc673-source/career-pilot`
- 分支：`main`
- 入口文件：`streamlit_app.py`
- Python：`3.12`
- 建议应用地址：`career-pilot-xiaoyu`（若已被占用，使用平台自动生成地址）

仓库根目录的 `requirements.txt` 会安装当前项目及 `pyproject.toml` 中声明的依赖。

## 2. 云端密钥

在 Streamlit Community Cloud 创建应用时，打开 **Advanced settings → Secrets**，填写：

```toml
DEEPSEEK_API_KEY = "在平台中填写真实 Key，不要写入 GitHub"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"
```

不要上传本地 `.env`，不要创建并提交真实的 `.streamlit/secrets.toml`。这两个路径都已被 Git 忽略。

## 3. 首次上线步骤

1. 登录 `https://share.streamlit.io/` 并连接 GitHub。
2. 选择 **Create app → Yup, I have an app**。
3. 填入上方仓库、分支和入口文件。
4. 在 **Advanced settings** 中选择 Python 3.12，并填写 Secrets。
5. 点击 **Deploy**，等待构建完成。

## 4. 上线验收

- 首页、四个功能页可以正常打开。
- 侧栏显示“DeepSeek 已配置”，但网页和日志中看不到真实 Key。
- 方向探索、岗位雷达和本地知识检索不调用 API。
- 只有用户明确点击生成按钮后才调用 DeepSeek。
- 上传的 DOCX 只在临时目录解析；真实简历、画像与匹配结果不进入 GitHub。
- 用脱敏测试简历完成一次报告后，重新打开无痕窗口，确认上一个会话的内容不可见。

## 5. 费用保护

公开演示会使用部署者账户中的 DeepSeek 余额。上线初期应设置较低的平台余额或告警，定期检查用量；如果出现异常调用，先从 Streamlit Secrets 中移除 `DEEPSEEK_API_KEY`，应用会自动退回离线模式。
