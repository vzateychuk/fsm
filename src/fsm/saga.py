from typing import Generic, TypeVar, Optional, Callable, Awaitable

from fsm.core import RunContext, SagaDefinition, TIn, TState

StepCallback = Callable[[int, RunContext], Awaitable[None]]


class Saga(Generic[TIn, TState]):
    """Stateless executor саги - выполняет pipeline шаги"""

    def __init__(
        self,
        definition: SagaDefinition[TIn, TState],
        pre_step_callback: Optional[Callable[[int, RunContext[TIn, TState]], Awaitable[None]]] = None,
        post_step_callback: Optional[Callable[[int, RunContext[TIn, TState]], Awaitable[None]]] = None,
    ) -> None:
        self._def = definition
        self._pre_step_callback = pre_step_callback
        self._post_step_callback = post_step_callback

    async def run(
        self,
        ctx: RunContext[TIn, TState],
    ) -> None:
        """Выполнить шаги саги начиная с текущей позиции cursor"""

        for i in range(ctx.cursor, len(self._def.steps)):
            step = self._def.steps[i]

            # Pre-step callback
            if self._pre_step_callback:
                await self._pre_step_callback(i, ctx)

            # Выполнить шаг
            await step.run(ctx)

            # Post-step callback
            if self._post_step_callback:
                await self._post_step_callback(i, ctx)

            # Обновить cursor
            ctx.cursor = i + 1
