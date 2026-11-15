"""把「一本书的纯文本」变成一个可检索的引擎（网页版用它）。

和命令行版本的区别：
- retrieve.py 读的是磁盘上预先建好的索引（data/bm25.pkl 等）
- 这里直接在内存里切章、切块、建索引，所以能接任何上传的 txt

用法：
    engine = BookEngine(open("data/novel.txt", encoding="utf-8").read(), title="照夜")
    engine.search("沈砚第一次拔剑是在第几章")
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from build_corpus import split_chapters
from chunk import chunk_text
from retrieve import rank
from textproc import BM25, clean_query, tokenize

DATA = Path(__file__).parent / "data"

_model = None  # bge 模型全局只加载一次，换书不用重新加载


def get_model():
    global _model
    if _model is None:
        import index_vector

        _model = index_vector.load_model()
    return _model


def load_text(path: str | Path) -> str:
    """尽量把文件读成文本：UTF-8 优先，其次 GBK（老 txt 常见）。"""
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            text = raw.decode(encoding)
            if text.count("\ufffd") == 0:
                return text
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def text_fingerprint(text: str) -> str:
    """同一本书重复上传时用这个做缓存键，避免重新建索引。"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class BookEngine:
    def __init__(self, text: str, title: str = "未命名", max_chars: int = 300,
                 overlap: int = 60, use_vector: bool = True):
        self.title = title
        self.chapters = split_chapters(text)
        if not self.chapters:
            raise ValueError(
                "一章都没切出来。章节标题需要单独成行，形如「第一章 落雁关的雪」「第12章 xxx」。"
            )
        if len(self.chapters) < 3:
            print(f"提醒：只切出 {len(self.chapters)} 章。如果这本书本来就这么短，忽略即可。")

        self.chunks: list[dict] = []
        for chapter in self.chapters:
            for i, piece in enumerate(chunk_text(chapter["text"], max_chars, overlap)):
                self.chunks.append({
                    "chunk_id": f"c{chapter['chapter_no']:03d}_{i:02d}",
                    "chapter_no": chapter["chapter_no"],
                    "chapter_title": chapter["chapter_title"],
                    "seq": i,
                    "text": piece,
                })

        # 标题重复两遍再拼正文 = 给标题加权
        self.bm25 = BM25([tokenize(c["chapter_title"] * 2 + c["text"]) for c in self.chunks])

        self.vectors = None
        self.vector_error = ""
        if use_vector:
            self._build_vectors()

    def _build_vectors(self) -> None:
        """建向量索引；失败就降级成纯 BM25，不影响使用。"""
        try:
            import numpy as np

            import index_vector
        except ImportError as exc:
            self.vector_error = f"没装向量依赖：{exc}"
            return

        try:
            model = get_model()
            vectors = index_vector.encode_documents(model, [c["text"] for c in self.chunks])
            self.vectors = vectors.astype(np.float32)
        except Exception as exc:  # 下载失败、显存不足、模型缺失都可能
            self.vector_error = f"向量索引失败，已降级为纯 BM25：{exc}"

    def search(self, query: str, top_k: int = 6) -> dict:
        query = clean_query(query)
        query_vector = None
        if self.vectors is not None:
            import index_vector

            query_vector = index_vector.encode_query(get_model(), query)
        return rank(query, self.chunks, self.bm25, self.vectors, query_vector, top_k)

    def stats(self) -> str:
        vector_state = "开" if self.vectors is not None else "关（只用 BM25）"
        return f"《{self.title}》 · {len(self.chapters)} 章 · {len(self.chunks)} 块 · 向量：{vector_state}"


def default_book_path() -> Path | None:
    """默认加载哪本书：优先 data/novel.txt，其次自带示例。"""
    for name in ("novel.txt", "demo_novel.txt"):
        path = DATA / name
        if path.exists():
            return path
    return None


if __name__ == "__main__":
    path = default_book_path()
    if path is None:
        raise SystemExit("data/ 下没有 txt")
    engine = BookEngine(load_text(path), title=path.stem, use_vector=False)
    print(engine.stats())
    for q in ("沈砚第一次拔剑是在第几章", "老周是怎么死的"):
        result = engine.search(q)
        print(f"\n{q}")
        for c in result["chapters"]:
            print(f"  第{c['chapter_no']}章 {c['chapter_title']}  {c['share']:.0%}")
