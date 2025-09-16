from letta_client import Letta
import time
import os

client = Letta(base_url="http://localhost:8283")

# get an available embedding_config
embedding_configs = client.embedding_models.list()
embedding_config = embedding_configs[0]

# create the folder
folder = client.folders.create(
    name="my_folder",
    embedding_config=embedding_config
)

# upload a file into the folder
job = client.folders.files.upload(
    folder_id=folder.id,
    file=open("jr.pdf", "rb")
)

# wait until the job is completed
while True:
    job = client.jobs.retrieve(job.id)
    if job.status == "completed":
        break
    elif job.status == "failed":
        raise ValueError(f"Job failed: {job.metadata}")
    print(f"Job status: {job.status}")
    time.sleep(1)


# list files in the folder
files = client.folders.files.list(folder_id=folder.id)
print(f"Files in folder: {files}")

# list passages in the folder
passages = client.folders.passages.list(folder_id=folder.id)
print(f"Passages in folder: {passages}")
