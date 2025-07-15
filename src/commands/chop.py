from src.helper.generic_job import execute_job

async def chop(interaction):
    print(f"{interaction.user}: /chop")

    job_name = "Lumberjack"
    job_items = ["Axe", "Chainsaw"]
    err_message = "You don't have an axe or chainsaw! How do you expect to chop down trees without it?"
    resource_choices = ["Wood", "Rubber"]
    job_verb = "chopped"

    await execute_job(interaction, job_name, job_items, err_message, resource_choices, job_verb)