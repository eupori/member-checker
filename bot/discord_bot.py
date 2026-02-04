"""
Discord 봇 - 서버 멤버 목록 API 제공
"""
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import json

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.members = True  # SERVER MEMBERS INTENT 필요
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 멤버 목록 저장용
member_cache = {}


@bot.event
async def on_ready():
    print(f'{bot.user} 로그인 완료!')
    print(f'연결된 서버: {len(bot.guilds)}개')
    for guild in bot.guilds:
        print(f'  - {guild.name} (ID: {guild.id})')


@bot.command(name='멤버')
async def get_members(ctx):
    """현재 서버의 멤버 목록 출력"""
    guild = ctx.guild
    members = []
    
    async for member in guild.fetch_members(limit=None):
        if not member.bot:  # 봇 제외
            members.append({
                'id': str(member.id),
                'name': member.name,
                'display_name': member.display_name,
                'nick': member.nick
            })
    
    # 캐시에 저장
    member_cache[str(guild.id)] = members
    
    # 닉네임/표시이름 목록
    names = [m['display_name'] or m['name'] for m in members]
    
    await ctx.send(f'**멤버 목록 ({len(members)}명)**\n' + '\n'.join(names[:50]))
    if len(names) > 50:
        await ctx.send(f'... 외 {len(names) - 50}명')


@bot.command(name='목록저장')
async def save_members(ctx):
    """멤버 목록을 JSON 파일로 저장"""
    guild = ctx.guild
    members = []
    
    async for member in guild.fetch_members(limit=None):
        if not member.bot:
            members.append({
                'id': str(member.id),
                'name': member.name,
                'display_name': member.display_name,
                'nick': member.nick
            })
    
    filename = f'members_{guild.id}.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(members, f, ensure_ascii=False, indent=2)
    
    await ctx.send(f'✅ {len(members)}명의 멤버 목록을 `{filename}`에 저장했어요!')


def get_guild_members(guild_id: str) -> list:
    """API용: 캐시된 멤버 목록 반환"""
    return member_cache.get(guild_id, [])


async def fetch_guild_members(guild_id: int) -> list:
    """API용: 서버 멤버 목록 가져오기"""
    guild = bot.get_guild(guild_id)
    if not guild:
        return []
    
    members = []
    async for member in guild.fetch_members(limit=None):
        if not member.bot:
            members.append({
                'id': str(member.id),
                'name': member.name,
                'display_name': member.display_name,
                'nick': member.nick
            })
    
    member_cache[str(guild_id)] = members
    return members


def run_bot():
    bot.run(TOKEN)


if __name__ == '__main__':
    run_bot()
