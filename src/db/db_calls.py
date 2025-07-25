from datetime import datetime, date
from dateutil.parser import parse
from dataclasses import asdict
from typing import Any

from src.db.db import supabase
from src.db.models import Player, PlayerItem, Item, CompanyItem, BuyOrder, MarketItem, SellOrder, Company, Government, \
    GovernmentGDP, CompanyJoinRequest



def parse_datetime(dt_str):
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else None



async def get_all_items():
    try:
        response = (
            supabase.table("Items")
            .select("*")
            .execute()
        )

        items = []
        for entry in response.data:
            item = Item(
                item_tag=entry["item_tag"].strip(),
                producible=entry["producible"],
                ingredients=entry.get("ingredients"),  # kann None sein
                worksteps=entry.get("worksteps"),
                base_price=entry["base_price"],
                durability=entry.get("durability"),
            )
            items.append(item)
        return items
    except Exception as e:
        print(e)


async def get_producible_items():
    try:
        response = (
            supabase.table("Items")
            .select("item_tag")
            .eq("producible", True)
            .execute()
        )

        # We only return the item tags
        return [entry["item_tag"].strip() for entry in response.data]
    except Exception as e:
        print(e)



async def get_item(item_tag: str):
    try:
        response = (
            supabase.table("Items")
            .select("*")
            .execute()
        )

        for entry in response.data:
            if entry.get("item_tag").strip().lower() == item_tag.strip().lower():
                return Item(
                    item_tag=entry.get("item_tag").strip(),
                    producible=entry.get("producible"),
                    ingredients=entry.get("ingredients"),
                    worksteps=entry.get("worksteps"),
                    base_price=entry.get("base_price"),
                    durability=entry.get("durability")
                )

        return None
    except Exception as e:
        print(e)



async def get_player_item(user_id, server_id, item_tag, min_amount=1):
    try:
        response = (
            supabase.table("Player_Items")
            .select("*")
            .eq("user_id", user_id)
            .eq("server_id", server_id)
            .gte("amount", min_amount)
            .execute()
        )

        for entry in response.data:
            if entry.get("item_tag").strip().lower() == item_tag.strip().lower():
                return PlayerItem(
                    user_id=entry.get("user_id"),
                    item_tag=entry.get("item_tag"),
                    server_id=entry.get("server_id"),
                    amount=entry.get("amount"),
                    durability=entry.get("durability")
                )

        return None
    except Exception as e:
        print(e)


async def get_company_item(user_id, server_id, item_tag):
    try:
        response = (
            supabase.table("Company_Items")
            .select("*")
            .eq("company_entrepreneur_id", user_id)
            .eq("server_id", server_id)
            .execute()
        )

        for entry in response.data:
            if entry.get("item_tag").strip().lower() == item_tag.strip().lower():
                return CompanyItem(
                    company_entrepreneur_id=entry.get("company_entrepreneur_id"),
                    item_tag=entry.get("item_tag"),
                    server_id=entry.get("server_id"),
                    amount=entry.get("amount"),
                )

        return None
    except Exception as e:
        print(e)


async def get_all_players(server_id):
    try:
        response = (
            supabase.table("Players")
            .select("*")
            .eq("server_id", server_id)
            .execute()
        )

        players = []
        for entry in response.data:
            player = Player(
                id=entry["id"],
                server_id=entry["server_id"],
                created_at=parse_datetime(entry["created_at"]),
                money=entry["money"],
                debt=entry["debt"],
                hunger=entry["hunger"],
                thirst=entry["thirst"],
                job=entry["job"],
                health=entry["health"],
                company_entrepreneur_id=entry["company_entrepreneur_id"],
                taxes_owed=entry["taxes_owed"],
                work_cooldown_until=parse_datetime(entry["work_cooldown_until"]),
                job_switch_cooldown_until=parse_datetime(entry["job_switch_cooldown_until"]),
                company_creation_cooldown_until=parse_datetime(entry["company_creation_cooldown_until"]),
                gift_cooldown_until=parse_datetime(entry["gift_cooldown_until"])
            )
            players.append(player)

        return players
    except Exception as e:
        print(e)


async def get_player(user_id, server_id):
    try:
        response = (
            supabase.table("Players")
            .select("*")
            .eq("id", user_id)
            .eq("server_id", server_id)
            .execute()
        )

        for entry in response.data:
            return Player(
                id=entry["id"],
                server_id=entry["server_id"],
                created_at=parse_datetime(entry["created_at"]),
                money=entry["money"],
                debt=entry["debt"],
                hunger=entry["hunger"],
                thirst=entry["thirst"],
                job=entry["job"],
                health=entry["health"],
                company_entrepreneur_id=entry["company_entrepreneur_id"],
                taxes_owed=entry["taxes_owed"],
                work_cooldown_until=parse_datetime(entry["work_cooldown_until"]),
                job_switch_cooldown_until=parse_datetime(entry["job_switch_cooldown_until"]),
                company_creation_cooldown_until=parse_datetime(entry["company_creation_cooldown_until"]),
                gift_cooldown_until=parse_datetime(entry["gift_cooldown_until"])
            )

        return None
    except Exception as e:
        print(e)

async def get_tax_owing_players(server_id):
    try:
        response = (
            supabase.table("Players")
            .select("*")
            .eq("server_id", server_id)
            .gt("taxes_owed", 0)
            .order("taxes_owed", desc=True)
            .execute()
        )

        players = []
        for entry in response.data:
            players.append(Player(
                id=entry.get("id"),
                server_id=entry.get("server_id"),
                created_at=datetime.fromisoformat(entry.get("created_at")),
                money=entry.get("money"),
                debt=entry.get("debt"),
                hunger=entry.get("hunger"),
                thirst=entry.get("thirst"),
                job=entry.get("job"),
                health=entry.get("health"),
                company_entrepreneur_id=entry.get("company_entrepreneur_id"),
                taxes_owed=entry.get("taxes_owed"),
                work_cooldown_until=datetime.fromisoformat(str(entry.get("work_cooldown_until"))) if entry.get("work_cooldown_until") else None,
                job_switch_cooldown_until=datetime.fromisoformat(str(entry.get("job_switch_cooldown_until"))) if entry.get("job_switch_cooldown_until") else None,
                company_creation_cooldown_until=datetime.fromisoformat(str(entry.get("company_creation_cooldown_until"))) if entry.get("company_creation_cooldown_until") else None,
                gift_cooldown_until=datetime.fromisoformat(str(entry.get("gift_cooldown_until"))) if entry.get("gift_cooldown_until") else None,
            ))

        return players
    except Exception as e:
        print(e)

async def get_tax_owing_companies(server_id):
    try:
        response = (
            supabase.table("Companies")
            .select("*")
            .eq("server_id", server_id)
            .gt("taxes_owed", 0)
            .order("taxes_owed", desc=True)
            .execute()
        )

        companies = []
        for entry in response.data:
            companies.append(Company(
                entrepreneur_id=entry.get("entrepreneur_id"),
                server_id=entry.get("server_id"),
                created_at=datetime.fromisoformat(str(entry["created_at"])) if entry.get("created_at") else None,
                producible_items=entry.get("producible_items", ""),
                capital=entry.get("capital", 0),
                worksteps=entry.get("worksteps", 0),
                wage=entry.get("wage", 0),
                name=entry.get("name", ""),
                taxes_owed=entry.get("taxes_owed", 0),
            ))

        return companies
    except Exception as e:
        print(e)

async def get_employees(entrepreneur_id: int, server_id: int):
    try:
        response = (
            supabase.table("Players")
            .select("*")
            .eq("company_entrepreneur_id", entrepreneur_id)
            .eq("server_id", server_id)
            .execute()
        )

        players = []
        for entry in response.data:
            players.append(Player(
                id=entry.get("id"),
                server_id=entry.get("server_id"),
                created_at=datetime.fromisoformat(str(entry["created_at"])) if entry.get("created_at") else None,
                money=entry.get("money", 0),
                debt=entry.get("debt", 0),
                hunger=entry.get("hunger", 0),
                thirst=entry.get("thirst", 0),
                job=entry.get("job", ""),
                health=entry.get("health", 100),
                company_entrepreneur_id=entry.get("company_entrepreneur_id"),
                taxes_owed=entry.get("taxes_owed", 0),
                work_cooldown_until=datetime.fromisoformat(str(entry["work_cooldown_until"])) if entry.get("work_cooldown_until") else None,
                job_switch_cooldown_until=datetime.fromisoformat(str(entry["job_switch_cooldown_until"])) if entry.get("job_switch_cooldown_until") else None,
                company_creation_cooldown_until=datetime.fromisoformat(str(entry["company_creation_cooldown_until"])) if entry.get("company_creation_cooldown_until") else None,
                gift_cooldown_until=datetime.fromisoformat(str(entry["gift_cooldown_until"])) if entry.get("gift_cooldown_until") else None,
            ))

        return players
    except Exception as e:
        print(e)


async def fire_employees(target_user_id: int, server_id: int):
    try:
        response = (
            supabase.table("Players")
            .update({"company_entrepreneur_id": None, "job": ""})
            .eq("company_entrepreneur_id", target_user_id)
            .eq("server_id", server_id)
            .execute()
        )
        return response
    except Exception as e:
        print(e)


async def get_join_requests(entrepreneur_id: int, server_id: int):
    try:
        response = (
            supabase.table("Company_Join_Requests")
            .select("*")
            .eq("company_entrepreneur_id", entrepreneur_id)
            .eq("server_id", server_id)
            .execute()
        )

        requests = []
        for entry in response.data:
            requests.append(CompanyJoinRequest(
                user_id=entry.get("user_id"),
                server_id=entry.get("server_id"),
                company_entrepreneur_id=entry.get("company_entrepreneur_id")
            ))

        return requests
    except Exception as e:
        print(e)


async def get_user_join_request(entrepreneur_id: int, server_id: int, user_id: int):
    try:
        response = (
            supabase.table("Company_Join_Requests")
            .select("*")
            .eq("company_entrepreneur_id", entrepreneur_id)
            .eq("server_id", server_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            return None

        entry = response.data[0]
        return CompanyJoinRequest(
            user_id=entry.get("user_id"),
            server_id=entry.get("server_id"),
            company_entrepreneur_id=entry.get("company_entrepreneur_id"),
        )
    except Exception as e:
        print(e)


async def get_all_companies(server_id):
    try:
        response = (
            supabase.table("Companies")
            .select("*")
            .eq("server_id", server_id)
            .execute()
        )

        companies = []
        for entry in response.data:
            companies.append(Company(
                entrepreneur_id=entry.get("entrepreneur_id"),
                server_id=entry.get("server_id"),
                created_at=datetime.fromisoformat(str(entry["created_at"])) if entry.get("created_at") else None,
                producible_items=entry.get("producible_items", ""),
                capital=entry.get("capital", 0),
                worksteps=entry.get("worksteps", 0),
                wage=entry.get("wage", 0),
                name=entry.get("name", ""),
                taxes_owed=entry.get("taxes_owed", 0),
            ))

        return companies
    except Exception as e:
        print(e)


async def get_company(user_id: int, server_id: int):
    try:
        response = (
            supabase.table("Companies")
            .select("*")
            .eq("entrepreneur_id", user_id)
            .eq("server_id", server_id)
            .execute()
        )

        if not response.data:
            return None

        entry = response.data[0]
        return Company(
            entrepreneur_id=entry.get("entrepreneur_id"),
            server_id=entry.get("server_id"),
            created_at=entry.get("created_at"),
            producible_items=entry.get("producible_items"),
            capital=entry.get("capital"),
            worksteps=entry.get("worksteps"),
            wage=entry.get("wage"),
            name=entry.get("name"),
            taxes_owed=entry.get("taxes_owed"),
        )
    except Exception as e:
        print(e)


async def get_player_inventory(user_id: int, server_id: int):
    try:
        response = (
            supabase.table("Player_Items")
            .select("*")
            .eq("user_id", user_id)
            .eq("server_id", server_id)
            .execute()
        )

        items = []
        for entry in response.data:
            items.append(PlayerItem(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                durability=entry.get("durability")
            ))
        return items
    except Exception as e:
        print(e)



async def get_company_inventory(user_id: int, server_id: int):
    try:
        response = (
            supabase.table("Company_Items")
            .select("*")
            .eq("company_entrepreneur_id", user_id)
            .eq("server_id", server_id)
            .execute()
        )

        items = []
        for entry in response.data:
            items.append(CompanyItem(
                company_entrepreneur_id=entry.get("company_entrepreneur_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount")
            ))
        return items
    except Exception as e:
        print(e)






async def get_own_sell_orders(user_id: int, server_id: int, item_tag: str, unit_price: float, is_company):
    
    try:
        if is_company == "both":
            response = (
                supabase.table("Sell_Orders")
                .select("*")
                .eq("user_id", user_id)
                .eq("item_tag", item_tag)
                .eq("server_id", server_id)
                .eq("unit_price", unit_price)
                .execute()
            )
        else:
           response = (
                supabase.table("Sell_Orders")
                .select("*")
                .eq("user_id", user_id)
                .eq("item_tag", item_tag)
                .eq("server_id", server_id)
                .eq("unit_price", unit_price)
                .eq("is_company", is_company)
                .execute()
            ) 
        orders = []
        for entry in response.data:
            orders.append(SellOrder(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                unit_price=entry.get("unit_price"),
                is_company=entry.get("is_company"),
            ))
        return orders
    except Exception as e:
        print(e)


async def get_sell_orders(server_id: int, item_tag: str, unit_price: float, now: datetime):
    try:
        response = (
            supabase.table("Sell_Orders")
            .select("*")
            .eq("server_id", server_id)
            .eq("item_tag", item_tag)
            .lte("unit_price", unit_price)
            .execute()
        )


        # Mappe zu SellOrder Objekten
        return [
            SellOrder(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                unit_price=entry.get("unit_price"),
                is_company=entry.get("is_company"),
            )
            for entry in response.data
        ]
    except Exception as e:
        print(e)

async def get_item_sell_orders(server_id: int, item_tag: str, now: datetime):
    try:
        response = (
            supabase.table("Sell_Orders")
            .select("*")
            .eq("server_id", server_id)
            .eq("item_tag", item_tag)
            .execute()
        )


        return [
            SellOrder(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                unit_price=entry.get("unit_price"),
                is_company=entry.get("is_company"),
            )
            for entry in response.data
        ]
    except Exception as e:
        print(e)


async def get_all_own_sell_orders(user_id: int, server_id: int, now: datetime, is_company):
    try:
        if is_company == "both":
            response = (
            supabase.table("Sell_Orders")
            .select("*")
            .eq("user_id", user_id)
            .eq("server_id", server_id)
            .execute()
        )
        else:

            response = (
                supabase.table("Sell_Orders")
                .select("*")
                .eq("user_id", user_id)
                .eq("server_id", server_id)
                .eq("is_company", is_company)
                .execute()
            )


        return [
            SellOrder(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                unit_price=entry.get("unit_price"),
                is_company=entry.get("is_company"),
            )
            for entry in response.data
        ]
    except Exception as e:
        print(e)



async def get_own_item_sell_orders(user_id: int, server_id: int, item_tag: str, now: datetime, is_company):
    try:
        if is_company == "both":
            response = (
                supabase.table("Sell_Orders")
                .select("*")
                .eq("user_id", user_id)
                .eq("server_id", server_id)
                .eq("item_tag", item_tag)
                .execute()
            )
        else:
            response = (
                supabase.table("Sell_Orders")
                .select("*")
                .eq("user_id", user_id)
                .eq("server_id", server_id)
                .eq("item_tag", item_tag)
                .eq("is_company", is_company)
                .execute()
            )

        return [
            SellOrder(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                unit_price=entry.get("unit_price"),
                is_company=entry.get("is_company"),
            )
            for entry in response.data
        ]
    except Exception as e:
        print(e)


async def get_buy_orders(server_id: int, item_tag: str, unit_price: float, now: datetime):
    try:
        response = (
            supabase.table("Buy_Orders")
            .select("*")
            .eq("server_id", server_id)
            .eq("item_tag", item_tag)
            .execute()
        )

        return [
            BuyOrder(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                unit_price=entry.get("unit_price"),
                is_company=entry.get("is_company"),
            )
            for entry in response.data
        ]
    except Exception as e:
        print(e)


async def get_item_buy_orders(server_id: int, item_tag: str, now: datetime):
    try:
        response = (
            supabase.table("Buy_Orders")
            .select("*")
            .eq("server_id", server_id)
            .eq("item_tag", item_tag)
            .execute()
        )


        return [
            BuyOrder(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                unit_price=entry.get("unit_price"),
                is_company=entry.get("is_company"),
            )
            for entry in response.data
        ]
    except Exception as e:
        print(e)


async def get_all_own_buy_orders(user_id: int, server_id: int, now: datetime, is_company):
    if is_company == "both":
        response = (
            supabase.table("Buy_Orders")
            .select("*")
            .eq("user_id", user_id)
            .eq("server_id", server_id)
            .execute()
        )
    else:
        response = (
            supabase.table("Buy_Orders")
            .select("*")
            .eq("user_id", user_id)
            .eq("server_id", server_id)
            .eq("is_company", is_company)
            .execute()
        )

    orders = []
    for entry in response.data:
        orders.append(BuyOrder(
            user_id=entry.get("user_id"),
            item_tag=entry.get("item_tag"),
            server_id=entry.get("server_id"),
            amount=entry.get("amount"),
            unit_price=entry.get("unit_price"),
            is_company=entry.get("is_company"),
        ))

    return orders


async def get_own_buy_orders(user_id: int, server_id: int, item_tag: str, unit_price: float, is_company):
    try:
        if is_company == "both":

            response = (
            supabase.table("Buy_Orders")
            .select("*")
            .eq("user_id", user_id)
            .eq("item_tag", item_tag)
            .eq("server_id", server_id)
            .eq("unit_price", unit_price)
            .execute()
        )
        else:
            response = (
            supabase.table("Buy_Orders")
            .select("*")
            .eq("user_id", user_id)
            .eq("item_tag", item_tag)
            .eq("server_id", server_id)
            .eq("unit_price", unit_price)
            .eq("is_company", is_company)
            .execute()
        )
        
        entries = []
        for entry in response.data:
            entries.append(BuyOrder(
                user_id=entry.get("user_id"),
                item_tag=entry.get("item_tag"),
                server_id=entry.get("server_id"),
                amount=entry.get("amount"),
                unit_price=entry.get("unit_price"),
                is_company=entry.get("is_company"),
            ))
        return entries
    except Exception as e:
        print(e)


async def get_market_item(server_id: int, item_tag: str):
    try:
        response = (
            supabase.table("Market_Items")
            .select("*")
            .eq("server_id", server_id)
            .eq("item_tag", item_tag)
            .execute()
        )

        if not response.data:
            return None

        entry = response.data[0]
        return MarketItem(
            item_tag=entry.get("item_tag"),
            server_id=entry.get("server_id"),
            min_price=entry.get("min_price"),
            max_price=entry.get("max_price"),
            stockpile=entry.get("stockpile"),
        )
    except Exception as e:
        print(e)


async def get_government(server_id: int):
    try:
        response = (
            supabase.table("Government")
            .select("*")
            .eq("id", server_id)
            .execute()
        )

        if not response.data:
            return None

        entry = response.data[0]
        return Government(
            id=entry.get("id"),
            created_at=entry.get("created_at"),
            taxrate=entry.get("taxrate"),
            interest_rate=entry.get("interest_rate"),
            treasury=entry.get("treasury"),
            governing_role=entry.get("governing_role"),
            admin_role=entry.get("admin_role"),
            gambling_pool=entry.get("gambling_pool")
        )
    except Exception as e:
        print(e)


async def get_gdp_entry(server_id: int, date: date):
    try:
        response = (
            supabase.table("Government_GDP")
            .select("*")
            .eq("server_id", server_id)
            .eq("date", date.isoformat())
            .execute()
        )

        if not response.data:
            return None

        entry = response.data[0]
        return GovernmentGDP(
            server_id=entry.get("server_id"),
            date=entry.get("date"),
            gdp_value=entry.get("gdp_value"),
        )
    except Exception as e:
        print(e)


async def get_all_gdp_entries(server_id: int, date: datetime):
    try:
        response = (
            supabase.table("Government_GDP")
            .select("*")
            .eq("server_id", server_id)
            .gte("date", date.isoformat())
            .order("date", desc=False)
            .execute()
        )

        if not response.data:
            return []

        result = []
        for entry in response.data:
            result.append(
                GovernmentGDP(
                    server_id=entry.get("server_id"),
                    date=entry.get("date"),
                    gdp_value=entry.get("gdp_value"),
                )
            )
        return result
    except Exception as e:
        print(e)


async def delete_buy_orders(user_id, server_id, item_tag, price=None):
    try:
        query = supabase.table("Buy_Orders") \
            .delete() \
            .eq("user_id", user_id) \
            .eq("server_id", server_id) \
            .eq("item_tag", item_tag)

        if price is not None:
            query = query.eq("unit_price", price)

        response = query.execute()
        return response
    except Exception as e:
        print(e)


async def delete_sell_orders(user_id, server_id, item_tag, price=None):
    try:
        query = supabase.table("Sell_Orders") \
            .delete() \
            .eq("user_id", user_id) \
            .eq("server_id", server_id) \
            .eq("item_tag", item_tag)

        if price is not None:
            query = query.eq("unit_price", price)

        response = query.execute()
        return response
    except Exception as e:
        print(e)




async def update_player(player: Player):

    try:

        def serialize_value(value):
            if isinstance(value, datetime):
                return value.isoformat()
            return value
        
        data = {k: serialize_value(v) for k, v in player.__dict__.items()}
        
        response = (
            supabase.table("Players")
            .update(data)
            .eq("id", player.id)
            .eq("server_id", player.server_id)
            .execute()
        )

        return response.data
    except Exception as e:
        print(e)



async def update_company(company: Company):
    try:

        def serialize_value(value):
            if isinstance(value, datetime):
                return value.isoformat()
            return value
        

        data = {k: serialize_value(v) for k, v in company.__dict__.items()}
        
        response = (
            supabase.table("Companies")
            .update(data)
            .eq("entrepreneur_id", company.entrepreneur_id)
            .eq("server_id", company.server_id)
            .execute()
        )

        return response.data
    except Exception as e:
        print(e)



async def update_company_item(item: CompanyItem):
    try:
        data = asdict(item)
        pk = {
            "company_entrepreneur_id": data.pop("company_entrepreneur_id"),
            "item_tag": data.pop("item_tag"),
            "server_id": data.pop("server_id"),
        }
        response = (
            supabase.table("Company_Items")
            .update(data)
            .eq("company_entrepreneur_id", pk["company_entrepreneur_id"])
            .eq("item_tag", pk["item_tag"])
            .eq("server_id", pk["server_id"])
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)




async def update_company_join_request(request: CompanyJoinRequest):
    try:
        data = asdict(request)
        pk = {
            "user_id": data.pop("user_id"),
            "server_id": data.pop("server_id"),
            "company_entrepreneur_id": data.pop("company_entrepreneur_id"),
        }
        response = (
            supabase.table("Company_Join_Requests")
            .update(data)
            .eq("user_id", pk["user_id"])
            .eq("server_id", pk["server_id"])
            .eq("company_entrepreneur_id", pk["company_entrepreneur_id"])
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)



async def update_government(gov: Government):
    try:
        def serialize_value(value):
            if isinstance(value, datetime):
                return value.isoformat()
            return value
        

        data = {k: serialize_value(v) for k, v in gov.__dict__.items()}
        
        response = (
            supabase.table("Government")
            .update(data)
            .eq("id", gov.id)
            .execute()
        )

        return response.data
    except Exception as e:
        print(e)



async def update_government_gdp(gdp: GovernmentGDP):
    try:
        def serialize_value(value):
            if isinstance(value, date):
                return value.isoformat()
            return value
        

        data = {k: serialize_value(v) for k, v in gdp.__dict__.items()}

        pk = {"server_id": data.pop("server_id"), "date": data.pop("date")}
        response = (
            supabase.table("Government_GDP")
            .update(data)
            .eq("server_id", pk["server_id"])
            .eq("date", pk["date"])
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)



async def update_market_item(item: MarketItem):
    data = asdict(item)
    pk = {"item_tag": data.pop("item_tag"), "server_id": data.pop("server_id")}
    response = (
        supabase.table("Market_Items")
        .update(data)
        .eq("item_tag", pk["item_tag"])
        .eq("server_id", pk["server_id"])
        .execute()
    )
    return response.data



async def update_player_item(item: PlayerItem):
    try:
        data = asdict(item)
        pk = {
            "user_id": data.pop("user_id"),
            "item_tag": data.pop("item_tag"),
            "server_id": data.pop("server_id"),
        }
        response = (
            supabase.table("Player_Items")
            .update(data)
            .eq("user_id", pk["user_id"])
            .eq("item_tag", pk["item_tag"])
            .eq("server_id", pk["server_id"])
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)



async def update_sell_order(order: SellOrder):
    try:
        def serialize_value(value):
            if isinstance(value, datetime):
                return value.isoformat()
            return value
        

        data = {k: serialize_value(v) for k, v in order.__dict__.items()}

        pk = {
            "user_id": data.pop("user_id"),
            "server_id": data.pop("server_id"),
            "item_tag": data.pop("item_tag"),
            "unit_price": data.pop("unit_price"),
            "is_company": data.pop("is_company"),
        }
        response = (
            supabase.table("Sell_Orders")
            .update(data)
            .eq("user_id", pk["user_id"])
            .eq("server_id", pk["server_id"])
            .eq("item_tag", pk["item_tag"])
            .eq("unit_price", pk["unit_price"])
            .eq("is_company", pk["is_company"])
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)



async def update_buy_order(order: BuyOrder):
    try:
        def serialize_value(value):
            if isinstance(value, datetime):
                return value.isoformat()
            return value
        

        data = {k: serialize_value(v) for k, v in order.__dict__.items()}

        pk = {
            "user_id": data.pop("user_id"),
            "server_id": data.pop("server_id"),
            "item_tag": data.pop("item_tag"),
            "unit_price": data.pop("unit_price"),
            "is_company": data.pop("is_company"),
        }
        response = (
            supabase.table("Buy_Orders")
            .update(data)
            .eq("user_id", pk["user_id"])
            .eq("server_id", pk["server_id"])
            .eq("item_tag", pk["item_tag"])
            .eq("unit_price", pk["unit_price"])
            .eq("is_company", pk["is_company"])
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)



async def delete_company_item(company_entrepreneur_id: int, item_tag: str, server_id: int):
    try:
        response = (
            supabase.table("Company_Items")
            .delete()
            .eq("company_entrepreneur_id", company_entrepreneur_id)
            .eq("item_tag", item_tag)
            .eq("server_id", server_id)
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)



async def delete_company(entrepreneur_id: int, server_id: int):
    try:
        response = (
            supabase.table("Companies")
            .delete()
            .eq("entrepreneur_id", entrepreneur_id)
            .eq("server_id", server_id)
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)


async def delete_join_requests(company_entrepreneur_id: int, user_id: int, server_id: int):
    try:
        response = (
            supabase.table("Company_Join_Requests")
            .delete()
            .eq("company_entrepreneur_id", company_entrepreneur_id)
            .eq("user_id", user_id)
            .eq("server_id", server_id)
            .execute()
        )
        return response.data
    
    except Exception as e:
        print(e)


async def delete_player_item(user_id: int, item_tag: str, server_id: int):
    try:
        response = (
            supabase.table("Player_Items")
            .delete()
            .eq("user_id", user_id)
            .eq("item_tag", item_tag)
            .eq("server_id", server_id)
            .execute()
        )
    
        return response.data

    except Exception as e:
        print(e)


async def add_object(obj: Any, table_name: str):
    try:
        data = obj.__dict__.copy()

        if isinstance(data.get("date"), date):
            data["date"] = data["date"].isoformat()

        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()

        response = (
            supabase.table(table_name)
            .insert(data)
            .execute()
        )
        return response.data
    except Exception as e:
        print(e)

   

