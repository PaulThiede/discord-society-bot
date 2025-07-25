import datetime

from math import floor

from src.db.models import Player, MarketItem, PlayerItem, CompanyItem, Government, GovernmentGDP, BuyOrder, SellOrder
from src.db.db_calls import get_item

def get_default_player(id, server_id):
    return Player(
            id=id,
            server_id=server_id,
            money=100.0,
            debt=0.0,
            hunger=100,
            thirst=100,
            health=100,
            job=None,
            created_at=datetime.datetime.utcnow(),
            company_entrepreneur_id=None,
            taxes_owed=0,
            work_cooldown_until=None,
            job_switch_cooldown_until=None,
            company_creation_cooldown_until=None,
            gift_cooldown_until=None
        )

async def get_default_player_item(user_id, server_id, item_tag, amount=1):
    item = await get_item(item_tag)
    if not item:
        raise Exception(f"{item_tag} not found")
    return PlayerItem(
            user_id=user_id,
            server_id=server_id,
            item_tag=item_tag,
            amount=amount,
            durability=item.durability
        )

def get_default_company_item(user_id, server_id, item_tag, amount=1):
    return CompanyItem(
            company_entrepreneur_id=user_id,
            server_id=server_id,
            item_tag=item_tag,
            amount=amount
        )

def get_default_market_item(item, server_id):
    return MarketItem(
        item_tag=item.item_tag,
        server_id=server_id,
        min_price=round(item.base_price * 0.75, 2),
        max_price=round(item.base_price * 1.25, 2),
        stockpile=floor(5000 / item.base_price)
    )

def get_default_government(server_id):
    return Government(
        id=server_id,
        created_at=datetime.datetime.utcnow,
        taxrate=0.1,
        interest_rate=0.3,
        treasury=0,
        governing_role=None,
        admin_role=None,
        gambling_pool=0
    )

def get_default_gdp_entry(server_id, date):
    return GovernmentGDP(
        server_id=server_id,
        date=date,
        gdp_value=0.0
    )

def get_default_buy_order(user_id, item_tag, server_id, amount, unit_price, is_company):
    return BuyOrder(
        user_id=user_id,
        item_tag=item_tag,
        server_id=server_id,
        amount=amount,
        unit_price=unit_price,
        is_company=is_company
    )

def get_default_sell_order(user_id, item_tag, server_id, amount, unit_price, is_company):
    return SellOrder(
        user_id=user_id,
        item_tag=item_tag,
        server_id=server_id,
        amount=amount,
        unit_price=unit_price,
        is_company=is_company
    )