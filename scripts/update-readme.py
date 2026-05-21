#!/usr/bin/env python3
"""Generate README.md from .claude-plugin/marketplace.json."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_FILE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
README_FILE = REPO_ROOT / "README.md"


def main():
    with open(MARKETPLACE_FILE) as f:
        data = json.load(f)

    name = data["name"]
    desc = data.get("description", "")
    owner = data.get("owner", {})

    lines = [
        f"# {name}",
        "",
        f"> {desc}",
        "",
        f"**作者**: {owner.get('name', '')} <{owner.get('email', '')}>",
        "",
        f"**仓库**: https://github.com/{owner.get('name', '')}/{name}",
        "",
        "## 安装",
        "",
        "```bash",
        f"# 添加市场",
        f"claude plugin marketplace add https://github.com/{owner.get('name', '')}/{name}.git",
        "",
        f"# 安装插件",
        f"claude plugin install <plugin-name>@{name}",
        "```",
        "",
        "---",
        "",
        "## 已发布插件",
        "",
    ]

    for p in data.get("plugins", []):
        pname = p["name"]
        pdesc = p.get("description", "")
        pauthor = p.get("author", {})
        pcat = p.get("category", "")

        lines.extend([
            f"### [{pname}](plugins/{pname}/)",
            "",
            f"**类别**: {pcat}",
            "",
            f"**作者**: {pauthor.get('name', '')}",
            "",
            pdesc,
            "",
            "**安装**:",
            f"```bash",
            f"claude plugin install {pname}@{name}",
            f"```",
            "",
            "**用法**:",
        ])

        # Try to read agent/skill description for usage info
        agents_dir = REPO_ROOT / "plugins" / pname / "agents"
        skills_dir = REPO_ROOT / "plugins" / pname / "skills"
        if agents_dir.exists():
            for agent_file in agents_dir.glob("*.md"):
                frontmatter = parse_frontmatter(agent_file)
                if frontmatter.get("description"):
                    lines.append(f"- `/{frontmatter.get('name', pname)}` — {frontmatter['description']}")
        if skills_dir.exists():
            for skill_file in skills_dir.rglob("SKILL.md"):
                frontmatter = parse_frontmatter(skill_file)
                if frontmatter.get("description"):
                    lines.append(f"- `/{frontmatter.get('name', pname)}` — {frontmatter['description']}")

        lines.append("")

    lines.extend([
        "---",
        "",
        "## 开发",
        "",
        "首次克隆后安装 pre-commit hook（自动更新 README）：",
        "```bash",
        "cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit",
        "```",
        "",
        "## 添加新插件",
        "",
        "1. 在 `plugins/` 下创建插件目录，包含 `.claude-plugin/plugin.json` 和 agents/skills",
        "2. 在 `.claude-plugin/marketplace.json` 的 `plugins` 数组中添加条目",
        f"3. 运行 `python3 scripts/update-readme.py` 更新本文件",
        "4. `claude plugin validate plugins/<name>` 校验",
        "5. `claude plugin tag plugins/<name>` 打版本标签",
        "6. `git push --tags` 推送",
        "",
    ])

    with open(README_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"README.md generated with {len(data.get('plugins', []))} plugin(s).")


def parse_frontmatter(filepath: Path) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    try:
        with open(filepath) as f:
            content = f.read()
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                raw = content[3:end].strip()
                result = {}
                for line in raw.split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        result[key.strip()] = val.strip()
                return result
    except Exception:
        pass
    return {}


if __name__ == "__main__":
    main()
