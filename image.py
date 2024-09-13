import torch
from diffusers import FluxPipeline
import os

MODEL_DIR = "models"
MODEL_PATH = f"{MODEL_DIR}/FLUX.1-dev"
OUTPUT_PATH = os.path.join('outputs', 'images')

dtype = torch.bfloat16
pipe = FluxPipeline.from_pretrained(MODEL_PATH, torch_dtype=dtype, cache_dir=MODEL_DIR)
pipe.enable_sequential_cpu_offload()
pipe.vae.enable_slicing()
pipe.vae.enable_tiling()

name = 'out'
prompts = [
]

os.makedirs(os.path.join(OUTPUT_PATH, name), exist_ok=True)

for i, prompt in enumerate(prompts):
    generator = torch.Generator()
    images = pipe(
        [prompt] * 32,
        guidance_scale=3.5,
        num_inference_steps=40,
        width=576,
        height=1024,
        generator=generator
    ).images

    for idx, image in enumerate(images):
        filename = os.path.join(OUTPUT_PATH, name, f"{i}-{idx}.png")
        image.save(filename)
