"""Generate posts via the API. Each variant maps to a post_type."""

import random
import sys

import requests

BASE_URL = "http://localhost:8000"

POST_VARIANTS = [
    {"post_type": "text", "text_content": "This is a text post with some thoughts."},
    {"post_type": "image", "text_content": "Check out this photo I took today."},
    {"post_type": "video", "text_content": "Watch this short clip from the event."},
    {"post_type": "link", "text_content": "Found an interesting article worth reading."},
    {"post_type": "poll", "text_content": "Quick question for the community."},
]


def generate_post(user_id: str, variant_index: int):
    variant = POST_VARIANTS[variant_index]
    resp = requests.post(
        f"{BASE_URL}/posts",
        headers={"X-User-ID": user_id},
        json={
            "post_type": variant["post_type"],
            "text_content": variant["text_content"],
        },
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"Post created: {data['id']} (type={variant['post_type']})")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <user_id> [variant_index]")
        sys.exit(1)

    uid = sys.argv[1]
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else random.randint(0, len(POST_VARIANTS) - 1)

    if idx < 0 or idx >= len(POST_VARIANTS):
        print(f"variant_index must be 0-{len(POST_VARIANTS) - 1}")
        sys.exit(1)

    generate_post(uid, idx)
