import tomllib
import pydantic as p

class ClientConfig(p.BaseModel):
   @staticmethod
   def from_file(path: str):
      f = open(path, "r")
      obj = tomllib.loads(f.read())
      return ClientConfig(**obj)

   log_level: int
   oauth2_callback_port: int
   secrets_path: str
