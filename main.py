import requests
import datetime
import os
import sys
import discord
import boto3
import json
from pathlib import Path
import asyncio


intents = discord.Intents.default()
intents.message_content = True

ssm = boto3.client("ssm", region_name="eu-west-1")
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    env_variables = get_env_variables()
    channel = discord.utils.get(
        client.get_all_channels(), name=env_variables["discord_channel_name"])

    msg = generate_discord_msg(env_variables)

    await client.get_channel(channel.id).send(msg)
    await client.close()


def get_investment_value(parameter_store_variable_name):
    result = ssm.get_parameter(Name=parameter_store_variable_name)
    return int(result["Parameter"]["Value"])


def set_investment_value(value, parameter_store_variable_name):
    ssm.put_parameter(Name=parameter_store_variable_name,
                      Overwrite=True, Value=value)


def get_eurojackpot_next_jackpot():
    r = requests.get(
        "https://msa.veikkaus.fi/jackpot/v1/latest-jackpot-results.json").json()
    return r["draws"]["EJACKPOT"][0]["jackpots"][0]["amount"]


def get_eurojackpot_results():
    now = datetime.datetime.now()

    week = now.isocalendar().week
    year = now.isocalendar().year

    r = requests.get(
        f"https://www.veikkaus.fi/api/draw-results/v1/games/EJACKPOT/draws/by-week/{year}-W{week}").json()

    if len(r) == 0:
        return None, None, None

    results = r[-1]["results"]

    primary_result = results[0]["primary"]
    secondary_result = results[0]["secondary"]

    prize_tiers = r[-1]["prizeTiers"]

    round_date_string = f"W{week}/{r[-1]['brandName'].split('-')[0]}"

    return primary_result, secondary_result, prize_tiers, round_date_string


def generate_discord_msg(env_variables):
    primary_result, secondary_result, prize_tiers, round_date_string = get_eurojackpot_results()
    next_jackpot = get_eurojackpot_next_jackpot()
    if not primary_result:
        return "Tuloksia ei saatu Veikkaukselta :("

    primary_hits = 0
    for number in env_variables["primary_numbers"]:
        if number in primary_result:
            primary_hits += 1

    secondary_hits = 0
    for number in env_variables["secondary_numbers"]:
        if number in secondary_result:
            secondary_hits += 1

    result = f"{primary_hits}+{secondary_hits} oikein"

    money_won = 0

    biggest_winners_share_name = ""
    biggest_winners_share_amount = 0
    for tier in prize_tiers:
        if tier["name"] == result:
            money_won = int(tier["shareAmount"])
        if biggest_winners_share_amount == 0 and tier["shareAmount"] != 0:
            biggest_winners_share_name = tier["name"]
            biggest_winners_share_amount = tier["shareAmount"]

    investment_value_old = get_investment_value(
        env_variables["parameter_store_variable_name"])
    investment_value = str(investment_value_old - 200 + money_won)

    set_investment_value(
        investment_value, env_variables["parameter_store_variable_name"])

    return f"""
    <@&{env_variables['discord_group_id']}> {round_date_string} {result}, voittoa `{int(money_won)/100:,.2f}`€, sijoituksen tuotto ||{int(investment_value)/100:,.2f}€||

    Isoin voitto tuloksella {biggest_winners_share_name} `{biggest_winners_share_amount/100:,.2f}`€
    Seuraava päävoitto `{next_jackpot/100:,.2f}`€
    """


def get_env_variables():
    discord_channel_name = os.environ.get("DISCORD_CHANNEL_NAME")
    discord_group_id = os.environ.get("DISCORD_GROUP_ID")

    parameter_store_variable_name = os.environ.get(
        "PARAMETER_STORE_VARIABLE_NAME")

    if not discord_channel_name or not parameter_store_variable_name or not discord_group_id:
        print("Env variables missing, exiting")
        sys.exit()

    try:
        primary_numbers = os.environ.get(
            "EUROJACKPOT_PRIMARY_NUMBERS").split(",")
        secondary_numbers = os.environ.get(
            "EUROJACKPOT_SECONDARY_NUMBERS").split(",")
    except:
        print("No eurojacpot numbers, exiting")
        sys.exit()

    return {
        "discord_channel_name": discord_channel_name,
        "discord_group_id": discord_group_id,
        "parameter_store_variable_name": parameter_store_variable_name,
        "primary_numbers": primary_numbers,
        "secondary_numbers": secondary_numbers,
    }


def lambda_handler(event=None, context=None):
    discord_key = os.environ.get("DISCORD_KEY")
    if not discord_key:
        print("No discord key, exiting")
        sys.exit()

    asyncio.run(client.start(discord_key))


if __name__ == "__main__":
    if Path("env.json").is_file():
        env_variables = json.load(open("env.json"))
        for variable_name, variable_value in env_variables.get("Variables").items():
            os.environ[variable_name] = variable_value
    lambda_handler()
