import tomllib
import typing as t

import pydantic as p


class ClientConfig(p.BaseModel):
   @staticmethod
   def from_file(file):
      obj = tomllib.loads(file.read())
      return ClientConfig(**obj)

   log_level: int
   oauth2_callback_port: int
   secrets_path: str
   device_name: str
