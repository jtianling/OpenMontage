# OpenMontage 平台版

这是 monkeys 平台适配 fork.  功能入口是 `skills/openmontage/SKILL.md`, 运行代码和素材均包含在该 skill 目录内.  修改前检查工作区, 保留不属于当前任务的变更.

生成媒体使用当前对话真实提供的 `image_generate`, `text_to_speech`, `video_generate`, `music_generate`.  不实现供应商直连, 凭据加载, 云 GPU 部署或外部宿主安装逻辑.  不读取 `.env` 或 `.env.*` 内容.

新增代码与日志标点使用英文, 新增说明使用中文和英文标点.  默认私有接入, 不自动提审.  保留上游作者归属, AGPL 和随附字体许可证.

验证使用 `tests/test_platform.py` 的定向用例和本地媒体 E2E, 不调用付费生成服务.  不操作 tmux, 不运行与任务无关的全量测试或清理命令.
