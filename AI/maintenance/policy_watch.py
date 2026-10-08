# 규칙 변경 뉴스 감시 (유지보수용)
#   AI/engine/data/policy_rules.json 의 pending(공고·건의 단계 변경)마다 뉴스를 찾아,
#   확정(고시·시행) 신호가 있는지 보여준다. 반영은 사람이 기사를 확인한 뒤 --apply 로 한다 —
#   법규를 기사 문장만으로 자동 반영하지 않는다 (공고 → 재공람·심의 → 고시 사이에 내용이 바뀌기도 한다)
#
#   python -m AI.maintenance.policy_watch                     # 카카오 웹검색 (뉴스 패널과 같은 API, 환경변수 KAKAO_API_KEY)
#   python -m AI.maintenance.policy_watch --from-file a.json  # 저장한 기사 목록으로 검사 [{title, contents, url, published_at}]
#   python -m AI.maintenance.policy_watch --list              # 지금 규칙 값과 대기 중인 변경
#   python -m AI.maintenance.policy_watch --apply <id> --source <확인한 기사 URL>
#
#   반영하면 policy_rules.json 이 바뀐다 → 백엔드를 다시 띄워야 계산에 들어간다
import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from AI.engine import policy

KAKAO_SEARCH_URL = "https://dapi.kakao.com/v2/search/web"

#로컬 docker override 가 넣는 더미 키 (뉴스 라우터가 import 시점에 키를 요구해서 넣어 둔 값)
DUMMY_KEYS = {"", "local-dummy-for-boot"}

#확정·시행 신호와 아직 안(案)이라는 신호. 둘 다 세어 보여주고 판단은 사람이 한다
CONFIRM_TERMS = ["최종 고시", "고시했", "고시됐", "고시된", "확정", "시행"]
DRAFT_TERMS = ["변경안", "공고", "재공람", "건의", "요청", "검토", "추진"]


#뉴스 라우터와 같은 정리 : 태그를 지우고 HTML 엔티티를 되돌린다
def clean_html(text: str | None) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or ""))


def fetch_kakao(query: str, key: str, size: int = 10) -> list[dict]:
    url = f"{KAKAO_SEARCH_URL}?" + urllib.parse.urlencode({"query": query, "sort": "recency", "size": size})
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {key}"})
    with urllib.request.urlopen(req, timeout=10) as res:
        documents = json.load(res).get("documents", [])
    return [
        {
            "title": clean_html(d.get("title")),
            "contents": clean_html(d.get("contents")),
            "url": d.get("url"),
            "published_at": d.get("datetime"),
        }
        for d in documents
    ]


#규칙 키워드 묶음마다 하나 이상 들어 있으면 그 규칙 기사로 본다
def matches(article: dict, rule: policy.PendingRule) -> bool:
    text = f"{article.get('title', '')} {article.get('contents', '')}"
    return all(any(word in text for word in group) for group in rule.keywords)


def signals(article: dict) -> tuple[list[str], list[str]]:
    text = f"{article.get('title', '')} {article.get('contents', '')}"
    return [t for t in CONFIRM_TERMS if t in text], [t for t in DRAFT_TERMS if t in text]


#기사 목록 → 규칙별 매칭 (이미 반영한 규칙은 건너뛴다). 다른 코드에서도 부를 수 있게 순수 함수로 둔다
def scan(articles: list[dict], rules: list[policy.PendingRule]) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {}
    for rule in rules:
        if rule.status == "반영":
            continue
        hits = []
        for article in articles:
            if matches(article, rule):
                confirm, draft = signals(article)
                hits.append({**article, "confirm": confirm, "draft": draft})
        found[rule.id] = sorted(hits, key=lambda a: a.get("published_at") or "", reverse=True)
    return found


def collect_from_kakao(rules: list[policy.PendingRule], key: str, size: int) -> list[dict]:
    seen, articles = set(), []
    for rule in rules:
        if rule.status == "반영":
            continue
        for query in rule.queries:
            for article in fetch_kakao(query, key, size):
                if article["url"] not in seen:
                    seen.add(article["url"])
                    articles.append(article)
    return articles


def print_report(found: dict[str, list[dict]], rules: list[policy.PendingRule]) -> None:
    for rule in rules:
        if rule.status == "반영":
            continue
        hits = found.get(rule.id, [])
        confirmed = [h for h in hits if h["confirm"]]
        verdict = "확정 신호 있음 — 기사 확인 후 --apply" if confirmed else ("관련 기사만 있음" if hits else "기사 없음")
        print(f"\n[{rule.id}] {rule.title}")
        print(f"  상태 {rule.status} ({rule.announced}) · 대상 {rule.applies_to} · 반영 값 {rule.apply or '없음(이 모델 영향 없음)'}")
        print(f"  → {verdict} (관련 {len(hits)}건, 확정 신호 {len(confirmed)}건)")
        for h in hits[:5]:
            tag = "확정?" if h["confirm"] else "안(案)"
            words = ",".join(h["confirm"] or h["draft"]) or "-"
            print(f"    · [{tag}] {(h.get('published_at') or '')[:10]} {h['title'][:60]} ({words})")
            print(f"      {h['url']}")


def print_list(data: dict) -> None:
    print(f"기준 : {data['basis']['document']} ({data['basis']['announced']})")
    rules = data["rules"]
    for key in ("correction_min", "correction_max", "land_contribution_coef", "excess_contribution_to_legal"):
        print(f"  {key:<30} {rules[key]}")
    print(f"  {'seoul_avg_land_price_redev':<30} {rules['seoul_avg_land_price_redev']}")
    print("대기 중인 변경 :")
    for rule in policy.pending_rules(data):
        state = f"반영 {rule.applied_at}" if rule.status == "반영" else rule.status
        print(f"  [{state}] {rule.id} — {rule.title} → {rule.apply or '영향 없음'}")


#확인한 기사 URL 을 함께 받아 기록한다 — 무엇을 보고 바꿨는지 파일에 남게
def apply_rule(rule_id: str, source: str, path: Path = policy.POLICY_PATH) -> tuple[dict, dict]:
    data = policy.load(path)
    item = next((p for p in data["pending"] if p["id"] == rule_id), None)
    if item is None:
        raise SystemExit(f"그런 규칙이 없습니다 : {rule_id}")
    if item["status"] == "반영":
        raise SystemExit(f"이미 반영했습니다 : {rule_id} ({item.get('applied_at')})")

    before = {k: data["rules"].get(k) for k in item["apply"]}
    data["rules"].update(item["apply"])
    item["status"] = "반영"
    item["applied_at"] = date.today().isoformat()
    if source not in item["sources"]:
        item["sources"].append(source)
    policy.save(data, path)
    return before, dict(item["apply"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="정비사업 규칙 변경 뉴스 감시 (유지보수용)")
    parser.add_argument("--from-file", help="기사 목록 JSON 으로 검사 (API 키 없이)")
    parser.add_argument("--list", action="store_true", help="지금 규칙 값과 대기 중인 변경")
    parser.add_argument("--apply", metavar="RULE_ID", help="확인한 변경을 rules 에 반영")
    parser.add_argument("--source", help="--apply 때 확인한 기사 URL (필수)")
    parser.add_argument("--policy", default=str(policy.POLICY_PATH), help="규칙 파일 경로")
    parser.add_argument("--size", type=int, default=10, help="검색어당 기사 수")
    args = parser.parse_args(argv)
    path = Path(args.policy)

    if args.list:
        print_list(policy.load(path))
        return 0

    if args.apply:
        if not args.source:
            parser.error("--apply 에는 확인한 기사 URL(--source)이 필요합니다")
        before, after = apply_rule(args.apply, args.source, path)
        print(f"반영 : {args.apply}")
        for k in after:
            print(f"  {k} : {before.get(k)} → {after[k]}")
        print("백엔드를 다시 띄워야 계산에 들어갑니다 (uvicorn --reload 는 .py 만 감시)")
        return 0

    data = policy.load(path)
    rules = policy.pending_rules(data)
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as f:
            articles = json.load(f)
    else:
        key = os.environ.get("KAKAO_API_KEY", "")
        if key in DUMMY_KEYS:
            print("KAKAO_API_KEY 가 없거나 로컬 더미 값입니다. 실제 키로 실행하거나 --from-file 로 기사 목록을 넣어 주세요.")
            return 2
        articles = collect_from_kakao(rules, key, args.size)

    print(f"기사 {len(articles)}건 검사")
    print_report(scan(articles, rules), rules)
    return 0


if __name__ == "__main__":
    sys.exit(main())
