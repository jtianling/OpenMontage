# Remotion 场景与渲染

需要标题动画, 图表, 字幕覆盖或定制动态图形时使用 Remotion.  原 OpenMontage 场景源码包含在 remotion-composer/src, 类型说明见 remotion-composer/SCENE_TYPES.md.  脚本和源码均随同本 skill 装载, 不需要在线克隆另一个仓库.

从任务工作区执行:

```bash
node <skill>/scripts/remotion.mjs init motion-film
node <skill>/scripts/remotion.mjs compositions motion-film
```

init 调用已安装的 monkeys-video-init 创建新工程, 检查项目的 remotion, @remotion/cli 和 @remotion/media-utils 同版本, 保留平台生成的浏览器与 CPU 并发配置, 再复制原场景源码.  不覆盖已有项目, 不执行 npm 或 npx.  缺模板, 包, 浏览器或 compositor 时报告具体错误, 不自动下载安装.

工程内自写 composition 或按真实 TypeScript 类型组织 props.  不虚构不存在的组件字段.  素材复制到工程 public/assets, 使用 staticFile 或本地相对 URL, 不把沙箱绝对路径作为浏览器素材 URL.  原场景库已带本地西文字体与 OFL; 中文用沙箱本地字体, 明确加载后实测中文和粗体, 不默认请求在线字体.

示例命令中的 composition ID 与 props 必须替换为项目实际注册值:

```bash
node <skill>/scripts/remotion.mjs still motion-film Explainer preview.png --props=props.json
node <skill>/scripts/remotion.mjs render motion-film Explainer final.mp4 --props=props.json
```

需要字幕时使用用户提供或真实转录的时间戳.  段级 TTS 只能产生段级字幕依据, 不把等分字数称为词级识别.  不使用外部语音识别服务或下载本地 ASR 模型.

原示例 Root 中的默认内容只是组件演示, 正式渲染要使用本次内容和真实素材.  仓库依赖清单记录源项目需求, 不代表沙箱所有包都存在.  商用许可及运行时依赖由平台维护, 不向终端用户索取 license key.

原生渲染后同样执行 FFprobe, 完整解码, 分别核对音视频时长并查看关键帧.  可以为同样时长和画幅写 timeline.json, 用 openmontage.py verify 和明确的 --output 路径生成技术报告.  没有交互预览代理时继续交付离线 MP4, 不提供无效 localhost 链接.
