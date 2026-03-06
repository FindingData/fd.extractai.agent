from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Pattern

from markitdown import MarkItDown

_md = MarkItDown()


def normalize_title(title: str) -> str:
    return re.sub(r"[\s：:，,（(）)\[\]【】]+", "", (title or "").strip().lower())


def _join_lines(lines: List[str], span: tuple[int, int]) -> str:
    return "\n".join(lines[span[0]:span[1]])


def sectionize(md_text: str) -> List[Dict[str, Any]]:
    """
    将 markdown 按 heading 切成节，返回:
    [
        {
            "level": 1,
            "title": "...",
            "content": "..."
        }
    ]
    """
    tokens = _md.parse(md_text)
    sections: List[Dict[str, Any]] = []
    stack: List[tuple[int, int, str]] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            title = ""
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                title = tokens[i + 1].content.strip()

            while stack and stack[-1][0] >= level:
                l, sidx, t = stack.pop()
                sections.append(
                    {
                        "level": l,
                        "title": t,
                        "start": sidx,
                        "end": i,
                    }
                )

            stack.append((level, i, title))
        i += 1

    while stack:
        l, sidx, t = stack.pop()
        sections.append(
            {
                "level": l,
                "title": t,
                "start": sidx,
                "end": len(tokens),
            }
        )

    results: List[Dict[str, Any]] = []
    for sec in sections:
        j = sec["start"]
        while j < sec["end"] and tokens[j].type != "heading_close":
            j += 1

        body_inline: List[str] = []
        k = j + 1
        while k < sec["end"]:
            tt = tokens[k]
            if tt.type == "inline":
                body_inline.append(tt.content)
            k += 1

        results.append(
            {
                "level": sec["level"],
                "title": sec["title"],
                "content": "\n".join(x for x in body_inline if x).strip(),
            }
        )

    return results


def bucket_by_targets(
    sections: List[Dict[str, Any]],
    config: Dict[str, List[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    按标题同义词把 section 映射到业务 key。
    """
    rev: Dict[str, str] = {}
    for key, syns in config.items():
        for s in syns:
            rev[normalize_title(s)] = key

    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for sec in sections:
        nt = normalize_title(sec.get("title", ""))

        if nt in rev:
            buckets[rev[nt]].append(sec)
            continue

        hit = None
        for syn_norm, key in rev.items():
            if syn_norm and syn_norm in nt:
                hit = key
                break

        if hit:
            buckets[hit].append(sec)

    return buckets


def find_blocks_by_pattern(
    md_text: str,
    pattern: str | Pattern[str],
    include_subsections: bool = True,
) -> List[Dict[str, Any]]:
    """
    命中标题 => 返回整节（可选是否包含子节）
    命中段落 => 返回该段落
    """
    rx = re.compile(pattern, re.I) if isinstance(pattern, str) else pattern
    tokens = _md.parse(md_text)
    lines = md_text.splitlines()

    results: List[Dict[str, Any]] = []
    i = 0

    while i < len(tokens):
        t = tokens[i]

        if t.type == "heading_open":
            level = int(t.tag[1])
            inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
            title = inline.content.strip() if inline else ""

            if rx.search(title):
                start_line = t.map[0] if t.map else 0
                j = i + 1
                end_line = len(lines)

                while j < len(tokens):
                    tj = tokens[j]
                    if tj.type == "heading_open":
                        lv = int(tj.tag[1])
                        if include_subsections:
                            if lv <= level:
                                end_line = tj.map[0] if tj.map else len(lines)
                                break
                        else:
                            end_line = tj.map[0] if tj.map else len(lines)
                            break
                    j += 1

                results.append(
                    {
                        "kind": "section",
                        "title": title,
                        "level": level,
                        "line_range": (start_line, end_line),
                        "text": "\n".join(lines[start_line:end_line]),
                    }
                )

        if t.type == "paragraph_open" and t.map:
            para = _join_lines(lines, tuple(t.map))
            if rx.search(para):
                results.append(
                    {
                        "kind": "paragraph",
                        "line_range": tuple(t.map),
                        "text": para,
                    }
                )

        i += 1

    return results