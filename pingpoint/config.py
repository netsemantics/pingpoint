import yaml
from pathlib import Path

def load_config(config_path: Path = Path("config.yaml")):
    """
    Loads the application configuration from a YAML file.

    Args:
        config_path: The path to the configuration file.

    Returns:
        A dictionary containing the configuration settings.
    """
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    with open(config_path, "r") as f:
        return yaml.safe_load(f)

# Example of how to use it:
if __name__ == "__main__":
    try:
        # Assuming the script is run from the project root
        config = load_config(Path(__file__).parent.parent / "config.yaml")
        import json
        print(json.dumps(config, indent=2))
    except FileNotFoundError as e:
        print(e)
