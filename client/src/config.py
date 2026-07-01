import tomllib

class yuPlaylistClientConfig:
   @staticmethod
   def from_file(path: str):
      f = open(path, "w")
      raw = tomllib.loads(f.read())
      log_level = raw.get("LOG_LEVEL")
      port = raw.get("OAUTH2_CALLBACK_PORT")
      scopes = raw.get("YT_SCOPES")
      secrets = raw.get("SECRETS_PATH")
      if type(log_level) is not int:
         raise ValueError("XXX")
      if type(port) is not int:
         raise ValueError("XXX")
      if not isinstance(scopes, list):
         raise ValueError("XXX")
      if type(secrets) is not str:
         raise ValueError("XXX")
      return yuPlaylistClientConfig(
         log_level=log_level,
         oauth2_callback_port=log_level,
         yt_scopes=scopes,
         secrets_path=secrets,
      )

   def __init__(
      self,
      *,
      log_level: int,
      oauth2_callback_port: int,
      yt_scopes: list[str],
      secrets_path: str,
   ):
      self.log_level = log_level
      self.port = oauth2_callback_port
      self.yt_scopes = yt_scopes
      self.secrets_path = secrets_path
