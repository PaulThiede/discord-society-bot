from sqlalchemy import (
    Column, Integer, Float, String, Boolean, Text, ForeignKey, Numeric, TIMESTAMP, BigInteger, delete, Date
)
from sqlalchemy.orm import declarative_base, relationship
import datetime
from discord.ui import View, Button
from discord import Interaction, ButtonStyle

from .db import get_session

Base = declarative_base()

class Player(Base):
    __tablename__ = "Players"
    id = Column(Numeric, primary_key=True)
    server_id = Column(Numeric, primary_key=True)
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    money = Column(Float, default=0)
    debt = Column(Float, default=0)
    hunger = Column(Integer, default=100)
    thirst = Column(Integer, default=100)
    job = Column(String, default="")
    health = Column(Integer, default=100)
    company_entrepreneur_id = Column(Numeric, nullable=True)
    taxes_owed = Column(Float, default=0)
    work_cooldown_until = Column(TIMESTAMP)
    job_switch_cooldown_until = Column(TIMESTAMP)
    company_creation_cooldown_until = Column(TIMESTAMP)
    gift_cooldown_until = Column(TIMESTAMP)




class Item(Base):
    __tablename__ = "Items"
    item_tag = Column(Text, primary_key=True)
    producible = Column(Boolean)
    ingredients = Column(Text)   # JSON wäre besser, wenn strukturiert
    worksteps = Column(Integer)
    base_price = Column(Float)
    durability = Column(Integer)


class Company(Base):
    __tablename__ = "Companies"
    entrepreneur_id = Column(Numeric, primary_key=True)
    server_id = Column(Numeric, primary_key=True)
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    producible_items = Column(Text)  # auch hier ggf. JSON später
    capital = Column(Float)
    worksteps = Column(Text)
    wage = Column(Float)
    name = Column(Text)
    taxes_owed = Column(Float)


class MarketItem(Base):
    __tablename__ = "Market_Items"
    item_tag = Column(Text, primary_key=True)
    server_id = Column(Numeric, primary_key=True)
    min_price = Column(Float)
    max_price = Column(Float)
    stockpile = Column(BigInteger)


class PlayerItem(Base):
    __tablename__ = "Player_Items"
    user_id = Column(Numeric, primary_key=True)
    item_tag = Column(Text, primary_key=True)
    server_id = Column(Numeric, primary_key=True)
    amount = Column(BigInteger)
    durability = Column(Integer)


class CompanyItem(Base):
    __tablename__ = "Company_Items"
    company_entrepreneur_id = Column(Numeric, primary_key=True)
    item_tag = Column(Text, primary_key=True)
    server_id = Column(Numeric, primary_key=True)
    amount = Column(BigInteger)


class CompanyJoinRequest(Base):
    __tablename__ = "Company_Join_Requests"
    user_id = Column(Numeric, primary_key=True)
    server_id = Column(Numeric, primary_key=True)
    company_entrepreneur_id = Column(Numeric, primary_key=True)

class BuyOrder(Base):
    __tablename__ = "Buy_Orders"
    user_id = Column(Numeric, primary_key=True)
    item_tag = Column(Text, primary_key=True)
    server_id = Column(Numeric, primary_key=True)
    amount = Column(BigInteger)
    unit_price = Column(Float, primary_key=True)
    expires_at = Column(TIMESTAMP)
    is_company = Column(Boolean, primary_key=True)

class SellOrder(Base):
    __tablename__ = "Sell_Orders"
    user_id = Column(Numeric, primary_key=True)
    item_tag = Column(Text, primary_key=True)
    server_id = Column(Numeric, primary_key=True)
    amount = Column(BigInteger)
    unit_price = Column(Float, primary_key=True)
    expires_at = Column(TIMESTAMP)
    is_company = Column(Boolean, primary_key=True)

class Government(Base):
    __tablename__ = "Government"
    id = Column(Numeric, primary_key=True)
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    taxrate = Column(Float)
    interest_rate = Column(Float)
    treasury = Column(Float)
    governing_role = Column(Numeric)
    admin_role = Column(Numeric)

class GovernmentGDP(Base):
    __tablename__ = "Government_GDP"
    server_id = Column(Numeric, primary_key=True)
    date = Column(Date, primary_key=True)  # z.B. 2025-07-02
    gdp_value = Column(Float, default=0.0)