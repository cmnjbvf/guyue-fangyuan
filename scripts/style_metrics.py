#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_metrics.py —— 文本风格量化（纯标准库，无第三方依赖）

用途：把一个作者/一本书/一批文章的写作习惯，变成一组可比对的数字。
用途不是"判断好坏"，是"把感觉拆成可修改的指标"。

用法：
    python style_metrics.py <文件或目录> [--json 输出.json] [--compare 另一份]

支持 .txt / .md，UTF-8 编码。多份文件会合并统计并给出每份的对照。
"""
import sys, os, re, json, argparse, statistics
from collections import Counter

# 中文标点与常见模糊限制语
SENT_END = "。！？!?；;"
HEDGES = ["大概", "或许", "也许", "可能", "我认为", "我觉得", "差不多", "基本上",
          "相对来说", "应该说", "算是", "有点", "可能吧", "大致", "几乎", "相当"]
FIRST = ["我", "我们", "咱们", "本人"]
SECOND = ["你", "你们", "您"]
THIRD = ["他", "她", "它", "他们", "她们", "它们"]


def read_texts(path):
    """返回 [(文件名, 文本)]"""
    if os.path.isfile(path):
        return [(os.path.basename(path), open(path, encoding="utf-8", errors="ignore").read())]
    out = []
    for dp, dn, fn in os.walk(path):
        for f in sorted(fn):
            if f.endswith((".txt", ".md")):
                p = os.path.join(dp, f)
                out.append((os.path.relpath(p, path), open(p, encoding="utf-8", errors="ignore").read()))
    return out


def strip_markdown(txt):
    """剥离 markdown。所有空白只吃空格和 tab，绝不吃换行"""
    txt = re.sub(r"```.*?```", "", txt, flags=re.S)
    txt = re.sub(r"~~~.*?~~~", "", txt, flags=re.S)
    txt = re.sub(r"`[^`\n]*`", "", txt)
    txt = re.sub(r"^[ \t]*\|.*$", "", txt, flags=re.M)
    txt = re.sub(r"^[ \t]*[-:|]+[ \t]*$", "", txt, flags=re.M)
    txt = re.sub(r"^[ \t]*[#>*\-+]+[ \t]*", "", txt, flags=re.M)
    txt = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", txt)
    txt = re.sub(r"^[ \t]*\d+\.[ \t]*", "", txt, flags=re.M)
    return txt


def split_sentences(txt):
    """按中文/英文句末标点切句，保留内容"""
    parts = re.split(f"[{re.escape(SENT_END)}]+", txt)
    return [p.strip() for p in parts if p.strip()]


def split_paragraphs(txt):
    return [p.strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]


def count_chars(txt):
    """去掉空白后的字符数（中文按字，英文按词近似）"""
    return len(re.sub(r"\s", "", txt))


def analyze(name, txt):
    txt = strip_markdown(txt)
    sents = split_sentences(txt)
    paras = split_paragraphs(txt)
    n_char = count_chars(txt)
    if n_char == 0:
        return None

    # 句长（按字符数）
    lens = [count_chars(s) for s in sents if count_chars(s) > 0]
    if not lens:
        return None

    # 四区间分布
    bins = {"1-10": 0, "11-20": 0, "21-40": 0, "41+": 0}
    for L in lens:
        if L <= 10:
            bins["1-10"] += 1
        elif L <= 20:
            bins["11-20"] += 1
        elif L <= 40:
            bins["21-40"] += 1
        else:
            bins["41+"] += 1
    total_s = len(lens)

    # 标点密度（每百字）
    def dens(ch):
        return round(txt.count(ch) / n_char * 100, 2)
    punct = {c: dens(c) for c in "，。！？；：、（）—…\"" }

    # 人称
    def pronoun(lst):
        return round(sum(txt.count(w) for w in lst) / n_char * 100, 2)

    # 模糊限制语
    hedge_hits = []
    for h in HEDGES:
        c = txt.count(h)
        if c:
            hedge_hits.append((h, c))
    hedge_total = sum(c for _, c in hedge_hits)

    # 段落
    para_lens = [count_chars(p) for p in paras]
    single_sent_paras = sum(1 for p in paras if len(split_sentences(p)) <= 1)

    # 词汇多样性（按 2-gram 近似）
    clean = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", txt)
    bigrams = [clean[i:i + 2] for i in range(len(clean) - 1)]
    uniq_ratio = round(len(set(bigrams)) / len(bigrams), 3) if bigrams else 0

    return {
        "文件": name,
        "总字符数": n_char,
        "句子数": total_s,
        "段落数": len(paras),
        "句长": {
            "平均": round(statistics.mean(lens), 1),
            "中位": round(statistics.median(lens), 1),
            "最短": min(lens),
            "最长": max(lens),
            "标准差": round(statistics.pstdev(lens), 1),
            "区间分布": {k: f"{v}（{round(v/total_s*100)}%）" for k, v in bins.items()},
            "短句比例(≤10字)": f"{round(bins['1-10']/total_s*100)}%",
        },
        "句型占比": {
            "问句": f"{round(txt.count('？')/max(total_s,1)*100)}%",
            "感叹句": f"{round(txt.count('！')/max(total_s,1)*100)}%",
        },
        "标点密度(每百字)": punct,
        "人称密度(每百字)": {
            "第一人称": pronoun(FIRST),
            "第二人称": pronoun(SECOND),
            "第三人称": pronoun(THIRD),
        },
        "词汇多样性(2gram)": uniq_ratio,
        "段落": {
            "平均长度": round(statistics.mean(para_lens), 1) if para_lens else 0,
            "单句段落比例": f"{round(single_sent_paras/max(len(paras),1)*100)}%",
        },
        "模糊限制语": {
            "总数": hedge_total,
            "每千字": round(hedge_total / n_char * 1000, 2),
            "明细": dict(sorted(hedge_hits, key=lambda x: -x[1])[:8]),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="文本风格量化")
    ap.add_argument("path", help="文件或目录")
    ap.add_argument("--json", help="输出到 JSON 文件")
    ap.add_argument("--compare", help="与另一份对比")
    args = ap.parse_args()

    texts = read_texts(args.path)
    if not texts:
        print("没找到 .txt / .md 文件")
        return 1

    results = []
    for name, txt in texts:
        r = analyze(name, txt)
        if r:
            results.append(r)

    if args.compare:
        other = read_texts(args.compare)
        for name, txt in other:
            r = analyze(f"[对照] {name}", txt)
            if r:
                results.append(r)

    # 样本纯净度警告：非散文（表格/清单）统计不可靠
    for r in results:
        if r["句子数"] < r["段落数"]:
            print(f"⚠️  {r['文件']}：句子数({r['句子数']}) < 段落数({r['段落数']})，"
                  f"剥离后有大量无标点的短行（常见于表格/清单）。"
                  f"本统计对散文才准，非散文样本请谨慎使用。", file=sys.stderr)
        elif r["总字符数"] < 800:
            print(f"⚠️  {r['文件']}：有效字符仅 {r['总字符数']}，样本偏小，"
                  f"建议每份材料 ≥2000 字再下结论。", file=sys.stderr)

    out = results[0] if len(results) == 1 else results

    if args.json:
        open(args.json, "w", encoding="utf-8").write(
            json.dumps(out, ensure_ascii=False, indent=2))
        print(f"已写入 {args.json}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))

    # 对比模式下给一句人话总结
    if args.compare and len(results) >= 2:
        a, b = results[0], results[1]
        print("\n=== 关键差异（第一份 vs 对照）===")
        for k in ["平均", "中位", "标准差"]:
            va, vb = a["句长"][k], b["句长"][k]
            mark = "更短" if va < vb else ("更长" if va > vb else "持平")
            print(f"  句长{k}: {va} vs {vb}  →  {mark}")
        print(f"  短句比例: {a['句长']['短句比例(≤10字)']} vs {b['句长']['短句比例(≤10字)']}")
        print(f"  单句段落: {a['段落']['单句段落比例']} vs {b['段落']['单句段落比例']}")
        print(f"  模糊语每千字: {a['模糊限制语']['每千字']} vs {b['模糊限制语']['每千字']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
