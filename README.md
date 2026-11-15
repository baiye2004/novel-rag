# 小说情节定位 RAG

输入一部长篇小说，用户问「某个情节在第几章」，系统检索原文、指出章节、给出置信度和原文依据。

原生 Python 实现（不用 LangChain），BM25 + 向量双路召回，按章聚合。

## 效果

自带 8 章示例语料、9 道题 + 2 道负样本（jieba + bge-small-zh + 双路召回）：

| 指标 | 结果 |
|---|---|
| 引用正确率（top1 章号正确） | **78%（7/9）** |
| top3 命中率 | 100%（9/9） |
| 检索命中率（标准答案原文被召回） | 100%（9/9） |
| 负样本（书里没有的情节） | 给出了候选但置信度低，没有硬编章节 |

单看 BM25 是 6/9，加向量后 7/9；纯向量单独用也是 7/9 —— 8 章 15 块太小，差距落在噪声里。
真正能看出差异的是两个语义问题：

- 「阿禾在哪里被救下」：BM25 找不到「救」字（原文是「在沙丘后面找到」），向量能对上。
- 「沈砚第一次拔剑」：BM25 被第 7 章的「他拔剑」吸走，向量认得出第 4 章的「第一次拔出了照夜」。

还剩两个错例是同一个原因：**问题里的词，原文一个都没有**（「老周是怎么死的」只匹配到第 2 章那句「你师父是怎么死的」；「阿禾送了什么」原文是「打成一块薄片」）。
这类要靠 query 改写，不是加向量能解决的。

## 架构

```
data/novel.txt
   │ ① build_corpus.py   按「第X章」切章
   ▼
data/chapters.jsonl（chapter_no / chapter_title / text）
   │ ② chunk.py          章内切 300 字，重叠 60，绝不跨章
   ▼
data/chunks.jsonl
   ├─ ③ index_bm25.py    jieba 分词 + BM25 → data/bm25.pkl
   └─ ④ index_vector.py  bge-small-zh 编码 → data/vectors.npz
                    │
                    ▼ ⑤ retrieve.py
        两路各取 20 → RRF 融合 → 补同章相邻块 → 按「最好块的名次」聚合成章节
                    │
                    ▼ ⑥ answer.py
        强制只依据原文、必须标出处；没 API Key 时降级为抽取式
                    │
                    ▼ ⑦ app.py / ⑧ evaluate.py
```

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

$env:DEEPSEEK_API_KEY="sk-..."          # 不设也能跑，走抽取式
$env:HF_ENDPOINT="https://hf-mirror.com" # 国内下模型

python build_corpus.py    # 切章（没放 novel.txt 就用自带示例）
python chunk.py           # 切块
python index_bm25.py      # 关键词索引
python index_vector.py    # 向量索引（可选，没装 sentence-transformers 会自动跳过）
python retrieve.py        # 命令行试检索
python answer.py "沈砚第一次拔剑是在第几章"
python evaluate.py        # 评估
python app.py             # http://127.0.0.1:7860
```

换成你自己的书，两种办法：

1. **网页上传**（最省事）：`python app.py` → 页面上选 txt → 自动切章、切块、建索引，直接问。
2. **命令行**：把 UTF-8 的 txt（章节标题单独成行）存成 `data/novel.txt`，从 `build_corpus.py` 重新跑一遍。

> 换了书一定要重建索引（`build_corpus` → `chunk` → `index_bm25` → `index_vector`），
> 否则检索的还是上一本书的内容。

## 目录

| 文件 | 作用 |
|---|---|
| `build_corpus.py` | 正则切章，中文数字转 int |
| `chunk.py` | 章内滑动窗口切块，带重叠 |
| `textproc.py` | 分词（jieba / 二字兜底）+ 40 行 BM25 |
| `index_bm25.py` | 建关键词索引 |
| `index_vector.py` | bge 编码，归一化后存 npz |
| `retrieve.py` | 双路召回、分数融合、邻块扩展、章节聚合 |
| `engine.py` | 把「一本书的纯文本」变成内存索引（网页上传用） |
| `answer.py` | 提示词约束 + DeepSeek 调用 + 抽取式降级 |
| `evaluate.py` | 引用正确率 / top3 / 检索命中 / 负样本 |
| `app.py` | Gradio 界面（支持上传任意 txt） |
| `START-HERE.md` | 手把手操作手册 |
| `TEACHING.md` | 从零到跑通的逐步教程 |

## 三个设计取舍

**1. 为什么按章切、不跨章切块**
章号是唯一可信的出处。块一旦跨章，回答里的「第几章」就可能是错的——这是这个项目最不能妥协的地方。

**2. 融合方式：为什么最后没用 RRF**
两种都实现了，实测差距很大：

| 方案 | 引用正确率 |
|---|---|
| 只用 BM25 | 6/9 |
| 只用向量 | 7/9 |
| **分数归一化 + 加权（当前）** | **7/9** |
| RRF（名次融合） | 4/9 |

原因是这本书只有 15 个块，两路的候选几乎覆盖全库，RRF 的「名次」信息被稀释，谁都能进榜。
RRF 适合「候选只占全库一小部分」的大库。代码里留了 `FUSION = "rrf"` 开关，换大书可以直接对比。

**3. 为什么章节得分不用融合分数**
融合分数是「块」的相关度，不是「章」的。一章里命中 5 个一般块，不该赢过命中 1 个极准块。
所以按「本章最好的块全局排第几」聚合：第 1 名记 1 分，第 2 名记 1/2。

## 为什么不用 Chroma / LangChain

- **Chroma**：几千个块，`npz + 点积` 就是毫秒级，装它多 300MB 依赖和一个构建坑。数据到十万块、需要元数据过滤时再换 FAISS/Chroma，这是有意识的取舍，不是不会用。
- **LangChain**：这个项目的检索逻辑只有 100 行，用框架反而看不清融合、邻块扩展、章节聚合这些真正要讲的东西。

## 局限与下一步

- 纯 BM25 时专有名词高频的章会「吸走」排名 → 向量路 + query 改写（让模型先把问题改写成检索词）
- 代词消解没做（「他」指谁）→ 检索时带上上一轮问题
- 只支持 txt → epub 需先转文本
- 没做 rerank → 加 `bge-reranker-base` 一般能再涨几个点，代价是慢

## 语料

自带 `data/demo_novel.txt`（8 章原创示例，可自由使用）。
正式演示建议用《三国演义》等公有领域作品，`data/novel.txt` 已被 `.gitignore` 忽略，不会误传有版权的文本。
