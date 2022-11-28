from models import (
    EuroJackpot as EuroJackpotPayload,
    PrizeTier as PrizeTierPayload,
    Result as ResultPayload
)
from typing import Optional


class Result:

    def __init__(self, payload: ResultPayload):
        self.primary = payload["primary"]
        self.secondary = payload["secondary"]


class PrizeTier:

    def __init__(self, payload: PrizeTierPayload):
        self.share_count = payload["shareCount"]
        self.share_amount = payload["shareAmount"]
        self.name = payload["name"]
        self.id = payload["id"]
        self.additional_prize_tier = payload["additionalPrizeTier"]


class EuroJackpot:

    def __init__(self, payload: EuroJackpotPayload):
        self.game_name = payload["gameName"]
        self.brand_name = payload["brandName"]
        self.id = payload["id"]
        self.name = payload["name"]
        self.status = payload["status"]
        self.open_time = payload["openTime"]
        self.close_time = payload["closeTime"]
        self.draw_time = payload["drawTime"]
        self.results_available_time = payload["resultsAvailableTime"]
        self.results = [Result(result) for result in payload["results"]]
        self.prize_tiers = [PrizeTier(prize_tier) for prize_tier in payload["prizeTiers"]]

    @property
    def biggest_prize_tier(self) -> Optional[PrizeTier]:
        biggest_share = 0
        biggest_prize_tier = None
        for prize_tier in self.prize_tiers:

            share_amount = prize_tier.share_amount
            if share_amount > biggest_share:
                biggest_prize_tier = prize_tier
                biggest_share = prize_tier.share_amount

        return biggest_prize_tier
