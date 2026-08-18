# -*- coding: utf-8 -*-
"""
blogger_publisher_v2.py — Blogger API v3 발행 어댑터

전제:
  - Google Cloud Console에서 Blogger API v3 활성화
  - OAuth 2.0 클라이언트 ID (또는 서비스 계정) 발급
  - BLOGGER_BLOG_ID 환경변수 노출 (예: 1527607409735024087)
  - 토큰을 secrets/google_token.json 에 보관
"""
import json
import re
from pathlib import Path
from typing import Optional


class BloggerError(Exception):
    pass


class BloggerPublisher:
    """Blogger API v3 발행 어댑터

    main_v2.py 에서 작성자 이름·날짜·이미지 정보를 meta.json 으로 받아
    Blogger 의 post.insert API 로 직접 게시한다.
    """

    def __init__(self, blog_id: str, credentials_path: str):
        self.blog_id = blog_id
        self.credentials_path = credentials_path
        self._service = None

    def _get_service(self):
        """Blogger API v3 서비스 객체 (lazy 초기화)

        python -m pip install google-api-python-client google-auth 필요
        """
        if self._service is not None:
            return self._service
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise BloggerError(
                "google-api-python-client / google-auth 패키지 필요: "
                "pip install google-api-python-client google-auth"
            ) from exc
        creds = Credentials.from_authorized_user_file(self.credentials_path)
        self._service = build("blogger", "v3", credentials=creds, cache_discovery=False)
        return self._service

    @staticmethod
    def _strip_human_markers(md: str) -> str:
        """1인칭 단락 마커만 제거하고 본문은 살린다.

        <!--HUMAN_EDIT_START--> … <!--HUMAN_EDIT_END--> 사이의 본문은 그대로 두어
        화면에는 사용자가 직접 쓴 1인칭 단락이 자연스럽게 노출되도록 한다.
        """
        return re.sub(r"<!--HUMAN_EDIT_(?:START|END)-->", "", md).strip()

    @staticmethod
    def _meta(post_md_path: str, meta_path: Optional[str]) -> tuple[str, dict]:
        html = BloggerPublisher._strip_human_markers(Path(post_md_path).read_text(encoding="utf-8"))
        meta: dict = {}
        if meta_path and Path(meta_path).exists():
            meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        return html, meta

    def publish(self, post_md_path: str, meta_path: Optional[str] = None,
                publish_status: str = "publish") -> dict:
        """게시 (publish) 또는 임시보관 (draft)

        Blogger API v3 의 posts.insert endpoint 를 호출한다.
        isDraft=True 이면 임시보관 상태로 저장되며 URL 없이 응답한다.
        """
        if publish_status not in {"publish", "draft"}:
            raise BloggerError("publish_status 는 'publish' 또는 'draft' 만 허용")

        service = self._get_service()
        html, meta = self._meta(post_md_path, meta_path)

        title = meta.get("title") or Path(post_md_path).stem.replace("-", " ").title()
        labels = meta.get("labels", ["AI·업무 자동화"])
        body = {"title": title, "content": html, "labels": labels}

        result = (
            service.posts()
            .insert(blogId=self.blog_id, body=body,
                    isDraft=(publish_status == "draft"))
            .execute()
        )
        return {
            "url": result.get("url"),
            "id": result.get("id"),
            "published": result.get("published"),
            "status": publish_status,
        }
