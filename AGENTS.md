# 给 AI 助手的项目规则

你是我的编程助手，帮我搭一个 **小说情节问答 RAG** 项目。请严格遵守下面的约束。

## 项目目标

输入一部长篇小说（txt，按章分节），用户可以问情节类问题，例如：
- 关羽第一次出场是哪一回？
- 草船借箭是谁提出的？
- 赤壁之战前后发生了什么？

系统要给出：答案 + 出自第几回 + 支撑答案的原文片段。

## 技术约束（不要擅自替换或增加）

- Python 3.10+，只使用 `requirements.txt` 里的依赖
- **不要使用 LangChain / LlamaIndex / 任何 RAG 框架**，全部原生实现
- 语料是 **txt**，不是 PDF；章节用正则切分（形如「第一回」「第十二章」）
- 向量模型：`sentence-transformers` 加载 `BAAI/bge-small-zh-v1.5`，编码必须 `normalize_embeddings=True`
- 向量库：`chromadb.PersistentClient(path="./chroma")`，metadata 必须带 `chapter_no` 和 `chapter_title`
- 关键词检索：`jieba` 分词 + `rank_bm25`，用于人物名、地名、招式名的精确匹配
- 最终检索结果用 **RRF 融合**向量与 BM25 两路结果
- 大模型：`openai` SDK 调 DeepSeek，`base_url="https://api.deepseek.com"`，`model="deepseek-chat"`
- API Key 只从环境变量 `DEEPSEEK_API_KEY` 读取，**绝不写死在代码里**

## 代码规范

- 每个 step 一个独立文件，可 `import` 复用；都要有 `if __name__ == "__main__"` 能单独跑
- 中间产物统一用 `jsonl` 存在 `data/` 下，字段名清单写在文件头注释里
- 函数加类型标注，关键逻辑写中文注释
- 异常要有明确中文提示（文件不存在、章节切分结果为 0、Key 未设置）
- 不要写我没要求的功能（不要用户系统、不要数据库 ORM、不要前端框架、不要 css 美化）

## 工作方式

1. **一次只改一个文件**，改完告诉我：怎么运行、预期输出、怎么验收
2. 不要一次生成多个文件
3. 需要我提供信息（书名、章节格式、人物表）时先问我
4. 我的要求和上面的约束冲突时，先指出来再改
