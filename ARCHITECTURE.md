# AI Multi-Model Router — 微服务架构设计

> 目标：从单体 CLI 演进为支持百万并发的微服务集群，内置熔断、限流、链路追踪

---

## 一、总体架构

```
                     ┌─────────────────────────────────┐
                     │       客户端层 (SDK/CLI/HTTP)      │
                     └──────────────┬──────────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────────┐
                     │         API Gateway              │
                     │   (Kong / APISIX / Envoy)        │
                     │   限流→鉴权→路由→审计日志         │
                     └──────────────┬──────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
     │  Router Service  │  │  Executor Svc   │  │  Policy Svc     │
     │  任务分类+路由     │  │  OpenCode执行    │  │  成本策略+升降级   │
     └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
              │                     │                     │
              ▼                     ▼                     ▼
     ┌─────────────────────────────────────────────────────────┐
     │               Message Queue (Kafka / RabbitMQ)           │
     │        异步解耦 · 削峰填谷 · 事件驱动                    │
     └──────┬──────────────┬──────────────┬────────────────────┘
            │              │              │
            ▼              ▼              ▼
     ┌──────────┐  ┌──────────┐  ┌──────────────┐
     │ Model    │  │ Stats    │  │  Notification│
     │ Proxy    │  │ Svc      │  │  Svc         │
     │LiteLLM   │  │ 统计+监控  │  │ Webhook/邮件  │
     │ 集群     │  │          │  │              │
     └──────────┘  └──────────┘  └──────────────┘
```

---

## 二、服务拆分

| 服务 | 职责 | 技术栈 |
|------|------|--------|
| **API Gateway** | 限流、鉴权、路由、请求校验、审计日志 | Kong / APISIX / Envoy |
| **Router Service** | 任务复杂度分类、模型层选择、路由决策 | FastAPI + LiteLLM |
| **Executor Service** | 调用 OpenCode 执行任务、流式/非流式响应 | FastAPI + subprocess/容器 |
| **Policy Service** | 成本策略、升降级判断、预算控制 | FastAPI + 规则引擎 |
| **Model Proxy** | 多模型统一接入、健康检查、负载均衡 | LiteLLM 集群 |
| **Stats Service** | 调用统计、成本核算、趋势分析 | FastAPI + ClickHouse |
| **Notification Svc** | 异步通知、Webhook、邮件告警 | FastAPI + Celery |
| **Job Queue** | 异步任务编排、事件驱动 | Kafka / RabbitMQ |

---

## 三、通信模式

### 3.1 同步通讯 (实时推理请求)

```
客户端 → Gateway → Router Svc → Executor Svc → Model Proxy → LLM
           ↓          ↓              ↓
         响应 ←──── Gateway 聚合 ←───┘
```

gRPC 双工流式传输，支持 SSE/WebSocket 实时推送。

### 3.2 异步通讯 (非实时/批量任务)

```
客户端 (提交任务ID) → Gateway → Kafka topic:task_submitted
                                          ↓
                               Executor Consumer (消费)
                                          ↓
                               Kafka topic:task_completed
                                          ↓
                               Notification Svc → Webhook/轮询
```

Kafka 分区键 = `task_id % N`，保证同一任务有序消费。

---

## 四、熔断 (Circuit Breaker)

### 层级设计

```
┌──────────────────────────────────────────────────────┐
│                     CEO 熔断器                        │
│  全局开关 — 支付/配额耗尽时手动触发                    │
├──────────────────────────────────────────────────────┤
│                Service 熔断器 (每服务)                 │
│  Router Svc / Executor Svc / Model Proxy 各自独立    │
│  基于 5xx 错误率 + 延迟 P99 自动打开/半开/关闭        │
├──────────────────────────────────────────────────────┤
│                Model 熔断器 (每模型)                   │
│  gpt-4o-mini / claude-sonnet 各自独立熔断            │
│  触发条件：连续 N 次超时/失败 → 半开 → 试探恢复       │
└──────────────────────────────────────────────────────┘
```

### 实现

```python
class CircuitBreaker:
    states = {"CLOSED", "OPEN", "HALF_OPEN"}

    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # 秒
        self.last_failure_time = 0
        self.state = "CLOSED"

    def call(self, fn, fallback=None):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                return fallback() if fallback else None

        try:
            result = fn()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            return fallback() if fallback else None
```

**熔断 + 降级联动：** 当 gpt-4o-mini 熔断 → 自动降级到 deepseek-chat → 还不够 → 升级到 mid 层。

---

## 五、限流 (Rate Limiting)

### 三层限流

| 层级 | 粒度 | 策略 | 实现 |
|------|------|------|------|
| **全局** | 集群总 QPS | Token Bucket (Redis) | `令牌桶 → 50000 QPS` |
| **租户** | API Key 级别 | Sliding Window | `滑动窗口 → 1000 QPS/Key` |
| **模型** | 每模型并发 | Semaphore + Queue | `模型 X → 50 并发` |

### Gateway 层（Kong）

```yaml
# Kong 限流插件
plugins:
  - name: rate-limiting
    config:
      second: 50000          # 全局
      policy: redis
      fault_tolerant: true
  - name: rate-limiting-advanced
    config:
      limit: [1000]          # 每 API Key
      window_size: [1]
      namespace: api_key_rate
```

### 服务层（本地熔断+限流）

```python
from circuitbreaker import circuit
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=100, period=1)  # 100 QPS 本地
@circuit(failure_threshold=5, recovery_timeout=30)
async def call_model(model: str, prompt: str):
    return await litellm_call(model, prompt)
```

---

## 六、链路追踪 (Distributed Tracing)

### OpenTelemetry 全链路

```
客户端 → Gateway → Router → Executor → Model Proxy → LLM
  ↓        ↓         ↓          ↓           ↓         ↓
 └─────────────────── OTel Collector ───────────────────┘
                            ↓
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
        Jaeger          Prometheus       ClickHouse
      (Trace UI)       (Metrics)       (Traces 持久化)
```

### Span 设计

| Span | 父 Span | 关键属性 |
|------|---------|---------|
| `http.request` | — | method, path, api_key |
| `router.decision` | `http.request` | tier, model, confidence |
| `executor.run` | `router.decision` | model, attempt, duration |
| `model.call` | `executor.run` | model_name, tokens_in, tokens_out |
| `policy.check` | `executor.run` | tier, cost, upgrade_reason |

### 在代码中埋点

```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

async def route_task(task: str):
    with tracer.start_as_current_span("router.decision") as span:
        tier = await classifier.classify(task)
        span.set_attribute("tier", tier.value)
        span.set_attribute("confidence", 0.9)
        return tier
```

---

## 七、部署架构

```
                         ┌──────────────┐
                         │  LB (Nginx)  │
                         │  HTTPS 终结   │
                         └──────┬───────┘
                                │
                    ┌───────────┴───────────┐
                    │   API Gateway 集群     │
                    │   (Kong x 3)          │
                    └───────────┬───────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
   ┌──────────┐          ┌──────────┐          ┌──────────┐
   │ Router   │          │ Executor │          │ Policy   │
   │ Svc x 2  │          │ Svc x 5  │          │ Svc x 2  │
   └────┬─────┘          └────┬─────┘          └────┬─────┘
        │                     │                     │
        ▼                     ▼                     ▼
   ┌──────────────────────────────────────────────────────┐
   │                   Kafka 集群 x 3                       │
   └──────────────────────────────────────────────────────┘
        │                     │
        ▼                     ▼
   ┌──────────┐          ┌──────────┐     ┌────────────────┐
   │ Model    │          │ Stats    │     │  Notification  │
   │ Proxy    │          │ Svc x 2  │     │  Svc x 1       │
   │ x 3      │          └──────────┘     └────────────────┘
   └────┬─────┘
        │
        ▼
   ┌──────────────────────────────────┐
   │   LiteLLM Proxy 集群 x 3         │
   │   → OpenAI / Anthropic / 其他     │
   └──────────────────────────────────┘
```

### 基础设施

| 组件 | 方案 | 规模 |
|------|------|------|
| 容器编排 | Kubernetes (K8s) | 3 master + N worker |
| 服务网格 | Istio | 流量管理 + mTLS |
| 配置中心 | etcd / Consul | 动态路由规则 |
| 可观测性 | Grafana + Jaeger + Prometheus | 统一仪表盘 |
| 日志 | ELK (Elasticsearch + Logstash + Kibana) | 7 天热 + 30 天冷 |
| 缓存 | Redis Cluster | 路由缓存 + 限流计数器 |
| 数据库 | PostgreSQL (主) + ClickHouse (时序) | 读写分离 |

---

## 八、数据流：完整请求生命周期

```
1. POST /v1/run {"task": "...", "api_key": "sk-xxx"}

2. Gateway 层:
   ├── 限流检查 (Redis Token Bucket)
   ├── API Key 鉴权 (Redis -> PostgreSQL)
   ├── 请求日志 (Kafka topic: audit_log)
   └── 路由到 Router Svc

3. Router Svc:
   ├── 奥特尔 Span: router.decision
   ├── gpt-4o-mini 分类任务
   ├── 输出: cheap/mid/premium
   └── 推送 Kafka topic: task_routed

4. Executor Svc:
   ├── 消费 task_routed topic
   ├── 奥特尔 Span: executor.run
   ├── 调用 Model Proxy (gRPC 流式)
   └── 推送 Kafka topic: task_completed

5. Model Proxy:
   ├── 奥特尔 Span: model.call
   ├── 熔断器检查 (模型级别)
   ├── LiteLLM 调用 LLM
   └── 流式返回 tokens

6. Policy Svc (旁路):
   ├── 消费 task_completed topic
   ├── 检查是否需要升级/降级
   ├── 更新成本统计
   └── 推送 Kafka topic: policy_action (如需干预)

7. Stats Svc (旁路):
   ├── 消费所有 topic
   ├── 写入 ClickHouse
   └── 更新 Grafana 仪表盘

8. 响应:
   └── HTTP 200 + JSON/SSE 流
```

---

## 九、从单体到微服务：演进路线

| 阶段 | 动作 | 效果 | 状态 |
|------|------|------|------|
| **Phase 0** | 现有单体 CLI | 单机可用 | ✅ 已完成 |
| **Phase 1** | 抽取为独立 FastAPI 服务，同步 HTTP 通信 | 水平扩展基础 | ✅ 已完成 |
| **Phase 2** | 引入 API Gateway + 熔断/限流/链路追踪 | 解耦+可靠性 | ✅ 已完成 |
| **Phase 3** | Docker Compose 容器化部署 | 环境一致 | ✅ 已完成 |
| **Phase 4** | K8s + Istio 服务网格 | 百万并发 | 📋 待实施 |
| **Phase 5** | 多租户 + 计费 + 自助服务 | SaaS 化 | 📋 待实施 |

---

## 十一、代码结构

```
ai-system/
├── shared/                    # 共享基础设施
│   ├── models.py              # TaskRequest / TaskResponse / RouterDecision
│   ├── circuit_breaker.py     # 熔断器 (CLOSED/OPEN/HALF_OPEN)
│   ├── rate_limiter.py        # 三层限流 (全局/租户/模型)
│   ├── tracing.py             # 链路追踪 (Span/Tracer)
│   ├── message_queue.py       # 异步消息队列 (InMemory / Redis)
│   └── config.py              # 集中配置
│
├── services/
│   ├── gateway/               # API Gateway (端口 8000)
│   │   └── app.py             # POST /v1/run — 统一入口
│   ├── router_service/        # Router Service (端口 8001)
│   │   └── app.py             # POST /v1/route — 任务分类
│   ├── executor/              # Executor Service (端口 8002)
│   │   └── app.py             # POST /v1/execute — OpenCode 执行
│   ├── policy/                # Policy Service (端口 8003)
│   │   └── app.py             # POST /v1/check — 升降级判定
│   ├── model_proxy/           # Model Proxy (端口 8004)
│   │   └── app.py             # POST /v1/chat/completions — LLM 代理
│   └── stats/                 # Stats Service (端口 8005)
│       └── app.py             # POST /v1/ingest — 统计采集
│
├── main.py                    # 单体 CLI (向下兼容)
├── docker-compose.yml         # 全容器编排
├── run_services.ps1           # 本地服务启动脚本
└── ARCHITECTURE.md            # 本文档
```

### 启动方式

**本地开发（无需 Docker）：**
```powershell
.\run_services.ps1 start       # 启动全部 6 个服务
.\run_services.ps1 stop        # 停止
.\run_services.ps1 status      # 查看状态
```

**Docker 部署：**
```bash
docker compose up -d
```

**调用示例：**
```bash
curl -X POST http://localhost:8000/v1/run \
  -H "Content-Type: application/json" \
  -d '{"task": "设计一个微服务架构", "api_key": "sk-test"}'
```

---

## 十、关键指标 (SLO)

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| P99 延迟 | < 2s (simple) / < 10s (complex) | Jaeger |
| 可用性 | 99.95% (月) | Prometheus + Alertmanager |
| 错误率 | < 0.1% | Gateway 5xx 统计 |
| 限流误杀 | < 0.01% | 限流命中日志 |
| 熔断误触 | < 0.1% | 熔断事件分析 |
| 链路追踪采样 | 100% 错误 + 10% 正常 | OTel 头部采样 |

---

> **设计原则：** 熔断保底、限流防冲、追踪可观测。三层防护共同保证系统在百万并发下的稳定性。
