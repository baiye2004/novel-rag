"""第 6 步：混合检索 —— BM25 + 向量，RRF 融合，最后定位到「第几章」。

这是整个项目的核心。输出长这样：
{
  "chapters": [{"chapter_no": 4, "chapter_title": "第四章 裴无咎的请帖", "score": ..., "share": 0.42}, ...],
  "chunks":   [{"chunk_id": ..., "chapter_no": 4, "text": ..., "score": ..., "sources": ["bm25","vector"]}, ...]
}

为什么要融合两路：
- 人名、地名、招式名 —— BM25 强
- 「主角第一次跟仇人动手」这种换了说法的问法 —— 向量强
RRF 只看排名不看分数，两路分数尺度不同也能直接相加，不用调权重。

rank() 是纯函数（给数据就能算），search() 负责从磁盘读索引再调它。
网页版（engine.py）上传 txt 后直接用 rank()，不用落盘。

运行：python retrieve.py
"""

from __future__ import annotations

import json
import pickle
from collections import defaultdict
from pathlib import Path

from textproc import clean_query, tokenize

DATA = Path(__file__).parent / "data"
RRF_K = 60  # RRF 平滑常数，业界默认 60

# 融合方式：score = 各自归一化后加权相加；rrf = 按名次融合
# 这本小书（15 个块）上实测：BM25 6/9、纯向量 7/9、score 7/9、rrf 4/9
FUSION = "score"
ALPHA = 0.5  # 关键词路的权重，剩下给向量路

_state: dict = {}


def _fuse(lexical: dict[int, float], cosine, n_chunks: int) -> dict[int, float]:
    """把两路结果合成一个分数表。

    score：两路各自归一化到 0–1 再加权，分数可比、可直接排序。
    rrf  ：只看名次，score = Σ 1/(60+rank)，不需要归一化，但候选集接近全库时会退化。
    """
    if cosine is None:
        top = max(lexical.values(), default=0.0) or 1.0
        return {idx: score / top for idx, score in lexical.items()}

    if FUSION == "rrf":
        fused: dict[int, float] = defaultdict(float)
        for position, (idx, _score) in enumerate(sorted(lexical.items(), key=lambda kv: kv[1], reverse=True), 1):
            fused[idx] += ALPHA / (RRF_K + position)
        for position, idx in enumerate(cosine.argsort()[::-1][:20], 1):
            fused[int(idx)] += (1 - ALPHA) / (RRF_K + position)
        return dict(fused)

    lex_top = max(lexical.values(), default=0.0) or 1.0
    cos_min, cos_max = float(cosine.min()), float(cosine.max())
    span = (cos_max - cos_min) or 1.0
    return {
        i: ALPHA * lexical.get(i, 0.0) / lex_top + (1 - ALPHA) * (float(cosine[i]) - cos_min) / span
        for i in range(n_chunks)
    }


def _load() -> dict:
    """把三个索引文件读进内存，只读一次。"""
    if _state:
        return _state

    chunk_file = DATA / "chunks.jsonl"
    bm25_file = DATA / "bm25.pkl"
    if not chunk_file.exists() or not bm25_file.exists():
        raise SystemExit("索引还没建好，先依次运行：python build_corpus.py && python chunk.py && python index_bm25.py")

    with bm25_file.open("rb") as f:
        payload = pickle.load(f)

    chunks = payload["chunks"]
    vectors = None
    vector_file = DATA / "vectors.npz"
    if vector_file.exists():
        try:
            import numpy as np

            data = np.load(vector_file)
            # 向量索引和 chunks 必须一一对应，否则检索结果会张冠李戴
            if list(data["chunk_ids"]) == [c["chunk_id"] for c in chunks]:
                vectors = data["vectors"]
            else:
                print("警告：vectors.npz 和 chunks.jsonl 不一致，已忽略向量索引，请重新运行 index_vector.py")
        except ImportError:
            print("提示：没装 numpy，跳过向量检索（只用 BM25 也能跑）")

    _state.update({
        "chunks": chunks,
        "bm25": payload["bm25"],
        "vectors": vectors,
        "model": None,
    })
    return _state


def _query_vector(query: str):
    """把问题编码成向量；模型只在第一次查询时加载。"""
    if _state["model"] is None:
        import index_vector

        _state["model"] = index_vector.load_model()
    import index_vector

    return index_vector.encode_query(_state["model"], query)


def rank(query: str, chunks: list[dict], bm25, vectors=None, query_vector=None,
         top_k: int = 6, expand: bool = True) -> dict:
    """给一份索引，算出「最可能是第几章」。纯函数，不碰磁盘。"""
    query = clean_query(query)
    index_of = {(c["chapter_no"], c["seq"]): i for i, c in enumerate(chunks)}
    chapter_titles = {c["chapter_no"]: c["chapter_title"] for c in chunks}

    # 第一路：关键词
    lexical = dict(bm25.top_k(tokenize(query), 20))

    # 第二路：语义（没有向量索引就自动降级成纯 BM25）
    cosine = None
    if vectors is not None and query_vector is not None:
        cosine = vectors @ query_vector

    fused = _fuse(lexical, cosine, len(chunks))
    if not fused:
        return {"chapters": [], "chunks": [], "used_vector": cosine is not None}

    sources: dict[int, set[str]] = defaultdict(set)
    for idx in lexical:
        sources[idx].add("bm25")
    if cosine is not None:
        for idx in cosine.argsort()[::-1][:20]:
            sources[int(idx)].add("vector")

    # 章节聚合：RRF 分数只用来排序，不能直接当「相关度」——它被压得很平。
    # 这里看的是「本章最好的块，在全局排第几」：第 1 名记 1 分，第 2 名记 1/2，依此类推。
    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    by_chapter: dict[int, list[float]] = defaultdict(list)
    for position, (idx, _score) in enumerate(ordered, start=1):
        by_chapter[chunks[idx]["chapter_no"]].append(1.0 / position)
    chapter_scores = {ch: max(s) + 0.5 * sorted(s, reverse=True)[1] if len(s) > 1 else max(s)
                      for ch, s in by_chapter.items()}
    ranked_chapters = sorted(chapter_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
    shown_total = sum(score for _, score in ranked_chapters)

    # 取前 top_k 个块，并把同章的前后块一起带上（情节常被切块边界切断）
    picked = ordered[:top_k]
    picked_idx = [idx for idx, _ in picked]
    if expand:
        extra: list[int] = []
        for idx in picked_idx:
            chapter_no, seq = chunks[idx]["chapter_no"], chunks[idx]["seq"]
            for neighbor_seq in (seq - 1, seq + 1):
                neighbor = index_of.get((chapter_no, neighbor_seq))
                if neighbor is not None and neighbor not in picked_idx and neighbor not in extra:
                    extra.append(neighbor)
        picked_idx.extend(extra)

    result_chunks = [{
        "chunk_id": chunks[i]["chunk_id"],
        "chapter_no": chunks[i]["chapter_no"],
        "chapter_title": chunks[i]["chapter_title"],
        "seq": chunks[i]["seq"],
        "text": chunks[i]["text"],
        "score": round(fused.get(i, 0.0), 5),
        "sources": sorted(sources.get(i, {"neighbor"})),
    } for i in picked_idx]
    result_chunks.sort(key=lambda c: (c["chapter_no"], c["seq"]))

    return {
        "chapters": [{
            "chapter_no": ch,
            "chapter_title": chapter_titles[ch],
            "score": round(score, 5),
            "share": round(score / shown_total, 3) if shown_total else 0.0,
        } for ch, score in ranked_chapters],
        "chunks": result_chunks,
        "used_vector": cosine is not None,
    }


def search(query: str, top_k: int = 6, use_vector: bool = True, expand: bool = True) -> dict:
    state = _load()
    # 先清洗再编码：两路必须用同一个版本的问题，否则 BM25 和向量看的不是同一句话
    query = clean_query(query)
    query_vector = None
    if use_vector and state["vectors"] is not None:
        query_vector = _query_vector(query)
    return rank(query, state["chunks"], state["bm25"], state["vectors"], query_vector, top_k, expand)


if __name__ == "__main__":
    for q in ("沈砚第一次拔剑是在第几章", "老周是怎么死的", "主角第一次跟仇人动手"):
        r = search(q)
        print(f"\n查询：{q}   （向量路：{'开' if r['used_vector'] else '关'}）")
        for c in r["chapters"]:
            print(f"  第{c['chapter_no']}章 {c['chapter_title']}  相关度 {c['share']:.0%}")
        print(f"  片段数：{len(r['chunks'])}")
