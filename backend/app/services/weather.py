from typing import Callable

from ..config import settings
from ..errors import validation

SAMPLES = {
    "울산": (17.6, "맑음", 52, 3.2),
    "거제": (18.9, "구름조금", 61, 4.1),
    "목포": (16.2, "흐림", 70, 5.0),
}
# 공급자 이름 -> 지역을 받아 {obsDt,tempC,condition,humidity,windMs}를 돌려주는 함수. 실제 공급자가 아직 없다.
PROVIDERS: dict[str, Callable[[str], dict]] = {}


def _sample(region: str, error: str) -> dict:
    temp, condition, humidity, wind = SAMPLES[region]
    return {
        "region": region, "source": "SAMPLE", "obsDt": settings.today, "tempC": temp,
        "condition": condition, "humidity": humidity, "windMs": wind, "error": error,
    }


def get_weather(region: str) -> dict:
    if region not in SAMPLES:
        raise validation("region", "지원하지 않는 지역입니다.")
    name = settings.weather_provider
    if not name:
        return _sample(region, "날씨 공급자가 설정되지 않았습니다.")
    provider = PROVIDERS.get(name)
    if provider is None:
        return _sample(region, f"등록되지 않은 날씨 공급자입니다: {name}")
    try:
        data = provider(region)
        return {
            "region": region, "source": "LIVE", "obsDt": str(data["obsDt"]), "tempC": float(data["tempC"]),
            "condition": str(data["condition"]), "humidity": float(data["humidity"]),
            "windMs": float(data["windMs"]), "error": None,
        }
    except Exception as exc:  # 공급자 장애·형식 오류는 어떤 예외든 샘플로 대체한다
        return _sample(region, f"날씨 공급자 오류: {exc!r}")
