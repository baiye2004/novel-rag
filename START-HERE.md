# 操作手册：从打开 VS Code 到跑出第一张评估表

> 每一步都写清楚：**用哪个工具 → 点什么/敲什么 → 应该看到什么 → 看不到怎么办**。
> 命令都在 VS Code 的集成终端里执行，路径固定为 `D:\deepseek\rag-doc-qa`。

---

## 0. 你机器上已经有的（我查过了，别重复装）

| 工具 | 版本 / 位置 | 结论 |
|---|---|---|
| VS Code | 1.144.1 | 已装，直接用 |
| Python 扩展 + Pylance + debugpy | 2026 版 | 已装，能选解释器、能断点调试 |
| 中文语言包 | 已装 | 界面是中文，下面按中文菜单写 |
| Python | 3.13.9，`E:\1python\python.exe` | 已装，`python` 命令可用 |
| pip | 25.2 | 已装 |
| Git | 2.55 | 已装 |

**所以你只需要做两件事：建虚拟环境 + 装 5 个包。** 其余全是敲命令。

---

## 1. 用 VS Code 打开项目

| 操作 | 具体怎么做 |
|---|---|
| 打开文件夹 | VS Code 菜单 **文件 → 打开文件夹** → 选 `D:\deepseek\rag-doc-qa` |
| 信任工作区 | 弹窗点 **是，我信任此作者**（不点的话调试和终端会受限） |
| 看文件树 | 左侧「资源管理器」应能看到 `build_corpus.py`、`chunk.py`、`TEACHING.md` 等 |
| 打开终端 | 快捷键 **Ctrl + `**（反引号，Esc 下面那个键），或菜单 **终端 → 新建终端** |

终端里应该显示：

```
PS D:\deepseek\rag-doc-qa>
```

如果路径不对（比如显示 `C:\Users\ts`），先敲：

```powershell
cd D:\deepseek\rag-doc-qa
```

> **为什么强调这个路径**：项目里所有脚本都用 `Path(__file__).parent` 找 `data/`，
> 所以路径其实不影响运行；但 `python xxx.py` 必须在这个目录下，否则找不到文件。

---

## 2. 建虚拟环境（只做一次）

**为什么要 venv**：把 torch 这种 2GB 的库关在项目里，不污染系统 Python，删项目时一起删掉。

### 2.1 允许 PowerShell 跑脚本（只做一次）

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

提示确认时敲 `Y` 回车。不做这步，激活环境会报「禁止运行脚本」。

### 2.2 创建并激活

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

成功后提示符前面会多出 `(.venv)`：

```
(.venv) PS D:\deepseek\rag-doc-qa>
```

没有 `(.venv)` 就是没激活成功，别往下走——后面装的包会装到系统里。

### 2.3 让 VS Code 用这个解释器（关键）

1. 按 **Ctrl + Shift + P** 打开命令面板
2. 输入 `Python: Select Interpreter`（中文界面是「Python: 选择解释器」）
3. 选带 `.venv` 的那一项，路径形如 `.\\.venv\\Scripts\\python.exe`
4. 看 VS Code **右下角状态栏**，应显示 `Python 3.13.9 ('.venv')`

**验收**（终端里敲）：

```powershell
python -c "import sys; print(sys.executable)"
```

必须输出 `D:\deepseek\rag-doc-qa\.venv\Scripts\python.exe`。

> 报错「无法加载文件……因为在此系统上禁止运行脚本」→ 回到 2.1。
> 报错 `ensurepip` 失败 → 跳过 venv，直接用系统 Python 装（第 3 节命令去掉激活步骤即可）。

---

## 3. 装依赖（5 个包，第一次 5–15 分钟）

```powershell
python -m pip install -U pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

| 包 | 干什么 | 体积 |
|---|---|---|
| `sentence-transformers` + `torch` | 加载 bge 向量模型 | **约 2GB（最慢的就是它）** |
| `numpy` | 存向量、算余弦 | 20MB |
| `jieba` | 中文分词 | 20MB |
| `openai` | 调 DeepSeek | 2MB |
| `gradio` | 网页界面 | 60MB |

**验收**：

```powershell
pip list | Select-String "torch|sentence|jieba|numpy|openai|gradio"
```

六行都有版本号就对了。

**报错对照表**：

| 报错 | 原因 | 解决 |
|---|---|---|
| `SSLError` / `ConnectionResetError` | 网络 | 换镜像：`-i https://mirrors.aliyun.com/pypi/simple/` |
| `Could not find a version that satisfies torch` | 3.13 没匹配轮子 | `pip install torch --index-url https://download.pytorch.org/whl/cpu` 再装其余 |
| `No space left on device` | 磁盘不足 | 需要约 5GB 空闲 |
| `Microsoft Visual C++ 14.0 required` | 在源码编译 | 说明没装到轮子，换 Python 3.11/3.12 更稳 |

> 装 torch 时卡住不动是正常的（200MB 下载），别按 Ctrl+C。

---

## 4. 配两个环境变量（只做一次）

| 变量 | 作用 | 不配会怎样 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 让模型生成自然语言回答 | 降级成「抽取式」：只给章节 + 原文，不给结论 |
| `HF_ENDPOINT` | 从国内镜像下 bge 模型 | 大概率卡在下载，或超时失败 |

```powershell
setx DEEPSEEK_API_KEY "sk-你的key"
setx HF_ENDPOINT "https://hf-mirror.com"
```

`setx` 只影响**新开的**窗口，所以：

1. **关掉 VS Code 里所有终端**（点终端右上角的垃圾桶图标）
2. **完全退出 VS Code 再打开**（不是关窗口，是退出程序）

**验收**（新终端里）：

```powershell
$env:DEEPSEEK_API_KEY
$env:HF_ENDPOINT
```

第一条要能打印出你的 key（`sk-` 开头），第二条打印 `https://hf-mirror.com`。

> 没有 Key 也能继续，第 6 节的 `answer.py` 会走降级模式，先跑通流程更重要。
> Key 在 platform.deepseek.com 申请，充 10 块够这个项目用很久。

---

## 5. 准备语料

### 5.1 先用自带的示例（什么都不用做）

项目已带 `data/demo_novel.txt`（8 章原创短篇）。`build_corpus.py` 找不到 `novel.txt` 时会自动用它。

### 5.2 换成你自己的书

**先说一个最容易搞错的地方**：左侧文件树里点开哪个文件，跟程序读哪本书**没有关系**。
程序只认两个固定路径：`data/novel.txt`（你的书）和 `data/demo_novel.txt`（示例兜底）。
你把 `180.txt` 放在 `data/` 里、在左侧点开它，程序也不会读它——除非改名成 `novel.txt`。

| 操作 | 怎么做 |
|---|---|
| 存文件 | 把你的 txt 放到 `D:\deepseek\rag-doc-qa\data\`，**改名成 `novel.txt`**（覆盖示例也没关系） |
| 编码 | 用 VS Code 打开它，**右下角**应显示 `UTF-8`；显示 `GBK` 就点它 → 「通过编码保存」→ 选 UTF-8 |
| 章节标题 | 必须单独成行，形如 `第一章 落雁关的雪`、`第12章 xxx`、`第一百二十回 xxx` |
| 去掉目录 | 开头如果有目录页（一堆章节名连在一起），删掉，否则会被切出几百个空章 |

**验收**：文件树里 `data/novel.txt` 存在，双击打开，随便翻到中间，能看到 `第X章` 单独一行。

> 改完书**必须重建索引**（6.1 → 6.4 全部重跑），否则检索的还是上一本书。
> 懒得改文件名？用第 6.8 节的网页版，直接上传任意 txt，程序自己处理。

---

## 6. 跑流水线（按顺序，一步一验）

每条命令都在**已激活 .venv 的终端**里执行。跑完一步，对照「应该看到」再走下一条。

### 6.1 切章

```powershell
python build_corpus.py
```

应该看到：

```
总章数：8
平均每章：368 字（全书 2951 字）
第一章：第一章 落雁关的雪
```

看到 `总章数：1` 或报「章节正则可能不匹配」→ 打开 `build_corpus.py` 第 21 行的 `HEADING` 正则，对照你的标题长相改。

### 6.2 切块

```powershell
python chunk.py
```

```
总块数：15（8 章）
平均块长：212 字，最长 298 字
```

一章至少 1 块，块数 ≈ 全书字数 ÷ 250。你的书 60 万字，大概是 2000–2500 块。

### 6.3 建关键词索引

```powershell
python index_bm25.py
```

```
文档数：15，词表大小：2140，平均长度：374.7 词
查询「沈砚第一次拔剑」
    9.26  第四章 裴无咎的请帖  ……
```

顶部如果显示「二字切分（未安装 jieba）」，说明第 3 节没装好——功能还在，效果略差。

### 6.4 建向量索引（第一次会下模型，2–5 分钟）

```powershell
python index_vector.py
```

```
块数：15，向量维度：512
已写入 ...\data\vectors.npz（30 KB）
```

| 卡在哪 | 怎么办 |
|---|---|
| 卡在 `Downloading` 不动 | 关掉重来，确认第 4 节 `HF_ENDPOINT` 生效 |
| `ConnectionError` | 同上；或先手动 `huggingface-cli download BAAI/bge-small-zh-v1.5` |
| `No module named sentence_transformers` | 回第 3 节，确认装进了 `.venv` |

> 这一步失败**不影响后面**：`retrieve.py` 检测不到 `vectors.npz` 会自动只用 BM25。

### 6.5 试检索（全项目核心）

```powershell
python retrieve.py
```

```
查询：沈砚第一次拔剑是在第几章   （向量路：开）
  第4章 第四章 裴无咎的请帖  相关度 52%
  第3章 第三章 夜访藏经阁  相关度 30%
```

**「向量路：开」说明双路都生效；「关」说明只跑了 BM25。**
第一候选应是正确章节；不是的话，问题在检索，不在模型——这就是第 7 节要调的。

### 6.6 生成回答

```powershell
python answer.py "沈砚第一次拔剑是在第几章"
```

配了 Key：

```
沈砚在听雪楼第一次拔剑，刺向裴无咎的咽喉，被两指夹住剑尖。
出处：第4章 裴无咎的请帖
```

没配 Key：显示「抽取式模式 + 最可能章节 + 原文」，同样能用。

### 6.7 评估

```powershell
python evaluate.py
```

```
类型      题数    引用正确   top3     检索命中
事件       3       3      3        3
...
引用正确率 78%，top3 命中率 100%，检索命中率 100%
```

同时生成 `data/eval_result.csv`，可拖进 Excel 看逐题明细。

### 6.8 界面（支持上传任意 txt）

```powershell
python app.py
```

终端出现 `Running on local URL: http://127.0.0.1:7860`，浏览器打开这个地址。

页面打开时会自动载入 `data/novel.txt`（没有就用示例）。要换书：

1. 左侧「上传小说 txt」选文件
2. 等它切章、切块、建索引（短篇几秒，长篇半分钟）
3. 状态栏显示「《书名》· N 章 · M 块 · 向量：开」就可以了

关掉服务：终端里按 **Ctrl + C**。**这个网页只在你开着 `python app.py` 时存在**，关掉终端就没了，也只在这台电脑上能访问。

> 端口被占用 → 把最后一行改成 `demo.launch(server_port=7861)`。

---

## 7. 怎么读结果、怎么调

### 7.1 先看三个数字

| 指标 | 含义 | 低说明什么 |
|---|---|---|
| 检索命中率 | 标准答案原文有没有被捞出来 | 切块/分词有问题，**先修这个** |
| top3 命中率 | 正确章节有没有进前三 | 检索勉强能用，排序不行 |
| 引用正确率 | 第一名是不是对的 | 排序/融合权重问题 |

顺序不能反：**命中率上不去，调排序没意义。**

### 7.2 调参顺序（一次只改一个，改完重跑）

| 改什么 | 在哪改 | 改完必须重跑 |
|---|---|---|
| 块大小 / 重叠 | `chunk.py` 的 `DEFAULT_MAX` / `DEFAULT_OVERLAP` | `chunk.py` → `index_bm25.py` → `index_vector.py` → `evaluate.py` |
| 给模型几块 | `retrieve.py` 的 `top_k` | `evaluate.py` |
| 标题权重 | `index_bm25.py` 的 `c["chapter_title"] * 2`（改 1 或 3） | `index_bm25.py` |

### 7.3 典型症状

| 症状 | 先查 |
|---|---|
| 章数不对 | `build_corpus.py` 的正则 |
| 答案对了但章号错 | `retrieve.py` 的章节聚合 |
| 每个章相关度都 30% 左右 | 向量没生效（`vectors.npz` 不存在） |
| 回答开始编 | `answer.py` 的 `SYSTEM_PROMPT` 被改松了 |

---

## 8. 用 Git 存档（每跑通一步存一次）

VS Code 左侧点 **源代码管理** 图标，或直接敲：

```powershell
git init
git add .
git commit -m "feat: 切章 + 切块 + BM25 索引"
```

之后每完成一步：

```powershell
git add .
git commit -m "feat: 向量索引"
```

推到 GitHub：

```powershell
git remote add origin https://github.com/你的账号/novel-rag.git
git push -u origin main
```

`.gitignore` 已经写好了，`data/*.pkl`、`*.npz`、`.venv/`、`.env` 都不会上传。
**Key 千万别写进代码**，写进去推到 GitHub 几小时就会被盗刷。

---

## 9. 调试技巧（VS Code 最值钱的功能）

| 想干什么 | 怎么做 |
|---|---|
| 单独试一个函数 | 文件末尾 `if __name__ == "__main__":` 里写两行，右键 →「在终端中运行 Python 文件」 |
| 断点 | 行号左边点一下出现红点，按 **F5**，选「Python 文件」 |
| 看变量 | 断点停下后，左侧「运行和调试」面板能看到所有局部变量 |
| 快速看某个块 | 终端 `python -c "import retrieve; print(retrieve.search('关键词')['chapters'][:1])"` |

调试 `retrieve.py` 时最值得看的是 `fused` 这个字典：两路各自把哪个块排第几，一目了然。

---

## 10. 跑通之后做什么

1. **换成真书**（三国演义 120 回），重跑 6.1–6.7，看指标变化
2. 把「BM25-only 6/9 → 加向量后 7/9，top3 都 100%」的对比写进 README —— 面试就讲这个
3. 加 rerank（`bge-reranker-base`）或 query 改写，再测一次
4. 录 30 秒屏：提问 → 出章节 → 点开原文
