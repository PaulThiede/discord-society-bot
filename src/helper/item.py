from sqlalchemy import select, and_

from src.db.models import PlayerItem
from src.db.db_calls import get_player_item, get_item, get_company_item
from src.helper.defaults import get_default_player_item, get_default_company_item

async def has_player_item(session, user_id, server_id, item_tag, min_amount=1):
    return await get_player_item(user_id, server_id, item_tag, min_amount) is not None


async def use_item(session, user_id, server_id, item_tag):
    player_item = await get_player_item(user_id, server_id, item_tag)

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
            item = await get_item(item_tag)
            if item and item.durability is not None:
                # Falls es ein passendes Feld für Haltbarkeit gibt
                player_item.durability = item.durability
            else:
                # Falls keine info vorhanden, setze auf None oder 0
                player_item.durability = None
    await session.commit()
    return durability


async def add_player_item(session, user_id, server_id, item_tag, amount):
    print("    Added player item")

    player_item = await get_player_item(user_id, server_id, item_tag)
    if player_item:
        player_item.amount += amount
    else:
        player_item = await get_default_player_item(session, user_id, server_id, item_tag, amount)
        session.add(player_item)

    await session.commit()


async def add_company_item(session, user_id, server_id, item_tag, amount):
    print("    Added company item")

    company_item = await get_company_item(session, user_id, server_id, item_tag)
    if company_item:
        company_item.amount += amount
    else:
        company_item = get_default_company_item(user_id, server_id, item_tag, amount)
        session.add(company_item)

    await session.commit()

async def remove_player_item(session, user_id: int, server_id: int, item_tag: str, amount: int = 1):
    player_item = await get_player_item(user_id, server_id, item_tag)

    if not player_item:
        return False  # Item nicht vorhanden

    if player_item.amount < amount:
        raise Exception(f"The amount of {item_tag} ({player_item.amout}) is not enough to remove {amount}x")

    player_item.amount -= amount

    if player_item.amount <= 0:
        await session.delete(player_item)

    await session.commit()