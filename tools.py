# tools.py · service-bot 的 5 个工具（毕设指导客服）
# 结构沿用 chat-api / week04 的套路：工具函数 + tools_schema（给模型看的说明书）+ ToolExecutor（执行器）
import json
import re
from datetime import datetime, timedelta
from pathlib import Path  # pathlib 文件操作，比手动拼路径干净

BASE_DIR = Path(__file__).parent  # 本文件所在目录，保证从任何地方启动都能找到数据文件


# ============ 工具 1：查学校政策 ============

def query_policy(category: str) -> dict:
    """按类别查政策库。类别模糊匹配：模型传'论文格式'也能命中'格式规范'"""
    with open(BASE_DIR / "policies.json", encoding="utf-8") as f:  # 每次现读，改数据不用重启
        policies = json.load(f)

    # 精确命中 → 直接返回
    if category in policies:
        return {"category": category, "content": policies[category]}

    # 模糊匹配：任一方包含另一方就算命中（"查重率"→"查重"）
    for key in policies:
        if key in category or category in key:
            return {"category": key, "content": policies[key]}

    # 没命中 → 把可选类别告诉模型，让它自己纠正后再问（工具容错的一部分）
    return {"error": f"没有'{category}'这个类别", "可选类别": list(policies.keys())}


# ============ 工具 2：查文书写作指南 ============

def get_writing_guide(doc_type: str) -> dict:
    """返回 guides/ 目录下对应文书的 Markdown 全文"""
    guide_path = BASE_DIR / "guides" / f"{doc_type}.md"
    if not guide_path.exists():
        available = [p.stem for p in (BASE_DIR / "guides").glob("*.md")]  # stem=去掉扩展名的文件名
        return {"error": f"暂无'{doc_type}'的写作指南", "已有指南": available}
    return {"doc_type": doc_type, "guide": guide_path.read_text(encoding="utf-8")}


# ============ 工具 3：选题可行性初筛（规则判断） ============

# 负面清单：命中任何一条直接判"不建议"
NEGATIVE_KEYWORDS = ["代写", "买论文", "包过", "枪手", "帮我写论文"]
# "题目太大"黑名单：这些词出现在题目里通常意味着只有大方向没有具体问题
TOO_BROAD_KEYWORDS = ["发展现状", "发展研究", "浅析", "浅谈", "综述", "的研究"]


def check_topic_feasibility(topic: str, major: str) -> dict:
    """纯规则初筛（不调 LLM）：返回 可行/需修改/不建议 + 理由 + 建议"""
    problems = []
    suggestions = []

    # 规则 1：学术不端一票否决
    for kw in NEGATIVE_KEYWORDS:
        if kw in topic:
            return {"verdict": "不建议", "reasons": [f"题目或诉求涉及'{kw}'，属于学术不端"], "suggestions": ["请自己完成研究，可咨询导师确定选题方向"]}

    # 规则 2：长度合理区间（太短=信息量不足，太长=没抓住重点）
    if len(topic) < 6:
        problems.append("题目太短，看不出研究对象和要解决的问题")
    if len(topic) > 40:
        problems.append("题目太长（超过40字），通常说明没有聚焦到具体问题")

    # 规则 3：大方向词黑名单
    for kw in TOO_BROAD_KEYWORDS:
        if kw in topic:
            problems.append(f"包含'{kw}'这类大方向词，容易写成资料汇总")
            suggestions.append(f"把'{kw}'换成具体的技术手段或切入点，如'基于X的Y设计与实现'")
            break  # 提一次就够，不刷屏

    # 规则 4：建议带限定词（基于/面向/针对 = 有场景有方法）
    if not any(kw in topic for kw in ["基于", "面向", "针对", "设计", "实现", "分析"]):
        suggestions.append("题目最好带'基于/面向/针对'等限定词，缩小到可完成的范围")

    if problems:
        verdict = "需修改"
    else:
        verdict = "可行"
        suggestions.append("题目结构清晰。建议再和导师确认一次方向是否与专业培养目标一致")

    return {"verdict": verdict, "major": major, "reasons": problems, "suggestions": suggestions}


# ============ 工具 4：时间规划（今天由工具自己算，不让模型传） ============

def get_timeline_template(deadline: str) -> dict:
    """根据答辩截止日期，把剩余天数按比例切成 4 个阶段。deadline 支持 '2026-06-01' 或 '6月1日' 格式"""
    today = datetime.now()  # 关键设计：日期自己算。模型根本不知道今天几号，传出来大概率是编的

    # 宽松解析日期：先试标准格式，再试中文格式
    for fmt in ["%Y-%m-%d", "%Y年%m月%d日"]:
        try:
            deadline_dt = datetime.strptime(deadline.strip(), fmt)
            break
        except ValueError:
            deadline_dt = None
    if deadline_dt is None:  # 再试 "6月1日" / "6月10号" 这种不带年份的
        m = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", deadline)
        if m:
            deadline_dt = datetime(today.year, int(m.group(1)), int(m.group(2)))
            if deadline_dt < today:  # 不带年份且已过 → 顺理成章是明年
                deadline_dt = datetime(today.year + 1, int(m.group(1)), int(m.group(2)))
    if deadline_dt is None:
        return {"error": f"看不懂截止日期'{deadline}'", "格式提示": "请传 2026-06-01 或 6月1日 格式"}

    days_left = (deadline_dt - today).days
    if days_left < 0:
        return {"error": f"截止日期 {deadline_dt.date()} 已经过去了", "suggestion": "请确认日期或直接转人工处理"}
    if days_left < 14:
        return {"days_left": days_left, "warning": "剩余不足两周，已来不及走完整流程，建议直接准备答辩材料并咨询导师"}

    # 阶段划分：研究/实现 40% → 写作 30% → 查重修改 15% → 答辩准备 15%
    phases = [
        ("研究与实现（核心实验/开发）", 0.40),
        ("论文写作（初稿各章）", 0.30),
        ("查重与修改（初稿→定稿）", 0.15),
        ("答辩准备（PPT+预演）", 0.15),
    ]
    plan = []
    cursor = today
    for name, ratio in phases:
        phase_days = max(1, int(days_left * ratio))  # 至少 1 天，防止四舍五入成 0
        end = min(cursor + timedelta(days=phase_days), deadline_dt)
        plan.append({"阶段": name, "起": str(cursor.date()), "止": str(end.date()), "天数": (end - cursor).days})
        cursor = end

    return {"today": str(today.date()), "deadline": str(deadline_dt.date()), "days_left": days_left, "plan": plan}


# ============ 工具 5：转人工 ============

def transfer_to_human(reason: str) -> dict:
    """打印转接话术并返回标记。main.py 的循环看到 transferred=true 就该结束，不再追问模型"""
    print(f"\n📞 转人工 | 原因: {reason}")
    print("   好的，已为您转接对应老师，请稍候……（演示：此处为转接动作）")
    return {"transferred": True, "reason": reason}


# ============ tools schema：给模型看的 5 张说明书 ============

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "query_policy",
            "description": "查询学校毕设相关政策规定（查重率、中期检查、格式规范、延期申请、答辩安排等）。凡是学校有什么规定、要求、流程的问题都用这个工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["查重", "中期检查", "格式规范", "延期申请", "答辩安排"],
                        "description": "政策类别，从枚举里选最接近的一个"
                    }
                },
                "required": ["category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_writing_guide",
            "description": "获取各类毕设文书（开题报告、任务书等）的写作指南。用户问某类文书'怎么写''包含哪些部分''有什么注意点'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {
                        "type": "string",
                        "enum": ["开题报告", "任务书"],
                        "description": "文书类型"
                    }
                },
                "required": ["doc_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_topic_feasibility",
            "description": "对毕业设计选题做可行性初筛（规则判断），返回可行/需修改/不建议及改进建议。用户问'我这个选题行不行''题目这样定好吗'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "用户的毕设题目原文"},
                    "major": {"type": "string", "description": "用户的专业，如：计算机科学与技术"}
                },
                "required": ["topic", "major"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeline_template",
            "description": "根据答辩截止日期生成阶段时间规划。用户说'来不及了''帮我排计划''还有多久要做什么'时使用。截止日期从用户消息里提取，不要猜测。",
            "parameters": {
                "type": "object",
                "properties": {
                    "deadline": {"type": "string", "description": "答辩截止日期，格式 2026-06-01 或 6月1日；用户没说就先追问，不要编造"}
                },
                "required": ["deadline"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "转接人工。遇到：需要教务处/学院人工审批的事项（如延期申请办手续）、用户情绪严重崩溃、用户主动要求转人工、Agent 确实无权限办理的事。调用后本轮回结束。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "转人工的原因，如：延期审批需线下办理"}
                },
                "required": ["reason"]
            }
        }
    }
]


# ============ 工具执行器：名字 → 函数 的路由 ============

class ToolExecutor:
    def __init__(self):
        self.function_map = {
            "query_policy": query_policy,
            "get_writing_guide": get_writing_guide,
            "check_topic_feasibility": check_topic_feasibility,
            "get_timeline_template": get_timeline_template,
            "transfer_to_human": transfer_to_human,
        }

    def execute(self, tool_name: str, arguments: dict) -> str:
        """执行工具。任何异常都包成错误 JSON 返回——让模型看到错误自己调整，而不是整个循环崩掉"""
        if tool_name not in self.function_map:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
        try:
            result = self.function_map[tool_name](**arguments)  # 参数字典解包成关键字参数
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"工具 {tool_name} 执行出错: {type(e).__name__}: {e}"}, ensure_ascii=False)
