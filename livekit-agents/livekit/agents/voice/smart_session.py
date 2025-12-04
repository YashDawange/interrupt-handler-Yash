"""
Smart Interruption Agent Session

This module provides a drop-in replacement for AgentSession that enables
smart interruption filtering with minimal code changes.
"""

import logging
from typing import Optional

from .agent_session import AgentSession
from .smart_activity import SmartInterruptionAgentActivity
from .smart_interruption import SmartInterruptionFilter

logger = logging.getLogger(__name__)


class SmartInterruptionAgentSession(AgentSession):
    """
    AgentSession with smart interruption filtering enabled.

    This is a drop-in replacement for AgentSession that adds intelligent
    filtering of interruptions to distinguish backchannel feedback from
    explicit interruption commands.

    Usage:
        # Instead of:
        # session = AgentSession(stt=..., llm=..., tts=..., vad=...)

        # Use:
        session = SmartInterruptionAgentSession(
            stt=..., llm=..., tts=..., vad=...,
            smart_interruption_enabled=True,  # Optional, defaults to True
        )
    """

    def __init__(
        self,
        *,
        smart_interruption_enabled: bool = True,
        smart_interruption_ignore_list: Optional[set[str]] = None,
        smart_interruption_interrupt_list: Optional[set[str]] = None,
        smart_interruption_max_words: int = 3,
        **kwargs,
    ):
        """
        Initialize SmartInterruptionAgentSession.

        Args:
            smart_interruption_enabled: Enable smart interruption filtering
            smart_interruption_ignore_list: Custom set of backchannel words to ignore
            smart_interruption_interrupt_list: Custom set of interrupt command words
            smart_interruption_max_words: Maximum words for backchannel classification
            **kwargs: All other arguments passed to AgentSession
        """
        self._smart_interruption_enabled = smart_interruption_enabled
        self._smart_filter = None

        if smart_interruption_enabled:
            self._smart_filter = SmartInterruptionFilter(
                ignore_list=smart_interruption_ignore_list,
                interrupt_list=smart_interruption_interrupt_list,
                max_words=smart_interruption_max_words,
            )

            logger.info(
                "SmartInterruptionAgentSession initialized",
                extra={
                    "enabled": True,
                    "ignore_list": sorted(self._smart_filter.ignore_list),
                    "interrupt_list": sorted(self._smart_filter.interrupt_list),
                },
            )

        super().__init__(**kwargs)

    async def _update_activity(
        self,
        agent,
        *,
        previous_activity="close",
        new_activity="start",
        blocked_tasks=None,
        wait_on_enter=True,
    ):
        """
        Override _update_activity to inject SmartInterruptionAgentActivity.
        
        This is called by AgentSession when creating a new activity.
        We intercept it to create our custom activity class instead.
        """
        # Call parent first, but we need to override the activity creation
        # Store the activity creation logic locally
        from .agent_activity import AgentActivity
        
        async with self._activity_lock:
            self._agent = agent

            if new_activity == "start":
                previous_agent = self._activity.agent if self._activity else None
                if agent._activity is not None and (
                    agent is not previous_agent or previous_activity != "close"
                ):
                    raise RuntimeError("cannot start agent: an activity is already running")

                # THIS IS THE KEY: Use SmartInterruptionAgentActivity instead of AgentActivity
                if self._smart_interruption_enabled:
                    self._next_activity = SmartInterruptionAgentActivity(
                        agent, self, smart_filter=self._smart_filter
                    )
                else:
                    self._next_activity = AgentActivity(agent, self)
            elif new_activity == "resume":
                if agent._activity is None:
                    raise RuntimeError("cannot resume agent: no existing active activity to resume")
                self._next_activity = agent._activity

            # Continue with rest of parent's logic
            if self._root_span_context is not None:
                from opentelemetry import context as otel_context
                otel_context.attach(self._root_span_context)

            previous_activity_v = self._activity
            if self._activity is not None:
                if previous_activity == "close":
                    await self._activity.drain()
                    await self._activity.aclose()
                elif previous_activity == "pause":
                    await self._activity.pause(blocked_tasks=blocked_tasks or [])

            self._activity = self._next_activity
            self._next_activity = None

            from .agent_session import AgentHandoff
            run_state = self._global_run_state
            handoff_item = AgentHandoff(
                old_agent_id=previous_activity_v.agent.id if previous_activity_v else None,
                new_agent_id=self._activity.agent.id,
            )
            if run_state:
                run_state._agent_handoff(
                    item=handoff_item,
                    old_agent=previous_activity_v.agent if previous_activity_v else None,
                    new_agent=self._activity.agent,
                )
            self._chat_ctx.insert(handoff_item)

            if new_activity == "start":
                await self._activity.start()
            elif new_activity == "resume":
                await self._activity.resume()

        if wait_on_enter:
            assert self._activity._on_enter_task is not None
            import asyncio
            await asyncio.shield(self._activity._on_enter_task)

    def _create_activity(self, *args, **kwargs):
        """
        Legacy method - keeping for compatibility but no longer used.
        Activity creation now happens in _update_activity override.
        """
        if self._smart_interruption_enabled:
            return SmartInterruptionAgentActivity(
                *args,
                smart_filter=self._smart_filter,
                **kwargs,
            )
        else:
            return super()._create_activity(*args, **kwargs)
