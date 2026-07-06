from router import route, get_models_for_tier
from policy import should_upgrade, calculate_cost_ratio
from executor import run_opencode
from llm import call_llm
from models import TaskRequest, TaskResponse, ModelTier
from config import MODEL_POOL, COST_POLICY
import json
import time


class AISystem:
    def __init__(self):
        self.stats = {"cheap": 0, "mid": 0, "premium": 0}
        self.history = []

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
        fallback_count = 0

        for model in models:
            print(f"\n尝试模型: {model} (第 {fallback_count + 1} 次)")

            try:
                result = run_opencode(model, task)

                response = TaskResponse(
                    success=True,
                    model_used=model,
                    tier_used=decision.tier,
                    result=result,
                    fallback_count=fallback_count
                )

                if should_upgrade(response):
                    print(f"  结果质量不达标，尝试升级...")
                    fallback_count += 1
                    continue

                self.stats[decision.tier.value] += 1
                self._record_history(request, response)
                self._print_stats()

                print(f"\n✅ 成功! 使用模型: {model}")
                return response

            except Exception as e:
                print(f"  ❌ 失败: {e}")
                fallback_count += 1
                continue

        print(f"\n⚠️ 当前层级所有模型失败，尝试升级层级...")
        return self._try_higher_tiers(request, decision.tier, task)

    def _try_higher_tiers(self, request: TaskRequest, current_tier: ModelTier, task: str) -> TaskResponse:
        tier_order = [ModelTier.CHEAP, ModelTier.MID, ModelTier.PREMIUM]
        current_idx = tier_order.index(current_tier)

        for tier in tier_order[current_idx + 1:]:
            print(f"\n升级到层级: {tier.value}")
            models = get_models_for_tier(tier)

            for model in models:
                print(f"  尝试模型: {model}")
                try:
                    result = run_opencode(model, task)
                    response = TaskResponse(
                        success=True,
                        model_used=model,
                        tier_used=tier,
                        result=result,
                        fallback_count=current_idx + 1
                    )
                    self.stats[tier.value] += 1
                    self._record_history(request, response)
                    self._print_stats()
                    print(f"\n✅ 升级成功! 使用模型: {model}")
                    return response
                except Exception as e:
                    print(f"  ❌ 失败: {e}")
                    continue

        return TaskResponse(
            success=False,
            model_used="none",
            tier_used=current_tier,
            result="",
            error="所有模型层级均失败"
        )

    def _record_history(self, request: TaskRequest, response: TaskResponse):
        self.history.append({
            "timestamp": time.time(),
            "task": request.task[:100],
            "model": response.model_used,
            "tier": response.tier_used.value,
            "success": response.success,
            "fallback_count": response.fallback_count
        })

    def _print_stats(self):
        ratio = calculate_cost_ratio(self.stats)
        print(f"\n📊 统计: 总计={sum(self.stats.values())} | "
              f"cheap={self.stats['cheap']}({ratio['cheap']:.0%}) | "
              f"mid={self.stats['mid']}({ratio['mid']:.0%}) | "
              f"premium={self.stats['premium']}({ratio['premium']:.0%})")

    def get_stats(self) -> dict:
        return {
            "counts": self.stats.copy(),
            "ratios": calculate_cost_ratio(self.stats),
            "history": self.history[-10:]
        }


def main():
    system = AISystem()

    print("""
╔══════════════════════════════════════════════════════════════╗
║           🤖 多模型智能路由系统 v1.0                          ║
║  cheap(80%) → mid(15%) → premium(5%) 自动降级                ║
╚══════════════════════════════════════════════════════════════╝
输入 'quit' 退出 | 'stats' 查看统计 | 'help' 帮助
""")

    while True:
        try:
            task = input("\n请输入任务: ").strip()

            if task.lower() in ('quit', 'exit', 'q'):
                print("再见!")
                break

            if task.lower() == 'stats':
                stats = system.get_stats()
                print(json.dumps(stats, indent=2, ensure_ascii=False))
                continue

            if task.lower() == 'help':
                print("""
命令:
  quit/exit/q  - 退出程序
  stats        - 查看使用统计
  help         - 显示帮助

任务示例:
  - "帮我写一个登录系统" (mid)
  - "翻译这段英文" (cheap)
  - "设计一个微服务架构" (premium)
  - "debug这个Python报错" (mid)
                """)
                continue

            if not task:
                continue

            response = system.run(task)

            if response.success:
                print(f"\n📝 结果:\n{response.result[:500]}...")
            else:
                print(f"\n❌ 失败: {response.error}")

        except KeyboardInterrupt:
            print("\n\n再见!")
            break
        except Exception as e:
            print(f"\n❌ 系统错误: {e}")


if __name__ == "__main__":
    main()