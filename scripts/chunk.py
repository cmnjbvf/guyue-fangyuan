#!/usr/bin/env python3
"""语义分块器：把大文本切成带重叠缓冲的块，保证主上下文永不接触原文。

用法:
    python chunk.py <input_file> -o <out_dir> [--target 5000] [--overlap 500]
                    [--min 1500] [--max 8000]

产物:
    <out_dir>/chunk-001.txt ...   每块的纯文本（不注入任何头部信息）
    <out_dir>/manifest.json       块清单 + 覆盖率校验结果

退出码:
    0  成功（manifest 中 coverage.ok 必为 true，否则以 1 退出）
    2  输入或参数错误（文件不存在、空文件、参数非法）
    1  其他失败（含覆盖率校验不过——不静默放过）

仅用标准库，Python 3.8+ 可跑。中文按字符数计，不需要 tokenizer。
"""

import argparse
import json
import os
import re
import sys

HEADING_RE = re.compile(r"^\s{0,3}(?:#{1,6}\s|第[0-9一二三四五六七八九十百千]+[章节回部篇卷集幕场]\s|【[^】]{1,30}】\s*$)")
SENT_DELIMS = "。！？!?；;…\n"


def read_text(path):
    """按 utf-8-sig -> utf-8 -> gbk -> utf-8(replace) 的顺序读文本，返回 (text, encoding)。"""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8(replace)"


def split_sentences(text):
    """按句末标点切句，保留标点在句尾。找不到标点的超长句原样返回。"""
    out = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in SENT_DELIMS:
            out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    return [s for s in out if s.strip()]


def build_units(text, max_len):
    """把原文切成语义单元列表 [(start, end, kind)]，kind ∈ heading/para/sent。

    优先按空行分块；以标题开头的块整体成为一个单元（标题不落单）；
    每个单元的尾部吞掉后续空行（分隔符），保证单元区间无缝平铺全文；
    超过 max_len 的块按句子再切，单句仍超长则硬切。
    """
    lines = text.split("\n")
    starts = []
    pos = 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln) + 1

    blocks = []
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].strip():
            j += 1
        blocks.append((i, j))
        i = j

    units = []
    for bi, (i, j) in enumerate(blocks):
        block_start = starts[i]
        block_end = starts[blocks[bi + 1][0]] if bi + 1 < len(blocks) else len(text)
        block = text[block_start:block_end]
        kind = "heading" if HEADING_RE.match(lines[i]) else "para"
        if len(block) <= max_len:
            units.append((block_start, block_end, kind))
        else:
            emitted = []
            pos = 0
            for s in split_sentences(block):
                if len(s) > max_len:
                    off = 0
                    while off < len(s):
                        piece = s[off:off + max_len]
                        emitted.append((pos + off, pos + off + len(piece)))
                        off += len(piece)
                else:
                    emitted.append((pos, pos + len(s)))
                pos += len(s)
            for a, b in emitted:
                units.append((block_start + a, block_start + b, "sent"))
    return units


def overlap_prefix(units, text, overlap):
    """取上一个块尾部的若干整单元作为重叠前缀，总长不超过 overlap。

    整单元放不下时退化为句界修剪的尾部切片，保证 content <= max + overlap。
    """
    if overlap <= 0 or not units:
        return ""
    tail_end = units[-1][1]
    taken = []
    total = 0
    for u in reversed(units):
        ulen = u[1] - u[0]
        if total + ulen > overlap:
            break
        taken.append(u)
        total += ulen
    if taken:
        return text[taken[-1][0]:tail_end]
    seg = text[max(units[0][0], tail_end - overlap):tail_end]
    cut = -1
    for idx, ch in enumerate(seg):
        if ch in SENT_DELIMS:
            cut = idx
    if 0 <= cut < len(seg) - 1:
        seg = seg[cut + 1:]
    return seg


def pack_units(units, text, target, min_len, max_len, overlap):
    """把单元贪心打包成块。标题边界优先关桶；保证 core 区间无缝平铺原文。"""
    chunks = []

    def close(cur):
        if not cur:
            return
        core_start = cur[0][0]
        core_end = cur[-1][1]
        prefix = overlap_prefix(cur, text, overlap) if chunks else ""
        content_start = core_start - len(prefix)
        chunks.append({
            "core_start": core_start,
            "core_end": core_end,
            "content_start": content_start,
            "content": text[content_start:core_end],
        })

    cur = []
    cur_len = 0
    for u in units:
        ulen = u[1] - u[0]
        if u[2] == "heading" and cur and cur_len >= min_len:
            close(cur)
            cur, cur_len = [], 0
        if cur and cur_len + ulen > max_len:
            close(cur)
            cur, cur_len = [], 0
        cur.append(u)
        cur_len += ulen
        if cur_len >= target:
            close(cur)
            cur, cur_len = [], 0
    close(cur)

    if len(chunks) >= 2:
        last = chunks[-1]
        prev = chunks[-2]
        merged_core = last["core_end"] - prev["core_start"]
        if last["core_end"] - last["core_start"] < min_len and merged_core <= max_len:
            merged = {
                "core_start": prev["core_start"],
                "core_end": last["core_end"],
                "content_start": prev["content_start"],
                "content": text[prev["content_start"]:last["core_end"]],
            }
            chunks[-2:] = [merged]
    return chunks


def validate_coverage(chunks, total_len):
    """core 区间必须从 0 无缝平铺到 total_len，否则不许放行。"""
    if not chunks:
        return False, "no chunks produced"
    if chunks[0]["core_start"] != 0:
        return False, "first chunk does not start at 0"
    if chunks[-1]["core_end"] != total_len:
        return False, "last chunk does not end at source length"
    for a, b in zip(chunks, chunks[1:]):
        if b["core_start"] != a["core_end"]:
            return False, "gap/overlap in core spans between chunks"
    return True, "ok"


def main(argv=None):
    ap = argparse.ArgumentParser(description="语义分块器：大文本 -> 带重叠的块 + manifest")
    ap.add_argument("input", help="输入文本文件路径")
    ap.add_argument("-o", "--out", required=True, help="输出目录")
    ap.add_argument("--target", type=int, default=5000, help="目标块长（字符），默认 5000")
    ap.add_argument("--overlap", type=int, default=500, help="块间重叠（字符），默认 500")
    ap.add_argument("--min", dest="min_len", type=int, default=1500, help="最小块长，默认 1500")
    ap.add_argument("--max", dest="max_len", type=int, default=8000, help="最大块长，默认 8000")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        print("ERROR: input file not found: %s" % args.input, file=sys.stderr)
        return 2
    if args.min_len < 1 or args.target < args.min_len or args.max_len < args.target:
        print("ERROR: need 1 <= min <= target <= max (got min=%d target=%d max=%d)"
              % (args.min_len, args.target, args.max_len), file=sys.stderr)
        return 2
    if args.overlap < 0 or args.overlap >= args.target:
        print("ERROR: need 0 <= overlap < target (got overlap=%d target=%d)"
              % (args.overlap, args.target), file=sys.stderr)
        return 2

    text, encoding = read_text(args.input)
    if not text.strip():
        print("ERROR: input is empty or whitespace-only: %s" % args.input, file=sys.stderr)
        return 2

    units = build_units(text, args.max_len)
    chunks = pack_units(units, text, args.target, args.min_len, args.max_len, args.overlap)
    ok, reason = validate_coverage(chunks, len(text))
    if not ok:
        print("ERROR: coverage check failed: %s" % reason, file=sys.stderr)
        return 1

    os.makedirs(args.out, exist_ok=True)
    width = max(3, len(str(len(chunks))))
    entries = []
    for idx, ch in enumerate(chunks, 1):
        name = "chunk-%0*d.txt" % (width, idx)
        with open(os.path.join(args.out, name), "w", encoding="utf-8", newline="") as f:
            f.write(ch["content"])
        entries.append({
            "id": idx,
            "file": name,
            "chars": len(ch["content"]),
            "core_start": ch["core_start"],
            "core_end": ch["core_end"],
            "overlap_chars": ch["core_start"] - ch["content_start"],
        })

    manifest = {
        "input": os.path.abspath(args.input),
        "encoding": encoding,
        "total_chars": len(text),
        "params": {"target": args.target, "overlap": args.overlap,
                   "min": args.min_len, "max": args.max_len},
        "chunk_count": len(entries),
        "chunks": entries,
        "coverage": {"ok": True, "core_tiles_source": True,
                     "duplicated_chars": sum(e["overlap_chars"] for e in entries)},
    }
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    sizes = [e["chars"] for e in entries]
    print("OK: %d chunks -> %s (chars: min=%d max=%d avg=%d, overlap total=%d)"
          % (len(entries), args.out, min(sizes), max(sizes),
             sum(sizes) // len(sizes), manifest["coverage"]["duplicated_chars"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
