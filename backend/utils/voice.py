import threading
import queue
import logging
import time


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

# Track last spoken objects to avoid repetition
_last_spoken_set = set()
_last_spoken_text = ""
_last_spoken_time = 0.0


def _format_sentence(items):
    """Convert a list of items into a natural sentence.
    
    Examples:
        ["person"] -> "Detected object is person"
        ["person", "chair"] -> "Detected objects are person and chair"
        ["person", "chair", "bottle"] -> "Detected objects are person, chair and bottle"
    """
    if not items:
        return ""
    
    if len(items) == 1:
        return f"Detected object is {items[0]}"
    elif len(items) == 2:
        return f"Detected objects are {items[0]} and {items[1]}"
    else:
        # Join all except last with commas, then add "and" before last item
        all_but_last = ", ".join(items[:-1])
        return f"Detected objects are {all_but_last} and {items[-1]}"


def speak_items(items, avoid_repetition=False):
    """Speak a list of items as a natural sentence (non-blocking).
    
    Args:
        items: List of item names to speak
        avoid_repetition: If True, only speak if the set of items has changed
    """
    global _VOICE, _last_spoken_set
    
    if not items:
        return
    
    # Check if we should skip due to repetition
    if avoid_repetition:
        current_set = set(items)
        if current_set == _last_spoken_set:
            return  # Same objects as last time, skip
        _last_spoken_set = current_set
    
    if _VOICE is None:
        try:
            _VOICE = _VoiceWorker()
        except Exception:
            logging.exception("Failed to create VoiceWorker; voice disabled")
            return

    # Format the sentence naturally
    text = _format_sentence(items)
    logging.info(f"Voice output: {text}")
    _VOICE.speak(text)


def speak_text(text, avoid_repetition=True, cooldown_sec=2.5):
    """Speak a raw text message (non-blocking) with smart repetition control."""
    global _VOICE, _last_spoken_text, _last_spoken_time

    if not text:
        return

    now = time.time()
    if avoid_repetition:
        if text == _last_spoken_text and (now - _last_spoken_time) < cooldown_sec:
            return

    _last_spoken_text = text
    _last_spoken_time = now

    if _VOICE is None:
        try:
            _VOICE = _VoiceWorker()
        except Exception:
            logging.exception("Failed to create VoiceWorker; voice disabled")
            return

    logging.info(f"Voice output: {text}")
    _VOICE.speak(text)
