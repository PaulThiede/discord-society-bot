from discord import Embed, Color

def create_inventory_embed(items, embed=Embed(title="")):
    if items:
        inventory_lines = []
        for item in items:
            line = f"{item.amount}x {item.item_tag}"
            if item.durability is not None:
                line += f" (Durability: {item.durability})"
            inventory_lines.append(line)
        inventory_str = "\n".join(inventory_lines)
        embed.add_field(name="Inventory", value=inventory_str, inline=False)
    else:
        embed.add_field(name="Inventory", value="Empty", inline=False)

    return embed


def create_job_embed(player, resource, amount, durability, old_hunger, old_thirst, tool, job_verb):
    embed = Embed(
        title="Success!",
        description=f"You just {job_verb} " + ("for your company" if player.job == "Worker" else "") + f" and gained {amount}x {resource}!",
        color=Color.green()
    )
    if durability is not None: embed.add_field(name=f"{tool} Durability", value=f"{durability} -> {durability - 1}")
    embed.add_field(name="Hunger", value=f"{old_hunger} -> {player.hunger}")
    embed.add_field(name="Thirst", value=f"{old_thirst} -> {player.thirst}")
    return embed