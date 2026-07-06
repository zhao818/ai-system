# 🤖 多模型智能路由系统 (AI Multi-Model Router)

> **工业级 LLM Router + Multi-model Gateway + Agent 执行系统**
>
> 等价于：Cursor 后端简化版 · Devin 调度层雏形 · 企业 AI Gateway

---

## 🎯 核心特性

| 特性 | 说明 |
|------|------|
| **智能路由** | GPT-4o-mini 自动判断任务复杂度，分配 cheap/mid/premium 三层模型 |
| **自动降级** | 模型失败/结果质量不达标 → 自动尝试下一个模型 → 再升级层级 |
| **统一接口** | LiteLLM 统一调用 OpenAI/Anthropic/Google/DeepSeek/Qwen 等 |
| **代码执行** | OpenCode 原生执行，非简单文本生成 |
| **成本控制** | 目标：80% cheap / 15% mid / 5% premium，实时统计追踪 |
| **可观测性** | 完整调用链路记录、统计仪表盘、历史记录 |

---

## 📁 项目结构

```
ai-system/
│
├── main.py           # 核心入口，交互式 CLI
├── router.py         # 任务分类路由器
├── policy.py         # 成本策略 & 升级判断
├── models.py         # 数据模型定义
├── llm.py            # LiteLLM 统一封装
├── executor.py       # OpenCode 执行层
├── config.py         # 模型池 & 配置参数
├── requirements.txt  # 依赖列表
├── .env.example      # 环境变量模板
└── README.md         # 本文档
```

---

## ⚡ 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

**至少需要一个可用的 API Key**：
- `OPENAI_API_KEY` (推荐，支持 gpt-4o-mini/gpt-4o)
- `ANTHROPIC_API_KEY` (支持 claude-sonnet)
- `GOOGLE_API_KEY` (支持 gemini-flash)
- `DEEPSEEK_API_KEY` (支持 deepseek-v3/deepseek-r1)
- `QWEN_API_KEY` (支持 qwen3)

### 3. 安装 OpenCode

```bash
pip install opencode-ai
# 或访问 https://opencode.ai 获取最新安装方式
```

### 4. 运行系统

```bash
python main.py
```

---

## 🧪 使用示例

```
请输入任务: 帮我写一个 Python 登录系统，包含 JWT 认证
路由决策: mid (置信度: 90%)
理由: Router classified as: mid

尝试模型: gpt-4o (第 1 次)
✅ 成功! 使用模型: gpt-4o

📝 结果:
[完整的登录系统代码...]

📊 统计: 总计=1 | cheap=0(0%) | mid=1(100%) | premium=0(0%)
```

```
请输入任务: 翻译这段代码注释成中文
路由决策: cheap (置信度: 90%)
理由: Router classified as: cheap

尝试模型: gpt-4o-mini (第 1 次)
✅ 成功! 使用模型: gpt-4o-mini

📊 统计: 总计=2 | cheap=1(50%) | mid=1(50%) | premium=0(0%)
```

```
请输入任务: 设计一个支持百万并发的微服务架构，包含熔断、限流、链路追踪
路由决策: premium (置信度: 90%)
理由: Router classified as: premium

尝试模型: claude-sonnet (第 1 次)
✅ 成功! 使用模型: claude-sonnet

📊 统计: 总计=3 | cheap=1(33%) | mid=1(33%) | premium=1(33%)
```

---

## 🎛️ 内置命令

| 命令 | 说明 |
|------|------|
| `quit` / `exit` / `q` | 退出程序 |
| `stats` | 查看详细统计（JSON 格式） |
| `help` | 显示帮助信息 |

---

## ⚙️ 配置详解

### 模型池 (config.py)

```python
MODEL_POOL = {
    "cheap": [
        "gpt-4o-mini",      # $0.15/1M input, $0.60/1M output
        "qwen3",             # 阿里通义千问
        "deepseek-v3"        # DeepSeek V3
    ],
    "mid": [
        "gpt-4o",            # $2.50/1M input, $10.00/1M output
        "deepseek-r1",       # 推理模型
        "gemini-flash"       # Google Gemini Flash
    ],
    "premium": [
        "claude-sonnet"      # $3.00/1M input, $15.00/1M output
    ]
}
```

> **注意**：模型名称需与 LiteLLM 支持的格式一致。查看完整列表：`litellm model_list`

### 成本策略 (config.py)

```python
COST_POLICY = {
    "max_retries_per_tier": 3,      # 每层最多重试次数
    "upgrade_on_error": True,        # 报错自动升级
    "upgrade_on_short_response": True, # 回复过短自动升级
    "min_response_length": 20,       # 最小有效回复长度
    "cheap_ratio_target": 0.80,      # 目标 cheap 占比 80%
    "mid_ratio_target": 0.15,        # 目标 mid 占比 15%
    "premium_ratio_target": 0.05     # 目标 premium 占比 5%
}
```

---

## 🔄 降级流程图

```
用户任务
    ↓
Router (gpt-4o-mini 判断)
    ↓
┌─────────┬─────────┬──────────┐
│ cheap   │ mid     │ premium  │
│ gpt-4o- │ gpt-4o  │ claude-  │
│ mini    │ deepseek│ sonnet   │
│ qwen3   │ -r1     │          │
│ deepseek│ gemini  │          │
│ -v3     │ -flash  │          │
└────┬────┴────┬────┴────┬────┘
     │         │         │
     ↓ 失败/质量不达标 ↓
尝试下一个模型 → 升级层级 → 尝试下一层模型
     ↓                     ↓
   成功 ←────────────── 成功
     ↓
  返回结果
```

---

## 📊 监控与统计

运行时输入 `stats` 查看：

```json
{
  "counts": {
    "cheap": 42,
    "mid": 8,
    "premium": 2
  },
  "ratios": {
    "cheap": 0.81,
    "mid": 0.15,
    "premium": 0.04
  },
  "history": [
    {
      "timestamp": 1720300000,
      "task": "帮我写一个登录系统...",
      "model": "gpt-4o",
      "tier": "mid",
      "success": true,
      "fallback_count": 0
    }
  ]
}
```

---

## 🛠️ 扩展指南

### 添加新模型

编辑 `config.py` 的 `MODEL_POOL`，确保模型名在 LiteLLM 支持列表中。

### 自定义路由规则

修改 `router.py` 的 `ROUTER_PROMPT`，或替换为微调模型/规则引擎。

### 接入其他执行器

在 `executor.py` 添加新的 `run_xxx` 函数，在 `main.py` 中调用。

### 持久化统计

```python
# 在 AISystem 中添加
import sqlite3

def _save_stats(self):
    conn = sqlite3.connect("ai_system.db")
    # 保存 stats 和 history
```

---

## 💰 成本估算 (参考)

| 层级 | 模型 | 单价 (输入/输出) | 预估日均成本 (1000次) |
|------|------|------------------|----------------------|
| cheap | gpt-4o-mini | $0.15/$0.60 | ~$0.75 |
| mid | gpt-4o | $2.50/$10.00 | ~$12.50 |
| premium | claude-sonnet | $3.00/$15.00 | ~$18.00 |

**按 80/15/5 分配，1000次调用约 $3.50** (vs 全用 GPT-4o 约 $12.50，**节省 72%**)

---

## 🚀 进阶版本规划

| 版本 | 特性 | 状态 |
|------|------|------|
| v1.0 | 单任务路由 + 降级 | ✅ 完成 |
| v1.1 | 任务拆解 + 多步执行 | 🔄 规划中 |
| v1.2 | 多智能体协作 (Orchestrator/Scout/Judge) | 📋 设计中 |
| v2.0 | 自动写项目 + 自动修 Bug + 自动分工 (Devin 级) | 💡 构想中 |

---

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支: `git checkout -b feature/xxx`
3. 提交变更: `git commit -m 'feat: add xxx'`
4. 推送分支: `git push origin feature/xxx`
5. 发起 PR

---

## 📄 许可证

MIT License - 可自由用于商业/个人项目

---

## 🔗 相关链接

- [LiteLLM 文档](https://docs.litellm.ai/)
- [OpenCode 官网](https://opencode.ai/)
- [模型价格对比](https://artificialanalysis.ai/models)

---

> **一句话总结**：✔️ Router 决定“用谁” ✔️ LiteLLM 负责“统一接口” ✔️ OpenCode 负责“执行” ✔️ fallback 保证“不崩”