import torch
from diffusers import FluxPipeline

MODEL_DIR = "models"
MODEL_PATH = "models/FLUX.1-dev"
pipe = FluxPipeline.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16, cache_dir=MODEL_DIR)
pipe.enable_model_cpu_offload()

prompts = [
  "A glowing strand of DNA floating in a dark, sterile lab. The strand is twisted unnaturally, with bright, dangerous-looking bioluminescent veins running through it. The background is sterile and dark, with medical equipment faintly visible, casting eerie shadows.",
  "A strand of DNA, but with a sinister twist: instead of smooth curves, the double helix is jagged, broken in places, and pulsing with an unnatural, faintly glowing red light. Small, dark tendrils are growing from the helix, like it's slowly evolving into something far worse.",
  "A close-up of a DNA strand in a petri dish, its surface flickering with alien patterns and glowing biohazard symbols, surrounded by ominous mist, in a dimly lit laboratory.",
  "A healthy human slowly transforming, their skin becoming translucent as veins glow faintly beneath, eyes hollow with a disturbing calmness. Their flesh looks like it's dissolving, while their internal organs shift and mutate under their skin, surrounded by a faint, glowing aura.",
  "An individual infected by a deadly DNA virus: their body is collapsing from within, with skin turning pale and translucent. The outline of their organs is barely visible beneath the skin, and their face is peaceful, even as dark veins spread across their body.",
  "A person moments before death from a deadly genetic virus: their body is unnaturally calm, but beneath the skin, organs and muscles are subtly disintegrating. The figure stands frozen in a peaceful stance, while faint, glowing strands of DNA can be seen within their veins, radiating outward like a deadly network.",
  "A desolate scene: bodies lie scattered, perfectly still and eerily peaceful. Their eyes remain open, skin pale and untouched, but the faint glow beneath the surface indicates something catastrophic happened. The environment is cold and sterile, a quarantined area with biohazard warning signs in the distance.",
  "An infected individual after sudden death from an internal genetic collapse: their body remains intact, but the surrounding air is filled with a faint mist, glowing red and blue from unseen energy. Their skin is cold and tight, with dark, branching veins visible beneath, as if something alien rewrote their biology.",
  "A village left in silence, every single person dead from a genetic virus. No visible wounds, no destruction—just dozens of bodies lying in place, as if time itself stopped. The soft glow of something sinister lingers in the air, as if the virus is still present, waiting for its next host.",
]


# Function to display the generated image using Matplotlib
def display_image(image):
    plt.imshow(np.array(image))
    plt.axis("off")
    plt.show()

for idx, prompt in enumerate(prompts):
    print("Generating from prompt:")
    print(f'\t{prompt}')
    
    # Step-by-step generation (get latent progress at intermediate steps)
    generator = torch.Generator("cuda").manual_seed(0)
    steps = 50
    breakpoint_steps = 10
    
    for step in range(0, steps, breakpoint_steps):  # Choose to display every 10th step
        # Update the `num_inference_steps` to the current step
        image = pipe(
            prompt,
            guidance_scale=3.5,
            num_inference_steps=step,  # Manually reduce the number of steps
            width=576,
            height=1024,
            generator=generator
        ).images[0]
        
        # # Display the intermediate image
        # display_image(image)
    
    # Save final image after all steps are completed
    final_image = pipe(
        prompt,
        guidance_scale=3.5,
        num_inference_steps=steps,
        width=576,
        height=1024,
        generator=generator
    ).images[0]

    # Save the final output
    filename = f"{name}_{idx}.png"
    final_image.save(filename)
    print(f"Saved image: {filename}")

