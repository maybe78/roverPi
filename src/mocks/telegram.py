import logging

logger = logging.getLogger("mock.telegram")


class MockTelegram:
    def __init__(self, **kwargs):
        logger.info("MockTelegram: messages will be logged, not sent")

    def send_text_message(self, text: str, **kwargs) -> dict:
        logger.info(f"Telegram → \"{text}\"")
        print(f"\n📱 Telegram: {text}\n", flush=True)
        return {"ok": True, "mock": True}

    def send_photo_message(self, photo_path: str,
                           caption: str = None, **kwargs) -> dict:
        logger.info(f"Telegram photo → {photo_path} | {caption}")
        return {"ok": True, "mock": True}

    def send_photo_from_bytes(self, photo_bytes: bytes,
                              caption: str = None, **kwargs) -> dict:
        logger.info(f"Telegram photo (bytes, {len(photo_bytes)}B) | {caption}")
        return {"ok": True, "mock": True}

    def capture_and_send_photo(self, caption: str = None, **kwargs) -> dict:
        logger.info(f"Telegram capture+send | {caption}")
        return {"ok": True, "mock": True}
