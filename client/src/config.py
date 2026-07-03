import tomllib
import typing as t
from pathlib import Path

import pydantic as p


class ClientConfig(p.BaseModel):
   @staticmethod
   def from_path(path: t.Union[str, Path]):
      f = open(path, "r")
      obj = tomllib.loads(f.read())
      return ClientConfig(**obj)

   log_level: int
   oauth2_callback_port: int
   secrets_path: str
