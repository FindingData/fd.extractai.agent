import os

def load_prompt(prompt_name: str) -> str:
    # 自动寻找 prompts 目录下对应文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(script_dir, "..", "prompts")
    prompts_dir = os.path.abspath(prompts_dir)
    prompt_path = os.path.join(prompts_dir, prompt_name)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()