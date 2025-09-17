# nodes.py
import json
import requests
import base64
import io
import os
from PIL import Image
import torch
import numpy as np
from server import PromptServer
from aiohttp import web


# Load the prompts JSON once, with proper path resolution and error handling
PROMPTS_JSON_PATH = os.path.join(os.path.dirname(__file__), "prompts.json")
try:
    with open(PROMPTS_JSON_PATH, 'r', encoding='utf-8') as f:
        PROMPTS_DATA = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"警告: 加载prompts.json失败 ({e})，使用空列表。")
    PROMPTS_DATA = []


class GoogleApiKeyNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "key_input": ("STRING", {
                    "default": "",
                    "display_name": "Google API Key Input"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("key",)
    FUNCTION = "execute"
    CATEGORY = "FrankAI"

    def execute(self, key_input):
        key = f"GKEY-{key_input}"
        return (key,)


class FrankApiKeyNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "key_input": ("STRING", {
                    "default": "",
                    "display_name": "FrankAI API Key Input"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("key",)
    FUNCTION = "execute"
    CATEGORY = "FrankAI"

    def execute(self, key_input):
        key = f"FKEY-{key_input}"
        return (key,)


class BananaMainNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "key": ("STRING", {"forceInput": True}),  # 只连接点，无输入框
                "prompt": ("STRING", {"forceInput": True}),  # 只连接点，无输入框
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "text")
    FUNCTION = "execute"
    CATEGORY = "FrankAI"

    def execute(self, images, key, prompt):
        # 检查必需输入
        if not key:
            empty_tensor = torch.zeros((1, 512, 512, 3))
            return (empty_tensor, "错误: 未提供API Key，请连接API Key节点")
        if not prompt:
            empty_tensor = torch.zeros((1, 512, 512, 3))
            return (empty_tensor, "错误: 未提供Prompt，请连接Prompt Selector节点")

        # 处理图像
        if len(images) == 0:
            raise ValueError("无输入图像")
        image_tensor = images[0].cpu().numpy()
        image_np = (image_tensor * 255).astype(np.uint8)
        if len(image_np.shape) == 3:
            if image_np.shape[2] == 3:  # RGB
                pil_image = Image.fromarray(image_np)
            elif image_np.shape[2] == 4:  # RGBA
                pil_image = Image.fromarray(image_np[:, :, :3])
            else:
                raise ValueError("图像格式不支持（期望RGB或RGBA）")
        else:
            raise ValueError("图像维度不支持")

        # 转换为bytes
        img_buffer = io.BytesIO()
        pil_image.save(img_buffer, format='PNG')
        img_bytes = img_buffer.getvalue()

        # 准备表单数据
        files = {'images': ('image.png', img_bytes, 'image/png')}
        data = {'key': key, 'prompt': prompt}

        # 发送POST请求
        try:
            response = requests.post(
                "https://yinothing.com/api/google/banana",
                files=files,
                data=data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            image_b64 = result.get("imageUrls")[0]
            text = result.get("text", "")
            if not image_b64:
                raise ValueError("API响应中无image_base64字段")
            
            # 【关键修改】处理Base64字符串
            # 1. 检查并移除常见的数据URI前缀
            if ',' in image_b64:
                # 只分割一次，并取逗号后面的部分
                image_b64 = image_b64.split(',', 1)[1]
            
            # 2. (可选但推荐) 补全Base64填充
            missing_padding = len(image_b64) % 4
            if missing_padding != 0:
                image_b64 += '=' * (4 - missing_padding)

            # 解码base64
            image_data = base64.b64decode(image_b64)
            pil_output = Image.open(io.BytesIO(image_data)).convert("RGB")

            # 转换为tensor
            output_np = np.array(pil_output).astype(np.float32) / 255.0
            output_tensor = torch.from_numpy(output_np).unsqueeze(0)

            return (output_tensor, text)

        except requests.exceptions.RequestException as e:
            empty_tensor = torch.zeros((1, 512, 512, 3))
            # 尝试获取API返回的message字段
            error_message = "Error: "
            try:
                if response.status_code:
                    error_message += f"HTTP {response.status_code} - "
                    if response.text:
                        error_data = response.json()
                        message = error_data.get("message", str(e))
                        if type(message) is dict:
                            error_message = f"Error: HTTP {message['status']} - "
                            message = message['name'] 
                        error_message += message
                    else:
                        error_message += str(e)
                else:
                    error_message += str(e)
            except ValueError:
                error_message += str(e)
            return (empty_tensor, error_message)


# --- 提示词选择节点 (最终API版) ---
class BananaPromptSelector:
    @classmethod
    def INPUT_TYPES(s):
        titles = [item["title"] for item in PROMPTS_DATA] if PROMPTS_DATA else ["(无提示词)"]
        default_prompt = PROMPTS_DATA[0]["prompt"] if PROMPTS_DATA else ""
        return {
            "required": {
                "title": (titles,),
                "prompt": ("STRING", {"default": default_prompt, "multiline": True}),
            },
            # hidden widget 已被移除
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "execute"
    CATEGORY = "FrankAI"

    def execute(self, title, prompt): # prompts_data 参数也已移除
        # 后端执行逻辑保持不变，它只信任 title
        final_prompt = next(
            (item["prompt"] for item in PROMPTS_DATA if item["title"] == title),
            ""
        )

        # 允许用户覆写
        default_prompt_for_selected_title = final_prompt
        if prompt != default_prompt_for_selected_title:
            all_default_prompts = {item["prompt"] for item in PROMPTS_DATA}
            if prompt not in all_default_prompts:
                final_prompt = prompt

        return (final_prompt,)


# API 接口
@PromptServer.instance.routes.get("/frankai/get_prompts")
async def get_prompts_data(request):
    return web.json_response(PROMPTS_DATA if PROMPTS_DATA else [])