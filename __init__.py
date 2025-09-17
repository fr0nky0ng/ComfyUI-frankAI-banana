
### File: `__init__.py`
### This file loads the nodes when ComfyUI starts.

from . import nodes


class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False
IMAGE_LIST = AnyType("*")


NODE_CLASS_MAPPINGS = {
    "BananaMainNode": nodes.BananaMainNode,
    "GoogleApiKeyNode": nodes.GoogleApiKeyNode,
    "FrankApiKeyNode": nodes.FrankApiKeyNode,
    "BananaPromptSelector": nodes.BananaPromptSelector,
    "ImageListCollector": nodes.ImageListCollectorNode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "BananaMainNode": "FrankAI Banana Main Node",
    "BananaApiKeyNode": "Google API Key Node",
    "FrankApiKeyNode": "FrankAI API Key Node",
    "BananaPromptSelector": "Banana Prompt Selector",
    "ImageListCollector": "Image List Collector"
}
WEB_DIRECTORY = "./js"
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']