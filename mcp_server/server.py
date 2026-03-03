import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "engram.settings.development")
django.setup()

from fastmcp import FastMCP  # noqa: E402

from mcp_server.auth import build_auth  # noqa: E402

mcp = FastMCP("engram", auth=build_auth())

# Import tool modules to register @mcp.tool() decorators
import mcp_server.tools  # noqa: F401, E402


def main():
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
