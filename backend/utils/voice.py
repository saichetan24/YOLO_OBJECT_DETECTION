import threading
import queue
import logging


# Lazily initialized voice worker. We avoid initializing pyttsx3 at import time
# because on some systems pyttsx3/pywin32 may require system DLLs that are not
# available in the environment. Initialization is attempted when first needed.
class _VoiceWorker:
    def __init__(self, rate=150, volume=1.0):
        self._q = queue.Queue()
        self._engine = None
        self._rate = rate
        self._volume = volume
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _init_engine(self):
        if self._engine is not None:
            return True
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            try:
                self._engine.setProperty("rate", self._rate)
                self._engine.setProperty("volume", self._volume)
            except Exception:
                logging.exception("pyttsx3 setProperty failed")
            return True
        except Exception:
            logging.exception("Failed to initialize pyttsx3; voice disabled")
            self._engine = None
            return False

    def speak(self, text: str):
        if not text:
            return
        self._q.put(str(text))

    def _run(self):
        while True:
            text = self._q.get()
            try:
                if self._engine is None:
                    ok = self._init_engine()
                    if not ok:
                        # drop the message; engine unavailable
                        logging.warning("Voice engine unavailable; dropping speech request")
                        continue
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:
                logging.exception("Voice engine failed while speaking")
            finally:
                try:
                    self._q.task_done()
                except Exception:
                    pass


# Singleton instance used by the app; created lazily below
_VOICE = None


def speak_items(items):
    """Speak a list of items (non-blocking)."""
    global _VOICE
    if not items:
        return
    if _VOICE is None:
        try:
            _VOICE = _VoiceWorker()
        except Exception:
            logging.exception("Failed to create VoiceWorker; voice disabled")
            return

    if isinstance(items, (list, tuple)):
        text = ", ".join(map(str, items))
    else:
        text = str(items)
    _VOICE.speak(text)
