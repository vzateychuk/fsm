import logging
from typing import Generic

from fsm.core import RunContext, SagaDefinition, SagaProgressStore, TIn, TState
from fsm.saga import Saga

logger = logging.getLogger(__name__)


class SagaRunner(Generic[TIn, TState]):
    """Orchestrator для запуска саги: загрузка, выполнение, сохранение"""

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
        """Запустить Saga: загрузить/создать, выполнить, сохранить"""

        logger.info(f"Starting saga '{self._def.name}' (run_id={run_id})")

        # Загрузить или создать pipeline
        ctx = await self._load_or_create_context(run_id, input, initial_state)

        # Callbacks для сохранения состояния
        async def pre_step(step_idx: int, context: RunContext[TIn, TState]) -> None:
            state_name = getattr(context.state, "state_name", "unknown")
            logger.info(
                f"Executing step {step_idx}: '{self._def.steps[step_idx].id}' on '{state_name}'"
            )
            logger.debug(f"Step input: {context.input}")
            logger.debug(f"Step state before: {context.state}")

        async def post_step(step_idx: int, context: RunContext[TIn, TState]) -> None:
            logger.debug(f"Step state after: {context.state}")

            # Сохранить состояние после шага
            state_name = getattr(context.state, "state_name", "unknown")
            await self._store.save(
                {
                    "run_id": context.run_id,
                    "saga_name": context.saga_name,
                    "cursor": context.cursor,
                    "state": context.state.model_dump(),
                }
            )
            logger.info(
                f"Checkpoint saved: cursor={context.cursor}, state='{state_name}'"
            )

        # Выполнить сагу
        saga = Saga(self._def, pre_step, post_step)
        await saga.run(ctx)

        logger.info(f"Saga '{self._def.name}' completed successfully")
        return ctx

    async def _load_or_create_context(
        self, run_id: str, input: TIn, initial_state: TState
    ) -> RunContext[TIn, TState]:
        """Загрузить сохраненный контекст или создать новый"""

        saved = await self._store.load(run_id)
        if saved and saved.get("saga_name") == self._def.name:
            logger.info(f"Resuming saga from cursor={saved['cursor']}")
            logger.debug(f"Loaded state: {saved['state']}")
            state = self._state_type.model_validate(saved["state"])
            return RunContext[TIn, TState](
                run_id=run_id,
                saga_name=self._def.name,
                cursor=saved["cursor"],
                input=input,
                state=state,
            )
        else:
            logger.info("No saved progress found, starting from beginning")
            return RunContext(
                run_id=run_id,
                saga_name=self._def.name,
                cursor=0,
                input=input,
                state=initial_state,
            )
