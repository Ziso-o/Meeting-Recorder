"""회의 링크(URL) → {platform, native_meeting_id} 파싱.

목적: 사용자가 **회의 링크만** 보내면 자동으로 platform/회의ID를 뽑아 Vexa에
`POST /bots` 하도록 한다. ("링크 보내면 알아서 참가")

지원: Google Meet / Zoom / Jitsi(정확) · Teams(best-effort).
platform 값은 Vexa 규격: google_meet / zoom / teams / jitsi.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def parse_meeting_url(url: str) -> dict[str, str]:
    """회의 링크에서 {platform, native_meeting_id, (passcode)} 추출.

    링크가 아니라 이미 코드만 온 경우(예: 'abc-defg-hij')는 google_meet로 간주.
    인식 못하면 ValueError.
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("빈 링크")

    # URL이 아니고 코드 형태면 Google Meet 코드로 간주(xxx-xxxx-xxx)
    if "://" not in raw and "." not in raw and "/" not in raw:
        return {"platform": "google_meet", "native_meeting_id": raw}

    u = urlparse(raw if "://" in raw else "https://" + raw)
    host = (u.hostname or "").lower()
    segs = [s for s in u.path.split("/") if s]
    q = parse_qs(u.query)

    # --- Google Meet: meet.google.com/abc-defg-hij ---
    if "meet.google.com" in host:
        if not segs:
            raise ValueError("Google Meet 코드를 찾을 수 없음")
        return {"platform": "google_meet", "native_meeting_id": segs[0]}

    # --- Zoom: .../j/1234567890 또는 .../wc/1234567890/join (?pwd=...) ---
    if "zoom.us" in host or "zoom.com" in host:
        mid = ""
        for i, s in enumerate(segs):
            if s in ("j", "wc") and i + 1 < len(segs):
                mid = segs[i + 1]
                break
        if not mid:
            digits = [s for s in segs if s.isdigit()]
            mid = digits[-1] if digits else ""
        if not mid:
            raise ValueError("Zoom 회의번호를 찾을 수 없음")
        out = {"platform": "zoom", "native_meeting_id": mid}
        if "pwd" in q:
            out["passcode"] = q["pwd"][0]
        return out

    # --- Jitsi: meet.jit.si/RoomName ---
    if "jit.si" in host or "jitsi" in host:
        if not segs:
            raise ValueError("Jitsi 방 이름을 찾을 수 없음")
        return {"platform": "jitsi", "native_meeting_id": segs[0]}

    # --- Teams ---
    if "teams.microsoft" in host or "teams.live" in host:
        # teams.live.com/meet/<id> → 숫자 회의ID 추출
        if "meet" in segs:
            i = segs.index("meet")
            if i + 1 < len(segs):
                return {"platform": "teams", "native_meeting_id": segs[i + 1]}
        # teams.microsoft.com/l/meetup-join/... 등은 구조가 복잡 → best-effort(전체 URL)
        return {"platform": "teams", "native_meeting_id": raw, "_note": "teams-id-verify"}

    raise ValueError(f"인식하지 못한 회의 링크(host={host!r})")
