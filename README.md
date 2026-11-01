# OpenMontage for monkeys

将文字需求, 用户素材和平台生成媒体制作成视频.  本 fork 保留 OpenMontage 的分镜规划方法, 本地创作检查库与 Remotion 场景组件, 将媒体生成接到 monkeys 的文生图, TTS, 文生视频和音乐工具.

平台加载入口为 [openmontage](skills/openmontage/SKILL.md).  该目录独立包含脚本, 说明, 原版场景源码与许可证, 不依赖仓库外工具目录.  使用 video-base 沙箱和四个托管工具.  新 agent 使用 private, 不自动提审.

已移除供应商 API 客户端, Key 与环境文件加载, 云 GPU 部署, OpenClaw 固定路径及其他旧宿主集成.  本地 FFmpeg 路线仅需 Python 3.11+ 标准库及已安装的 FFmpeg/FFprobe; Remotion 路线另需平台模板及匹配依赖.  任务中不安装包或下载模型.

自动 ASR, 数字人, 云素材库和 GPU 模型不属于本版能力; 用户可以提供已有字幕和参考素材.  合成夹具不能证明平台生成成功; agent 配置成功也不能证明已实际出片.  适配范围及验证状态见 [适配记录](docs/monkeys-platform.md).

原项目: [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage).  原始源码保留 GNU AGPLv3, 字体保留各自 OFL.  修改后的对应源码位于本仓库, 商业部署同时遵守所用 Remotion 及其他依赖的适用许可.
