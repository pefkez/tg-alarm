import os, logging, json, threading, time

logger = logging.getLogger(__name__)


class MQTTBridge:
    def __init__(self):
        self.client = None
        self.ready = False
        self._on_message = None

    def connect(self):
        try:
            import paho.mqtt.client as mqtt
            broker = os.getenv("MQTT_BROKER", "localhost")
            port = int(os.getenv("MQTT_PORT", "1883"))
            user = os.getenv("MQTT_USER", "")
            password = os.getenv("MQTT_PASS", "")

            self.client = mqtt.Client(client_id="tg-alarm")
            if user and password:
                self.client.username_pw_set(user, password)

            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_mqtt_message
            self.client.connect_async(broker, port, 60)
            self.client.loop_start()
            self.ready = True
            logger.info(f"MQTT connecting to {broker}:{port}")
        except ImportError:
            logger.warning("paho-mqtt not installed")
        except Exception as e:
            logger.error(f"MQTT connect error: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected")
            self.client.subscribe("tg-alarm/command/#")
        else:
            logger.error(f"MQTT connect failed: {rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode()
        logger.info(f"MQTT: {topic} -> {payload}")
        if self._on_message:
            self._on_message(topic, payload)

    def on_message(self, callback):
        self._on_message = callback

    def publish_state(self, state: dict):
        if not self.ready:
            return
        try:
            self.client.publish("tg-alarm/state", json.dumps(state), qos=1, retain=True)
        except Exception as e:
            logger.error(f"MQTT publish error: {e}")

    def publish_alarm(self, message: str):
        if not self.ready:
            return
        try:
            self.client.publish("tg-alarm/alarm", message, qos=1)
        except Exception as e:
            logger.error(f"MQTT alarm publish error: {e}")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
