"""Replay cached live embeddings; compare legacy RRF with the runtime relevance gate.

This command makes no provider or BigQuery calls and uses an isolated database.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from retail.golden import load_demo_corpus
from retail.knowledge import Knowledge, cosine, document
from retail.retrieval_evaluation import _validate_cases, _evaluate, _eligible
from retail.security import principal_for
from retail.store import Store


class CachedEmbeddings:
    def __init__(self, payload):
        self.version = payload['version']
        self.vectors = payload['vectors']

    def embed(self, texts, task, timeout=10):
        return [self.vectors[task + '\n' + text] for text in texts]


def compare(cases, cache, corpus, floor=0.60):
    cases = [c for c in _validate_cases(cases) if c['language'] == 'en']
    if not cases:
        raise ValueError('No English evaluation cases.')
    embedder = CachedEmbeddings(cache)
    with tempfile.TemporaryDirectory(prefix='retail-relevance-gate-') as directory:
        store = Store('sqlite:///' + directory + '/state.db')
        try:
            lexical = Knowledge(store)
            load_demo_corpus(store, corpus)
            knowledge = Knowledge(store, embedder, 0.65, floor)
            knowledge.index()
            principal = principal_for('alice', SimpleNamespace(entitlements_json='{"alice":[1,2]}'))
            trios = _eligible(knowledge, principal)
            pairs = {(t['id'], t['version']) for t in trios}
            if any((r['id'], r['version']) not in pairs for c in cases for r in c['relevant']):
                raise ValueError('Relevance reference missing from eligible corpus.')

            def baseline(question, k):
                # Legacy full-index RRF, evaluated with exactly the same vectors.
                query = embedder.embed([question], 'RETRIEVAL_QUERY')[0]
                semantic = [{**t, 'similarity': cosine(query,
                    embedder.embed([document(t)], 'RETRIEVAL_DOCUMENT')[0])} for t in trios]
                semantic = sorted([t for t in semantic if t['similarity'] >= 0.65],
                    key=lambda t: (-t['similarity'], t['id']))
                fused = {}
                for ranking in (lexical.retrieve(question, principal, k=len(trios)), semantic):
                    for rank, trio in enumerate(ranking, 1):
                        item = fused.setdefault(trio['id'], {**trio, 'score': 0})
                        item['score'] += 1 / (60 + rank)
                return sorted(fused.values(), key=lambda t: (-t['score'], t['id']))[:k]

            cutoffs = (1,2,5)
            return {'evidence': 'offline replay of supplied cached embeddings',
                'cache_digest': hashlib.sha256(json.dumps(cache,sort_keys=True).encode()).hexdigest(),
                'case_digest': hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest(),
                'corpus_digest': hashlib.sha256(json.dumps(trios,sort_keys=True).encode()).hexdigest(),
                'embedding_version': embedder.version, 'document_count': len(trios),
                'language': 'en', 'semantic_threshold': 0.65, 'lexical_semantic_floor': floor,
                'retrieval_policy': 'semantic-lexical-gate-v1',
                'baseline': _evaluate('legacy_hybrid', cases, baseline, 'reciprocal_rank_fusion', cutoffs),
                'candidate': _evaluate('gated_hybrid', cases,
                    lambda q,k: knowledge.retrieve(q,principal,k=k), 'reciprocal_rank_fusion',cutoffs),
                'limitations': ['Synthetic unreviewed relevance labels.',
                    'Latency includes cache replay, not live provider latency.',
                    'False match rate counts any returned example through rank 5.',
                    'No SQL, report faithfulness or human acceptance evaluated.']}
        finally:
            store.engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, default=ROOT/'retail/data/golden-trios.json')
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    try:
        payload=json.loads(args.cases.read_text())
        report=compare(payload['cases'],json.loads(args.vectors.read_text()),args.corpus)
    except (OSError,ValueError,KeyError,TypeError):
        parser.error('Invalid input or missing cached vectors/relevance references.')
    report['dataset_version']=payload['dataset_version']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'positive_cases':report['candidate']['metrics']['positive_cases'],
        'negative_cases':report['candidate']['metrics']['negative_cases']}))


if __name__=='__main__':
    main()
