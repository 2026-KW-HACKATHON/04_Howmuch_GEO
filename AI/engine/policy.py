# 정비사업 규칙 값 로더
#   서울시 기본계획·조례가 정한 숫자(4단 용적률, 종상향 공공기여율, 보정계수 범위, 서울시 평균 공시지가 등)는
#   코드 상수가 아니라 data/policy_rules.json 에 둔다 — 규칙이 바뀌면 파일만 고친다.
#
#   pending 은 공고·건의 단계라 아직 반영하지 않은 변경이다.
#     뉴스 감시 도구(AI/maintenance/policy_watch.py)가 기사를 찾아 확정 신호를 보여주고,
#     사람이 기사를 확인한 뒤 --apply 로 rules 에 덮어쓴다. 법규라 기사 문장으로 자동 반영하지 않는다
#
#   ※ 백엔드는 시작할 때 한 번 읽는다 → 파일을 고치면 백엔드를 다시 띄워야 한다 (uvicorn --reload 는 .py 만 감시)
import json
from dataclasses import dataclass, field
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("data") / "policy_rules.json"


@dataclass
class PendingRule:
    id: str
    title: str
    status: str                 # 공고 · 건의 · 반영
    announced: str              # 공고·건의 날짜
    apply: dict                 # 반영할 때 rules 에 덮어쓸 값 (비어 있으면 이 모델에 영향 없음)
    queries: list[str]          # 뉴스 검색어
    keywords: list[list[str]]   # 기사 매칭 — 묶음마다 하나 이상 들어 있어야 그 규칙 기사로 본다
    sources: list[str] = field(default_factory=list)
    applies_to: str = "재개발"
    note: str = ""
    applied_at: str = ""        # 반영한 날 (policy_watch --apply 가 적는다)


def load(path: Path = POLICY_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(data: dict, path: Path = POLICY_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def pending_rules(data: dict) -> list[PendingRule]:
    return [PendingRule(**item) for item in data.get("pending", [])]


#엔진이 import 할 때 읽는 값
RULES: dict = load()["rules"]
