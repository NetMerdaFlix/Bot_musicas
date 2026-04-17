# User_Infor_bot_v3.py
"""
🕵️ User Info Bot Pro v3.0 — Telethon Edition
Créditos: Edivaldo Silva @Edkd1

Novidades v3.1:
  - Sistema "Ocultar infor" (owner) por campo e por usuário
  - Sistema Premium com módulos granulares
  - Telefone censurado para free / completo para premium
  - Paginação 20% free / 100% premium
  - Grupos 20% free / 100% premium
  - Gerar combo via userbot (Xtream Codes)
  - Limites de combo configuráveis por usuário
  - Busca via @Bot+termo → apenas username
  - Criação automática de todos os arquivos necessários
"""

import re
import json
import os
import asyncio
import tempfile
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError
from telethon.tl.functions.users import GetFullUserRequest

# ══════════════════════════════════════════════
# ⚙️  CONFIGURAÇÕES
# ══════════════════════════════════════════════
API_ID      = 29214781
API_HASH    = "9fc77b4f32302f4d4081a4839cc7ae1f"
PHONE       = "+5588998225077"
BOT_TOKEN   = "8618840827:AAHohLnNTWh_lkP4l9du6KJTaRQcPsNrwV8"
OWNER_ID    = 2061557102

BOT_USERNAME = "InforUser_Bot"   # SEM o @

FOLDER_PATH  = "data"
FILE_PATH    = os.path.join(FOLDER_PATH, "user_database.json")
LOG_PATH     = os.path.join(FOLDER_PATH, "monitor.log")
SESSION_USER = "session_monitor"
SESSION_BOT  = "session_bot"

ITEMS_PER_PAGE = 8
SCAN_INTERVAL  = 3600
MAX_HISTORY    = 50

# Padrão: "@BotUsername termo"  ou  "BotUsername termo"
BOT_SEARCH_PATTERN = re.compile(
    r'^@?' + re.escape(BOT_USERNAME) + r'\s+(.+)',
    re.IGNORECASE
)

# Módulos premium disponíveis
PREMIUM_MODULES = {
    "phone_full":      "☎️ Telefone 100%",
    "pagination_full": "🗂 Paginação Completa",
    "bio":             "🖊 Bio",
    "groups_full":     "✅ Ver todos os grupos",
    "combo":           "📋 Gerar combo",
}

# Padrões Xtream Codes
XTREAM_PATTERNS = [
    re.compile(r'https?://[^\s/]+(?::\d+)?/([A-Za-z0-9_\-\.]+)/([A-Za-z0-9_\-\.]+)'),
    re.compile(r'username=([^\s&"\']+)[&\s].*?password=([^\s&"\']+)'),
    re.compile(r'password=([^\s&"\']+)[&\s].*?username=([^\s&"\']+)'),
]

# ══════════════════════════════════════════════
# 📁  CRIAÇÃO AUTOMÁTICA DE ARQUIVOS E PASTAS
# ══════════════════════════════════════════════
os.makedirs(FOLDER_PATH, exist_ok=True)

def _ensure_files():
    """Garante que todos os arquivos necessários existem."""
    if not os.path.exists(FILE_PATH):
        default_db = {
            "_settings": {
                "free_combo_limit":    100,
                "premium_combo_limit": 500,
            }
        }
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_db, f, indent=2, ensure_ascii=False)

    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] Log iniciado\n")

_ensure_files()

# ══════════════════════════════════════════════
# 📁  BANCO DE DADOS
# ══════════════════════════════════════════════
def carregar_dados() -> dict:
    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            db = json.load(f)
    except (json.JSONDecodeError, IOError):
        db = {}
    # Garante chave _settings
    if "_settings" not in db:
        db["_settings"] = {
            "free_combo_limit":    100,
            "premium_combo_limit": 500,
        }
    return db

def salvar_dados(db: dict):
    try:
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except IOError as e:
        log(f"❌ Erro ao salvar banco: {e}")

def log(msg: str):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except IOError:
        pass

def iter_usuarios(db: dict):
    """Itera apenas entradas de usuários (ignora _settings)."""
    for k, v in db.items():
        if not k.startswith("_"):
            yield k, v

# ══════════════════════════════════════════════
# 🔑  CONTROLE DE ACESSO
# ══════════════════════════════════════════════
def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_premium_user(db: dict, uid: str) -> bool:
    if uid not in db or uid.startswith("_"):
        return False
    return db[uid].get("premium", {}).get("active", False)

def has_module(db: dict, uid: str, module: str) -> bool:
    if not is_premium_user(db, uid):
        return False
    return module in db[uid].get("premium", {}).get("modules", [])

def is_field_hidden(dados: dict, field: str) -> bool:
    return dados.get("hidden_info", {}).get(field, False)

def get_combo_limits(db: dict, uid: str) -> tuple:
    """Retorna (free_limit, premium_limit) para o usuário."""
    settings       = db.get("_settings", {})
    global_free    = settings.get("free_combo_limit",    100)
    global_premium = settings.get("premium_combo_limit", 500)
    user_limits    = db.get(uid, {}).get("custom_combo_limits", {})
    return (
        user_limits.get("free",    global_free),
        user_limits.get("premium", global_premium),
    )

# ══════════════════════════════════════════════
# 📱  TELEFONE — CENSURA FREE
# ══════════════════════════════════════════════
def censurar_telefone(phone: str) -> str:
    """Exibe aprox. 20% dos dígitos — para usuários free."""
    if not phone:
        return "_Não disponível_"
    digits = re.sub(r'\D', '', phone)
    if len(digits) <= 2:
        return "`+**`"
    keep = max(1, len(digits) // 5)
    vis  = digits[:keep]
    mask = '*' * (len(digits) - keep)
    prefix = '+' if phone.startswith('+') else ''
    return f"`{prefix}{vis}{mask}`"

def exibir_telefone(dados: dict, viewer_id: int, db: dict) -> str:
    """
    Regras de exibição do telefone:
    1. Campo oculto pelo owner → só owner vê / demais veem 🔒
    2. Viewer é owner → vê sempre
    3. Viewer tem premium phone_full → vê completo
    4. Viewer free → vê censurado
    """
    phone  = dados.get("phone", "")
    hidden = is_field_hidden(dados, "phone")
    uid    = str(viewer_id)

    if is_owner(viewer_id):
        tag = " _(oculto para outros)_" if hidden else ""
        return f"`{phone}`{tag}" if phone else f"_Não disponível_{tag}"

    if hidden:
        return "🔒 _Oculto pelo administrador_"

    if has_module(db, uid, "phone_full"):
        return f"`{phone}`" if phone else "_Não disponível_"

    return censurar_telefone(phone)

def exibir_campo(dados: dict, field: str, viewer_id: int) -> str | None:
    """Retorna None se o campo está oculto para este viewer."""
    if is_owner(viewer_id):
        return dados.get(field, "")
    if is_field_hidden(dados, field):
        return None
    return dados.get(field, "")

# ══════════════════════════════════════════════
# 🤖  CLIENTES TELETHON
# ══════════════════════════════════════════════
user_client = TelegramClient(SESSION_USER, API_ID, API_HASH)
bot         = TelegramClient(SESSION_BOT,  API_ID, API_HASH)

scan_running = False
scan_stats   = {"last_scan": None, "users_scanned": 0,
                "groups_scanned": 0, "changes_detected": 0}

# ══════════════════════════════════════════════
# 🧠  MÁQUINA DE ESTADOS (multi-etapas)
# ══════════════════════════════════════════════
# pending_states[chat_id] = {
#   "action": str,
#   "data":   dict
# }
pending_states: dict = {}

# pending_module_sel[chat_id] = {
#   "target_uid": str,
#   "modules":    set()
# }
pending_module_sel: dict = {}

# ══════════════════════════════════════════════
# 🔔  NOTIFICAÇÃO
# ══════════════════════════════════════════════
async def notificar(texto: str):
    try:
        await bot.send_message(OWNER_ID, texto, parse_mode='md')
    except Exception as e:
        log(f"Erro notificação: {e}")

# ══════════════════════════════════════════════
# 💾  PERFIL COMPLETO
# ══════════════════════════════════════════════
async def obter_perfil_completo(client: TelegramClient, user_id: int) -> dict:
    extras = {"bio": "", "phone": "", "fotos": 0, "restricoes": "Nenhuma"}
    try:
        full = await client(GetFullUserRequest(user_id))
        extras["bio"]  = full.full_user.about or ""
        extras["fotos"] = full.full_user.profile_photo is not None
        raw_user = full.users[0] if full.users else None
        if raw_user:
            extras["phone"]      = getattr(raw_user, 'phone', '') or ""
            extras["restricoes"] = str(getattr(raw_user, 'restriction_reason', '') or "Nenhuma")
    except Exception as e:
        log(f"⚠️ Perfil completo indisponível para {user_id}: {e}")
    return extras

async def salvar_usuario_dm(user) -> None:
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    db    = carregar_dados()
    uid   = str(user.id)

    nome_atual = (f"{user.first_name or ''} {user.last_name or ''}".strip() or "Sem nome")
    user_atual = f"@{user.username}" if user.username else "Nenhum"
    extras     = await obter_perfil_completo(bot, user.id)

    if uid not in db:
        db[uid] = {
            "id":                user.id,
            "nome_atual":        nome_atual,
            "username_atual":    user_atual,
            "bio":               extras["bio"],
            "phone":             extras["phone"],
            "fotos":             extras["fotos"],
            "restricoes":        extras["restricoes"],
            "grupos":            [],
            "fonte":             "DM",
            "primeiro_registro": agora,
            "historico":         [],
            "hidden_info":       {"phone": False, "id": False,
                                  "username": False, "bio": False},
            "premium":           {"active": False, "modules": []},
            "custom_combo_limits": {},
        }
        salvar_dados(db)
        log(f"💬 Novo via DM: {nome_atual} ({uid})")
        await notificar(
            f"💬 **NOVO USUÁRIO NO DM**\n\n"
            f"👤 Nome: `{nome_atual}`\n🆔 `{user_atual}`\n🔢 ID: `{uid}`\n"
            f"📱 `{extras['phone'] or 'Oculto'}`\n📝 `{extras['bio'][:80] or 'N/A'}`"
        )
        return

    changed = False
    if db[uid]["nome_atual"] != nome_atual:
        db[uid]["historico"].append({"data": agora, "tipo": "NOME",
                                     "de": db[uid]["nome_atual"], "para": nome_atual, "grupo": "DM"})
        await notificar(f"🔔 **MUDANÇA NOME (DM)**\n`{db[uid]['nome_atual']}` ➜ `{nome_atual}`")
        db[uid]["nome_atual"] = nome_atual
        changed = True

    if db[uid]["username_atual"] != user_atual:
        db[uid]["historico"].append({"data": agora, "tipo": "USER",
                                     "de": db[uid]["username_atual"], "para": user_atual, "grupo": "DM"})
        await notificar(f"🆔 **MUDANÇA USERNAME (DM)**\n`{db[uid]['username_atual']}` ➜ `{user_atual}`")
        db[uid]["username_atual"] = user_atual
        changed = True

    db[uid].setdefault("hidden_info",       {"phone": False, "id": False, "username": False, "bio": False})
    db[uid].setdefault("premium",           {"active": False, "modules": []})
    db[uid].setdefault("custom_combo_limits", {})
    db[uid]["bio"]        = extras["bio"]
    db[uid]["phone"]      = extras["phone"]
    db[uid]["fotos"]      = extras["fotos"]
    db[uid]["restricoes"] = extras["restricoes"]

    if len(db[uid]["historico"]) > MAX_HISTORY:
        db[uid]["historico"] = db[uid]["historico"][-MAX_HISTORY:]

    salvar_dados(db)
    if changed:
        log(f"🔄 Atualização DM: {nome_atual} ({uid})")

# ══════════════════════════════════════════════
# 🎨  BOTÕES E MENUS
# ══════════════════════════════════════════════
def menu_principal_buttons(owner: bool = False) -> list:
    base = [
        [Button.inline("🔍 Buscar Usuário",    b"cmd_buscar"),
         Button.inline("📊 Estatísticas",       b"cmd_stats")],
        [Button.inline("📋 Últimas Alterações", b"cmd_recent"),
         Button.inline("⚙️ Configurações",      b"cmd_config")],
        [Button.inline("ℹ️ Sobre",              b"cmd_about")],
    ]
    if owner:
        base.insert(1, [
            Button.inline("🔄 Varredura",        b"cmd_scan"),
            Button.inline("📤 Exportar Banco",   b"cmd_export"),
        ])
        base.insert(2, [
            Button.inline("🙈 Ocultar infor",    b"cmd_ocultar_menu"),
            Button.inline("⭐ Gerenciar Premium", b"cmd_premium_menu"),
        ])
        base.insert(3, [
            Button.inline("🎛️ Config. Combo",    b"cmd_combo_config"),
        ])
    return base

def voltar_button() -> list:
    return [[Button.inline("🔙 Menu Principal", b"cmd_menu")]]

def paginar_buttons(prefix: str, page: int, total_pages: int) -> list:
    nav = []
    if page > 0:
        nav.append(Button.inline("◀️", f"{prefix}_page_{page-1}".encode()))
    nav.append(Button.inline(f"📄 {page+1}/{total_pages}", b"noop"))
    if page < total_pages - 1:
        nav.append(Button.inline("▶️", f"{prefix}_page_{page+1}".encode()))
    return [nav, [Button.inline("🔙 Menu Principal", b"cmd_menu")]]

def module_selection_buttons(chat_id: int, target_uid: str) -> list:
    """Botões de seleção de módulos premium com estado ✅/⬜."""
    sel  = pending_module_sel.get(chat_id, {}).get("modules", set())
    rows = []
    for mod_key, mod_label in PREMIUM_MODULES.items():
        mark   = "✅" if mod_key in sel else "⬜"
        label  = f"{mark} {mod_label}"
        cb     = f"toggle_mod_{target_uid}_{mod_key}".encode()
        rows.append([Button.inline(label, cb)])
    rows.append([
        Button.inline("✔️ Confirmar",  f"confirm_premium_{target_uid}".encode()),
        Button.inline("❌ Cancelar",   b"cmd_premium_menu"),
    ])
    return rows

# ══════════════════════════════════════════════
# 🔍  BUSCA
# ══════════════════════════════════════════════
def buscar_usuario(query: str, username_only: bool = False) -> list:
    db          = carregar_dados()
    query_lower = query.lower().lstrip('@')
    results     = []

    for uid, dados in iter_usuarios(db):
        username = dados.get("username_atual", "").lower().lstrip('@')

        if username_only:
            if username and query_lower == username:
                results.insert(0, dados)
            elif username and query_lower in username:
                results.append(dados)
            continue

        if query == uid:
            results.insert(0, dados)
            continue
        if username and query_lower == username:
            results.insert(0, dados)
            continue
        nome = dados.get("nome_atual", "").lower()
        if query_lower in nome or (username and query_lower in username):
            results.append(dados)

    # Remove duplicatas mantendo ordem
    seen = set()
    unique = []
    for r in results:
        rid = r.get("id")
        if rid not in seen:
            seen.add(rid)
            unique.append(r)
    return unique

def formatar_perfil(dados: dict, viewer_id: int, db: dict) -> str:
    uid      = dados.get("id", "?")
    nome     = dados.get("nome_atual", "Desconhecido")
    username = dados.get("username_atual", "Nenhum")
    restricoes = dados.get("restricoes", "Nenhuma")
    fonte    = dados.get("fonte", "Varredura")
    historico = dados.get("historico", [])
    uid_str  = str(uid)
    owner    = is_owner(viewer_id)
    viewer_str = str(viewer_id)

    # ── Campo ID ──
    if is_field_hidden(dados, "id") and not owner:
        id_text = "🔒 _Oculto_"
    else:
        id_text = f"`{uid}`"
        if owner and is_field_hidden(dados, "id"):
            id_text += " _(oculto para outros)_"

    # ── Campo Username ──
    if is_field_hidden(dados, "username") and not owner:
        username_text = "🔒 _Oculto_"
    else:
        username_text = f"`{username}`"
        if owner and is_field_hidden(dados, "username"):
            username_text += " _(oculto para outros)_"

    # ── Campo Bio ──
    bio_raw = dados.get("bio", "")
    if is_field_hidden(dados, "bio") and not owner:
        bio_text = "🔒 _Oculto_"
    elif has_module(db, viewer_str, "bio") or owner:
        bio_text = f"`{bio_raw[:120]}`" if bio_raw else "_Nenhuma_"
        if owner and is_field_hidden(dados, "bio"):
            bio_text += " _(oculto para outros)_"
    else:
        bio_text = f"`{bio_raw[:120]}`" if bio_raw else "_Nenhuma_"

    # ── Campo Telefone ──
    phone_text = exibir_telefone(dados, viewer_id, db)

    # ── Grupos ──
    grupos = dados.get("grupos", [])
    if owner or has_module(db, viewer_str, "groups_full"):
        g_show = grupos
        g_extra = ""
    else:
        max_g  = max(1, len(grupos) // 5) if grupos else 0
        g_show = grupos[:max_g]
        if len(grupos) > max_g:
            g_extra = f" _(+{len(grupos)-max_g} ocultos — Premium)_"
        else:
            g_extra = ""
    grupos_text = ", ".join(g_show[:8]) or "N/A"
    if len(g_show) > 8:
        grupos_text += f" (+{len(g_show)-8})"
    grupos_text += g_extra

    # ── Histórico recente ──
    total_ch = len(historico)
    recent   = historico[-5:]
    hist_text = ""
    for h in reversed(recent):
        emoji     = "📛" if h.get("tipo") == "NOME" else "🆔"
        hist_text += f"  {emoji} `{h['data']}` — {h['de']} ➜ {h['para']}\n"
    if not hist_text:
        hist_text = "  _Nenhuma alteração registrada_\n"

    first_seen  = historico[0]["data"]  if historico else "N/A"
    last_change = historico[-1]["data"] if historico else "N/A"

    # ── Premium tag ──
    is_prem = is_premium_user(db, uid_str)
    prem_tag = " ⭐ **PREMIUM**" if (is_prem and owner) else ""

    return (
        f"╔══════════════════════════╗\n"
        f"║  🕵️ **PERFIL DO USUÁRIO**  ║\n"
        f"╚══════════════════════════╝{prem_tag}\n\n"
        f"👤 **Nome:** `{nome}`\n"
        f"🆔 **Username:** {username_text}\n"
        f"🔢 **ID:** {id_text}\n"
        f"📱 **Telefone:** {phone_text}\n"
        f"📝 **Bio:** {bio_text}\n"
        f"🚫 **Restrições:** `{restricoes}`\n"
        f"📡 **Fonte:** `{fonte}`\n"
        f"📂 **Grupos:** _{grupos_text}_\n\n"
        f"📊 **Resumo:**\n"
        f"├ 📝 Total de alterações: **{total_ch}**\n"
        f"├ 📅 Primeiro registro: `{first_seen}`\n"
        f"└ 🕐 Última alteração: `{last_change}`\n\n"
        f"📜 **Últimas Alterações:**\n"
        f"{hist_text}\n"
        f"_Créditos: @Edkd1_"
    )

async def _enviar_resultados(event, query: str, results: list,
                              viewer_id: int, db: dict,
                              page: int = 0, username_only: bool = False):
    owner      = is_owner(viewer_id)
    viewer_str = str(viewer_id)
    prem       = is_premium_user(db, viewer_str) or owner

    if not results:
        tip = "(busca por username)" if username_only else ""
        await event.reply(
            f"❌ **Nenhum resultado para** `{query}` {tip}\n\n"
            f"💡 Tente ID numérico, @username ou nome parcial.",
            parse_mode='md', buttons=voltar_button()
        )
        return

    if len(results) == 1:
        await event.reply(
            formatar_perfil(results[0], viewer_id, db),
            parse_mode='md',
            buttons=[[Button.inline("📜 Histórico",
                                    f"hist_{results[0]['id']}_0".encode())],
                     *voltar_button()]
        )
        return

    # Paginação
    total = len(results)
    if prem and has_module(db, viewer_str, "pagination_full") or owner:
        ipp         = ITEMS_PER_PAGE
        total_pages = max(1, (total + ipp - 1) // ipp)
    else:
        # Free: 20% dos resultados, 1 página
        max_free    = max(1, total // 5)
        results     = results[:max_free]
        total       = len(results)
        ipp         = ITEMS_PER_PAGE
        total_pages = 1

    page  = min(page, total_pages - 1)
    start = page * ipp
    chunk = results[start:start + ipp]

    tag  = " _(username only)_" if username_only else ""
    text = f"🔍 **{total} resultado(s) para** `{query}`{tag}  —  pág. {page+1}/{total_pages}\n\n"
    btns = []
    for r in chunk:
        label = f"👤 {r['nome_atual']} | {r['username_atual']}"
        btns.append([Button.inline(label[:48], f"profile_{r['id']}".encode())])

    # Navegação de paginação nos resultados de busca
    nav = []
    if page > 0:
        nav.append(Button.inline("◀️", f"search_page_{query}_{page-1}".encode()))
    if page < total_pages - 1:
        nav.append(Button.inline("▶️", f"search_page_{query}_{page+1}".encode()))
    if nav:
        btns.append(nav)
    btns.append([Button.inline("🔙 Menu", b"cmd_menu")])

    if not prem and total < len(buscar_usuario(query)):
        text += "⚠️ _Resultados limitados. Premium desbloqueia busca completa._\n\n"

    await event.reply(text, parse_mode='md', buttons=btns)

# ══════════════════════════════════════════════
# 📋  GERADOR DE COMBO (Userbot)
# ══════════════════════════════════════════════
async def gerar_combo(limit: int) -> list:
    """Varre grupos via userbot extraindo credenciais Xtream Codes."""
    combos  = []
    seen    = set()

    try:
        async for dialog in user_client.iter_dialogs():
            if len(combos) >= limit:
                break
            if not (dialog.is_group or dialog.is_channel):
                continue
            try:
                async for msg in user_client.iter_messages(dialog.id, limit=200):
                    if not msg.text:
                        continue
                    for pat in XTREAM_PATTERNS:
                        for match in pat.findall(msg.text):
                            user_part = match[0].strip()
                            pass_part = match[1].strip()
                            if len(user_part) < 2 or len(pass_part) < 2:
                                continue
                            combo = f"{user_part}:{pass_part}"
                            if combo not in seen:
                                seen.add(combo)
                                combos.append(combo)
                            if len(combos) >= limit:
                                break
                    if len(combos) >= limit:
                        break
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception:
                continue
    except Exception as e:
        log(f"⚠️ Erro combo: {e}")

    return combos[:limit]

# ══════════════════════════════════════════════
# 📡  VARREDURA
# ══════════════════════════════════════════════
async def executar_varredura(notify_chat=None):
    global scan_running, scan_stats
    if scan_running:
        if notify_chat:
            await bot.send_message(notify_chat, "⚠️ Varredura já em andamento!")
        return

    scan_running = True
    scan_stats   = {"last_scan": None, "users_scanned": 0,
                    "groups_scanned": 0, "changes_detected": 0}
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    scan_stats["last_scan"] = agora
    db    = carregar_dados()

    if notify_chat:
        await bot.send_message(notify_chat,
            "🔄 **Varredura iniciada...**\n⏳ Aguarde notificação ao finalizar.",
            parse_mode='md')

    log("🔄 Varredura iniciada")
    try:
        async for dialog in user_client.iter_dialogs():
            if not (dialog.is_group or dialog.is_channel):
                continue
            nome_grupo = dialog.name
            scan_stats["groups_scanned"] += 1
            try:
                async for user in user_client.iter_participants(dialog.id):
                    if user.bot:
                        continue
                    uid        = str(user.id)
                    nome_atual = (f"{user.first_name or ''} {user.last_name or ''}".strip() or "Sem nome")
                    user_atual = f"@{user.username}" if user.username else "Nenhum"
                    extras     = await obter_perfil_completo(user_client, user.id)
                    scan_stats["users_scanned"] += 1

                    if uid not in db:
                        db[uid] = {
                            "id":                user.id,
                            "nome_atual":        nome_atual,
                            "username_atual":    user_atual,
                            "bio":               extras["bio"],
                            "phone":             extras["phone"],
                            "fotos":             extras["fotos"],
                            "restricoes":        extras["restricoes"],
                            "grupos":            [nome_grupo],
                            "fonte":             "Varredura",
                            "primeiro_registro": agora,
                            "historico":         [],
                            "hidden_info":       {"phone": False, "id": False,
                                                  "username": False, "bio": False},
                            "premium":           {"active": False, "modules": []},
                            "custom_combo_limits": {},
                        }
                    else:
                        db[uid].setdefault("hidden_info",
                                           {"phone": False, "id": False,
                                            "username": False, "bio": False})
                        db[uid].setdefault("premium",           {"active": False, "modules": []})
                        db[uid].setdefault("custom_combo_limits", {})

                        if nome_grupo not in db[uid].get("grupos", []):
                            db[uid].setdefault("grupos", []).append(nome_grupo)

                        db[uid]["bio"]        = extras["bio"]
                        db[uid]["phone"]      = extras["phone"]
                        db[uid]["fotos"]      = extras["fotos"]
                        db[uid]["restricoes"] = extras["restricoes"]

                        if db[uid]["nome_atual"] != nome_atual:
                            scan_stats["changes_detected"] += 1
                            db[uid]["historico"].append(
                                {"data": agora, "tipo": "NOME",
                                 "de": db[uid]["nome_atual"], "para": nome_atual,
                                 "grupo": nome_grupo})
                            await notificar(
                                f"🔔 **NOME ALTERADO**\n`{db[uid]['nome_atual']}` ➜ `{nome_atual}`\n📍 _{nome_grupo}_")
                            db[uid]["nome_atual"] = nome_atual

                        if db[uid]["username_atual"] != user_atual:
                            scan_stats["changes_detected"] += 1
                            db[uid]["historico"].append(
                                {"data": agora, "tipo": "USER",
                                 "de": db[uid]["username_atual"], "para": user_atual,
                                 "grupo": nome_grupo})
                            await notificar(
                                f"🆔 **USERNAME ALTERADO**\n`{db[uid]['username_atual']}` ➜ `{user_atual}`\n📍 _{nome_grupo}_")
                            db[uid]["username_atual"] = user_atual

                        if len(db[uid]["historico"]) > MAX_HISTORY:
                            db[uid]["historico"] = db[uid]["historico"][-MAX_HISTORY:]

            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log(f"⚠️ Erro grupo {nome_grupo}: {e}")
    except Exception as e:
        log(f"❌ Varredura: {e}")
    finally:
        salvar_dados(db)
        scan_running = False
        log(f"✅ Varredura: {scan_stats['groups_scanned']} grupos / "
            f"{scan_stats['users_scanned']} usuários / "
            f"{scan_stats['changes_detected']} alterações")

    if notify_chat:
        await bot.send_message(
            notify_chat,
            f"✅ **Varredura Concluída!**\n\n"
            f"📂 Grupos: **{scan_stats['groups_scanned']}**\n"
            f"👥 Usuários: **{scan_stats['users_scanned']}**\n"
            f"🔔 Alterações: **{scan_stats['changes_detected']}**\n"
            f"🕐 `{agora}`",
            parse_mode='md', buttons=voltar_button()
        )

# ══════════════════════════════════════════════
# 🎮  HANDLERS — COMANDOS
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(pattern='/start'))
async def cmd_start(event):
    if event.is_private:
        sender = await event.get_sender()
        asyncio.create_task(salvar_usuario_dm(sender))
    owner = is_owner(event.sender_id)
    await event.respond(
        f"╔══════════════════════════════╗\n"
        f"║  🕵️ **User Info Bot Pro v3.0**  ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"Monitor profissional de usuários Telegram.\n\n"
        f"🔍 Busca por ID, @username, nome ou:\n"
        f"`@{BOT_USERNAME} termo` → busca só por username\n\n"
        f"{'⭐ Painel owner ativo' if owner else '👤 Modo usuário'}\n\n"
        f"👨‍💻 _Créditos: Edivaldo Silva @Edkd1_",
        parse_mode='md',
        buttons=menu_principal_buttons(owner)
    )

@bot.on(events.NewMessage(pattern='/menu'))
async def cmd_menu_msg(event):
    await cmd_start(event)

@bot.on(events.NewMessage(pattern=r'/buscar\s+(.+)'))
async def cmd_buscar_text(event):
    if event.is_private:
        sender = await event.get_sender()
        asyncio.create_task(salvar_usuario_dm(sender))
    query   = event.pattern_match.group(1).strip()
    db      = carregar_dados()
    results = buscar_usuario(query)
    await _enviar_resultados(event, query, results, event.sender_id, db)

# ══════════════════════════════════════════════
# 🔘  CALLBACKS INLINE
# ══════════════════════════════════════════════
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data      = event.data.decode()
    chat_id   = event.chat_id
    sender_id = event.sender_id
    owner     = is_owner(sender_id)

    try:
        message = await event.get_message()

        # ────────────────────────────────────────
        # MENU PRINCIPAL
        # ────────────────────────────────────────
        if data == "cmd_menu":
            await message.edit(
                "🕵️ **User Info Bot Pro v3.0**\n\nSelecione uma opção:",
                parse_mode='md',
                buttons=menu_principal_buttons(owner)
            )

        # ────────────────────────────────────────
        # BUSCAR
        # ────────────────────────────────────────
        elif data == "cmd_buscar":
            pending_states[chat_id] = {"action": "search", "data": {}}
            await message.edit(
                f"🔍 **Modo Busca**\n\n"
                f"Envie:\n"
                f"• `123456789` → por ID\n"
                f"• `@username` → por username\n"
                f"• `Nome` → por nome parcial\n"
                f"• `@{BOT_USERNAME} termo` → apenas username\n\n"
                f"_Aguardando..._",
                parse_mode='md', buttons=voltar_button()
            )

        # ────────────────────────────────────────
        # OCULTAR INFOR — MENU (owner only)
        # ────────────────────────────────────────
        elif data == "cmd_ocultar_menu":
            if not owner:
                await event.answer("🚫 Restrito ao owner.", alert=True)
                return
            await message.edit(
                "🙈 **Ocultar Informações**\n\n"
                "Escolha qual campo ocultar ou revelar para um usuário.\n"
                "_O bot pedirá o ID ou @username do alvo._",
                parse_mode='md',
                buttons=[
                    [Button.inline("📵 Ocultar/Revelar Telefone",  b"ocultar_phone"),
                     Button.inline("🔒 Ocultar/Revelar ID",        b"ocultar_id")],
                    [Button.inline("👤 Ocultar/Revelar Username",   b"ocultar_username"),
                     Button.inline("📝 Ocultar/Revelar Bio",        b"ocultar_bio")],
                    [Button.inline("📋 Ver ocultações ativas",      b"ocultar_list")],
                    [Button.inline("🔙 Menu Principal",             b"cmd_menu")],
                ]
            )

        elif data in ("ocultar_phone", "ocultar_id", "ocultar_username", "ocultar_bio"):
            if not owner:
                await event.answer("🚫 Restrito ao owner.", alert=True)
                return
            field_map = {
                "ocultar_phone":    "phone",
                "ocultar_id":       "id",
                "ocultar_username": "username",
                "ocultar_bio":      "bio",
            }
            field = field_map[data]
            pending_states[chat_id] = {"action": "toggle_hide", "data": {"field": field}}
            await message.edit(
                f"🙈 **Ocultar/Revelar campo:** `{field}`\n\n"
                f"Envie o **ID numérico** ou **@username** do usuário alvo:",
                parse_mode='md', buttons=[[Button.inline("❌ Cancelar", b"cmd_ocultar_menu")]]
            )

        elif data == "ocultar_list":
            if not owner:
                await event.answer("🚫", alert=True)
                return
            db   = carregar_dados()
            text = "📋 **Campos ocultos ativos:**\n\n"
            found = False
            for uid, dados in iter_usuarios(db):
                hi = dados.get("hidden_info", {})
                ocultos = [k for k, v in hi.items() if v]
                if ocultos:
                    found = True
                    text += f"👤 `{dados['nome_atual']}` (`{uid}`)\n"
                    text += f"   🔒 {', '.join(ocultos)}\n\n"
            if not found:
                text += "_Nenhum campo oculto no momento._"
            await message.edit(text, parse_mode='md', buttons=[[
                Button.inline("🔙 Ocultar infor", b"cmd_ocultar_menu")]])

        # ────────────────────────────────────────
        # PREMIUM — MENU (owner only)
        # ────────────────────────────────────────
        elif data == "cmd_premium_menu":
            if not owner:
                await event.answer("🚫 Restrito ao owner.", alert=True)
                return
            await message.edit(
                "⭐ **Gerenciar Premium**\n\n"
                "Adicione ou remova o status premium de usuários\n"
                "e escolha quais módulos cada um pode acessar.",
                parse_mode='md',
                buttons=[
                    [Button.inline("➕ Adicionar Premium",  b"premium_add"),
                     Button.inline("➖ Remover Premium",    b"premium_remove")],
                    [Button.inline("📋 Listar Premiums",    b"premium_list")],
                    [Button.inline("🔙 Menu Principal",     b"cmd_menu")],
                ]
            )

        elif data == "premium_add":
            if not owner:
                await event.answer("🚫", alert=True)
                return
            pending_states[chat_id] = {"action": "add_premium", "data": {}}
            await message.edit(
                "➕ **Adicionar Premium**\n\n"
                "Envie o **ID** ou **@username** do usuário:",
                parse_mode='md',
                buttons=[[Button.inline("❌ Cancelar", b"cmd_premium_menu")]]
            )

        elif data == "premium_remove":
            if not owner:
                await event.answer("🚫", alert=True)
                return
            pending_states[chat_id] = {"action": "remove_premium", "data": {}}
            await message.edit(
                "➖ **Remover Premium**\n\n"
                "Envie o **ID** ou **@username** do usuário:",
                parse_mode='md',
                buttons=[[Button.inline("❌ Cancelar", b"cmd_premium_menu")]]
            )

        elif data == "premium_list":
            if not owner:
                await event.answer("🚫", alert=True)
                return
            db   = carregar_dados()
            text = "⭐ **Usuários Premium:**\n\n"
            found = False
            for uid, dados in iter_usuarios(db):
                prem = dados.get("premium", {})
                if prem.get("active"):
                    found   = True
                    modules = prem.get("modules", [])
                    mods    = ", ".join(PREMIUM_MODULES.get(m, m) for m in modules) or "Nenhum"
                    text   += f"👤 `{dados['nome_atual']}` (`{uid}`)\n📦 {mods}\n\n"
            if not found:
                text += "_Nenhum usuário premium cadastrado._"
            await message.edit(text, parse_mode='md', buttons=[[
                Button.inline("🔙 Premium", b"cmd_premium_menu")]])

        # ── Seleção de módulos ──
        elif data.startswith("toggle_mod_"):
            if not owner:
                await event.answer("🚫", alert=True)
                return
            parts      = data.split("_", 4)
            target_uid = parts[3]
            module     = parts[4]

            if chat_id not in pending_module_sel:
                pending_module_sel[chat_id] = {"target_uid": target_uid, "modules": set()}

            sel = pending_module_sel[chat_id]["modules"]
            if module in sel:
                sel.discard(module)
                await event.answer(f"⬜ {PREMIUM_MODULES.get(module, module)} desmarcado")
            else:
                sel.add(module)
                await event.answer(f"✅ {PREMIUM_MODULES.get(module, module)} marcado")

            await message.edit(
                f"⭐ **Selecionar módulos para** `{target_uid}`\n\n"
                f"Marque os módulos que o usuário vai receber:",
                parse_mode='md',
                buttons=module_selection_buttons(chat_id, target_uid)
            )

        elif data.startswith("confirm_premium_"):
            if not owner:
                await event.answer("🚫", alert=True)
                return
            target_uid = data.replace("confirm_premium_", "")
            db         = carregar_dados()

            if target_uid not in db:
                await event.answer("❌ Usuário não encontrado.", alert=True)
                return

            sel = pending_module_sel.pop(chat_id, {}).get("modules", set())
            db[target_uid]["premium"] = {"active": True, "modules": list(sel)}
            salvar_dados(db)
            mods_text = "\n".join(f"  ✅ {PREMIUM_MODULES.get(m, m)}" for m in sel) or "  _Nenhum_"
            await message.edit(
                f"✅ **Premium ativado!**\n\n"
                f"👤 `{db[target_uid]['nome_atual']}` (`{target_uid}`)\n\n"
                f"**Módulos:**\n{mods_text}",
                parse_mode='md',
                buttons=[[Button.inline("🔙 Premium", b"cmd_premium_menu")]]
            )
            log(f"⭐ Premium ativado: {target_uid} módulos={list(sel)}")

        # ────────────────────────────────────────
        # CONFIG. COMBO (owner)
        # ────────────────────────────────────────
        elif data == "cmd_combo_config":
            if not owner:
                await event.answer("🚫", alert=True)
                return
            db       = carregar_dados()
            settings = db.get("_settings", {})
            await message.edit(
                f"🎛️ **Configuração de Combo**\n\n"
                f"📊 **Limites globais atuais:**\n"
                f"├ Free: **{settings.get('free_combo_limit', 100)}** combos\n"
                f"└ Premium: **{settings.get('premium_combo_limit', 500)}** combos\n\n"
                f"Para alterar um usuário específico ou o global, envie:\n"
                f"`/setcombo <uid> <free_limit> <premium_limit>`\n"
                f"`/setcombo global <free_limit> <premium_limit>`",
                parse_mode='md',
                buttons=voltar_button()
            )

        # ────────────────────────────────────────
        # ESTATÍSTICAS
        # ────────────────────────────────────────
        elif data == "cmd_stats":
            db            = carregar_dados()
            total_users   = sum(1 for _ in iter_usuarios(db))
            total_changes = sum(len(d.get("historico", [])) for _, d in iter_usuarios(db))
            total_names   = sum(
                1 for _, d in iter_usuarios(db)
                for h in d.get("historico", []) if h["tipo"] == "NOME"
            )
            total_usernames = sum(
                1 for _, d in iter_usuarios(db)
                for h in d.get("historico", []) if h["tipo"] == "USER"
            )
            with_hist = sum(1 for _, d in iter_usuarios(db) if d.get("historico"))
            groups    = set()
            for _, d in iter_usuarios(db):
                groups.update(d.get("grupos", []))
            premium_count = sum(1 for _, d in iter_usuarios(db)
                                if d.get("premium", {}).get("active"))
            last = scan_stats.get("last_scan", "Nunca")

            if owner:
                text = (
                    f"╔══════════════════════╗\n║  📊 **ESTATÍSTICAS**  ║\n╚══════════════════════╝\n\n"
                    f"👥 Usuários no banco: **{total_users}**\n"
                    f"⭐ Usuários premium: **{premium_count}**\n"
                    f"📂 Grupos monitorados: **{len(groups)}**\n"
                    f"🔔 Alterações: **{total_changes}** "
                    f"(📛 {total_names} nomes / 🆔 {total_usernames} users)\n\n"
                    f"🕐 Última varredura: `{last}`\n"
                    f"💾 Banco: **{os.path.getsize(FILE_PATH)//1024 if os.path.exists(FILE_PATH) else 0} KB**"
                )
            else:
                text = (
                    f"╔══════════════════════╗\n║  📊 **ESTATÍSTICAS**  ║\n╚══════════════════════╝\n\n"
                    f"🔔 Total de alterações: **{total_changes}**\n"
                    f"📛 Mudanças de nome: **{total_names}**\n"
                    f"🆔 Mudanças de username: **{total_usernames}**\n"
                    f"🕐 Última varredura: `{last}`"
                )
            await message.edit(text, parse_mode='md', buttons=voltar_button())

        # ────────────────────────────────────────
        # VARREDURA (owner)
        # ────────────────────────────────────────
        elif data == "cmd_scan":
            if not owner:
                await event.answer("🚫 Restrito ao owner.", alert=True)
                return
            if scan_running:
                await event.answer("⏳ Já em andamento!", alert=True)
            else:
                await event.answer("🔄 Iniciando varredura...")
                asyncio.create_task(executar_varredura(notify_chat=chat_id))

        # ────────────────────────────────────────
        # ÚLTIMAS ALTERAÇÕES (paginado)
        # ────────────────────────────────────────
        elif data == "cmd_recent" or data.startswith("recent_page_"):
            page = 0
            if data.startswith("recent_page_"):
                page = int(data.split("_")[-1])

            db          = carregar_dados()
            viewer_str  = str(sender_id)
            prem        = is_premium_user(db, viewer_str) or owner
            all_changes = []
            for uid, dados in iter_usuarios(db):
                for h in dados.get("historico", []):
                    all_changes.append({**h, "uid": uid, "nome": dados["nome_atual"]})

            all_changes.sort(key=lambda x: x["data"], reverse=True)

            if not prem:
                max_items   = max(1, len(all_changes) // 5)
                all_changes = all_changes[:max_items]

            total       = len(all_changes)
            total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            page        = min(page, total_pages - 1)
            chunk       = all_changes[page * ITEMS_PER_PAGE:(page + 1) * ITEMS_PER_PAGE]

            text = f"📋 **Últimas Alterações** — pág. {page+1}/{total_pages}\n\n"
            if not chunk:
                text += "_Nenhuma alteração registrada._"
            else:
                for c in chunk:
                    emoji = "📛" if c["tipo"] == "NOME" else "🆔"
                    text += f"{emoji} `{c['data']}`\n   👤 {c['nome']} — {c['de']} ➜ {c['para']}\n\n"

            if not prem and len(all_changes) < total:
                text += "_⚠️ Resultados limitados (Free). Premium = histórico completo._"

            await message.edit(text, parse_mode='md',
                               buttons=paginar_buttons("recent", page, total_pages))

        # ────────────────────────────────────────
        # EXPORTAR (owner)
        # ────────────────────────────────────────
        elif data == "cmd_export":
            if not owner:
                await event.answer("🚫 Restrito ao owner.", alert=True)
                return
            if os.path.exists(FILE_PATH):
                await bot.send_file(chat_id, FILE_PATH,
                                    caption="📤 **Banco exportado!**\n_@Edkd1_",
                                    parse_mode='md')
                await event.answer("✅ Enviado!")
            else:
                await event.answer("❌ Banco vazio!", alert=True)

        # ────────────────────────────────────────
        # CONFIGURAÇÕES
        # ────────────────────────────────────────
        elif data == "cmd_config":
            await message.edit(
                f"⚙️ **Configurações**\n\n"
                f"🔄 Intervalo varredura: **{SCAN_INTERVAL//60} min**\n"
                f"📜 Máx. histórico/usuário: **{MAX_HISTORY}**\n"
                f"📄 Itens/página: **{ITEMS_PER_PAGE}**\n"
                f"💾 Banco: `{FILE_PATH}`\n"
                f"📝 Log: `{LOG_PATH}`\n\n"
                f"_Altere as constantes no topo do arquivo._",
                parse_mode='md', buttons=voltar_button()
            )

        # ────────────────────────────────────────
        # SOBRE
        # ────────────────────────────────────────
        elif data == "cmd_about":
            await message.edit(
                f"╔══════════════════════════════╗\n"
                f"║  ℹ️ **SOBRE**                  ║\n"
                f"╚══════════════════════════════╝\n\n"
                f"🕵️ **User Info Bot Pro v3.0**\n\n"
                f"**Recursos Free:**\n"
                f"☎️ Telefone (censurado 20%)\n"
                f"🗂 Paginação limitada\n"
                f"🖊 Bio\n"
                f"✅ Grupos (20%)\n\n"
                f"**Recursos Premium:** ⭐\n"
                f"☎️ Telefone 100%\n"
                f"🗂 Paginação completa\n"
                f"🖊 Bio completa\n"
                f"✅ Todos os grupos\n"
                f"📋 Gerar combo\n\n"
                f"👨‍💻 Criado por: **Edivaldo Silva**\n"
                f"📱 Contato: @Edkd1\n"
                f"🔖 Versão: **3.1**",
                parse_mode='md', buttons=voltar_button()
            )

        # ────────────────────────────────────────
        # PERFIL INDIVIDUAL
        # ────────────────────────────────────────
        elif data.startswith("profile_"):
            uid = data.replace("profile_", "")
            db  = carregar_dados()
            if uid in db:
                prem_btn = []
                if (is_premium_user(db, str(sender_id)) and
                        has_module(db, str(sender_id), "combo")) or owner:
                    prem_btn = [[Button.inline("📋 Gerar Combo", f"combo_{uid}".encode())]]
                await message.edit(
                    formatar_perfil(db[uid], sender_id, db),
                    parse_mode='md',
                    buttons=[
                        [Button.inline("📜 Histórico", f"hist_{uid}_0".encode())],
                        *prem_btn,
                        [Button.inline("🔙 Menu", b"cmd_menu")],
                    ]
                )
            else:
                await event.answer("❌ Usuário não encontrado.", alert=True)

        # ────────────────────────────────────────
        # HISTÓRICO PAGINADO
        # ────────────────────────────────────────
        elif data.startswith("hist_"):
            parts = data.split("_")
            uid   = parts[1]
            page  = int(parts[2]) if len(parts) > 2 else 0

            db         = carregar_dados()
            viewer_str = str(sender_id)

            if uid not in db:
                await event.answer("❌ Usuário não encontrado.", alert=True)
                return

            prem      = is_premium_user(db, viewer_str) or owner
            dados     = db[uid]
            historico = list(reversed(dados.get("historico", [])))

            if not prem:
                max_items = max(1, len(historico) // 5)
                historico = historico[:max_items]

            total       = len(historico)
            total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            page        = min(page, total_pages - 1)
            chunk       = historico[page * ITEMS_PER_PAGE:(page + 1) * ITEMS_PER_PAGE]

            text = (f"📜 **Histórico de** `{dados['nome_atual']}`\n"
                    f"ID: `{uid}` — pág. {page+1}/{total_pages}\n\n")

            for h in chunk:
                emoji = "📛" if h.get("tipo") == "NOME" else "🆔"
                text += f"{emoji} `{h['data']}`\n  {h['de']} ➜ {h['para']}\n  📍 _{h.get('grupo','N/A')}_\n\n"

            if not chunk:
                text += "_Sem registros._"

            if not prem:
                text += "⚠️ _Histórico limitado (Free)._"

            await message.edit(text, parse_mode='md',
                               buttons=paginar_buttons(f"hist_{uid}", page, total_pages))

        # ────────────────────────────────────────
        # GERAR COMBO
        # ────────────────────────────────────────
        elif data.startswith("combo_"):
            viewer_str = str(sender_id)
            db         = carregar_dados()

            can_combo = (owner or
                         (is_premium_user(db, viewer_str) and
                          has_module(db, viewer_str, "combo")))
            if not can_combo:
                await event.answer("🚫 Recurso exclusivo Premium.", alert=True)
                return

            free_lim, prem_lim = get_combo_limits(db, viewer_str)
            limit = prem_lim if (is_premium_user(db, viewer_str) or owner) else free_lim

            await event.answer(f"📋 Gerando até {limit} combos...")
            msg_temp = await bot.send_message(
                chat_id,
                f"⏳ **Gerando combo...**\nBuscando credenciais Xtream em grupos.\nLimite: **{limit}**",
                parse_mode='md'
            )

            combos = await gerar_combo(limit)

            if not combos:
                await msg_temp.edit("❌ **Nenhum combo encontrado.**\n"
                                    "_Grupos precisam ter URLs Xtream Codes._",
                                    parse_mode='md')
                return

            combo_text = "\n".join(combos)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                             delete=False, encoding='utf-8') as f:
                f.write(f"# Combo gerado por @{BOT_USERNAME}\n")
                f.write(f"# Total: {len(combos)} | {datetime.now()}\n\n")
                f.write(combo_text)
                tmp_path = f.name

            await bot.send_file(
                chat_id, tmp_path,
                caption=f"📋 **{len(combos)} combos gerados!**\n_@Edkd1_",
                parse_mode='md'
            )
            os.unlink(tmp_path)
            await msg_temp.delete()

        elif data == "noop":
            await event.answer()
        else:
            await event.answer("⚠️ Ação não reconhecida.")

        try:
            await event.answer()
        except Exception:
            pass

    except Exception as e:
        log(f"❌ Callback [{data}]: {e}")
        try:
            await event.answer("❌ Erro interno.")
        except Exception:
            pass

# ══════════════════════════════════════════════
# 💬  HANDLER: TEXTO LIVRE
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(func=lambda e: e.is_private and not e.text.startswith('/')))
async def text_handler(event):
    chat_id   = event.chat_id
    sender_id = event.sender_id
    owner     = is_owner(sender_id)
    text      = event.text.strip()
    db        = carregar_dados()

    sender = await event.get_sender()
    asyncio.create_task(salvar_usuario_dm(sender))

    # ── Busca via "@BotUsername termo" → apenas username ──
    bot_match = BOT_SEARCH_PATTERN.match(text)
    if bot_match:
        query   = bot_match.group(1).strip()
        results = buscar_usuario(query, username_only=True)
        await _enviar_resultados(event, query, results, sender_id, db, username_only=True)
        return

    # ── Estado: toggle_hide (ocultar campo) ──
    state = pending_states.get(chat_id)
    if state and state["action"] == "toggle_hide":
        del pending_states[chat_id]
        field   = state["data"]["field"]
        query   = text.strip().lstrip('@')
        results = buscar_usuario(text)
        if not results:
            await event.reply(f"❌ Usuário `{text}` não encontrado no banco.",
                              parse_mode='md', buttons=[[Button.inline("🔙 Ocultar infor", b"cmd_ocultar_menu")]])
            return
        target  = results[0]
        uid_str = str(target["id"])
        db[uid_str].setdefault("hidden_info", {"phone": False, "id": False, "username": False, "bio": False})
        current = db[uid_str]["hidden_info"].get(field, False)
        db[uid_str]["hidden_info"][field] = not current
        salvar_dados(db)
        status = "🔒 Ocultado" if not current else "🔓 Revelado"
        await event.reply(
            f"{status} **campo `{field}`** para:\n"
            f"👤 `{target['nome_atual']}` (`{uid_str}`)",
            parse_mode='md',
            buttons=[[Button.inline("🔙 Ocultar infor", b"cmd_ocultar_menu")]]
        )
        log(f"🙈 Campo '{field}' {'ocultado' if not current else 'revelado'} para {uid_str}")
        return

    # ── Estado: add_premium ──
    if state and state["action"] == "add_premium":
        del pending_states[chat_id]
        results = buscar_usuario(text)
        if not results:
            await event.reply(f"❌ `{text}` não encontrado.", parse_mode='md',
                              buttons=[[Button.inline("🔙 Premium", b"cmd_premium_menu")]])
            return
        target     = results[0]
        target_uid = str(target["id"])
        pending_module_sel[chat_id] = {"target_uid": target_uid, "modules": set()}
        await event.reply(
            f"⭐ **Selecionar módulos para:**\n"
            f"👤 `{target['nome_atual']}` (`{target_uid}`)\n\n"
            f"Marque os módulos desejados e confirme:",
            parse_mode='md',
            buttons=module_selection_buttons(chat_id, target_uid)
        )
        return

    # ── Estado: remove_premium ──
    if state and state["action"] == "remove_premium":
        del pending_states[chat_id]
        results = buscar_usuario(text)
        if not results:
            await event.reply(f"❌ `{text}` não encontrado.", parse_mode='md',
                              buttons=[[Button.inline("🔙 Premium", b"cmd_premium_menu")]])
            return
        target     = results[0]
        target_uid = str(target["id"])
        db[target_uid]["premium"] = {"active": False, "modules": []}
        salvar_dados(db)
        await event.reply(
            f"✅ **Premium removido de:**\n👤 `{target['nome_atual']}` (`{target_uid}`)",
            parse_mode='md',
            buttons=[[Button.inline("🔙 Premium", b"cmd_premium_menu")]]
        )
        log(f"⭐ Premium removido: {target_uid}")
        return

    # ── Estado: busca genérica ──
    if state and state["action"] == "search":
        del pending_states[chat_id]
        results = buscar_usuario(text)
        await _enviar_resultados(event, text, results, sender_id, db)
        return

    # ── Mensagem genérica ──
    await event.reply(
        f"💡 Use /start para abrir o menu.\n"
        f"Busca rápida: `@{BOT_USERNAME} @username`",
        parse_mode='md',
        buttons=menu_principal_buttons(owner)
    )

# ══════════════════════════════════════════════
# 💬  HANDLER: GRUPOS (BotName + termo)
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(
    func=lambda e: not e.is_private and bool(e.text and BOT_SEARCH_PATTERN.match(e.text))
))
async def group_botname_search(event):
    match = BOT_SEARCH_PATTERN.match(event.text.strip())
    if not match:
        return
    query   = match.group(1).strip()
    db      = carregar_dados()
    results = buscar_usuario(query, username_only=True)
    await _enviar_resultados(event, query, results, event.sender_id, db, username_only=True)

# ══════════════════════════════════════════════
# 🎛️  COMANDO: SETCOMBO (owner)
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(pattern=r'/setcombo\s+(.+)'))
async def cmd_setcombo(event):
    if not is_owner(event.sender_id):
        await event.reply("🚫 Restrito ao owner.")
        return
    args = event.pattern_match.group(1).strip().split()
    if len(args) != 3:
        await event.reply("Uso: `/setcombo <uid|global> <free_limit> <premium_limit>`", parse_mode='md')
        return

    target, free_s, prem_s = args
    try:
        free_lim = int(free_s)
        prem_lim = int(prem_s)
    except ValueError:
        await event.reply("❌ Limites devem ser números inteiros.")
        return

    db = carregar_dados()
    if target.lower() == "global":
        db["_settings"]["free_combo_limit"]    = free_lim
        db["_settings"]["premium_combo_limit"] = prem_lim
        salvar_dados(db)
        await event.reply(
            f"✅ **Limites globais atualizados:**\nFree: `{free_lim}` | Premium: `{prem_lim}`",
            parse_mode='md'
        )
    elif target in db:
        db[target].setdefault("custom_combo_limits", {})
        db[target]["custom_combo_limits"]["free"]    = free_lim
        db[target]["custom_combo_limits"]["premium"] = prem_lim
        salvar_dados(db)
        await event.reply(
            f"✅ **Limites para** `{db[target]['nome_atual']}`:\nFree: `{free_lim}` | Premium: `{prem_lim}`",
            parse_mode='md'
        )
    else:
        await event.reply(f"❌ UID `{target}` não encontrado no banco.", parse_mode='md')

# ══════════════════════════════════════════════
# 🔁  AUTO-SCAN
# ══════════════════════════════════════════════
async def auto_scanner():
    while True:
        await asyncio.sleep(SCAN_INTERVAL)
        log("🔄 Auto-scan iniciado")
        await executar_varredura()

# ══════════════════════════════════════════════
# 🚀  MAIN
# ══════════════════════════════════════════════
async def main():
    _ensure_files()

    await user_client.start(PHONE)
    await bot.start(bot_token=BOT_TOKEN)

    log("🚀 User Info Bot Pro v3.1 iniciado — @Edkd1")
    log(f"📁 Arquivos: {FOLDER_PATH}/")
    log(f"🔄 Auto-scan a cada {SCAN_INTERVAL//60} min")
    log(f"🤖 Busca por username: '@{BOT_USERNAME} <termo>'")

    await executar_varredura(notify_chat=OWNER_ID)
    asyncio.create_task(auto_scanner())

    print("✅ Bot online! /start")
    await bot.run_until_disconnected()


if __name__ == "__main__":
    try:
        bot.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n👋 Encerrado com segurança.")
        log("Bot encerrado.")
