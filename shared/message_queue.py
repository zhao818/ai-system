import json
import time
import threading
import uuid
from typing import Callable, Optional
from dataclasses import dataclass, field


@dataclass
class QueueMessage:
    topic: str
    body: dict
    message_id: str = ""
    timestamp: float = 0.0
    retry_count: int = 0

    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()

    def to_json(self) -> str:
        return json.dumps({
            "topic": self.topic,
            "body": self.body,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
        })

    @classmethod
    def from_json(cls, data: str):
        d = json.loads(data)
        return cls(**d)


class InMemoryQueue:
    def __init__(self):
        self._queues: dict[str, list] = {}
        self._consumers: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def publish(self, topic: str, body: dict) -> str:
        msg = QueueMessage(topic=topic, body=body)
        with self._lock:
            if topic not in self._queues:
                self._queues[topic] = []
            self._queues[topic].append(msg)

        self._dispatch(topic, msg)
        return msg.message_id

    def subscribe(self, topic: str, handler: Callable):
        with self._lock:
            if topic not in self._consumers:
                self._consumers[topic] = []
            self._consumers[topic].append(handler)

    def _dispatch(self, topic: str, msg: QueueMessage):
        with self._lock:
            handlers = list(self._consumers.get(topic, []))
        for handler in handlers:
            try:
                handler(msg)
            except Exception as e:
                print(f"  ! Handler error on {topic}: {e}")

    def start_consumer_loop(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            with self._lock:
                for topic, messages in list(self._queues.items()):
                    while messages:
                        msg = messages.pop(0)
                        self._dispatch(topic, msg)
            time.sleep(0.01)

    def stop(self):
        self._running = False


class RedisQueue:
    def __init__(self, redis_client, prefix="ai:queue:"):
        self.redis = redis_client
        self.prefix = prefix

    def publish(self, topic: str, body: dict) -> str:
        msg = QueueMessage(topic=topic, body=body)
        self.redis.rpush(f"{self.prefix}{topic}", msg.to_json())
        return msg.message_id

    def consume(self, topic: str, timeout: int = 1) -> Optional[QueueMessage]:
        data = self.redis.blpop(f"{self.prefix}{topic}", timeout=timeout)
        if data:
            return QueueMessage.from_json(data[1])
        return None
