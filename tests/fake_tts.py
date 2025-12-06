from __future__ import annotations

import asyncio
import copy
import time
from typing import Literal

from pydantic import BaseModel

# Import handlers, but DO NOT CALL THEM HERE
from livekit.interrupt_handlers import on_tts_start, on_tts_end

from livekit.agents import NOT_GIVEN, APIConnectionError, NotGivenOr, tts, utils
from livekit.agents.tts import (
    TTS,
    ChunkedStream,
    SynthesizeStream,
    TTSCapabilities,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions


class FakeTTSResponse(BaseModel):
    """Maps input text to audio duration characteristics."""

    type: Literal["tts"] = "tts"
    input: str
    audio_duration: float
    ttfb: float
    duration: float

    def speed_up(self, factor: float) -> FakeTTSResponse:
        obj = copy.deepcopy(self)
        obj.audio_duration /= factor
        obj.ttfb /= factor
        obj.duration /= factor
        return obj


class FakeTTS(TTS):
    def __init__(
        self,
        *,
        sample_rate: int = 24000,
        num_channels: int = 1,
        fake_timeout: float | None = None,
        fake_audio_duration: float | None = None,
        fake_exception: Exception | None = None,
        fake_responses: list[FakeTTSResponse] | None = None,
    ) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=True),
            sample_rate=sample_rate,
            num_channels=num_channels,
        )

        self._fake_timeout = fake_timeout
        self._fake_audio_duration = fake_audio_duration
        self._fake_exception = fake_exception

        self._fake_response_map: dict[str, FakeTTSResponse] = {}
        if fake_responses is not None:
            for response in fake_responses:
                self._fake_response_map[response.input] = response

        self._synthesize_ch = utils.aio.Chan[FakeChunkedStream]()
        self._stream_ch = utils.aio.Chan[FakeSynthesizeStream]()

    def update_options(
        self,
        *,
        fake_timeout: NotGivenOr[float | None] = NOT_GIVEN,
        fake_audio_duration: NotGivenOr[float | None] = NOT_GIVEN,
        fake_exception: NotGivenOr[Exception | None] = NOT_GIVEN,
    ) -> None:
        if utils.is_given(fake_timeout):
            self._fake_timeout = fake_timeout
        if utils.is_given(fake_audio_duration):
            self._fake_audio_duration = fake_audio_duration
        if utils.is_given(fake_exception):
            self._fake_exception = fake_exception

    @property
    def synthesize_ch(self) -> utils.aio.ChanReceiver[FakeChunkedStream]:
        return self._synthesize_ch

    @property
    def stream_ch(self) -> utils.aio.ChanReceiver[FakeSynthesizeStream]:
        return self._stream_ch

    @property
    def fake_response_map(self) -> dict[str, FakeTTSResponse]:
        return self._fake_response_map

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> FakeChunkedStream:
        stream = FakeChunkedStream(tts=self, input_text=text, conn_options=conn_options)
        self._synthesize_ch.send_nowait(stream)
        return stream

    def stream(
        self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> FakeSynthesizeStream:
        stream = FakeSynthesizeStream(
            tts=self,
            conn_options=conn_options,
        )
        self._stream_ch.send_nowait(stream)
        return stream


class FakeChunkedStream(ChunkedStream):
    def __init__(self, *, tts: FakeTTS, input_text: str, conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt

    async def _run(self, output_emitter: tts.AudioEmitter):
        """
        Chunked TTS output simulation.
        We mark TTS start at the FIRST chunk being emitted.
        We mark TTS end after all audio is flushed.
        """
        self._attempt += 1
        assert isinstance(self._tts, FakeTTS)

        # Tell handler TTS has started
        try:
            on_tts_start()
        except Exception:
            pass

        output_emitter.initialize(
            request_id=utils.shortuuid("fake_tts_"),
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/pcm",
        )

        if self._tts._fake_timeout is not None:
            if self._tts._fake_timeout > self._conn_options.timeout:
                await asyncio.sleep(self._conn_options.timeout)
                raise APIConnectionError("timeout")
            await asyncio.sleep(self._tts._fake_timeout)

        start_time = time.perf_counter()
        resp = self._tts.fake_response_map.get(
            self._input_text,
            FakeTTSResponse(
                input=self._input_text,
                audio_duration=self._tts._fake_audio_duration or 0.0,
                ttfb=0.0,
                duration=0.0,
            ),
        )

        # Emit audio chunks
        if resp.audio_duration > 0.0:
            await asyncio.sleep(resp.ttfb)
            pushed = 0
            max_samples = int(self._tts.sample_rate * resp.audio_duration + 0.5)
            while pushed < max_samples:
                chunk = min(self._tts.sample_rate // 100, max_samples - pushed)
                output_emitter.push(b"\x00\x00" * chunk)
                pushed += chunk

        if self._tts._fake_exception is not None:
            raise self._tts._fake_exception

        output_emitter.flush()

        # Ensure full duration
        delay = resp.duration - (time.perf_counter() - start_time)
        if delay > 0.0:
            await asyncio.sleep(delay)

        # Mark TTS end
        try:
            on_tts_end()
        except Exception:
            pass


class FakeSynthesizeStream(SynthesizeStream):
    def __init__(
        self,
        *,
        tts: TTS,
        conn_options: APIConnectOptions,
    ):
        super().__init__(tts=tts, conn_options=conn_options)
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        """
        Streaming mode: TTS start/end determined by first and last pushed segment.
        """
        self._attempt += 1
        assert isinstance(self._tts, FakeTTS)

        # TTS START
        try:
            on_tts_start()
        except Exception:
            pass

        if self._tts._fake_timeout is not None:
            if self._tts._fake_timeout > self._conn_options.timeout:
                await asyncio.sleep(self._conn_options.timeout)
                raise APIConnectionError("timeout")
            await asyncio.sleep(self._tts._fake_timeout)

        output_emitter.initialize(
            request_id=utils.shortuuid("fake_tts_"),
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/pcm",
            stream=True,
        )

        input_text = ""
        async for data in self._input_ch:
            if isinstance(data, str):
                input_text += data
                continue

            if isinstance(data, SynthesizeStream._FlushSentinel) and not input_text:
                continue

            resp = self._tts.fake_response_map.get(
                input_text,
                FakeTTSResponse(
                    input=input_text,
                    audio_duration=self._tts._fake_audio_duration or 0.0,
                    ttfb=0.0,
                    duration=0.0,
                ),
            )

            input_text = ""
            if resp.audio_duration == 0.0:
                continue

            start = time.perf_counter()

            if resp.ttfb > 0.0:
                await asyncio.sleep(resp.ttfb)

            output_emitter.start_segment(segment_id=utils.shortuuid("fake_segment_"))
            pushed = 0
            max_samples = int(self._tts.sample_rate * resp.audio_duration + 0.5)

            while pushed < max_samples:
                chunk = min(self._tts.sample_rate // 100, max_samples - pushed)
                output_emitter.push(b"\x00\x00" * chunk)
                pushed += chunk

            output_emitter.flush()

            # maintain full duration
            diff = time.perf_counter() - start
            if resp.duration - diff > 0:
                await asyncio.sleep(resp.duration - diff)

        # TTS END
        try:
            on_tts_end()
        except Exception:
            pass

        if self._tts._fake_exception is not None:
            raise self._tts._fake_exception
