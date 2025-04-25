# import os
# from openai import OpenAI
#
# client = OpenAI(
#     # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
#     api_key="sk-622fa3ca710e4b99bc7029fb08c6d7a9",
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
# )
# completion = client.chat.completions.create(
#     model="qwen-plus",  # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
#     messages=[
#         {'role': 'system', 'content': '你是一个帮用户简化商品名称的助手，只返回简洁的商品标题，去掉无关词汇，比如促销词、广告词等。'},
#         {'role': 'user', 'content': ' `原始商品名称：正品卡哈特Carhartt 爱心字母LOGO冷帽 情侣款百搭保暖毛线针织帽，请返回简洁名称：'}],
# )
#
# print(completion.model_dump_json())

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os

app = FastAPI()

# 阿里云百炼 Qwen API 配置
client = OpenAI(
    api_key="sk-622fa3ca710e4b99bc7029fb08c6d7a9",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


# 请求数据结构
class TitleRequest(BaseModel):
    title: str


# 响应数据结构（可选）
class TitleResponse(BaseModel):
    simple: str


@app.post("/simplify_title", response_model=TitleResponse)
async def simplify_title(req: TitleRequest):
    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个帮用户简化商品名称的助手，只返回简洁的商品标题，去掉无关词汇，比如促销词、广告词等。",
                },
                {
                    "role": "user",
                    "content": f"原始商品名称：{req.title}，请返回简洁名称：",
                },
            ],
        )

        result = completion.choices[0].message.content.strip()
        return {"simple": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"简化失败: {str(e)}")
