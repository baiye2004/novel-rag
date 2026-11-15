"""第 4 步：建立关键词索引（BM25），存成 data/bm25.pkl。

运行：python index_bm25.py
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from textproc import BM25, HAS_JIEBA, tokenize

DATA = Path(__file__).parent / "data"
IN = DATA / "chunks.jsonl"
OUT = DATA / "bm25.pkl"


def main() -> None:
    if not IN.exists():
        raise SystemExit(f"找不到 {IN}，请先运行 python chunk.py")

    chunks = [json.loads(line) for line in IN.open(encoding="utf-8")]
    # 字段加权：标题重复 2 次再拼正文。等于告诉 BM25「标题里的词更重要」，
    # 「白骨滩之战的结果」这类问题和章名高度重合，权重给对了，章就排得准。
    tokens = [tokenize(c["chapter_title"] * 2 + c["text"]) for c in chunks]
    bm25 = BM25(tokens)

    payload = {
        "chunks": chunks,          # 和 tokens / bm25 的行号一一对应
        "tokens": tokens,
        "bm25": bm25,
        "tokenizer": "jieba" if HAS_JIEBA else "bigram",
    }
    with OUT.open("wb") as f:
        pickle.dump(payload, f)

    print(f"分词方式：{'jieba' if HAS_JIEBA else '二字切分（未安装 jieba，效果略差但能跑）'}")
    print(f"文档数：{len(chunks)}，词表大小：{len(bm25.idf)}，平均长度：{bm25.avgdl:.1f} 词")
    print(f"已写入 {OUT}\n")

    for query in ("沈砚第一次拔剑", "老周是怎么死的"):
        hits = bm25.top_k(tokenize(query), 3)
        print(f"查询「{query}」")
        for idx, score in hits:
            print(f"  {score:6.2f}  {chunks[idx]['chapter_title']}  {chunks[idx]['text'][:30]}……")


if __name__ == "__main__":
    main()
