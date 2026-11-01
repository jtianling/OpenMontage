---
name: openmontage
description: Produce videos from a brief or supplied footage using scene planning, platform image/video/speech/music generation, local editing, and MP4 rendering. Use for explainers, promos, narrated visual stories, and footage edits.
---

# OpenMontage

把文字需求或用户素材制作为有分镜, 配音, 视觉素材和配乐的视频.  保留 OpenMontage 的创意规划, 镜头意图和成片复核方法, 使用 monkeys 的媒体工具与 video-base 本地渲染.

读取 [平台媒体约定](references/platform.md).  每个任务先确认交付目标, 再读 [制作流程](references/production.md).  使用模板或动态图形时另读 [Remotion](references/remotion.md).  所有相对 skill 路径均相对于本文件所在目录, 脚本用其真实绝对路径执行, 工作目录保持当前任务工作区.

先执行 `python3 <skill>/scripts/openmontage.py preflight`.  不在只读 skill 内写项目, 不安装依赖, 下载模型或读取环境凭据.  缺少命令或编码器时报告原始错误和缺项, 不切换供应商 API.

在当前任务工作区创建新项目:

```bash
python3 <skill>/scripts/openmontage.py init film
```

使用四个真实对话工具, 每个任务只生成所需素材:

| 素材 | 工具 |
| --- | --- |
| 图片, 插画, 背景 | `image_generate` |
| 分镜视频 | `video_generate` |
| 分场景配音 | `text_to_speech` |
| 背景配乐 | `music_generate` |

工具参数以当轮 schema 为准.  它们不是 shell 命令, 本 skill 不提供 HTTP 代理.  等待真实成功终态, 核对结果的 localPath 可读后再导入.  不猜路径, 不把 pending 当成功, 不为失败或超时盲目重做付费请求.

将完成的单个结果归一化为内部导入回执, 例如 image-receipt.json:

```json
{"id":"opening","tool":"image_generate","status":"completed","localPath":"actual-output.png"}
```

这是本地导入 schema, 不是供应商或平台工具的原始响应格式.  localPath 必须来自真实成功结果, 绝不能用示例名代替.  用户附件用 tool=user, 同样必须存在且通过文件检查.  回执和源文件都放在任务工作区内, 导入操作串行执行.

```bash
python3 <skill>/scripts/openmontage.py import-media film --receipt image-receipt.json
```

导入会检查媒体类型, 时长和哈希, 复制到项目 assets 并写 assets.json.  同 id 的不同素材拒绝覆盖.  配音逐段生成并实测时长, 据此排场景, 不用估计字速冒充时间戳.

按 [制作流程](references/production.md) 写 film/timeline.json, 合成并运行技术检查:

```bash
python3 <skill>/scripts/openmontage.py render film
```

成片是 film/renders/final.mp4, 技术报告与首中末帧位于 film/qa/.  技术通过后还要实际查看抽帧, 核对中文, 构图, 镜头内容与字幕; 配音内容需实际检查, 不将自动报告当成内容审核已通过.  需要修改时保留首版, 使用新的输出文件名和版本目录.

最终使用当前平台文件交付工具的真实 schema 与路径交付 MP4.  有需要时一并交付字幕, 源码和报告.  不将 localhost 或沙箱绝对路径当公开下载链接.  失败时如实交付已有文件和具体诊断, 不把源码生成或工具调用成功称为成片完成.
