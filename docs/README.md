# Robotics arXiv Daily

自动汇集具身智能与机器人论文，按研究方向和任务／机器人形态提供交叉索引。

## Topics

这些是本站的自定义专题，**不是 arXiv 官方学科分类**。同一篇论文可以进入多个专题，例如 Agentic Robotics + VLA + Manipulation。

| Research topic | Scope |
| --- | --- |
| Agentic Robotics | 任务规划、代码控制、工具与技能调用、记忆、闭环反馈和错误恢复 |
| VLA and Robot Policies | 视觉语言动作模型、通用机器人策略、Diffusion / Flow Policy |
| Robot RL and Adaptation | 强化学习、后训练、在线适应、自我改进与蒸馏 |
| Embodied Perception and Reasoning | 面向机器人的 VLM、空间推理、可供性与视觉指令落地 |

Manipulation、Humanoid、Dexterous 保留为任务／形态标签。原有 `#vla`、`#vlm`、`#manipulation`、`#humanoid`、`#dexterous` 链接继续有效。

分类由标题、摘要中的关键词自动匹配，是供阅读筛选的候选索引；提到某个方法并不一定意味着该论文的主要贡献属于这个方向。Agent 与 VLA 可以协作，也有 Agent 直接生成控制代码或动作的路线。

## Usage

### Automatic updates

- **Run Arxiv Papers Daily**：每日北京时间 **08:17**（UTC `17 0 * * *`）。修改主分支上的分类配置、抓取代码、依赖、测试或该工作流时，也会触发更新。
- **Run Update Paper Links Weekly**：每周日北京时间 **08:47**（UTC `47 0 * * 0`），重新检查缺失的项目／代码链接。
- 两个工作流都保留 **Run workflow** 手动入口，并共享写锁，避免同时提交生成文件。GitHub 的定时任务可能延迟。

成功抓取后，工作流提交数据并显式请求 GitHub Pages 构建，因为 `GITHUB_TOKEN` 推送本身不会触发基于分支的 Pages 构建。工作流使用仓库自带的令牌（`contents: write` 和 `pages: write`），不需要 LLM API key。

Pages 发布源应为 **Deploy from a branch → main → /docs**。Fork 后请检查 Actions 是否启用，并将工作流和配置中的仓库用户名改为自己的账号；`push.branches` 默认是 `main`。

### Fetching and coverage

1. 在 `cs.RO` 中检索；对于 `cs.AI`、`cs.CV`、`cs.LG`、`cs.MA`，额外要求标题或摘要包含机器人／具身相关词。
2. 专题词仅匹配标题和摘要，使用带引号的词组和显式 `AND` / `OR`。收到结果后再次进行本地词组校验，兼容连字符和复数，避免 arXiv 词干搜索将普通 agent 误当作 agentic。
3. 已有专题默认回看 **14 天**，新专题首次回看 **30 天**，自动分页。若距上次成功抓取超过回看窗口，会从上次成功日期前一天补抓。
4. `max_results: 2000` 是每个专题每次查询的保护上限。超过上限会报错，而不会静默截断。
5. 任一专题抓取失败，整次更新报错，不写入部分抓取结果，也不刷新成功时间。
6. 以去掉版本号的 arXiv ID 去重；新抓取行的日期是首次提交日期，修订日期另存于元数据。

历史论文和已知代码链接均保留。旧记录不会因收紧检索范围而自动删除，也不会在这次升级中全部重新分类；尚未重新抓取的历史行可能仍显示旧脚本使用的修订日期。`paper-metadata.json` 从本次升级开始积累，不代表全部历史论文已经补齐摘要。

页面显示的是最近一次**成功抓取论文**的时间。每周补链接和离线重渲染不会将这个时间伪装成一次新的论文抓取。

### Local commands

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python daily_arxiv.py
python daily_arxiv.py --lookback_days 30
python daily_arxiv.py --render_only
python daily_arxiv.py --update_paper_links
```

`--lookback_days` 可以扩大回看范围以补抓。新专题的 `bootstrap_days` 和较早的成功时间仍会扩大实际窗口。若查询超过保护上限，请提高 `max_results`，或同时调整窗口、首次回看天数与状态后分批补抓。

### Configuration and files

- `config.yaml`：`keywords` 的键是稳定专题 ID；`label` 控制显示名称，`group` 控制目录分组，`description` 解释收录范围，`filters` 设置检索词。Agentic Robotics 放在首位。仅抓取和展示配置中的专题；移除专题后保留其历史 JSON 归档，但不再显示栏目或为该专题检索新论文。
- `daily_arxiv.py`：检索、归档和 Markdown 渲染。
- `docs/cv-arxiv-daily.json`、`docs/cv-arxiv-daily-web.json`：保留原来的按专题归档格式，兼容历史记录。
- `docs/paper-metadata.json`：以 arXiv ID 为键保存新抓取论文的标题、摘要、作者、提交／修订时间、官方学科分类、链接、多个本站专题标签和实际匹配词。
- `docs/update-status.json`：最近成功抓取时间、各专题的回看起点和返回篇数。
- `README.md`、`docs/index.md`：生成文件，请通过修改脚本／配置后重新生成。

每周链接更新仅使用论文作者在 arXiv 摘要或评论中公开的地址，优先保留 GitHub 仓库链接，再使用项目页；不会克隆或修改论文代码仓库。

### References

- [arXiv official subject taxonomy](https://arxiv.org/category_taxonomy)
- [arXiv API query syntax](https://info.arxiv.org/help/api/user-manual.html)
- [GitHub Pages publishing sources and automatic-build limitations](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

Based on the original [cv-arxiv-daily](https://github.com/Vincentqyw/cv-arxiv-daily) project and its robotics adaptations.

