# Maya Viewmodel Weapon Toolkit 3.2.0

## English

Updated the bundled CAST translator to upstream v2.00 with the toolkit's
batch-mode, UV fallback, and per-call option patches. Model preflight and
animation routing now use consistent normalized names; ambiguous naming
collisions are rejected before importing. Source checkouts also prefer the
bundled translator when CAST is not already loaded.

The English and Simplified Chinese interfaces group source files, joint
mapping, output files, and scene tools. Forms resize and scroll while primary
actions remain visible. Controls have descriptive accessible names, keyboard
focus indicators, larger targets, wrapping labels, and a clear empty queue.
Unselected format folders are disabled while retaining their saved values.

Single-frame export, DQS, dual animation composition, reference-pose
compensation, and existing commands/preferences remain supported.

## 简体中文

内置 CAST 升级到上游 v2.00，保留本项目的 Batch、缺失 UV 容错和单次操作选项
补丁。模型预检与动画路由使用一致的名称清理规则；名称清理后发生冲突时，
会在导入前明确报错。直接运行源码时也会优先查找项目内置的 CAST。

中英文界面按输入文件、关节映射、输出文件和场景工具分组。窗口支持缩放与滚动，
主要操作保持可见。增加了描述性可访问名称、键盘焦点提示、更大的控件、换行标签
和队列空状态。未勾选格式的目录控件会禁用，但保留已填写的值。

继续支持单帧导出、DQS、双持动画组合、参考姿态补偿及现有命令与偏好设置。

## Installation

Install either the English or Simplified Chinese package. Load only one
toolkit entry point at a time. See the included README for Maya installation.

Maya 2022+ in Python 3 mode remains the expected minimum; runtime verification
targets Maya 2025 for Windows.
