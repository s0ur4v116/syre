from typing import Dict, List, Any, Optional
import pymongo
import os
from misc import dock_it
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from config import MONGO_URI, CHOICES, DIFFS

# categories = ["crypto","forensics","rev","pwn","osint","gskills","web"]
docker = dock_it()


class Database:
    def __init__(self, resetChallenges=True) -> None:
        client = pymongo.MongoClient(MONGO_URI)
        db = client["db"]
        self.challs = db["challs"]
        self.users = db["users"]
        self.containers = db["containers"]
        self.container = None
        self.runningContainers = {}
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self.containerDestroyer, "interval", minutes=1)
        self.scheduler.start()
        if resetChallenges:
            self.resetChallenges()

    def addContainer(self, containerid, userid, challid):
        startTime = datetime.now()
        endTime = startTime + timedelta(minutes=30)
        self.runningContainers[containerid] = [int(userid), challid, endTime]

    def containerDestroyer(self):
        updated = self.runningContainers.copy()
        for i in self.runningContainers:
            if self.runningContainers[i][2] <= datetime.now():
                userid = self.runningContainers[i][0]
                challid = self.runningContainers[i][1]
                del updated[i]
                self.stopChallenge(str(userid), str(challid))
                print(f"Destroyed container for user {userid}")
        self.runningContainers = updated.copy()

    def resetChallenges(self) -> None:
        self.users.update_many(
            {}, {"$set": {"active_containers": dict(), "active_challs": list()}}
        )

    def bannedUsers(self) -> List:
        return [i["_id"] for i in list(self.users.find({"isUserBanned": True}))]

    def user_info(self, username: str) -> Dict:
        return self.users.find_one({"name": username})

    def isUserPresent(self, uid: str) -> int:
        return self.users.count_documents({"_id": uid}, limit=1)

    def addUser(self, uid: str, name: str) -> int:
        if self.isUserPresent(str(uid)) != 0:
            return -1

        user: Dict[str, Any] = {
            "_id": str(uid),
            "name": name,
            "active_challs": [],
            "active_containers": {},
            "isUserBanned": False,
        }
        for category in CHOICES:
            user[category] = []
            user["score_" + category] = 0
        self.users.insert_one(user)
        return 0

    def isUserBanned(self, userid: str) -> bool:
        info = self.userDetails(userid)
        return info["isUserBanned"] if info is not None else None

    def delete_user(self, userid: str) -> int:
        if self.isUserPresent(userid) != 1:
            return -1

        self.users.delete_one({"_id": userid})

        return 0

    def getActiveChallenges(self, uid: str) -> Optional[Dict]:
        if len(self.users.find_one({"_id": str(uid)})["active_challs"]) == 0:
            return None

        else:
            toReturn = list()
            activeChalls = self.users.find_one({"_id": str(uid)})["active_challs"]
            for chall in activeChalls:
                name = self.challs.find_one({"_id": chall}, {"name": 1, "_id": 0})
                toReturn.append(chall + "  " + name["name"])
            return toReturn

    def banUser(self, userid: str) -> str:
        info = self.userDetails(uid=userid)
        if info is None:
            return f"No such user found"
        if info["isUserBanned"]:
            return f"User is already banned"
        else:
            self.users.update_one({"_id": userid}, {"$set": {"isUserBanned": True}})
            return f"User is banned"

    def unbanUser(self, userid: str) -> str:
        info = self.userDetails(uid=userid)
        if info is None:
            return f"No such user found"
        if not info["isUserBanned"]:
            return f"User is not banned"
        else:
            self.users.update_one(
                {"_id": str(userid)}, {"$set": {"isUserBanned": False}}
            )
            return f"User is no longer banned"

    def getChallList(self, category) -> str:
        challs = {"easy": [], "medium": [], "hard": []}

        for chall in self.challs.find({"category": category}):
            challs[chall["difficulty"]].append({str(chall["_id"]): chall["name"]})

        temp = []
        for difficulty in challs:
            if len(challs[difficulty]) == 0:
                continue
            temp.append(difficulty)
            for challenge in challs[difficulty]:
                temp.append(
                    list(challenge.keys())[0] + " " + list(challenge.values())[0]
                )

        return temp if temp else None

    def userDetails(self, uid: str) -> Dict:
        return self.users.find_one({"_id": str(uid)})

    def getChallDifficulty(self, challid: str, category: str) -> str:
        return self.challs.find_one({"_id": challid, "category": category}).get(
            "difficulty"
        )

    def getChallCategory(self, challid) -> str:
        return self.challs.find_one({"_id": challid}).get("category")

    def getUserStatus(self, uid: str, category: str) -> Dict[str, str]:
        completed = self.users.find_one({"_id": str(uid)})[category]
        status = {"Completed": [], "Not Completed": []}
        for chall in self.challs.find({"category": category}, {"_id": 0, "name": 1}):
            if chall["name"] in completed:
                status["Completed"].append(chall["name"])
            else:
                status["Not Completed"].append(chall["name"])
        return None if not status else status

    def get_chall_list(self, category: str) -> Dict[str, List[Dict]]:
        challs = {"easy": [], "medium": [], "hard": []}

        for chall in self.challs.find({"category": category}):
            challs[chall["difficulty"]].append({str(chall["_id"]): chall["name"]})

        temp = []
        for difficulty in challs:
            if len(challs[difficulty]) == 0:
                continue
            temp.append(difficulty)
            for challenge in challs[difficulty]:
                temp.append(
                    list(challenge.keys())[0] + "  " + list(challenge.values())[0]
                )

        return temp if temp else None

    def checkFlag(self, uid: str, challid: str, flag: str) -> bool:
        if self.challs.find_one({"_id": challid})["flag"] == flag:
            self.stopChallenge(uid, challid)
            self.updateStatus(uid, challid)
            return True
        else:
            return False

    def getFlag(self, challid: str) -> str:
        flag = self.challs.find_one({"_id": challid})
        return flag["flag"] if flag else "Not found"

    def updateStatus(self, uid: str, challid: int) -> None:
        challDetails = self.challs.find_one({"_id": challid})
        challName = challDetails["name"]
        challCategory = challDetails["category"]
        challCompleted = self.users.find_one({"_id": str(uid)})[challCategory]

        if challName not in challCompleted:
            challCompleted.append(challName)
            self.updateScore(uid=str(uid), challid=challid)
        self.users.update_one(
            {"_id": str(uid)}, {"$set": {challCategory: challCompleted}}
        )

    def isChallRunning(self, uid: str, challid: int) -> bool:
        return challid in self.users.find_one({"_id": str(uid)})["active_challs"]

    def challExists(self, challid: int) -> bool:
        if self.challs.find_one({"_id": challid}):
            return True
        else:
            return False

    def startChallenge(self, uid: str, challid: int) -> Dict:
        activeChallenges = self.users.find_one({"_id": str(uid)}).get("active_challs")
        files = []
        chall = self.challs.find_one({"_id": challid})
        footer = None
        if chall["category"] in ["web", "pwn"]:
            code = self.startContainer(chall, uid)
            if code != 0:
                started = False
                notes = "Backend Error!"
            else:
                started = True
                notes = open(os.path.join(chall["path"], "description.txt")).read()
                if chall["category"] == "web":
                    notes = notes.strip()
                    notes += (
                        "\nhttp://bondjames.sytes.net:" + self.container.labels["port"]
                    )
                else:
                    notes = notes.strip()
                    notes += f"\n```nc bondjames.sytes.net {self.container.labels['port']}```"

                activeChallenges.append(challid)
                self.users.update_one(
                    {"_id": str(uid)}, {"$set": {"active_challs": activeChallenges}}
                )
                footer = chall["name"] + ":" + chall["_id"]
                filesPath = os.path.join(chall["path"], "files")
                for file in os.listdir(filesPath):
                    files.append(os.path.join(filesPath, file))

        else:
            started = True
            notes = open(os.path.join(chall["path"], "description.txt")).read()
            activeChallenges.append(challid)
            self.users.update_one(
                {"_id": str(uid)}, {"$set": {"active_challs": activeChallenges}}
            )
            footer = "\n\n" + chall["_id"] + "\t" + chall["name"]
            filesPath = os.path.join(chall["path"], "files")
            for file in os.listdir(filesPath):
                files.append(os.path.join(filesPath, file))

        return {"started": started, "notes": notes, "files": files, "footer": footer}

    def startContainer(self, chall: Dict, uid: str) -> int:
        self.container = docker.run_container(uid, chall)
        if self.container is None:
            return -1
        self.addContainer(self.container.id, str(uid), str(chall["_id"]))
        activeContainers = self.users.find_one({"_id": str(uid)})["active_containers"]
        activeContainers[str(chall["_id"])] = str(self.container.id)
        self.users.update_one(
            {"_id": str(uid)}, {"$set": {"active_containers": activeContainers}}
        )
        return 0

    def getUserContainers(self, userid: str = None):
        if userid:
            return list(self.users.find({"_id": userid}))
        else:
            return list(self.users.find())

    def stopChallenge(self, uid: str, challid: str) -> bool:
        uid = int(uid)
        chall = self.challs.find_one({"_id": challid})
        if chall["category"] in ["web", "pwn"]:
            activeContainers = self.users.find_one({"_id": str(uid)})[
                "active_containers"
            ]
            if not activeContainers.get(challid):
                pass
            else:
                docker.remove_container(activeContainers[challid])
                del activeContainers[challid]
                self.users.update_one(
                    {"_id": str(uid)}, {"$set": {"active_containers": activeContainers}}
                )

        activeChallenges = self.users.find_one({"_id": str(uid)})["active_challs"]
        try:
            activeChallenges.remove(challid)
        except Exception as e:
            print(str(e))

        self.users.update_one(
            {"_id": str(uid)}, {"$set": {"active_challs": activeChallenges}}
        )
        return True

    def updateScore(self, uid: str, challid: str):
        # category, difficulty = map(self.challs.find_one({"_id":challid}).get, ["category","difficulty"])
        challInfo = self.challs.find_one({"_id": challid})
        category = challInfo.get("category")
        difficulty = challInfo.get("difficulty")
        name = challInfo.get("name")
        completedChalls = self.users.find_one({"_id": str(uid)}, {category: 1}).get(
            category
        )
        print(completedChalls)
        try:
            self.users.update_one(
                {"_id": str(uid)},
                {"$inc": {"score_" + category: DIFFS.index(difficulty) + 1}},
            )
        except Exception as e:
            print(str(e))

        print(self.users.find_one({"_id": str(uid)}, {"score_" + category: 1}))

    def getCategoryScore(self, uid: str, category: str):
        return self.users.find_one({"_id": str(uid)})["score_" + category]
        # allChalls = self.challs.find({"category":category})
        # score = 0
        # for chall in allChalls :
        #     score += DIFFS.index(chall["difficulty"]) + 1
        # return score

    def getCategoryMaxScore(self, category: str):
        allChalls = self.challs.find({"category": category})
        score = 0
        for chall in allChalls:
            score += DIFFS.index(chall["difficulty"]) + 1
        return score

    def scoreboard(self, category: str):
        temp = self.users.find()
        temp3 = list()
        for i in temp:  # Do not complain that code is untidy because of 3 temp vars
            temp2 = [str(i[f"score_{category}"]), i["name"]]
            temp3.append(temp2)
        return sorted(temp3)

    def getTotalScore(self, uid: str):
        return sum(self.getCategoryScore(uid, category) for category in CHOICES)

    def getTotalMaxScore(self):
        return sum(self.getCategoryMaxScore(category) for category in CHOICES)
