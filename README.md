# Tool Agent（项目①：工具型 Agent）

手写 ReAct 循环 + Function Calling 的工具型 Agent，不依赖任何框架。

> 状态：🚧 W4 启动（2026-08-28）。本 README 随项目推进补全。

## 目标

- 输入自然语言任务，Agent 自主决定调用哪些工具、多轮调用、最终给出回答
- 5 个工具：计算器、当前时间、天气、搜索、文档读取（按实际进度调整）
- 亮点：工具错误容错、最大迭代次数保护、每一步 trace 打印

## 技术栈

- Python + httpx（直调 DeepSeek function calling）
- 手写 Agent 循环（不用 LangGraph，先懂本质）

## 快速开始

（待补：venv → pip install → .env 配置 → 运行）
