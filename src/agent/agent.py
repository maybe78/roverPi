"""
RoverAgent — the brain of the robot.

Flow per turn:
  user_input (str)
    → append to history
    → ollama.chat(model, history, tools)
    → if tool_calls: execute each → append results → loop
    → final text response → return

The agent runs its own background thread that:
  1. Reads from the STT queue
  2. Calls chat()
  3. Calls TTS to speak the response
  4. Updates display state throughout
"""

import logging
import threading
import queue
from typing import Optional

import ollama

from config import (
    OLLAMA_HOST, OLLAMA_MODEL, ROBOT_PERSONALITY,
    AGENT_MAX_HISTORY, AGENT_TOOL_TIMEOUT
)
from agent.tools import ToolRegistry

logger = logging.getLogger("rover.agent")


class RoverAgent:
    def __init__(self, tool_registry: ToolRegistry, tts=None, display=None):
        self.registry = tool_registry
        self.tts = tts
        self.display = display

        self.client = ollama.Client(host=OLLAMA_HOST)
        self.model = OLLAMA_MODEL

        self._system_message = {"role": "system", "content": ROBOT_PERSONALITY}
        self._history: list[dict] = []
        self._history_lock = threading.Lock()

        self._input_queue: queue.Queue[str] = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, text: str) -> None:
        """Put a user utterance into the processing queue (non-blocking)."""
        self._input_queue.put(text)

    def chat(self, user_input: str) -> str:
        """
        Synchronous single-turn conversation.
        Handles multi-step tool calling internally.
        Returns the final text response.
        """
        self._set_display("thinking")

        with self._history_lock:
            self._history.append({"role": "user", "content": user_input})

        response_text = self._run_tool_loop()

        with self._history_lock:
            self._trim_history()

        return response_text

    def start(self) -> None:
        """Start the background processing thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="AgentThread"
        )
        self._thread.start()
        logger.info(f"Agent started (model: {self.model})")

    def stop(self) -> None:
        self._running = False
        self._input_queue.put(None)  # unblock the queue
        if self._thread:
            self._thread.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            text = self._input_queue.get()
            if text is None:
                break
            try:
                response = self.chat(text)
                if response:
                    self._set_display("speaking")
                    if self.tts:
                        self.tts.say(response)
                    self._set_display("idle")
                    logger.info(f"Agent: {response[:120]}")
            except Exception as e:
                logger.error(f"Agent loop error: {e}", exc_info=True)
                self._set_display("idle")

    def _run_tool_loop(self) -> str:
        """
        Send current history to LLM, handle tool calls, return final text.
        Loops until LLM returns a message without tool_calls.
        """
        max_rounds = 8  # prevent infinite tool loops
        for round_num in range(max_rounds):
            with self._history_lock:
                messages = [self._system_message] + list(self._history)

            try:
                response = self.client.chat(
                    model=self.model,
                    messages=messages,
                    tools=self.registry.schemas(),
                )
            except Exception as e:
                logger.error(f"ollama.chat failed: {e}")
                return f"Что-то пошло не так: {e}"

            msg = response.message

            with self._history_lock:
                self._history.append(msg)

            if not msg.tool_calls:
                return msg.content or ""

            # --- execute tool calls ---
            for tc in msg.tool_calls:
                name = tc.function.name
                args = tc.function.arguments or {}

                self._set_display("thinking")
                result = self.registry.execute(name, args)

                tool_result_msg = {
                    "role": "tool",
                    "content": str(result),
                }
                with self._history_lock:
                    self._history.append(tool_result_msg)

        logger.warning("Tool loop hit max rounds, returning empty response")
        return ""

    def _trim_history(self) -> None:
        """Keep only the last N messages (called with lock held)."""
        if len(self._history) > AGENT_MAX_HISTORY:
            self._history = self._history[-AGENT_MAX_HISTORY:]

    def _set_display(self, state: str) -> None:
        if self.display:
            try:
                self.display.set_state(state)
            except Exception:
                pass
