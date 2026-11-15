"""第 3 步：中文分词 + BM25（关键词检索的地基）。

BM25 解决的是：用户问「沈砚第一次拔剑」，哪一段最可能包含这个情节。
它只看词有没有出现、出现几次、这个词在全书中稀不稀罕——
「沈砚」很稀罕，权重高；「的」到处都是，权重接近 0。

这里不依赖第三方库：装了 jieba 就用 jieba 分词，没装就用「二字切分」兜底。
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

try:  # jieba 可选
    import jieba

    HAS_JIEBA = True
except ImportError:  # pragma: no cover
    HAS_JIEBA = False

# 中文里高频但没有信息量的字
STOPWORDS = set("的了是在和与也就都而及或把被让给对从向这那他她它我你您们一个不没有很还又再才只就")

CJK_OR_WORD = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+")
PUNCT_ONLY = re.compile(r"^[^\w\u4e00-\u9fff]+$")

# 提问时的「包装词」：它们不携带情节信息，却会把检索带偏
QUERY_NOISE = re.compile(
    r"(请问|我想知道|我想问|告诉我|小说里|小说中|书中|原文里|原文中|这本书里|"
    r"在哪一章|在哪一回|哪一章|哪一回|第几章|第几回|第几节|是在|是第|"
    r"吗|呢|？|\?)"
)


def clean_query(query: str) -> str:
    """去掉「是在第几章」这类提问包装，只留下真正的检索意图。"""
    cleaned = QUERY_NOISE.sub("", query).strip(" ，。、")
    return cleaned or query


def tokenize(text: str) -> list[str]:
    """把一段话切成词。装了 jieba 走 jieba，否则用二字切分。"""
    if HAS_JIEBA:
        words = jieba.lcut(text)
        return [w.strip() for w in words
                if w.strip() and not PUNCT_ONLY.match(w) and w not in STOPWORDS]
    tokens: list[str] = []
    for run in CJK_OR_WORD.findall(text):
        if run[0].isascii():
            tokens.append(run.lower())
        elif len(run) == 1:
            tokens.append(run)
        else:
            # 单字 + 两字窗口：「落雁关」→ 落/雁/关 + 落雁/雁关。
            # 单字保证「死」「剑」这种词也能命中，两字窗口保证人名地名不被切碎。
            tokens.extend(run)
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


class BM25:
    """标准 BM25（Okapi），k1 控制词频饱和，b 控制长文档惩罚。"""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_len = [len(tokens) for tokens in corpus_tokens]
        self.avgdl = sum(self.doc_len) / max(len(self.doc_len), 1)
        self.tf: list[Counter] = [Counter(tokens) for tokens in corpus_tokens]

        df: Counter = Counter()
        for counter in self.tf:
            df.update(counter.keys())
        n = len(corpus_tokens)
        # 词越稀罕 idf 越大；+1 保证 idf 非负
        self.idf = {term: math.log((n - freq + 0.5) / (freq + 0.5) + 1.0)
                    for term, freq in df.items()}

    def scores(self, query_tokens: list[str]) -> list[float]:
        result = [0.0] * len(self.tf)
        for term in set(query_tokens):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, counter in enumerate(self.tf):
                freq = counter.get(term, 0)
                if not freq:
                    continue
                dl = self.doc_len[i]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                result[i] += idf * freq * (self.k1 + 1) / denom
        return result

    def top_k(self, query_tokens: list[str], k: int) -> list[tuple[int, float]]:
        scored = list(enumerate(self.scores(query_tokens)))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [pair for pair in scored[:k] if pair[1] > 0]
