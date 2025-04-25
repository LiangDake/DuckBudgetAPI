from typing import Optional
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from alibabacloud_tea_openapi.models import Config
from alibabacloud_imagesearch20210501.client import Client as AliyunImageClient
from alibabacloud_imagesearch20210501.models import SearchByUrlRequest, SearchByPicAdvanceRequest
from alibabacloud_tea_util.models import RuntimeOptions
from fastapi import FastAPI, File, UploadFile
from fastapi import FastAPI, Request, HTTPException, Header
from supabase import create_client, Client as SupabaseClient
import jwt
import os
from dotenv import load_dotenv

load_dotenv()  # 加载.env文件中的变量

app = FastAPI()


# 初始化阿里云客户端
def init_client():
    config = Config()
    config.access_key_id = os.getenv("ALIYUN_ACCESS_KEY_ID")
    config.access_key_secret = os.getenv("ALIYUN_ACCESS_KEY_SECRET")
    config.endpoint = os.getenv("ALIYUN_ENDPOINT")
    config.region_id = os.getenv("ALIYUN_REGION")
    return AliyunImageClient(config)



@app.post("/search_local_pic")
async def search_local_pic(file: UploadFile = File(...)):
    try:
        client = init_client()
        runtime_option = RuntimeOptions()

        # 1. 保存图片到本地临时路径
        contents = await file.read()
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(contents)

        # 2. 读取并发送给阿里云
        request = SearchByPicAdvanceRequest()
        with open(temp_path, 'rb') as image_file:
            request.pic_content_object = image_file
            request.pid = "mm_7693888200_3267300010_115996650080"
            request.fields = "Title,ReservePrice"
            response = client.search_by_pic_advance(request, runtime_option)
            result = response.body.data.auctions[0].result

        return {
            "title": result.title,
            "price": result.reserve_price,
            "hello": result.title
        }

    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


# 请求参数模型
class ImageSearchRequest(BaseModel):
    pic_url: str
    pid: Optional[str] = "mm_7693888200_3267300010_115996650080"
    fields: Optional[str] = "Title,ReservePrice"
    start: Optional[int] = 0
    num: Optional[int] = 1


@app.post("/search_by_url")
async def search_by_url(data: ImageSearchRequest):
    try:
        client = init_client()
        request = SearchByUrlRequest()
        request.pic_url = data.pic_url
        request.pid = data.pid
        request.fields = data.fields
        request.start = data.start
        request.num = data.num

        response = client.search_by_url(request)
        result = response.body.data.auctions[0].result

        return {
            "title": result.title,
            "price": result.reserve_price
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# 阿里云百炼 Qwen API 配置
client = OpenAI(
    api_key=os.getenv("QWEN_API_KEY"),
    base_url=os.getenv("QWEN_API_BASE"),
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
                    "content": "You are an assistant who helps users simplify product names, only return concise "
                               "product titles, remove irrelevant words, such as promotional words, advertising "
                               "words, etc., maintain the original language output and no more than 15 words.",
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


# 请求结构
class SuggestRequest(BaseModel):
    itemName: str
    itemPrice: float
    difficulty: int  # 1: 温和, 2: 中肯, 3: 严厉


class SuggestResponse(BaseModel):
    suggestion: str


@app.post("/purchase_suggest", response_model=SuggestResponse)
async def purchase_suggest(req: SuggestRequest):
    try:
        body = req.json()
        print("收到请求体:", body)
        tone_map = {
            1: "in a gentle and considerate tone",
            2: "in a rational and relevant tone",
            3: "in a stern and direct tone"
        }
        tone_instruction = tone_map.get(req.difficulty, "in a rational and relevant tone")
        prompt = (
            f'You are a consumer psychology consultant who is good at dissuading users from shopping impulsively. '
            f'The user now intends to buy "{req.itemName}" at a price of {req.itemPrice}元.\n\n'
            f'Please give a short and convincing suggestion {tone_instruction}，including:\n'
            f'1. Why this product may not be worth buying;\n'
            f'2. What are the alternatives?\n'
            f'3. How to prevent falling into the consumption.\n\n'
            f'Directly return to the Chinese suggested text, do not use Markdown or code blocks.'
        )

        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
            ],
        )

        result = completion.choices[0].message.content.strip()
        return {"suggestion": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestion Failed: {str(e)}")


# 请求结构
class CombinedRequest(BaseModel):
    title: str
    price: float


# 响应结构
class CombinedResponse(BaseModel):
    simple_title: str
    suggestion: str


@app.post("/simplify_suggest_combined", response_model=CombinedResponse)
async def analyze_purchase_combined(req: CombinedRequest):
    try:
        # 合并后的提示词
        prompt = [
            {
                "role": "system",
                "content": (
                    "你是一个消费心理顾问和商品标题优化助手。\n\n"
                    "首先，请将以下商品标题简化，去除广告词、品牌宣传等冗余内容，只保留核心商品信息。\n\n"
                    f"原始标题：{req.title}\n"
                    f"价格：{req.price} 元\n\n"
                    "然后，基于简化后的标题和价格，给出以下三个方面的理性消费建议：\n"
                    "为什么现在可能不值得买？\n"
                    "有哪些替代方案？\n"
                    "如何理性对待这次消费冲动？\n\n"
                    "请使用以下格式回答：\n"
                    "简洁名称：xxx\n"
                    "消费建议：xxx\n\n"
                    "请用中文直接返回结果，不要使用Markdown或代码块。"
                ),
            }
        ]

        response = client.chat.completions.create(
            model="qwen-plus",
            messages=prompt,
        )

        content = response.choices[0].message.content.strip()

        # 解析输出
        simple_title = ""
        suggestion = ""
        if "简洁名称：" in content and "消费建议：" in content:
            try:
                parts = content.split("消费建议：", 1)
                simple_title = parts[0].replace("简洁名称：", "").strip()
                suggestion = parts[1].strip()
            except Exception as parse_err:
                raise HTTPException(status_code=500, detail="模型输出解析失败")

        else:
            raise HTTPException(status_code=500, detail="模型输出格式异常")

        return {
            "simple_title": simple_title,
            "suggestion": suggestion
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)



@app.post("/api/delete-user")
async def delete_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid token payload")
        supabase.auth.admin.delete_user(user_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")