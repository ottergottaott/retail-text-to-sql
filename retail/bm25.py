"""Okapi BM25 evaluation baseline; no stemming, stopwords or production changes."""
import math
import re
from collections import Counter, defaultdict


class BM25:
    def __init__(self, documents, k1=1.2, b=0.75):
        self.k1, self.b = k1, b
        self.lengths, self.postings = {}, defaultdict(dict)
        for id, text in documents.items():
            terms = Counter(self.tokens(text))
            self.lengths[id] = sum(terms.values())
            for term, count in terms.items():
                self.postings[term][id] = count
        self.size = len(documents)
        self.avg_length = sum(self.lengths.values()) / max(1, self.size)

    @staticmethod
    def tokens(text):
        return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)

    def search(self, query, k=5):
        scores = defaultdict(float)
        for term in set(self.tokens(query)):
            posting = self.postings.get(term, {})
            idf = math.log(1 + (self.size - len(posting) + 0.5) / (len(posting) + 0.5))
            for id, tf in posting.items():
                norm = self.k1 * (1 - self.b + self.b * self.lengths[id] / (self.avg_length or 1))
                scores[id] += idf * tf * (self.k1 + 1) / (tf + norm)
        return [{"id": id, "score": score} for id, score in
            sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:k]]
