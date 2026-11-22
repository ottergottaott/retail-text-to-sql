import contextlib
import json
import logging
import time
import uuid
from pathlib import Path


class Trace:
    """Metadata-only export; prompts/results require separately reviewed capture."""
    def __init__(self, config, user, conversation, sink=None):
        self.id = uuid.uuid4().hex
        self.config, self.user, self.conversation = config, user, conversation
        self.sink = sink or (lambda event: None)
        self.events = []
        self.client = None
        if config.langfuse_public_key and config.langfuse_secret_key:
            try:
                from langfuse import Langfuse
                self.client = Langfuse(public_key=config.langfuse_public_key, secret_key=config.langfuse_secret_key, base_url=config.langfuse_base_url)
            except Exception:
                logging.warning("Langfuse unavailable; using local metadata log")

    def event(self, stage, **facts):
        # Only callers' reviewed structured facts belong here, never raw exceptions.
        event = {"trace_id": self.id, "request_id": self.id, "turn_id": self.id,
            "conversation_id": self.conversation, "stage": stage, "time": time.time(),
            "mode": self.config.retail_mode, "config_version": "mvp-v1", **facts}
        self.events.append(event)
        try:
            with Path(self.config.log_path).open("a") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except OSError:
            logging.warning("Telemetry file unavailable")
        try:
            self.sink(event)
        except Exception:
            logging.warning("Progress transport unavailable")
        if self.client:
            try:
                with self.client.start_as_current_observation(name=stage, as_type="span", trace_context={"trace_id": self.id}) as span:
                    span.update(metadata=event)
            except Exception:
                logging.warning("Telemetry export unavailable")

    @contextlib.contextmanager
    def stage(self, name):
        start = time.monotonic()
        self.event(name, outcome="started")
        try:
            yield
        except Exception as e:
            self.event(name, outcome="failed", error_category=type(e).__name__, seconds=time.monotonic() - start)
            raise
        else:
            self.event(name, outcome="completed", seconds=time.monotonic() - start)

    def close(self):
        if self.client:
            try:
                self.client.flush()
            except Exception:
                pass
