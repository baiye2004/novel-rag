"""第 2 步：把每一章切成「块」（chunk）。

输入：data/chapters.jsonl
输出：data/chunks.jsonl
字段：chunk_id(str) / chapter_no(int) / chapter_title(str) / seq(int) / text(str)

为什么要在章内切块？
- 一章动辄几千字，整章塞给模型既贵又不准；
- 但要保证一个块不跨章，否则「出自第几章」就说不清了。

运行：python chunk.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DATA = Path(__file__).parent / "data"
IN = DATA / "chapters.jsonl"
OUT = DATA / "chunks.jsonl"

# 300 字适合这种短章演示；《三国演义》这种一章四五千字的，改成 450 / 100
DEFAULT_MAX = 300
DEFAULT_OVERLAP = 60

SENT_END = re.compile(r"(?<=[。！？!?…])")


def split_sentences(text: str) -> list[str]:
    """按句号/问号/叹号切句，保留标点。"""
    return [s.strip() for s in SENT_END.split(text) if s.strip()]


def hard_split(sentence: str, max_chars: int) -> list[str]:
    """一句话本身就超长（比如没有标点的段落）时，按字数硬切。"""
    if len(sentence) <= max_chars:
        return [sentence]
    return [sentence[i:i + max_chars] for i in range(0, len(sentence), max_chars)]


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """滑动窗口切块：块与块之间重叠 overlap 个字，尽量在句子边界断开。"""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in split_sentences(text):
        for piece in hard_split(sentence, max_chars):
            if current and current_len + len(piece) > max_chars:
                chunks.append("".join(current).strip())
                # 从上一块尾部取若干句作为重叠，保证情节不被切断
                tail: list[str] = []
                tail_len = 0
                for s in reversed(current):
                    if tail_len + len(s) > overlap:
                        break
                    tail.insert(0, s)
                    tail_len += len(s)
                current, current_len = tail, tail_len
            current.append(piece)
            current_len += len(piece)

    if current:
        chunks.append("".join(current).strip())
    return [c for c in chunks if c]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    args = parser.parse_args()

    if not IN.exists():
        raise SystemExit(f"找不到 {IN}，请先运行 python build_corpus.py")

    chapters = [json.loads(line) for line in IN.open(encoding="utf-8")]
    records: list[dict] = []
    for chapter in chapters:
        pieces = chunk_text(chapter["text"], args.max_chars, args.overlap)
        for i, piece in enumerate(pieces):
            records.append({
                "chunk_id": f"c{chapter['chapter_no']:03d}_{i:02d}",
                "chapter_no": chapter["chapter_no"],
                "chapter_title": chapter["chapter_title"],
                "seq": i,
                "text": piece,
            })

    with OUT.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    avg = sum(len(r["text"]) for r in records) // len(records)
    print(f"总块数：{len(records)}（{len(chapters)} 章）")
    print(f"平均块长：{avg} 字，最长 {max(len(r['text']) for r in records)} 字")
    sample = records[len(records) // 2]
    print(f"示例块 {sample['chunk_id']} → {sample['chapter_title']}")
    print(f"  {sample['text'][:80]}……")
    print(f"已写入 {OUT}")


if __name__ == "__main__":
    main()
