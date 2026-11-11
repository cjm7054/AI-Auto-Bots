import os
import re
import subprocess
import logging
from pathlib import Path
from dotenv import load_dotenv
from wordpress_uploader import upload_to_wordpress, get_recent_wordpress_titles

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
DRAFT_DIR = BASE_DIR / "data" / "drafts"
LOG_FILE = BASE_DIR / "data" / "sync_wp.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

load_dotenv(REPO_DIR / ".env")
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("sync_drafts_to_wp")


def normalize_title(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9가-힣]", "", title).lower()


def extract_title(md_text: str, fallback_name: str) -> str:
    for line in md_text.strip().splitlines():
        s = line.strip()
        if s:
            if s.startswith("#"):
                return re.sub(r"^#+\s*", "", s).strip()
            return s
    return fallback_name


def pull_latest_from_git():
    try:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.run(
            ["git", "-C", str(REPO_DIR), "pull", "--rebase", "--autostash", "origin", "main"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            **kwargs,
        )
    except Exception as e:
        logger.warning(f"Git pull 중 경고 (무시 가능): {e}")


def sync_all_drafts_to_wordpress():
    pull_latest_from_git()

    if not DRAFT_DIR.exists():
        logger.info("초안 폴더가 없습니다.")
        return 0

    published_titles = get_recent_wordpress_titles(per_page=100)
    published_norm = {normalize_title(t) for t in published_titles if t}
    logger.info(f"현재 워드프레스 공개 글 {len(published_titles)}개 확인됨")

    published_count = 0
    for md_file in sorted(DRAFT_DIR.glob("*.md")):
        raw_md = md_file.read_text(encoding="utf-8")
        if not raw_md.strip():
            continue
        title = extract_title(raw_md, md_file.stem)
        norm = normalize_title(title)

        if norm in published_norm:
            logger.info(f"[건너뜀 - 이미 발행됨] {title}")
            continue

        logger.info(f"[신규 발행 시도] {title} ({md_file.name})")
        res = upload_to_wordpress(title, raw_md, status="publish", categories=[119])
        if res:
            logger.info(f"✅ [발행 완료] ID={res.get('id')} URL={res.get('link')}")
            published_norm.add(norm)
            published_count += 1
        else:
            logger.error(f"❌ [발행 실패] {title}")

    return published_count


if __name__ == "__main__":
    sync_all_drafts_to_wordpress()
