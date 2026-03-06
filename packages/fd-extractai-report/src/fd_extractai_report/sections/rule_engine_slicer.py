from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List,Pattern, Tuple,Optional

from fd_extractai_report.context import ReportContext, ReportSection
from fd_extractai_report.sections.base import SectionSlicer
from fd_extractai_report.rules.slicing.schema import SliceRuleSet, SliceStep 

from fd_extractai_report.text.mdkit import (
    bucket_by_targets,
    sectionize,
    find_blocks_by_pattern,
)

class RuleEngineSlicer(SectionSlicer):
    """
    规则切片执行器（强调调试可观测性）：
    - 每个 step 打印：输入范围、命中数量、去重、merge、truncate
    - 可通过构造参数 debug=True 或 ctx.metadata["debug_slice"]=True 开启
        """


    def __init__(
        self,
        ruleset: SliceRuleSet,
        *,
        key: str = "rule_engine",
        debug: bool = False,
        preview_chars: int = 120,
        print_text_preview: bool = False,
    ) -> None:
        super().__init__(key=key)
        self.ruleset = ruleset
        self.debug = debug
        self.preview_chars = preview_chars
        self.print_text_preview = print_text_preview

    def _dbg(self, ctx: ReportContext, msg: str) -> None:
        if self.debug or bool((ctx.metadata or {}).get("debug_slice")):
            print(msg)


    def _compile_patterns(self, patterns: Iterable[str]) -> List[Pattern]:
                    return [re.compile(p, re.MULTILINE) for p in (patterns or [])]

    def _get_line_span(self, text: str, pos: int) -> Tuple[int, int]:
        # 返回 pos 所在行的 [line_start, line_end)
        line_start = text.rfind("\n", 0, pos) + 1  # rfind 找不到返回 -1
        line_end = text.find("\n", pos)
        if line_end == -1:
            line_end = len(text)
        return line_start, line_end

    def _should_skip_match_by_line(
        self, 
        text: str,
        m: re.Match,
        skip_line_res: List[Pattern],
    ) -> bool:
        if not skip_line_res:
            return False
        ls, le = self._get_line_span(text, m.start())
        line = text[ls:le]
        for rx in skip_line_res:
            if rx.search(line):
                return True
        return False

    def _pick_match(
        self, 
        text: str,
        matches: List[re.Match],
        pick: str,
        skip_line_res: List[Pattern],
    ) -> Optional[re.Match]:
        if not matches:
            return None

        # earliest: 从前往后找第一个不过滤的
        if pick == "earliest":
            for m in matches:
                if not self._should_skip_match_by_line(text, m, skip_line_res):
                    return m
            return None

        # latest: 从后往前找第一个不过滤的
        if pick == "latest":
            for m in reversed(matches):
                if not self._should_skip_match_by_line(text, m, skip_line_res):
                    return m
            return None

        # 兜底：默认 earliest
        for m in matches:
            if not self._should_skip_match_by_line(text, m, skip_line_res):
                return m
        return None
    def _preview(self, s: str) -> str:
        s = (s or "").replace("\n", "\\n")
        return s if len(s) <= self.preview_chars else s[: self.preview_chars] + "..."

   

    def slice(self, context: ReportContext) -> Iterable[ReportSection]:
        full = context.ensure_markdown()
        self._dbg(context, f"🧩 [RuleEngine] ruleset={self.ruleset.name} steps={len(self.ruleset.steps)}")

        for si, step in enumerate(self.ruleset.steps, start=1):
            self._dbg(
                context,
                f"➡️  [Step {si}/{len(self.ruleset.steps)}] key={step.key} mode={step.mode} within={step.within or '__full__'} missing={step.missing}",
            )

            base_texts = self._resolve_base_texts(context, full, step)
            if not base_texts:
                self._dbg(context, f"   ⚠️ base_texts=0 -> skip (missing policy={step.missing})")
                continue

            produced_total = 0
            for bi, base in enumerate(base_texts):
                if not base.strip():
                    self._dbg(context, f"   ⚠️ base[{bi}] empty -> skip")
                    continue

                if self.print_text_preview:
                    self._dbg(context, f"   📎 base[{bi}] preview: {self._preview(base)}")

                secs = list(self._run_step(context, step, base, base_scope=step.within or "__full__", base_idx=bi))
                produced_total += len(secs)

                for s in secs:
                    context.add_slice(s)
                    yield s
            if self.debug:
                try:
                    keys = list((context.slices or {}).keys())
                except Exception:
                    keys = []
                print(f"   🧾 ctx.slices keys now: {keys}")
                if step.key in (context.slices or {}):
                    print(f"   🧾 ctx.slices['{step.key}'] count={len(context.slices[step.key])}")
            self._dbg(context, f"   ✅ produced={produced_total} sections for step={step.key}")

    def _resolve_base_texts(self, ctx: ReportContext, full: str, step: SliceStep) -> List[str]:
        if not step.within:
            self._dbg(ctx, "   🔎 input_scope=__full__")
            return [full]

        src = ctx.get_slices(step.within) or []
        if not src:
            if step.missing == "raise":
                raise KeyError(f"within slice '{step.within}' missing for step '{step.key}'")
            if step.missing == "full":
                self._dbg(ctx, f"   🔁 within '{step.within}' missing -> fallback to __full__")
                return [full]
            return []

        self._dbg(ctx, f"   🔎 input_scope={step.within} slices={len(src)}")
        return [s.text for s in src if s and s.text]

    def _run_step(self, ctx: ReportContext, step: SliceStep, text: str, *, base_scope: str, base_idx: int) -> Iterable[ReportSection]:
        p = {**(self.ruleset.defaults or {}), **(step.params or {})}

        merge = bool(p.get("merge", False))
        dedup = bool(p.get("dedup", True))
        max_sections = int(p.get("max_sections") or 0)
        max_chars = int(p.get("max_chars") or 0)

        self._dbg(
            ctx,
            f"   🧪 run: merge={merge} dedup={dedup} max_sections={max_sections or '∞'} max_chars={max_chars or '∞'} targets={len(step.targets)}",
        )

        produced: List[ReportSection] = []
        if step.mode == "by_heading":
            produced = self._by_heading(step, text, base_scope, base_idx)
        elif step.mode == "by_regex_block":
            produced = self._by_regex_block(step, text, base_scope, base_idx)
        elif step.mode == "by_table_after":
            produced = self._by_table_after(step, text, p, base_scope, base_idx)
        elif step.mode == "by_window_after":
            produced = self._by_window_after(step, text, p, base_scope, base_idx)
        elif step.mode == "by_regex_between":                         
            produced = self._by_regex_between(step, text, p, base_scope, base_idx)
        elif step.mode == "by_segment_tables":
            produced = self._by_segment_tables(step, text, p, base_scope, base_idx)
        else:
            self._dbg(ctx, f"   ❌ unknown mode={step.mode}")
            return

        self._dbg(ctx, f"   📦 raw_produced={len(produced)}")
        
        if produced and step.mode == "by_regex_between" and (self.debug or bool((ctx.metadata or {}).get("debug_slice"))):
            md0 = produced[0].metadata or {}
            self._dbg(ctx, f"   🎯 between start={md0.get('start')} end={md0.get('end')}")
        # ✅ 紧跟在 produced 之后加（在 self._dbg 那一层）
        if produced and (self.debug or bool((ctx.metadata or {}).get("debug_slice"))):
            md = produced[0].metadata or {}
            anchor = md.get("anchor")
            hits = md.get("hits") or []
            pos = hits[0].get("pos") if hits else None  # 注意：hits[0] 不一定就是最终 anchor（earliest 时应该是最小pos，但安全起见下面更严谨）
            # 更严谨：从 hits 里找到最终 anchor 的 pos
            pos2 = None
            if anchor and hits:
                for h in hits:
                    if h.get("anchor") == anchor:
                        pos2 = h.get("pos")
                        break
            ctx_pos = pos2 if pos2 is not None else pos

            self._dbg(ctx, f"   🎯 window_after picked anchor='{anchor}' pos={ctx_pos} hit_count={md.get('hit_count')} window_chars={md.get('window_chars')}")
            if self.print_text_preview:
                self._dbg(ctx, f"   🧾 window preview: {self._preview(produced[0].text)}")

        if dedup and produced:
            before = len(produced)
            produced = self._dedup_sections(produced)
            after = len(produced)
            if after != before:
                self._dbg(ctx, f"   🧹 dedup: {before} -> {after}")

        if max_sections and len(produced) > max_sections:
            self._dbg(ctx, f"   ✂️ max_sections: {len(produced)} -> {max_sections}")
            produced = produced[:max_sections]

        if merge and produced:
            merged = "\n\n".join(s.text for s in produced if s.text).strip()
            self._dbg(ctx, f"   🧷 merge parts={len(produced)} merged_len={len(merged)}")

            if not merged:
                self._dbg(ctx, "   ⚠️ merged empty -> skip")
                return

            truncated = False
            if max_chars and len(merged) > max_chars:
                merged = merged[:max_chars]
                truncated = True
                self._dbg(ctx, f"   ✂️ merged truncated to {max_chars}")

            yield ReportSection(
                key=step.key,
                title=step.key,
                text=merged,
                metadata={
                    "mode": step.mode,
                    "base_scope": base_scope,
                    "base_idx": base_idx,
                    "merged": True,
                    "truncated": truncated,
                    "step_targets": list(step.targets),
                    "ruleset": self.ruleset.name,
                },
            )
            return

        if max_chars:
            for s in produced:
                if s.text and len(s.text) > max_chars:
                    self._dbg(ctx, f"   ✂️ section truncated key={s.key} title={s.title}")
                    yield ReportSection(
                        key=s.key,
                        title=s.title,
                        text=s.text[:max_chars],
                        metadata={**(s.metadata or {}), "truncated": True, "max_chars": max_chars},
                    )
                else:
                    yield s
            return

        for s in produced:
            yield s

    def _by_heading(self, step: SliceStep, text: str, base_scope: str, base_idx: int) -> List[ReportSection]:
        sections = sectionize(text)
        grouped = bucket_by_targets(sections, {step.key: step.targets})
        raws = grouped.get(step.key) or []
        out: List[ReportSection] = []

        for i, raw in enumerate(raws):
            content = (raw.get("content") or "").strip()
            if not content:
                continue
            out.append(
                ReportSection(
                    key=step.key,
                    title=raw.get("title") or step.key,
                    text=content,
                    metadata={
                        "mode": step.mode,
                        "level": raw.get("level"),
                        "hit": list(step.targets),
                        "base_scope": base_scope,
                        "base_idx": base_idx,
                        "match_index": i,
                        "ruleset": self.ruleset.name,
                    },
                )
            )
        return out

    def _by_regex_block(self, step: SliceStep, text: str, base_scope: str, base_idx: int) -> List[ReportSection]:
        out: List[ReportSection] = []
        patterns = [re.compile(t, re.I) for t in (step.targets or [])]
        for pat in patterns:
            blocks = find_blocks_by_pattern(text, pat)
            for i, b in enumerate(blocks):
                raw = (b.get("text") or "").strip()
                if not raw:
                    continue
                out.append(
                    ReportSection(
                        key=step.key,
                        title=b.get("title") or step.key,
                        text=raw,
                        metadata={
                            "mode": step.mode,
                            "pattern": pat.pattern,
                            "kind": b.get("kind"),
                            "match_index": i,
                            "base_scope": base_scope,
                            "base_idx": base_idx,
                            "ruleset": self.ruleset.name,
                        },
                    )
                )
        return out

    def _by_regex_between(
        self,
        step: SliceStep,
        text: str,
        p: Dict[str, Any],
        base_scope: str,
        base_idx: int,
    ) -> List[ReportSection]:
        pick = (p.get("pick") or "earliest").lower()  # earliest | priority
        include_start = bool(p.get("include_start", True))
        include_end = bool(p.get("include_end", False))
        fallback_end_chars = int(p.get("fallback_end_chars") or 0)
        # ✅ 方案3：按“命中所在行”过滤（目录链接行等）
        skip_line_patterns = [s for s in (p.get("skip_if_line_matches") or []) if isinstance(s, str) and s.strip()]
        if self.debug:
            print(f"   🧷 skip_if_line_matches={skip_line_patterns!r}")
        starts = [t for t in (step.targets or []) if isinstance(t, str) and t.strip()]
        ends = [t for t in (p.get("ends") or []) if isinstance(t, str) and t.strip()]
        if not starts or not ends:
            return []

        def _loose_space_pattern(s: str) -> str:
            out = []
            for ch in s:
                if ch.strip():
                    out.append(re.escape(ch))
                    out.append(r"\s*")
                else:
                    out.append(r"\s*")
            return "".join(out)

        def _compile_many(arr: List[str]) -> List[re.Pattern]:
            pats: List[re.Pattern] = []
            for s in arr:
                try:
                    if p.get("loose_space", False):
                        s = _loose_space_pattern(s)
                    pats.append(re.compile(s, re.I | re.M))
                except re.error:
                    continue
            return pats

        start_pats = _compile_many(starts)
        end_pats = _compile_many(ends)
        if not start_pats or not end_pats:
            return []

        skip_line_res: List[re.Pattern] = []
        for s in skip_line_patterns:
            try:
                skip_line_res.append(re.compile(s, re.M))
            except re.error as e:
                if self.debug:
                    print(f"   ⚠️ bad skip regex: {s!r} err={e}")

        def _get_line_span(_text: str, pos: int) -> Tuple[int, int]:
            ls = _text.rfind("\n", 0, pos) + 1
            le = _text.find("\n", pos)
            if le == -1:
                le = len(_text)
            return ls, le

        def _line_text(_text: str, pos: int) -> str:
            ls, le = _get_line_span(_text, pos)
            return _text[ls:le]

        def _should_skip_by_line(_text: str, m: re.Match) -> bool:
            if not skip_line_res:
                return False
            line = _line_text(_text, m.start())
            for rx in skip_line_res:
                if rx.search(line):
                    return True
            return False

        # 统一：收集某一组 patterns 的全部候选命中（可限制搜索起点）
        def _collect_hits(pats: List[re.Pattern], _text: str, start_at: int = 0, *, kind: str = "start") -> Tuple[List[Dict[str, Any]], int]:
            """
            返回 (hits, skipped_count)
            hit 结构保持你原来的字段，但额外加 line 方便调试
            """
            hits: List[Dict[str, Any]] = []
            skipped = 0

            for i, pat in enumerate(pats):
                # finditer：让每个 pattern 有多个候选（目录一条、正文一条）
                try:
                    it = pat.finditer(_text, start_at)
                except TypeError:
                    # 兼容老 python：finditer(text, pos) 不支持时兜底
                    it = pat.finditer(_text[start_at:])
                    # 注意：这种兜底需要位移
                    for m in it:
                        # 位移修正
                        fake_start = start_at + m.start()
                        fake_end = start_at + m.end()
                        # 构造一个“类 match”信息
                        # 这里不强造 match 对象了，直接走命中判断用 line
                        line = _line_text(_text, fake_start)
                        if skip_line_res and any(rx.search(line) for rx in skip_line_res):
                            skipped += 1
                            continue
                        hits.append({"idx": i, "pat": pat.pattern, "pos": fake_start, "end": fake_end, "match": m.group(0), "line": line, "kind": kind})
                    continue

                for m in it:
                    if _should_skip_by_line(_text, m):
                        skipped += 1
                        if self.debug:
                            print(f"   ⛔ skip({kind}) pos={m.start()} line={_line_text(_text, m.start())[:120]!r}")
                        continue
                    hits.append(
                        {
                            "idx": i,
                            "pat": pat.pattern,
                            "pos": m.start(),
                            "end": m.end(),
                            "match": m.group(0),
                            "line": _line_text(_text, m.start()),
                            "kind": kind,
                        }
                    )
            return hits, skipped

        # 选择命中：priority（pattern 优先）/ earliest（位置优先）
        def _pick_hit(hits: List[Dict[str, Any]]) -> Dict[str, Any] | None:
            if not hits:
                return None
            if pick == "priority":
                # 先 idx，再 pos：同一 pattern 出现多次，取更早的那次
                return min(hits, key=lambda h: (h["idx"], h["pos"]))
            # 默认 earliest
            return min(hits, key=lambda h: h["pos"])

        # 1) start hits（全局收集，过滤目录行）
        start_hits, start_skipped = _collect_hits(start_pats, text, 0, kind="start")
        if not start_hits:
            return []

        start_hit = _pick_hit(start_hits)
        if not start_hit:
            return []

        start_pos = start_hit["pos"] if include_start else start_hit["end"]

        # 2) end hits（从 start_pos 之后收集，过滤目录行）
        end_hits, end_skipped = _collect_hits(end_pats, text, start_pos, kind="end")

        if end_hits:
            end_hit = _pick_hit(end_hits) if pick == "priority" else min(end_hits, key=lambda h: h["pos"])
            # end 的 priority 通常也可以用 idx 优先，但为了与你原逻辑一致，上面写得更保守：
            # - 如果 pick == priority：_pick_hit 会按 idx/pos
            # - 如果 pick != priority：按 pos 最早
            end_pos = end_hit["end"] if include_end else end_hit["pos"]
        else:
            if fallback_end_chars > 0:
                end_pos = min(len(text), start_pos + fallback_end_chars)
            else:
                end_pos = len(text)
            end_hit = None

        chunk = text[start_pos:end_pos].strip()
        if not chunk:
            return []

        # ✅ 可观测性：给你一个轻量 preview（不污染正文）
        start_line_preview = (start_hit.get("line") or "")[:180]
        end_line_preview = ((end_hit or {}).get("line") or "")[:180]

        return [
            ReportSection(
                key=step.key,
                title=step.key,
                text=chunk,
                metadata={
                    "mode": step.mode,
                    "base_scope": base_scope,
                    "base_idx": base_idx,
                    "ruleset": self.ruleset.name,
                    "pick": pick,
                    "include_start": include_start,
                    "include_end": include_end,
                    "fallback_end_chars": fallback_end_chars,
                    "skip_if_line_matches": skip_line_patterns,
                    "skipped_by_line": {
                        "start": start_skipped,
                        "end": end_skipped,
                    },
                    "start": start_hit,
                    "end": end_hit,
                    "start_candidates": len(starts),
                    "end_candidates": len(ends),
                    "start_hits": len(start_hits),
                    "end_hits": len(end_hits),
                    "start_line_preview": start_line_preview,
                    "end_line_preview": end_line_preview,
                },
            )
        ]
    
    def _looks_like_md_table(self, s: str, *, min_rows: int = 3) -> bool:
        if not s:
            return False
        if "| ---" in s or "|---" in s:
            return True
        lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
        pipe_lines = sum(1 for ln in lines if ln.startswith("|"))
        return pipe_lines >= min_rows

    def _grab_table_after_heading(self, text: str, heading: str, *, max_chars: int = 8000) -> str:
        pos = text.find(heading)
        if pos < 0:
            return ""
        tail = text[pos : pos + max_chars]
        lines = tail.splitlines()

        out: List[str] = []
        in_table = False
        started_at = None

        for ln in lines:
            s = ln.strip()

            # 表格尚未开始：先把标题/说明行都收进来，直到遇到第一行表格
            if not in_table:
                out.append(ln)
                if s.startswith("|"):
                    in_table = True
                    started_at = len(out) - 1
                continue

            # 表格开始后：
            # 1) 允许空行（有些清洗会插空行），但空行不作为结束
            if s == "":
                out.append(ln)
                continue

            # 2) 只要遇到“不是表格行”，就结束
            if not s.startswith("|"):
                break

            out.append(ln)

        # 如果根本没进表格，返回空（避免只返回标题）
        if not in_table:
            return ""

        # 可选：只返回从表格开始那一行起（不要标题），看你需求
        return "\n".join(out[started_at:]).strip()

    def _by_table_after(self, step: SliceStep, text: str, p: Dict[str, Any], base_scope: str, base_idx: int) -> List[ReportSection]:
        max_table_chars = int(p.get("max_table_chars") or 12000)
        min_table_rows = int(p.get("min_table_rows") or 3)

        out: List[ReportSection] = []
        for i, heading in enumerate(step.targets):
            grabbed = self._grab_table_after_heading(text, heading, max_chars=max_table_chars)
            if not grabbed:
                continue
            if not self._looks_like_md_table(grabbed, min_rows=min_table_rows):
                # 这个打印对调参很有用：知道“命中了标题但不是表”
                # 注意：不要太吵，默认 debug 才会打印
                # self._dbg 在上层 run_step 里，这里直接返回结构即可
                continue

            out.append(
                ReportSection(
                    key=step.key,
                    title=heading,
                    text=grabbed,
                    metadata={
                        "mode": step.mode,
                        "heading": heading,
                        "match_index": i,
                        "base_scope": base_scope,
                        "base_idx": base_idx,
                        "ruleset": self.ruleset.name,
                    },
                )
            )
        return out

    def _by_window_after(
        self,
        step: SliceStep,
        text: str,
        p: Dict[str, Any],
        base_scope: str,
        base_idx: int,
    ) -> List[ReportSection]:
        window_chars = int(p.get("window_chars") or 12000)
        pick = (p.get("anchor_pick") or "earliest").lower()   # "earliest" | "priority"
        use_regex = bool(p.get("anchor_regex", False))

        targets = [t for t in (step.targets or []) if isinstance(t, str) and t.strip()]
        if not targets:
            return []

        hits = []  # [(pos, anchor, extra)]
        if use_regex:
            for t in targets:
                try:
                    m = re.search(t, text, flags=re.I)
                except re.error:
                    m = None
                if m:
                    hits.append((m.start(), t, {"match": m.group(0)}))
        else:
            for t in targets:
                pos = text.find(t)
                if pos >= 0:
                    hits.append((pos, t, {}))

        if not hits:
            return []

        # 选择锚点
        if pick == "priority":
            # 按 targets 顺序：第一个命中的
            # hits 里已经按 targets 遍历顺序 append，直接取第一个即可
            pos, anchor, extra = hits[0]
        else:
            # 默认：选最早出现的
            pos, anchor, extra = min(hits, key=lambda x: x[0])
        
        end = min(len(text), pos + window_chars)
        win = text[pos:end]

        return [
            ReportSection(
                key=step.key,
                title=f"window_after:{anchor}",
                text=win,
                metadata={
                    "mode": step.mode,
                    "anchor": anchor,
                    "anchor_pick": pick,
                    "anchor_regex": use_regex,
                    "window_chars": window_chars,
                    "base_scope": base_scope,
                    "base_idx": base_idx,
                    "ruleset": self.ruleset.name,
                    "hit_count": len(hits),
                    "hits": [{"pos": h[0], "anchor": h[1], **h[2]} for h in hits[:20]],  # 防止过大
                    **extra,
                },
            )
        ]

    def _compile_patternlikes(self, patterns: Iterable[Any]) -> List[re.Pattern]:
        """允许 targets 里同时传 regex 字符串 / re.Pattern"""
        out: List[re.Pattern] = []
        src = list(patterns or [])
        if self.debug:
            print(f"   🧪 compile_patternlikes: in={len(src)}")

        for i, p in enumerate(src):
            if isinstance(p, re.Pattern):
                out.append(p)
                if self.debug:
                    print(f"      ✅ pat[{i}] re.Pattern: {p.pattern!r}")
            elif isinstance(p, str) and p.strip():
                try:
                    rx = re.compile(p, re.I | re.M)
                    out.append(rx)
                    if self.debug:
                        print(f"      ✅ pat[{i}] compiled: {p!r}")
                except re.error as e:
                    if self.debug:
                        print(f"      ❌ pat[{i}] bad regex: {p!r} err={e}")
                    continue
            else:
                if self.debug:
                    print(f"      ⛔ pat[{i}] ignored: type={type(p).__name__} value={p!r}")

        if self.debug:
            print(f"   🧪 compile_patternlikes: out={len(out)}")
        return out


    def _by_segment_tables(
        self,
        step: SliceStep,
        text: str,
        p: Dict[str, Any],
        base_scope: str,
        base_idx: int,
    ) -> List[ReportSection]:
        """
        段内表格抽取：
        - 对 step.targets 逐个 regex 找 block（find_blocks_by_pattern）
        - 如果 block 只是标题（短、含“表”），向下抓表
        - 用 _looks_like_md_table 过滤
        - truncate + 去重
        """
        max_table_chars = int(p.get("max_table_chars") or 12000)
        min_table_rows = int(p.get("min_table_rows") or 3)
        max_hits_per_pattern = int(p.get("max_hits_per_pattern") or 0)  # 0=不限（建议调试期先不限）

        patterns = self._compile_patternlikes(step.targets or [])
        if self.debug:
            print(
                f"   🧩 by_segment_tables: step={step.key} scope={base_scope} idx={base_idx} "
                f"text_len={len(text)} patterns={len(patterns)} "
                f"max_table_chars={max_table_chars} min_table_rows={min_table_rows} max_hits_per_pattern={max_hits_per_pattern or '∞'}"
            )

        if not patterns:
            if self.debug:
                print("   ⚠️ by_segment_tables: no valid patterns -> return []")
            return []

        out: List[ReportSection] = []
        seen = set()

        # 统计：帮助你判断到底卡在哪个环节
        stat_blocks = 0
        stat_raw_nonempty = 0
        stat_title_like = 0
        stat_grabbed = 0
        stat_table_pass = 0
        stat_table_fail = 0
        stat_dedup_skip = 0
        stat_truncated = 0

        for pi, pat in enumerate(patterns):
            if self.debug:
                print(f"   🔍 pattern[{pi}]={pat.pattern!r}")

            blocks = find_blocks_by_pattern(text, pat)

            if self.debug:
                print(f"      📦 blocks_found={len(blocks)}")

            if not blocks:
                # 关键诊断：pattern 是否至少能在 text 里匹配到？
                # 这不改变逻辑，只告诉你是“pattern没命中”还是“命中但 find_blocks 不产块”
                m = None
                try:
                    m = pat.search(text)
                except Exception as e:
                    if self.debug:
                        print(f"      ❌ pat.search error: {e}")

                if self.debug:
                    if m:
                        ls = text.rfind("\n", 0, m.start()) + 1
                        le = text.find("\n", m.start())
                        if le == -1:
                            le = len(text)
                        line = text[ls:le]
                        print(f"      ⚠️ regex_match_yes_but_blocks_0 pos={m.start()} line={line[:160]!r}")
                    else:
                        print("      ⚠️ regex_match_no (pattern not found in text)")
                continue

            stat_blocks += len(blocks)

            if max_hits_per_pattern and len(blocks) > max_hits_per_pattern:
                if self.debug:
                    print(f"      ✂️ cap blocks {len(blocks)} -> {max_hits_per_pattern}")
                blocks = blocks[:max_hits_per_pattern]

            for i, b in enumerate(blocks):
                title = b.get("title") or b.get("kind", "snippet")
                raw = (b.get("text") or "").strip()
                kind = b.get("kind")

                if self.debug:
                    print(f"      ➤ block[{i}] kind={kind!r} title={str(title)[:60]!r} raw_len={len(raw)}")

                if not raw:
                    if self.debug:
                        print("         ⛔ skip: raw empty")
                    continue

                stat_raw_nonempty += 1
                expanded = raw
                did_expand = False

                # 1) 如果只是标题段：尝试向下抓表
                is_title_like = (len(raw) <= 40 and ("表" in raw))
                if is_title_like:
                    stat_title_like += 1
                    if self.debug:
                        print(f"         🧷 title_like=yes raw={raw[:80]!r}")

                    grabbed = self._grab_table_after_heading(
                        text,
                        raw,
                        max_chars=min(max_table_chars, 8000),
                    )
                    if grabbed:
                        expanded = grabbed
                        did_expand = True
                        stat_grabbed += 1
                        if self.debug:
                            print(f"         ✅ grabbed_table len={len(grabbed)} preview={self._preview(grabbed)}")
                    else:
                        if self.debug:
                            print("         ⚠️ grabbed_table=empty")

                # 2) 过滤：必须像表
                ok = self._looks_like_md_table(expanded, min_rows=min_table_rows)
                if not ok:
                    stat_table_fail += 1
                    if self.debug:
                        lines = [ln.strip() for ln in expanded.splitlines() if ln.strip()]
                        pipe_lines = sum(1 for ln in lines if ln.startswith("|"))
                        has_sep = ("|---" in expanded) or ("| ---" in expanded)
                        print(
                            f"         ⛔ looks_like_table=NO pipe_lines={pipe_lines} has_sep={has_sep} "
                            f"expanded_len={len(expanded)} preview={self._preview(expanded)}"
                        )
                    continue

                stat_table_pass += 1
                if self.debug:
                    print(f"         ✅ looks_like_table=YES expanded={did_expand} expanded_len={len(expanded)}")

                # 3) 截断
                truncated = False
                if max_table_chars and len(expanded) > max_table_chars:
                    expanded = expanded[:max_table_chars]
                    truncated = True
                    stat_truncated += 1
                    if self.debug:
                        print(f"         ✂️ truncated to {max_table_chars}")

                # 4) 去重
                sig = (expanded[:200], pat.pattern, base_scope, base_idx)
                if sig in seen:
                    stat_dedup_skip += 1
                    if self.debug:
                        print("         🧹 dedup_skip")
                    continue
                seen.add(sig)

                out.append(
                    ReportSection(
                        key=step.key,
                        title=str(title),
                        text=expanded,
                        metadata={
                            "mode": step.mode,
                            "pattern": pat.pattern,
                            "kind": b.get("kind"),
                            "match_index": i,
                            "base_scope": base_scope,
                            "base_idx": base_idx,
                            "ruleset": self.ruleset.name,
                            "expanded": expanded != raw,
                            "truncated": truncated,
                            "max_table_chars": max_table_chars,
                            "min_table_rows": min_table_rows,
                        },
                    )
                )

        if self.debug:
            print(
                "   📊 by_segment_tables summary: "
                f"blocks={stat_blocks} raw_nonempty={stat_raw_nonempty} "
                f"title_like={stat_title_like} grabbed={stat_grabbed} "
                f"table_pass={stat_table_pass} table_fail={stat_table_fail} "
                f"dedup_skip={stat_dedup_skip} truncated={stat_truncated} out={len(out)}"
            )

        return out
        
    
    def _dedup_sections(self, sections: List[ReportSection]) -> List[ReportSection]:
        seen = set()
        out: List[ReportSection] = []
        for s in sections:
            sig = (s.key, (s.title or "")[:80], (s.text or "")[:200])
            if sig in seen:
                continue
            seen.add(sig)
            out.append(s)
        return out