import asyncio, logging, time, random

logger = logging.getLogger(__name__)


class WhatsAppProvider:
    def __init__(self):
        self.ready = False
        self.client = None

    async def init(self):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            opts = Options()
            opts.add_argument("--user-data-dir=whatsapp_session")
            opts.add_argument("--headless=new")
            self.driver = webdriver.Chrome(options=opts)
            self.driver.get("https://web.whatsapp.com")
            self.ready = True
            logger.info("WhatsApp provider ready")
        except ImportError:
            logger.warning("selenium not installed, WhatsApp unavailable")
            self.ready = False
        except Exception as e:
            logger.error(f"WhatsApp init error: {e}")
            self.ready = False

    async def wait_for_reply(self, target, on_reply, check_interval=15):
        if not self.ready:
            return False
        try:
            from selenium.webdriver.common.by import By
            wait = WebDriverWait(self.driver, 30)
            search_box = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
            ))
            search_box.click()
            search_box.clear()
            search_box.send_keys(target)
            time.sleep(2)

            chat = wait.until(EC.element_to_be_clickable(
                (By.XPATH, f'//span[@title="{target}"]')
            ))
            chat.click()
            time.sleep(1)

            last_msg_count = len(self.driver.find_elements(By.XPATH,
                '//div[contains(@class,"message-in")]'))

            while True:
                time.sleep(check_interval)
                msgs = self.driver.find_elements(By.XPATH,
                    '//div[contains(@class,"message-in")]')
                if len(msgs) > last_msg_count:
                    on_reply()
                    return True
        except Exception as e:
            logger.error(f"WhatsApp loop error: {e}")
            return False

    async def make_call(self, target):
        if not self.ready:
            return
        try:
            from selenium.webdriver.common.by import By
            call_btn = self.driver.find_element(By.XPATH,
                '//button[@aria-label="Voice call"]')
            call_btn.click()
            time.sleep(random.randint(5, 10))
            hangup = self.driver.find_element(By.XPATH,
                '//button[@aria-label="End call"]')
            hangup.click()
        except Exception as e:
            logger.error(f"WhatsApp call error: {e}")

    async def cleanup(self):
        if self.driver:
            self.driver.quit()
