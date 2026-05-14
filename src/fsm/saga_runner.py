import logging
from typing import Generic

from fsm.core import RunContext, SagaDefinition, TIn, TData
from fsm.saga import Saga
from store.store import Store, SavedProgress

logger = logging.getLogger(__name__)


class SagaRunner(Generic[TIn, TData]):
    """Orchestrator для запуска саги: загрузка, выполнение, сохранение"""

    def __init__(
        self,
        saga_def: SagaDefinition[TIn, TData],
        store: Store,
        data_type: type[TData],
    ) -> None:
        self._def = saga_def
        self._store = store
        self._data_type = data_type

    async def run(
        self,
        *,
        run_id: str,
        input: TIn,
        initial_data: TData,
    ) -> RunContext[TIn, TData]:
        """Запустить Saga: загрузить/создать, выполнить, сохранить"""

        logger.info(f"Starting saga '{self._def.name}' (run_id={run_id})")

        # Загрузить или создать pipeline
        ctx = await self._load_or_create_context(run_id, input, initial_data)

        # Callbacks для сохранения данных
        async def pre_step(step_idx: int, run_ctx: RunContext[TIn, TData]) -> None:
            step = self._def.steps[step_idx]
            step_desc = getattr(step, "desc", None) or "No description"
            logger.info(
                f"Executing step {step_idx}: '{step.id}' ({step_desc})"
            )
            logger.debug(f"Step input: {run_ctx.input}")
            # logger.trace(f"Step data before: {run_ctx.data}")

        async def post_step(step_idx: int, run_ctx: RunContext[TIn, TData]) -> None:
            # logger.debug(f"Step data after: {run_ctx.data}")

            # Сохранить данные после шага
            data_type_name = type(run_ctx.data).__name__
            progress: SavedProgress = {
                "run_id": run_ctx.run_id,
                "saga_name": run_ctx.saga_name,
                "cursor": run_ctx.cursor,
                "state": run_ctx.data.model_dump(),
            }
            await self._store.save(progress)
            logger.info(
                f"Checkpoint saved: cursor={run_ctx.cursor}, data='{data_type_name}'"
            )

        # Выполнить сагу
        saga = Saga(self._def, pre_step, post_step)
        await saga.run(ctx)

        logger.info(f"Saga '{self._def.name}' completed successfully")
        return ctx

    async def _load_or_create_context(
        self, run_id: str, input: TIn, initial_data: TData
    ) -> RunContext[TIn, TData]:
        """Загрузить сохраненный контекст или создать новый"""

        saved = await self._store.load(run_id)
        if saved and saved.get("saga_name") == self._def.name:
            logger.info(f"Resuming saga from cursor={saved['cursor']}")
            logger.debug(f"Loaded state: {saved['state']}")
            data = self._data_type.model_validate(saved["state"])
            return RunContext[TIn, TData](
                run_id=run_id,
                saga_name=self._def.name,
                cursor=saved["cursor"],
                input=input,
                data=data,
            )
        else:
            logger.info("No saved progress found, starting from beginning")
            return RunContext(
                run_id=run_id,
                saga_name=self._def.name,
                cursor=0,
                input=input,
                data=initial_data,
            )
