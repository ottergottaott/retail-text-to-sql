"""Owned response snapshots bind WebUI feedback to server-produced traces."""
import hashlib
import json
from .governance import Governance
from .security import PolicyError


class Learning:
    def __init__(self, config, store):
        self.config, self.store = config, store

    @staticmethod
    def key(principal, chat, message):
        if not all(isinstance(v,str) and 0 < len(v) <= 200 for v in (chat,message)):
            raise PolicyError('A valid response reference is required.')
        return 'wturn_' + hashlib.sha256(json.dumps([principal.user_id,chat,message]).encode()).hexdigest()

    def record(self, principal, chat, message, result):
        key=self.key(principal,chat,message)
        existing=next((r for r in self.store.list('webui_turn',principal.user_id) if r['id']==key),None)
        # A replacement response must never leave feedback bound to its predecessor,
        # even if the new trace could not be persisted after an unexpected failure.
        if existing:
            self.store.replace('webui_turn',principal.user_id,key,{'unavailable':True})
        conversation=self.store.get('conversation',principal.user_id,result['conversation_id'])['body']
        source=next((m for m in reversed(conversation['messages']) if m['trace']==result['trace_id']),None)
        if not source:
            raise PolicyError('Response reference is unavailable.')
        body={'conversation':result['conversation_id'],'trace_id':result['trace_id'],
            'products':source['products'],'question':source['question'][:2000],
            'answer':source['answer'][:3000]}
        if existing:
            self.store.replace('webui_turn',principal.user_id,key,body)
        else:
            self.store.put('webui_turn',principal.user_id,body,id=key)

    def target(self, principal, chat, message):
        record=self.store.get('webui_turn',principal.user_id,self.key(principal,chat,message))
        body=record['body']
        if body.get('unavailable'):
            raise PolicyError('Response reference is unavailable.')
        self.store.get('conversation',principal.user_id,body['conversation'])
        if not body.get('products') or not set(body['products']) <= set(principal.products):
            raise PolicyError('Response not found or no longer accessible.')
        return record

    def feedback(self, principal, chat, message, revision, rating, comment):
        record=self.target(principal,chat,message)
        if revision != record['version']:
            raise PolicyError('This response changed. Reload it before submitting feedback.')
        body=record['body']
        return Governance(self.config,self.store)._record_feedback(principal,
            body['conversation'],body['trace_id'],comment,rating)
