# monkeys 平台适配记录

适配日期: 2026-11-01.  基于 calesthio/OpenMontage 的上游提交 195eab24478dc9363326aec437aefc3701635ddf, 在用户指定的 jtianling/OpenMontage fork 中实现.

本版是平台托管媒体生成与本地制作版本.  保留原版 Remotion 场景, 图表, 字幕覆盖, 本地字体及镜头提示词, 画幅, 静态卡片风险和场景变化检查库.  移除供应商 API 客户端, SDK, Key 加载, 云 GPU/本地生成模型部署, 素材服务客户端, 旧宿主入口与对应测试.  旧供应商驱动的流水线不再作为可执行入口, 不宣称保留全部上游功能.

新的独立 skill 位于 skills/openmontage.  所有运行资源均在该目录中, 不依赖仓库根 tools.  四种生成由对话层调用真实 image_generate, text_to_speech, video_generate, music_generate; 脚本只接受成功后的本地文件.  回执严格验证, 路径限制在任务工作区, 素材记录 SHA256, 时间轴按实际文件合成.  不假装存在沙箱到平台工具的 HTTP 代理.

本地验证覆盖待完成回执拒绝, 字段校验, 路径越界和 symlink, 素材篡改, 四类素材合成, 原声/配音长度差异, MP3 封面, GIF 循环, WebM 独立画面流时长和新文件输出.  13 个定向用例在断网容器中全部通过.  不操作 tmux, 不运行被移除的上游全量套件.

实际本机 runtime 镜像 ID 为 sha256:5db7aa275c31f67f2a20d79339d938ba01224a8086d00dc00210408df9a3f89c.  以 docker inspect 解析取得, linux/amd64, 非 root UID 65534, network=none, Python 3.15.1, Node v24.22.1, Remotion 4.0.539.  容器初始化与枚举真实场景通过.  中文标题样例生成 MP4 并查看实际抽帧, 中文显示正常.  图片, 视频, 旁白和音乐本地夹具组合的 Remotion 成片为 H.264/AAC, 480x270, 30fps, 视频流 2 秒/60 帧, 音频 2.005 秒, 完整解码与首中末抽帧通过.  文件 SHA256 为 1bbbfad27ce834de6dceff2758a2920c17bdc26ecfa29ab6905277f1e92408f4.  使用 scale=0.25 验证本地入口, 不作为所有尺寸/复杂度的性能保证.  共享 node_modules 的 webpack 缓存目录不可写产生非阻塞警告, 两次实际出片均完成.

首次本机 tar 命令带入 AppleDouble 元数据, CLI 单 skill 预检正确拒绝.  改用 Python tarfile 打包后通过, 单目录共 66 文件.  平台接入实际使用固定 GitHub commit, 不将这个本地 tar 冒充服务端冻结产物.

上述媒体均为本地合成夹具.  本轮未调用真实平台付费媒体生成, 未执行远程产品 runner 或用户下载链路验收.  配置接入与运行验收分开报告, 不把 private/live 状态当实际生成已通过.  仍须按项目实际目标复核语音内容和视觉质量.

保留 AGPLv3 和随附字体 OFL.  平台正常展示实际 skill 来源, 对应修改源码位于本 fork.  商业使用同时遵守运行依赖的适用许可.
