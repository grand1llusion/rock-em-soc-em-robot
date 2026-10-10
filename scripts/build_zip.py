"""Package the Lambda function into dist/rock-em-soc-em-robot.zip (upload this in the Lambda console)."""
import os
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "lambda")
OUT = os.path.join(ROOT, "dist", "rock-em-soc-em-robot.zip")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name in ("lambda_function.py", "data.py", "index.html"):
        info = zipfile.ZipInfo(name, date_time=(2026, 10, 10, 0, 0, 0))  # fixed date = reproducible zip
        info.external_attr = 0o644 << 16
        with open(os.path.join(SRC, name), "rb") as f:
            z.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
print("Wrote", os.path.normpath(OUT))
