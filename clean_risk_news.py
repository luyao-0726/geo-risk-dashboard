#!/usr/bin/env python3
"""清洗 raw_risk_news.csv → risk_events_clean.csv"""

import pandas as pd
import re
from datetime import datetime

# ── 1. 读入 ──────────────────────────────────────────────
df = pd.read_csv("raw_risk_news.csv", dtype=str, keep_default_na=False)
raw_rows = len(df)
print(f"原始行数: {raw_rows}")

deletion_log = []

# ── 2. 清理各字段的乱码和HTML（先去脏，再判空） ──────────
def clean_text(s: str) -> str:
    """去掉 BOM 乱码、HTML 标签、多余空白"""
    s = str(s)
    s = s.replace("ï»¿", "")
    s = re.sub(r"<[^>]*>", "", s)
    s = re.sub(r"&[a-zA-Z]+;", "", s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    return s

for col in df.columns:
    df[col] = df[col].apply(clean_text)

# ── 3. 删除无效行（标题和正文摘要都为空，无实际信息） ────
before = len(df)
garbage_mask = df["标题"].eq("") & df["正文摘要"].eq("")
garbage_rows = df[garbage_mask]
for _, r in garbage_rows.iterrows():
    nid = r["news_id"] if r["news_id"] else "(无ID)"
    deletion_log.append(f"删除无效行（标题和正文均为空）: news_id={nid}")

df = df[~garbage_mask].copy()
print(f"删除无效行: {before - len(df)} 行")

# ── 4. 风险类型归并映射 ──────────────────────────────────
risk_map = {
    "准入受阻": "准入受阻",
    "准入 受阻": "准入受阻",
    "market_access_blocked": "准入受阻",

    "政局失稳": "政局失稳",
    "政局失稳 ": "政局失稳",

    "政策突变": "政策突变",
    "policy_shift": "政策突变",

    "政社夹击": "政社夹击",
    "state_society_squeeze": "政社夹击",

    "沉没成本": "沉没成本",
    "sunk_cost": "沉没成本",
}

unmapped = set(df["风险类型"].unique()) - set(risk_map.keys())
if unmapped:
    print(f"⚠ 未映射的风险类型: {unmapped}")

df["风险类型"] = df["风险类型"].map(risk_map).fillna(df["风险类型"])

# ── 5. 国家名统一为中文 ──────────────────────────────────
country_map = {
    "USA": "美国",
    "United States": "美国",
    "UK": "英国",
    "Vietnam": "越南",
}

df["国家"] = df["国家"].map(country_map).fillna(df["国家"])

# ── 6. 日期统一为 YYYY-M-DD ──────────────────────────────
def parse_date(s: str) -> str:
    s = s.strip()
    if not s:
        return ""

    formats = [
        "%Y/%m/%d",      # 2026/5/7
        "%Y-%m-%d",      # 2026-5-7
        "%Y年%m月%d日",   # 2026年4月16日
        "%m/%d/%Y",      # 3/4/2026
        "%d.%m.%Y",      # 04.06.2026
        "%d.%m.%y",      # 04.06.26
        "%d/%m/%Y",      # 04/06/2026
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return f"{dt.year}-{dt.month}-{dt.day}"
        except ValueError:
            continue

    return ""

fail_before = df["发布日期"].eq("").sum()
df["发布日期"] = df["发布日期"].apply(parse_date)
fail_after = df["发布日期"].eq("").sum()
if fail_after > fail_before:
    print(f"⚠ 有 {fail_after} 行日期解析失败")

# ── 7. 去重 ──────────────────────────────────────────────
# 7a. 按 news_id 去重（保留首次出现）
before = len(df)
dup_id_mask = df.duplicated(subset="news_id", keep=False)
for nid in df.loc[dup_id_mask, "news_id"].unique():
    cnt = (df["news_id"] == nid).sum()
    deletion_log.append(f"按news_id去重: {nid} 出现{cnt}次, 保留1行")

df = df.drop_duplicates(subset="news_id", keep="first").copy()
print(f"news_id去重: {before - len(df)} 行")

# 7b. 按内容去重（相同标题+正文但不同news_id）
before = len(df)
dup_content_mask = df.duplicated(subset=["标题", "正文摘要"], keep=False)
dup_content = df[dup_content_mask]
if not dup_content.empty:
    grouped = dup_content.groupby(["标题", "正文摘要"])
    for (title, summary), group in grouped:
        ids = group["news_id"].tolist()
        deletion_log.append(
            f"内容重复去重: 标题'{title[:40]}...' 对应ID {ids}, 保留 {ids[0]}"
        )
df = df.drop_duplicates(subset=["标题", "正文摘要"], keep="first").copy()
print(f"内容去重: {before - len(df)} 行")

# ── 8. 输出 ──────────────────────────────────────────────
df.to_csv("risk_events_clean.csv", index=False, encoding="utf-8-sig")
clean_rows = len(df)
deleted = raw_rows - clean_rows

print(f"\n清洗后行数: {clean_rows}")
print(f"共删除: {deleted} 行")

print("\n========== 删除明细 ==========")
for entry in deletion_log:
    print(f"  • {entry}")

print(f"\n汇总: 原始{raw_rows}行 → 清洗后{clean_rows}行, 删除{deleted}行")
print(f"  其中: 无效行(空内容) {sum(1 for e in deletion_log if '无效' in e)} 行")
print(f"        news_id重复 {sum(1 for e in deletion_log if 'news_id' in e)} 行")
print(f"        内容重复 {sum(1 for e in deletion_log if '内容重复' in e)} 行")
print("输出文件: risk_events_clean.csv")