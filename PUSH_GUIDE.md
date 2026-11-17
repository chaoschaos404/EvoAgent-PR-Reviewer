# GitHub 推送与仓库维护指南

本目录是一个已整理干净、可随时推送的本地 Git 仓库（已完成 `git init`，文件在暂存区）。
本机没有配置 git 全局身份，因此**推送时请在仓库内设置本仓库级身份**，不要用全局配置。

## 方式 A：一键脚本（推荐）

在本目录的**上一级**（`ai-builder-portfolio/`）执行：

```bash
./push_to_github.sh
```

脚本会交互式询问 GitHub Personal Access Token（classic PAT，勾选 `repo`），输入不回显；
然后自动创建两个公开仓库、设置本仓库级提交身份、创建初始提交并推送。
Token 只通过 HTTP 请求头临时传递，**不写入任何文件、不写入 git remote**。推送完成后建议立即撤销该 Token。

## 方式 B：GitHub 连接器

在 WorkBuddy 里启用 GitHub 连接器并**重开一个对话**让新会话加载工具，
然后请助手把 `EvoAgent-PR-Reviewer/` 和 `bailian-studio/` 推送到你的账号。

## 方式 C：手动命令

```bash
cd EvoAgent-PR-Reviewer

git config user.name  "你的 GitHub 用户名"
git config user.email "你的用户名@users.noreply.github.com"
git add -A
git commit -m "Initial commit: EvoAgent PR Reviewer"
git branch -M main

# 在 GitHub 网页新建空仓库（不要勾选 README / .gitignore / license）
git remote add origin https://github.com/<你的用户名>/EvoAgent-PR-Reviewer.git
git push -u origin main
```

`bailian-studio/` 同理，把仓库名换成 `bailian-studio` 即可。

## 建议的 GitHub 主页包装

| 仓库 | Description | Topics |
|---|---|---|
| `EvoAgent-PR-Reviewer` | AI PR Reviewer · 自研 Agent Runtime / 多 Agent 协作 / 自动修复 / 评测与灰度发布 | `ai-agent` `llm` `code-review` `agent-runtime` `python` `github-webhook` |
| `bailian-studio` | AI 生图 / 生视频工作台 · 零依赖 Python 代理 + 完整前端交互闭环 | `ai` `image-generation` `video-generation` `dashscope` `python` |

- 把 `docs/runtime-flow.png` 或 `docs/architecture-flow.html` 的截图放进 README 顶部。
- 两个仓库 + 一个 Profile README，比单个大仓库更能体现「Builder」的广度。

## 推送前检查清单

- [ ] `git status --short` 里没有 `.env`、`.venv/`、`*.db`、`__pycache__/`
- [ ] 目录内无硬编码 API Key（本仓库只有 `.env.example`，值均为空）
- [ ] `docs/ORIGINAL_README.md` 中的密码都是占位符，未替换成真实口令
- [ ] 公开仓库请先决定 License（当前未附许可证，公开即默认「保留所有权利」）
- [ ] Web 管理台截图建议用本地 `local` provider 跑一遍再截，避免暴露真实模型返回内容
