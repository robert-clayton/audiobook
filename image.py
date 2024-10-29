import torch
from diffusers import FluxPipeline, FluxControlNetModel
from diffusers.pipelines import FluxControlNetPipeline
from diffusers.utils import load_image
from huggingface_hub import login
from dotenv import load_dotenv
import os
import gc

# Load environment variables from .env
load_dotenv()

# Get Hugging Face token from .env
huggingface_token = os.getenv('HUGGINGFACE_TOKEN')

# Authenticate with Hugging Face using the token
login(token=huggingface_token, add_to_git_credential=True)

MODEL_DIR = "models"
MODEL_PATH = f"{MODEL_DIR}/FLUX.1-dev"
OUTPUT_PATH = os.path.join('outputs', 'images')

dtype = torch.bfloat16

# Use the token in from_pretrained to access the gated model
pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-dev", 
                                    torch_dtype=dtype, 
                                    cache_dir=MODEL_DIR)
pipe.enable_model_cpu_offload()

# pipe.enable_sequential_cpu_offload()
pipe.vae.enable_slicing()
pipe.vae.enable_tiling()

name = 'newtest'
prompts = [
    "A Board Apes (bitcoin NFT) holding a big sign that says 'Theia Inc.' while standing in a Board Apes-themed first person shooter stadium"
]

os.makedirs(os.path.join(OUTPUT_PATH, name), exist_ok=True)

for i, prompt in enumerate(prompts):
    generator = torch.Generator("cuda").manual_seed(0)
    images = pipe(
        [prompt] * 16,
        guidance_scale=1.5,
        num_inference_steps=50,
        width=576,
        height=1024,
        generator=generator
    ).images

    for idx, image in enumerate(images):
        filename = os.path.join(OUTPUT_PATH, name, f"{i}-{idx}.png")
        image.save(filename)

pipe = None
if torch.cuda.is_available():
    torch.cuda.empty_cache()
gc.collect()

controlnet = FluxControlNetModel.from_pretrained(
  "jasperai/Flux.1-dev-Controlnet-Upscaler",
  torch_dtype=torch.bfloat16,
  cache_dir=MODEL_DIR
)
pipe = FluxControlNetPipeline.from_pretrained(
  "black-forest-labs/FLUX.1-dev",
  controlnet=controlnet,
  torch_dtype=torch.bfloat16
)
pipe.to("cuda")

images = #load image paths from above output into this
os.makedirs(os.path.join(OUTPUT_PATH, name, "upscaled"), exist_ok=True)
for i, image in enumerate(images):
    control_image = load_image(
    "https://huggingface.co/jasperai/Flux.1-dev-Controlnet-Upscaler/resolve/main/examples/input.jpg"
    )
    image = pipe(
        prompt="", 
        control_image=control_image,
        controlnet_conditioning_scale=0.6,
        num_inference_steps=28, 
        guidance_scale=3.5,
        height=control_image.size[1],
        width=control_image.size[0]
    ).images[0]

    # save image in the new dir

