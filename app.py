"""第 10 步：网页界面（Gradio），支持上传任意 txt。

和命令行版的区别：上传的书在内存里建索引，不用先跑 build_corpus/chunk/index_*。

运行：python app.py
浏览器打开 http://127.0.0.1:7860
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from answer import chapter_label, generate
from engine import BookEngine, default_book_path, load_text, text_fingerprint

EXAMPLES = [
    "沈砚第一次拔剑是在第几章",
    "老周是怎么死的",
    "照夜剑是谁交给沈砚的",
    "主角第一次跟仇人动手",
]

# 建好的索引放内存里，同一本书再次上传不用重建；最多留 3 本
_cache: dict[str, BookEngine] = {}
MAX_BOOKS = 3

# 记住最后一次上传的是哪本，刷新页面时不用重传
_last_key: str | None = None


def _remember(key: str, engine: BookEngine) -> BookEngine:
    _cache[key] = engine
    while len(_cache) > MAX_BOOKS:
        _cache.pop(next(iter(_cache)))
    return engine


def _status(engine: BookEngine) -> str:
    text = f"**当前：{engine.stats()}**"
    if engine.vector_error:
        text += f"\n\n> {engine.vector_error}"
    return text


def load_default() -> tuple[str, str | None]:
    """页面打开时：优先用上一次上传的书，其次 data/novel.txt，最后自带示例。"""
    global _last_key
    if _last_key and _last_key in _cache:
        return _status(_cache[_last_key]), _last_key

    path = default_book_path()
    if path is None:
        return "data/ 下没有 txt，先上传一本吧。", None
    text = load_text(path)
    key = text_fingerprint(text)
    if key not in _cache:
        try:
            _remember(key, BookEngine(text, title=path.stem))
        except Exception as exc:
            return f"示例加载失败：{exc}", None
    _last_key = key
    return _status(_cache[key]), key


def on_upload(file_path: str | None) -> tuple[str, str | None]:
    global _last_key
    if not file_path:
        return "没有选择文件。", None
    text = load_text(file_path)
    key = text_fingerprint(text)
    if key not in _cache:
        try:
            _remember(key, BookEngine(text, title=Path(file_path).stem))
        except Exception as exc:
            return f"这本读不了：{exc}", None
    _last_key = key
    return _status(_cache[key]), key


def render(out: dict) -> str:
    lines = [f"### {out['answer']}", ""]
    if out["chapters"]:
        lines.append("**候选章节**")
        for c in out["chapters"]:
            lines.append(f"- {chapter_label(c['chapter_no'], c['chapter_title'])} · 相关度 {c['share']:.0%}")
        lines.append("")
        lines.append("**原文摘录**")
        for chunk in sorted(out["sources"], key=lambda c: c["score"], reverse=True)[:4]:
            lines.append(f"> **{chapter_label(chunk['chapter_no'], chunk['chapter_title'])}** {chunk['text']}")
            lines.append("")
    return "\n".join(lines)


def on_ask(question: str, key: str | None) -> tuple[str, str | None]:
    if not question or not question.strip():
        return "先输入一个问题。", key
    if not key or key not in _cache:
        status, key = load_default()
        if not key:
            return status, key
    engine = _cache[key]
    return render(generate(question, engine.search(question))), key


with gr.Blocks(title="小说情节定位助手") as demo:
    gr.Markdown(
        "# 小说情节定位助手\n"
        "上传任意 txt（UTF-8，章节标题单独成行），问情节，定位到第几章并给出原文。\n\n"
        "> 第一次上传会现场切章、切块、建索引：短篇几秒，几十万字的长篇可能要 30–60 秒。"
    )
    book_key = gr.State(None)

    with gr.Row():
        with gr.Column(scale=1):
            file_in = gr.File(label="上传小说 txt", file_types=[".txt"], type="filepath")
            status = gr.Markdown("正在载入…")
        with gr.Column(scale=2):
            question = gr.Textbox(
                label="你想找哪个情节？",
                placeholder="例：沈砚第一次拔剑是在第几章",
                lines=2,
            )
            ask_btn = gr.Button("查找", variant="primary")
            answer_md = gr.Markdown()

    gr.Examples(examples=[[q] for q in EXAMPLES], inputs=question)

    demo.load(load_default, outputs=[status, book_key])
    file_in.upload(on_upload, inputs=file_in, outputs=[status, book_key])
    ask_btn.click(on_ask, inputs=[question, book_key], outputs=[answer_md, book_key])
    question.submit(on_ask, inputs=[question, book_key], outputs=[answer_md, book_key])


if __name__ == "__main__":
    demo.launch()
