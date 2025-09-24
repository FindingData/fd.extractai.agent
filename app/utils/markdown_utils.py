from markdown_it import MarkdownIt
import re
from collections import defaultdict

def normalize_title(t: str) -> str:
    return re.sub(r'[\s：:，,（(）)\[\]【】]+', '', t.strip().lower())

def _extract_bolds_from_inline(inline_tok):
    """从 heading 的 inline token 中提取 **粗体** 片段列表"""
    bolds, in_strong, buf = [], False, []
    # markdown-it-py 把粗体解析为 strong_open / strong_close 包裹的 text
    for ch in (inline_tok.children or []):
        if ch.type == "strong_open":
            in_strong, buf = True, []
        elif ch.type == "strong_close":
            if in_strong and buf:
                bolds.append("".join(buf).strip())
            in_strong, buf = False, []
        elif ch.type == "text" and in_strong:
            buf.append(ch.content)
    return bolds

def sectionize(md_text: str):
    """返回：[{level,title,start,end,content}] ；start/end 为 token 索引（半开区间）"""
    md = MarkdownIt()
    tokens = md.parse(md_text)
    sections = []
    stack = []  # [(level, start_idx, title)]
    # 收集 heading_open / inline / heading_close 三连
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])  # h1->1, h2->2...
            # 下一个通常是标题文本的 inline
            title = ""
            if i+1 < len(tokens) and tokens[i+1].type == "inline":
                title = tokens[i+1].content.strip()
            # 关闭同级/更深级
            while stack and stack[-1][0] >= level:
                l, sidx, t = stack.pop()
                sections.append({"level": l, "title": t, "start": sidx, "end": i})
            stack.append((level, i, title))
        i += 1
    # 收尾
    while stack:
        l, sidx, t = stack.pop()
        sections.append({"level": l, "title": t, "start": sidx, "end": len(tokens)})

    # 提取每段正文纯文本（介于 heading_close 和下一个 heading_open 之间的 inline/paragraph 等）
    # 简化：拼接 inline.content
    results = []
    for sec in sections:
        # 找到这一节的 heading_close
        j = sec["start"]
        while j < sec["end"] and tokens[j].type != "heading_close":
            j += 1
        body_inline = []
        k = j + 1
        while k < sec["end"]:
            tt = tokens[k]
            if tt.type == "inline":
                body_inline.append(tt.content)
            k += 1
        results.append({
            "level": sec["level"],
            "title": sec["title"],
            "content": "\n".join(x for x in body_inline if x).strip()
        })
    return results

def bucket_by_targets(sections, config):
    """按照同义词映射到业务Key"""
    rev = {}
    for key, syns in config.items():
        for s in syns:
            rev[normalize_title(s)] = key
    buckets = defaultdict(list)
    for s in sections:
        nt = normalize_title(s["title"])
        if nt in rev:
            buckets[rev[nt]].append(s)
            continue
        # 模糊包含兜底
        hit = None
        for syn_norm, key in rev.items():
            if syn_norm and syn_norm in nt:
                hit = key; break
        if hit: buckets[hit].append(s)
    return buckets