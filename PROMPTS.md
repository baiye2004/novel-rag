# 给 AI 助手的任务清单（按顺序粘，一次一条）

> 现状：这 8 个任务对应的代码**已经实现**在本目录里（`build_corpus.py` → `app.py`），
> 本文保留作「自己动手重写一遍」的练习清单。两处实现取舍见 README：
> 没用 Chroma（numpy 点积够用）、BM25 自己写了 40 行（没用 rank_bm25）。
>
> 用法：VS Code 里打开 `rag-doc-qa`，切到 Codex（或 Cline）的 **Agent 模式**，
> 每次只粘一条，跑通、看懂、`git commit`，再发下一条。

---

## 任务 1 · 按章切分小说

```
读 AGENTS.md 的约束，写 build_corpus.py：
- 读取 data/novel.txt（utf-8），用正则匹配章节标题，形如「第一回」「第十二回」「第一百二十回」，也兼容「第一章」
- 切出 chapters.jsonl，每行字段：chapter_no(int)、chapter_title(str)、text(str)
- __main__ 里打印：总章数、每章平均字数、第一章的标题和前 100 字
- 如果切出来的章数 < 10，抛出明确错误，提示"章节正则可能不匹配"
```

**验收**：打印「总章数 120」，第一章标题正确，`chapters.jsonl` 有 120 行。

---

## 任务 2 · 章内切块

```
新建 chunk.py，不要改 build_corpus.py：
- 读 chapters.jsonl，把每章按段落聚合成 400–500 字的块，块间重叠 100 字
- 输出 chunks.jsonl，字段：chunk_id(str)、chapter_no(int)、chapter_title(str)、text(str)
- 不要把一个块跨到两章去
- __main__ 里打印：总块数、平均块长、随手挑一个块打印它属于哪一回
```

**验收**：总块数是合理量级（几万字的书大约几百块），每块都带 chapter_no。

---

## 任务 3 · 向量索引

```
新建 index_vector.py：
- 读 chunks.jsonl，用 bge-small-zh-v1.5 编码（normalize_embeddings=True）
- 存进 chroma 的 collection "novel"，metadata 带上 chapter_no、chapter_title
- 入库前清空旧数据
- __main__ 打印：块数、向量维度、耗时
```

**验收**：打印入库块数；`chroma/` 目录生成；重复运行不报 ID 冲突。

---

## 任务 4 · 关键词索引（BM25）

```
新建 index_bm25.py：
- 读 chunks.jsonl，用 jieba 分词（关闭新词发现以外的多余参数即可）
- 用 rank_bm25 建 BM25Okapi，把 tokenized 文本和 chunk 元数据一起 pickle 到 data/bm25.pkl
- 额外维护一个"人物/关键词 → chunk_id"的倒排表，用于按人名快速过滤（先用简单字符串匹配即可）
- __main__ 里用"关羽"检索，打印 top-3 的 chapter_title
```

**验收**：搜「关羽」能返回包含关羽的片段，且回目正确。

---

## 任务 5 · 混合检索

```
新建 retrieve.py：
- 提供 search(query: str, top_k: int = 8) -> list[dict]
- 并行跑两路：向量检索 top-20、BM25 检索 top-20
- 用 RRF 融合（score = Σ 1/(60 + rank)），取融合后 top_k
- 每条结果附带相邻块（同一章的前一块和后一块），保证情节连贯
- 返回字段：chunk_id、chapter_no、chapter_title、text、score
- __main__ 里查"草船借箭"，打印命中的回目列表
```

**验收**：查询命中的回目和直觉一致；相邻块确实来自同一章。

---

## 任务 6 · 生成回答

```
新建 answer.py：
- 提供 ask(question: str) -> dict，返回 {answer, chapter_no, chapter_title, sources}
- 用 retrieve.search 取片段，按回目排序后拼进 prompt
- prompt 里明确要求：只依据资料回答；资料不足就说"书中未找到相关情节，无法回答"；
  回答后必须注明出自第几回；不要补充资料以外的内容
- temperature=0.2
- 另外做一个 no_retrieval(question) 函数：不检索，直接问模型，用于对照组
```

**验收**：问「关羽第一次出场是哪一回」，回答里带正确回目；问一个书里没有的事，模型明确拒答。

---

## 任务 7 · 评估

```
新建 eval.py 和 eval.csv（先放 8 行示例，我补到 40 行）：
- eval.csv 字段：question、answer_key（原文关键句）、chapter_key（正确回目编号）、type（人物/事件/因果/关系）
- 对每题记录三项：检索命中（answer_key 是否出现在检索片段里）、
  引用正确（返回的 chapter_no 是否等于 chapter_key）、答案正确（人工判断，先留空列）
- 同时跑 no_retrieval 对照组，记录"答案正确"（用于证明检索的价值）
- 输出：分类命中率、总体命中率、引用正确率
```

**验收**：能打印一张四类问题的命中率表。

---

## 任务 8 · 界面

```
新建 app.py，用 gradio：
- 输入框：问题
- 输出：回答、出处（第 X 回 + 回目）、命中片段（用 --- 分隔，每段前标回目）
- 标题「《书名》情节问答助手」，副标题说明"回答仅依据原文，并标注回目"
- 不要做 css 美化
```

**验收**：`python app.py` 打开页面，能提问并看到回答 + 回目 + 原文。

---

## 收尾

```bash
git add .
git commit -m "feat: 小说情节问答 RAG（章节切分/混合检索/生成/评估）"
git push
```
