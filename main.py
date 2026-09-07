# main.py · service-bot 毕设指导客服 Agent
# 结构：week04 的 run_agent 改造 → 多轮对话版（客服要能接着聊）
import os
import json
import httpx  # type: ignore
from dotenv import load_dotenv  # type: ignore
from tools import tools_schema, ToolExecutor

load_dotenv()
api_key = os.environ.get("DEEPSEEK_API_KEY", "")
if not api_key:
    raise SystemExit("没找到 DEEPSEEK_API_KEY：在 .env 里写一行 DEEPSEEK_API_KEY=sk-你的key")

SYSTEM_PROMPT = """你是"毕小助"，毕业设计指导客服，语气亲切、回答简洁。

职责：解答毕设流程问题（查政策、写作指南、选题初筛、时间规划）。

规则：
1. 学校规定、政策、流程类问题 → 调 query_policy 查了再答，不许凭记忆编
2. 文书怎么写 → 调 get_writing_guide，基于指南内容回答
3. 用户问选题行不行 → 调 check_topic_feasibility
4. 用户着急排计划 → 调 get_timeline_template（截止日期从用户消息里找，没说就先追问）
5. 涉及审批办手续（延期申请交材料等）→ 调 transfer_to_human，并告知用户需线下办理
6. 用户情绪严重崩溃或主动要求转人工 → 调 transfer_to_human
7. 有人请你代写论文 → 拒绝并说明属于学术不端，建议咨询导师；语气坚定但不指责
8. 概念解释、经验建议类问题（如"任务书和开题报告有啥区别"）→ 直接回答，不要调工具
"""

executor = ToolExecutor()

# 多轮记忆：messages 放在函数外面、跨轮共享——这就是"短期记忆"本体
messages = [{"role": "system", "content": SYSTEM_PROMPT}]
MAX_ITERATIONS = 5  # 保险丝：单轮提问最多转 5 圈


def handle_one_question(question: str) -> None:
    """处理用户一条提问：内层 ReAct 循环跑完（答完或转人工）就返回"""
    # 填空①：把用户这句话存进 messages（role 是什么？）
    messages.append({"role": "user", "content": question})

    for i in range(MAX_ITERATIONS):
        response = httpx.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": messages,   # 填空②：为什么这里不用重新拼 messages，直接传整个列表？
                "tools": tools_schema,
                "tool_choice": "auto",
            },
            timeout=60,
        )
        if response.status_code != 200:
            print(f"DeepSeek 调用失败: {response.text}")
            return

        message = response.json()["choices"][0]["message"]

        # 填空③：模型不要工具了 = 答完了。做什么（存档？打印？返回？）
        # 提示：和 week04 的出口一样，但多轮版必须把这条 assistant 消息也 append 进 messages，
        #       不然下一轮模型就"失忆"了（你 chat-api 踩过这个坑的变体）
        if not message.get("tool_calls"):
            messages.append(message)  # 存档 assistant 的回答
            print(f"毕小助: {message.get('content')}")
            return

        messages.append(message)  # 模型"我要调工具"的发言先存档（week04 已会）

        # 执行工具 + 回填 + trace
        for tool_call in message.get("tool_calls", []):
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])
            print(f"[第{i+1}轮] 🔧 {function_name}({function_args})")

            # 填空④：解析参数、执行工具、把结果 append 回 messages（week04 那三行，原样搬）
            # 注意：json.loads 包 try/except，失败就把错误信息当工具结果回填（你笔记里的坑②）
            messages.append({
                "tool_call_id": tool_call["id"],
                "role": "tool",
                "content": executor.execute(function_name, function_args),
            })
            try:
                function_args = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError:
                function_args = {"error": "参数不是合法 JSON"}


            # 填空⑤：转人工检测——工具名是 transfer_to_human 时，本轮对话该结束了。
            # 提示：最简单的判法是看 function_name；返回后别忘了 print 一句结束语
            if function_name == "transfer_to_human":
                print("（人工接管，本轮结束）")
                return

    


# ============ 程序入口：多轮对话循环 ============
print("毕小助上线！问点毕设的事吧（输入 q 退出）")
while True:
    user_input = input("\n你: ").strip()
    if user_input.lower() == "q":
        print("再见，祝答辩顺利！🎓")
        break
    if not user_input:
        continue
    handle_one_question(user_input)
