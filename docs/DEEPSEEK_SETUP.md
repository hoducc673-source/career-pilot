# DeepSeek API Key 配置指南

## 重要原则

- API Key 等同于账户密码，不要发送到聊天、截图或公开仓库
- 初期只充值小额，建议 20～50 元，先验证项目再决定是否增加
- Key 只保存在本机项目根目录的 `.env` 文件中
- `.env` 已被 `.gitignore` 排除

## 配置步骤

1. 打开 [DeepSeek 开放平台](https://platform.deepseek.com/)。
2. 注册或登录账号，在 API Keys 页面创建一个新的 Key。
3. 复制完整 Key。关闭页面后通常无法再次查看完整内容。
4. 打开项目根目录中的 `.env` 文件。
5. 找到这一行：

   ```text
   DEEPSEEK_API_KEY=
   ```

6. 把 Key 粘贴在等号右侧，不要加空格，不要发给任何人：

   ```text
   DEEPSEEK_API_KEY=你的真实Key
   ```

7. 把 `MODEL_PROVIDER=demo` 改为：

   ```text
   MODEL_PROVIDER=deepseek
   ```

8. 保存文件，然后只告诉我“本地 Key 已配置”，不要粘贴 Key 内容。

## 首次验证会做什么

首次联网只分析一条已经保存的公开岗位 JD。程序会：

1. 从环境变量读取 Key
2. 调用 `https://api.deepseek.com/chat/completions`
3. 要求模型返回 JSON
4. 在本地校验字段、决策枚举和证据引用
5. 拒绝缺字段、无证据或格式错误的输出

程序不会打印 API Key，也不会自动投递简历。

## 常见错误

- HTTP 401：Key 缺失、复制不完整或已失效
- HTTP 402：账户余额不足
- 请求超时：网络或服务暂时不稳定，稍后重试
- JSON 校验失败：模型没有遵守输出合同，需要保存 Bad Case 并调整提示词

官方接口示例和模型名称以 [DeepSeek API 文档](https://api-docs.deepseek.com/) 为准。
