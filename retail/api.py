"""Shared HTTP interface for CLI and a trusted, thin Open WebUI adapter."""
from .security import scope_snapshot, scope_allowed
import asyncio
import hmac
import json
import logging
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Annotated
from fastapi import FastAPI, Depends, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, StrictBool, ConfigDict, model_validator
from typing import Literal
from .agent import Agent
from .config import settings
from .security import PolicyError, principal_for
from .store import Store
from .governance import Governance
from .report_presentation import render_report
from .learning import Learning


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    conversation_id: str | None = Field(default=None, max_length=80)
    external_chat_id: str | None = Field(default=None, max_length=200)
    external_message_id: str | None = Field(default=None, min_length=1, max_length=200)
    include_report_view: bool = False

    @model_validator(mode='after')
    def message_needs_chat(self):
        if self.external_message_id and not self.external_chat_id:
            raise ValueError('An external message requires its chat identifier.')
        return self


class DeleteInput(BaseModel):
    conversation_id: str = Field(max_length=80)
    phrase: str | None = Field(default=None, max_length=200)
    current_conversation: bool = False
    report_ids: list[str] | None = Field(default=None, max_length=100)


class Confirmation(BaseModel):
    conversation_id: str = Field(max_length=80)
    confirm: StrictBool


class Preference(BaseModel):
    format: str
    depth: str


class Feedback(BaseModel):
    conversation_id: str = Field(max_length=80)
    trace_id: str = Field(max_length=80)
    comment: str = Field(min_length=1, max_length=4000)
    rating: str


class WebUIFeedback(BaseModel):
    model_config=ConfigDict(extra='forbid')
    external_chat_id: str = Field(min_length=1,max_length=200)
    external_message_id: str = Field(min_length=1,max_length=200)
    revision: str = Field(min_length=1,max_length=80)
    rating: Literal['helpful','unhelpful','correction']
    comment: str = Field(default='',max_length=4000)


def create_app(config=None, model=None):
    config = config or settings()
    config.validate_live()
    store = Store(config.database_url)
    agent = Agent(config, store, model=model)
    # Bound simultaneous agent executions. Each invocation has isolated state.
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="retail")
    @asynccontextmanager
    async def lifespan(app):
        yield
        executor.shutdown(wait=False, cancel_futures=True)
        store.engine.dispose()
    app = FastAPI(title="Retail Assistant", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.agent = store, agent

    @app.middleware("http")
    async def sanitized_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logging.warning("HTTP operation failed: %s", type(e).__name__)
            return JSONResponse(status_code=500, content={"detail": "The request could not complete. Check saved state before retrying a mutation."})

    @app.exception_handler(PolicyError)
    async def policy_error(request: Request, error: PolicyError):
        return JSONResponse(status_code=403, content={"detail": str(error)})

    def identity(authorization: Annotated[str | None, Header()] = None,
                 x_webui_user: Annotated[str | None, Header()] = None):
        token = authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else ""
        # Constant-time comparisons; never accept a client-selected principal.
        if config.adapter_secret and token and hmac.compare_digest(token, config.adapter_secret):
            mapped = json.loads(config.webui_users_json).get(x_webui_user or "")
            if not mapped:
                raise PolicyError("WebUI identity is not mapped to application access.")
            return principal_for(mapped, config)
        user = next((user for key, user in json.loads(config.api_tokens_json).items()
                     if token and hmac.compare_digest(token, key)), None)
        if not user:
            raise PolicyError("Authentication required.")
        return principal_for(user, config)

    @app.get("/health")
    def health():
        # Readiness of external providers requires separate live checks.
        return {"status": "ok", "mode": config.retail_mode, "version": "0.1.0"}

    @app.post("/chat")
    async def chat(body: ChatInput, principal=Depends(identity)):
        conversation = resolve_conversation(body, principal)
        result = await asyncio.get_running_loop().run_in_executor(executor,
            partial(agent.chat, principal, body.message, conversation))
        return present_result(result, body, principal)

    def owned_report(report_id, principal):
        record = store.get("report", principal.user_id, report_id)
        if not scope_allowed(record["body"], principal):
            raise PolicyError("Report not found or not accessible.")
        return record

    def present_result(result, body, principal):
        if body.external_message_id:
            try:
                Learning(config,store).record(principal,body.external_chat_id,body.external_message_id,result)
            except Exception as error:
                # Optional feedback UI cannot invalidate an already committed report.
                logging.warning('Feedback reference unavailable: %s',type(error).__name__)
        if not body.include_report_view or result.get("outcome") != "succeeded":
            return result
        try:
            management = result.get("management")
            report_id = management.get("report_id") if isinstance(management, dict) else None
            if report_id:
                record = owned_report(report_id, principal)
                view = render_report(record["body"], report_id, record["created"])
            elif result.get("completed_analysis") and result.get("evidence"):
                view = render_report({"title": "Retail analysis", "content": result["answer"],
                    "provenance": result["evidence"], **scope_snapshot(principal)})
            else:
                return result
            return {**result, "report_view": view}
        except Exception as error:
            # An optional display failure must never hide a committed save or retry it.
            logging.warning("Report presentation unavailable: %s", type(error).__name__)
            return result

    def resolve_conversation(body, principal):
        if body.external_chat_id:
            if body.conversation_id:
                raise PolicyError("Use either a backend conversation or a WebUI chat identifier.")
            return store.webui_conversation(principal, body.external_chat_id)
        return store.conversation(principal, body.conversation_id)

    @app.post("/chat/stream")
    async def stream(body: ChatInput, principal=Depends(identity)):
        # Authenticate and check conversation ownership before committing SSE headers.
        conversation = resolve_conversation(body, principal)
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue(maxsize=256)

        def deliver(event):
            # A full progress queue must not fail an already committed operation.
            def enqueue():
                if not queue.full():
                    queue.put_nowait(event)
            loop.call_soon_threadsafe(enqueue)

        async def events():
            task = loop.run_in_executor(executor,
                partial(agent.chat, principal, body.message, conversation, deliver))
            try:
                while not task.done() or not queue.empty():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=0.25)
                        yield "event: progress\ndata: " + json.dumps(event) + "\n\n"
                    except asyncio.TimeoutError:
                        pass
                try:
                    result = present_result(await task, body, principal)
                    yield "event: result\ndata: " + json.dumps(result) + "\n\n"
                except PolicyError as e:
                    yield "event: error\ndata: " + json.dumps({"detail": str(e)}) + "\n\n"
                except Exception:
                    yield 'event: error\ndata: {"detail":"Request failed; check saved state before retrying."}\n\n'
            finally:
                # Disconnect does not undo committed mutations. Agent budgets still apply.
                if not task.done():
                    task.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)

        return StreamingResponse(events(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/reports")
    def reports(principal=Depends(identity)):
        return [{"id": r["id"], "title": r["body"]["title"], "created": r["created"]}
                for r in store.reports(principal)]

    @app.get("/reports/{report_id}")
    def report(report_id: str, principal=Depends(identity)):
        return owned_report(report_id, principal)

    @app.get("/reports/{report_id}/html")
    def report_html(report_id: str, principal=Depends(identity)):
        record = owned_report(report_id, principal)
        view = render_report(record["body"], report_id, record["created"])
        return HTMLResponse(view["html"], headers={"Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff"})

    @app.post("/reports/deletion-proposals")
    def deletion(body: DeleteInput, principal=Depends(identity)):
        return store.propose_delete(principal, body.conversation_id, phrase=body.phrase,
            current=body.current_conversation, ids=body.report_ids)

    @app.post("/reports/deletion-proposals/{proposal_id}/confirmation")
    def confirm(proposal_id: str, body: Confirmation, principal=Depends(identity)):
        return store.confirm_delete(principal, body.conversation_id, proposal_id, body.confirm)

    @app.get("/preferences")
    def preferences(principal=Depends(identity)):
        return store.profile(principal.user_id)

    @app.put("/preferences")
    def preference(body: Preference, principal=Depends(identity)):
        return store.preference(principal.user_id, body.format, body.depth)

    @app.post("/feedback")
    def feedback(body: Feedback, principal=Depends(identity)):
        id = Governance(config, store).feedback(principal, body.conversation_id,
            body.trace_id, body.comment, body.rating)
        return {"feedback_id": id, "status": "unreviewed"}

    @app.get('/webui/feedback-target')
    def feedback_target(external_chat_id: str, external_message_id: str, principal=Depends(identity)):
        record=Learning(config,store).target(principal,external_chat_id,external_message_id)
        return {'question':record['body']['question'],'answer':record['body']['answer'],
            'revision':record['version']}

    @app.post('/webui/feedback')
    def webui_feedback(body: WebUIFeedback, principal=Depends(identity)):
        id=Learning(config,store).feedback(principal,body.external_chat_id,body.external_message_id,
            body.revision,body.rating,body.comment)
        return {'feedback_id':id,'status':'unreviewed'}

    return app
