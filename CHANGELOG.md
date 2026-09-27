# Changelog

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
