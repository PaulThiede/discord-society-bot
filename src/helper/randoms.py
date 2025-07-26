from random import choice, randint
from typing import List, Tuple


def generate_resources(choices: List[str], tool) -> Tuple:
    resource_type = choice(choices)

    ### LUMBERJACK ###
    if tool == "Chainsaw":
        amount = randint(2, 6) if resource_type == "Wood" else randint(1, 3) # Rubber
    elif tool == "Axe":
        amount = randint(1, 3) if resource_type == "Wood" else 1 # Rubber

    ### MINER ###
    elif tool == "Pickaxe":
        amount = randint(1, 2) if resource_type == "Iron" else 1 if resource_type == "Minerals" \
            else randint(1, 2) if resource_type == "Coal" else randint(1, 4) # Phosphorus
    elif tool == "Mining Machine":
        amount = randint(5, 12) if resource_type == "Iron" else  randint(3, 6) if resource_type == "Minerals" \
            else randint(5, 12) if resource_type == "Coal" else randint(7, 15) # Phosphorus

    ### FARMER ###
    elif tool == "Hand-F":
        amount = randint(1, 2) if resource_type == "Grain" else randint(1, 3) if resource_type == "Fish" \
            else randint(1, 3) if resource_type == "Leather" else randint(1, 2)  # Wool
    elif tool == "Fertilizer":
        amount = randint(1, 5) if resource_type == "Grain" else randint(2, 6) if resource_type == "Fish" \
            else randint(2, 6) if resource_type == "Leather" else randint(1, 5)  # Wool
    elif tool == "Tractor":
        amount = randint(8, 10) if resource_type == "Grain" else randint(10, 14) if resource_type == "Fish" \
            else randint(10, 14) if resource_type == "Leather" else randint(8, 10)  # Wool

    ### SPECIAL JOB ###
    elif tool == "Hand-W" or tool == "Hand-N" or tool == "Hand-P":
        amount = randint(1, 2)

    else:
        raise Exception(f"{tool} is not accounted for in generate_resources()")

    return resource_type, amount

def generate_rare_resources(choices: List[str], tool):
    resource_type = choice(choices)

    ### MINER ###
    if tool == "Pickaxe":
        amount = 1
    elif tool == "Mining Machine":
        amount = randint(1, 3) if resource_type == "Gold" else  randint(1, 2) # Diamond

    else:
        raise Exception(f"{tool} is not accounted for in generate_resources()")
    
    return resource_type, amount


def get_hunger_depletion():
    return randint(2,8)

def get_thirst_depletion():
    return randint(5,10)