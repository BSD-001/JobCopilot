"""新版网页离线验收数据，全部为中性虚构材料。"""

from __future__ import annotations


SAMPLE_RESUME = "示例求职者，示例学校本科。参与需求记录整理，制作并交付3份项目说明。"
SAMPLE_JD = "产品助理：整理需求文档，协助项目推进与验收。"


class WebFakeClient:
    def __init__(self, api_key=None):
        pass

    def generate_json(self, system_prompt, user_prompt, **kwargs):
        if "请解析简历文本" in user_prompt:
            return {"education": [{"school": "示例学校"}], "skills": ["文档整理"], "projects": [{"name": "需求记录整理", "results": ["交付3份项目说明"]}], "experiences": []}
        if "请解析岗位描述" in user_prompt:
            return {"job_title": "产品助理", "requirements": ["文档整理"], "responsibilities": ["协助验收"], "keywords": ["需求分析"]}
        if "匹配度评分" in user_prompt:
            return {"score": 73, "matched_points": ["有需求文档整理与交付经验"], "missing_points": ["缺少明确的验收记录"], "reason": "已有文档基础，需补充验收实践证据。"}
        if "请针对目标岗位重写" in user_prompt:
            return {"optimized_projects": [{"title": "需求记录整理", "content": "【文档交付】整理需求记录，制作并交付3份项目说明。"}], "pending_items": ["需求记录整理：补充项目使用反馈。"]}
        if "十个高频面试问题" in user_prompt:
            return {"questions": [{"question": f"问题{index}：你如何确认需求记录准确？", "answer": "先记录原始需求，再请相关人员核对，保留变更说明。", "focus": "事实核验与沟通"} for index in range(1, 11)]}
        if "三十天学习计划" in user_prompt:
            return {"weeks": [{"week": index, "goal": f"完成第{index}周需求实践", "tasks": ["阅读需求说明", "整理验收检查项"], "deliverable": "一份脱敏练习文档"} for index in range(1, 5)], "summary": "从文档整理到验收实践，逐步补齐证据。"}
        if "resume_blocks" in user_prompt:
            return {"replacements": [{"block_id": 1, "original_text": "制作并交付3份项目说明。", "new_text": "【文档交付】整理需求记录，制作并交付3份项目说明。", "kind": "experience", "reason": "明确动作与结果"}], "removals": [], "skill_boosts": [], "pending_items": [], "summary": "保留真实文档成果。"}
        if "招聘平台 HR" in user_prompt:
            return {"greeting": "您好，我应聘产品助理。我有需求文档整理经验，方便看下简历吗？"}
        raise AssertionError("未识别的离线任务")

    def generate_text(self, system_prompt, user_prompt, **kwargs):
        return "# 求职分析报告\n\n## 匹配分析\n\n基础方向匹配。\n\n## 简历优化建议\n\n模型扩写内容，应被结构化建议替换。\n\n## 面试题\n\n请核对事实。\n\n## 30天学习计划\n\n按周完成练习。"
