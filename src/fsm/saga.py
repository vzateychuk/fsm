from typing import Generic, Optional, Callable, Awaitable

from fsm.core import RunContext, SagaDefinition, TIn, TData

StepCallback = Callable[[int, RunContext[TIn, TData]], Awaitable[None]]


class Saga(Generic[TIn, TData]):
    """Stateless executor саги - выполняет pipeline шаги"""

    def __init__(
        self,
        definition: SagaDefinition[TIn, TData],
        pre_step_callback: Optional[Callable[[int, RunContext[TIn, TData]], Awaitable[None]]] = None,
        post_step_callback: Optional[Callable[[int, RunContext[TIn, TData]], Awaitable[None]]] = None,
    ) -> None:
        self._def = definition
        self._pre_step_callback = pre_step_callback
        self._post_step_callback = post_step_callback

    async def run(
        self,
        ctx: RunContext[TIn, TData],
    ) -> None:
        """Выполнить шаги саги начиная с текущей позиции cursor"""

        for i in range(ctx.cursor, len(self._def.steps)):
            step = self._def.steps[i]

            # Pre-step callback
            if self._pre_step_callback:
                await self._pre_step_callback(i, ctx)

            # Выполнить шаг
            await step.run(ctx)

            # Обновить cursor перед post-step callback для консистентного checkpoint
            ctx.cursor = i + 1

            # Post-step callback с актуальным cursor (указывает на следующий шаг)
            if self._post_step_callback:
                await self._post_step_callback(i, ctx)
