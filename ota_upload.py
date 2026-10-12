import json
import re
from pathlib import Path

Import("env")


def configure_ota(environment):
    config_path = Path(environment.subst("$PROJECT_DIR")) / "src" / "ota_config.h"
    match = re.search(
        r'^\s*#define\s+OTA_PASSWORD\s+("(?:\\.|[^"\\])*")\s*$',
        config_path.read_text(),
        re.MULTILINE,
    )
    if not match:
        raise RuntimeError("Define OTA_PASSWORD in src/ota_config.h before OTA upload")
    password = json.loads(match.group(1))
    environment.Replace(
        UPLOAD_PORT="192.168.1.251",
        UPLOADERFLAGS=["--progress", "-i", "$UPLOAD_PORT", "--auth=" + json.dumps(password)],
    )


configure_ota(env)


def prepare_upload(source, target, env):
    configure_ota(env)


env.AddPreAction("upload", prepare_upload)