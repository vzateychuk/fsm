import logging
from typing import Generic, TypeVar

from fsm.core import (
    RunContext,
    SagaDefinition,
    SagaProgressStore,
    TIn,
    TState,
)

logger = logging.getLogger(__name__)


class Saga(Generic[TIn, TState]):
    """Исполнитель саги"""

    def __init__(
        self,
        saga_def: SagaDefinition[TIn, TState],
        store: SagaProgressStore,
        state_type: type[TState],
    ) -> None:
        self._def = saga_def
        self._store = store
        self._state_type = state_type

    async def run(
        self,
        *,
        run_id: str,
        input: TIn,
        initial_state: TState,
    ) -> RunContext[TIn, TState]:
        logger.info(f"Starting saga '{self._def.name}' (run_id={run_id})")

        # Попытка загрузить сохраненный прогресс
        saved = await self._store.load(run_id)
        if saved and saved.get("saga_name") == self._def.name:
            logger.info(f"Resuming saga from cursor={saved['cursor']}")
            logger.debug(f"Loaded state: {saved['state']}")
            state = self._state_type.model_validate(saved["state"])
            ctx = RunContext[TIn, TState](
                run_id=run_id,
                saga_name=self._def.name,
                cursor=saved["cursor"],
                input=input,
                state=state,
            )
        else:
            logger.info("No saved progress found, starting from beginning")
            ctx = RunContext(
                run_id=run_id,
                saga_name=self._def.name,
                cursor=0,
                input=input,
                state=initial_state,
            )

        # Исполнение шагов
        for i in range(ctx.cursor, len(self._def.steps)):
            step = self._def.steps[i]
            state_name = getattr(ctx.state, "state_name", "unknown")
            logger.info(f"Executing step {i}: '{step.id}' on '{state_name}'")
            logger.debug(f"Step input: {ctx.input}")
            logger.debug(f"Step state before: {ctx.state}")

            await step.run(ctx)

            logger.debug(f"Step state after: {ctx.state}")

            # Чекпоинт после шага
            ctx.cursor = i + 1
            state_name = getattr(ctx.state, "state_name", "unknown")
            await self._store.save(
                {
                    "run_id": ctx.run_id,
                    "saga_name": ctx.saga_name,
                    "cursor": ctx.cursor,
                    "state": ctx.state.model_dump(),
                }
            )
            logger.info(f"Checkpoint saved: cursor={ctx.cursor}, state='{state_name}'")

        logger.info(f"Saga '{self._def.name}' completed successfully")
        return ctx
