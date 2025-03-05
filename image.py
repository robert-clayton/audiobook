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
pipe.vae.enable_slicing()
pipe.vae.enable_tiling()

name = 'dnd_session2'
prompts = [
    # Bihena - "Anime-style depiction of the Goddess of the sea, battle, and justice. A woman whose bearing strikes unto all who gaze her the term 'Golden Paladin of the Sea'. This work is done in a beautiful paintbrush-anime style. She has large breasts, blonde hair, and thick hips beneath her armor."
    # Tubrock - "Anime-style depiction of the God of blacksmithing. A fantasy dwarf who strikes a sense of focus on making something new. Weilding his divine hammer, he creates miracles out of any material he can get his hands on. He has great beard and flowing red hair like a Scottsman. This work is done in a beautiful paintbrush anime style."
    # Ashley - "Painted western fantasy, greek mythos painting of the Goddess of Shadows with a hint of anime feeling. A dark-skinned succubus wearing a business suit. Her wings are strikingly cute. Her eyes glow slightly red. An Indian descent beauty. A pair of dark red horns with a slight curl adorn her jet black straight hair."
    # Aurivy - "Anime-style depiction of the Goddess of Love and Travel. A young girl whose bearing strikes unto all who gaze her the term 'Cute little girl'. This work is done in a beautiful paintbrush-anime style. She has budding breasts, pink hair, and thick hips beneath her form fitting traveling clothes."
    # "Illustration of an ankle-tall and, well, Tiny Shadowfey Gremlin monster in western fantasy style. Standing on an underground staircase leading into the underdark, it's leaking dark fog from patches of fur growing here and there.",
    # "Illustration of a shoulder-height Shadowfey Gremlin monster in western fantasy style. Standing on an underground staircase leading into the underdark, it's leaking dark fog it's mouth. It has a gigantic belly."
    "Western fantasy style illustration of a 18 year old halfling girl. She has long brown hair and blue eyes. Around two foot, ten inches tall. She wears leather armor similar to a barbarian and is obsessed with bacon."
]

os.makedirs(os.path.join(OUTPUT_PATH, name), exist_ok=True)

# Generate images
for i, prompt in enumerate(prompts):
    generator = torch.Generator("cuda")
    images = pipe(
        [prompt] * 16,
        guidance_scale=1.8,
        num_inference_steps=50,
        width=576,
        # width=1024,
        # height=576,
        height=1024,
        generator=generator
    ).images

    for idx, image in enumerate(images):
        filename = os.path.join(OUTPUT_PATH, name, f"{i}-{idx}.png")
        image.save(filename)

# # Unload the initial pipeline
# pipe = None
# if torch.cuda.is_available():
#     torch.cuda.empty_cache()
# gc.collect()

# # Load the control model for upscaling
# controlnet = FluxControlNetModel.from_pretrained(
#     "jasperai/Flux.1-dev-Controlnet-Upscaler",
#     torch_dtype=torch.bfloat16,
#     cache_dir=MODEL_DIR
# )

# # Create a new pipeline for upscaling
# pipe = FluxControlNetPipeline.from_pretrained(
#     "black-forest-labs/FLUX.1-dev",
#     controlnet=controlnet,
#     torch_dtype=torch.bfloat16
# )
# pipe.to("cuda")

# # Load image paths from the previously generated images
# image_paths = [os.path.join(OUTPUT_PATH, name, f"{i}-{j}.png") for i in range(len(prompts)) for j in range(16)]

# os.makedirs(os.path.join(OUTPUT_PATH, name, "upscaled"), exist_ok=True)

# for i, image_path in enumerate(image_paths):
#     # Load the image for upscaling
#     control_image = load_image(image_path)  # Load the generated image

#     # Use the control image to upscale
#     upscaled_image = pipe(
#         prompt=prompts[0], 
#         control_image=control_image,
#         controlnet_conditioning_scale=0.6,
#         num_inference_steps=28, 
#         guidance_scale=3.5,
#         height=control_image.size[1],
#         width=control_image.size[0]
#     ).images[0]

#     # Save the upscaled image in the new directory
#     upscaled_filename = os.path.join(OUTPUT_PATH, name, "upscaled", f"upscaled_{i}.png")
#     upscaled_image.save(upscaled_filename)
