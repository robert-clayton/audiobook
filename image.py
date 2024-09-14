# import torch
# from diffusers import FluxPipeline
import os

MODEL_DIR = "models"
MODEL_PATH = f"{MODEL_DIR}/FLUX.1-dev"
OUTPUT_PATH = os.path.join('outputs', 'images')

# dtype = torch.bfloat16
# pipe = FluxPipeline.from_pretrained(MODEL_PATH, torch_dtype=dtype, cache_dir=MODEL_DIR)
# pipe.enable_sequential_cpu_offload()
# pipe.vae.enable_slicing()
# pipe.vae.enable_tiling()

# name = 'out'
# prompts = [
# ]

# os.makedirs(os.path.join(OUTPUT_PATH, name), exist_ok=True)

# for i, prompt in enumerate(prompts):
#     generator = torch.Generator()
#     images = pipe(
#         [prompt] * 32,
#         guidance_scale=3.5,
#         num_inference_steps=40,
#         width=576,
#         height=1024,
#         generator=generator
#     ).images

#     for idx, image in enumerate(images):
#         filename = os.path.join(OUTPUT_PATH, name, f"{i}-{idx}.png")
#         image.save(filename)


import torch

from model import T5EncoderModel, FluxTransformer2DModel
from diffusers import FluxPipeline


text_encoder_2: T5EncoderModel = T5EncoderModel.from_pretrained(
    "HighCWu/FLUX.1-dev-4bit",
    subfolder="text_encoder_2",
    torch_dtype=torch.bfloat16,
    # hqq_4bit_compute_dtype=torch.float32,
)

transformer: FluxTransformer2DModel = FluxTransformer2DModel.from_pretrained(
    "HighCWu/FLUX.1-dev-4bit",
    subfolder="transformer",
    torch_dtype=torch.bfloat16,
)

pipe: FluxPipeline = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-dev",
    text_encoder_2=text_encoder_2,
    transformer=transformer,
    torch_dtype=torch.bfloat16,
)
pipe.enable_model_cpu_offload()
# pipe.remove_all_hooks()
pipe.enable_vae_slicing()
pipe.enable_vae_tiling()

prompts = [
    # ...
]
name = "HelloWorld"

os.makedirs(os.path.join(OUTPUT_PATH, name), exist_ok=True)
for i, prompt in enumerate(prompts):
    images = pipe(
        prompt, 
        guidance_scale=3.5, 
        width=2048, 
        height=2048, 
        num_inference_steps=50, 
        generator=torch.Generator().manual_seed(0)).images
    for idx, image in enumerate(images):
        filename = os.path.join(OUTPUT_PATH, name, f"{i}-{idx}.png")
        image.save(filename)
