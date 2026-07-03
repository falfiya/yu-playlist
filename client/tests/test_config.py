import config
from pathlib import Path

config_path = Path(__file__).parent.parent / "src" / "config.default.toml"

def test_config():
   c = config.ClientConfig.from_path(config_path)
   assert c.oauth2_callback_port == 0
