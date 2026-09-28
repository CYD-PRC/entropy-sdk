# Changelog

## v0.1.9（2026-09-28 · KIMICODE-SDKFIX9-20260928，**终局票：审计语义封口**）

**FIX9-1**：非有限 float **键**消毒——`nan/±inf` 作 dict 键时降级为字符串标记
（与 value 侧同记号）。`json.dumps` 对非有限键产出的是非严格 JSON，本票起键侧
与值侧同一把尺（严格解析器可消费，断言端含 parse_constant 钩子）。

**FIX9-2**：审计元数据迁入保留命名空间 `_audit_meta`——撞键标记
`{"_audit_meta": {"key_collision": true}}`，不再占用用户字段名 `_key_collision`；
用户自带 `_audit_meta` 字段时原值移入 `user_field_shadowed` 保留（零丢失）。
**行为变更**：v0.1.8 引入的顶层 `_key_collision` 标记位置随之迁移（一日龄 API，
随 FIX9-2 转正）。

**FIX9-3**：CI pip-audit 证据三态化——`PASS`（运行且零漏洞）／`VULN`（硬失败）／
`UNMEASURED`（查询未完成如 503，step 输出与 check 摘要显式可见，不得计入通过）。
本轮本地实测：**PASS**（No known vulnerabilities found；v0.1.8 轮的 503 是瞬时态）。

**终局注记**：本票后 SDK 审查循环正式关闭。冻结规则生效——仅「核心控制路径
新 P1/P2」可开新票；hygiene 层一律攒批，不逐轮打。

## v0.1.8（2026-09-28 · KIMICODE-SDKFIX8-20260928，**收官票：契约一致性收尾**）

**FIX8-1（P3）**：审计消毒器补键侧降级——dict 键与值同规则：非 JSON 键类型
（str/int/float/bool/None 以外）降级为 `str(k)`，合法键类型原样保留；撞键判据
按 JSON 序列化后的键形（`1` 与 `"1"` 同键），保留先见者并加 `"_key_collision": true`
标记（不静默覆盖）。

**FIX8-2（P3）**：数值契约统一拒 bool——`UtilityGate.theta`、`GearPolicy` 全部
数值字段（sigma_low/high/decay/step）对 bool 构造即抛；`FallbackConfig` 两字段
与 `GearPolicy.patience` 自 v0.1.2 起本已拒 bool（回归保持）。同一 SDK 同一
bool 态度（与 `_safe_gear` 对齐）；合法值（0/1/0.0/1.0）不受影响。

**收官注记**：GPT 第八轮审查五票以来首次无新 P2，严重度曲线触底；本票清掉
两条 P3 API hygiene 后 SDK 线冻结，进入攒批模式。

## v0.1.7（2026-09-28 · KIMICODE-SDKFIX7-20260928）

**FIX7-1（P2）**：`entries()` 改深拷贝——浅拷贝在嵌套字段时代不再足够
（v0.1.5 引入嵌套容器后，返回值的嵌套引用与真账/缓存共享，涂改即污染）；
与 FIX6-1 的 record() 同法。

**FIX7-2（P2）**：整数值 float 归一化——`FallbackConfig(max_alternatives=3.0)` /
`max_consecutive_rejections=5.0` 及 `GearPolicy.patience=2.0` 构造时归一为 int
（构造契约 == 执行契约；3.0 时代 runtime 的 `range(3.0)` 会炸 TypeError）。
非整数值 float 维持拒绝。

**FIX7-3（P3）**：审计消毒器对未知类型对象统一 `str()` 降级（与 file mode
`default=str` 同语义，保证 FIX6-1 的 deepcopy 对任何对象不炸）；契约写明：
audit fields 应为 JSON-compatible，未知对象按 str() 落账。

**FIX7-4（P3）**：README 测试计数与口径注记（106 passed 全量面 vs 96+3 裸 wheel
面，两数各配一句，防误读）。

## v0.1.6（2026-09-28 · KIMICODE-SDKFIX6-20260928）

**FIX6-1（P2）**：`AuditLog.record()` 返回值改深拷贝——memory mode 下返回值与真账
不再是同一个可变对象，调用方涂改返回值不再改写审计真账（v0.1.3 修的是 `entries`
出栈隔离，本票把 `record()` 返回值这条闭上）。file mode 行为不变。

**发布工程**：packaging smoke 增 wheel 内容显式断言（`entropy_sdk/py.typed` 与
LICENSE 必须在 wheel 内，负控实测会红）；license 声明迁移 SPDX 形式
（`license = "MIT"`，删 deprecated classifier，构建告警消失，twine check 仍 PASSED）。

**发布**：GitHub Release v0.1.6（+ v0.1.5 补登）；PyPI v0.1.6。

## v0.1.5（2026-09-27 · KIMICODE-SDKFIX5-20260927，微修 + 发布工程）

**FIX5-1 审计序列化递归消毒**：嵌套 dict/list/tuple 内的非有限 float（nan/±inf）
递归替换为字符串标记（"nan"/"+inf"/"-inf"，与顶层记号同族）；防循环引用（递归路径
id set，共享但不成环的兄弟引用不误伤）+ 深度上限 32（超限截断标记）。顶层既有行为
与标记格式不动（v0.1.2 记号演进史保持）。

**FIX5-2 LangChain adapter 齿轮契约统一**：构造期复用 runtime 的 `_safe_gear`——
`3.0` / `"3"` / `True` 等非法形构造即拒，与 runtime 判定完全一致（消灭「adapter 静默
截断、runtime 拒绝」的双口径）。

**FIX5-3 README 措辞降级**：PydanticAI「适配器」实为纯 stdlib 装饰器——两份 README
统一改为「PydanticAI-compatible callable decorator / PydanticAI 兼容的可调用装饰器」，
并注明未经真实 PydanticAI runtime 集成验证。功能入口不动。

**PyPI**：v0.1.5 起发布至 PyPI（`pip install entropy-sdk`）；README 的「尚未发布」声明到期摘除（FIX4-4 的另一半寿命闭合）。

**发布工程**（顺手项）：CI 增 packaging smoke（build → 装 wheel → import → pytest →
twine check）/ mypy src/ 全量 / langchain-core 兼容双档（最低实测支持版 0.2.43 +
声明域内最新）/ pip-audit（allow-fail）；langchain-core 声明区间收窄为
`>=0.2.43,<1.0`（0.2.0 实测不兼容，地板钉实测值不钉声明）。

## v0.1.4（2026-09-27 · KIMICODE-SDKFIX4-20260927，发布准备）

**fail-open 修复（FIX4-1，Grok 首发）**：效用门内新增非有限校验——utility 返回
NaN / +inf / -inf 一律拒绝。此前存在方向不对称：NaN 靠 IEEE 比较碰巧 fail-closed，
而 **`+inf >= θ` 恒真会放行执行**。同一把尺，两个方向都闭上；审计落盘经 FIX2-6
带符号消毒标记（"nan"/"+inf"/"-inf"）。

**发布面**：LICENSE（MIT 全文，GitHub License 栏可识别）；CI matrix 补 3.10
（对齐 requires-python）；`py.typed`；`examples/lifecycle_demo.py` 最小可跑例；
git tag `v0.1.4`。PyPI 发布因凭证不可用未发（README 的「尚未发布 PyPI」声明保留）。

**README 英文化**：主 README 全文英文（GitHub 受众面），中文原稿留 README.zh-CN.md；
威胁模型七条边界语义逐字保留；测试口径徽章附「实读日志」注记（82 passed / 0 skipped，
非 conclusion 徽章）。

## v0.1.3（2026-09-27 · KIMICODE-SDKFIX3-20260927，终审尾款）

**兼容性注记（fail-closed 方向）**：`required_gear=3.0`（整数值 float）自 v0.1.2
（strict attestation）起由接受变拒绝——依赖该写法的集成方请改用 int（`3` 或
`Gear.EXECUTE`）。

**修复**：
- 审计缓存隔离：对外 `.entries` 逐条浅拷贝，调用方涂改不再污染缓存与磁盘真值；
- 换挡清零同律：降档路径也清 `clean_streak`（v0.1.2 只清升档——σ 降档路径会残留）；
- CI 口径：`pip install -e .[dev,langchain]`，消灭「60 passed + 2 skipped 被报成 62」
  的合并口径；
- `initial_gear` 与 `required_gear` 同一严格度（非法构造即抛）；
- 文档：审计文件被删时读路径 fail-open 的不对称声明（README 威胁模型第 7 条）。

## v0.1.2（2026-09-27 · KIMICODE-SDKFIX2-20260927）

**BEHAVIOR CHANGE（FIX2-4）**：升档后 `clean_streak` 归零——每一档都需重新挣满 h 个
连续干净周期（论文「慢升、自主度逐档挣得」语义的实现对齐）。v0.1.1 及以前是首档挣 h、
之后每周期一档直窜 G4。依赖旧轨迹节拍的集成测试需按新期望（G0→G4 全升程 = 4h 个
干净周期）更新——这是刻意的行为变更，不是回归。

**PATCH 内破坏性恢复（FIX2-3）**：`max_alternatives=0` 恢复为合法配置，语义 =
「关闭 fallback」（拒绝后不调用 proposer，直接进 σ/降档/挂起流程）。v0.1.1 的
`>=1` 校验误杀了该意图；同时新增上界 ≤100（防 10**9 级每周期循环）。

**安全契约硬化**：
- strict gear attestation（`_safe_gear`）：只接受 Gear 实例与真 int；
  显式拒绝 bool（IntEnum 值查找里 True==1 会静默成 SUGGEST）、float/str/None/object；
  捕获 OverflowError（±inf）。
- 配置面 finite + 整数性校验：theta 拒 NaN/±inf；sigma 族全 finite；
  patience / fallback 两参数限有限整数。
- 审计链：文件模式读缓存（mtime+size 失效）；`_nonfinite` 消毒标记带符号
  （+inf / -inf / nan）；corrupt_lines 内存模式语义统一（恒 0）。

**文档**：威胁模型补 BaseException 边界与 args_schema 透传边界句；
pyproject Homepage 指向本仓。

**CI**：新增 GitHub Actions（push/PR × Python 3.11/3.12/3.13 全量 pytest）。

## v0.1.1（2026-09-26 · KIMICODE-SDKFIX-20260926）

fail-closed 边界（proposer/utility 异常、非法 gear）、配置零校验、审计链四病
（挂起换挡留痕 / 文件模式 entries / 坏行容错 / 非有限浮点消毒）、适配层
args_schema 与 description 透传、威胁模型五边界。逐票判词见 FIXREPORT（SDKFIX 票）。
