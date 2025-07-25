from src.helper.generic_job import execute_job

async def mine(interaction):
    print(f"{interaction.user}: /mine")

    job_name = "Miner"
    job_items = [["Pickaxe"], ["Mining Machine"]]
    err_message = "You don't have a pickaxe! How do you expect to mine resources without it?"
    resource_choices = ["Iron", "Minerals", "Coal", "Phosphorus"]
    job_verb = "mined"

    await execute_job(interaction, job_name, job_items, err_message, resource_choices, job_verb)