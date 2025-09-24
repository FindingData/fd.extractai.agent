from markdown_it import MarkdownIt
import re
from collections import defaultdict



def extract_title_plus_pipe_table(md_text: str, title:str):
    lines = md_text.splitlines()
    n = len(lines)

    # 1) 找标题所在行（精确匹配去空白）
    title_idx = next((i for i, ln in enumerate(lines) if ln.strip() == title), None)
    if title_idx is None:
        return ""

    # 2) 跳过空行与 Setext 下划线（---）
    i = title_idx + 1
    while i < n and lines[i].strip() == "":
        i += 1
    if i < n and re.fullmatch(r"\s*-{3,}\s*", lines[i]):
        i += 1
        while i < n and lines[i].strip() == "":
            i += 1

    # 3) 简单判断是否是管道表格行（| a | b | …）
    def is_table_row(s):
        s = s.rstrip()
        return s.strip().startswith("|") and s.count("|") >= 2

    if i >= n or not is_table_row(lines[i]):
        # 标题后不是表格，就只返回标题
        return "\n".join(lines[title_idx:title_idx+1]).strip("\n")

    # 4) 连续收集表格行
    j = i
    while j < n and is_table_row(lines[j]):
        j += 1

    return "\n".join(lines[title_idx:j]).strip("\n")


def extract_basic_info_table(md_text: str, title="估价对象基本情况一览表"):
    md = MarkdownIt()
    tokens = md.parse(md_text)
    lines = md_text.splitlines()

    i = 0
    while i < len(tokens):
        t = tokens[i]
        # 1) 命中标题（这里是普通段落，而非 # 开头的 heading）
        if t.type == "paragraph_open":
            # 下一个通常是 inline，里面有文本
            if i+1 < len(tokens) and tokens[i+1].type == "inline":
                hdr = tokens[i+1].content.strip()
                if hdr == title:
                    start_line = t.map[0]  # 标题起始行
                    # 2) 紧随其后应是表格，找到 table_open/table_close 的行号范围
                    j = i + 2
                    end_line = start_line + 1  # 兜底：至少包含标题行
                    # 找第一张紧随其后的表
                    while j < len(tokens):
                        tj = tokens[j]
                        if tj.type == "table_open":
                            # table_close 的 map[1] 是表的结束行（半开区间）
                            # 先向前找对应的 table_close
                            k = j + 1
                            close_end = None
                            while k < len(tokens):
                                if tokens[k].type == "table_close":
                                    close_end = tokens[k].map[1]
                                    break
                                k += 1
                            if close_end is not None:
                                end_line = close_end
                            break
                        # 如果遇到新的块级元素就停止（避免跨太远）
                        if tj.type.endswith("_open") and tj.type not in ("thead_open", "tbody_open", "tr_open"):
                            break
                        j += 1
                    # 3) 回切文本
                    return "\n".join(lines[start_line:end_line])
        i += 1
    return ""  # 未命中


def normalize_title(t: str) -> str:
    return re.sub(r'[\s：:，,（(）)\[\]【】]+', '', t.strip().lower())

def _join(lines, m):
    return "\n".join(lines[m[0]:m[1]])


def find_blocks_by_pattern(md_text: str, pattern: str | re.Pattern, include_subsections=True):
    """
    命中标题 => 返回整节（可选是否包含子节）
    命中段落 => 返回该段落
    其他块（如引用、代码块）也可据需添加
    """
    rx = re.compile(pattern, re.I) if isinstance(pattern, str) else pattern
    md = MarkdownIt()
    tokens = md.parse(md_text)
    lines = md_text.splitlines()

    results = []
    i = 0
    while i < len(tokens):
        t = tokens[i]

        # 1) 标题命中：返回整节
        if t.type == "heading_open":
            level = int(t.tag[1])
            inline = tokens[i+1] if i+1 < len(tokens) and tokens[i+1].type == "inline" else None
            title = inline.content.strip() if inline else ""
            if rx.search(title):
                start_line = t.map[0]
                # 找节的结束行
                j = i + 1
                end_line = len(lines)
                while j < len(tokens):
                    tj = tokens[j]
                    if tj.type == "heading_open":
                        lv = int(tj.tag[1])
                        if include_subsections:
                            if lv <= level:
                                end_line = tj.map[0]
                                break
                        else:
                            end_line = tj.map[0]
                            break
                    j += 1
                results.append({
                    "kind": "section",
                    "title": title,
                    "level": level,
                    "line_range": (start_line, end_line),
                    "text": "\n".join(lines[start_line:end_line]),
                })

        # 2) 段落命中：仅返回该段
        if t.type == "paragraph_open":
            para = _join(lines, t.map)
            if rx.search(para):
                results.append({
                    "kind": "paragraph",
                    "line_range": tuple(t.map),
                    "text": para,
                })

        # 3) 可选：命中引用块/代码块时如何处理（示例：整块返回）
        # if t.type in ("blockquote_open", "fence", "code_block"):
        #     if rx.search(_join(lines, t.map)):
        #         results.append({...})

        i += 1

    return results


def _collect_paragraphs(md_text: str):
    md = MarkdownIt()
    tokens = md.parse(md_text)
    lines = md_text.splitlines()
    paras = []
    heading_stack = []  # [(level, title)]

    i = 0
    while i < len(tokens):
        t = tokens[i]

        # 维护当前标题路径
        if t.type == "heading_open":
            level = int(t.tag[1])  # 'h2' -> 2
            title = ""
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                title = tokens[i + 1].content.strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))

        # 收集段落
        if t.type == "paragraph_open" and t.map:
            start, end = t.map  # 行号范围（闭开区间）
            text = "\n".join(lines[start:end]).strip()
            paras.append({
                "index": len(paras),
                "text": text,
                "start_line": start,
                "end_line": end,
                "section_path": " / ".join([h[1] for h in heading_stack]),
            })
        i += 1
    return paras

def get_paragraph_by_index(md_text: str, idx: int) -> str | None:
    paras = _collect_paragraphs(md_text)
    return paras[idx]["text"] if 0 <= idx < len(paras) else None

def get_section_by_title(md_text: str, title: str, level: int | None = None) -> str | None:
    """返回以某标题开始，到下一个同级或更高标题前的原文片段。"""
    md = MarkdownIt()
    tokens = md.parse(md_text)
    lines = md_text.splitlines()

    start_line = end_line = current_level = None
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "heading_open":
            lvl = int(t.tag[1])
            txt = tokens[i + 1].content.strip() if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else ""
            # 命中的节已开始，遇到同级或更高标题则结束
            if start_line is not None and lvl <= current_level:
                end_line = t.map[0] if t.map else None
                break
            # 命中起点
            if txt == title and (level is None or lvl == level):
                current_level = lvl
                start_line = t.map[0] if t.map else None
        i += 1

    if start_line is None:
        return None
    if end_line is None:
        end_line = len(lines)
    return "\n".join(lines[start_line:end_line]).strip()

def get_paragraph_in_section(md_text: str, section_title: str, k: int = 0) -> str | None:
    paras = _collect_paragraphs(md_text)
    in_section = [p for p in paras if p["section_path"].split(" / ")[-1] == section_title]
    return in_section[k]["text"] if 0 <= k < len(in_section) else None


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