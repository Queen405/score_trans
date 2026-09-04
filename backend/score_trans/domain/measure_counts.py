"""声部小节数一致性校验（F5：合并 parse 层与 exec 层的重复实现）。

简谱多页文档里每页声部独立编号，跨页比较无意义，必须按 page_index 分组；
MusicXML 构建的声部 page_index 全为 0，自然归为一组。两种输入由此共用同一份逻辑。
"""

from __future__ import annotations

from ..models.score import JianpuScore


def find_measure_count_mismatch(
    scores: list[JianpuScore],
) -> tuple[int, str] | None:
    """返回第一个不一致页的 (page_index, 完整消息)；全一致返回 None。

    组内只有 1 个声部时跳过（与「单声部不校验」的旧行为一致）。
    多页文档的消息带「第 N 页」前缀，单页不带以保持向后兼容。
    """
    multi_page = len({score.page_index for score in scores}) > 1
    index = 0
    while index < len(scores):
        page_index = scores[index].page_index
        end = index
        while end < len(scores) and scores[end].page_index == page_index:
            end += 1
        group = scores[index:end]
        index = end
        if len(group) <= 1:
            continue
        counts = [len(score.measures) for score in group]
        if len(set(counts)) <= 1:
            continue
        details = "、".join(
            f"{score.part_name or f'声部{score.part_index + 1}'}={counts[i]}"
            for i, score in enumerate(group)
        )
        page_prefix = f"第 {page_index + 1} 页" if multi_page else ""
        return page_index, f"{page_prefix}各声部小节数量不一致：{details}"
    return None
