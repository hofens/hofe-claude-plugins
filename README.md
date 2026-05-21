# hofe-claude-plugins

> Personal Claude Code plugins — work report generation and more

**作者**: hofens <hofe.cn@gmail.com>

**仓库**: https://github.com/hofens/hofe-claude-plugins

## 安装

```bash
# 添加市场
claude plugin marketplace add https://github.com/hofens/hofe-claude-plugins.git

# 安装插件
claude plugin install <plugin-name>@hofe-claude-plugins
```

---

## 已发布插件

### [work-report](plugins/work-report/)

**类别**: productivity

**作者**: hofens

Generate daily/weekly/monthly work reports from git commits and Claude session history. Supports Chinese (日报/周报/月报) output.

**安装**:
```bash
claude plugin install work-report@hofe-claude-plugins
```

**用法**:
- `/report` — Generate daily/weekly/monthly work reports from git commits and Claude session history

---

## 开发

首次克隆后安装 pre-commit hook（自动更新 README）：
```bash
cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## 添加新插件

1. 在 `plugins/` 下创建插件目录，包含 `.claude-plugin/plugin.json` 和 agents/skills
2. 在 `.claude-plugin/marketplace.json` 的 `plugins` 数组中添加条目
3. 运行 `python3 scripts/update-readme.py` 更新本文件
4. `claude plugin validate plugins/<name>` 校验
5. `claude plugin tag plugins/<name>` 打版本标签
6. `git push --tags` 推送

