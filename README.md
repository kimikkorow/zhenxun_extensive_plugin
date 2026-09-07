# 真寻的扩展插件库

<p>
  <a href="https://www.oscs1024.com/cd/1535499661232435200?sign=e9655203">
    <img src="https://www.oscs1024.com/platform/badge/CRAZYShimakaze/zhenxun_extensive_plugin.svg">
  </a>

  <a href="https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin">
    <img src="https://badgen.net/badge/Github/CRAZYShimakaze/zhenxun_extensive_plugin?icon=github">
  </a>

  <img src="https://img.shields.io/badge/-Python3.9-3776AB?style=flat-square">
  <a href="https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/LICENSE">
    <img alt="GitHub" src="https://img.shields.io/github/license/CRAZYShimakaze/zhenxun_extensive_plugin?style=flat-square">
  </a>
  <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/CRAZYShimakaze/zhenxun_extensive_plugin?style=flat-square">
  <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/CRAZYShimakaze/zhenxun_extensive_plugin?style=flat-square">
</p>

适用于真寻的扩展插件库。仓库根目录对应真寻的 `zhenxun/plugins` 目录，每个顶层目录通常是一个可单独加载的插件。

第三方插件交流群：217496217

## 仓库结构

本仓库维护通用插件、共享工具以及攻略类插件，主要目录包括：

- `plugin_utils`：多个插件共用的工具代码
- `genshin_recommend`：原神攻略
- `starrail_recommend`：星铁攻略
- `zenlesszonezero_recommend`：绝区零攻略
- 其他插件目录：按需安装，具体用法以目录内 README 为准

原神、星铁和绝区零这三个角色面板插件已迁移至以下独立仓库，`plugins` 仓库不再包含它们：

| 插件 | 独立仓库 | 安装目录 |
| --- | --- | --- |
| 原神角色面板 | [zhenxun_plugin_genshin_role_info](https://github.com/CRAZYShimakaze/zhenxun_plugin_genshin_role_info) | `genshin_role_info` |
| 星铁角色面板 | [zhenxun_plugin_starrail_role_info](https://github.com/CRAZYShimakaze/zhenxun_plugin_starrail_role_info) | `starrail_role_info` |
| 绝区零角色面板 | [zhenxun_plugin_zenlesszonezero_role_info](https://github.com/CRAZYShimakaze/zhenxun_plugin_zenlesszonezero_role_info) | `zenlesszonezero_role_info` |

迁移后的三个插件仍应与本仓库的 `plugin_utils` 保持同级目录。它们可以直接放在同一个 `zhenxun/plugins` 目录中，但需要分别使用各自仓库进行安装和更新。

## 插件列表

以下为仍由本仓库维护的插件；已迁移的三个角色面板插件见上方的独立仓库列表。

- [金币转账](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/gold_trans)
- [验车](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/whatslink)
- [星铁攻略](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/starrail_recommend)
- [绝区零攻略](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/zenlesszonezero_recommend)
- [网页截图](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/call)
- [入群检测](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/join_group_check)
- [Chatgpt](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/chatgpt)
- [昵称检测](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/nickname_check)
- [插件管理](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/plugin_manager)
- [舔狗日记](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/tgrj)
- [图片打分](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/setu_score)
- [成语接龙](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/idiom_salon)
- [24点](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/24_point)
- [21点](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/21_point)
- [打工赚金币版](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/work)
- [原神攻略](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/genshin_recommend)
- [原神角色卡片](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/genshin_role_card)
- [扫雷赚金币版](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/minesweeper)
- [猜成语赚金币版](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/guess_riddle)
- [发涩图](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/setu)
- [洛克王国助手](https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin/tree/main/rocom_helper)

## 安装

### 安装本仓库

将本仓库克隆到真寻项目的 `plugins` 目录：

```bash
cd /path/to/zhenxun
git clone https://github.com/CRAZYShimakaze/zhenxun_extensive_plugin.git plugins
```

如果只安装部分插件，复制对应插件目录即可；依赖共享工具的插件还需要同时保留 `plugin_utils`。

### 安装三个独立角色面板插件

```bash
cd /path/to/zhenxun/plugins
git clone https://github.com/CRAZYShimakaze/zhenxun_plugin_genshin_role_info.git genshin_role_info
git clone https://github.com/CRAZYShimakaze/zhenxun_plugin_starrail_role_info.git starrail_role_info
git clone https://github.com/CRAZYShimakaze/zhenxun_plugin_zenlesszonezero_role_info.git zenlesszonezero_role_info
```

更新时分别进入对应目录执行 `git pull --ff-only`。

安装完成后重启机器人即可加载插件。

## Stargazers over time

[![Stargazers over time](https://starchart.cc/CRAZYShimakaze/zhenxun_extensive_plugin.svg?variant=adaptive)](https://starchart.cc/CRAZYShimakaze/zhenxun_extensive_plugin)
