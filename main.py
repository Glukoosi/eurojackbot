import requests
import datetime
import os
import sys
import discord
import boto3


intents = discord.Intents.default()
intents.message_content = True

ssm = boto3.client("ssm", region_name="eu-north-1")
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    channel = discord.utils.get(
        client.get_all_channels(), name=discord_channel_name)

    msg = generate_discord_msg()

    await client.get_channel(channel.id).send(msg)
    await client.close()

def get_investment_value():
    result = ssm.get_parameter(Name="eurojackbot-investment-value")
    return int(result["Parameter"]["Value"])

def set_investment_value(value):
    ssm.put_parameter(Name=parameter_store_variable_name,
                      Overwrite=True, Value=value)


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

    return primary_result, secondary_result, prize_tiers


def generate_discord_msg():
    primary_result, secondary_result, prize_tiers = get_eurojackpot_results()
    if not primary_result:
        return "Tuloksia ei saatu Veikkaukselta :("

    primary_hits = 0
    for number in primary_numbers:
        if number in primary_result:
            primary_hits += 1

    secondary_hits = 0
    for number in secondary_numbers:
        if number in secondary_result:
            secondary_hits += 1

    result = f"{primary_hits}+{secondary_hits} oikein"

    money_won = 0

    for tier in prize_tiers:
        if tier["name"] == result:
            money_won = int(tier["shareAmount"])

    investment_value_old = get_investment_value()
    investment_value = str(investment_value_old - 200 + money_won)

    set_investment_value(investment_value)

    return f"{result}, voittoa {int(money_won)/100:.2f}€, sijoituksen tuotto ||{int(investment_value)/100:.2f}€||"


discord_key = os.environ.get("DISCORD_KEY")
discord_channel_name = os.environ.get("DISCORD_CHANNEL_NAME")
parameter_store_variable_name = os.environ.get("PARAMETER_STORE_VARIABLE_NAME")

if not discord_key or not discord_channel_name or not parameter_store_variable_name:
    print("Env variables missing, exiting")
    sys.exit()

try:
    primary_numbers = os.environ.get("EUROJACKPOT_PRIMARY_NUMBERS").split(",")
    secondary_numbers = os.environ.get("EUROJACKPOT_SECONDARY_NUMBERS").split(",")
except:
    print("No eurojacpot numbers, exiting")
    sys.exit()


def lambda_handler(event=None, context=None):
    client.run(discord_key)


if __name__ == "__main__":
    lambda_handler()
