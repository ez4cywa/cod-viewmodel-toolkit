# CAST 导入后端改进与集成研究

> 这是实施前的 3.4.3 研究快照，文中的“当前”和“建议”指该阶段。
> 已完成的 3.5.0 改进与验证见[发布说明](RELEASE_NOTES_3.5.0.md)和
> [实测记录](CAST_BACKEND_BENCHMARK.md)；下文保留原始判断供追溯。

核对日期：2026-09-24。范围：本项目 3.4.3 的 Maya CAST 后端；Blender 仅对照相关上游变化与加载方式。本轮只研究源码与官方资料，不修改运行代码、不重新测量性能、不更新本机安装或发布版本。

## 结论

**可以继续改进，并且项目已经集成了修改版 CAST，并不是要从零集成。** 建议下一步先把现有修改版整理成工具包专用、版本明确的后端，再依据实际分阶段测量优化热点。保留上游序列化库与格式兼容，不重写 `.cast` 解析器，不先做全量 C++ 重写。

下文将可核查事实标为“事实”，设计判断标为“建议/推断”，没有运行证明的部分标为“待验证”。此前 18.1% 是特定模型在 3.4.2 → 3.4.3 的完整检查、导入、挂载耗时下降，不是本轮的新测量，更不是下一轮的性能承诺。[已有测量记录](CAST_IMPORT_OPTIMIZATION.md)

## 1. 当前已经具备的能力

**事实：** `third_party/cast` 固定在上游 v2.00 / `a8ca18a0acf3b97b19332c53b54b47fcc3217755`。`cast.py` 保持上游原样；`castplugin.py` 有十项本地补丁，包括 batch 跳过 UI、调用级选项与恢复、名字规范化、蒙皮批量写入、几何缓冲区准备、单次挂载解析复用。发布包把两个运行文件放到工具包 `plug-ins` 中，同时保留许可证与补丁记录。[本地补丁清单](../third_party/cast/PATCHES.md)、[3.4.3 发布说明](RELEASE_NOTES_3.4.3.md)

**事实：** 网格已经通过 `MFnMesh` 创建，动画已经使用 `MFnAnimCurve.addKeys`，蒙皮已经通过 API 2.0 `MFnSkinCluster.setWeights` 分块写入。不能把“改用这些批量 API”再次当成尚未实现的优化。创建初始 skinCluster 仍调用 `cmds.skinCluster`，当前记录明确没有关闭自动初始绑定、材质、校验、撤销或场景求值来换速度。[当前导入实现](../third_party/cast/castplugin.py)、[性能边界](CAST_IMPORT_OPTIMIZATION.md)

**事实：** 现有工具包会优先接受 Maya 已经加载的 `castplugin`；模块加载还会查看公共 `sys.modules`，必要时向 `sys.path` 注入目录，并用公共名字 `castplugin` 加载。batch 另有工具包代为注册 `Cast` translator 的兼容路径。因此“发布包带了新版本”并不等于“所有启动顺序都必定执行该版本”。这是源码可见的集成边界，不是已复现的用户故障。[`ensure_cast_plugin`、`_load_castplugin_module`、`_register_batch_cast_translator`](../plug-ins/viewmodel_weapon_toolkit.py)

**静态审计事实：** 单持动画拖放路径有四处可达解析：`_cast_content_counts` 检查内容、`_set_scene_framerate_from_animation` 读取帧率、translator 实际导入、`_cast_animation_inventory` 导入后查询轨道。其中三个工具包读取函数直接调用 `Cast.load`，并未统一进入模型挂载的只读解析复用接口。因此动画解析复用是具体候选；“四处”是源码调用链结论，不是本轮运行计数，也不表示动画大部分耗时都在解析。[工具包动画路径](../plug-ins/viewmodel_weapon_toolkit.py)、[translator 导入实现](../third_party/cast/castplugin.py)

## 2. 上游版本核对

**事实：** 查询时，上游最新发布为 **v2.01**，发布时间 2026-09-16；`master` 与 v2.01 均指向 `363cb39c0425844e29bf4c2457bbbb1d2b9bb4c6`。相对本项目 v2.00 基线前进七个提交。最新状态会变化，以下固定提交链接用于复核。[v2.01 发布页](https://github.com/dtzxporter/cast/releases/tag/v2.01)、[固定提交](https://github.com/dtzxporter/cast/commit/363cb39c0425844e29bf4c2457bbbb1d2b9bb4c6)、[官方比较数据](https://api.github.com/repos/dtzxporter/cast/compare/a8ca18a0acf3b97b19332c53b54b47fcc3217755...363cb39c0425844e29bf4c2457bbbb1d2b9bb4c6)

| 上游变化 | 对本项目的意义 |
| --- | --- |
| Maya 骨架导出父关系修复：读取真实父 DAG，用完整路径匹配父索引 | 值得优先选择性合并并补导出层级回归；属于正确性修复，不是 Maya 导入提速 |
| Blender 动画导入改用已有帧、相邻反向四元数翻转与线性曲线 | 有性能相关改动，但更改了插值处理，不能作为 Maya 无损加速方案直接搬用 |
| Blender 根变换导出、默认 Z 轴、单骨架自动选择等 | 独立于本次 Maya 集成，应单独验证 Blender 行为 |
| `libraries/python/cast.py` 没有变化 | 暂无证据说明升级序列化库本身会改善本项目导入速度 |

表中事实来自[完整提交比较](https://api.github.com/repos/dtzxporter/cast/compare/a8ca18a0acf3b97b19332c53b54b47fcc3217755...363cb39c0425844e29bf4c2457bbbb1d2b9bb4c6)、[Maya 父关系修复](https://github.com/dtzxporter/cast/commit/02a759082b22e278ba8cc2aff4df9169bdfb2195)、[Blender 动画提交](https://github.com/dtzxporter/cast/commit/7d56cb0bf3bca70221b88e6bec7036db7e846694)。

**建议：** 不直接用上游 ZIP 覆盖本地导入器。可以保留 v2.00 补丁分支并移植特定修复，或重基到 v2.01 后重新应用十项补丁；两条路线都要更新补丁清单、固定提交、校验值和回归记录。父关系修复仍不能替代“同名骨骼是否被去重”的独立验证。

## 3. 再分发条件

**事实，限于源码许可证文本：** 上游采用 MIT License，允许修改、合并、发布及再分发；副本或实质部分须包含原版权及许可声明。项目现有 `third_party/cast/LICENSE` 与补丁记录符合继续维护修改版的组织方式。此处只是核对许可证文字，不作额外法律判断。[上游固定版本许可证](https://github.com/dtzxporter/cast/blob/363cb39c0425844e29bf4c2457bbbb1d2b9bb4c6/LICENSE)、[本地许可证](../third_party/cast/LICENSE)

**建议：** 继续标记“基于上游、项目维护的修改版”，保存源码来源、基线和每项补丁，发布包保留原 LICENSE。不要把项目修改版描述成上游官方构建；不要带入用户个人 `cast.cfg`。

## 4. 推荐的集成边界

**建议，不是现有实现：** 工具包持有一个私有 CAST 后端；Maya 文件 translator、工具包按钮、动画拖放和 batch 入口只负责传参、调用后端、展示错误。它们共用解析、导入、导出和校验逻辑，不复制四套实现。

**项目已有先例：** Blender 的 `backend.py` 已在插件包私有命名空间加载固定 CAST 实现，不执行上游 `register()`、不抢占独立插件的同名导入导出 operator；可借用隔离思路，但 Maya 的 translator 注册与生命周期需要独立实现和验证。[Blender 后端适配器](../blender/cod_viewmodel_toolkit/backend.py)

```text
工具包按钮 ─────┐
动画拖放 ───────┼─> 工具包私有 CAST 后端 ─> 上游 cast.py + Maya 主线程写场景
独立 translator ┤       ↑
batch 命令 ─────┘   明确的 options / session / 目标节点映射
```

建议约束如下：

1. 后端模块使用项目私有名字与固定路径，不依赖全局 `import cast` / `import castplugin` 是否已被别的插件占用；私有化不等于改写序列化协议。
2. 工具包显式选择自己的 translator/backend。若保留用户独立安装的原版 Cast，使用互不冲突的注册名，分别持有自己的注册与配置，不强制卸载对方、不删除对方菜单、不覆盖对方 `cast.cfg`。双 translator 对同一扩展名的普通文件打开/拖放选择需要实测，不能只靠扩展名注册保证路由。
3. 使用操作级 options 与 context。临时导入器选项等应在 `finally` 恢复；成功导入需要保留的新帧率、播放范围和新建场景内容是操作结果，不能一概回滚。失败和取消另按既有事务约定回滚。解析缓存只跨同一次操作，不长期持有可变场景对象；取消、失败、嵌套操作均走清理路径。
4. GUI 提供进度与错误展示；batch 不创建 UI。成功继续保持安静，不恢复此前已取消的挂载成功弹窗。
5. 可回滚到现有已验证路径，但回退应写明实际后端版本与原因，避免静默切换后性能结果和行为不可解释。

**官方 API 依据：** `MPxFileTranslator` 是第三方文件读写的注册入口，`reader` / `writer` 由 Maya 调用并负责创建或导出场景对象；`MFnPlugin` 提供配套注册/注销；加载和卸载的入口应对称处理本插件注册的能力。由此可以保留标准文件导入能力，把实现移到可共享后端，不必将导入器揉成一个巨大脚本。[MPxFileTranslator](https://help.autodesk.com/cloudhelp/2027/ENU/MAYA-API-REF/cpp_ref/class_m_px_file_translator.html)、[MFnPlugin](https://help.autodesk.com/cloudhelp/2027/ENU/MAYA-API-REF/cpp_ref/class_m_fn_plugin.html)、[插件生命周期](https://help.autodesk.com/cloudhelp/2022/ENU/Maya-SDK/Maya-API-introduction/initialize-uninitialize.html)

## 5. 可优化点与不能越过的边界

| 优先级 | 工作 | 性质及验收重点 |
| --- | --- | --- |
| P0 | 明确后端来源、能力与私有模块加载 | 首先改善版本可控性和可维护性；不承诺因此提速。验证两种 Cast 加载顺序、反复加载卸载、旧版已加载、无 `__file__`、异常回收 |
| P0 | 选择性合并 v2.01 Maya 父关系修复 | 正确性改进；验证多层骨架、根骨骼、非 joint 父节点、命名空间和 CAST 导出再导入 |
| P1 | 分段 profile：解析、校验、网格/UV、材质、初始绑定、写权重、动画、挂载 | 先确定剩余耗时占比。分别报告纯导入与完整挂载，不把启动/导出混入，不只测单一模型 |
| P1 | 动画只读解析复用，再统一 GUI/batch 调用入口 | 验证实际 `Cast.load` 次数下降、帧率与轨道检查结果不变、文件变化失效和异常释放；避免长期缓存。统一入口首先用于消除两种执行路径的版本与状态差异 |
| P1 | 动画目标节点、plug、休止变换的操作级缓存；显式目标映射 | 是待测候选，不是已证明热点。减少重复查找，并逐步摆脱临时重命名路由；验证单持/双持、重名、命名空间、相对/绝对/叠加曲线 |
| P1 | 材质/拓扑处理和初始 skinCluster 绑定优化 | 仅在 profile 证明值得时做；保留材质分配、纹理、UV 拆分、法线、权重、bind 状态、DQS，不通过删功能制造收益 |
| P2 | 局部 Maya Python API 2.0 迁移 | 选择对象转换开销确实显著的模块；既有 API 1.0/2.0 对象不能混传。保留薄 translator，不为了迁移而全量重写 |
| P3 | 独立 C++ 热点或纯数据处理并行 | 只有局部 Python/API 优化后仍有明确 CPU 热点才评估；单独计算构建、分发、版本维护成本 |

推荐主线顺序：确定性私有后端/来源能力 → 动画只读解析复用 → GUI/batch 统一 → 显式目标节点映射。上游正确性补丁可独立评估，不必把所有候选捆成一次大重写。

### 蒙皮

**事实：** `MFnSkinCluster.setWeights` 支持多 component、多 influence 批量写入。influence 参数使用 `influenceObjects()` 顺序对应的 **physical index**，不是 `indexForInfluenceObject()` 返回的 logical index；权重数组按 component 为主序排列，`normalize` 可明确关闭。单个 skinCluster 只作用于一份几何，不能简单把多网格合在同一个 cluster 调用中。[Maya 2027 MFnSkinCluster C++ 说明](https://help.autodesk.com/cloudhelp/2027/ENU/MAYA-API-REF/cpp_ref/class_m_fn_skin_cluster.html)、[Python API 2.0 说明](https://help.autodesk.com/cloudhelp/2027/ENU/MAYA-API-REF/py_ref/class_open_maya_anim_1_1_m_fn_skin_cluster.html)

**事实：** CAST 规范要求重复骨骼权重相加、不要假定权重已归一化，并用 `sm = quaternion` 表示 DQS。当前分块写入已经保留重复槽累加、实际 influence 映射及不归一化行为；进一步提速不能丢弃这些条件。[上游格式规范](https://github.com/dtzxporter/cast/blob/363cb39c0425844e29bf4c2457bbbb1d2b9bb4c6/README.md#mesh)、[本地蒙皮补丁](../third_party/cast/PATCHES.md)

**待验证：** 跳过 Maya 初始自动算权重是否确有收益，以及能否完整建立 influence 连接、`bindPreMatrix`、几何连接和绑定状态；不能只凭导入后的静态外观判断正确。批量写入已存在，下一步应先量出初始绑定与最终写权重各自花多少时间。

### 线程、GUI 与 batch

**事实：** Autodesk 明确说明 Maya commands/API 架构不是通用线程安全接口。`executeInMainThreadWithResult` 可把工作交回主线程，但依赖 idle 事件，不适用于 batch。[Autodesk Python and threading](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Scripting/files/GUID-9B5AECBB-B212-4C92-959A-22599760E91A.htm)

**建议/推断：** 可以评估把不接触 Maya 对象的读文件、解析或纯数据准备移出 UI 工作段；不能让多个 Python 线程同时创建网格、关节、skinCluster 或改场景。batch 应同步执行主线程场景写入，不靠等待 GUI idle。后台读取还需确认上游解析器对象/哈希状态的隔离、传输开销及取消行为；“异步更顺畅”与“总耗时更短”应分别测量。

### API 2.0 与 C++

**事实：** Autodesk 将 Python API 2.0 定位为更 Python 化、一般更高效的接口，但 API 1.0 与 2.0 对象不可互换。因此当前局部用 API 2.0 写蒙皮、其他位置用 API 1.0 并不自动构成问题，前提是模块边界重新取得正确类型的对象。[Maya 2027 Python API 2.0 总览](https://help.autodesk.com/cloudhelp/2027/ENU/MAYA-API-REF/py_ref/)

**事实：** C++ Maya 插件涉及对应平台和 Maya 版本的构建；Python 插件在所用 API 保持兼容时可跨版本。官方通用性能描述不是本项目 CAST 文件上的基准，不能据此承诺若干倍提速。[Autodesk C++ versus Python plug-ins](https://help.autodesk.com/cloudhelp/2017/ENU/Maya-SDK/files/API_Introduction.htm)

**建议：** 优先隔离可替换的小热点，而非把整个导入器迁移到 C++。如果主要时间在 Maya 自身创建/绑定节点，换语言不会自动消除同一批 Maya 内部工作；本项目上的收益仍待 profile 和原型对照证明。

## 6. 实施后的验收条件

以下是建议的验收合同，不表示本轮已执行：

- **身份与生命周期：** GUI、mayapy/batch、注册插件的无 `__file__` 环境都能加载；独立原版 Cast 和工具包不同加载顺序下使用预期后端；反复卸载重载无遗留 callback/菜单；用户 `cast.cfg` 不变。
- **输出等价：** 用当前用户手臂/武器样本，加多网格、缺失可选 UV、重复 influence、非归一化权重、刚性网格、命名冲突和损坏输入样本，对照网格拓扑、位置、法线与索引、全部 UV/颜色、材质/纹理、骨骼层级与变换、权重及 DQS。性能计时外执行快照比较。
- **动画与挂载：** 单持/双持、拖放回调、手动导入、绝对/相对/叠加、四元数跨半球和稀疏关键帧；检查逐帧结果，不能只数关键帧。保持武器挂载局部平移归零的现有约定。
- **失败行为：** 出错仍报告具体文件/节点；取消与异常后释放操作缓存并恢复临时选项、选择等约定状态；成功导入预期改变的帧率/播放范围仍保留，不因通用清理被恢复成旧值；失败场景按既有事务约定回滚，不留半成品导入造成下一次行为改变。成功不弹挂载完成确认。
- **性能：** 以 3.4.3 为固定基线，在同一 Maya、相同模型、交替运行顺序下测多次；分别记录纯导入、完整挂载、峰值内存和各阶段耗时，报告中位数及样本范围。没有改善则不宣称提速；降低阻塞但不降低总耗时则明确区分。
- **发布：** 更新来源/补丁记录与完整性校验，运行现有 CAST、动画、批导出、打包回归；只有另行进入实施与发布任务时才更新 GitHub 与本机。

## 7. 本轮未证明的内容

没有运行新的 Maya 性能测试，没有确定材质、初始绑定或动画查找一定是剩余主瓶颈；没有声称现有项目已具备私有后端、已合并 v2.01 或已解决所有同名骨骼情况。`CONTRIBUTING.md` 仍提及旧 v1.99，与实际 v2.00 补丁记录不同；后续实施时应同步该文档，不能按过期文字覆盖当前依赖。
