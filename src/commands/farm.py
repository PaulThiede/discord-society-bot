from src.helper.generic_job import execute_job

async def farm(interaction, item_choice):
    print(f"{interaction.user}: /farm {item_choice}")

    job_name = "Farmer"
    job_items = [["F", "Fertilizer", "Tractor"], ["Tractor"]]
    err_message = ""
    resource_choices = ["Grain", "Fish", "Leather", "Wool"] if item_choice is None else [item_choice.value]
    job_verb = "farmed"

    await execute_job(interaction, job_name, job_items, err_message, resource_choices, job_verb)