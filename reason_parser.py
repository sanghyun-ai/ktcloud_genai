import re
from typing import Dict, Any

# ============================
# 공통 유틸 함수
# ============================

EXTRA_KEYWORDS = [
    "신상정보 등록", "신상정보 제출", "신상정보",
    "공개명령", "고지명령", "취업제한",
    "보호관찰", "사회봉사", "수강명령", "치료프로그램"
]


def clean_text(text: str) -> str:
    """기본 클린: None 처리 + 캐리지 리턴 제거 + 양끝 공백 제거"""
    if text is None:
        return ""
    text = text.replace("\r", "")
    return text.strip()


def remove_header_yanghyung(text: str) -> str:
    """
    맨 위에 '양형의 이유' 헤더가 있으면 제거.
    (is_sentencing 플래그로 '양형이 있는 사건인지'는 따로 표시할 것)
    """
    t = text.lstrip()
    if t.startswith("양형의 이유"):
        t = t[len("양형의 이유"):].lstrip(" \n")
    return t


def detect_is_sentencing(raw_text: str) -> bool:
    """
    양형이 있는 사건인지 여부 플래그.
    - 텍스트가 비어있으면 False
    - 그 외에는 True로 두는 보수적 설정
      (원하면 '양형의 이유' 포함 여부로 더 엄격하게 체크 가능)
    """
    if raw_text is None:
        return False
    return bool(clean_text(raw_text))


# ============================
# 타입 분류기
# ============================

def classify_reason_type(raw_text: str) -> str:
    """
    actual_reason 원문을 받아서 7가지 타입 중 하나로 분류한다.
    1) omitted
    2) structured_sections
    3) bullets_only
    4) num_plus_bullets
    5) simple_narrative
    6) with_extras
    7) very_short
    """
    text = clean_text(raw_text)
    if not text:
        return "omitted"

    text_no_header = remove_header_yanghyung(text)

    # 1. 생략형: '생략' + 아주 짧은 경우
    if "생략" in text_no_header and len(text_no_header) < 50:
        return "omitted"

    # 플래그들
    has_extras = any(k in text for k in EXTRA_KEYWORDS)
    has_bullets = "○" in text
    has_section_numbers = bool(re.search(r"\n\s*\d+\.", text))

    # 짧은 템플릿형 판단: 헤더 제거 후 글자 수 기준
    plain = text_no_header.replace("\n", "").strip()
    is_very_short = 0 < len(plain) <= 80

    # 분류 우선순위
    if has_extras:
        return "with_extras"
    if has_section_numbers and has_bullets:
        return "num_plus_bullets"
    if has_section_numbers:
        return "structured_sections"
    if has_bullets:
        return "bullets_only"
    if is_very_short:
        return "very_short"
    return "simple_narrative"


# ============================
# 타입별 파서 함수들
# ============================

def parse_omitted(text_no_header: str) -> Dict[str, Any]:
    """
    1. 생략형 (omitted)
    예: '양형의 이유\n생략'
    """
    return {
        "reason_main": "",
        "reason_sections": {},
        "reason_bullets": {},
        "reason_extras": "",
        "reason_flags": {
            "is_omitted": True
        }
    }


def split_main_and_extras(text_no_header: str) -> (str, str):
    """
    6. with_extras (양형 이유 + 신상정보/고지명령 등)
    키워드를 기준으로 앞(양형 이유) / 뒤(extras) 분리
    """
    idxs = []
    for k in EXTRA_KEYWORDS:
        pos = text_no_header.find(k)
        if pos != -1:
            idxs.append(pos)

    if not idxs:
        return text_no_header, ""

    split_pos = min(idxs)
    main = text_no_header[:split_pos].rstrip()
    extras = text_no_header[split_pos:].lstrip()
    return main, extras


def parse_with_extras(text_no_header: str) -> Dict[str, Any]:
    """
    6. with_extras 타입 처리:
    - 양형 이유 본문 + 신상정보·고지명령 등 extras 분리
    """
    main, extras = split_main_and_extras(text_no_header)
    return {
        "reason_main": main.strip(),
        "reason_sections": {},
        "reason_bullets": {},
        "reason_extras": extras.strip(),
        "reason_flags": {
            "has_extras": True
        }
    }


def parse_bullets_block(text_no_header: str) -> Dict[str, list]:
    """
    bullet형 공통 파서:
    '○ 유리한 정상: ...' → {favorable: [...], unfavorable: [...], other: [...]}
    """
    bullets = {"favorable": [], "unfavorable": [], "other": []}
    lines = text_no_header.split("\n")

    for line in lines:
        line = line.strip()
        if not line.startswith("○"):
            continue

        # '○' 제거
        content = line.lstrip("○").strip()

        category = "other"
        # 카테고리 및 라벨 제거
        if "유리한 정상" in content or "유리한 양형" in content:
            category = "favorable"
            content = content.replace("유리한 정상:", "").replace("유리한 정상", "")
        elif "불리한 정상" in content or "불리한 양형" in content:
            category = "unfavorable"
            content = content.replace("불리한 정상:", "").replace("불리한 정상", "")
        elif content.startswith("그 밖에") or content.startswith("그밖에") or "기타" in content:
            category = "other"
            content = re.sub(r"^그[^\:]*\:", "", content).strip()

        # 쉼표 기준 요소 분리
        parts = [p.strip() for p in content.split(",") if p.strip()]
        bullets[category].extend(parts)

    return bullets


def parse_bullets_only(text_no_header: str) -> Dict[str, Any]:
    """
    3. 동그라미 bullet형 (bullets_only)
    """
    bullets = parse_bullets_block(text_no_header)
    return {
        "reason_main": "",
        "reason_sections": {},
        "reason_bullets": bullets,
        "reason_extras": "",
        "reason_flags": {
            "has_bullets": True
        }
    }


def parse_structured_sections(text_no_header: str) -> Dict[str, Any]:
    """
    2. 번호 구조형 (structured_sections)
    1. 법률상 처단형의 범위
    2. 양형기준에 따른 권고형의 범위
    3. 선고형의 결정
    """
    sections: Dict[str, Any] = {}
    pattern = re.compile(r"^\s*(\d+)\.\s*(.+)$", re.MULTILINE)

    matches = list(pattern.finditer(text_no_header))
    if not matches:
        return {
            "reason_main": text_no_header.strip(),
            "reason_sections": {},
            "reason_bullets": {},
            "reason_extras": "",
            "reason_flags": {}
        }

    for i, m in enumerate(matches):
        num = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text_no_header)

        body = text_no_header[start:end].strip()

        if "법률상 처단형" in title or "처단형의 범위" in title:
            key = "law_range"
        elif "양형기준" in title:
            key = "guideline"
        elif "선고형의 결정" in title or "선고형" in title:
            key = "decision"
        else:
            key = f"etc_{num}"

        sections[key] = body if body else title

    flags = {}
    if "guideline" in sections:
        flags["has_guideline"] = True

    return {
        "reason_main": "",
        "reason_sections": sections,
        "reason_bullets": {},
        "reason_extras": "",
        "reason_flags": flags
    }


def parse_num_plus_bullets(text_no_header: str) -> Dict[str, Any]:
    """
    4. 번호 + bullet 혼합형 (num_plus_bullets)
    1. 선고형의 결정
    ○ 유리한 정상: ...
    ○ 불리한 정상: ...
    """
    # 1. ~ 선고형의 결정 찾기
    m = re.search(r"^\s*1\.\s*(.+)$", text_no_header, flags=re.MULTILINE)
    header = None
    body = text_no_header
    if m:
        header = m.group(1).strip()
        body = text_no_header[m.end():].strip()

    bullets = parse_bullets_block(body)

    sections = {
        "decision": {
            "header": header or "선고형의 결정",
            "favorable": bullets["favorable"],
            "unfavorable": bullets["unfavorable"],
            "other": bullets["other"],
        }
    }

    return {
        "reason_main": "",
        "reason_sections": sections,
        "reason_bullets": {},
        "reason_extras": "",
        "reason_flags": {}
    }


def parse_very_short(text_no_header: str) -> Dict[str, Any]:
    """
    7. 짧은 템플릿형 (very_short)
    한두 문장짜리 템플릿 수준
    """
    main = text_no_header.replace("\n", " ").strip()
    return {
        "reason_main": main,
        "reason_sections": {},
        "reason_bullets": {},
        "reason_extras": "",
        "reason_flags": {
            "is_low_info": True
        }
    }


def parse_simple_narrative(text_no_header: str) -> Dict[str, Any]:
    """
    5. 단순 서술형 (simple_narrative)
    줄바꿈/공백만 정리해서 그대로 보존
    """
    text = re.sub(r"[ \t]+", " ", text_no_header)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text).strip()
    return {
        "reason_main": text,
        "reason_sections": {},
        "reason_bullets": {},
        "reason_extras": "",
        "reason_flags": {}
    }


# ============================
# 메인 엔트리 함수
# ============================

def parse_actual_reason(raw_text: str) -> Dict[str, Any]:
    """
    actual_reason 원문 하나를 받아서
    - reason_type
    - reason_main / reason_sections / reason_bullets / reason_extras / reason_flags
    - + is_sentencing 플래그
    를 포함한 dict를 반환한다.
    """
    cleaned = clean_text(raw_text)
    text_no_header = remove_header_yanghyung(cleaned)
    reason_type = classify_reason_type(raw_text)
    is_sentencing = detect_is_sentencing(raw_text)

    # 타입별 파서 디스패치
    if reason_type == "omitted":
        parsed = parse_omitted(text_no_header)
    elif reason_type == "with_extras":
        parsed = parse_with_extras(text_no_header)
    elif reason_type == "num_plus_bullets":
        parsed = parse_num_plus_bullets(text_no_header)
    elif reason_type == "structured_sections":
        parsed = parse_structured_sections(text_no_header)
    elif reason_type == "bullets_only":
        parsed = parse_bullets_only(text_no_header)
    elif reason_type == "very_short":
        parsed = parse_very_short(text_no_header)
    elif reason_type == "simple_narrative":
        parsed = parse_simple_narrative(text_no_header)
    else:
        # 예외적으로 타입이 인식 안 되면 simple_narrative처럼 처리
        parsed = parse_simple_narrative(text_no_header)

    # 공통 필드 + is_sentencing 플래그 합치기
    result: Dict[str, Any] = {
        "reason_type": reason_type,
        "reason_main": parsed.get("reason_main", ""),
        "reason_sections": parsed.get("reason_sections", {}),
        "reason_bullets": parsed.get("reason_bullets", {}),
        "reason_extras": parsed.get("reason_extras", ""),
        "reason_flags": parsed.get("reason_flags", {})
    }

    # 양형 여부 플래그 추가
    # (이미 있는 reason_flags에 병합)
    result["reason_flags"]["is_sentencing"] = is_sentencing

    return result
