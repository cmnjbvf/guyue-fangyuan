#!/usr/bin/env python3
"""多文件语料合并器：把爬取/收集产出的多文件目录合成一个带溯源的单一 source。

典型上游是 crawl4ai-site-to-md 的产物（<语言>/<栏目>/<slug>.md 目录树）。
合并后交给 chunk.py 分块，进入分批笔记流水线。

用法:
    python merge_corpus.py <dir> -o <output.md> [--ext .md .txt ...]
                          [--header "## 来源：{relpath}"]

产物:
    <output.md>                合并后的单一文本（块间以空行分隔）
    <output.md>.manifest.json  每个文件的字符区间清单（块区间无缝平铺全文，供溯源）

排序: 按相对路径自然排序（2.md 在 10.md 前）。
退出码: 0 成功; 2 目录不存在/无匹配文件/参数错误; 1 写出失败。
"""

import argparse
import json
import os
import re
import sys

from chunk import read_text

DEFAULT_EXTS = (".md", ".markdown", ".txt")


def natural_key(s):
    """自然排序键：数字段按数值比，避免 10.md 排在 2.md 前；混合类型安全。"""
    key = []
    for part in re.split(r"(\d+)", s):
        if part.isdigit():
            key.append((0, int(part), ""))
        else:
            key.append((1, 0, part.lower()))
    return key


def collect_files(root, exts):
    """递归收集 root 下扩展名匹配的文件，返回 (相对路径, 绝对路径) 列表，自然序。"""
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if os.path.splitext(name)[1].lower() in exts:
                abs_path = os.path.join(dirpath, name)
                rel = os.path.relpath(abs_path, root).replace(os.sep, "/")
                found.append((rel, abs_path))
    found.sort(key=lambda item: natural_key(item[0]))
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="多文件语料合并器：目录 -> 带溯源的单一 source + manifest")
    ap.add_argument("dir", help="语料目录（递归扫描）")
    ap.add_argument("-o", "--out", required=True, help="输出文件路径")
    ap.add_argument("--ext", nargs="+", default=list(DEFAULT_EXTS),
                    help="要合并的扩展名，默认 .md .markdown .txt")
    ap.add_argument("--header", default="## 来源：{relpath}",
                    help="每个文件前的来源标题，必须包含 {relpath} 占位符")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.dir):
        print("ERROR: directory not found: %s" % args.dir, file=sys.stderr)
        return 2
    if "{relpath}" not in args.header:
        print("ERROR: --header must contain {relpath} placeholder", file=sys.stderr)
        return 2
    exts = {e.lower() if e.startswith(".") else "." + e.lower() for e in args.ext}

    files = collect_files(args.dir, exts)
    if not files:
        print("ERROR: no files with extensions %s under %s"
              % (sorted(exts), args.dir), file=sys.stderr)
        return 2

    entries = []
    skipped = []
    for rel, abs_path in files:
        text, _enc = read_text(abs_path)
        if not text.strip():
            skipped.append({"path": rel, "reason": "empty"})
            continue
        entries.append({"relpath": rel, "content": text})

    if not entries:
        print("ERROR: all %d matched files are empty" % len(files), file=sys.stderr)
        return 2

    blocks = []
    spans = []
    pos = 0
    for e in entries:
        header = args.header.format(relpath=e["relpath"])
        block = header + "\n\n" + e["content"]
        spans.append({"relpath": e["relpath"], "start": pos, "end": pos + len(block),
                      "chars": len(block)})
        blocks.append(block)
        pos += len(block) + 2
    merged = "\n\n".join(blocks)

    if spans[-1]["end"] != len(merged) or spans[0]["start"] != 0:
        print("ERROR: internal span tiling check failed", file=sys.stderr)
        return 1

    manifest = {
        "source_dir": os.path.abspath(args.dir),
        "exts": sorted(exts),
        "file_count": len(entries),
        "skipped": skipped,
        "total_chars": len(merged),
        "files": spans,
    }
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(merged)
    with open(args.out + ".manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("OK: merged %d files (%d skipped) -> %s (%d chars)"
          % (len(entries), len(skipped), args.out, len(merged)))
    for s in skipped:
        print("  skipped: %s (%s)" % (s["path"], s["reason"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
