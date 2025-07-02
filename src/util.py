from datetime import datetime, timedelta, date
from config import WORK_COOLDOWN
from sqlalchemy import select, update, delete
import discord
from db.models import Player, PlayerItem, Item, MarketItem, CompanyItem, Company, Government, GovernmentGDP
from db.db import get_session
from sqlalchemy import and_
from sqlalchemy.future import select
from random import randint
from math import floor

def get_hunger_depletion():
    return randint(2,8)

def get_thirst_depletion():
    return randint(5,10)

async def initialize_market_for_server(server_id: int):
    async for session in get_session():
        result = await session.execute(select(Item))
        items = result.scalars().all()

        for item in items:
            market_item = MarketItem(
                item_tag=item.item_tag,
                server_id=server_id,
                min_price=round(item.base_price * 0.75, 2),
                max_price=round(item.base_price * 1.25, 2),
                stockpile=floor(5000 / item.base_price)
            )
            session.add(market_item)

        await session.commit()

async def has_item(user_id, server_id, item_tag, min_amount=1):
    async for session in get_session():
        result = await session.execute(
            select(PlayerItem).where(
                and_(
                    PlayerItem.user_id == user_id,
                    PlayerItem.server_id == server_id,
                    PlayerItem.item_tag == item_tag,
                    PlayerItem.amount >= min_amount
                )
            )
        )
        return result.scalar_one_or_none() is not None
    return False

async def add_item(user_id, server_id, item_tag, amount, is_company: bool = False):
    async for session in get_session():
        if is_company:
            print("    Added company item")
            # Company-Item aktualisieren
            result = await session.execute(
                select(CompanyItem).where(
                    and_(
                        CompanyItem.company_entrepreneur_id == user_id,
                        CompanyItem.server_id == server_id,
                        CompanyItem.item_tag == item_tag
                    )
                )
            )
            company_item = result.scalar_one_or_none()

            if company_item:
                company_item.amount += amount
            else:
                company_item = CompanyItem(
                    company_entrepreneur_id=user_id,
                    server_id=server_id,
                    item_tag=item_tag,
                    amount=amount
                )
                session.add(company_item)
        else:
            print("    Added player item")
            # Player-Item aktualisieren
            result = await session.execute(
                select(PlayerItem).where(
                    and_(
                        PlayerItem.user_id == user_id,
                        PlayerItem.server_id == server_id,
                        PlayerItem.item_tag == item_tag
                    )
                )
            )
            player_item = result.scalar_one_or_none()

            if player_item:
                player_item.amount += amount
            else:
                item_result = await session.execute(
                    select(Item).where(Item.item_tag == item_tag)
                )
                item = item_result.scalar_one_or_none()

                player_item = PlayerItem(
                    user_id=user_id,
                    server_id=server_id,
                    item_tag=item_tag,
                    amount=amount,
                    durability=item.durability
                )
                session.add(player_item)
        await session.commit()

async def use_item(user_id, server_id, item_tag):
    durability = None
    async for session in get_session():
        result = await session.execute(
            select(PlayerItem).where(
                PlayerItem.user_id == user_id,
                PlayerItem.server_id == server_id,
                PlayerItem.item_tag == item_tag,
                PlayerItem.amount > 0
            )
        )
        player_item = result.scalar_one_or_none()
        if not player_item:
            return None

        if player_item.durability is None:
            # Unzerstörbares Item
            return None

        durability = player_item.durability
        player_item.durability -= 1


        if player_item.durability <= 0:
            # Durability 0 oder weniger: einen Item-Stack reduzieren
            player_item.amount -= 1
            if player_item.amount <= 0:
                await session.delete(player_item)
            else:
                # Haltbarkeit vom Item aus der Items-Tabelle neu setzen
                item_result = await session.execute(
                    select(Item).where(Item.item_tag == item_tag)
                )
                item = item_result.scalar_one_or_none()
                if item and item.durability is not None:
                    # Falls es ein passendes Feld für Haltbarkeit gibt
                    player_item.durability = item.durability
                else:
                    # Falls keine info vorhanden, setze auf None oder 0
                    player_item.durability = None
        await session.commit()
    return durability


async def remove_item(user_id: int, server_id: int, item_tag: str, amount: int = 1):
    async for session in get_session():
        result = await session.execute(
            select(PlayerItem).where(
                and_(
                    PlayerItem.user_id == user_id,
                    PlayerItem.server_id == server_id,
                    PlayerItem.item_tag == item_tag
                )
            )
        )
        player_item = result.scalar_one_or_none()

        if not player_item:
            return False  # Item nicht vorhanden

        if player_item.amount < amount:
            return False  # Nicht genug Items zum Entfernen

        player_item.amount -= amount

        if player_item.amount <= 0:
            await session.delete(player_item)
        else:
            session.add(player_item)


        await session.commit()
    return True


async def add_owed_taxes(user_id: int, server_id: int, amount: float, is_company: bool = False):
    async for session in get_session():
        if amount <= 0:
            return  # keine negativen oder null-Beträge

        await increase_gdp(session, server_id, amount)

        # Taxrate holen
        result = await session.execute(
            select(Government).where(Government.id == server_id)
        )
        government = result.scalar_one_or_none()
        if not government:
            return  # Kein Government vorhanden

        taxrate = government.taxrate or 0.0
        tax_amount = round(amount * taxrate, 2)

        if tax_amount <= 0:
            return  # Steuerbetrag zu gering

        if is_company:
            result = await session.execute(
                select(Company).where(
                    Company.entrepreneur_id == user_id,
                    Company.server_id == server_id
                )
            )
            company = result.scalar_one_or_none()
            if not company:
                return  # Company existiert nicht

            company.taxes_owed = (company.taxes_owed or 0) + tax_amount
        else:
            result = await session.execute(
                select(Player).where(
                    Player.id == user_id,
                    Player.server_id == server_id
                )
            )
            player = result.scalar_one_or_none()
            if not player:
                return  # Spieler existiert nicht

            player.taxes_owed = (player.taxes_owed or 0) + tax_amount

        await session.commit()

async def increase_gdp(session, server_id: int, amount: float):
    today = date.today()
    gdp_entry = await session.scalar(
        select(GovernmentGDP).where(GovernmentGDP.server_id == server_id, GovernmentGDP.date == today)
    )
    if not gdp_entry:
        gdp_entry = GovernmentGDP(server_id=server_id, date=today, gdp_value=0.0)
        session.add(gdp_entry)

    gdp_entry.gdp_value += amount