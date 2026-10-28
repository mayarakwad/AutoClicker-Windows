"""Turns failed tests in `python -m unittest -v` output into GitHub annotations.

Annotations show on the run page and in GitHub's public API, unlike the logs,
which only signed-in users can read.
Usage: python .github/annotate_test_failures.py test-output.txt
"""
import re
import sys

SEPARATOR = "=" * 70
MAX_ANNOTATIONS = 10  # GitHub shows at most 10 error annotations per step


def escape(text, title=False):
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return text.replace(":", "%3A").replace(",", "%2C") if title else text


def main(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        output = f.read()
    blocks = [block.strip() for block in output.split(SEPARATOR)[1:]]
    failures = [block for block in blocks if block.startswith(("FAIL:", "ERROR:"))]
    for block in failures[:MAX_ANNOTATIONS]:
        title, _, body = block.partition("\n")
        body = body.split("-" * 70, 1)[-1]                    # drop the dashes under the title
        body = re.split(r"\n-{70}\nRan \d+ test", body)[0].strip()  # and the summary after the last one
        print(f"::error title={escape(title, title=True)}::{escape(body[-4000:])}")
    if not failures:
        tail = "\n".join(output.strip().splitlines()[-40:])
        print(f"::error title=Tests crashed or failed to start::{escape(tail)}")


if __name__ == "__main__":
    main(sys.argv[1])
