from discord import Interaction, Embed, Color, ui, ButtonStyle

class Paginator(ui.View):
    def __init__(self, get_page_embed, query_result):
        super().__init__(timeout=60)
        self.page = 0
        self.get_page_embed = get_page_embed
        self.items_per_page = 5
        self.max_page = (len(query_result) - 1) // self.items_per_page
        self.query_result = query_result

    @ui.button(label="⏮️", style=ButtonStyle.secondary)
    async def first(self, interaction_btn: Interaction, _):
        self.page = 0
        await interaction_btn.response.edit_message(embed=self.get_page_embed(self.page, self.query_result, self.items_per_page, self.max_page), view=self)

    @ui.button(label="⬅️", style=ButtonStyle.primary)
    async def previous(self, interaction_btn: Interaction, _):
        if self.page > 0:
            self.page -= 1
            await interaction_btn.response.edit_message(embed=self.get_page_embed(self.page, self.query_result, self.items_per_page, self.max_page), view=self)
        else:
            await interaction_btn.response.defer()

    @ui.button(label="➡️", style=ButtonStyle.primary)
    async def next(self, interaction_btn: Interaction, _):
        if self.page < self.max_page:
            self.page += 1
            await interaction_btn.response.edit_message(embed=self.get_page_embed(self.page, self.query_result, self.items_per_page, self.max_page), view=self)
        else:
            await interaction_btn.response.defer()

    @ui.button(label="⏭️", style=ButtonStyle.secondary)
    async def last(self, interaction_btn: Interaction, _):
        self.page = self.max_page
        await interaction_btn.response.edit_message(embed=self.get_page_embed(self.page, self.query_result, self.items_per_page, self.max_page), view=self)


