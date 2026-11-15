"""第 5 步：建立向量索引（语义检索）。

和 BM25 的区别：
- BM25 看「词有没有出现」；向量看「意思像不像」。
- 用户问「主角什么时候第一次跟反派动手」，原文写的是「拔剑」「刺向咽喉」，
  一个词都对不上，BM25 就瞎了，向量还能命中。

输入：data/chunks.jsonl
输出：data/vectors.npz（vectors: float32[N,512]，chunk_ids: str[N]）

运行：python index_vector.py
需要：pip install sentence-transformers
国内下载模型慢，先设镜像：$env:HF_ENDPOINT="https://hf-mirror.com"
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
IN = DATA / "chunks.jsonl"
OUT = DATA / "vectors.npz"

# bge-zh 系列推荐给「查询」加一句指令，文档不用加；这是官方用法
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


def load_model():
    """加载 bge 模型（懒加载，只有真正用向量检索时才付出这几秒）。"""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise SystemExit(
            "没有安装 sentence-transformers。\n"
            "运行：pip install sentence-transformers\n"
            "装完仍报错就设镜像：$env:HF_ENDPOINT=\"https://hf-mirror.com\""
        )
    return SentenceTransformer(MODEL_NAME)


def encode_documents(model, texts: list[str]):
    """文档向量：normalize_embeddings=True 之后，余弦相似度 = 点积，省一步计算。"""
    return model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True)


def encode_query(model, query: str):
    return model.encode([QUERY_PREFIX + query], normalize_embeddings=True)[0]


def main() -> None:
    if not IN.exists():
        raise SystemExit(f"找不到 {IN}，请先运行 python chunk.py")

    import numpy as np

    chunks = [json.loads(line) for line in IN.open(encoding="utf-8")]
    model = load_model()
    vectors = encode_documents(model, [c["text"] for c in chunks]).astype("float32")

    np.savez_compressed(
        OUT,
        vectors=vectors,
        chunk_ids=np.array([c["chunk_id"] for c in chunks]),
    )
    print(f"块数：{len(chunks)}，向量维度：{vectors.shape[1]}")
    print(f"已写入 {OUT}（{OUT.stat().st_size / 1024:.0f} KB）")

    # 自检：拿一个和原文用词完全不同的问法试试
    for query in ("主角第一次跟仇人动手", "那个铁匠最后怎么了"):
        scores = vectors @ encode_query(model, query)
        order = scores.argsort()[::-1][:3]
        print(f"\n查询「{query}」")
        for idx in order:
            print(f"  {scores[idx]:.3f}  {chunks[idx]['chapter_title']}")


if __name__ == "__main__":
    main()
