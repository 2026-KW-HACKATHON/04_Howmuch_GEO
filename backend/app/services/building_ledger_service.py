# 건축물대장 조회 (국토교통부 건축HUB, 공공데이터포털 1613000)
#
# 왜 필요한가
#   종전자산 = 토지분 + 건물분 이고, 건물분은 공시지가에 안 들어 있다.
#   건물분을 빼면 개인·구역에 같은 배수가 들어가 분담금에서 약분된다 (수치로 확인했다).
#   여기서 받아오는 값이 그 약분을 깨는 유일한 실체다.
#
# 엔드포인트
#   getBrTitleInfo          표제부   — 연면적·구조·사용승인일·세대수 (동별)
#   getBrExposPubuseAreaInfo 전유공용 — 호별 전유면적. 집합건물에서 내 몫을 나누는 데 쓴다
#   getBrRecapTitleInfo     총괄표제부 — 단지 공식 세대수·용적률 산정 연면적 (아파트 필지만, 재건축 판정·계산)
#   getBrAtchJibunInfo      부속지번 — 건물 없이 단지에 묶인 필지 (아파트 필지만, 재건축 판정)
#
# PNU(19자리) → 건축물대장 파라미터
#   PNU = 법정동코드(10) + 필지구분(1) + 본번(4) + 부번(4)
#         법정동코드(10) = 시군구(5) + 법정동(5)
#         필지구분 1=일반(대지) → platGbCd 0,  2=산 → platGbCd 1
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

TITLE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
EXPOS_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"
RECAP_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo"
ATCH_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrAtchJibunInfo"

#부속지번은 표제부(동)마다 같은 지번이 반복된다 (미미삼 13번지 = 44행, 모두 17번지). 몇 페이지면 충분하다
MAX_ATCH_PAGES = 5

#한 필지에 동·호가 많을 수 있다. 단독주택은 1~3건, 대단지 아파트는 한 필지에 8개 동도 있다
#  ※ pageNo 를 보내지 않으면 이 API 는 numOfRows 를 무시하고 1건만 돌려준다 (실측).
#    그래서 _rows 가 pageNo 를 항상 붙인다 — 빠뜨리면 아파트 연면적이 한 동치만 잡힌다
#  ※ numOfRows 상한은 100 이다. 더 크게 요청해도 서버가 100 으로 깎는다 (실측).
#    1000 을 보내고 1000행 받았다고 믿으면 전유면적 합계가 1/10 로 잡힌다
API_MAX_ROWS = 100

#표제부는 한 필지의 동 수만큼이라 몇 페이지면 충분하다 (대단지 8개 동)
MAX_TITLE_PAGES = 5

#전유공용은 호 × 면적구분마다 한 행이라 금방 수천 행이 된다 (월계동 12번지 = 3,670행 = 37페이지).
#  상한을 넘으면 합계가 과소집계되므로 0 을 돌려주고 세대수 균등분할로 떨어진다 — 조용히 틀리지 않게
MAX_EXPOS_PAGES = 50

#건축HUB 는 동시 호출에 민감하다. 병렬로 던지면 HTTPError 가 쏟아진다 (실측)
CALL_GAP = 0.12

SESSION = requests.Session()
#건축HUB 는 간헐적으로 503 SERVICETIMEOUT_ERROR 를 낸다 (실측 3회 중 1회).
#  필지마다 호출하므로 재시도가 없으면 구역의 1/3 이 나대지로 떨어져 건물분이 크게 과소된다.
#  (485필지 구역이면 160필지가 날아간다 — 경고는 뜨지만 숫자가 크게 틀어진다)
SESSION.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=5,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
    ),
)

#200 인데 본문이 비거나 JSON 이 아닌 경우도 있다 (Retry 가 못 잡는다). 그때 직접 다시 부른다
JSON_RETRY = 3

#주용도로 주거 여부를 걸러내지 않는다.
#  처음에는 주거용 주용도만 세대수를 셌는데, 월계동 실측에서 356명이 누락됐다.
#  상가주택(1층 근생 + 2~3층 주택)은 주용도가 '근린생활시설' 로 등록되지만 세대가 여럿이고,
#  월계동 321-2번지는 주용도 근생인데 106세대·연면적 18,130㎡(주상복합)다.
#  건축물대장의 세대·가구 수는 주용도와 무관하게 실제 주거 단위를 뜻하므로 그대로 신뢰한다.
#  비주거 건물은 애초에 hhldCnt·fmlyCnt 가 0 이라 1 로 떨어진다.
#  (재개발 대상지 487필지 기준 2,595 → 2,780명, +7.1%. 조합원 수는 사업이익의 분모라 영향이 크다)


@dataclass
class BuildingLedger:
    pnu: str
    floor_area_m2: float = 0.0        # 연면적 합계(㎡). 건물분 계산의 바탕
    structure: str = ""               # 대표 구조 (연면적이 가장 큰 동)
    approval_ymd: str = ""            # 사용승인일 YYYYMMDD
    elapsed_years: float = 0.0        # 경과연수 = 평가시점 − 사용승인일
    household_count: int = 1          # 세대·가구 수. 조합원 수 실측에 쓴다
    is_condo: bool = False            # 집합건물 여부 (한 필지에 조합원이 여럿)
    main_purpose: str = ""            # 주용도
    etc_purpose: str = ""             # 기타용도 (공동주택이면 아파트·다세대주택 등)
    floors: int = 0                   # 지상층수 (대표 동). 공동주택에서 아파트(주택 5개 층 이상)를 가른다
    has_building: bool = False        # False 면 나대지 → 건물분 0
    fallback: bool = False            # 조회 실패. 건물분을 못 구한 상태
    warnings: list[str] = field(default_factory=list)


def _service_key() -> str | None:
    #.env 는 사용자 영역이라 코드가 쓰지 않는다. 없으면 건물분 없이(나대지로) 계산된다
    return os.getenv("BLDRGST_API_KEY") or os.getenv("BUILDING_LEDGER_API_KEY")


#PNU → (시군구, 법정동, 필지구분, 본번, 부번)
def parse_pnu(pnu: str) -> tuple[str, str, str, str, str] | None:
    pnu = (pnu or "").strip()
    if len(pnu) != 19 or not pnu.isdigit():
        return None
    return (
        pnu[0:5],                       # sigunguCd
        pnu[5:10],                      # bjdongCd
        "1" if pnu[10] == "2" else "0",  # platGbCd : 산이면 1
        pnu[11:15],                     # bun
        pnu[15:19],                     # ji
    )


def _page(url: str, params: dict, page_no: int, rows_per_page: int) -> tuple[list[dict], int]:
    #pageNo 는 반드시 보낸다. 없으면 numOfRows 가 무시되고 1건만 온다
    call = {**params, "numOfRows": rows_per_page, "pageNo": page_no}

    payload = None
    last_error: Exception | None = None
    for attempt in range(JSON_RETRY):
        if attempt:
            time.sleep(CALL_GAP * (attempt + 1))
        response = SESSION.get(url, params=call, timeout=15)
        try:
            payload = response.json()
        except ValueError as err:
            #200 인데 본문이 비었거나 JSON 이 아니다. 재시도 대상
            last_error = err
            payload = None
            continue

        #정상 응답은 "response" 키를 갖는다.
        #  장애 시에는 OpenAPI_ServiceResponse.cmmMsgHeader 로 온다 (503 SERVICETIMEOUT_ERROR 등)
        if "response" in payload:
            break

        fault = (payload.get("OpenAPI_ServiceResponse") or {}).get("cmmMsgHeader") or {}
        last_error = RuntimeError(
            f"{fault.get('errMsg') or 'UNKNOWN'} / {fault.get('returnAuthMsg') or response.status_code}"
        )
        payload = None

    if payload is None:
        raise last_error or RuntimeError("건축물대장 응답을 받지 못했습니다")

    body = payload.get("response", {}).get("body", {})

    try:
        total = int(body.get("totalCount") or 0)
    except (TypeError, ValueError):
        total = 0

    items = body.get("items") or {}

    #건수가 0 이면 items 가 빈 문자열로 오기도 한다
    if not isinstance(items, dict):
        return [], total

    rows = items.get("item")
    if rows is None:
        return [], total
    return (rows if isinstance(rows, list) else [rows]), total


#전체 페이지를 모아서 돌려준다. totalCount 를 보고 필요한 만큼만 더 부른다
def _rows(url: str, params: dict, max_pages: int) -> tuple[list[dict], int]:
    collected, total = _page(url, params, 1, API_MAX_ROWS)
    if not collected:
        return [], total

    pages = min(-(-total // API_MAX_ROWS), max_pages)
    for page_no in range(2, pages + 1):
        time.sleep(CALL_GAP)
        more, _ = _page(url, params, page_no, API_MAX_ROWS)
        if not more:
            break
        collected += more

    return collected, total


def _f(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _i(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


#사용승인일 → 경과연수. 기준시점을 넘기면 그 시점으로 센다
def elapsed_years(approval_ymd: str, as_of: date | None = None) -> float:
    if not approval_ymd or len(approval_ymd) < 4:
        return 0.0
    as_of = as_of or date.today()
    try:
        year = int(approval_ymd[0:4])
        month = int(approval_ymd[4:6]) if len(approval_ymd) >= 6 else 1
    except ValueError:
        return 0.0
    years = (as_of.year - year) + (as_of.month - max(month, 1)) / 12.0
    return max(years, 0.0)


#필지 1건의 건축물대장 요약
#  실패해도 예외를 올리지 않는다 — 건물분을 0 으로 두면 나대지가 되어 기존 동작과 같다.
#  조용히 틀리는 쪽이 아니라 "못 구했다"(fallback=True)를 남기는 쪽을 택한다
def fetch_building(pnu: str, as_of: date | None = None) -> BuildingLedger:
    result = BuildingLedger(pnu=pnu)
    parts = parse_pnu(pnu)
    if parts is None:
        result.fallback = True
        result.warnings.append(f"PNU 형식이 아닙니다: {pnu}")
        return result

    key = _service_key()
    if not key:
        result.fallback = True
        result.warnings.append("건축물대장 API 키(BLDRGST_API_KEY)가 없어 건물분을 계산하지 못했습니다.")
        return result

    sigungu, bjdong, plat_gb, bun, ji = parts
    base = {
        "serviceKey": key, "sigunguCd": sigungu, "bjdongCd": bjdong,
        "platGbCd": plat_gb, "bun": bun, "ji": ji, "_type": "json",
    }

    try:
        titles, _ = _rows(TITLE_URL, base, MAX_TITLE_PAGES)
    except Exception as err:
        logger.warning(f"[ Log ] : 건축물대장 표제부 조회 실패 {pnu} : {err}")
        result.fallback = True
        result.warnings.append("건축물대장을 조회하지 못해 건물분을 0 으로 두었습니다.")
        return result

    #표제부가 없으면 나대지다. 오류가 아니라 정상적인 결과다
    if not titles:
        return result

    result.has_building = True
    result.floor_area_m2 = sum(_f(row.get("totArea")) for row in titles)

    #대표 용도·구조·층수·사용승인일은 연면적이 가장 큰 동에서 가져온다 (여러 동이면 그 동이 지배적이다).
    #  단 세대가 있는 동이 있으면 그중에서 고른다 — 신축 대단지는 지하주차장이 한 동으로 등록돼
    #  연면적이 가장 크다 (그랑빌 3,003세대 : 기타용도 '지하주차장…' · 지상 0층). 그 동을 대표로 쓰면
    #  아파트 판정(공동주택 + 기타용도 '아파트' 또는 5층 이상)에 실패해 재개발로 잘못 판정된다
    housing_rows = [row for row in titles if _i(row.get("hhldCnt")) > 0 or _i(row.get("fmlyCnt")) > 0]
    main = max(housing_rows or titles, key=lambda row: _f(row.get("totArea")))
    result.structure = (main.get("strctCdNm") or "").strip()
    result.main_purpose = (main.get("mainPurpsCdNm") or "").strip()
    result.etc_purpose = (main.get("etcPurps") or "").strip()
    result.floors = _i(main.get("grndFlrCnt"))
    result.approval_ymd = (main.get("useAprDay") or "").strip()
    result.elapsed_years = elapsed_years(result.approval_ymd, as_of)

    #집합건물 여부. 대장종류가 '집합' 이거나 세대수가 2 이상이면 조합원이 여럿이다
    kinds = " ".join((row.get("regstrKindCdNm") or "") for row in titles)
    hhld = sum(_i(row.get("hhldCnt")) for row in titles)
    fmly = sum(_i(row.get("fmlyCnt")) for row in titles)

    #단독주택은 hhldCnt=0, fmlyCnt=1 로 온다 (실측).
    #  다가구는 fmlyCnt 가 세대수(월계동 단독주택 471건 중 140건이 fmlyCnt>1, 최대 16),
    #  공동주택은 hhldCnt 가 세대수(최대 275)다. 둘 중 큰 값을 쓴다
    result.household_count = max(hhld, fmly, 1)
    result.is_condo = "집합" in kinds or result.household_count > 1

    #전유면적 합계는 여기서 받지 않는다.
    #  호·면적구분마다 한 행이라 대단지는 수천 행이고(월계동 12번지 = 3,670행),
    #  구역 전 필지에 대해 받으면 /zone 이 몇 분씩 걸린다.
    #  실제로 쓰이는 건 "내 필지" 하나뿐이고, 그것도 사용자가 전유면적을 입력했을 때만이다.
    #  → fetch_exclusive_total() 로 떼어내 /contribution 이 필요할 때만 부른다
    return result


#집합건물 전유면적 합계(㎡). 집합건물에서 내 몫을 나누는 분모다
#   내 몫 = 내 전유면적 ÷ 이 합계
#  연면적(totArea)으로 나누면 공용면적까지 분모에 들어가 내 몫이 과소평가된다.
#  '전유' 이면서 '주건축물' 인 행만 센다 — 부속건축물(창고·주차장)은 지분 분모가 아니다
def fetch_exclusive_total(pnu: str) -> float:
    parts = parse_pnu(pnu)
    key = _service_key()
    if parts is None or not key:
        return 0.0

    sigungu, bjdong, plat_gb, bun, ji = parts
    base = {
        "serviceKey": key, "sigunguCd": sigungu, "bjdongCd": bjdong,
        "platGbCd": plat_gb, "bun": bun, "ji": ji, "_type": "json",
    }

    try:
        rows, total = _rows(EXPOS_URL, base, MAX_EXPOS_PAGES)
    except Exception as err:
        logger.warning(f"[ Log ] : 건축물대장 전유공용 조회 실패 {pnu} : {err}")
        return 0.0

    #다 못 받았으면 합계가 과소집계된다. 틀린 값을 주는 대신 0 (= 세대수 균등분할)
    if total > len(rows):
        logger.warning(f"[ Log ] : 전유공용 {total}행 중 {len(rows)}행만 수신 {pnu} — 합계 포기")
        return 0.0

    return sum(
        _f(row.get("area")) for row in rows
        if "전유" in (row.get("exposPubuseGbCdNm") or "")
        and "부속" not in (row.get("mainAtchGbCdNm") or "")
    )


#아파트 단지 정보 — 재건축 판정·계산에 쓴다. 아파트 필지에만 부른다 (구역 전 필지에 부르면 /zone 이 느려진다)
@dataclass
class ApartmentComplex:
    pnu: str
    households: int = 0          # 총괄표제부 세대수 (공식). 표제부 합계는 부속동 등으로 어긋난다 (미미삼 4,033 vs 3,930)
    far_area_m2: float = 0.0     # 용적률 산정 연면적 → 현황용적률 = 이 값 ÷ (단지 + 부속지번 대지면적)
    annex_pnus: list[str] = field(default_factory=list)  # 부속지번 PNU (건물 없이 단지에 묶인 필지, 미미삼 17번지)
    recap_found: bool = False    # 총괄표제부가 있었나 (한 동짜리 단지는 없을 수 있다 → 표제부로 대신한다)
    #상가 등 비주거 건물 — 재건축 조합원이지만 공동주택가격이 없다 → 토지 지분 + 건물 원가법으로 따로 잡는다.
    #  표제부에서 주용도가 공동주택이 아닌 동(근린생활시설·노유자시설 등)이다. 공동주택 부대시설(노인정·관리사무소·기계실)은
    #  주용도가 공동주택이라 빠진다 — 공용이라 따로 소유자가 없다
    #  호수 = hoCnt, 없으면 hhldCnt(상가동이 세대수 칸에 호수를 적기도 한다 : 미미삼 가동 55·나동 48), 둘 다 0 이면 1 (일반건축물 한 채)
    commercial_units: int = 0
    commercial_floor_area_m2: float = 0.0
    commercial_structure: str = ""
    commercial_approval_ymd: str = ""
    total_floor_area_m2: float = 0.0     # 단지 표제부 연면적 합계 — 상가 토지 지분(연면적 비율)의 분모
    fallback: bool = False


def fetch_apartment_complex(pnu: str) -> ApartmentComplex:
    result = ApartmentComplex(pnu=pnu)
    parts = parse_pnu(pnu)
    key = _service_key()
    if parts is None or not key:
        result.fallback = True
        return result

    sigungu, bjdong, plat_gb, bun, ji = parts
    base = {
        "serviceKey": key, "sigunguCd": sigungu, "bjdongCd": bjdong,
        "platGbCd": plat_gb, "bun": bun, "ji": ji, "_type": "json",
    }

    try:
        recaps, _ = _rows(RECAP_URL, base, 1)
        #총괄표제부는 용도별로 여러 행일 수 있다 (미미삼 : 공동주택 3,930세대 + 교육연구및복지시설 0세대).
        #  세대수는 더하고, 용적률 산정 연면적은 대지 전체 값이 행마다 같게 들어 있어 큰 값을 쓴다
        time.sleep(CALL_GAP)
        titles, _ = _rows(TITLE_URL, base, MAX_TITLE_PAGES)
        if recaps:
            result.recap_found = True
            result.households = sum(_i(row.get("hhldCnt")) for row in recaps)
            result.far_area_m2 = max(_f(row.get("vlRatEstmTotArea")) for row in recaps)
        else:
            result.households = sum(_i(row.get("hhldCnt")) for row in titles if "공동주택" in (row.get("mainPurpsCdNm") or ""))
            result.far_area_m2 = sum(_f(row.get("vlRatEstmTotArea")) for row in titles)

        result.total_floor_area_m2 = sum(_f(row.get("totArea")) for row in titles)
        shops = [row for row in titles if "공동주택" not in (row.get("mainPurpsCdNm") or "") and _f(row.get("totArea")) > 0]
        if shops:
            result.commercial_units = sum(_i(row.get("hoCnt")) or _i(row.get("hhldCnt")) or 1 for row in shops)
            result.commercial_floor_area_m2 = sum(_f(row.get("totArea")) for row in shops)
            main_shop = max(shops, key=lambda row: _f(row.get("totArea")))
            result.commercial_structure = (main_shop.get("strctCdNm") or "").strip()
            result.commercial_approval_ymd = (main_shop.get("useAprDay") or "").strip()

        time.sleep(CALL_GAP)
        atch, _ = _rows(ATCH_URL, base, MAX_ATCH_PAGES)
        annex = []
        for row in atch:
            a_bun, a_ji = (row.get("atchBun") or "").strip(), (row.get("atchJi") or "").strip()
            if not a_bun.isdigit():
                continue
            a_sigungu = (row.get("atchSigunguCd") or sigungu).strip() or sigungu
            a_bjdong = (row.get("atchBjdongCd") or bjdong).strip() or bjdong
            a_plat = "2" if (row.get("atchPlatGbCd") or "0").strip() == "1" else "1"
            annex_pnu = f"{a_sigungu}{a_bjdong}{a_plat}{int(a_bun):04d}{int(a_ji or 0):04d}"
            if annex_pnu != pnu and annex_pnu not in annex:
                annex.append(annex_pnu)
        result.annex_pnus = annex
    except Exception as err:
        logger.warning(f"[ Log ] : 건축물대장 총괄표제부·부속지번 조회 실패 {pnu} : {err}")
        result.fallback = True
    return result

