# ArtGate｜游戏美术资产语义检索与入库预检工作台

> **已由 [ieg-artpipe](https://github.com/felix6328/ieg-artpipe) 取代。** 本仓库是早期版本，保留作过程记录；ArtPipe 改用开源游戏 0 A.D. 的真实资产和开发历史做评测，后续更新都在那边。

个人项目，为投递「腾讯 IEG｜腾讯游戏管理平台产品实习生」而做。  
**不是**腾讯或任何游戏项目组的生产系统，评测资产全部来自公开许可（Kenney CC0、Poly Haven CC0、Khronos 按模型各自许可）。

一句话产品观：**能用工具算死的，不交给模型；模型只做规则写不死的视觉判断，并且默认不阻断生产。通过或申诉通过后，资产才进入可检索库。**

## 它做什么

- **检索（v2 默认）：** 中文 / 英文自然语言 + 以图搜图。先按项目、类型、格式、面数区间做结构化过滤；文本查询走 **OpenCLIP 语义 + BM25 词法的 RRF 混合检索**，词法一路带手写中文游戏美术同义词扩展。`retriever=semantic` 可复现 v1。项目之间默认隔离。
- **入库预检：** 规则层用官方工具做命名、格式、体积、2 的幂次、面数预算、glTF 规范；可选的 VLM 只判断「文件名和画面是否一致」「是否偏离风格参考」，默认 warn，进人工队列。
- **平台化：** 引擎一套，规范是 YAML 模板。模板 M 模拟风格化手游低模（Kenney），模板 R 模拟写实项目（Poly Haven）。换项目只换配置，不改代码。

技术栈：Python 3.13、OpenCLIP `xlm-roberta-base-ViT-B-32` / `laion5b_s13b_b90k`（CPU）、LanceDB、Khronos glTF-Validator、glTF-Transform、FastAPI 工作台。没有 fork Immich 或其他相册内核。

## 如何运行

需要：Python 3.11+（开发时为 3.13.5）、Node.js（官方校验器与 glTF-Transform；没有 Node 时规则层会降级到 Python 回退，并在报告里标明）。建议 8GB 以上内存：模型加载后进程 RSS 约 2.2 GB。

```bash
git clone <本仓库> artgate && cd artgate
python3 -m venv .venv
source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
npm install          # 安装 gltf-validator 与 @gltf-transform/cli

export PYTHONPATH=$PWD
export HF_HOME=$PWD/.cache/huggingface   # 模型权重会下载到这里，约 1 GB，请勿提交

# 1. 下载公开资产（Kenney 子集、Poly Haven 1K、Khronos 样本），并写许可清单
python scripts/download_data.py

# 2. 生成故意损坏的预检夹具与预检金标
python scripts/create_broken_assets.py

# 3. 入库、渲预览、跑预检、嵌入索引（CPU 上大约数分钟到十几分钟）
python scripts/build_library.py

# 4. 按目录元数据自动起草检索金标（必须再由人审，见 eval/GOLD_QUERIES_README.md）
python scripts/generate_gold.py

# 5. v1 离线评测（纯语义，数字写入 eval/results.md）
python eval/measure.py

# 5b. v2 对比评测（同一套金标，不改题；写入 eval/results_v2.md）
python scripts/run_eval_v2.py

# 6. 把几条夹具放进人工队列，方便演示
python scripts/prepare_demo_queue.py

# 7. 打开工作台
./scripts/run_app.sh    # http://127.0.0.1:8765
```

已经有一份测完的 `eval/results.md`（v1）、`eval/results_v2.md`（v1 vs v2）和 `eval/badcases.md` 随仓库提供。若你重新跑评测，以新日志为准，不要把不同进程的时延混在一张表里。

复现 v1 检索：把 `configs/settings.yaml` 的 `search.retriever` 设为 `semantic`，或 `git checkout v1`。默认 `hybrid` 是 v2。金标 `eval/gold_queries.yaml` 在 v2 中未改动（SHA256 `8a019ae5a03e0ff3b0b69041d884861bda634905b12515839da020ed27d13f48`）。

单元测试：

```bash
python tests/test_rules.py
python tests/test_hybrid.py    # 分词、同义词、BM25、RRF，不加载 CLIP
```

### 可选：打开真实 VLM

默认 `configs/settings.yaml` 里 `vlm.backend: disabled`。无 API key 时视觉项标「未完成」，预检只保留规则层——这是设计，不是缺陷。

若要调用 OpenAI 兼容接口：

```bash
export ARTGATE_VLM_API_KEY=...          # 或 OPENAI_API_KEY
export ARTGATE_VLM_BASE_URL=https://... # 可选
export ARTGATE_VLM_MODEL=...            # 可选
```

并把 `vlm.backend` 改为 `openai_compat`。演示流水线可用 `mock`（只对夹具返回预定结果，**不能当视觉层评测**）。

## 本次实测数字（2026-11-13，Asia/Shanghai）

机器：Linux x86_64，8 核，内存约 16 GB，**仅 CPU**，Python 3.13.5。  
**检索金标是脚本自动起草的，尚未经人工审阅**，面试前请先看 [`eval/GOLD_QUERIES_README.md`](eval/GOLD_QUERIES_README.md)。金标在 v2 中未改（SHA256 `8a019ae5…d13f48`）。

### v1（纯语义，详见 [`eval/results.md`](eval/results.md)）

| 指标 | 实测 | 口径与限制 |
| --- | --- | --- |
| 可检索库规模 | 入库 960 条，成功索引 954 条 | Kenney 子集 931 + Poly Haven 29；3D 用软件等轴测预览 |
| 文本 Recall@10 | **0.6086**（n=87） | 中文 0.5548（n=54），英文 0.6967（n=33） |
| 文本 nDCG@10 | **0.5824**（n=87） | 中文 0.5415，英文 0.6493 |
| 文件名基线 Recall@10 | 中文 0.3355，英文 0.8206 | 中文语义高于文件名；英文文件名基线高于语义 |
| 以图搜图 Recall@10 | 1.0000（n=8） | 查询图是库内预览，偏乐观 |
| 检索 P95 时延 | **58.34 ms**（n=95，含以图搜图） | 另一轮配对重测的 v1 文本 P95 为 76.78 ms（n=87），与 v2 对比请用后者 |
| 规则层 P/R / 误拦 / 漏放 | 各检查项 1.00；误拦 0/9；漏放 0/8 | **仅 18 条注入样本**；v2 未重跑预检 |
| 单资产规则预检 P95 | **198.72 ms**（n=18） | mean 102.33 ms |
| 视觉层 P/R | 未测 | 无 VLM API key，简历保持占位 |

### v2（混合检索，同一套金标，详见 [`eval/results_v2.md`](eval/results_v2.md)）

方法：语义一路用原查询；BM25 一路对文件名/路径/标签做词法检索，查询经手写同义词扩展；两路用 **RRF（k=60）** 融合。英文短查询略抬 BM25 权重。词表与超参在看本轮分组结果之前冻结，**没有根据 dev 调参**。作者在写词表前已经见过 v1 全量坏例，存在泄漏风险。

| 系统 | 分组 | Recall@5 | Recall@10 | nDCG@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| v1 语义 | 全部文本 | 0.5304 (n=87) | 0.6086 (n=87) | 0.5824 (n=87) | 0.5962 (n=87) |
| v1 语义 | 中文 | 0.4783 (n=54) | 0.5548 (n=54) | 0.5415 (n=54) | 0.5559 (n=54) |
| v1 语义 | 英文 | 0.6158 (n=33) | 0.6967 (n=33) | 0.6493 (n=33) | 0.6621 (n=33) |
| **v2 混合** | **全部文本** | **0.7442** (n=87) | **0.8248** (n=87) | **0.8190** (n=87) | **0.8316** (n=87) |
| v2 混合 | 中文 | 0.7244 (n=54) | 0.7973 (n=54) | 0.7664 (n=54) | 0.7789 (n=54) |
| v2 混合 | 英文 | 0.7766 (n=33) | 0.8699 (n=33) | 0.9051 (n=33) | 0.9179 (n=33) |
| BM25 + 扩展（消融） | 全部文本 | 0.7090 (n=87) | 0.7629 (n=87) | 0.8004 (n=87) | 0.8170 (n=87) |
| BM25 + 扩展 | 中文 | 0.6823 (n=54) | 0.7338 (n=54) | 0.7511 (n=54) | 0.7608 (n=54) |
| BM25 + 扩展 | 英文 | 0.7526 (n=33) | 0.8105 (n=33) | 0.8810 (n=33) | 0.9091 (n=33) |
| 文件名基线 | 全部文本 | 0.4894 (n=87) | 0.5195 (n=87) | 0.5435 (n=87) | 0.5776 (n=87) |
| 文件名基线 | 中文 | 0.3262 (n=54) | 0.3355 (n=54) | 0.3354 (n=54) | 0.3750 (n=54) |
| 文件名基线 | 英文 | 0.7564 (n=33) | 0.8206 (n=33) | 0.8841 (n=33) | 0.9091 (n=33) |

同一轮时延（模型已加载，n=87 条文本）：v1 P95 **76.78 ms**，v2 P95 **86.31 ms**（mean 75.04），BM25-only P95 19.25 ms。v2 大约多 10 ms。

dev / test（固定种子 42，按语言 50/50，**事后检验，未在上面调参**）：v2 全文本 Recall@10 在 dev 为 0.7817（n=43），在 test 为 0.8670（n=44），test 没有塌陷；因作者见过 v1 全量坏例，这不能消除泄漏风险。

**相对 v1 的逐条变化：** 17 条从 Recall@10=0 变为有召回（含「一把剑」「圆形盾牌」「长矛」「一支箭」、`a sword`、`a spear` 等）；7 条明显提升（Δ≥0.15）；6 条两边仍为 0（「长方形盾牌」「男性角色」「横向滑动条」「牛油果」「地牢里的陷阱」、`drawbridge`）；**回退到 0 的有 0 条**；2 条明显下降（`rocket launcher` 1.00→0.67，「游戏手柄图标」0.40→0.20）。

特别要讲的两点：
1. 英文 v2 Recall@10 **0.8699 高于文件名基线 0.8206**（v1 语义 0.6967 是低于基线的）。这是 v2 的目标之一。
2. 「长方形盾牌」「男性角色」在 **BM25 单独已经是 1.0，混合后仍是 0**：两路都命中的 UI / 2D 干扰项把只在词法一路命中的正确答案挤出前 10。这是 RRF 的真实代价，本轮看完结果后没有回改融合规则。详见 `eval/results_v2.md` 与 `eval/badcases.md`。

种子库预检那两件（38 个 Kenney 武器 `SCENE_NON_ROOT_NODE`、15 张 Poly Haven 通道不全）与 v1 相同。

## 许可

详见 [`data/licenses.md`](data/licenses.md) 与 [`data/manifest.json`](data/manifest.json)。

- Kenney：原作 CC0（kenney.nl）。因官网 `download-link` 对非浏览器请求返回 403，下载脚本从 CC0 再分发仓库 [shorepine/kenney](https://github.com/shorepine/kenney) 稀疏克隆所选子集，并记录 commit。
- Poly Haven：CC0，官方 API，只拉 1K 与缩略图，不下 8K 全集。
- Khronos glTF-Sample-Assets：按模型各自许可，只作校验器测试，不是检索主库。
- 开源组件：OpenCLIP（MIT，以仓库 LICENSE 为准）、LanceDB（Apache-2.0）、glTF-Validator（Apache-2.0）、glTF-Transform（MIT）。

不要把这些资产写成「项目组真实资产」。

## 代码导读（面试用：每个模块为什么这样设计）

仓库根目录的 `artgate/` 是 Python 包，`app/` 是工作台，`scripts/` 是数据与评测，`configs/templates/` 是两套规范，`eval/` 是金标和结果。

### `configs/templates/`：引擎一套，规范可切换

面数、贴图上限、命名正则、block/warn、必选通道全部在 YAML 里。模板 M 的面数预算来自本仓库对 539 个 Kenney glb 的实测（min=2，p50=140，p95=880，max=1660），不是拍脑袋。模板 R 按写实资产抬高预算，并要求贴图套装的 PBR 通道；`ktx2` 在配置里允许，但评测集未覆盖真实样本，README 和模板都写了「未覆盖」。

**2 的幂次不一刀切：** 对 `texture` 类型和 3D 模型贴图强制，对 UI / 2D 精灵不强制。游戏 UI 经常是 1000×800 这种非 POT 尺寸，强制会误拦、打死使用率。夹具里有同一张 1000×800：类型为 texture 则 block，类型为 ui 则通过。这是产品判断，可以用这两条演示。

### `artgate/precheck/gltf_tools.py` + 两个 JS 脚本：数值只来自官方工具

- `gltf_validate.js` 调用 Khronos `gltf-validator`，并提供 `externalResourceFunction` 去读 GLB 旁边的 `Textures/colormap.png`。若不提供，Kenney 这类「GLB + 外部贴图」会被误报 `IO_ERROR`（error）——那是调用方式的问题，不是资产不合规。这是面试里「你有没有对 AI / 工具输出做过高质量判断」的例子。
- `gltf_inspect.js` 调用 `@gltf-transform/functions` 的 `inspect()`，取 `glPrimitives`（三角面）和贴图 `resolution`。
- 官方工具失败时，Python / trimesh 可以回退出面数，但报告必须标明「使用了回退」；**禁止改由 LLM 口算**。校验器失败则该项标「待人工」，overall 最多升为 warn，不伪装成通过，也不伪装成规范错误。
- 只有校验器 **severity=0（error）** 才可作为 block；warning 不阻断。避免「把 warning 误当成 error」。

### `artgate/precheck/engine.py`：工作流，不是自主 Agent

固定编排：规则全部跑完 → 仅当规则层没有 block 失败、且模板启用了视觉项时才调 VLM（成本策略）→ 汇总给人。写操作（入检索库、改级别）不在本模块。工具包括 `validate_gltf`、`inspect_mesh`、`check_image_specs`、`match_naming`、`vlm_visual_review`，面试若问「这是不是 Agent」，答：更像工作流 + 工具调用。

总体判定：任一 block 失败 → `block`；否则有 warn 失败或工具失败 → `warn`；全过 → `pass`。即使 overall=pass，默认仍进人工队列。

### `artgate/precheck/vlm.py`：可插拔，可降级

三种后端：`disabled`（默认）、`mock`（只为夹具演示）、`openai_compat`（有 key 才走）。输出必须是结构化 JSON（issue_code、证据、置信度、建议级别），禁止散文，禁止给出面数或像素。低置信 / 超时 / 解析失败：视觉项标未完成，不编评语。VLM 建议默认限制为 warn，模板没有把该项升为 block 之前，不会因为模型一句话卡住线。

### `artgate/search/`：先过滤；v2 是语义 + 词法的 RRF，不是只靠向量

- `preview.py`：CLIP 不能直接吃网格。Kenney 本子集没有逐模型官方预览，所以用纯软件等轴测光栅化（不依赖 GPU）。做不完或失败会落占位图——3D 文本检索变差，往往与预览域有关。v2 **并没有从模型上治好剑/刀混淆**，只是用词法一路把 `weapon-sword.glb` 托上来（「一把剑」语义约第 37、BM25 第 1）。
- `embedder.py`：指定的多语言模型，CPU，按文件哈希缓存。中文查询不用英文 CLIP。**语义一路始终用原始查询，不把译名塞进 CLIP**，以免稀释多语言语义。
- `tokenize.py` / `bm25.py`：文档由文件名、路径、类型、标签构成（文件名和标签加权）。实现 Lucene 风格 BM25（k1=1.5，b=0.75），960 条完全放内存，与向量库共用同一套结构化过滤。不引入额外依赖，公式可以在面试里写出来。
- `expand.py` + `configs/synonyms_game_art.yaml`：手写中英游戏美术词表。按词条从长到短匹配。「剑」→ sword/blade，**不**→ knife，避免把剑和刀互串。泄漏风险写在词表头注释和评测报告里。
- `hybrid.py`：RRF，k=60（Cormack 常用值）。选用 RRF 是因为 CLIP 展示分和 BM25 分数量纲不同，直接加权要先归一化，容易过拟合。查询类型路由：中文或长英文描述两路等权；标识符或 1–2 个英文实词（`a sword`）把 BM25 权重调到 1.5——这是 v1 已发布的观察，不是本轮网格搜索。
- `index.py` / `query.py`：`retriever` 为 `hybrid`（默认）/ `semantic`（v1）/ `bm25`。LanceDB 预过滤。嵌入不可用时降级为 BM25，再不行才用旧的文件名重叠，并明确提示。过宽查询仍提示加过滤。

### `artgate/review/queue.py`：人在回路

通过 / 退回 / 申诉通过，原因必填，写入评测回流。禁止自动删除、禁止自动驳回 warn。只有通过或申诉通过才写入向量库。种子库用 `seed_approve` 模拟「已在生产库的历史资产」，预检仍然跑了，不是跳过门禁。

### `eval/`：先定义指标，再填数，不回改金标

检索金标由 `scripts/generate_gold.py` 根据文件名 / 包名 / 类型起草，**起草时不运行检索**。状态是 `auto_drafted_needs_review`。预检金标在 `create_broken_assets.py` 注入错误时写定，不根据预检输出回改。`scripts/run_eval.py` 写 v1 结果；`scripts/run_eval_v2.py` 在**同一套未改动的金标**上对比 v1 / v2 / BM25 / 文件名基线，并用固定种子切 dev/test 做事后检验，但本轮没有按 dev 调参。切分方案见 `eval/split_v2.json`。

### `app/`：给 Demo 用的薄工作台

FastAPI + 单页：检索、入库预检、人工队列、模板对照、费用看板、评测结果。费用看板里的 VLM 单价是假设，不得写成账单。

## 已知限制

- 检索金标未经人工审阅；相关集可能过宽或过窄（例如「武器」把 72 件武器都标相关，Recall@10 自然会被拉低）。
- 预检金标只有 18 条，规则层 1.00 只能说明夹具被正确拦住，不能代表生产误拦率。
- 3D 预览是自己渲的，不是引擎截图；语义一路的兵器近形混淆还在，v2 靠词法托上来。有两条 BM25 已能召回、混合后仍为 0（RRF 干扰项问题），见 `eval/results_v2.md`。
- v2 同义词表作者见过 v1 全量坏例，有泄漏风险；dev/test 是缓解不是消除。
- 没有真实项目组访谈（【待实际访谈后填】），没有线上点击率 / 申诉率。
- 未测真实 VLM。
- 风格覆盖有限（Kenney 卡通低模 + Poly Haven 写实），不能代表二次元或像素风。
- 冷启动：空库时预检门禁仍然有价值，检索的价值随库增长出现。

## 简历条目（数字已用本次实测替换；金标待审必须写明）

见下方，也可直接对照 `eval/results.md`（v1）与 `eval/results_v2.md`（对比）。访谈人数、视觉层指标保持占位。金标待审必须写明。

**游戏美术资产语义检索与入库预检工作台（ArtGate）**｜个人项目｜2026.11

基于 OpenCLIP（`xlm-roberta-base-ViT-B-32`，LAION-5B）、LanceDB、自研 BM25 与 Khronos glTF-Validator、glTF-Transform 等开源组件二次开发（非商业游戏资产；评测使用 Kenney CC0、Poly Haven CC0 及按许可使用的 Khronos 样本）

- 面向游戏美术「已有资产找不到、入库规范靠人工抽查」的痛点，将命名、格式、分辨率、面数预算、贴图通道等共性能力做成**可按项目切换的规范模板**，差异全部配置化；用两套模板分别模拟风格化手游与写实资产项目，验证同一套预检与检索引擎可复用。【待实际访谈后填：访谈 N 位游戏美术 / TA，将高频返修原因写入检查项】
- 设计「结构化过滤 + 多模态语义」的检索，并在 v1 评测后针对坏例做了 v2：**语义检索与 BM25 词法检索用 RRF 融合**，词法一路配手写中文游戏美术同义词表（「剑」译为 sword/blade、不译为 knife）。在同一套 87 条文本查询金标（中文 54、英文 33，另有 8 条以图搜图；**由脚本根据文件名自动起草，尚未人工审阅**；v2 **未改题**）上：v1 文本 Recall@10 为 0.6086（中文 0.5548，英文 0.6967），nDCG@10 为 0.5824；v2 文本 Recall@10 为 0.8248（中文 0.7973，英文 0.8699），nDCG@10 为 0.8190。对照纯文件名搜索，中文从基线 0.3355 升到 v2 的 0.7973；英文 v1 语义 0.6967 曾低于文件名基线 0.8206，v2 为 0.8699，高于该基线。17 条查询从 Recall@10=0 变为有召回（含「一把剑」「圆形盾牌」「长矛」、`a sword` 等），0 条回退到 0。词表写于 v1 评测之后，作者见过全量坏例，**存在泄漏风险**；用固定种子切了 dev/test 做事后检验（v2 Recall@10：dev 0.7817，test 0.8670），本轮未按 dev 调参。以图搜图 Recall@10 为 1.0，查询图为库内预览，偏乐观。
- 将质量预检拆成两层：**规则引擎与官方工具**负责命名、尺寸、格式、2 的幂次、glTF 规范与面数 / 贴图体积（数值只来自工具，不交给模型）；**VLM** 只做文件名与内容是否一致、是否偏离项目风格参考板，输出带证据与置信度的建议，无 key 时降级为仅规则结果。结果默认进入人工确认，TA 通过后才入可检索库。在 18 条注入错误与合规对照上，规则层各检查项 Precision / Recall 为 1.00（**样本量小，不能外推**），合格资产误拦率 0/9，应拦截漏放率 0/8。视觉层精确率 / 召回率【未测，保持占位】。
- 明确 AI 边界与失败兜底：确定性错误才默认阻断，视觉项默认警告；校验器 warning 不升为 block；VLM 超时或低置信则降级为仅规则结果；禁止自动删除或自动驳回警告项。整理检索与预检坏例：语义一路的剑/刀混淆并未从模型上消失；「长方形盾牌」「男性角色」在 BM25 单独 Recall@10=1.0、混合后仍为 0（两路都命中的干扰项挤掉只在词法一路命中的正确答案），本轮看完结果后没有回改融合规则。见 `eval/badcases.md`。
- 建立费用与时延看板：嵌入本地计算并按文件哈希缓存，VLM 仅对启用视觉项的资产调用缩略图。本地嵌入 API 费用为 0。同一轮配对测量中，v1 单次检索 P95 为 76.78 ms，v2 为 86.31 ms（CPU，模型已加载，n=87 条文本）；单资产规则预检 P95 198.72 ms（n=18）。（v1 首轮含以图搜图的 P95 为 58.34 ms，n=95，不要与配对表混用。）
