"""Безопасный буфер обмена с автоочисткой."""
import threading
import pyperclip


def copy_secure(text: str, clear_after_seconds: int = 20) -> None:
    """Копирует текст и очищает буфер через N секунд."""
    pyperclip.copy(text)

    def _clear():
        import time
        time.sleep(clear_after_seconds)
        # Очищаем только если в буфере всё ещё наш текст
        try:
            if pyperclip.paste() == text:
                pyperclip.copy("")
        except Exception:
            pass

    t = threading.Thread(target=_clear, daemon=True)
    t.start()