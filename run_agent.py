from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name(".env"))
from deep_research_agent.graph import graph

def main():
    topic = input("请输入研究主题：").strip()

    if not topic:
        print("研究主题不能为空。")
        return

    print("\n正在研究，请稍候……")

    result = graph.invoke(
        {"research_topic": topic},
        config={
            "configurable": {
                "ddgs_backend": "yahoo",
                "max_web_research_loops": 0,
                "fetch_full_page": False,
            },
            "recursion_limit": 15,
        },
    )

    print("\n===== 研究报告 =====")
    print(result["running_summary"])

if __name__ == "__main__":
    main()