# ArtGate｜游戏美术资产语义检索与入库预检工作台

个人项目，为投递「腾讯 IEG｜腾讯游戏管理平台产品实习生」而做。  
**不是**腾讯或任何游戏项目组的生产系统，评测资产全部来自公开许可（Kenney CC0、Poly Haven CC0、Khronos 按模型各自许可）。

一句话产品观：**能用工具算死的，不交给模型；模型只做规则写不死的视觉判断，并且默认不阻断生产。通过或申诉通过后，资产才进入可检索库。**

## 它做什么

- **检索：** 中文 / 英文自然语言 + 以图搜图。先按项目、类型、格式、面数区间做结构化过滤，再在子集里做 OpenCLIP 多模态语义检索。项目之间默认隔离。
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

# 5. 离线评测（数字写入 eval/results.md，不编造）
python eval/measure.py

# 6. 把几条夹具放进人工队列，方便演示
python scripts/prepare_demo_queue.py

# 7. 打开工作台
./scripts/run_app.sh    # http://127.0.0.1:8765
```

已经有一份测完的 `eval/results.md` / `eval/badcases.md` 随仓库提供。若你重新跑评测，以新日志为准，不要混用两次的数字。

单元测试（不依赖完整库，有资产时会顺带测一把剑的预检）：

```bash
python tests/test_rules.py
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

机器：Linux x86_64，8 核，内存约 16 GB，**仅 CPU**，Python 3.13.5。完整表格与逐条结果见 [`eval/results.md`](eval/results.md)。**检索金标是脚本自动起草的，尚未经人工审阅**，面试前请先看 [`eval/GOLD_QUERIES_README.md`](eval/GOLD_QUERIES_README.md)。

| 指标 | 实测 | 口径与限制 |
| --- | --- | --- |
| 可检索库规模 | 入库 960 条，成功索引 954 条 | Kenney 子集 931 + Poly Haven 29；3D 用软件等轴测预览 |
| 文本 Recall@10 | **0.6086**（n=87） | 金标待审；中文 0.5548（n=54），英文 0.6967（n=33） |
| 文本 nDCG@10 | **0.5824**（n=87） | 中文 0.5415，英文 0.6493 |
| 文本 MRR / Recall@5 | 0.5962 / 0.5304 | 同上 |
| 文件名基线 Recall@10 | 中文 0.3355，英文 0.8206 | 中文语义高于文件名；英文文件名基线高于语义（查询词与英文文件名重叠） |
| 以图搜图 Recall@10 | 1.0000（n=8） | 查询图是库内预览，偏乐观 |
| 检索 P95 时延 | **58.34 ms**（n=95） | 模型已加载后的查询；mean 47.01 ms。不含首次加载（约 7–11 s） |
| 规则层 Precision / Recall / F1 | 各检查项均为 1.00，宏平均 1.00 | **仅 18 条注入样本**，不能外推到生产 |
| 误拦率 | **0 / 9 = 0** | 合格或不应 block 的对照 |
| 漏放率 | **0 / 8 = 0** | 应 block 的注入错误 |
| 单资产规则预检 P95 | **198.72 ms**（n=18） | mean 102.33 ms，max 237.41 ms |
| 视觉层 P/R、误拦率 | 未测 | 无 VLM API key，简历保持占位 |
| 嵌入 API 费用 | 0 | 本地计算并按哈希缓存 |

种子库里还有两件与评测金标无关、但值得在面试讲的事：

1. Kenney Weapon Pack 中 38 个 glb 被官方校验器报 `SCENE_NON_ROOT_NODE`（error）。按「官方 error 才 block」的策略，它们被规则层拦截。引擎里它们往往仍能打开——若要降为 warn，应改模板策略并重跑误拦率，而不是改工具输出。
2. 15 张 Poly Haven 贴图按「只提交了 albedo 文件」对照模板 R 的三通道要求，被 `required_channels` 拦截。这是规则在干活，不是误报。

坏例分类见 [`eval/badcases.md`](eval/badcases.md)。比较突出的：中文「一把剑」「圆形盾牌」「长矛」和英文 `a sword` 的 Recall@10 为 0，返回经常是刀或近形物体。

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

### `artgate/search/`：先过滤，再向量；失败则降级

- `preview.py`：CLIP 不能直接吃网格。Kenney 本子集没有逐模型官方预览，所以用纯软件等轴测光栅化（不依赖 GPU）。做不完或失败会落占位图，并记入限制——3D 文本检索变差，很可能与预览域有关。
- `embedder.py`：指定的多语言模型，CPU，按文件哈希缓存。中文查询不用英文 CLIP。
- `index.py` / `query.py`：LanceDB。默认带 `project_id` 预过滤。精确 ID 走元数据，不绕向量。嵌入不可用时降级为文件名 / 标签搜索，并在界面明确提示「语义检索暂时不可用」。过宽查询（「武器」「food」）仍检索，但提示加过滤；完整短语如「一把剑」不当作过宽。

### `artgate/review/queue.py`：人在回路

通过 / 退回 / 申诉通过，原因必填，写入评测回流。禁止自动删除、禁止自动驳回 warn。只有通过或申诉通过才写入向量库。种子库用 `seed_approve` 模拟「已在生产库的历史资产」，预检仍然跑了，不是跳过门禁。

### `eval/`：先定义指标，再填数，不回改金标

检索金标由 `scripts/generate_gold.py` 根据文件名 / 包名 / 类型起草，**起草时不运行检索**。状态是 `auto_drafted_needs_review`。预检金标在 `create_broken_assets.py` 注入错误时写定，不根据预检输出回改。`scripts/run_eval.py`（`eval/measure.py` 是入口）只负责算数和归坏例。

### `app/`：给 Demo 用的薄工作台

FastAPI + 单页：检索、入库预检、人工队列、模板对照、费用看板、评测结果。费用看板里的 VLM 单价是假设，不得写成账单。

## 已知限制

- 检索金标未经人工审阅；相关集可能过宽或过窄（例如「武器」把 72 件武器都标相关，Recall@10 自然会被拉低）。
- 预检金标只有 18 条，规则层 1.00 只能说明夹具被正确拦住，不能代表生产误拦率。
- 3D 预览是自己渲的，不是引擎截图；一批兵器类文本查询召回为 0。
- 没有真实项目组访谈（【待实际访谈后填】），没有线上点击率 / 申诉率。
- 未测真实 VLM。
- 风格覆盖有限（Kenney 卡通低模 + Poly Haven 写实），不能代表二次元或像素风。
- 冷启动：空库时预检门禁仍然有价值，检索的价值随库增长出现。

## 简历条目（数字已用本次实测替换；金标待审必须写明）

见下方，也可直接对照 `eval/results.md`。访谈人数、视觉层指标、若未做的模块，保持占位，不要填。

**游戏美术资产语义检索与入库预检工作台（ArtGate）**｜个人项目｜2026.11

基于 OpenCLIP（`xlm-roberta-base-ViT-B-32`，LAION-5B）、LanceDB 与 Khronos glTF-Validator、glTF-Transform 等开源组件二次开发（非商业游戏资产；评测使用 Kenney CC0、Poly Haven CC0 及按许可使用的 Khronos 样本）

- 面向游戏美术「已有资产找不到、入库规范靠人工抽查」的痛点，将命名、格式、分辨率、面数预算、贴图通道等共性能力做成**可按项目切换的规范模板**，差异全部配置化；用两套模板分别模拟风格化手游与写实资产项目，验证同一套预检与检索引擎可复用。【待实际访谈后填：访谈 N 位游戏美术 / TA，将高频返修原因写入检查项】
- 设计「结构化过滤 + 多模态语义」的检索：支持中文自然语言与以图搜图，项目、类型、格式、面数区间走字段过滤，语义检索只在过滤后的子集上进行；3D 资产按软件渲染的预览图嵌入。在自建 87 条文本查询金标（中文 54、英文 33，另有 8 条以图搜图；**由脚本根据文件名自动起草，尚未人工审阅**）上，文本 Recall@10 为 0.6086（中文 0.5548，英文 0.6967），nDCG@10 为 0.5824（中文 0.5415，英文 0.6493）。对照纯文件名搜索，中文 Recall@10 从 0.3355 提升到 0.5548；英文文件名基线为 0.8206，高于语义的 0.6967（英文查询与英文文件名高度重叠）。以图搜图 Recall@10 为 1.0，但查询图为库内预览，偏乐观。
- 将质量预检拆成两层：**规则引擎与官方工具**负责命名、尺寸、格式、2 的幂次、glTF 规范与面数 / 贴图体积（数值只来自工具，不交给模型）；**VLM** 只做文件名与内容是否一致、是否偏离项目风格参考板，输出带证据与置信度的建议，无 key 时降级为仅规则结果。结果默认进入人工确认，TA 通过后才入可检索库。在 18 条注入错误与合规对照上，规则层各检查项 Precision / Recall 为 1.00（**样本量小，不能外推**），合格资产误拦率 0/9，应拦截漏放率 0/8。视觉层精确率 / 召回率【未测，保持占位】。
- 明确 AI 边界与失败兜底：确定性错误才默认阻断，视觉项默认警告；校验器 warning 不升为 block；VLM 超时或低置信则降级为仅规则结果；禁止自动删除或自动驳回警告项。整理检索与预检坏例（兵器类文本召回为 0、近形刀剑混淆、过宽查询、Kenney 武器包 `SCENE_NON_ROOT_NODE` 等），见 `eval/badcases.md`。
- 建立费用与时延看板：嵌入本地计算并按文件哈希缓存，VLM 仅对启用视觉项的资产调用缩略图。本地嵌入 API 费用为 0。单次检索 P95 时延 58.34 ms（CPU，模型已加载，n=95），单资产规则预检 P95 198.72 ms（n=18）。
