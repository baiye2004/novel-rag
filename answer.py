"""第 7 步：让大模型「带着原文和章节号」回答。

关键不是模型多聪明，而是把检索到的片段按章节排好，逼它只依据原文回答。
没有配置 DEEPSEEK_API_KEY 时，自动降级成「抽取式」：直接给出最可能的章节 + 原文。

运行：python answer.py "沈砚第一次拔剑是在第几章"
"""

from __future__ import annotations

import os

from retrieve import search

SYSTEM_PROMPT = """你是一个小说检索助手。用户想知道某个情节出现在第几章。
下面会给出从原文中检索到的片段，每段前面标了章节。

回答规则：
1. 只能依据给出的片段回答，不要使用你自己的知识，不要补充片段里没有的内容；
2. 先回答情节本身，再单独用一行写「出处：第X章 章节名」；
3. 如果片段不足以回答，只回复这一句：检索到的原文里没有找到相关情节。
4. 回答控制在 120 字以内。"""


def build_context(result: dict, limit: int = 6, max_chars: int = 2000) -> str:
    parts, used = [], 0
    # 按相关度排序后再拼，别让补进来的低分邻块占掉 prompt 名额
    for chunk in sorted(result["chunks"], key=lambda c: c["score"], reverse=True)[:limit]:
        block = f"[第{chunk['chapter_no']}章 {chunk['chapter_title']}]\n{chunk['text']}"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def chapter_label(chapter_no: int | None, chapter_title: str) -> str:
    """拼出处时避免「第4章 第四章 xxx」「第16章《第16章》」这类重复。"""
    import re

    if chapter_title and re.search(r"第[零〇一二三四五六七八九十百千两0-9]+[章回节]", chapter_title):
        return chapter_title
    if not chapter_no:
        return chapter_title or ""
    return f"第{chapter_no}章 {chapter_title}".strip()


def _extractive(question: str, result: dict) -> dict:
    """没有 API Key 时的降级：检索到什么就说什么，反而不会编。"""
    top_chapter = result["chapters"][0]
    # 取这一章里得分最高的两块（章节标题计入打分，短块可能占便宜，多给一块更稳）
    candidates = [c for c in result["chunks"] if c["chapter_no"] == top_chapter["chapter_no"]]
    candidates.sort(key=lambda c: c["score"], reverse=True)
    excerpts = "\n\n……\n\n".join(c["text"][:200] + "……" for c in candidates[:2]) or result["chunks"][0]["text"][:200]
    answer = (
        f"（未配置 DEEPSEEK_API_KEY，当前为抽取式模式，只给证据不给结论）\n\n"
        f"最可能出现在{chapter_label(top_chapter['chapter_no'], top_chapter['chapter_title'])}。\n\n"
        f"原文：{excerpts}"
    )
    return {
        "answer": answer,
        "chapter_no": top_chapter["chapter_no"],
        "chapter_title": top_chapter["chapter_title"],
        "chapters": result["chapters"],
        "sources": result["chunks"],
        "mode": "extractive",
    }


def ask(question: str) -> dict:
    """命令行版：自己检索，再生成。"""
    return generate(question, search(question))


def generate(question: str, result: dict) -> dict:
    """网页版：检索结果由外部传入（可能是内存里的书，不落盘）。"""
    if not result["chapters"]:
        return {"answer": "检索到的原文里没有找到相关情节。", "chapter_no": None,
                "chapter_title": None, "chapters": [], "sources": [], "mode": "empty"}

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return _extractive(question, result)

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            temperature=0.2,  # 低温度，减少发挥
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"资料：\n{build_context(result)}\n\n问题：{question}"},
            ],
        )
        text = response.choices[0].message.content.strip()
    except Exception as exc:  # 网络、额度、鉴权都可能出错，别让界面崩掉
        return {"answer": f"调用大模型失败：{exc}\n（可先检查 DEEPSEEK_API_KEY 和网络）",
                "chapter_no": result["chapters"][0]["chapter_no"],
                "chapter_title": result["chapters"][0]["chapter_title"],
                "chapters": result["chapters"], "sources": result["chunks"], "mode": "error"}

    return {
        "answer": text,
        "chapter_no": result["chapters"][0]["chapter_no"],
        "chapter_title": result["chapters"][0]["chapter_title"],
        "chapters": result["chapters"],
        "sources": result["chunks"],
        "mode": "llm",
    }


def no_retrieval(question: str) -> str:
    """对照组：不检索直接问模型，用来证明「检索确实有用」。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "（没有 DEEPSEEK_API_KEY，无法运行对照组）"
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat", temperature=0.2,
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "沈砚第一次拔剑是在第几章"
    out = ask(q)
    print(f"问题：{q}\n")
    print(out["answer"])
    print("\n候选章节：")
    for c in out["chapters"]:
        print(f"  第{c['chapter_no']}章 {c['chapter_title']}  {c['share']:.0%}")
