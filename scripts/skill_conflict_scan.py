#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_conflict_scan.py —— 技能冲突扫描（纯标准库）

设计原则：**不用相似度算法**。
社区里做得最好的 skill-organizer 明确写过：
    "Do NOT use keyword matching, Jaccard similarity, or heuristic categorization."
因为"像不像"和"会不会抢活"是两件事。所以这里用「枚举 + 交集」，只报能举证的冲突。

三级判定：
  🔴 确定抢触发 —— 完全相同的触发短语出现在两个技能里
  🟡 疑似重叠   —— 共享 ≥2 个领域词，但触发短语不交叉
  ⚪ 名称可疑   —— 名字互为子串或带版本后缀（可能是新旧并存）

用法：
    python skill_conflict_scan.py <技能根目录>
    python skill_conflict_scan.py <技能根目录> --json report.json
    python skill_conflict_scan.py <技能根目录> --only-red     只报确定冲突
"""
import sys, os, re, json, argparse
from collections import defaultdict

# 领域词表：命中 ≥2 个就算"疑似重叠"。可按需增补。
DOMAIN_WORDS = [
    "PDF", "APK", "EXE", "代理", "节点", "IP", "DNS", "写作", "小说", "该领域", "剧本",
    "代码", "重构", "测试", "部署", "配置", "日志", "数据库", "缓存", "文件", "目录",
    "视频", "音频", "转录", "配音", "图片", "截图", "OCR", "文档", "表格", "网页",
    "抓取", "爬虫", "下载", "上传", "微信", "QQ", "浏览器", "扩展", "插件", "技能",
    "记忆", "对话", "聊天", "翻译", "总结", "提炼", "蒸馏", "拆分", "合并", "清理",
    "磁盘", "空间", "备份", "恢复", "迁移", "权限", "密钥", "限流", "性能",
]

# 版本/备份后缀
VERSION_SUFFIX = re.compile(r"([-_]v?\d+(\.\d+)*|_backup.*|_bak.*|[-_]old.*)$", re.I)


def read_frontmatter(path):
    """只取 SKILL.md 的 frontmatter（name/description），不读正文"""
    try:
        txt = open(path, encoding="utf-8", errors="ignore").read(6000)
    except Exception:
        return None, None
    m = re.search(r"^---\s*\n(.*?)\n---", txt, re.S)
    if not m:
        return None, None
    fm = m.group(1)
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    desc = re.search(r"^description:\s*(.+?)(?=^\w+:|\Z)", fm, re.S | re.M)
    name = name.group(1).strip().strip('"\'') if name else None
    desc = re.sub(r"\s+", " ", desc.group(1)).strip() if desc else ""
    return name, desc


def extract_triggers(desc):
    """提取触发短语。

    两个噪音源必须挡住：
    1. 英文按空格切 → user/for/to/use/when 这类虚词全被当成触发词
    2. 单个英文单词 → HTML/APK 这类是领域词，不是触发短语
    """
    out = set()

    # ① 引号内的短语（中英文引号都认）
    for m in re.finditer(r'[\u201c"]([^\u201d"]{2,24})[\u201d"]', desc):
        t = m.group(1).strip()
        if not t:
            continue
        # 纯英文小写单词 → 丢弃
        if re.fullmatch(r"[a-z]+", t):
            continue
        out.add(t)

    # ② 中文「触发词：」后面，按中文标点切
    for kw in ("触发词", "触发关键词"):
        i = desc.find(kw)
        if i >= 0:
            tail = re.sub(r"^[^：:]*[：:]", "", desc[i:i + 300])
            for part in re.split(r"[、,，;；。]+", tail):
                part = part.strip(" \u201c\u201d\"'")
                if 2 <= len(part) <= 20 and not re.fullmatch(r"[a-z]+", part):
                    out.add(part)

    # ③ 英文 Use when 后面：按逗号分句，且必须是多词短语
    for kw in ("Use when", "use when", "Use for", "use for"):
        i = desc.find(kw)
        if i >= 0:
            tail = desc[i + len(kw):i + 400]
            for part in re.split(r"[,;.]", tail):
                part = part.strip(" \u201c\u201d\"'")
                words = part.split()
                # 只留 2–6 个词、长度 ≥8 的短语
                if 2 <= len(words) <= 6 and len(part) >= 8:
                    out.add(part)

    return {t for t in out if t}


def extract_domains(desc):
    return {w for w in DOMAIN_WORDS if w.lower() in desc.lower()}


def load_disabled_map():
    """从 .skill-list-cache.json 读哪些技能是关着的。读不到就当全开着。"""
    cache = os.path.expanduser(r"~\.workbuddy\.skill-list-cache.json")
    try:
        d = json.load(open(cache, encoding="utf-8"))
        return {it.get("name"): bool(it.get("disable")) for it in d.get("results", [])}
    except Exception:
        return {}


def scan(root):
    skills = []
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            continue
        sk = os.path.join(p, "SKILL.md")
        if not os.path.isfile(sk):
            continue
        name, desc = read_frontmatter(sk)
        if not name:
            continue
        skills.append({
            "dir": d,
            "name": name,
            "triggers": extract_triggers(desc),
            "domains": extract_domains(desc),
        })
    return skills


def find_conflicts(skills):
    red, yellow, gray = [], [], []

    # 触发短语反向索引
    trig_index = defaultdict(list)
    for s in skills:
        for t in s["triggers"]:
            trig_index[t].append(s["name"])
    for t, names in trig_index.items():
        if len(names) >= 2:
            red.append({"trigger": t, "skills": names})

    # 领域词交叉（两两）
    n = len(skills)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = skills[i], skills[j]
            shared = a["domains"] & b["domains"]
            if len(shared) >= 2:
                # 已判红的对子不重复报黄
                pair_red = any(
                    set(a["name"] for _ in [0]) and
                    a["name"] in r["skills"] and b["name"] in r["skills"] for r in red
                )
                if not pair_red:
                    yellow.append({
                        "skills": [a["name"], b["name"]],
                        "shared_domains": sorted(shared),
                    })

    # 名称可疑
    for i in range(n):
        for j in range(i + 1, n):
            a, b = skills[i]["name"], skills[j]["name"]
            if a == b or VERSION_SUFFIX.search(skills[i]["dir"]) or VERSION_SUFFIX.search(skills[j]["dir"]):
                gray.append({"skills": [a, b], "reason": "同名或带版本后缀"})
            elif len(a) >= 3 and len(b) >= 3 and (a in b or b in a):
                gray.append({"skills": [a, b], "reason": "名字互为子串"})

    return red, yellow, gray


def main():
    ap = argparse.ArgumentParser(description="技能冲突扫描")
    ap.add_argument("root", help="技能根目录（含多个子目录，每个有 SKILL.md）")
    ap.add_argument("--json", help="输出 JSON 报告路径")
    ap.add_argument("--only-red", action="store_true", help="只报确定冲突")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print(f"目录不存在：{args.root}")
        return 1

    skills = scan(args.root)
    if not skills:
        print("没找到带 SKILL.md 的技能")
        return 1

    red, yellow, gray = find_conflicts(skills)

    print(f"扫描 {len(skills)} 个技能 → "
          f"确定冲突 {len(red)} 组 / 疑似重叠 {len(yellow)} 对 / 名称可疑 {len(gray)} 对\n")

    if red:
        print("🔴 确定抢触发（同一个触发短语被两个技能认领）")
        for r in red:
            print(f"   「{r['trigger']}」 → {'  ×  '.join(r['skills'])}")
        print()

    if not args.only_red and yellow:
        print("🟡 疑似重叠（共享 ≥2 个领域词，但触发短语不冲突）")
        for y in yellow[:20]:
            print(f"   {'  ~  '.join(y['skills'])}   共享：{'、'.join(y['shared_domains'])}")
        if len(yellow) > 20:
            print(f"   …还有 {len(yellow)-20} 对")
        print()

    if not args.only_red and gray:
        print("⚪ 名称可疑（可能是新旧并存）")
        for g in gray[:10]:
            print(f"   {'  ?  '.join(g['skills'])}   原因：{g['reason']}")
        if len(gray) > 10:
            print(f"   …还有 {len(gray)-10} 对")
        print()

    if not red and not yellow:
        print("✅ 没发现冲突")

    print("─" * 60)
    print("判定说明：")
    print("  [红] 才有资格谈合并；[黄] 只是值得看一眼，多数可以不动")
    print("  本工具不判「像不像」，只报能举证的交叉点")
    print("  ⚠ 本工具不判断技能是否已关闭——请自行对照，已关的那几组忽略即可")
    print("  下一步 → 读 references/MERGE.md 的【判】段，别直接动手")

    if args.json:
        open(args.json, "w", encoding="utf-8").write(json.dumps({
            "技能数": len(skills),
            "确定冲突": red,
            "疑似重叠": yellow,
            "名称可疑": gray,
        }, ensure_ascii=False, indent=2))
        print(f"\n已写入 {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
