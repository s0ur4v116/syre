import os
from pymongo import MongoClient

client = MongoClient("localhost", 27017)
db = client["db"]
challenges = db["challs"]
os.chdir("challenges")
startIndex = {
    "crypto": "120000",
    "web": "220000",
    "rev": "320000",
    "pwn": "420000",
    "gskills": "520000",
    "forensics": "620000",
}
directories = os.listdir()

for directory in directories:
    maxid = None
    domainPath = directory
    difficulties = os.listdir(domainPath)
    for difficulty in difficulties:
        difficultyPath = os.path.join(domainPath, difficulty)
        _challenges = os.listdir(difficultyPath)
        allchalls = [i for i in challenges.find({"category": directory})]
        presentChalls = [i.get("name") for i in allchalls]
        allchalls = [i.get("_id") for i in allchalls]
        if len(os.listdir(difficultyPath)) == 0:
            print(f"No challenges in {difficulty} under {directory}, skipping.")
            continue
        if not allchalls:
            maxid = startIndex[directory]
        elif not maxid:
            maxid = str(int(max(allchalls)) + 1)

        for challenge in _challenges:
            challengePath = os.path.join(difficultyPath, challenge)

            if challenge not in presentChalls:
                if not os.path.isfile(os.path.join(challengePath, "description.txt")):
                    print(
                        f"not found description.txt for the challenge {challenge} under {directory}"
                    )
                    print("Skipping")
                    continue
                if not os.path.isfile(os.path.join(challengePath, "flag.txt")):
                    print(
                        f"Not found flag.txt for the challenge {challenge} under {directory}"
                    )
                    print("skipping")
                    continue
                addthispath = "challenges"
                addthispath = os.path.join(addthispath, challengePath)
                toAdd = dict(
                    _id=str(maxid),
                    category=directory,
                    path=addthispath,
                    flag=open(os.path.join(challengePath, "flag.txt")).read().strip(),
                    difficulty=difficulty,
                    name=challenge,
                )
                print(f"Adding {challenge} in {directory} category")
                print("Adding :- ", toAdd)
                challenges.insert_one(toAdd)
                maxid = int(maxid) + 1
