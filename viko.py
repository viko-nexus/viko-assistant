import asyncio
import threading
import sys
import traceback
from pathlib import Path

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

from viko.ui     import VikoUI
from viko.core.memory import (
    update_memory,
    should_extract_memory, extract_memory, remember,
)
from viko.core.conversation import (
    start_session as conv_start_session,
    end_session   as conv_end_session,
    save_message  as conv_save_message,
    get_recent_messages,
    summarize_session_async,
)
from viko.core.context_builder import build_system_context
from viko.core.vector_store import index_message as vs_index_message
from viko.core.logger import get_logger
from viko.core.speaker_verifier import SpeakerVerifier

_log = get_logger("main")

from viko.tools.declarations import TOOL_DECLARATIONS
from viko.tools.executor import execute_tool as _execute_tool_fn
import viko.core.offline as _offline
import viko.core.client as _client_module


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR            = get_base_dir()
PROMPT_PATH         = BASE_DIR / "viko" / "prompt.txt"
# Half-cascade Live model. The gemini-2.5-flash-native-audio-* models have a
# widely-reported bug (discuss.ai.google.dev/t/.../114644, livekit/agents#4545)
# where the session rejects realtime audio input after a tool_call → WebSocket
# 1008 "operation not supported" → drop. VIKO streams audio continuously, so it
# hit this constantly. The 3.1 live model isn't native-audio, supports the same
# Kore voice + tools, and doesn't have the bug.
LIVE_MODEL          = "models/gemini-3.1-flash-live-preview"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024
SPEECH_THRESHOLD    = 40    # int16 RMS — active speech (MacBook Air mic level)
AUDIO_GAIN          = 3.0   # software amplification for output (1.0 = no change)
SILENCE_CHUNKS      = 20    # ~1.3s silence ends an utterance
MIN_SPEECH_CHUNKS   = 8     # ~512ms minimum speech to process
# NOTE: lowered to clear the stale Jun-7 voice profile, which scores the owner's
# own voice only ~0.46–0.54. Raise back toward 0.60/0.55 after a clean re-enroll
# restores proper owner/stranger separation (owner should then score ~0.7+).
SV_PASS_THRESHOLD  = 0.50  # similarity >= this → verified owner
SV_BLOCK_THRESHOLD = 0.40  # similarity <  this → blocked non-owner

# Wake-word output gating ("only reply when called Viko"). Disabled: gating
# Gemini's audio post-hoc on the input transcription is racy (audio starts before
# "Viko" is transcribed) and misses non-Latin transcriptions. Speaker verification
# already restricts replies to the owner. The _is_viko_addressed matcher is kept
# for a future non-racy (input-side) redesign. Flip to True to re-enable.
WAKE_WORD_ENABLED = False


def _get_api_key() -> str:
    from viko.core.config import get_gemini_key
    return get_gemini_key()


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are Viko, a sharp and efficient AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )


_last_memory_input = ""


def _update_memory_async(user_text: str, viko_text: str) -> None:
    global _last_memory_input

    user_text = (user_text or "").strip()
    viko_text = (viko_text or "").strip()

    if len(user_text) < 5 or user_text == _last_memory_input:
        return
    _last_memory_input = user_text

    try:
        api_key = _get_api_key()
        if not should_extract_memory(user_text, viko_text, api_key):
            return
        data = extract_memory(user_text, viko_text, api_key)
        if data:
            update_memory(data)
            print(f"[Memory] {list(data.keys())}")
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] {e}")



import re as _re
_CTRL_SEQ_RE = _re.compile(r'^<ctrl\d+>$', _re.IGNORECASE)

def _is_ctrl_seq(text: str) -> bool:
    return bool(_CTRL_SEQ_RE.match(text.strip()))


# Gemini Live's input transcription has no language setting and runs an English/
# multilingual acoustic model, so the Indonesian wake word "Viko" (VEE-koh) comes
# back inconsistently — "Vico", "Pico", "Biko", "Fico", "Ficou", "Focou" etc.
# A fixed variant list can't enumerate them all, so match the phonetic SHAPE:
# labial onset [v/b/p/f/w] + front vowel [i/e/o] + velar [c/k] + back vowel [o/u].
# This catches the mishearings while rejecting normal ID/EN words (buka, baik,
# back, book, fokus). False positives are cheap (speaker verification gates to the
# owner, a stray wake is minor); a MISSED wake — VIKO ignoring you — is not.
_WAKE_RE    = _re.compile(r"^[vbpfw][ieo]+[ck]+[ou]+$")
_WAKE_EXTRA = frozenset({"viktor"})  # outlier the shape pattern can't match

def _is_viko_addressed(accumulated: str) -> bool:
    return any(_WAKE_RE.match(w) or w in _WAKE_EXTRA
               for w in _re.findall(r"[a-z]+", accumulated.lower()))


def _rms(pcm_bytes: bytes) -> float:
    """RMS energy of int16 PCM bytes. Returns 0.0 for empty input."""
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0


class VikoLive:

    SESSION_MAX_IDLE = 8 * 60  # seconds — reconnect if idle this long

    def __init__(self, ui: VikoUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self._last_active   = 0.0
        self._session_id    = 0
        self._offline_stt   = None  # pre-warmed OfflineSTT instance
        self._sv                  = SpeakerVerifier()
        self._verification_bypass = False
        self._enrolling           = False
        self._enroll_buf: list    = []
        self._enroll_target: int  = 0
        self._sv_verified:   bool = True   # updated by _verify_and_forward background loop
        self._viko_addressed: bool = False  # set when "viko" detected in input_transcription
        self._vad_model             = None  # loaded lazily in _listen_audio
        self.raw_queue            = None
        self.ui.on_text_command = self._on_text_command
        self.ui.on_file_command = self._on_file_command

    def _on_text_command(self, text: str):
        if self.ui.paused:
            return

        # Passphrase bypass — must check before logging to avoid exposing it on screen
        from viko.core.config import get_owner_passphrase
        passphrase = get_owner_passphrase()
        if passphrase and text.strip() == passphrase:
            self.ui.write_log("YOU: [passphrase]")
            def _reset_bypass():
                self._verification_bypass = False
                self.ui.write_log("SYS: Bypass verifikasi suara nonaktif.")
            self._verification_bypass = True
            if self._loop:
                self._loop.call_later(300, _reset_bypass)
            self.ui.write_log("SYS: Bypass aktif 5 menit.")
            return  # never sent to Gemini

        self.ui.write_log(f"YOU: {text}")

        # Re-enrollment phrase. Typed (not spoken) — physical keyboard access already
        # implies the owner, so no passphrase/bypass gate is needed here.
        if text.strip().lower() == "viko, kenali suaraku":
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._start_re_enrollment(), self._loop
                )
            return  # never sent to Gemini

        if not self._loop or not self.session:
            self.ui.write_log("SYS: Session not ready — try again in a moment.")
            return
        self._viko_addressed = True  # text command — allow response through gate
        fut = asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"role": "user", "parts": [{"text": text}]},
                turn_complete=True,
            ),
            self._loop,
        )
        def _on_done(f):
            try:
                f.result()
            except Exception as exc:
                self.ui.write_log(f"ERR: text send failed — {exc}")
        fut.add_done_callback(_on_done)

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        try:
            if value:
                self.ui.set_state("SPEAKING")
            elif not self.ui.muted:
                self.ui.set_state("LISTENING")
        except RuntimeError:
            pass  # Qt window already destroyed during shutdown

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        self._viko_addressed = True  # VIKO-initiated speech bypasses wake word gate
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def _warmup_offline_stt(self) -> None:
        """Download and load faster-whisper model in background thread (called once after connect)."""
        try:
            from viko.core.offline_stt import OfflineSTT
            stt = OfflineSTT()
            stt._load()
            self._offline_stt = stt
            print("[Viko] Offline STT model ready")
            self.ui.write_log("SYS: Model offline siap.")
        except Exception as _e:
            print(f"[Viko] Offline STT warmup failed: {_e}")

    async def _enroll_voice(self) -> None:
        """Record 10 seconds of mic audio and save owner voice profile."""
        loop = asyncio.get_running_loop()
        audio_q: asyncio.Queue = asyncio.Queue()

        def _cb(indata, frames, time_info, status):
            loop.call_soon_threadsafe(audio_q.put_nowait, indata.tobytes())

        target = int(10 * SEND_SAMPLE_RATE / CHUNK_SIZE)  # ~156 chunks = 10s
        chunks = []

        with sd.InputStream(
            samplerate=SEND_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            callback=_cb,
        ):
            for i in range(target):
                chunk = await audio_q.get()
                chunks.append(chunk)

        pcm = b"".join(chunks)
        await loop.run_in_executor(None, self._sv.enroll, pcm)

    async def _start_re_enrollment(self) -> None:
        """Signal _verify_and_forward() to collect 10s of audio for re-enrollment."""
        self.ui.write_log("SYS: Silakan berbicara bebas selama 10 detik untuk mendaftarkan suara baru...")
        self._enroll_buf    = []
        self._enroll_target = int(10 * SEND_SAMPLE_RATE / CHUNK_SIZE)
        self._enrolling     = True

    async def _offline_mode(self, max_seconds: int = 60) -> None:
        from viko.core.offline_stt import OfflineSTT
        await _offline.offline_mode(
            stt=self._offline_stt or OfflineSTT(),
            sv=self._sv,
            sv_pass_threshold=SV_PASS_THRESHOLD,
            verification_bypass=self._verification_bypass,
            is_muted=lambda: self.ui.muted,
            is_paused=lambda: self.ui.paused,
            write_log=self.ui.write_log,
            sample_rate=SEND_SAMPLE_RATE,
            channels=CHANNELS,
            chunk_size=CHUNK_SIZE,
            speech_threshold=SPEECH_THRESHOLD,
            silence_chunks=SILENCE_CHUNKS,
            min_speech_chunks=MIN_SPEECH_CHUNKS,
            max_seconds=max_seconds,
        )

    def _on_file_command(self, path: str):
        """Called when user uploads a file. Images are sent as vision input."""
        import mimetypes
        from pathlib import Path as _P
        p = _P(path)
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        is_image = mime.startswith("image/")
        size = p.stat().st_size
        size_str = (f"{size//1_048_576}MB" if size >= 1_048_576
                    else f"{size//1024}KB" if size >= 1024 else f"{size}B")
        self.ui.write_log(f"FILE: {p.name} ({size_str}) → {'vision' if is_image else 'text'}")

        if not self._loop or not self.session:
            self.ui.write_log("SYS: Session not ready.")
            return

        if is_image:
            # Send image data directly to Gemini Live vision
            self._viko_addressed = True  # file upload — allow response through gate
            async def _send_img():
                data = p.read_bytes()
                await self.session.send_realtime_input(
                    video=types.Blob(mime_type=mime, data=data)
                )
                await self.session.send_client_content(
                    turns={"role": "user",
                           "parts": [{"text": f"[Image uploaded: {p.name}] Analisa gambar ini."}]},
                    turn_complete=True,
                )
            fut = asyncio.run_coroutine_threadsafe(_send_img(), self._loop)
        else:
            # Non-image: just notify with text so VIKO can ask what to do
            self._viko_addressed = True  # file upload — allow response through gate
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size_str} | "
                f"File '{p.name}' sudah diupload. Tanya mau diapakan."
            )
            fut = asyncio.run_coroutine_threadsafe(
                self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": msg}]},
                    turn_complete=True,
                ),
                self._loop,
            )

        def _on_done(f):
            try:
                f.result()
            except Exception as exc:
                self.ui.write_log(f"ERR: file send failed — {exc}")
        fut.add_done_callback(_on_done)

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"{tool_name} encountered an error. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime
        from viko.core.config import get_voice, get_voice_language

        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        history_ctx = build_system_context()

        parts = [time_ctx]
        if history_ctx:
            parts.append(history_ctx)
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=get_voice()
                    )
                ),
                language_code=get_voice_language(),
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        return await _execute_tool_fn(fc, ui=self.ui, speak=self.speak, speak_error=self.speak_error)

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            # 3.1 live API: media= is deprecated, use audio= (typed Blob)
            await self.session.send_realtime_input(
                audio=types.Blob(data=msg["data"], mime_type=msg["mime_type"])
            )

    async def _listen_audio(self):
        import threading as _threading

        if self._vad_model is None:
            try:
                from silero_vad import load_silero_vad
                self._vad_model = load_silero_vad()
            except Exception as _e:
                print(f"[Viko] VAD load failed ({_e}) — treating all audio as speech")
                self._vad_model = False  # sentinel: unavailable

        try:
            dev = sd.query_devices(kind='input')
            print(f"[Viko] Mic: {dev['name']} @ {SEND_SAMPLE_RATE}Hz")
        except Exception:
            print("[Viko] Mic started")

        loop = asyncio.get_running_loop()
        _stop = _threading.Event()
        _vad  = self._vad_model if self._vad_model is not False else None

        def _audio_thread():
            import numpy as _np
            import torch as _torch
            try:
                with sd.RawInputStream(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                ) as stream:
                    print("[Viko] Mic stream open")
                    while not _stop.is_set():
                        data, _ = stream.read(CHUNK_SIZE)
                        with self._speaking_lock:
                            viko_speaking = self._is_speaking
                        if viko_speaking or self.ui.muted or self.ui.paused:
                            continue
                        pcm_f32 = _np.frombuffer(bytes(data), dtype=_np.int16).astype(_np.float32) / 32768.0
                        if _vad is not None:
                            # Silero VAD requires 512-sample windows at 16kHz
                            half = pcm_f32[:512]
                            try:
                                with _torch.no_grad():
                                    speech_prob = float(_vad(_torch.from_numpy(half), SEND_SAMPLE_RATE))
                            except Exception:
                                speech_prob = 1.0  # fallback: treat as speech on VAD error
                        else:
                            speech_prob = 1.0  # VAD unavailable — pass all audio through
                        item = {
                            "data":      bytes(data),
                            "mime_type": "audio/pcm",
                            "is_speech": speech_prob > 0.5,
                        }
                        try:
                            loop.call_soon_threadsafe(self.raw_queue.put_nowait, item)
                        except Exception:
                            pass  # drop if loop is closed
            except Exception as _e:
                print(f"[Viko] Mic error: {_e}")

        t = _threading.Thread(target=_audio_thread, daemon=True)
        t.start()

        try:
            await asyncio.Event().wait()
        finally:
            _stop.set()

    async def _verify_and_forward(self):
        """Run speaker verification in background; always forward real audio to out_queue.

        Updates self._sv_verified (True/False). Output gating happens in _receive_audio.
        Accumulates only speech chunks (is_speech=True) for resemblyzer so silence windows
        don't dilute the embedding.
        """
        loop = asyncio.get_running_loop()
        verify_buf:      list[bytes] = []
        VERIFY_CHUNKS    = 32    # 32 × 64ms ≈ 2s — minimum for reliable resemblyzer embedding
        PASS_THRESHOLD   = SV_PASS_THRESHOLD
        BLOCK_THRESHOLD  = SV_BLOCK_THRESHOLD
        RECOVERY_WINDOWS = 5
        ambiguous_streak = 0

        while True:
            item        = await self.raw_queue.get()
            chunk_bytes = item["data"]
            is_speech   = item.get("is_speech", True)

            # Re-enrollment: collect audio, skip normal verification
            if self._enrolling:
                self._enroll_buf.append(item)
                if len(self._enroll_buf) >= self._enroll_target:
                    self._enrolling   = False
                    pcm = b"".join(i["data"] for i in self._enroll_buf)
                    self._enroll_buf  = []
                    await loop.run_in_executor(None, self._sv.enroll, pcm)
                    self.ui.write_log("SYS: Suara berhasil didaftarkan.")
                    self._sv_verified = True
                    ambiguous_streak  = 0
                    verify_buf        = []
                continue

            # Accumulate speech-only chunks for periodic verification
            if is_speech:
                verify_buf.append(chunk_bytes)

            if len(verify_buf) >= VERIFY_CHUNKS:
                pcm        = b"".join(verify_buf)
                verify_buf = verify_buf[-8:]   # keep ~500ms overlap
                if self._sv.is_enrolled() and not self._verification_bypass:
                    sim = await loop.run_in_executor(None, self._sv.similarity, pcm)
                    print(f"[SV] similarity={sim:.3f} verified={self._sv_verified}")
                    if sim >= PASS_THRESHOLD:
                        self._sv_verified = True
                        ambiguous_streak  = 0
                    elif sim < BLOCK_THRESHOLD:
                        self._sv_verified = False
                        ambiguous_streak  = 0
                    else:
                        # ambiguous (0.55–0.60): if blocked, count toward auto-recovery
                        if not self._sv_verified:
                            ambiguous_streak += 1
                            if ambiguous_streak >= RECOVERY_WINDOWS:
                                self._sv_verified = True
                                ambiguous_streak  = 0
                                print("[SV] auto-recovery: reopened after silence")

            # Always forward real audio — output gating is in _receive_audio
            media_item = {"data": item["data"], "mime_type": item["mime_type"]}
            await self.out_queue.put(media_item)

    async def _receive_audio(self):
        print("[Viko] Receive started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        try:
                            addressed = self._viko_addressed or not WAKE_WORD_ENABLED
                            if addressed and (
                                self._sv_verified
                                or self._verification_bypass
                                or not self._sv.is_enrolled()
                            ):
                                self.audio_in_queue.put_nowait(response.data)
                        except asyncio.QueueFull:
                            pass  # drop chunk under load; preferable to crashing

                    if response.server_content:
                        sc = response.server_content

                        if sc.interrupted:
                            while not self.audio_in_queue.empty():
                                try:
                                    self.audio_in_queue.get_nowait()
                                except Exception:
                                    break
                            self.set_speaking(False)
                            out_buf = []

                        if sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            txt = sc.output_transcription.text
                            if txt and not _is_ctrl_seq(txt):
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text
                            if txt and not _is_ctrl_seq(txt):
                                in_buf.append(txt)
                                if WAKE_WORD_ENABLED and not self._viko_addressed \
                                        and _is_viko_addressed("".join(in_buf)):
                                    self._viko_addressed = True
                                    print(f"[Viko] wake word detected — gate open ({txt!r})")

                        if sc.turn_complete:
                            self._viko_addressed = False   # reset for next turn
                            self.set_speaking(False)
                            self._last_active = asyncio.get_event_loop().time()

                            full_in = "".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = "".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Viko: {full_out}")
                            out_buf = []

                            if full_in and len(full_in) > 5:
                                # Keyword trigger: "viko, ingat ini..."
                                _lower = full_in.lower()
                                if "ingat ini" in _lower:
                                    _after = full_in[_lower.find("ingat ini") + 9:].strip().lstrip(":").strip()
                                    if _after:
                                        _key = f"note_{int(asyncio.get_event_loop().time())}"
                                        threading.Thread(
                                            target=remember,
                                            args=(_key, _after, "notes"),
                                            daemon=True
                                        ).start()
                                        self.speak("Oke, sudah saya ingat.")

                                # Save to SQLite + ChromaDB in background
                                _sid = self._session_id
                                def _persist(user_txt=full_in, viko_txt=full_out, sid=_sid):
                                    try:
                                        mid = conv_save_message(sid, "user", user_txt)
                                        vs_index_message(user_txt, "user", sid, mid)
                                        if viko_txt:
                                            mid2 = conv_save_message(sid, "viko", viko_txt)
                                            vs_index_message(viko_txt, "viko", sid, mid2)
                                    except Exception as _e:
                                        print(f"[Memory] Persist failed: {_e}")
                                threading.Thread(target=_persist, daemon=True).start()

                                threading.Thread(
                                    target=_update_memory_async,
                                    args=(full_in, full_out),
                                    daemon=True
                                ).start()

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[Viko] Tool: {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )

        except Exception as e:
            print(f"[Viko] Receive error: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        try:
            dev = sd.query_devices(kind='output')
            print(f"[Viko] Output: {dev['name']} @ {RECEIVE_SAMPLE_RATE}Hz")
        except Exception:
            print("[Viko] Audio playback started")

        # latency='high' gives PortAudio a larger internal ring-buffer (~200-500ms)
        # so the device keeps playing even if asyncio is briefly delayed by tools.
        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=0,       # let PortAudio choose optimal block size
            latency=0.1,       # 100ms explicit buffer — safe on macOS, ~3x better than "high"
        )
        stream.start()
        loop = asyncio.get_running_loop()
        _speak_off_handle = None
        try:
            while True:
                # Wait for first chunk
                chunk = await self.audio_in_queue.get()
                # Cancel any pending speaking=False — new audio arrived
                if _speak_off_handle is not None:
                    _speak_off_handle.cancel()
                    _speak_off_handle = None
                self.set_speaking(True)
                # Drain any queued chunks without waiting (batch write reduces
                # asyncio round-trips and keeps PortAudio buffer fed)
                chunks = [chunk]
                while True:
                    try:
                        chunks.append(self.audio_in_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                data = b"".join(chunks)
                if AUDIO_GAIN != 1.0:
                    pcm = np.frombuffer(data, dtype=np.int16)
                    data = np.clip(pcm * AUDIO_GAIN, -32768, 32767).astype(np.int16).tobytes()
                await asyncio.to_thread(stream.write, data)
                if self.audio_in_queue.empty():
                    # Debounce: schedule speaking=False 150ms from now.
                    # call_later doesn't block consumption so the queue stays drained.
                    _speak_off_handle = loop.call_later(0.15, self.set_speaking, False)
        except Exception as e:
            print(f"[Viko] Playback error: {e}")
            raise
        finally:
            if _speak_off_handle is not None:
                _speak_off_handle.cancel()
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def _session_watchdog(self):
        while True:
            await asyncio.sleep(30)
            if self._last_active == 0.0:
                continue
            idle = asyncio.get_event_loop().time() - self._last_active
            if idle >= self.SESSION_MAX_IDLE and not self._is_speaking:
                print(f"[Viko] Session idle {idle:.0f}s — refreshing connection")
                self.ui.write_log("SYS: Refreshing connection...")
                raise RuntimeError("Session idle refresh")

    async def _network_watchdog(self):
        """Detect network loss within ~10s by probing 8.8.8.8:53 (Google DNS).

        Raises RuntimeError when the probe fails 2 times in a row so the main
        loop drops to offline mode instead of waiting up to 8 minutes for the
        idle watchdog to fire.
        """
        PROBE_HOST    = "8.8.8.8"
        PROBE_PORT    = 53
        PROBE_TIMEOUT = 3.0
        INTERVAL      = 10
        failures      = 0

        await asyncio.sleep(15)  # give Gemini time to finish its own connect
        while True:
            try:
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: __import__("socket").create_connection(
                            (PROBE_HOST, PROBE_PORT), timeout=PROBE_TIMEOUT
                        ).close()
                    ),
                    timeout=PROBE_TIMEOUT + 1,
                )
                failures = 0
            except Exception:
                failures += 1
                print(f"[Net] probe failed ({failures}/2)")
                if failures >= 2:
                    print("[Net] network unreachable — dropping Gemini session")
                    raise RuntimeError("Network unreachable")
            await asyncio.sleep(INTERVAL)

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        self.ui.write_log("SYS: App dimulai ulang.")

        # Boot phase 1: loading memory + context
        self.ui.set_boot_progress(0.1, "LOADING MEMORY...")
        await asyncio.sleep(0.05)
        self.ui.set_boot_progress(0.35, "BUILDING CONTEXT...")
        await asyncio.sleep(0.05)

        # Enrollment: first launch (no voice profile yet)
        if not self._sv.is_enrolled():
            self.ui.set_boot_progress(0.45, "MENDAFTARKAN SUARA...")
            self.ui.write_log("SYS: Silakan berbicara bebas selama 10 detik...")
            await self._enroll_voice()
            self.ui.write_log("SYS: Suara berhasil didaftarkan.")

        _first_connect = True
        _reconnect = True

        while _reconnect:
            try:
                if _first_connect:
                    self.ui.set_boot_progress(0.6, "CONNECTING...")
                print("[Viko] Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    # Gemini streams a full reply faster than real-time playback, so this
                    # buffer must hold an ENTIRE response or long replies get truncated when
                    # _receive_audio drops chunks on QueueFull. 2000 chunks ≈ 80s of speech.
                    self.audio_in_queue = asyncio.Queue(maxsize=2000)
                    self.out_queue      = asyncio.Queue(maxsize=200)  # sized to hold full utterance burst from _verify_and_forward
                    self.raw_queue      = asyncio.Queue(maxsize=200)
                    self._last_active   = asyncio.get_event_loop().time()
                    self._enrolling     = False
                    self._enroll_buf    = []

                    # Start a new SQLite session
                    try:
                        self._session_id = conv_start_session()
                        print(f"[Conversation] Session started: {self._session_id}")
                    except Exception as _e:
                        print(f"[Conversation] Session start failed: {_e}")
                        self._session_id = 0

                    if _first_connect:
                        self.ui.set_boot_progress(1.0, "ONLINE")
                        _first_connect = False

                    print("[Viko] Connected.")
                    _client_module.active_model = "Gemini 3.1 Flash Live"
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: Viko online.")

                    # Pre-load offline STT model in background so offline mode starts instantly
                    if self._offline_stt is None:
                        self.ui.write_log("SYS: Mempersiapkan model offline...")
                        threading.Thread(target=self._warmup_offline_stt, daemon=True).start()

                    # Announce self-update restart if flag was set by restarter.py
                    try:
                        from viko.self_engineer.restarter import check_and_clear_flag
                        _restart_msg = check_and_clear_flag()
                        if _restart_msg:
                            self.ui.write_log("SYS: Restarted after self-update.")
                            async def _announce_restart(msg=_restart_msg):
                                await asyncio.sleep(2.0)
                                await session.send_client_content(
                                    turns={"parts": [{"text": msg}]},
                                    turn_complete=True
                                )
                            tg.create_task(_announce_restart())
                    except Exception as _re:
                        print(f"[SelfEngineer] Restart check failed: {_re}")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._session_watchdog())
                    tg.create_task(self._network_watchdog())
                    tg.create_task(self._verify_and_forward())

            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                print(f"[Viko] {type(e).__name__}: {e}")
                traceback.print_exc()
            finally:
                # Always clean up session and enter offline mode before reconnect
                if self._session_id:
                    try:
                        conv_end_session(self._session_id)
                        msgs = get_recent_messages(30)
                        summarize_session_async(self._session_id, msgs)
                    except Exception as _e:
                        print(f"[Conversation] Session end failed: {_e}")

                self.set_speaking(False)
                try:
                    self.ui.set_state("OFFLINE")
                    if _first_connect:
                        # Never connected — dismiss boot screen so dashboard shows
                        self.ui.set_boot_progress(1.0, "GEMINI OFFLINE")
                        _first_connect = False
                    _client_module.active_model = ""  # cleared until OpenRouter picks up
                except RuntimeError:
                    _reconnect = False  # Qt window destroyed — stop reconnect loop
                if _reconnect:
                    print("[Viko] Connection lost — offline mode")
                    try:
                        await self._offline_mode()
                    except Exception as _oe:
                        print(f"[Viko] Offline mode error: {_oe}")
                    try:
                        self.ui.set_state("THINKING")
                    except RuntimeError:
                        _reconnect = False
                if _reconnect:
                    print("[Viko] Reconnecting...")
                    await asyncio.sleep(1)


def main():
    _log.info("=" * 60)
    _log.info("VIKO startup")
    ui = VikoUI("face.png")
    ui.set_boot_progress(0.0, "INITIALIZING...")

    def runner():
        ui.wait_for_api_key()
        viko = VikoLive(ui)
        try:
            asyncio.run(viko.run())
        except KeyboardInterrupt:
            _log.info("VIKO shutdown (keyboard interrupt)")
            print("\nShutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()
    _log.info("VIKO shutdown")


if __name__ == "__main__":
    main()
