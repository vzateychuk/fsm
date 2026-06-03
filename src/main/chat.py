"""Medical chat CLI — agentic consultation REPL."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import typer

from src.api.factory import AppContext, create_app_context
from src.common.logging_config import setup_logging
from src.services.errors import AppError, NotFoundError

app = typer.Typer(add_completion=False)

_QUIT_COMMANDS = {"quit", "exit", "q"}

logger = logging.getLogger(__name__)


async def _pick_session(ctx: AppContext) -> str | None:
    """Display active sessions and let user choose one or start new."""
    sessions = await ctx.sessions_service.list_sessions(status="active")
    if not sessions:
        print("No sessions found.")
        return None

    print("\nAvailable sessions:")
    for i, sess in enumerate(sessions, start=1):
        print(f"  {i}. {sess.title} ({sess.updated_at[:10]})")

    try:
        choice = input("\nSelect session (number) or 'n' for new: ").strip()
        if choice.lower() == "n":
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            return sessions[idx].session_id
    except (ValueError, IndexError):
        pass
    return None


async def _run_chat(session_id: str | None, ctx: AppContext) -> None:
    sessions_service = ctx.sessions_service
    chat_service = ctx.chat_service

    # Resolve or select session
    if session_id:
        try:
            session = await sessions_service.get_session(session_id)
        except NotFoundError:
            print(f"Session {session_id!r} not found.")
            sys.exit(1)
        print(f"Resuming session: [{session.session_id}] {session.title}")
    else:
        picked = await _pick_session(ctx)
        if picked:
            session = await sessions_service.get_session(picked)
            session_id = picked
            print(f"Resuming session: [{session_id}] {session.title}")
        else:
            session_id = None
            print("Starting new session.")

    # Show last assistant message when resuming
    if session_id:
        messages = await chat_service.get_messages(session_id)
        last = next(
            (m for m in reversed(messages) if m.role == "assistant" and m.content),
            None,
        )
        if last:
            print(f"\n[Last response]\n\n{last.content}\n")

    print("Medical consultation started. Type your complaint and press Enter.")
    print("Type 'quit' or press Ctrl+D to exit.\n")

    new_session = session_id is None
    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print("\nSession ended.")
            break

        if not user_input:
            continue
        if user_input.lower() in _QUIT_COMMANDS:
            print("Session ended.")
            break

        # Create session lazily on first actual message
        if new_session:
            auto_title = user_input[:50] or "New session"
            created = await sessions_service.create_session(title=auto_title)
            session_id = created.session_id
            new_session = False

        assert session_id is not None
        try:
            msg = await chat_service.send_message(session_id, user_input)
        except AppError as e:
            print(f"\n[Error: {e.message}]\n")
            continue

        print(f"\n{msg.content}\n")


@app.command()
def chat(
    session_id: str | None = typer.Option(None, "--session", help="Session ID to resume"),  # noqa: B008
    debug: bool = typer.Option(False, "--debug", help="Enable DEBUG-level logging."),  # noqa: B008
    pkg_debug: bool = typer.Option(False, "--pkg-debug", help="Enable DEBUG-level logging for project packages only."),  # noqa: B008
    log_file: Path | None = typer.Option(None, "--log-file", help="Write logs to file."),  # noqa: B008
) -> None:
    """Agentic medical consultation: interactive REPL with KB tool access."""
    setup_logging(
        level=logging.DEBUG if debug else logging.INFO,
        log_file=str(log_file) if log_file else None,
        debug_packages=pkg_debug,
    )

    async def _main() -> None:
        ctx = await create_app_context()
        await _run_chat(session_id, ctx)

    asyncio.run(_main())


if __name__ == "__main__":
    app()
