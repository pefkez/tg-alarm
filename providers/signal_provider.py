import asyncio, logging, subprocess, json, tempfile, os

logger = logging.getLogger(__name__)


class SignalProvider:
    def __init__(self):
        self.ready = False

    async def init(self):
        try:
            result = subprocess.run(["signal-cli", "--version"],
                capture_output=True, text=True, timeout=10)
            self.ready = result.returncode == 0
            if self.ready:
                logger.info("Signal provider ready")
        except FileNotFoundError:
            logger.warning("signal-cli not found, Signal unavailable")
            self.ready = False
        except Exception as e:
            logger.error(f"Signal init error: {e}")
            self.ready = False

    async def send_message(self, target, text):
        if not self.ready:
            return
        try:
            subprocess.run(
                ["signal-cli", "-u", os.getenv("SIGNAL_NUMBER", ""),
                 "send", "-m", text, target],
                capture_output=True, timeout=30
            )
        except Exception as e:
            logger.error(f"Signal send error: {e}")

    async def wait_for_reply(self, target, on_reply, check_interval=15):
        if not self.ready:
            return False
        try:
            while True:
                await asyncio.sleep(check_interval)
                result = subprocess.run(
                    ["signal-cli", "-u", os.getenv("SIGNAL_NUMBER", ""),
                     "receive"],
                    capture_output=True, text=True, timeout=30
                )
                if target in result.stdout:
                    on_reply()
                    return True
        except Exception as e:
            logger.error(f"Signal loop error: {e}")
            return False

    async def cleanup(self):
        pass
