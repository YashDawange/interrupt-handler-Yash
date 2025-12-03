from __future__ import annotations

import asyncio
import base64
import json
import os
import weakref
from dataclasses import dataclass, replace
from typing import Any, Literal, TypedDict, Union, overload

import aiohttp

from .. import tokenize, tts, utils
from .._exceptions import APIConnectionError, APIError, APIStatusError, APITimeoutError
from ..log import logger
from ..types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, APIConnectOptions, NotGivenOr
from ..utils import is_given
from ._utils import create_access_token

# near module imports, global
from playback_manager import PlaybackManager
playback_manager = PlaybackManager()


# ---- paste START ----
# Local fallback TTS using pyttsx3 with clamped rate to avoid too-fast speech.
import os
import threading
try:
    import pyttsx3
except Exception:
    pyttsx3 = None

def speak_with_local_tts(text: str, rate: int = 50, voice_index: int | None = None, block: bool = False) -> None:
    """
    Local TTS fallback that clamps the speaking rate so it doesn't speak too fast.
    - text: text to speak
    - rate: requested WPM (will be clamped)
    - voice_index: optional voice index
    - block: if True, call blocks until speech finishes
    """
    # if pyttsx3 not installed, bail (caller should have fallback)
    if pyttsx3 is None:
        try:
            print("speak_with_local_tts: pyttsx3 not available. Text:", text)
        except Exception:
            pass
        return

    # allow overriding desired rate with env var LIVEKIT_TTS_RATE
    env_rate = os.environ.get("LIVEKIT_TTS_RATE")
    if env_rate:
        try:
            rate = int(env_rate)
        except Exception:
            pass

    # clamp to readable range (adjust min/max if you prefer slower/faster)
    MIN_RATE = 50
    MAX_RATE = 80
    try:
        rate = max(MIN_RATE, min(int(rate), MAX_RATE))
    except Exception:
        rate = 50

    def _do_speak():
        try:
            engine = pyttsx3.init()
            # Set rate & volume
            try:
                engine.setProperty('rate', int(rate))
            except Exception:
                pass
            try:
                engine.setProperty('volume', 1.0)
            except Exception:
                pass

            # select voice if requested
            try:
                if voice_index is not None:
                    voices = engine.getProperty('voices')
                    if 0 <= int(voice_index) < len(voices):
                        engine.setProperty('voice', voices[int(voice_index)].id)
            except Exception:
                pass

            # optionally log small message (safe)
            try:
                print(f"speak_with_local_tts: speaking (rate={rate})")
            except Exception:
                pass

            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            try:
                print("speak_with_local_tts error:", e)
            except Exception:
                pass

    if block:
        _do_speak()
    else:
        t = threading.Thread(target=_do_speak, daemon=True)
        t.start()
# ---- paste END ----

print("tts.py: speak_with_local_tts defined and module loaded")






CartesiaModels = Literal[
    "cartesia",
    "cartesia/sonic",
    "cartesia/sonic-2",
    "cartesia/sonic-turbo",
]
ElevenlabsModels = Literal[
    "elevenlabs",
    "elevenlabs/eleven_flash_v2",
    "elevenlabs/eleven_flash_v2_5",
    "elevenlabs/eleven_turbo_v2",
    "elevenlabs/eleven_turbo_v2_5",
    "elevenlabs/eleven_multilingual_v2",
]
RimeModels = Literal[
    "rime",
    "rime/mist",
    "rime/mistv2",
    "rime/arcana",
]
InworldModels = Literal[
    "inworld",
    "inworld/inworld-tts-1",
]


class CartesiaOptions(TypedDict, total=False):
    duration: float  # max duration of audio in seconds
    speed: Literal["slow", "normal", "fast"]  # default: not specified


class ElevenlabsOptions(TypedDict, total=False):
    inactivity_timeout: int  # default: 60
    apply_text_normalization: Literal["auto", "off", "on"]  # default: "auto"


class RimeOptions(TypedDict, total=False):
    pass


class InworldOptions(TypedDict, total=False):
    pass


TTSModels = Union[CartesiaModels, ElevenlabsModels, RimeModels, InworldModels]

TTSEncoding = Literal["pcm_s16le"]

DEFAULT_ENCODING: TTSEncoding = "pcm_s16le"
DEFAULT_SAMPLE_RATE: int = 24000
DEFAULT_BASE_URL = "https://agent-gateway.livekit.cloud/v1"


@dataclass
class _TTSOptions:
    model: TTSModels | str
    voice: NotGivenOr[str]
    language: NotGivenOr[str]
    encoding: TTSEncoding
    sample_rate: int
    base_url: str
    api_key: str
    api_secret: str
    extra_kwargs: dict[str, Any]


class TTS(tts.TTS):
    @overload
    def __init__(
        self,
        model: CartesiaModels,
        *,
        voice: NotGivenOr[str] = NOT_GIVEN,
        language: NotGivenOr[str] = NOT_GIVEN,
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        sample_rate: NotGivenOr[int] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        api_secret: NotGivenOr[str] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
        extra_kwargs: NotGivenOr[CartesiaOptions] = NOT_GIVEN,
    ) -> None:
        pass

    @overload
    def __init__(
        self,
        model: ElevenlabsModels,
        *,
        voice: NotGivenOr[str] = NOT_GIVEN,
        language: NotGivenOr[str] = NOT_GIVEN,
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        sample_rate: NotGivenOr[int] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        api_secret: NotGivenOr[str] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
        extra_kwargs: NotGivenOr[ElevenlabsOptions] = NOT_GIVEN,
    ) -> None:
        pass

    @overload
    def __init__(
        self,
        model: RimeModels,
        *,
        voice: NotGivenOr[str] = NOT_GIVEN,
        language: NotGivenOr[str] = NOT_GIVEN,
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        sample_rate: NotGivenOr[int] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        api_secret: NotGivenOr[str] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
        extra_kwargs: NotGivenOr[RimeOptions] = NOT_GIVEN,
    ) -> None:
        pass

    @overload
    def __init__(
        self,
        model: InworldModels,
        *,
        voice: NotGivenOr[str] = NOT_GIVEN,
        language: NotGivenOr[str] = NOT_GIVEN,
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        sample_rate: NotGivenOr[int] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        api_secret: NotGivenOr[str] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
        extra_kwargs: NotGivenOr[InworldOptions] = NOT_GIVEN,
    ) -> None:
        pass

    @overload
    def __init__(
        self,
        model: str,
        *,
        voice: NotGivenOr[str] = NOT_GIVEN,
        language: NotGivenOr[str] = NOT_GIVEN,
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        sample_rate: NotGivenOr[int] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        api_secret: NotGivenOr[str] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> None:
        pass

    def __init__(
        self,
        model: TTSModels | str,
        *,
        voice: NotGivenOr[str] = NOT_GIVEN,
        language: NotGivenOr[str] = NOT_GIVEN,
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        sample_rate: NotGivenOr[int] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        api_secret: NotGivenOr[str] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
        extra_kwargs: NotGivenOr[
            dict[str, Any] | CartesiaOptions | ElevenlabsOptions | RimeOptions | InworldOptions
        ] = NOT_GIVEN,
    ) -> None:
        """Livekit Cloud Inference TTS

        Args:
            model (TTSModels | str): TTS model to use, in "provider/model" format
            voice (str, optional): Voice to use, use a default one if not provided
            language (str, optional): Language of the TTS model.
            encoding (TTSEncoding, optional): Encoding of the TTS model.
            sample_rate (int, optional): Sample rate of the TTS model.
            base_url (str, optional): LIVEKIT_URL, if not provided, read from environment variable.
            api_key (str, optional): LIVEKIT_API_KEY, if not provided, read from environment variable.
            api_secret (str, optional): LIVEKIT_API_SECRET, if not provided, read from environment variable.
            http_session (aiohttp.ClientSession, optional): HTTP session to use.
            extra_kwargs (dict, optional): Extra kwargs to pass to the TTS model.
        """
        sample_rate = sample_rate if is_given(sample_rate) else DEFAULT_SAMPLE_RATE
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True, aligned_transcript=False),
            sample_rate=sample_rate,
            num_channels=1,
        )

        lk_base_url = (
            base_url
            if is_given(base_url)
            else os.environ.get("LIVEKIT_INFERENCE_URL", DEFAULT_BASE_URL)
        )

        lk_api_key = (
            api_key
            if is_given(api_key)
            else os.getenv("LIVEKIT_INFERENCE_API_KEY", os.getenv("LIVEKIT_API_KEY", ""))
        )
        if not lk_api_key:
            raise ValueError(
                "api_key is required, either as argument or set LIVEKIT_API_KEY environmental variable"
            )

        lk_api_secret = (
            api_secret
            if is_given(api_secret)
            else os.getenv("LIVEKIT_INFERENCE_API_SECRET", os.getenv("LIVEKIT_API_SECRET", ""))
        )
        if not lk_api_secret:
            raise ValueError(
                "api_secret is required, either as argument or set LIVEKIT_API_SECRET environmental variable"
            )
        



        # Start with any extra kwargs passed in
        extra_kwargs_dict: dict[str, Any] = (
            dict(extra_kwargs) if is_given(extra_kwargs) else {}
        )

        # Read TTS rate from env var (LIVEKIT_TTS_RATE)
        # lower than 1.0 = slower, greater than 1.0 = faster
        try:
            tts_rate = float(os.environ.get("LIVEKIT_TTS_RATE", "1.0"))
        except Exception:
            tts_rate = 1.0

        if tts_rate != 1.0:
            # Many TTS backends accept "rate" or "speed"
            extra_kwargs_dict.setdefault("rate", tts_rate)
            extra_kwargs_dict.setdefault("speed", tts_rate)





        self._opts = _TTSOptions(
            model=model,
            voice=voice,
            language=language,
            encoding=encoding if is_given(encoding) else DEFAULT_ENCODING,
            sample_rate=sample_rate,
            base_url=lk_base_url,
            api_key=lk_api_key,
            api_secret=lk_api_secret,
            extra_kwargs=dict(extra_kwargs) if is_given(extra_kwargs) else {},
        )
        self._session = http_session
        self._pool = utils.ConnectionPool[aiohttp.ClientWebSocketResponse](
            connect_cb=self._connect_ws,
            close_cb=self._close_ws,
            max_session_duration=300,
            mark_refreshed_on_get=True,
        )
        self._streams = weakref.WeakSet[SynthesizeStream]()

    @classmethod
    def from_model_string(cls, model: str) -> TTS:
        """Create a TTS instance from a model string

        Args:
            model (str): TTS model to use, in "provider/model[:voice_id]" format

        Returns:
            TTS: TTS instance
        """
        voice: NotGivenOr[str] = NOT_GIVEN
        if (idx := model.rfind(":")) != -1:
            voice = model[idx + 1 :]
            model = model[:idx]
        return cls(model, voice=voice)

    @property
    def model(self) -> str:
        return self._opts.model

    @property
    def provider(self) -> str:
        return "livekit"

    async def _connect_ws(self, timeout: float) -> aiohttp.ClientWebSocketResponse:
        session = self._ensure_session()
        base_url = self._opts.base_url
        if base_url.startswith(("http://", "https://")):
            base_url = base_url.replace("http", "ws", 1)

        headers = {
            "Authorization": f"Bearer {create_access_token(self._opts.api_key, self._opts.api_secret)}",
        }
        ws = None
        try:
            ws = await asyncio.wait_for(
                session.ws_connect(f"{base_url}/tts", headers=headers), timeout
            )
        except (aiohttp.ClientConnectorError, asyncio.TimeoutError) as e:
            if isinstance(e, aiohttp.ClientResponseError) and e.status == 429:
                raise APIStatusError("LiveKit TTS quota exceeded", status_code=e.status) from e
            raise APIConnectionError("failed to connect to LiveKit TTS") from e

        params = {
            "type": "session.create",
            "sample_rate": str(self._opts.sample_rate),
            "encoding": self._opts.encoding,
            "extra": self._opts.extra_kwargs,
        }

        if self._opts.voice:
            params["voice"] = self._opts.voice
        if self._opts.model:
            params["model"] = self._opts.model
        if self._opts.language:
            params["language"] = self._opts.language

        try:
            await ws.send_str(json.dumps(params))
        except Exception as e:
            await ws.close()
            raise APIConnectionError("failed to send session.create message to LiveKit TTS") from e

        return ws

    async def _close_ws(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        await ws.close()

    def _ensure_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = utils.http_context.http_session()

        return self._session

    def prewarm(self) -> None:
        self._pool.prewarm()

    def update_options(
        self,
        *,
        voice: NotGivenOr[str] = NOT_GIVEN,
        model: NotGivenOr[TTSModels | str] = NOT_GIVEN,
        language: NotGivenOr[str] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> None:
        """
        Args:
            voice (str, optional): Voice.
            model (TTSModels | str, optional): TTS model to use.
            language (str, optional): Language code for the TTS model.
            extra_kwargs (dict, optional): Extra kwargs to pass to the TTS model.
        """
        if is_given(model):
            self._opts.model = model
        if is_given(voice):
            self._opts.voice = voice
        if is_given(language):
            self._opts.language = language
        if is_given(extra_kwargs):
            self._opts.extra_kwargs.update(extra_kwargs)

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts.ChunkedStream:
        raise NotImplementedError("ChunkedStream is not implemented")

    def stream(
        self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> SynthesizeStream:
        stream = SynthesizeStream(tts=self, conn_options=conn_options)
        self._streams.add(stream)
        return stream

    async def aclose(self) -> None:
        for stream in list(self._streams):
            await stream.aclose()

        self._streams.clear()
        await self._pool.aclose()


class SynthesizeStream(tts.SynthesizeStream):
    """Streamed API using websockets"""

    def __init__(self, *, tts: TTS, conn_options: APIConnectOptions):
        super().__init__(tts=tts, conn_options=conn_options)
        self._tts: TTS = tts

        self._opts = replace(tts._opts)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        request_id = utils.shortuuid()
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._opts.sample_rate,
            num_channels=1,
            stream=True,
            mime_type="audio/pcm",
        )

        sent_tokenizer_stream = tokenize.basic.SentenceTokenizer().stream()
        input_sent_event = asyncio.Event()

        async def _input_task() -> None:
            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    sent_tokenizer_stream.flush()
                    continue
                sent_tokenizer_stream.push_text(data)

            sent_tokenizer_stream.end_input()

        async def _sentence_stream_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            base_pkt: dict[str, Any] = {}
            base_pkt["type"] = "input_transcript"
            async for ev in sent_tokenizer_stream:
                token_pkt = base_pkt.copy()
                token_pkt["transcript"] = ev.token + " "
                token_pkt["extra"] = self._opts.extra_kwargs if self._opts.extra_kwargs else {}
                self._mark_started()
                await ws.send_str(json.dumps(token_pkt))
                input_sent_event.set()

            end_pkt = {
                "type": "session.flush",
            }
            await ws.send_str(json.dumps(end_pkt))
            # needed in case empty input is sent
            input_sent_event.set()

        async def _recv_task(ws: aiohttp.ClientWebSocketResponse) -> None:
            current_session_id: str | None = None
            await input_sent_event.wait()

            while True:
                msg = await ws.receive(timeout=self._conn_options.timeout)
                if msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    raise APIStatusError(
                        "Gateway connection closed unexpectedly", request_id=request_id
                    )

                if msg.type != aiohttp.WSMsgType.TEXT:
                    logger.warning("unexpected Gateway message type %s", msg.type)
                    continue

                data: dict[str, Any] = json.loads(msg.data)
                session_id = data.get("session_id")
                if current_session_id is None and session_id is not None:
                    current_session_id = session_id
                    output_emitter.start_segment(segment_id=session_id)

                if data.get("type") == "session.created":
                    pass
                elif data.get("type") == "output_audio":
                    b64data = base64.b64decode(data["audio"])
                    output_emitter.push(b64data)
                elif data.get("type") == "done":
                    output_emitter.end_input()
                    break
                elif data.get("type") == "error":
                    raise APIError(f"LiveKit TTS returned error: {msg.data}")
                else:
                    logger.warning("unexpected message %s", data)

        try:
            async with self._tts._pool.connection(timeout=self._conn_options.timeout) as ws:
                tasks = [
                    asyncio.create_task(_input_task()),
                    asyncio.create_task(_sentence_stream_task(ws)),
                    asyncio.create_task(_recv_task(ws)),
                ]

                try:
                    await asyncio.gather(*tasks)
                finally:
                    input_sent_event.set()
                    await sent_tokenizer_stream.aclose()
                    await utils.aio.gracefully_cancel(*tasks)

        except asyncio.TimeoutError:
            raise APITimeoutError() from None

        except aiohttp.ClientResponseError as e:
            raise APIStatusError(
                message=e.message, status_code=e.status, request_id=None, body=None
            ) from None

        except Exception as e:
            raise APIConnectionError() from e








# ---------------- synth -> WAV bytes (numpy fallback, resample to 48000 Hz mono PCM16) ----------------
import tempfile
import os
import wave

# numpy will be required (the project already has it). If not installed, install via pip.
import numpy as np

def _synthesize_to_wav_bytes(text: str, rate: int = 110, voice_index: int | None = None, target_samplerate: int = 48000) -> bytes:
    """Synthesize text with pyttsx3, then ensure WAV is mono PCM16 at target_samplerate and return bytes.
       Uses numpy-based fallback (no audioop required).
    """
    try:
        if pyttsx3 is None:
            raise RuntimeError("pyttsx3 missing")

        # clamp rate
        try:
            rate = max(40, min(int(rate), 220))
        except Exception:
            rate = 110

        engine = pyttsx3.init()
        try:
            engine.setProperty("rate", int(rate))
        except Exception:
            pass
        try:
            engine.setProperty("volume", 1.0)
        except Exception:
            pass
        try:
            if voice_index is not None:
                voices = engine.getProperty("voices")
                if 0 <= int(voice_index) < len(voices):
                    engine.setProperty("voice", voices[int(voice_index)].id)
        except Exception:
            pass

        # write a temp WAV from pyttsx3
        tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmpname = tf.name
        tf.close()

        engine.save_to_file(text, tmpname)
        engine.runAndWait()

        # read generated WAV
        with wave.open(tmpname, "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            frames = wf.readframes(nframes)

        # convert raw frames -> numpy array
        try:
            if sampwidth == 1:
                # 8-bit unsigned PCM
                arr = np.frombuffer(frames, dtype=np.uint8).astype(np.int32) - 128
                arr = (arr.astype(np.int16) << 8)  # scale to 16-bit range
            elif sampwidth == 2:
                arr = np.frombuffer(frames, dtype=np.int16).astype(np.int32)
            elif sampwidth == 3:
                # 24-bit packed -> convert to int32
                a = np.frombuffer(frames, dtype=np.uint8)
                a = a.reshape((-1, 3))
                # little-endian to int32
                arr = (a[:,0].astype(np.int32) | (a[:,1].astype(np.int32) << 8) | (a[:,2].astype(np.int32) << 16))
                # sign correction
                mask = arr & 0x800000
                arr = arr - (mask << 1)
                arr = (arr >> 8).astype(np.int32)  # downscale to 16-bit-ish
            else:
                # generic path: convert via int32 then scale
                dtype = np.uint8 if sampwidth == 1 else np.int16
                arr = np.frombuffer(frames, dtype=dtype).astype(np.int32)
        except Exception:
            # last-resort: return original bytes (so caller can detect failure)
            with open(tmpname, "rb") as f:
                data = f.read()
            try:
                os.unlink(tmpname)
            except Exception:
                pass
            return data

        # if stereo (or multi), reshape and convert to mono by averaging channels
        if nchannels > 1:
            arr = arr.reshape((-1, nchannels)).astype(np.int32)
            arr = arr.mean(axis=1).astype(np.int32)

        # now arr is int32-ish, convert to int16 range
        # normalize/clamp to int16
        arr = np.clip(arr, -32768, 32767).astype(np.int16)

        # resample if framerate != target_samplerate
        if framerate != target_samplerate:
            try:
                # simple linear interpolation resample (pure numpy)
                old_len = arr.shape[0]
                new_len = int(round(old_len * (target_samplerate / float(framerate))))
                if new_len <= 0:
                    new_len = 1
                old_idx = np.linspace(0, 1, old_len)
                new_idx = np.linspace(0, 1, new_len)
                arr = np.interp(new_idx, old_idx, arr).astype(np.int16)
                framerate = target_samplerate
            except Exception:
                pass

        out_tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        outname = out_tf.name
        out_tf.close()
        with wave.open(outname, "wb") as out_wf:
            # WRITE STEREO here (duplicate mono channel)
            out_wf.setnchannels(2)            # <- changed to 2 channels
            out_wf.setsampwidth(2)
            out_wf.setframerate(target_samplerate)
            # duplicate mono samples to L+R
            stereo_bytes = np.repeat(arr, 2).tobytes()
            out_wf.writeframes(stereo_bytes)
        with open(outname, "rb") as f:
            data = f.read()

        # cleanup
        try:
            os.unlink(tmpname)
        except Exception:
            pass
        try:
            os.unlink(outname)
        except Exception:
            pass

        try:
            print(f"SYNTH_LOCAL_WAV: produced {len(data)} bytes (rate={rate}, out_sr={target_samplerate})")
        except Exception:
            pass

        return data
    except Exception as e:
        try:
            print("SYNTH_LOCAL_WAV error:", e)
        except Exception:
            pass
        return b""
# -------------------------------------------------------------------------------------------







# Monkeypatch any common synth methods on module/class to use local WAV bytes
def _force_synthesize_audio_return(text: str, rate: int | None = None, voice_index: int | None = None, *a, **k):
    try:
        # prefer explicit rate -> env -> default
        if rate is None:
            rate = int(os.environ.get("LIVEKIT_TTS_RATE") or 110)
    except Exception:
        rate = 110
    return _synthesize_to_wav_bytes(text, rate=rate, voice_index=voice_index)

# If module defines a synth function, override it
for nm in ("synthesize_audio", "synthesize", "synthesize_to_bytes", "synthesize_wav"):
    if nm in globals():
        globals()[nm] = _force_synthesize_audio_return

# If a TTS class exists, override instance synth methods
TTS_cls = globals().get("TTS") or globals().get("TTSModels") or globals().get("TTSClient")
if isinstance(TTS_cls, type):
    for mname in ("synthesize_audio", "synthesize", "synthesize_to_bytes", "synthesize_wav", "synthesize_audio_bytes"):
        if hasattr(TTS_cls, mname):
            def _wrap(mname):
                def _method(self, text, *a, **k):
                    rate = k.get("rate") or k.get("speed") or None
                    voice_index = k.get("voice_index") or None
                    return _force_synthesize_audio_return(text, rate=rate, voice_index=voice_index)
                return _method
            setattr(TTS_cls, mname, _wrap(mname))

print("tts.py: FORCE_LOCAL_SYNTH active (pyttsx3 -> WAV bytes).")
# -------------------------------------------------------------------------------------------

