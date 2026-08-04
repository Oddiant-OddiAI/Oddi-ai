import json

try:
    with open("database/memory.json", "r") as file:
        memory = json.load(file)
except:
    memory = {}