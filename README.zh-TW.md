<div align="center">

<h1>pcb</h1>

<p><strong>給 agent 用的 KiCad PCB 設計：固定的設計順序、在固定版本 KiCad 容器裡跑的無頭關卡，以及透過 MCP 查 JLCPCB 料號。</strong></p>

[![CI](https://img.shields.io/github/actions/workflow/status/zyx1121/pcb/check.yml?branch=main&style=flat-square&label=CI)](https://github.com/zyx1121/pcb/actions)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-D97757?style=flat-square)](https://github.com/zyx1121/marketplace)
[![License](https://img.shields.io/github/license/zyx1121/pcb?style=flat-square)](LICENSE)

[English](README.md) | **繁體中文** | [简体中文](README.zh-CN.md)

</div>

KiCad 10 的自訂規則檔只要錯一處，就會整份被丟掉，而且不出聲：DRC 改用預設間距通過，exit code 是 0。pcbkit 先證明規則有載入，再逐腳比對板子與電路圖，每個關卡都看實際找到什麼。

## 功能

- **規則確實有跑**：先 lint `.kicad_dru`，再在副本加一條一定觸發的哨兵規則跑 DRC。
- **板子對電路圖**：每個位號、封裝、腳位網路與數值，雙向比對。
- **走線 lint**：直角轉彎與自動佈線留下的短線段。
- **JLCPCB 生產檔**：Gerber zip、BOM、CPL(含旋轉修正)；BOM 對 JLCPCB 即時料庫查基本件與庫存。
- **先讀規格書**：MCP 查料並存下規格書 PDF。
- **第二意見**：kicad-druid 的 JLCPCB 規則與 kicad-happy 的分析在關卡後列出建議，不會讓關卡失敗。
- **每塊板一份設定**：`pcb.toml` 放專案選擇與例外，每個例外都寫原因。

## 快速開始

```sh
claude plugin marketplace add zyx1121/marketplace
claude plugin install pcb@zyx1121
```

MCP server 需要 Bun。`bin/pcbkit` 需要 Linux 上的 Docker。在板子旁放 `pcb.toml`(見 [skills/pcb/references/pcb-toml.md](skills/pcb/references/pcb-toml.md))，在該資料夾執行 `bin/pcbkit gate`。

## 用法

| 指令或工具 | 做什麼 |
|---|---|
| `bin/pcbkit gate [名稱]` | 跑關卡：`rules`、`drc`、`parity`、`route`、`jlc`，加上專案指令 |
| `bin/pcbkit fab` | 產生 Gerber zip、`bom-jlc.csv`、`cpl-jlc.csv` |
| `bin/pcbkit jlc` | BOM 對 JLCPCB 料庫 |
| `bin/pcbkit datasheets` | 下載 BOM 每顆料的規格書 |
| `bin/pcbkit freeroute IN OUT` | 用 Freerouting 2.6.0 自動佈線(固定版本、驗 checksum) |
| MCP `jlc_search`、`jlc_part`、`datasheet_fetch` | 查料、查料號、存規格書 |

## 授權

[MIT](LICENSE)
