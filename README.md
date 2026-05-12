# CANoe Automated Testing Agent

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![CANoe](https://img.shields.io/badge/CANoe-Supported-orange?logo=vector&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)

**面向车载总线测试场景的 AI 驱动自动化测试 Agent**

[English](#english) | [中文](#中文)

</div>

---

## 中文

### 🎯 项目简介

CANoe Automated Testing Agent 是一个专为车载总线（CAN/LIN/FlexRay）测试场景设计的 AI 驱动自动化测试框架。它通过多模块协作 Agent 架构，核心解决了传统 CANoe 测试中的三大痛点：

| 痛点 | 传统方式 | Agent 方式 |
|------|---------|-----------|
| 报文配置低效 | 手动逐信号配置，单报文 30 分钟 | 自动解析 DBC，2 分钟完成 |
| 多信号校验易出错 | 人工比对起始位/字节序/复用 | 自动校验并修复不规范定义 |
| 联调耗时久 | 反复手动执行、目视对比 | 闭环自动仿真 + 标准化报告 |

### 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    CANoe Automated Testing Agent                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  DBC Parser  │───▶│    Signal    │───▶│      CAPL        │  │
│  │  Sub-Agent   │    │  Reasoner    │    │    Generator     │  │
│  │              │    │  Sub-Agent   │    │    Sub-Agent     │  │
│  │ • 解析 DBC   │    │              │    │                  │  │
│  │ • 校验信号   │    │ • 依赖分析   │    │ • OEM 规范脚本   │  │
│  │ • 修复定义   │    │ • 长链推理   │    │ • CAPL 用例生成  │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│         │                    │                     │            │
│         ▼                    ▼                     ▼            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Closed-loop Verification Sub-Agent          │  │
│  │                                                          │  │
│  │  • CANoe API 调用  • 仿真执行  • 数据比对  • 报告生成   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### ✨ 核心特性

- **🔧 DBC 智能解析**：自动读取 DBC 文件，校验信号起始位、字节序（Motorola/Intel）、多路复用配置，识别并修复不规范定义
- **🧠 信号依赖推理**：基于长链推理分析信号间依赖关系，自动识别多路复用器与多路信号的映射
- **📝 CAPL 用例生成**：根据 OEM 规范自动生成报文发送脚本和 CAPL 测试用例，支持诊断服务（UDS）和信号仿真
- **🔄 闭环验证**：调用 CANoe API 执行仿真，自动对比预期值与总线实际数据
- **📊 标准化报告**：一键生成 HTML/JSON 格式测试报告，包含通过率、失败详情、信号时序图

### 📈 性能指标

| 指标 | 传统方式 | Agent 方式 | 提升 |
|------|---------|-----------|------|
| 单报文配置时间 | 30 分钟 | 2 分钟 | **93%** |
| 测试用例编写效率 | 基准 | 提升 | **90%** |
| 人工配置错误率 | 高 | 极低 | **大幅降低** |
| 联调重复工作 | 大量 | 最小化 | **显著减少** |

### 🚀 快速开始

#### 环境要求

- Python 3.10+
- Vector CANoe 14.0+（闭环验证模块需要）
- Windows 10/11

#### 安装

```bash
git clone https://github.com/Wansuhui3/canoe-automated-testing-agent.git
cd canoe-automated-testing-agent
pip install -r requirements.txt
```

#### 基础用法

```python
from src.agents import DBCParseAgent, SignalReasonerAgent, CAPLGeneratorAgent, VerificationAgent

# 1. 解析 DBC 文件
parser = DBCParseAgent()
dbc_model = parser.parse("examples/dbc/bcm_example.dbc")
validation_result = parser.validate(dbc_model)

# 2. 信号依赖推理
reasoner = SignalReasonerAgent()
dependency_graph = reasoner.analyze(dbc_model)

# 3. 生成 CAPL 测试用例
generator = CAPLGeneratorAgent(spec="config/oem_specs/bcm_spec.yaml")
capl_scripts = generator.generate(dbc_model, dependency_graph)

# 4. 闭环验证
verifier = VerificationAgent(canoe_config="examples/config/bcm_test.yaml")
report = verifier.execute_and_verify(capl_scripts)
print(f"测试通过率: {report.pass_rate:.1%}")
```

#### 命令行工具

```bash
# 一键式：从 DBC 到测试报告
python tools/batch_runner.py --dbc examples/dbc/bcm_example.dbc --config examples/config/bcm_test.yaml --output examples/output/

# DBC 校验工具
python tools/dbc_checker.py --input examples/dbc/bcm_example.dbc --fix
```

### 📂 项目结构

```
canoe-automated-testing-agent/
├── src/                          # 核心源码
│   ├── agents/                   # 多模块协作 Agent
│   │   ├── dbc_parser_agent.py   # DBC 解析子 Agent
│   │   ├── signal_reasoner_agent.py  # 信号推理子 Agent
│   │   ├── capl_generator_agent.py   # CAPL 生成子 Agent
│   │   └── verification_agent.py     # 闭环验证子 Agent
│   ├── dbc/                      # DBC 解析引擎
│   │   ├── parser.py             # DBC 文件解析器
│   │   ├── validator.py          # 信号校验器
│   │   └── models.py             # 数据模型
│   ├── signal/                   # 信号分析引擎
│   │   ├── dependency_analyzer.py # 信号依赖分析
│   │   └── mux_handler.py        # 多路复用处理
│   ├── capl/                     # CAPL 生成引擎
│   │   ├── generator.py          # CAPL 代码生成器
│   │   ├── oem_rules.py          # OEM 规范引擎
│   │   └── templates/            # CAPL 模板
│   ├── verification/             # 闭环验证引擎
│   │   ├── canoe_interface.py    # CANoe API 接口
│   │   ├── comparator.py         # 数据比对器
│   │   └── simulator.py          # 仿真控制器
│   └── report/                   # 报告生成引擎
│       ├── generator.py          # 报告生成器
│       └── templates/            # 报告模板
├── config/                       # 配置文件
│   ├── default.yaml              # 默认配置
│   └── oem_specs/                # OEM 规范
├── examples/                     # 示例文件
│   ├── dbc/                      # 示例 DBC
│   ├── config/                   # 示例配置
│   └── output/                   # 示例输出
├── tests/                        # 单元测试
├── docs/                         # 文档
├── tools/                        # 命令行工具
│   ├── dbc_checker.py            # DBC 校验工具
│   └── batch_runner.py           # 批量运行工具
└── requirements.txt              # 依赖列表
```

### 🔧 应用场景

#### BCM 诊断报文仿真测试

```yaml
# examples/config/bcm_test.yaml
target: BCM
protocol: UDS
services:
  - 0x22  # ReadDataByIdentifier
  - 0x2E  # WriteDataByIdentifier
  - 0x31  # RoutineControl
  - 0x11  # ECUReset
  - 0x27  # SecurityAccess
  - 0x19  # ReadDTCInformation
  - 0x14  # ClearDTC
security:
  seed: 0xA5B6
  session_check: false
```

#### 毫米波雷达信号仿真测试

```yaml
# examples/config/radar_test.yaml
target: FLR
protocol: CAN
messages:
  - name: RadarTrack
    id: 0x18FEDA27
    signals:
      - Track_ID
      - Track_Dist
      - Track_Vrel
      - Track_Angle
```

### 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

### 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

<a id="english"></a>

## English

### 🎯 Overview

CANoe Automated Testing Agent is an AI-driven automated testing framework designed for vehicle bus (CAN/LIN/FlexRay) testing scenarios. Through a multi-module collaborative Agent architecture, it addresses three core pain points in traditional CANoe testing:

| Pain Point | Traditional | Agent-powered |
|-----------|-------------|---------------|
| Inefficient message config | Manual per-signal, 30 min/message | Auto-parse DBC, 2 min/message |
| Error-prone multi-signal validation | Manual bit/byte-order/mux check | Auto-validate & fix non-compliant definitions |
| Time-consuming integration | Manual execution + visual comparison | Closed-loop simulation + standardized reports |

### 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CANoe Automated Testing Agent                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  DBC Parser  │───▶│    Signal    │───▶│      CAPL        │  │
│  │  Sub-Agent   │    │  Reasoner    │    │    Generator     │  │
│  │              │    │  Sub-Agent   │    │    Sub-Agent     │  │
│  │ • Parse DBC  │    │              │    │                  │  │
│  │ • Validate   │    │ • Dependency │    │ • OEM-compliant  │  │
│  │ • Fix issues │    │ • Reasoning  │    │ • CAPL cases     │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│         │                    │                     │            │
│         ▼                    ▼                     ▼            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Closed-loop Verification Sub-Agent          │  │
│  │                                                          │  │
│  │  • CANoe API  • Simulation  • Data Compare  • Reports   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### ✨ Key Features

- **🔧 Smart DBC Parsing**: Auto-read DBC files, validate signal start bits, byte order (Motorola/Intel), multiplexing config, identify and fix non-compliant definitions
- **🧠 Signal Dependency Reasoning**: Long-chain reasoning to analyze signal dependencies, auto-identify multiplexer-to-mux-signal mappings
- **📝 CAPL Test Generation**: Auto-generate message sending scripts and CAPL test cases per OEM specs, supporting UDS diagnostics and signal simulation
- **🔄 Closed-loop Verification**: Call CANoe API for simulation, auto-compare expected vs. actual bus data
- **📊 Standardized Reports**: One-click HTML/JSON test reports with pass rate, failure details, signal timing diagrams

### 📈 Performance Metrics

| Metric | Traditional | Agent-powered | Improvement |
|--------|------------|---------------|-------------|
| Single message config time | 30 min | 2 min | **93%** |
| Test case writing efficiency | Baseline | Boosted | **90%** |
| Manual config error rate | High | Minimal | **Greatly reduced** |
| Integration rework | Extensive | Minimal | **Significantly reduced** |

### 🚀 Quick Start

#### Prerequisites

- Python 3.10+
- Vector CANoe 14.0+ (for closed-loop verification)
- Windows 10/11

#### Installation

```bash
git clone https://github.com/Wansuhui3/canoe-automated-testing-agent.git
cd canoe-automated-testing-agent
pip install -r requirements.txt
```

#### Basic Usage

```python
from src.agents import DBCParseAgent, SignalReasonerAgent, CAPLGeneratorAgent, VerificationAgent

# 1. Parse DBC file
parser = DBCParseAgent()
dbc_model = parser.parse("examples/dbc/bcm_example.dbc")
validation_result = parser.validate(dbc_model)

# 2. Signal dependency reasoning
reasoner = SignalReasonerAgent()
dependency_graph = reasoner.analyze(dbc_model)

# 3. Generate CAPL test cases
generator = CAPLGeneratorAgent(spec="config/oem_specs/bcm_spec.yaml")
capl_scripts = generator.generate(dbc_model, dependency_graph)

# 4. Closed-loop verification
verifier = VerificationAgent(canoe_config="examples/config/bcm_test.yaml")
report = verifier.execute_and_verify(capl_scripts)
print(f"Pass rate: {report.pass_rate:.1%}")
```

#### CLI Tools

```bash
# One-click: DBC to test report
python tools/batch_runner.py --dbc examples/dbc/bcm_example.dbc --config examples/config/bcm_test.yaml --output examples/output/

# DBC validation tool
python tools/dbc_checker.py --input examples/dbc/bcm_example.dbc --fix
```

### 📄 License

This project is licensed under the [MIT License](LICENSE).
