# EvoAgent PR Reviewer

> 一个从「收到 PR」到「给出审查结论、自动修复、回归验证」全链路可运行的 AI Agent 系统。
> 不是为了演示某个模型调用，而是把 Agent 运行时、记忆、工具、评测、发布门禁做成了一个能部署的服务。

---

## 一句话定位

GitHub `pull_request` webhook 进来之后，系统会把 diff 拆成可审查的单元，交给多个专职 Agent 并行分析，汇总成结构化问题清单与修复建议；在配置允许时，还会在独立分支上做保守型自动修复，并在编译 / 测试门禁通过后才允许合入。全程有 Web 管理台、任务轨迹、Markdown 报告和 Prometheus 指标。

**这是投「AI Builder」岗最直接的作品：它回答的不是「我会不会调大模型」，而是「我能不能把大模型放进一个可靠、可观测、可回滚的产品里」。**

---

## 能力地图

| 层 | 做了什么 | 对应代码 |
|---|---|---|
| 接入层 | GitHub webhook（`opened` / `reopened` / `synchronize`）、HMAC-SHA256 验签、delivery 幂等与重放时间窗、PR 评论 upsert 回写 | `evoagent/api.py`、`github.py`、`service.py` |
| Agent 运行时 | 自研有界 Agent Loop、Tool Registry + 参数 Schema 校验、结构化 Observation、checkpoint 持久化、执行预算与断点续跑 | `runtime.py`、`harness.py`、`skills.py` |
| 上下文与记忆 | 任务 / 工具 / 反馈 / 记忆 / 观察 / Diff 统一 Context Window，逐轮压缩；Working / Episodic / Semantic 分层记忆、租户级检索、归档与过期清理 | `context_manager.py`、`memory.py` |
| 多 Agent 协作 | 安全、可靠性、AI、动态 Skill 四类 Agent 并行审查，独立 diff 解析与结论汇总 | `agents.py`、`reviewer.py`、`diff_parser.py` |
| 模型层 | OpenAI 兼容端点（DeepSeek / OpenRouter / 自定义）；**未配置模型时自动降级为确定性本地规则审查器**，因此离线也能完整跑通 | `reviewer.py`、`config.py` |
| 自动修复 | 独立分支上的保守型修复提交、编译 / 测试门禁、灰度发布与影子流量 | `fixer.py`、`verifier.py`、`rollout.py` |
| 评测与进化 | 基础验证集 + 隐藏回归集、失败案例回流、提示词评测、版本激活与回滚、Skill manifest 校验与隔离沙箱 | `evaluation_*.py`、`evolution*.py`、`skill_evolution.py`、`skill_runner.py` |
| 可靠性 | Redis Streams ACK、Worker 租约、指数退避重试、死信队列；SQLite 本地模式 / PostgreSQL + Redis 生产模式 | `task_queue.py`、`store.py`、`postgres_store.py` |
| 产品化 | 用户登录、RBAC、租户与仓库隔离、不可变审计日志、Web 管理台与任务 Dashboard、Prometheus 指标、OpenTelemetry Trace | `auth.py`、`models.py`、`web/`、`metrics.py`、`observability.py` |

---

## 本地跑起来（不需要 API Key）

需要 Python 3.11。项目默认 `EVOAGENT_LLM_PROVIDER=local`，走确定性本地规则审查器，**不调用任何大模型即可完整体验**。

```bash
cd EvoAgent-PR-Reviewer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 开启登录并创建本地管理员（密码至少 10 位，请勿使用示例值）
export EVOAGENT_AUTH_REQUIRED=true
export EVOAGENT_AUTH_SECRET="$(python3 -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())')"
export EVOAGENT_BOOTSTRAP_ADMIN_USERNAME=admin
export EVOAGENT_BOOTSTRAP_ADMIN_PASSWORD='换成你自己的密码'

.venv/bin/python -m evoagent
# 打开 http://127.0.0.1:8080
```

登录后调用审查接口，或直接用一段 diff 做最小复现：

```bash
TOKEN=<登录返回的 access_token>

curl -X POST http://127.0.0.1:8080/v1/reviews \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "repository": "demo/api",
  "pull_request": 12,
  "diff": "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1,2 @@\n+eval(user_input)\n+DEBUG = True"
}
JSON
```

查询任务与报告：`GET /v1/tasks/<task-id>`、`GET /v1/tasks/<task-id>/report`。

跑测试：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

生产形态另见 `Dockerfile`、`docker-compose.yml` 与 `.env.example`（密钥只走环境变量，`.env` 已被忽略）。

---

## 建议的演示方式（3 分钟）

1. **先讲链路**：webhook → 验签 → 任务入队 → 多 Agent 并行 → 汇总报告 →（可选）自动修复 → 门禁 → 回写 PR。用 `docs/architecture-flow.html` / `docs/runtime-flow.html` 两张图。
2. **再讲一个真实难点**：为什么要有「有界 Agent Loop + 执行预算 + checkpoint」，为什么 Context Window 要逐轮压缩，为什么提示词版本必须能回滚 —— 这些是「能跑」和「能上线」的区别。
3. **最后亮证据**：`output/evaluation/` 里的评测报告、`evaluation_data/pr_diff_100.jsonl` 的样本集、`tests/` 下的测试模块、`web/` 的管理台。
4. 想接真实模型时，把 provider 换成任意 OpenAI 兼容端点即可，不需要改业务代码。

面试讲稿与可能被追问的问题见 `docs/INTERVIEW_TALK.md`。

---

## 目录结构

```
EvoAgent-PR-Reviewer/
├── README.md                 本文件（作品集导读）
├── docs/ORIGINAL_README.md   原始完整技术文档（配置、API、评测细节）
├── docs/architecture-flow.html / runtime-flow.html / runtime-flow.pdf / .png
├── docs/INTERVIEW_TALK.md    面试讲稿
├── evoagent/                 服务与 Agent 运行时全部源码
├── web/                      Web 管理台与 Dashboard（app.js / app.css / index.html）
├── skills/code-quality/      动态 Skill 示例（manifest + 实现）
├── tests/                    单元测试与协作 / 运行时 / 生产特性测试
├── scripts/                  端到端评测、LLM 基准、Prompt 进化验证、知识库导出
├── evaluation_data/          PR diff 评测样本
├── output/evaluation/        已跑出的评测报告（JSON + Markdown）
├── requirements.txt / Dockerfile / docker-compose.yml / .env.example
└── PUSH_GUIDE.md             GitHub 推送与仓库维护指南
```

---

## 关于这份材料

- 本目录是从本地开发副本整理出的**展示版**：已剔除虚拟环境、字节码缓存、运行时数据库、`.DS_Store` 和与项目无关的素材；原始 81 MB 精简为约 2 MB，源码与文档完整保留。
- 未附开源许可证：代码用于招聘测评展示，如需开源请先选定 License。
- 密钥安全：目录内只有 `.env.example`（值均为空），没有 `.env`、没有硬编码 API Key；`.gitignore` 已覆盖 `.env` / `.venv` / `*.db`。
- 完整技术细节（模型配置、webhook、RBAC、评测与提示词进化、部署）请读 `docs/ORIGINAL_README.md`。
