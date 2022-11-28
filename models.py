from typing import TypedDict, List


class Result(TypedDict):
    primary: List[str]
    secondary: List[str]


class PrizeTier(TypedDict):
    shareCount: int
    shareAmount: int
    name: str
    id: str
    additionalPrizeTier: bool


class EuroJackpot(TypedDict):
    gameName: str
    brandName: str
    id: int
    name: str
    status: str
    openTime: int
    closeTime: int
    drawTime: int
    resultsAvailableTime: int
    results: List[Result]
    prizeTiers: List[PrizeTier]
