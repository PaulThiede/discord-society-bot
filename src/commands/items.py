from discord import Interaction, Embed, Color

from src.db.db_calls import get_all_items
from src.helper.paginator import Paginator

async def get_items(interaction: Interaction):
    print(f"{interaction.user}: /items")
    await interaction.response.defer(thinking=True)

    items = await get_all_items()

    if not items:
        await interaction.followup.send("No items found.")
        return

    paginator = Paginator(get_page_embed, items)
    await interaction.followup.send(embed=get_page_embed(0, items, paginator.items_per_page, paginator.max_page), view=paginator)

def get_page_embed(page: int, query_result, items_per_page, max_page) -> Embed:
    embed = Embed(
        title=f"Item List (Page {page + 1}/{max_page + 1})",
        description="List of all registered items",
        color=Color.green()
    )
    for item in query_result[page * items_per_page:(page + 1) * items_per_page]:
        embed.add_field(
            name=item.item_tag,
            value=f"Base Price: ${item.base_price}\n" +
                f"Producible: {item.producible}\n" +
                  (f"Ingredients: {item.ingredients.replace(',', ', ').replace(':', ': ')}\n" if item.ingredients is not None else '') +
                  (f"Worksteps: {item.worksteps}\n" if item.worksteps is not None else '') +
                  (f"Durability: {item.durability}\n" if item.durability is not None else ''),
            inline=False
        )
    return embed

