import re
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR='models'

def generate_tagged_text(text):
    # model_name = "meta-llama/Meta-Llama-3.1-70B"
    model_name = "mattshumer/Reflection-Llama-3.1-70B"
    tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=MODEL_DIR)
    model = AutoModelForCausalLM.from_pretrained(model_name, cache_dir=MODEL_DIR)

    # Define input text for LLaMA
    input_text = f"Wrap all instances of dialogue with <<SPEAKER=*>><</SPEAKER>> tags, where * is who you believe the speaker to be. If unknown, put default:\n\n{text}"

    # Tokenize and preprocess input text
    inputs = tokenizer(input_text, return_tensors="pt")

    # Generate speaker tags using LLaMA
    outputs = model.generate(**inputs, max_new_tokens=500)

    # Decode the generated text
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return generated_text

def main():
    with open('inputs/The Path of Ascension/2024-04-22_Chapter 313.txt', 'r', encoding='utf-8') as file:
        text = file.read()
    
    # Generate and print the tagged text
    tagged_text = generate_tagged_text(text)
    print(tagged_text)

if __name__ == "__main__":
    main()
