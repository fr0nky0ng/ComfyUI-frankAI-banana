
### File: `__init__.py`
### This file loads the nodes when ComfyUI starts.

from . import nodes
NODE_CLASS_MAPPINGS = {
    "BananaMainNode": nodes.BananaMainNode,
    "GoogleApiKeyNode": nodes.GoogleApiKeyNode,
    "FrankApiKeyNode": nodes.FrankApiKeyNode,
    "BananaPromptSelector": nodes.BananaPromptSelector,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "BananaMainNode": "FrankAI Banana Main Node",
    "BananaApiKeyNode": "Google API Key Node",
    "FrankApiKeyNode": "FrankAI API Key Node",
    "BananaPromptSelector": "Banana Prompt Selector",
}
WEB_DIRECTORY = "./js"
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']