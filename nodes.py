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


# 修改: 图片列表收集节点
class ImageListCollectorNode:
    @classmethod
    def INPUT_TYPES(s):
        # 定义一个必需的图片输入，和两个可选的图片输入
        return {
            "required": {
                "image_1": ("IMAGE",), # 至少需要连接一张图片
            },
            "optional": {
                "image_2": ("IMAGE",),
                "image_3": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("IMAGE_LIST",) # 自定义一个返回类型，方便连接
    RETURN_NAMES = ("image_list",)
    FUNCTION = "collect_images"
    CATEGORY = "FrankAI"

    # 使用显式参数，这样可以直接检查是否为None
    def collect_images(self, image_1, image_2=None, image_3=None):
        image_list = []
        
        # image_1 是必需的，所以它总会有一个值 (通常是一个batch的tensor)
        for img_tensor in image_1:
            image_list.append(img_tensor.unsqueeze(0)) # 保持batch维度为1

        # 检查并添加可选图片
        if image_2 is not None:
            for img_tensor in image_2:
                image_list.append(img_tensor.unsqueeze(0))
        
        if image_3 is not None:
            for img_tensor in image_3:
                image_list.append(img_tensor.unsqueeze(0))
        
        # 这里不需要额外的长度检查，因为 required/optional 已经强制了至少一个，
        # 且我们只收集了最多3个输入。
        
        return (image_list,)



# 修改: BananaMainNode 以接收图片列表并进行数量验证
class BananaMainNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # 接收我们自定义的 "IMAGE_LIST" 类型
                "images": ("IMAGE_LIST",), 
                "key": ("STRING", {"forceInput": True}),
                "prompt": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "text")
    FUNCTION = "execute"
    CATEGORY = "FrankAI"

    # execute方法的 images 参数现在会接收一个Python list
    def execute(self, images, key, prompt):
        # 错误返回的空tensor
        empty_tensor = torch.zeros((1, 512, 512, 3))

        if not key:
            return (empty_tensor, "Error: No API Key provided, please connect to the API Key node")
        if not prompt:
            return (empty_tensor, "Error: No Prompt provided, please connect a Prompt Selector node")

        # images 现在是一个 list of tensors
        if not isinstance(images, list):
            return (empty_tensor, "Error: Image input is not a valid list.")
        
        # 关键修改：检查图片数量
        num_images = len(images)
        if num_images < 1:
            return (empty_tensor, "ERROR: BananaMainNode requires at least one input image.")
        if num_images > 3:
            return (empty_tensor, f"ERROR: BananaMainNode expects at most 3 images, but received {num_images}.")

        imgList_for_api = []
        # 遍历列表中的每一个图片tensor
        for i, image_tensor_batch in enumerate(images):
            if image_tensor_batch is None:
                raise ValueError(f"The {i+1}th image in the list is empty.")

            # 通常列表里的每个元素是一个 (1, H, W, C) 的tensor
            # 提取实际的 (H, W, C) tensor
            image_tensor = image_tensor_batch[0] 
            image_np = (image_tensor.cpu().numpy() * 255).astype(np.uint8)
            
            if len(image_np.shape) == 3:
                if image_np.shape[2] == 3:  # RGB
                    pil_image = Image.fromarray(image_np)
                elif image_np.shape[2] == 4:  # RGBA
                    pil_image = Image.fromarray(image_np[:, :, :3])
                else:
                    return (empty_tensor, f"The image{i+1} format is not supported (RGB or RGBA is expected)")
            else:
                return (empty_tensor, f"The image{i+1} dimension is not supported")

            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format='PNG')
            img_bytes = img_buffer.getvalue()
            
            # 关键修改: 所有图片都使用 'images' 作为字段名
            imgList_for_api.append(('images', (f"image_{i}.png", img_bytes, 'image/png')))

        # 准备表单数据
        files = imgList_for_api
        data = {'key': key, 'prompt': prompt}

        try:
            response = requests.post(
                "https://yinothing.com/api/google/banana",
                files=files, # files 现在包含了所有图片
                data=data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            image_b64 = result.get("imageUrls")[0]
            text = result.get("text", "")
            if not image_b64:
                raise ValueError("API响应中无image_base64字段")
            
            if ',' in image_b64:
                image_b64 = image_b64.split(',', 1)[1]
            
            missing_padding = len(image_b64) % 4
            if missing_padding != 0:
                image_b64 += '=' * (4 - missing_padding)

            image_data = base64.b64decode(image_b64)
            pil_output = Image.open(io.BytesIO(image_data)).convert("RGB")

            output_np = np.array(pil_output).astype(np.float32) / 255.0
            output_tensor = torch.from_numpy(output_np).unsqueeze(0)

            return (output_tensor, text)

        except requests.exceptions.RequestException as e:
            error_message = "Error: "
            try:
                if response.status_code:
                    error_message += f"HTTP {response.status_code} - "
                    if response.text:
                        error_data = response.json()
                        message = error_data.get("message", str(e))
                        if type(message) is dict and "status" in message and "name" in message:
                            error_message = f"Error: HTTP {message['status']} - "
                            message = message['name'] 
                        elif type(message) is dict:
                            message = str(message)
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