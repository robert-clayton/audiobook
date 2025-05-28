import yaml

def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)

def save_config(path, cfg):
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False)
