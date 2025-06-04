import nextcord 
from nextcord.ext import commands, menus
from nextcord import Intents, Interaction, Embed, File
from config import * 
from typing import Dict, List, Optional 
from database import Database
from misc import dock_it
from nextcord.ext.commands.errors import MissingAnyRole
from nextcord.utils import escape_markdown

runningContainers = dict()
database = Database()
docker = dock_it()

intents = Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

class Pager(menus.ListPageSource):
    
    def __init__(self, data):
        super().__init__(data, per_page=15)
    
    async def format_page(self, menu, entries):
        desc = "```\n"
        desc += "╔"+"═"*7+"╦"+"═"*20+"╗"
        k=1
        for entry in entries:
            if entry in ["easy", "medium", "hard"]:
                if k != 1:
                    desc += "\n╠"+"═"*7+"╬"+"═"*20+"║"
                
                desc += f"\n║{entry.title()}{" "*(7-len(entry))}║{" "*20}║"
                k = 0
            else:
                desc+="\n╠"+"═"*7+"╬"+"═"*20+"╣"
                challid, name = entry.split()
                desc += "\n║"+challid+" ║"+name+" "*(20-len(name))+"║"
        desc += "\n╚"+"═"*7+"╩"+"═"*20+"╝"
        desc += "\n```"
        embed=Embed(title="Here you go!", description=desc, color=nextcord.Color.blurple())
        return embed

def updateBannedUsers() -> None:
    global BANNED_USERS
    BANNED_USERS = database.bannedUsers()

def toggleEphemeralMessage() -> None:
    global EPHEMERAL
    EPHEMERAL = not EPHEMERAL

async def deleteAllRoles(userid:int) -> None:
    guild = bot.get_guild(GID[0])
    user = guild.get_member(userid)
    roles = user.roles 
    toDelete = []
    for role in roles:
        if role.name in ALL_ROLES:
            toDelete.append(role)
    await user.remove_roles(*toDelete)

async def modifyRole(userid:str, role:str, action:str) -> None :
 
    guild = bot.get_guild(GID[0])    
    roles = guild.roles 
    allotRole = None 
    for _role in roles:
        if _role.name == role:
            allotRole = _role 
            break 
    if not allotRole:
        return   
    member = guild.get_member(int(userid))
    if action == "assign":
        await member.add_roles(allotRole)
    else :
        await member.remove_roles(allotRole)


async def checkCompletionAssignRole(userid:str, category:str) -> None :
    categoryTotal = database.getCategoryMaxScore(category=category)
    userTotal = database.getCategoryScore(uid=userid, category=category)
    completion = (userTotal/categoryTotal)*100
    if completion >= 20 and completion < 50:
        await modifyRole(userid, ROLES[category][0], action="assign")
    elif completion >= 50 and completion < 80:
        await modifyRole(userid, ROLES[category][1], action="assign")
        await modifyRole(userid, ROLES[category][0], action="remove")
    else:
        await modifyRole(userid, ROLES[category][2], action="assign")
        await modifyRole(userid, ROLES[category][1], action="remove")

async def checkUser(interaction:Interaction) -> bool:
    userid : int = interaction.user.id
    if str(userid) in BANNED_USERS:
        await interaction.followup.send(embed=BAN_EMBED)
        return False
    if database.isUserPresent(str(userid)) != 1:
        await interaction.followup.send(embed=NOT_REGISTERED_EMBED)
        return False
    return True 

@bot.slash_command(name="ping", description="Check Bot Latency.", guild_ids=GID)
async def ping(interaction:Interaction):

    await interaction.response.send_message(f"Pong! In {round(bot.latency*1000)}ms.", ephemeral=EPHEMERAL) 

@bot.slash_command(name="about", description="In case you want to know more about our lonely Syre!", guild_ids=GID)
async def about(interaction:Interaction):

    await interaction.response.send_message(embed=ABOUT_EMBED)

@bot.slash_command(name="register", description="Register yourself to get Started!", guild_ids=GID)    
async def register(interaction:Interaction):
    
    user : nextcord.User = interaction.user
    response : int = database.addUser(name=user.name, uid=user.id) 
    if response == 0:
        await interaction.response.send_message(embed=ON_REGISTRATION_SUCCESS_EMBED)
    
    else : 
       await interaction.response.send_message(embed=ON_REGISTRATION_FAILURE_EMBED, ephemeral=EPHEMERAL) 

@bot.slash_command(name="list_challenges", description="Take a look of available challenges.", guild_ids=GID)
async def listChallenges(interaction:Interaction, category:str=CATEGORY_SELECTION): 
    
    await interaction.response.defer(ephemeral=EPHEMERAL)
    
    check : bool = await checkUser(interaction)
    if check is False:
        return 

    challList : List = database.getChallList(category) 
    if challList:
        pages = menus.ButtonMenuPages(
            source=Pager(challList)
        )
        await pages.start(interaction=interaction)

    else:
        await interaction.followup.send(embed=NO_CHALL_DESC_EMBED, ephemeral=EPHEMERAL)

@bot.slash_command(name="start_challenge", description="Start your challenge!", guild_ids=GID)
async def startChallenge(interaction:Interaction, challengeid:str):
    
    await interaction.response.defer(ephemeral=EPHEMERAL)

    user : nextcord.User = interaction.user 
    check : bool = await checkUser(interaction)
    if check is False:
        return

    if not database.challExists(challengeid):
        await interaction.followup.send(embed=CHALL_NOT_FOUND_EMBED, ephemeral=EPHEMERAL)
        return 
    
    if database.isChallRunning(uid=user.id, challid=challengeid):
        await interaction.followup.send(embed=CHALL_ALREADY_RUNNING_EMBED, ephemeral=EPHEMERAL)
        return 
    
    if len(database.userDetails(uid=user.id).get("active_challs")) >= MAX_ACTIVE_CHALLENGES :
        await interaction.followup.send(embed=MAX_ACTIVE_CHALLENGES, ephemeral=EPHEMERAL)
        return

    if database.getChallCategory(challengeid) in ["pwn", "rev"]:
        if len(docker.botContainersList()) >= MAX_CONTAINERS_COUNT :
            await interaction.followup.send(embed=MAX_CONTAINERS_ERROR_EMBED, ephemeral=EPHEMERAL)
            return 
    
        if len(database.userDetails(uid=user.id).get("active_containers")) >= MAX_CONTAINERS_COUNT_PER_USER :
            await interaction.followup.send(embed=MAX_CONTAINERS_PER_USER_ERROR_EMBED, ephemeral=EPHEMERAL)
            return 


    response : Dict[str, str | List] = database.startChallenge(uid=user.id, challid=challengeid)
    if response['started'] is False:
        embed : nextcord.Embed = Embed(title="Oops!", description="Error occurred:-\n"+response["notes"])
        await interaction.followup.send(embed=embed, ephemeral=EPHEMERAL)
        return 

    embed : nextcord.Embed = Embed(title="Running!", description="Your challenge has started! :white_check_mark:\n"+response["notes"])
    await interaction.followup.send(embed=embed, files=[File(file) for file in response["files"]], ephemeral=EPHEMERAL)

@bot.slash_command(name="stop_challenge", description="Stop a running challenge", guild_ids=GID)
async def stopChallenge(interaction : Interaction, challengeid:str):

    await interaction.response.defer()

    user : nextcord.User = interaction.user 
    check : bool = await checkUser(interaction)
    if check is False:
        return 
    
    if not database.isChallRunning(uid=user.id, challid=challengeid):
        await interaction.followup.send(embed=CHALL_NOT_STARTED_EMBED, ephemeral=EPHEMERAL)
        return 
    
    if database.getChallCategory(challengeid) in ["pwn", "web"]:
        for i in runningContainers:
            if challengeid in runningContainers[i] and user.id in runningContainers[i]:
                break
        try:
            del runningContainers[i]
        except Exception as e : 
            print(str(e))
 
    challStop : bool = database.stopChallenge(uid=user.id, challid=challengeid)
    if challStop : 
        await interaction.followup.send(embed=CHALL_STOPPED_EMBED, ephemeral=EPHEMERAL)

@bot.slash_command(name="active_challenges", description="Check your running challenges.", guild_ids=GID)
async def activeChallenges(interaction:Interaction):
    
    await interaction.response.defer()

    check : bool = await checkUser(interaction)
    if check is False:
        return 

    activeChalls : Optional[List[str]] = database.getActiveChallenges(interaction.user.id)
    embed : nextcord.Embed = Embed(title="Active Challenges", description="\n".join(activeChalls) if activeChalls else "None")
    await interaction.followup.send(embed=embed, ephemeral=EPHEMERAL)

@bot.slash_command(name="check_progress", description="Check your progress.", guild_ids=GID)
async def checkProgress(interaction:Interaction, category:str=CATEGORY_SELECTION):

    user : nextcord.User = interaction.user    
    await interaction.response.defer(ephemeral=EPHEMERAL)
    check : bool = await checkUser(interaction)
    if check is False:
        return 

    progress_dict : Dict[str, List] = database.getUserStatus(uid=user.id, category=category)
    if not progress_dict : 
        await interaction.followup.send(embed=NO_PROGRESS_ERROR_EMBED, ephemeral=EPHEMERAL)
        return 

    desc = ''
    for i in progress_dict:
        desc += '**' + i + '**' + ":\n"
        desc += escape_markdown('\n'.join(chall for chall in progress_dict[i]))
        desc += '\n\n'

    embed : nextcord.Embed = Embed(color=0x5be61c, title=category.title(), description=desc)
    await interaction.followup.send(embed=embed, ephemeral=EPHEMERAL)

@bot.slash_command(name="submit_flag", description="I waited an eternity for this.")
async def submit_flag(interaction:Interaction, challengeid:str, flag:str):
 
    await interaction.response.defer()
    user : nextcord.User = interaction.user 
    check : bool = await checkUser(interaction)
    if check is False:
        return 

    message : nextcord.Message = await interaction.followup.send(embed=CHALL_STATUS_CHECK_EMBED, ephemeral=EPHEMERAL)
    
    if not database.challExists(challid=challengeid):
        await message.edit(embed=CHALL_NOT_FOUND_EMBED)
        return 

    if not database.isChallRunning(uid=user.id,challid=challengeid):
        await message.edit(embed=CHALL_NOT_RUNNING_EMBED)
        return 

    message = await message.edit(embed=CHALL_ACTIVE_EMBED)

    if database.checkFlag(uid=user.id, challid=challengeid, flag=flag):
        await message.edit(embed=CORRECT_FLAG_EMBED)
        await checkCompletionAssignRole(userid=user.id, category=database.getChallCategory(challid=challengeid))
    else: 
        await message.edit(embed=INCORRECT_FLAG_EMBED)

@bot.command(name="flag")
@commands.has_any_role(*ADMIN_ROLES)
async def flag(ctx, challengeid:str):

    flag = database.getFlag(challengeid)
    await ctx.send("```"+flag+"```")

@bot.group(name="set", invoke_without_command=True)
@commands.has_any_role(*ADMIN_ROLES)
async def _set(ctx):
    
    if ctx.invoked_subcommand is None:
        await ctx.send("**Use $help set**")

@_set.command(name="ephemeral")
@commands.has_any_role(*ADMIN_ROLES)
async def ephemeral(ctx, action : str | None = None):
    
    if action is None:
        toggleEphemeralMessage()
        reply = "Ephemeral messages are now on" if EPHEMERAL else "Ephemeral messages are now off"
    else:
        if action.lower() == "on":
            if EPHEMERAL :
                reply = "Ephemeral messages are already on!"
            else: 
                toggleEphemeralMessage()
                reply = "Ephemeral messages are now on!"
        elif action.lower() == "off":
            if not EPHEMERAL:
                reply = "Ephemeral messages are already off!"
            else:
                toggleEphemeralMessage()
                reply = "Ephemeral messages are now off!"

        else:
            reply = "Invalid argument."

    await ctx.send(reply)
 

@bot.group(name="user", invoke_without_subcommand=True)
@commands.has_any_role(*ADMIN_ROLES)
async def user(ctx:commands.context):

    if ctx.invoked_subcommand is None:
        await ctx.send("Use $help user.")

@user.command(name="progress")
@commands.has_any_role(*ADMIN_ROLES)
async def progress(ctx:commands.context, user:nextcord.User | None = None):

    if not isinstance(user, nextcord.User):
        await ctx.send("Sunn aise use kr ke dekh:-\n$user progress @(user)")
        return
     
    user_info = database.userDetails(user.id)
    if not user_info: return await ctx.send("No such user found!")

    desc = ""
    for category in CHOICES:
        if len(user_info[category]) != 0:
            desc += f"**Challs completed in {category}**\n- " + "\n- ".join(user_info[category])+"\n"
    if len(desc) == 0 : desc = "No progress yet."
    await ctx.send(desc)

@user.command(name="status")
@commands.has_any_role(*ADMIN_ROLES)
async def status(ctx, user : nextcord.User | None = None):

    if not isinstance(user, nextcord.User):
        await ctx.send("Thik se use krna sikh le:-\n$user stats @(user)")
        return 
    response = database.isUserBanned(user.id)
    if response is None : reply = "No such user found"
    if response : reply = "User is banned"
    else : reply = "User is not banned"
    await ctx.send(reply)

@user.command(name="ban")
@commands.has_any_role(*ADMIN_ROLES)
async def ban(ctx, user : nextcord.User | None = None):

    if not isinstance(user, nextcord.User):
        await ctx.send("Aise use kro:-\n$user ban @(user)") 
        return 
    response = database.banUser(str(user.id))
    updateBannedUsers()
    await ctx.send(response)

@user.command(name="unban")
@commands.has_any_role(*ADMIN_ROLES)
async def unban(ctx, user : nextcord.User | None = None):

    if not isinstance(user, nextcord.User):
        await ctx.send("Aise use kro:-\n$user unban @(user)")

    response = database.unbanUser(user.id)
    updateBannedUsers()
    await ctx.send(response)

@user.command(name="remove")
@commands.has_any_role(*ADMIN_ROLES)
async def remove(ctx, user : nextcord.User | None = None):

    if not isinstance(user, nextcord.User):
        await ctx.send("Aise use kro:-\n$user remove @(user)")
        return 

    await deleteAllRoles(user.id)

    response : int = database.delete_user(str(user.id))

    if response == 0:
        await ctx.send("User deleted.")
    else : 
        await ctx.send("No such user has registered.")


@bot.group(name="containers",description="Manage Containers!", invoke_without_command=True)
@commands.has_any_role(*ADMIN_ROLES)
async def containers(ctx):

    if ctx.invoked_subcommand is None:
        await ctx.send("Use $help containers")

@containers.command(name="count")
@commands.has_any_role(*ADMIN_ROLES)
async def count(ctx):

    runningContainers = len(docker.botContainersList())
    if runningContainers == 0 : await ctx.send("No containers running.")
    elif runningContainers == 1: await ctx.send("1 container is running")
    else : await ctx.send(f"{runningContainers} container are running.") 

@containers.command(name="list")
@commands.has_any_role(*ADMIN_ROLES)
async def list(ctx : commands.Context, user:nextcord.User | None = None):

    if not isinstance(user, nextcord.User):
        await ctx.send("Aise use kr bhai:-\n$containers list @(user)")
        return 

    getContainers : List = database.getUserContainers(user.id)
    response : str = ""
    for i in getContainers:
        if len(i["active_containers"]) == 0 : continue
        response += f"**Containers running for {i['name']}**\n"
        for _, containerid in zip(i["active_containers"].keys(), i["active_containers"].values()) :
            labels = docker.getLabels(str(containerid))
            if labels is None : 
                response +=  f"```Container with id:- {containerid} for challengeid:- {_} stopped unexpectedly during runtime.```"
                continue 
            keys, values = labels.keys(), labels.values()
            temp = [key+" : "+value for key,value in zip(keys,values)]    
            response += "```"+"\n".join(temp)+"```"
        

    if not response : response = "No containers active."
    await ctx.send(response)

@containers.command(name="remove")
@commands.has_any_role(*ADMIN_ROLES)
async def remove(ctx, cid : str = None):

    if not cid : 
        return await ctx.send("**Usage**\n$containers remove all/containerid")
    allContainers = docker.botContainersList()
    
    if len(allContainers) == 0:
        return await ctx.send("Nothing to remove.")

    if cid == "all":
        await ctx.send("All containers destruction is triggered!")
        for container in allContainers:
            labels = container.labels
            database.stopChallenge(labels["uid"], labels["challid"])
    else:
        containerids = [i.id for i in allContainers]
        if cid not in containerids:
            await ctx.send("No container with given id is running.")
        else:
            for container in allContainers : 
                if container.id == cid : break
            labels = container.labels
            database.stopChallenge(labels["uid"], labels["challid"])
            await ctx.send("Container stopped!")

@bot.slash_command(name="scoreboard", description="Check scores!", guild_ids=GID)
async def scoreboard(interaction:Interaction, category=CATEGORY_SELECTION):
    scores = database.scoreboard(category)
    desc = "\n".join(i[1]+" "+i[0] for i in scores)
    await interaction.response.send_message(embed=Embed(title="LE SALE SCOREBOARD!", description=desc))

@bot.event 
async def on_ready():
    print(f"{bot.user.name} is ready!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, MissingAnyRole):
        await ctx.send(embed=RESTRICTED_EMBED)

if __name__ == "__main__":
    updateBannedUsers()
    bot.run(TOKEN)
