from lib.eurojackpot import EuroJackpot
from typing import List, Tuple
import requests
import datetime
import os
import sys
import boto3
import json
from pathlib import Path


ssm = boto3.client("ssm", region_name="eu-west-1")


def get_investment_value(parameter_store_variable_name: str) -> int:
    result = ssm.get_parameter(Name=parameter_store_variable_name)
    return int(result["Parameter"]["Value"])


def set_investment_value(value: int, parameter_store_variable_name: str) -> None:
    ssm.put_parameter(Name=parameter_store_variable_name,
                      Overwrite=True, Value=str(value))


def get_eurojackpot_next_jackpot() -> int:
    r = requests.get(
        "https://msa.veikkaus.fi/jackpot/v1/latest-jackpot-results.json").json()
    if r["draws"].get("EJACKPOT"):
        return r["draws"]["EJACKPOT"][0]["jackpots"][0]["amount"]
    else:
        return 0


def get_eurojackpot_results() -> List[EuroJackpot]:
    """
    Request current weeks Eurojackpot data from the Veikkaus API.

    :return: List of Eurojackpot game objects, or an empty list if no games available yet for current week.
    """
    now = datetime.datetime.now()

    week = now.isocalendar().week
    year = now.isocalendar().year

    r = requests.get(
        f"https://www.veikkaus.fi/api/draw-results/v1/games/EJACKPOT/draws/by-week/{year}-W{week}").json()

    return [EuroJackpot(e) for e in r]


def fetch_winnings(
        eurojackpot: EuroJackpot,
        primary_numbers: List[str],
        secondary_numbers: List[str],
        parameter_store_variable_name: str
) -> Tuple[int, int, int, int]:
    """
    Fetch winnings for one Eurojackpot game.

    :param eurojackpot: The Eurojackpot game object.
    :param primary_numbers: Primary numbers for the Eurojackpot lottery.
    :param secondary_numbers: Secondary numbers for the Eurojackpot lottery.
    :param parameter_store_variable_name: Variable names for retrieving data from the AWS storage.
    :return: Tuple containing hits for primary numbers and secondary numbers, money won and updated investment value.
    """
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

    investment_value_old = get_investment_value(parameter_store_variable_name)
    investment_value_new = investment_value_old - 200 + money_won
    set_investment_value(investment_value_new, parameter_store_variable_name)

    return primary_hits, secondary_hits, money_won, investment_value_new


def generate_discord_msg(env_variables) -> str:
    """
    Generate the final message to send to Discord. Contains only one or all Eurojackpot game results depending on
    settings in env.json.

    :param env_variables: Environment variables read to dictionary from env.json.
    :return: A message that can be sent to Discord straight away.
    """
    primary_numbers = env_variables["primary_numbers"]
    secondary_numbers = env_variables["secondary_numbers"]
    parameter_store_variable_name = env_variables["parameter_store_variable_name"]
    latest_game_only = env_variables["latest_game_only"]
    group_id = env_variables["discord_group_id"]

    messages = []
    eurojackpots = get_eurojackpot_results()
    if not eurojackpots:
        return "Tuloksia ei saatu Veikkaukselta :("
    elif latest_game_only:
        eurojackpots = eurojackpots[-1:]

    next_jackpot = get_eurojackpot_next_jackpot()
    if next_jackpot == 0:
        next_jackpot = "ei tiedossa"
    else:
        next_jackpot = f"`{next_jackpot / 100:,.2f}`€"

    for eurojackpot in eurojackpots:
        winnings = fetch_winnings(
            eurojackpot, primary_numbers, secondary_numbers, parameter_store_variable_name)
        primary_hits = winnings[0]
        secondary_hits = winnings[1]
        money_won = winnings[2]
        investment_value = winnings[3]

        ejackpot_week = datetime.datetime.fromtimestamp(
            eurojackpot.close_time/1000).isocalendar().week
        weekday = eurojackpot.brand_name.split("-")[0]

        biggest_prize_tier = eurojackpot.biggest_prize_tier

        msg = f"W{ejackpot_week}/{weekday} {primary_hits}+{secondary_hits} oikein, " \
              f"voittoa `{int(money_won) / 100:,.2f}`€, sijoituksen tuotto ||{investment_value / 100:,.2f}||€\n" \
              f"Isoin voitto tuloksella {biggest_prize_tier.name} `{biggest_prize_tier.share_amount / 100:,.2f}`€"

        messages.append(msg)

    joined = "\n--\n".join(messages)
    return f"<@&{group_id}>\n{joined}\n\nSeuraava päävoitto {next_jackpot}"


def get_env_variables():
    discord_key = os.environ.get("DISCORD_KEY")
    discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    discord_group_id = os.environ.get("DISCORD_GROUP_ID")

    parameter_store_variable_name = os.environ.get(
        "PARAMETER_STORE_VARIABLE_NAME")

    if not discord_channel_id or not parameter_store_variable_name or not discord_group_id or not discord_key:
        print("Env variables missing, exiting")
        sys.exit()

    try:
        primary_numbers = os.environ.get(
            "EUROJACKPOT_PRIMARY_NUMBERS").split(",")
        secondary_numbers = os.environ.get(
            "EUROJACKPOT_SECONDARY_NUMBERS").split(",")
    except:
        print("No eurojackpot numbers, exiting")
        sys.exit()

    latest_game_only = os.environ.get(
        "FETCH_LATEST_GAME_ONLY").lower() in ["true", "1"]

    return {
        "discord_key": discord_key,
        "discord_channel_id": discord_channel_id,
        "discord_group_id": discord_group_id,
        "parameter_store_variable_name": parameter_store_variable_name,
        "primary_numbers": primary_numbers,
        "secondary_numbers": secondary_numbers,
        "latest_game_only": latest_game_only
    }


def lambda_handler(event=None, context=None):
    env_variables = get_env_variables()
    discord_key = env_variables["discord_key"]
    channel_id = env_variables["discord_channel_id"]

    message = generate_discord_msg(env_variables)

    r = requests.post(f"https://discord.com/api/channels/{channel_id}/messages", headers={
                      "Authorization": f"Bot {discord_key}"}, json={"content": message})
    if r.status_code != 200:
        print("Failed to post to discord api, code " + str(r.status_code))


if __name__ == "__main__":
    if Path("env.json").is_file():
        env_vars_tmp = json.load(open("env.json"))
        for variable_name, variable_value in env_vars_tmp.get("Variables", {}).items():
            os.environ[variable_name] = str(variable_value)
    lambda_handler()
