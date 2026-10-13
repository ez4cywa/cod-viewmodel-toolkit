# 3.5.1 — Metric export compatibility and reliable release builds

Maya 的米制导出统一定位实际核心实现文件，兼容 Maya 插件加载器未提供
`__file__` 或 `__name__` 的情况，并区分英文实现与中文、旧版注册入口。导出使用
实际注册核心的函数和数据类型，worker 不再重复导入核心。依赖路径在分配输出和
写入场景快照前验证。既有单位换算、骨骼映射、DQS 行为和输出目录规则保持兼容。

发布构建先验证所有源文件、入口版本、面板标题和中文转换结果，再生成完整安装包。
构建失败时清理本次创建的产物；已有安装包保持原样。共用发布文档只维护一份清单，
各平台继续使用明确的文件白名单。CLI 和 `build(output, blender_zh_only=False)`
调用方式保持兼容。

版本检查使用明确异常，在 `python -O` 下仍生效。中文生成器检查特殊转换的匹配
次数，源码变化导致转换失效时会报告具体问题。

GitHub Actions 新增普通 Python 可运行的发布构建回归，并检查全部 Maya 运行文件
的 Python 3.7 语法。宿主运行仍单独验证；语法通过不等于完成 Maya 2022 实机测试。
发布过程见 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)。

## 安装

下载 Maya 或 Blender 对应的英文、简体中文 ZIP。Maya 升级前关闭宿主，复制完整
`plug-ins` 目录内容，包括 `cod_viewmodel_cast` 子目录。Blender 从磁盘安装 ZIP；
中英文版本共用模块，切换前禁用旧版。详见 [Maya 指南](MAYA.zh-CN.md)及
[Blender 指南](BLENDER.zh-CN.md)。

本版保留 Maya CAST 2.01 和 Blender CAST 2.00 后端，不包含新的导入性能测量。
3.5.0 的性能结果仍见 [CAST_BACKEND_BENCHMARK.md](CAST_BACKEND_BENCHMARK.md)。

## 验证

2026-10-13 已通过的本机验证：

- Python 3.14：53 个源码文件语法检查、全部 7 个 Maya 运行文件的 Python 3.7
  语法检查、两种 CAST 后端完整性、17 项发布构建与中文转换回归。
- Maya 2027 / Python 3.13.9：英文、中文、旧版入口的静态及动画米制导出，
  共 6 个真实 worker；使用实际注册核心，源场景完整快照一致，MA/CAST 中
  `10 ft → 3.048 m`。依赖路径错误发生在输出分配/快照前，米制状态在异常后恢复。
- 既有米制回归：MA/FBX/CAST、双持、重复导出、米制场景重开及不重复缩放。
- Maya 中英文、Blender 中英文四个安装包分别通过 Maya 2027、Blender 5.2.1 LTS
  的隔离配置验收，包含安装、组装、动画及输出检查。

GitHub Actions 为 Python 3.11、3.14 分别运行源码和构建回归；远端结果在
仓库 Actions 页面查看。

本轮验证采用后台宿主，不新增人工 GUI 交互验收。
