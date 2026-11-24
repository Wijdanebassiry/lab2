"""Generate the gRPC code of the Inventory service.

Run from the inventory-service folder:
    python scripts/gen_grpc.py

Input : proto/inventory.proto (copy of msoa-backend/contracts/inventory.proto)
Output: app/grpc_gen/inventory_pb2.py and app/grpc_gen/inventory_pb2_grpc.py

protoc writes "import inventory_pb2" in the grpc file, which fails inside a
package. This script rewrites it as a relative import, so the correction does
not have to be done by hand after each generation.
"""

import re
import sys
from pathlib import Path

from grpc_tools import protoc

ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = ROOT / "proto"
OUT_DIR = ROOT / "app" / "grpc_gen"


def main() -> int:
    proto_file = PROTO_DIR / "inventory.proto"
    if not proto_file.exists():
        print(f"Missing contract: {proto_file}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").touch()

    result = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={OUT_DIR}",
            f"--grpc_python_out={OUT_DIR}",
            str(proto_file),
        ]
    )
    if result != 0:
        print("protoc failed")
        return result

    grpc_file = OUT_DIR / "inventory_pb2_grpc.py"
    text = grpc_file.read_text(encoding="utf-8")
    text = re.sub(
        r"^import inventory_pb2 as inventory__pb2",
        "from . import inventory_pb2 as inventory__pb2",
        text,
        flags=re.MULTILINE,
    )
    grpc_file.write_text(text, encoding="utf-8")

    print(f"Generated gRPC code in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())