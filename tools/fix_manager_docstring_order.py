"""Fix-up: keep class docstrings above the injected manager line.

The first insertion pass placed ``objects = TenantManager()`` before the
docstring of a few classes (docstrings were indented, so the detection missed
them). This moves the docstring back to the top of the class body.
"""
import io
import re

FILES = [
    "app/models/products.py",
    "app/models/transactions.py",
    "app/models/customers.py",
    "app/models/suppliers.py",
    "app/models/organization.py",
    "app/models/human_resource.py",
    "app/models/finance.py",
    "app/models/perfume.py",
]

PATTERN = re.compile(
    r"(?P<indent>[ \t]*)objects = TenantManager\(\)\n"
    r"(?P<gap>\n*)"
    r"(?P<doc>(?P=indent)(?:\"\"\"|''').*?(?:\"\"\"|''')\n)",
    re.DOTALL,
)


def fix(text):
    def repl(match):
        indent = match.group("indent")
        doc = match.group("doc")
        return f"{doc}{indent}objects = TenantManager()\n"

    return PATTERN.sub(repl, text)


for path in FILES:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        raw = fh.read()
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    new = fix(text)
    if new != text:
        out = new.replace("\n", "\r\n") if crlf else new
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
        print("fixed docstring order in %s" % path)
    else:
        print("ok %s" % path)
