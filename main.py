from eurojackpot import EuroJackpot
from typing import List, Tuple, Union
import requests
import datetime
import os
import sys
import discord
import boto3
import json
import asyncio


intents = discord.Intents.default()
intents.message_content = True

ssm = boto3.client("ssm", region_name="eu-west-1")
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    # Discord allows multiple channels with same name -> use ID here
    channel = client.get_channel(int(discord_channel_id))

    msg = generate_discord_msg(primary_numbers, secondary_numbers)
    msg_with_mention = f"<@&{discord_group_id}>\n\n{msg}"

    await client.get_channel(channel.id).send(msg_with_mention)
    await client.close()


def get_investment_value() -> int:
    result = ssm.get_parameter(Name=parameter_store_variable_name)
    return int(result["Parameter"]["Value"])


def set_investment_value(value: int):
    ssm.put_parameter(Name=parameter_store_variable_name,
                      Overwrite=True, Value=str(value))


def get_eurojackpot_results() -> List[EuroJackpot]:
    now = datetime.datetime.now()

    week = now.isocalendar().week
    year = now.isocalendar().year

    r = requests.get(
        f"https://www.veikkaus.fi/api/draw-results/v1/games/EJACKPOT/draws/by-week/{year}-W{week}").json()

    return [EuroJackpot(e) for e in r]


def fetch_winnings(
        eurojackpot: EuroJackpot,
        guesses_primary: List[str],
        guesses_secondary: List[str]) -> Tuple[int, int, int, int]:
    primary_results = eurojackpot.results[0].primary
    secondary_results = eurojackpot.results[0].secondary

    primary_hits = 0
    for number in primary_results:
        if number in guesses_primary:
            primary_hits += 1

    secondary_hits = 0
    for number in secondary_results:
        if number in guesses_secondary:
            secondary_hits += 1

    total_hits = f"{primary_hits}+{secondary_hits} oikein"

    money_won = 0
    for prize_tier in eurojackpot.prize_tiers:
        if prize_tier.name == total_hits:
            money_won = prize_tier.share_amount
            break

    investment_value_old = get_investment_value()
    investment_value_new = investment_value_old - 200 + money_won

    set_investment_value(investment_value_new)

    return primary_hits, secondary_hits, money_won, investment_value_new


def generate_discord_msg(guesses_primary: List[Union[int, str]], guesses_secondary: List[Union[int, str]]) -> str:
    guesses_primary = [str(i) for i in guesses_primary]
    guesses_secondary = [str(i) for i in guesses_secondary]

    ejackpot_messages = []
    results = get_eurojackpot_results()
    if not results:
        return "Tuloksia ei saatu Veikkaukselta :("

    for result in results:
        info = fetch_winnings(result, guesses_primary, guesses_secondary)

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


def lambda_handler(event=None, context=None):
    asyncio.run(client.start(discord_key))


def fetch_env_variables() -> None:
    with open("env.json", "r") as env_file:
        env_variables = json.load(env_file)
        for variable_name, variable_value in env_variables.get("Variables").items():
            os.environ[variable_name] = variable_value


if __name__ == "__main__":
    fetch_env_variables()
    discord_key = os.environ.get("DISCORD_KEY")
    discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    discord_group_id = os.environ.get("DISCORD_GROUP_ID")
    parameter_store_variable_name = os.environ.get("PARAMETER_STORE_VARIABLE_NAME")

    if not discord_key or not discord_channel_id or not parameter_store_variable_name or not discord_group_id:
        print("Env variables missing, exiting")
        sys.exit()

    primary_numbers = os.environ.get("EUROJACKPOT_PRIMARY_NUMBERS").split(",")
    secondary_numbers = os.environ.get("EUROJACKPOT_SECONDARY_NUMBERS").split(",")

    if not primary_numbers or not secondary_numbers:
        print("No Eurojackpot numbers. Exiting.")
        sys.exit()

    lambda_handler()
