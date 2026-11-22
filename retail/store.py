"""Transactional application state; no report lifetime dependency on a chat."""
from .security import scope_snapshot, scope_allowed
import json
import secrets
import time
import hashlib
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine, MetaData, Table, Column, String, Text, Float, select, insert, update, delete, and_
from .security import PolicyError, clean, safe_output

metadata = MetaData()
records = Table("records", metadata,
    Column("id", String(80), primary_key=True), Column("kind", String(40), nullable=False),
    Column("owner", String(120), nullable=False), Column("body", Text, nullable=False),
    Column("created", Float, nullable=False), Column("version", String(40), nullable=False))


class Store:
    def __init__(self, url):
        self.engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
        metadata.create_all(self.engine)

    def put(self, kind, owner, body, id=None, conn=None):
        id = id or f"{kind[:3]}_{secrets.token_hex(8)}"
        row = dict(id=id, kind=kind, owner=owner, body=json.dumps(body, default=str), created=time.time(), version=secrets.token_hex(6))
        if conn is not None:
            conn.execute(insert(records).values(**row))
        else:
            with self.engine.begin() as c:
                c.execute(insert(records).values(**row))
        return id

    def get(self, kind, owner, id, conn=None):
        stmt = select(records).where(and_(records.c.id == id, records.c.kind == kind, records.c.owner == owner))
        if conn is None:
            with self.engine.connect() as c:
                row = c.execute(stmt).mappings().first()
        else:
            row = conn.execute(stmt.with_for_update()).mappings().first()
        if row is None:
            raise PolicyError("Record not found or not accessible.")
        return {**dict(row), "body": json.loads(row["body"])}

    def list(self, kind, owner):
        with self.engine.connect() as c:
            rows = c.execute(select(records).where(and_(records.c.kind == kind, records.c.owner == owner)).order_by(records.c.created)).mappings().all()
        return [{**dict(r), "body": json.loads(r["body"])} for r in rows]

    def replace(self, kind, owner, id, body):
        with self.engine.begin() as c:
            self.get(kind, owner, id, c)
            c.execute(update(records).where(and_(records.c.id == id, records.c.owner == owner)).values(body=json.dumps(body, default=str), version=secrets.token_hex(6)))

    def conversation(self, principal, id=None):
        if id:
            self.get("conversation", principal.user_id, id)
            return id
        return self.put("conversation", principal.user_id, {"messages": []})

    def webui_conversation(self, principal, external_id):
        if not external_id or len(external_id) > 200:
            raise PolicyError("A valid WebUI chat identifier is required.")
        # Persist association without storing raw external identifiers in telemetry.
        digest = hashlib.sha256(f"{principal.user_id}:{external_id}".encode()).hexdigest()
        id = "con_web_" + digest
        try:
            self.get("conversation", principal.user_id, id)
        except PolicyError:
            try:
                self.put("conversation", principal.user_id, {"messages": []}, id=id)
            except IntegrityError:
                self.get("conversation", principal.user_id, id)
        return id

    def append(self, principal, conversation, question, answer, trace):
        body = self.get("conversation", principal.user_id, conversation)["body"]
        body["messages"] = (body["messages"] + [{"question": clean(question), "answer": safe_output(answer),
            "trace": trace, **scope_snapshot(principal)}])[-20:]
        self.replace("conversation", principal.user_id, conversation, body)

    def profile(self, user):
        try:
            return self.get("profile", user, f"profile_{user}")["body"]
        except PolicyError:
            return {"format": "tables", "depth": "standard", "version": 0}

    def preference(self, user, format, depth):
        if format not in {"tables", "bullets", "prose"} or depth not in {"concise", "standard", "detailed"}:
            raise PolicyError("Unsupported presentation preference.")
        p = {"format": format, "depth": depth, "source": "explicit", "version": self.profile(user)["version"] + 1}
        if self.list("profile", user):
            self.replace("profile", user, f"profile_{user}", p)
        else:
            self.put("profile", user, p, f"profile_{user}")
        return p

    def reports(self, principal):
        return [r for r in self.list("report", principal.user_id) if scope_allowed(r["body"], principal)]

    def save_report(self, principal, conversation, title, content, provenance):
        self.get("conversation", principal.user_id, conversation)
        return self.put("report", principal.user_id, {"title": safe_output(title), "content": safe_output(content), "conversation": conversation, **scope_snapshot(principal), "provenance": provenance})

    def propose_delete(self, principal, conversation, phrase=None, current=False, ids=None):
        self.get("conversation", principal.user_id, conversation)
        if not phrase and not current and not ids:
            raise PolicyError("Provide a phrase, report IDs, or current conversation scope.")
        selected = [r for r in self.reports(principal)
                    if (not phrase or phrase.casefold() in (r["body"]["title"] + " " + r["body"]["content"]).casefold())
                    and (not current or r["body"]["conversation"] == conversation)
                    and (not ids or r["id"] in ids)]
        if not selected:
            return {"proposal_id": None, "reports": [], "message": "No matching owned reports."}
        proposal = {"conversation": conversation, "targets": {r["id"]: r["version"] for r in selected}, "expires": time.time() + 600, "status": "pending"}
        id = self.put("proposal", principal.user_id, proposal)
        return {"proposal_id": id, "reports": [{"id": r["id"], "title": r["body"]["title"]} for r in selected], "expires": proposal["expires"]}

    def confirm_delete(self, principal, conversation, id, confirm):
        with self.engine.begin() as c:
            row = self.get("proposal", principal.user_id, id, c)
            p = row["body"]
            if p["conversation"] != conversation:
                raise PolicyError("Confirmation belongs to a different conversation.")
            if p["status"] != "pending":
                return {"status": p["status"], "deleted": 0}
            if p["expires"] < time.time():
                raise PolicyError("Confirmation expired; request a new preview.")
            # Compare-and-set also serializes concurrent consumers under SQLite.
            claim = c.execute(update(records).where(and_(records.c.id == id, records.c.version == row["version"])).values(version=secrets.token_hex(6)))
            if claim.rowcount != 1:
                raise PolicyError("Confirmation already handled; refresh the operation.")
            if confirm:
                for rid, version in p["targets"].items():
                    report = self.get("report", principal.user_id, rid, c)
                    if report["version"] != version or not scope_allowed(report["body"], principal):
                        raise PolicyError("Targets or access changed; request a new preview.")
                for rid in p["targets"]:
                    c.execute(delete(records).where(and_(records.c.id == rid, records.c.owner == principal.user_id)))
            p["status"] = "deleted" if confirm else "cancelled"
            c.execute(update(records).where(records.c.id == id).values(body=json.dumps(p)))
            self.put("audit", principal.user_id, {"operation": id, "targets": list(p["targets"]), "outcome": p["status"]}, conn=c)
            return {"status": p["status"], "deleted": len(p["targets"]) if confirm else 0}
