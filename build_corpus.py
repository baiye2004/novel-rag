"""第 1 步：把整本小说切成「章」。

输入：data/novel.txt（UTF-8，章节标题单独成行，形如「第一章 落雁关的雪」）
输出：data/chapters.jsonl
字段：chapter_no(int) / chapter_title(str) / text(str)

运行：python build_corpus.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).parent / "data"
# 优先用你自己的书；没有就用自带的 8 章示例，保证 clone 下来就能跑
SRC = DATA / "novel.txt"
DEMO = DATA / "demo_novel.txt"
OUT = DATA / "chapters.jsonl"

# 章节标题：第 + 中文或阿拉伯数字 + 回/章/节，后面可以跟标题
HEADING = re.compile(
    r"^\s*(第[零〇一二三四五六七八九十百千两0-9]{1,12}[回章节])\s*[、．.:：·]?\s*(.{0,40})$"
)
# 也接受「楔子」「序章」「尾声」这类没有编号的标题
SPECIAL = re.compile(r"^\s*(楔子|序章|序幕|尾声|后记)\s*$")

CN_NUM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
          "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn_to_int(text: str) -> int:
    """把「一百二十」「十二」「三」这类中文数字转成 int。"""
    if text.isdigit():
        return int(text)
    total, section, number = 0, 0, 0
    for ch in text:
        if ch in CN_NUM:
            number = CN_NUM[ch]
        elif ch in CN_UNIT:
            unit = CN_UNIT[ch]
            # 「十二」里的十，前面没有数字时按 1 算
            section += (number or 1) * unit
            number = 0
        else:
            raise ValueError(f"无法识别的数字：{text}")
    total += section + number
    return total


def split_chapters(raw: str) -> list[dict]:
    chapters: list[dict] = []
    current: dict | None = None
    buffer: list[str] = []

    for line in raw.splitlines():
        match = HEADING.match(line)
        special = SPECIAL.match(line)
        if match:
            if current is not None:
                current["text"] = "\n".join(buffer).strip()
                chapters.append(current)
            title = match.group(1) + (" " + match.group(2).strip() if match.group(2).strip() else "")
            current = {
                "chapter_no": cn_to_int(re.sub(r"[回章节]", "", match.group(1))[1:]),
                "chapter_title": title.strip(),
                "text": "",
            }
            buffer = []
        elif special:
            if current is not None:
                current["text"] = "\n".join(buffer).strip()
                chapters.append(current)
            current = {"chapter_no": len(chapters) + 1, "chapter_title": line.strip(), "text": ""}
            buffer = []
        elif current is not None:
            buffer.append(line)

    if current is not None:
        current["text"] = "\n".join(buffer).strip()
        chapters.append(current)

    return [c for c in chapters if c["text"]]


def main() -> None:
    if SRC.exists():
        source = SRC
    elif DEMO.exists():
        source = DEMO
        print(f"没有找到 data/novel.txt，先用自带示例语料 {DEMO.name} 跑通。")
        print("换成你自己的书：把 txt 存成 data/novel.txt，重新跑本脚本。\n")
    else:
        sys.exit(f"找不到语料：{SRC}\n请把小说存成 UTF-8 的 txt 放到 data/ 下，并命名为 novel.txt")

    raw = source.read_text(encoding="utf-8-sig")
    chapters = split_chapters(raw)

    if not chapters:
        sys.exit(
            "一章都没切出来，章节标题格式不对。\n"
            "请打开 txt 看看标题长什么样，例如「第1章 xxx」「第一章、xxx」，"
            "再改 build_corpus.py 顶部的 HEADING 正则。"
        )
    if len(chapters) < 3:
        print(f"提醒：只切出 {len(chapters)} 章。如果你这本书本来就这么短，忽略这条；"
              f"否则章节正则可能没匹配上。\n")

    DATA.mkdir(exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for c in chapters:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    total = sum(len(c["text"]) for c in chapters)
    print(f"语料：{source.name}")
    print(f"总章数：{len(chapters)}")
    print(f"平均每章：{total // len(chapters)} 字（全书 {total} 字）")
    first = chapters[0]
    print(f"第一章：{first['chapter_title']}")
    print(f"开头：{first['text'][:100]}……")
    print(f"已写入 {OUT}")


if __name__ == "__main__":
    main()
