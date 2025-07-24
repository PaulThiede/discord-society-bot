from datetime import datetime

from dataclasses import dataclass
from typing import Optional


@dataclass
class Player:
    id: int
    server_id: int
    created_at: datetime
    money: float
    debt: float
    hunger: int
    thirst: int
    job: str
    health: int
    company_entrepreneur_id: Optional[int]
    taxes_owed: float
    work_cooldown_until: Optional[datetime]
    job_switch_cooldown_until: Optional[datetime]
    company_creation_cooldown_until: Optional[datetime]
    gift_cooldown_until: Optional[datetime]

@dataclass
class Item:
    item_tag: str
    producible: bool
    ingredients: Optional[str]
    worksteps: Optional[int]
    base_price: float
    durability: Optional[int]

@dataclass
class Company:
    entrepreneur_id: int
    server_id: int
    created_at: datetime
    producible_items: str
    capital: float
    worksteps: int
    wage: float
    name: str
    taxes_owed: float

@dataclass
class MarketItem:
    item_tag: str
    server_id: int
    min_price: float
    max_price: float
    stockpile: int

@dataclass
class PlayerItem:
    user_id: int
    item_tag: str
    server_id: int
    amount: int
    durability: Optional[int]

@dataclass
class CompanyItem:
    company_entrepreneur_id: int
    item_tag: str
    server_id: int
    amount: int

@dataclass
class CompanyJoinRequest:
    user_id: int
    server_id: int
    company_entrepreneur_id: int

@dataclass
class BuyOrder:
    user_id: int
    item_tag: str
    server_id: int
    amount: int
    unit_price: float
    expires_at: datetime
    is_company: bool

@dataclass
class SellOrder:
    user_id: int
    item_tag: str
    server_id: int
    amount: int
    unit_price: float
    expires_at: datetime
    is_company: bool

@dataclass
class Government:
    id: int
    created_at: datetime
    taxrate: float
    interest_rate: float
    treasury: float
    governing_role: Optional[int]
    admin_role: Optional[int]

@dataclass
class GovernmentGDP:
    server_id: int
    date: datetime
    gdp_value: float