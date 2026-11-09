"""저장소: Cloudflare R2 (secrets 에 R2 키가 있으면) 또는 로컬 폴더.

모든 파일은 'drama/' 아래 작품 단위로 저장한다.
    drama/works/index.json                      작품 목록
    drama/works/<wid>/work.json                 작품 상태 (대본 분석, 캐스팅, 장소, 화별 진행)
    drama/works/<wid>/script.<ext>              대본 원본
    drama/works/<wid>/cast/<slug>/cand_1.jpg    캐스팅 후보
    drama/works/<wid>/loc/<slug>/cand_1.jpg     장소 마스터 후보
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

PREFIX = "drama/"
R2_KEYS = ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")


class Store:
    def __init__(self, keys: dict, local_root: str = "data"):
        self.keys = keys
        self.r2 = all(str(keys.get(k, "")).strip() for k in R2_KEYS)
        self.root = Path(local_root)
        self._c = None

    # ---- 백엔드 ----
    @property
    def kind(self) -> str:
        return "Cloudflare R2" if self.r2 else "로컬 폴더 (앱이 다시 시작되면 지워짐)"

    def _client(self):
        if self._c is None:
            import boto3
            from botocore.config import Config
            ep = str(self.keys["R2_ENDPOINT"]).strip().rstrip("/")
            if not ep.startswith("http"):
                ep = "https://" + ep
            u = urlparse(ep)
            ep = f"{u.scheme}://{u.netloc}"          # 버킷 경로가 붙어 있어도 계정 주소만 사용
            self._c = boto3.client("s3", endpoint_url=ep, region_name="auto",
                                   aws_access_key_id=str(self.keys["R2_ACCESS_KEY_ID"]).strip(),
                                   aws_secret_access_key=str(self.keys["R2_SECRET_ACCESS_KEY"]).strip(),
                                   config=Config(signature_version="s3v4", retries={"max_attempts": 3}))
        return self._c

    @property
    def bucket(self) -> str:
        return str(self.keys.get("R2_BUCKET", "")).strip()

    # ---- 바이트 ----
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        key = PREFIX + key
        if self.r2:
            self._client().put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        else:
            p = self.root / key
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return key

    def get_bytes(self, key: str) -> bytes | None:
        key = PREFIX + key
        try:
            if self.r2:
                return self._client().get_object(Bucket=self.bucket, Key=key)["Body"].read()
            p = self.root / key
            return p.read_bytes() if p.exists() else None
        except Exception:
            return None

    def delete(self, key: str) -> None:
        key = PREFIX + key
        try:
            if self.r2:
                self._client().delete_object(Bucket=self.bucket, Key=key)
            else:
                p = self.root / key
                if p.exists():
                    p.unlink()
        except Exception:
            pass

    # ---- JSON ----
    def get_json(self, key: str, default=None):
        raw = self.get_bytes(key)
        if raw is None:
            return default
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return default

    def put_json(self, key: str, data) -> None:
        self.put_bytes(key, json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"), "application/json")

    # ---- 작품 ----
    def works(self) -> list[dict]:
        return self.get_json("works/index.json", []) or []

    def save_index(self, items: list[dict]) -> None:
        self.put_json("works/index.json", items)

    def load_work(self, wid: str) -> dict | None:
        return self.get_json(f"works/{wid}/work.json")

    def save_work(self, work: dict) -> None:
        self.put_json(f"works/{work['id']}/work.json", work)
        idx = [w for w in self.works() if w["id"] != work["id"]]
        idx.insert(0, {"id": work["id"], "title": work["title"], "created": work.get("created", "")})
        self.save_index(idx)


def secrets_dict() -> dict:
    """Streamlit secrets + 환경 변수를 한 dict 로."""
    out = {}
    try:
        import streamlit as st
        out.update({k: v for k, v in st.secrets.items() if isinstance(v, (str, int, float))})
    except Exception:
        pass
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "REPLICATE_API_TOKEN", *R2_KEYS,
              "CLAUDE_MODEL", "OPENAI_IMAGE_QUALITY"):
        if os.environ.get(k) and not out.get(k):
            out[k] = os.environ[k]
    return out
