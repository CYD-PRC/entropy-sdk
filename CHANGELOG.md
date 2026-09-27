# Changelog

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
