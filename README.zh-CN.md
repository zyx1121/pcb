<div align="center">

<h1>pcb</h1>

<p><strong>给 agent 用的 KiCad PCB 设计：固定的设计顺序、在固定版本 KiCad 容器里跑的无头关卡，以及通过 MCP 查 JLCPCB 料号。</strong></p>

[![CI](https://img.shields.io/github/actions/workflow/status/zyx1121/pcb/check.yml?branch=main&style=flat-square&label=CI)](https://github.com/zyx1121/pcb/actions)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-D97757?style=flat-square)](https://github.com/zyx1121/marketplace)
[![License](https://img.shields.io/github/license/zyx1121/pcb?style=flat-square)](LICENSE)

[English](README.md) | [繁體中文](README.zh-TW.md) | **简体中文**

</div>

KiCad 10 的自定义规则文件只要错一处，就会整份被丢弃，而且不报错：DRC 改用默认间距通过，exit code 是 0。pcbkit 先证明规则已加载，再逐脚比对板子与原理图，每个关卡都看实际找到了什么。

## 功能

- **规则确实生效**：先 lint `.kicad_dru`，再在副本加一条必定触发的哨兵规则跑 DRC。
- **板子对原理图**：每个位号、封装、引脚网络与数值，双向比对。
- **走线 lint**：直角转弯与自动布线留下的短线段。
- **JLCPCB 生产文件**：Gerber zip、BOM、CPL(含旋转修正)；BOM 对 JLCPCB 实时料库查基础件与库存。
- **先读规格书**：MCP 查料并保存规格书 PDF。
- **每块板一份配置**：`pcb.toml` 存项目选择与例外，每个例外都写原因。

## 快速开始

```sh
claude plugin marketplace add zyx1121/marketplace
claude plugin install pcb@zyx1121
```

MCP server 需要 Bun。`bin/pcbkit` 需要 Linux 上的 Docker。在板子旁放 `pcb.toml`(见 [skills/pcb/references/pcb-toml.md](skills/pcb/references/pcb-toml.md))，在该目录执行 `bin/pcbkit gate`。

## 用法

| 命令或工具 | 做什么 |
|---|---|
| `bin/pcbkit gate [名称]` | 跑关卡：`rules`、`drc`、`parity`、`route`、`jlc`，加上项目命令 |
| `bin/pcbkit fab` | 生成 Gerber zip、`bom-jlc.csv`、`cpl-jlc.csv` |
| `bin/pcbkit jlc` | BOM 对 JLCPCB 料库 |
| `bin/pcbkit datasheets` | 下载 BOM 每颗料的规格书 |
| MCP `jlc_search`、`jlc_part`、`datasheet_fetch` | 查料、查料号、存规格书 |

## 许可

[MIT](LICENSE)
