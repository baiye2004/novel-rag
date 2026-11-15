"""第 9 步：评估 —— 这个项目真正的分水岭。

三个指标：
- 检索命中率：标准答案里那句原文，有没有被检索到
- 引用正确率（主指标）：排在第一位的是不是正确章节
- top3 命中率：正确章节有没有进前三

为什么要单列「引用正确率」：大模型本来就读过一些书，光看答案对错会虚高；
「第几章」这种精确信息它记不住，必须靠检索，所以这个指标最能反映系统好坏。

运行：python evaluate.py
输入：eval.csv（question / answer_key / chapter_no / type）
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from retrieve import search

DATA = Path(__file__).parent / "data"
EVAL = Path(__file__).parent / "eval.csv"
OUT = DATA / "eval_result.csv"


def norm(text: str) -> str:
    """只保留汉字和字母数字，避免标点/空格影响匹配。"""
    return re.sub(r"[^\w\u4e00-\u9fff]", "", text or "")


def main() -> None:
    if not EVAL.exists():
        raise SystemExit(f"找不到 {EVAL}")

    rows = list(csv.DictReader(EVAL.open(encoding="utf-8-sig")))
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "top1": 0, "top3": 0, "recall": 0})
    details = []

    for row in rows:
        question = row["question"].strip()
        result = search(question)
        chapters = [c["chapter_no"] for c in result["chapters"]]
        top1 = chapters[0] if chapters else None

        key_chapter = (row.get("chapter_no") or "").strip()
        key_text = norm(row.get("answer_key") or "")

        if not key_chapter:  # 负样本：书里根本没有这回事
            details.append({
                "question": question, "type": row["type"], "truth": "-",
                "pred": top1, "hit1": "", "hit3": "", "recall": "",
                "share": result["chapters"][0]["share"] if chapters else 0,
            })
            continue

        truth = int(key_chapter)
        hit1 = top1 == truth
        hit3 = truth in chapters
        recall = any(key_text in norm(c["text"]) for c in result["chunks"]) if key_text else False

        bucket = stats[row["type"]]
        bucket["n"] += 1
        bucket["top1"] += int(hit1)
        bucket["top3"] += int(hit3)
        bucket["recall"] += int(recall)

        details.append({
            "question": question, "type": row["type"], "truth": truth, "pred": top1,
            "hit1": "✓" if hit1 else "✗", "hit3": "✓" if hit3 else "✗",
            "recall": "✓" if recall else "✗",
            "share": result["chapters"][0]["share"] if chapters else 0,
        })

    print(f"{'类型':<6}{'题数':>4}{'引用正确':>8}{'top3':>7}{'检索命中':>9}")
    total = {"n": 0, "top1": 0, "top3": 0, "recall": 0}
    for type_name, s in stats.items():
        print(f"{type_name:<6}{s['n']:>4}{s['top1']:>8}{s['top3']:>7}{s['recall']:>9}")
        for k in total:
            total[k] += s[k]
    if total["n"]:
        print(f"{'总体':<6}{total['n']:>4}{total['top1']:>8}{total['top3']:>7}{total['recall']:>9}")
        print(f"\n引用正确率 {total['top1'] / total['n']:.0%}，top3 命中率 {total['top3'] / total['n']:.0%}，"
              f"检索命中率 {total['recall'] / total['n']:.0%}")

    print("\n逐题：")
    for d in details:
        print(f"  [{d['type']}] {d['question']}")
        print(f"      真实第{d['truth']}章，预测第{d['pred']}章，置信度 {d['share']:.0%} {d['hit1']}")

    DATA.mkdir(exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "type", "truth", "pred", "hit1", "hit3", "recall", "share"])
        writer.writeheader()
        writer.writerows(details)
    print(f"\n明细已写入 {OUT}")


if __name__ == "__main__":
    main()
