import requests
import datetime
from eurojackpot import EuroJackpot
from typing import List, Union, Tuple


def get_eurojackpot_results() -> List[EuroJackpot]:
    now = datetime.datetime.now()

    week = now.isocalendar().week - 1
    year = now.isocalendar().year

    r = requests.get(
        f"https://www.veikkaus.fi/api/draw-results/v1/games/EJACKPOT/draws/by-week/{year}-W{week}").json()

    if len(r) == 0:
        return []

    return [EuroJackpot(e) for e in r]


def calculate_hits(eurojackpot: EuroJackpot, primary_numbers: List[str], secondary_numbers: List[str]) -> Tuple[int, int, int, int]:
    primary_results = eurojackpot.results[0].primary
    secondary_results = eurojackpot.results[0].secondary

    primary_hits = 0
    for number in primary_results:
        if number in primary_numbers:
            primary_hits += 1

    secondary_hits = 0
    for number in secondary_results:
        if number in secondary_numbers:
            secondary_hits += 1

    total_hits = f"{primary_hits}+{secondary_hits} oikein"

    money_won = 0
    for prize_tier in eurojackpot.prize_tiers:
        if prize_tier.name == total_hits:
            money_won = prize_tier.share_amount
            break

    investment_value_old = 200  # get_investment_value()
    investment_value_new = investment_value_old - 200 + money_won

    return primary_hits, secondary_hits, money_won, investment_value_new


def generate_discord_msg(primary_numbers: List[Union[int, str]], secondary_numbers: List[Union[int, str]]) -> str:
    primary_numbers = [str(i) for i in primary_numbers]
    secondary_numbers = [str(i) for i in secondary_numbers]

    ejackpot_messages = []
    results = get_eurojackpot_results()
    if not results:
        return "Tuloksia ei saatu Veikkaukselta :("

    for result in results:
        info = calculate_hits(result, primary_numbers, secondary_numbers)

        primary_hits = info[0]
        secondary_hits = info[1]
        money_won = info[2]
        investment_value = info[3]

        ejackpot_week = datetime.datetime.fromtimestamp(result.close_time/1000).isocalendar().week
        game = result.brand_name.split("-")[1]
        weekday = result.brand_name.split("-")[0]
        msg = f"{game} viikko {ejackpot_week}/{weekday}, " \
              f"{primary_hits}+{secondary_hits} oikein, " \
              f"voittoa {int(money_won)/100:.2f}€, " \
              f"sijoituksen tuotto ||{investment_value/100:.2f}€||"
        ejackpot_messages.append(msg)

    return "\n".join(ejackpot_messages)


message = generate_discord_msg([18, 32, 39, 42, 44], [4, 9])
print(message)
