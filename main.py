from router import route, get_models_for_tier
from policy import should_upgrade, calculate_cost_ratio
from executor import run_opencode
from models import TaskRequest, TaskResponse, ModelTier
from config import STATS_FILE, HISTORY_FILE, MAX_HISTORY
import json, os, time, concurrent.futures


class AISystem:
    def __init__(self):
        self.stats = {"cheap": 0, "mid": 0, "premium": 0}
        self.history = []
        self._load_state()

    def run(self, task: str, preferred_tier: str = None, context: str = None) -> TaskResponse:
        print(f"\n{'='*60}")
        print(f"任务: {task}")
        print(f"{'='*60}")

        request = TaskRequest(
            task=task,
            preferred_tier=ModelTier(preferred_tier) if preferred_tier else None,
            context=context
        )

        decision = route(request)
        print(f"路由决策: {decision.tier.value} (置信度: {decision.confidence:.0%})")
        print(f"理由: {decision.reasoning}")

        models = get_models_for_tier(decision.tier)

        # cheap 层并发跑，谁快用谁
        if decision.tier == ModelTier.CHEAP:
            response = self._run_concurrent(models, request, decision)
        else:
            response = self._run_sequential(models, request, decision)

        if response.success:
            return response

        # 当前层级全失败，升级
        print(f"\n⚠️ 当前层级全失败，升级...")
        return self._try_higher_tiers(request, decision.tier, task)

    def _run_concurrent(self, models: list, request: TaskRequest, decision) -> TaskResponse:
        print(f"并发尝试: {', '.join(models)}")
        tried = set()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(models))
        try:
            futures = {executor.submit(run_opencode, m, request.task): m for m in models}
            for future in concurrent.futures.as_completed(futures):
                model = futures[future]
                tried.add(model)
                try:
                    result = future.result()
                    response = TaskResponse(
                        success=True, model_used=model,
                        tier_used=decision.tier, result=result
                    )
                    if not should_upgrade(response):
                        self.stats[decision.tier.value] += 1
                        self._record_history(request, response)
                        self._print_stats()
                        print(f"\n✅ 最快响应: {model}")
                        return response
                except Exception:
                    continue
        finally:
            # 立即返回，不等待其余子进程；已完成结果不达标才走兜底
            executor.shutdown(wait=False, cancel_futures=True)

        # 顺序兜底：只重试尚未跑过（被取消/未完成）的模型，避免重复劳动
        remaining = [m for m in models if m not in tried]
        if not remaining:
            return TaskResponse(success=False, model_used="", tier_used=decision.tier, result="")
        return self._run_sequential(remaining, request, decision)

    def _run_sequential(self, models: list, request: TaskRequest, decision, fallback_count: int = 0) -> TaskResponse:
        for i, model in enumerate(models):
            print(f"\n尝试模型: {model}")
            try:
                result = run_opencode(model, request.task)
                response = TaskResponse(
                    success=True, model_used=model,
                    tier_used=decision.tier, result=result,
                    fallback_count=fallback_count + i
                )
                if should_upgrade(response):
                    print(f"  结果质量不达标")
                    continue
                self.stats[decision.tier.value] += 1
                self._record_history(request, response)
                self._print_stats()
                print(f"\n✅ 成功: {model}")
                return response
            except Exception as e:
                print(f"  ❌ 失败: {e}")
                continue

        return TaskResponse(success=False, model_used="", tier_used=decision.tier, result="")

    def _try_higher_tiers(self, request: TaskRequest, current_tier: ModelTier, task: str) -> TaskResponse:
        tier_order = [ModelTier.CHEAP, ModelTier.MID, ModelTier.PREMIUM]
        for tier in tier_order[tier_order.index(current_tier) + 1:]:
            print(f"\n升级到: {tier.value}")
            response = self._run_sequential(get_models_for_tier(tier), request, MockDecision(tier))
            if response.success:
                return response

        return TaskResponse(success=False, model_used="none", tier_used=current_tier, result="", error="所有模型均失败")

    def _record_history(self, request, response):
        entry = {
            "timestamp": time.time(), "task": request.task[:100],
            "model": response.model_used, "tier": response.tier_used.value,
            "success": response.success, "fallback_count": response.fallback_count
        }
        self.history.append(entry)
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        self._save_state(entry)

    def _load_state(self):
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, encoding="utf-8") as f:
                    saved = json.load(f)
                for k in self.stats:
                    self.stats[k] = int(saved.get(k, 0))
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, encoding="utf-8") as f:
                    self.history = [json.loads(line) for line in f if line.strip()][-MAX_HISTORY:]
        except (OSError, ValueError) as e:
            print(f"⚠️ 无法加载历史状态: {e}")

    def _save_state(self, entry: dict):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False)
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"⚠️ 无法保存状态: {e}")

    def _print_stats(self):
        ratio = calculate_cost_ratio(self.stats)
        print(f"📊 统计: 总计={sum(self.stats.values())} | "
              f"cheap={self.stats['cheap']}({ratio['cheap']:.0%}) | "
              f"mid={self.stats['mid']}({ratio['mid']:.0%}) | "
              f"premium={self.stats['premium']}({ratio['premium']:.0%})")

    def get_stats(self) -> dict:
        return {"counts": self.stats.copy(), "ratios": calculate_cost_ratio(self.stats), "history": self.history[-10:]}


class MockDecision:
    def __init__(self, tier): self.tier = tier


def main():
    system = AISystem()
    print("""
╔══════════════════════════════════════════════╗
║  多模型智能路由系统 v1.0                      ║
║ cheap(免费并发) → mid → premium 自动降级      ║
╚══════════════════════════════════════════════╝
""")

    while True:
        try:
            task = input("> ").strip()
            if task.lower() in ('quit', 'exit', 'q'): break
            if task.lower() == 'stats':
                print(json.dumps(system.get_stats(), indent=2, ensure_ascii=False))
                continue
            if task.lower() == 'help':
                print("quit/stats/help")
                continue
            if not task: continue

            response = system.run(task)
            if response.success:
                print(f"📝 {response.result[:300]}")
            else:
                print(f"❌ {response.error}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ {e}")


if __name__ == "__main__":
    main()
