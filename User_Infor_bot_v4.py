# User_Infor_bot_v3.2.py
"""
🕵️ User Info Bot Pro v3.2 — Telethon Edition
Créditos: Edivaldo Silva @Edkd1

Novidades v3.2 (correções profissionais):
  - 🐛 FIX: paginação de busca (search_page_*) — handler dedicado com cache
  - 🐛 FIX: paginação de histórico via paginar_buttons (hist_<uid>_page_<n>)
  - 🐛 FIX: "Abrir perfil" — Telegram bloqueia Button.url com tg://. Trocado por
           link inline clicável na mensagem + botão t.me quando há @username
  - 🐛 FIX: "@InforUser_Bot @username" agora prioriza banco (username_only=True)
           e só faz lookup externo se não encontrar nada
  - 🐛 FIX: callback genérico — roteamento robusto, sem "Ação não reconhecida"
           em prefixos válidos. Logs detalhados de cada branch.
  - 🐛 FIX: gerenciar_premium aceita @username direto + lookup automático
  - ⚡ Cache de queries de busca por chat (search_cache) para paginação O(1)
  - 🛡️ Tratamento de erros aprimorado em todos os handlers
"""

import re
import json
import os
import asyncio
import tempfile
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.errors import (
    FloodWaitError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.contacts import ResolveUsernameRequest

# ══════════════════════════════════════════════
# ⚙️  CONFIGURAÇÕES
# ══════════════════════════════════════════════
API_ID      = 29214781
API_HASH    = "9fc77b4f32302f4d4081a4839cc7ae1f"
PHONE       = "+5588998225077"
BOT_TOKEN   = "8618840827:AAHohLnNTWh_lkP4l9du6KJTaRQcPsNrwV8"
OWNER_ID    = 2061557102

BOT_USERNAME = "InforUser_Bot"

FOLDER_PATH  = "data"
FILE_PATH    = os.path.join(FOLDER_PATH, "user_database.json")
LOG_PATH     = os.path.join(FOLDER_PATH, "monitor.log")
SESSION_USER = "session_monitor"
SESSION_BOT  = "session_bot"

ITEMS_PER_PAGE = 8
SCAN_INTERVAL  = 3600
MAX_HISTORY    = 50

BOT_SEARCH_PATTERN = re.compile(
    r'^@?' + re.escape(BOT_USERNAME) + r'\s+(.+)',
    re.IGNORECASE
)

PREMIUM_MODULES = {
    "phone_full":      "☎️ Telefone 100%",
    "pagination_full": "🗂 Paginação Completa",
    "bio":             "🖊 Bio",
    "groups_full":     "✅ Ver todos os grupos",
    "combo":           "📋 Gerar combo",
}

XTREAM_PATTERNS = [
    re.compile(r'https?://[^\s/]+(?::\d+)?/([A-Za-z0-9_\-\.]+)/([A-Za-z0-9_\-\.]+)'),
    re.compile(r'username=([^\s&"\']+)[&\s].*?password=([^\s&"\']+)'),
    re.compile(r'password=([^\s&"\']+)[&\s].*?username=([^\s&"\']+)'),
]

DEFAULT_HIDDEN = {"phone": False, "id": False, "username": False, "bio": False}

# ══════════════════════════════════════════════
# 📁  ARQUIVOS / BANCO
# ══════════════════════════════════════════════
os.makedirs(FOLDER_PATH, exist_ok=True)

def _ensure_files():
    if not os.path.exists(FILE_PATH):
        default_db = {"_settings": {"free_combo_limit": 100, "premium_combo_limit": 500}}
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_db, f, indent=2, ensure_ascii=False)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] Log iniciado\n")

_ensure_files()

def carregar_dados() -> dict:
    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            db = json.load(f)
    except (json.JSONDecodeError, IOError):
        db = {}
    if "_settings" not in db:
        db["_settings"] = {"free_combo_limit": 100, "premium_combo_limit": 500}
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
    for k, v in db.items():
        if not k.startswith("_"):
            yield k, v

def _agora_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def _ensure_user_shape(entry: dict):
    """Garante que um registro tem todos os campos esperados."""
    entry.setdefault("hidden_info", dict(DEFAULT_HIDDEN))
    entry.setdefault("premium", {"active": False, "modules": []})
    entry.setdefault("custom_combo_limits", {})
    entry.setdefault("historico", [])
    entry.setdefault("grupos", [])
    entry.setdefault("bio", "")
    entry.setdefault("phone", "")
    entry.setdefault("fotos", False)
    entry.setdefault("restricoes", "Nenhuma")
    entry.setdefault("nome_atual", "Sem nome")
    entry.setdefault("username_atual", "Nenhum")
    entry.setdefault("fonte", "Manual")

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
    settings       = db.get("_settings", {})
    global_free    = settings.get("free_combo_limit",    100)
    global_premium = settings.get("premium_combo_limit", 500)
    user_limits    = db.get(uid, {}).get("custom_combo_limits", {}) if uid in db else {}
    return (
        user_limits.get("free",    global_free),
        user_limits.get("premium", global_premium),
    )

# ══════════════════════════════════════════════
# 📱  CENSURA TELEFONE
# ══════════════════════════════════════════════
def censurar_telefone(phone: str) -> str:
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

# ══════════════════════════════════════════════
# 🤖  CLIENTES
# ══════════════════════════════════════════════
user_client = TelegramClient(SESSION_USER, API_ID, API_HASH)
bot         = TelegramClient(SESSION_BOT,  API_ID, API_HASH)

scan_running = False
scan_stats   = {"last_scan": None, "users_scanned": 0,
                "groups_scanned": 0, "changes_detected": 0}

pending_states: dict = {}
pending_module_sel: dict = {}

# Cache de buscas por chat: { chat_id: {"query": str, "results_ids": [uid,...],
#                                       "username_only": bool, "ts": float} }
# Permite paginação O(1) sem refazer a busca toda vez que o usuário clica ◀️ ▶️
search_cache: dict = {}

# ══════════════════════════════════════════════
# 🔔  NOTIFICAÇÃO
# ══════════════════════════════════════════════
async def notificar(texto: str):
    try:
        await bot.send_message(OWNER_ID, texto, parse_mode='md')
    except Exception as e:
        log(f"Erro notificação: {e}")

# ══════════════════════════════════════════════
# 📜  HISTÓRICO GENÉRICO (nome, username, bio, phone)
# ══════════════════════════════════════════════
def _push_historico(entry: dict, tipo: str, de: str, para: str, grupo: str = "DM"):
    """Adiciona entrada de histórico se houve mudança real."""
    if (de or "") == (para or ""):
        return False
    entry.setdefault("historico", []).append({
        "data":  _agora_str(),
        "tipo":  tipo,
        "de":    de or "—",
        "para":  para or "—",
        "grupo": grupo,
    })
    if len(entry["historico"]) > MAX_HISTORY:
        entry["historico"] = entry["historico"][-MAX_HISTORY:]
    return True

def _aplicar_atualizacao_campos(entry: dict, *, nome=None, username=None,
                                bio=None, phone=None, grupo="DM",
                                notify=True) -> list:
    """Atualiza campos rastreáveis, registra histórico e devolve lista de mudanças."""
    mudancas = []
    if nome is not None and entry.get("nome_atual") != nome:
        if _push_historico(entry, "NOME", entry.get("nome_atual", ""), nome, grupo):
            mudancas.append(("NOME", entry.get("nome_atual", ""), nome))
        entry["nome_atual"] = nome
    if username is not None and entry.get("username_atual") != username:
        if _push_historico(entry, "USER", entry.get("username_atual", ""), username, grupo):
            mudancas.append(("USER", entry.get("username_atual", ""), username))
        entry["username_atual"] = username
    if bio is not None and entry.get("bio", "") != bio:
        if _push_historico(entry, "BIO", entry.get("bio", ""), bio, grupo):
            mudancas.append(("BIO", entry.get("bio", ""), bio))
        entry["bio"] = bio
    if phone is not None and entry.get("phone", "") != phone:
        if _push_historico(entry, "PHONE", entry.get("phone", ""), phone, grupo):
            mudancas.append(("PHONE", entry.get("phone", ""), phone))
        entry["phone"] = phone
    return mudancas

# ══════════════════════════════════════════════
# 💾  PERFIL COMPLETO
# ══════════════════════════════════════════════
async def obter_perfil_completo(client: TelegramClient, user_id) -> dict:
    extras = {"bio": "", "phone": "", "fotos": False, "restricoes": "Nenhuma"}
    try:
        full = await client(GetFullUserRequest(user_id))
        extras["bio"]   = full.full_user.about or ""
        extras["fotos"] = full.full_user.profile_photo is not None
        raw_user = full.users[0] if full.users else None
        if raw_user:
            extras["phone"]      = getattr(raw_user, 'phone', '') or ""
            extras["restricoes"] = str(getattr(raw_user, 'restriction_reason', '') or "Nenhuma")
    except Exception as e:
        log(f"⚠️ Perfil completo indisponível para {user_id}: {e}")
    return extras

# ══════════════════════════════════════════════
# 🔎  RESOLUÇÃO VIA USERBOT (busca externa)
# ══════════════════════════════════════════════
async def resolver_usuario_externo(query: str):
    """
    Tenta resolver um username/ID via userbot e retorna um objeto User do Telethon
    ou None. Aceita @username, username puro ou ID numérico.
    """
    q = query.strip().lstrip('@')
    try:
        if q.isdigit():
            return await user_client.get_entity(int(q))
        # tenta resolve por username
        try:
            res = await user_client(ResolveUsernameRequest(q))
            if res and res.users:
                return res.users[0]
        except (UsernameNotOccupiedError, UsernameInvalidError):
            return None
        # fallback genérico
        return await user_client.get_entity(q)
    except Exception as e:
        log(f"⚠️ resolver_usuario_externo({query}): {e}")
        return None

async def upsert_usuario_externo(query: str, fonte: str = "Lookup") -> tuple:
    """
    Garante que um usuário exista no banco. Retorna (uid_str, dados, criado_bool).
    Se o ID já existir mas o username mudou, registra histórico do username antigo.
    """
    db   = carregar_dados()
    user = await resolver_usuario_externo(query)
    if not user:
        return None, None, False

    uid        = str(user.id)
    nome_atual = (f"{getattr(user,'first_name','') or ''} "
                  f"{getattr(user,'last_name','') or ''}").strip() or "Sem nome"
    user_atual = f"@{user.username}" if getattr(user, 'username', None) else "Nenhum"
    extras     = await obter_perfil_completo(user_client, user.id)

    criado = False
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
            "fonte":             fonte,
            "primeiro_registro": _agora_str(),
            "historico":         [],
            "hidden_info":       dict(DEFAULT_HIDDEN),
            "premium":           {"active": False, "modules": []},
            "custom_combo_limits": {},
        }
        criado = True
        log(f"➕ Upsert externo: {nome_atual} ({uid}) via '{query}'")
    else:
        _ensure_user_shape(db[uid])
        mud = _aplicar_atualizacao_campos(
            db[uid],
            nome=nome_atual,
            username=user_atual,
            bio=extras["bio"],
            phone=extras["phone"],
            grupo=fonte,
        )
        # restrições/fotos são metadados, não viram histórico
        db[uid]["fotos"]      = extras["fotos"]
        db[uid]["restricoes"] = extras["restricoes"]
        if mud:
            log(f"🔄 Atualização via lookup ({uid}): {[m[0] for m in mud]}")

    salvar_dados(db)
    return uid, db[uid], criado

# ══════════════════════════════════════════════
# 💬  SALVAR USUÁRIO (DM)
# ══════════════════════════════════════════════
async def salvar_usuario_dm(user) -> None:
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
            "primeiro_registro": _agora_str(),
            "historico":         [],
            "hidden_info":       dict(DEFAULT_HIDDEN),
            "premium":           {"active": False, "modules": []},
            "custom_combo_limits": {},
        }
        salvar_dados(db)
        log(f"💬 Novo via DM: {nome_atual} ({uid})")
        await notificar(
            f"💬 **NOVO USUÁRIO (DM)**\n👤 `{nome_atual}`\n🆔 `{uid}`\n{user_atual}"
        )
        return

    _ensure_user_shape(db[uid])
    mud = _aplicar_atualizacao_campos(
        db[uid],
        nome=nome_atual,
        username=user_atual,
        bio=extras["bio"],
        phone=extras["phone"],
        grupo="DM",
    )
    db[uid]["fotos"]      = extras["fotos"]
    db[uid]["restricoes"] = extras["restricoes"]
    salvar_dados(db)
    for tipo, de, para in mud:
        await notificar(f"🔔 **MUDANÇA {tipo} (DM)**\n`{de}` ➜ `{para}`")

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
    sel  = pending_module_sel.get(chat_id, {}).get("modules", set())
    rows = []
    for mod_key, mod_label in PREMIUM_MODULES.items():
        mark   = "✅" if mod_key in sel else "⬜"
        label  = f"{mark} {mod_label}"
        # callback: tmod|<uid>|<mod_key>  (delimitador seguro, nada de _ ambíguo)
        cb     = f"tmod|{target_uid}|{mod_key}".encode()
        rows.append([Button.inline(label, cb)])
    rows.append([
        Button.inline("✔️ Confirmar",  f"cprem|{target_uid}".encode()),
        Button.inline("❌ Cancelar",   b"cmd_premium_menu"),
    ])
    return rows

def perfil_link_buttons(dados: dict) -> list:
    """
    Botões de acesso ao perfil. ATENÇÃO: Telegram NÃO permite Button.url com
    esquema tg:// — gera erro "BUTTON_URL_INVALID". Usamos apenas https://t.me/
    para usuários com @username público. O link tg:// já fica clicável dentro
    da mensagem (formatar_perfil) graças ao parse_mode='md'.
    """
    rows = []
    user = (dados.get("username_atual") or "").lstrip("@")
    if user and user.lower() != "nenhum":
        rows.append([Button.url("🔗 Abrir no Telegram", f"https://t.me/{user}")])
    return rows

# ══════════════════════════════════════════════
# 🔍  BUSCA
# ══════════════════════════════════════════════
def buscar_usuario(query: str, username_only: bool = False) -> list:
    db          = carregar_dados()
    query_lower = query.lower().lstrip('@')
    results     = []

    for uid, dados in iter_usuarios(db):
        username = (dados.get("username_atual", "") or "").lower().lstrip('@')

        if username_only:
            if username and query_lower == username:
                results.insert(0, dados)
            elif username and query_lower in username:
                results.append(dados)
            # também procura nos históricos de USER
            else:
                for h in dados.get("historico", []):
                    if h.get("tipo") == "USER":
                        old = (h.get("de", "") or "").lower().lstrip('@')
                        new = (h.get("para", "") or "").lower().lstrip('@')
                        if query_lower == old or query_lower == new:
                            results.append(dados)
                            break
            continue

        if query == uid:
            results.insert(0, dados)
            continue
        if username and query_lower == username:
            results.insert(0, dados)
            continue
        nome = (dados.get("nome_atual", "") or "").lower()
        if query_lower in nome or (username and query_lower in username):
            results.append(dados)
            continue
        # também procura username em histórico
        for h in dados.get("historico", []):
            if h.get("tipo") == "USER":
                old = (h.get("de", "") or "").lower().lstrip('@')
                new = (h.get("para", "") or "").lower().lstrip('@')
                if query_lower in old or query_lower in new:
                    results.append(dados)
                    break

    seen = set()
    unique = []
    for r in results:
        rid = r.get("id")
        if rid not in seen:
            seen.add(rid)
            unique.append(r)
    return unique

async def buscar_com_lookup(query: str, fonte: str = "Lookup") -> list:
    """
    Busca no banco; se vazio, tenta resolver via userbot e atualiza/cria registro.
    Caso o ID resolvido já esteja no banco com username diferente, o histórico
    de usernames é atualizado automaticamente em upsert_usuario_externo.
    """
    results = buscar_usuario(query)
    if results:
        # Se encontramos por username/nome, ainda assim podemos validar com o ID
        # da primeira entrada para garantir que username em uso está atual.
        return results

    uid, dados, _ = await upsert_usuario_externo(query, fonte=fonte)
    if dados:
        return [dados]
    return []

# ══════════════════════════════════════════════
# 📋  FORMATAR PERFIL
# ══════════════════════════════════════════════
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

    if is_field_hidden(dados, "id") and not owner:
        id_text = "🔒 _Oculto_"
    else:
        id_text = f"`{uid}`"
        if owner and is_field_hidden(dados, "id"):
            id_text += " _(oculto para outros)_"

    if is_field_hidden(dados, "username") and not owner:
        username_text = "🔒 _Oculto_"
    else:
        username_text = f"`{username}`"
        if owner and is_field_hidden(dados, "username"):
            username_text += " _(oculto para outros)_"

    bio_raw = dados.get("bio", "")
    if is_field_hidden(dados, "bio") and not owner:
        bio_text = "🔒 _Oculto_"
    elif has_module(db, viewer_str, "bio") or owner:
        bio_text = f"`{bio_raw[:120]}`" if bio_raw else "_Nenhuma_"
        if owner and is_field_hidden(dados, "bio"):
            bio_text += " _(oculto para outros)_"
    else:
        bio_text = f"`{bio_raw[:120]}`" if bio_raw else "_Nenhuma_"

    phone_text = exibir_telefone(dados, viewer_id, db)

    grupos = dados.get("grupos", [])
    if owner or has_module(db, viewer_str, "groups_full"):
        g_show, g_extra = grupos, ""
    else:
        max_g  = max(1, len(grupos) // 5) if grupos else 0
        g_show = grupos[:max_g]
        g_extra = f" _(+{len(grupos)-max_g} ocultos — Premium)_" if len(grupos) > max_g else ""
    grupos_text = ", ".join(g_show[:8]) or "N/A"
    if len(g_show) > 8:
        grupos_text += f" (+{len(g_show)-8})"
    grupos_text += g_extra

    total_ch = len(historico)
    recent   = historico[-5:]
    hist_emoji = {"NOME": "📛", "USER": "🆔", "BIO": "📝", "PHONE": "📱"}
    hist_text = ""
    for h in reversed(recent):
        emoji = hist_emoji.get(h.get("tipo"), "🔄")
        hist_text += f"  {emoji} `{h['data']}` — {h['de']} ➜ {h['para']}\n"
    if not hist_text:
        hist_text = "  _Nenhuma alteração registrada_\n"

    first_seen  = historico[0]["data"]  if historico else "N/A"
    last_change = historico[-1]["data"] if historico else "N/A"

    is_prem  = is_premium_user(db, uid_str)
    prem_tag = " ⭐ **PREMIUM**" if (is_prem and owner) else ""

    # Link clicável para perfil (visível também na mensagem)
    user_clean = (username or "").lstrip("@")
    if user_clean and user_clean.lower() != "nenhum":
        link_md = f"[abrir](tg://user?id={uid}) • [t.me/{user_clean}](https://t.me/{user_clean})"
    else:
        link_md = f"[abrir](tg://user?id={uid})"

    return (
        f"╔══════════════════════════╗\n"
        f"║  🕵️ **PERFIL DO USUÁRIO**  ║\n"
        f"╚══════════════════════════╝{prem_tag}\n\n"
        f"👤 **Nome:** `{nome}`\n"
        f"🆔 **Username:** {username_text}\n"
        f"🔢 **ID:** {id_text}\n"
        f"🔗 **Acesso:** {link_md}\n"
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
                              page: int = 0, username_only: bool = False,
                              edit: bool = False):
    """
    Envia (ou edita) a mensagem com a lista de resultados de busca.
    Usa o cache `search_cache[chat_id]` para paginação O(1) — clicar ◀️ ▶️
    apenas troca a página sem refazer a busca.

    edit=True → tenta editar a mensagem atual (vindo do callback de paginação)
    """
    owner      = is_owner(viewer_id)
    viewer_str = str(viewer_id)
    prem       = is_premium_user(db, viewer_str) or owner
    chat_id    = event.chat_id

    async def _send(txt, btns):
        if edit:
            try:
                msg = await event.get_message()
                await msg.edit(txt, parse_mode='md', buttons=btns, link_preview=False)
                return
            except Exception:
                pass  # cai para reply
        await event.reply(txt, parse_mode='md', buttons=btns, link_preview=False)

    if not results:
        tip = "(busca por username)" if username_only else ""
        await _send(
            f"❌ **Nenhum resultado para** `{query}` {tip}\n\n"
            f"💡 Tente ID numérico, @username ou nome parcial.",
            voltar_button()
        )
        return

    if len(results) == 1:
        dados = results[0]
        await _send(
            formatar_perfil(dados, viewer_id, db),
            [
                *perfil_link_buttons(dados),
                [Button.inline("📜 Histórico", f"hist_{dados['id']}_page_0".encode())],
                *voltar_button()
            ]
        )
        return

    total_full = len(results)
    if (prem and has_module(db, viewer_str, "pagination_full")) or owner:
        ipp         = ITEMS_PER_PAGE
        total       = total_full
        total_pages = max(1, (total + ipp - 1) // ipp)
    else:
        max_free    = max(1, total_full // 5)
        results     = results[:max_free]
        total       = len(results)
        ipp         = ITEMS_PER_PAGE
        total_pages = 1

    # Atualiza cache para próximas paginações
    search_cache[chat_id] = {
        "query":         query,
        "results_ids":   [str(r["id"]) for r in results],
        "username_only": username_only,
    }

    page  = max(0, min(page, total_pages - 1))
    start = page * ipp
    chunk = results[start:start + ipp]

    tag  = " _(username only)_" if username_only else ""
    text = f"🔍 **{total} resultado(s) para** `{query}`{tag}  —  pág. {page+1}/{total_pages}\n\n"
    btns = []
    for r in chunk:
        label = f"👤 {r.get('nome_atual','?')} | {r.get('username_atual','?')}"
        btns.append([Button.inline(label[:48], f"profile_{r['id']}".encode())])

    nav = []
    if page > 0:
        nav.append(Button.inline("◀️", f"searchpg_{page-1}".encode()))
    nav.append(Button.inline(f"📄 {page+1}/{total_pages}", b"noop"))
    if page < total_pages - 1:
        nav.append(Button.inline("▶️", f"searchpg_{page+1}".encode()))
    if len(nav) > 1:
        btns.append(nav)
    btns.append([Button.inline("🔙 Menu", b"cmd_menu")])

    if not prem and total < total_full:
        text += "⚠️ _Resultados limitados. Premium desbloqueia busca completa._\n\n"

    await _send(text, btns)

# ══════════════════════════════════════════════
# 📋  COMBO
# ══════════════════════════════════════════════
async def gerar_combo(limit: int) -> list:
    combos, seen = [], set()
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
    agora = _agora_str()
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
                            "hidden_info":       dict(DEFAULT_HIDDEN),
                            "premium":           {"active": False, "modules": []},
                            "custom_combo_limits": {},
                        }
                    else:
                        _ensure_user_shape(db[uid])
                        if nome_grupo not in db[uid].get("grupos", []):
                            db[uid].setdefault("grupos", []).append(nome_grupo)

                        mud = _aplicar_atualizacao_campos(
                            db[uid],
                            nome=nome_atual,
                            username=user_atual,
                            bio=extras["bio"],
                            phone=extras["phone"],
                            grupo=nome_grupo,
                        )
                        for tipo, de, para in mud:
                            scan_stats["changes_detected"] += 1
                            label = {"NOME": "🔔 NOME ALTERADO", "USER": "🆔 USERNAME ALTERADO",
                                     "BIO": "📝 BIO ALTERADA", "PHONE": "📱 TELEFONE ALTERADO"}.get(tipo, tipo)
                            await notificar(f"{label}\n`{de}` ➜ `{para}`\n📍 _{nome_grupo}_")

                        db[uid]["fotos"]      = extras["fotos"]
                        db[uid]["restricoes"] = extras["restricoes"]

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
# 🎮  COMANDOS
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(pattern='/start'))
async def cmd_start(event):
    if event.is_private:
        sender = await event.get_sender()
        asyncio.create_task(salvar_usuario_dm(sender))
    owner = is_owner(event.sender_id)
    await event.respond(
        f"╔══════════════════════════════╗\n"
        f"║  🕵️ **User Info Bot Pro v3.1**  ║\n"
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
    results = await buscar_com_lookup(query, fonte="Busca direta")
    db      = carregar_dados()  # recarrega caso lookup tenha alterado
    await _enviar_resultados(event, query, results, event.sender_id, db)

# ══════════════════════════════════════════════
# 🔘  CALLBACKS
# ══════════════════════════════════════════════
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data      = event.data.decode()
    chat_id   = event.chat_id
    sender_id = event.sender_id
    owner     = is_owner(sender_id)

    try:
        message = await event.get_message()

        if data == "cmd_menu":
            await message.edit(
                "🕵️ **User Info Bot Pro v3.1**\n\nSelecione uma opção:",
                parse_mode='md',
                buttons=menu_principal_buttons(owner)
            )

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

        # ── OCULTAR INFOR ──
        elif data == "cmd_ocultar_menu":
            if not owner:
                await event.answer("🚫 Restrito ao owner.", alert=True); return
            await message.edit(
                "🙈 **Ocultar Informações**\n\n"
                "Escolha qual campo ocultar ou revelar para um usuário.\n"
                "_O bot pedirá o ID ou @username do alvo._",
                parse_mode='md',
                buttons=[
                    [Button.inline("📵 Telefone",  b"ocultar_phone"),
                     Button.inline("🔒 ID",        b"ocultar_id")],
                    [Button.inline("👤 Username",  b"ocultar_username"),
                     Button.inline("📝 Bio",       b"ocultar_bio")],
                    [Button.inline("📋 Ver ocultações ativas", b"ocultar_list")],
                    [Button.inline("🔙 Menu Principal", b"cmd_menu")],
                ]
            )

        elif data in ("ocultar_phone", "ocultar_id", "ocultar_username", "ocultar_bio"):
            if not owner:
                await event.answer("🚫 Restrito ao owner.", alert=True); return
            field_map = {"ocultar_phone": "phone", "ocultar_id": "id",
                         "ocultar_username": "username", "ocultar_bio": "bio"}
            field = field_map[data]
            pending_states[chat_id] = {"action": "toggle_hide", "data": {"field": field}}
            await message.edit(
                f"🙈 **Ocultar/Revelar campo:** `{field}`\n\n"
                f"Envie o **ID numérico** ou **@username** do usuário alvo:",
                parse_mode='md', buttons=[[Button.inline("❌ Cancelar", b"cmd_ocultar_menu")]]
            )

        elif data == "ocultar_list":
            if not owner:
                await event.answer("🚫", alert=True); return
            db   = carregar_dados()
            text = "📋 **Campos ocultos ativos:**\n\n"
            found = False
            for uid, dados in iter_usuarios(db):
                hi = dados.get("hidden_info", {})
                ocultos = [k for k, v in hi.items() if v]
                if ocultos:
                    found = True
                    text += f"👤 `{dados['nome_atual']}` (`{uid}`)\n   🔒 {', '.join(ocultos)}\n\n"
            if not found:
                text += "_Nenhum campo oculto no momento._"
            await message.edit(text, parse_mode='md',
                               buttons=[[Button.inline("🔙 Ocultar infor", b"cmd_ocultar_menu")]])

        # ── PREMIUM ──
        elif data == "cmd_premium_menu":
            if not owner:
                await event.answer("🚫 Restrito ao owner.", alert=True); return
            await message.edit(
                "⭐ **Gerenciar Premium**\n\n"
                "Adicione ou remova o status premium e escolha módulos.",
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
                await event.answer("🚫", alert=True); return
            pending_states[chat_id] = {"action": "add_premium", "data": {}}
            await message.edit(
                "➕ **Adicionar Premium**\n\n"
                "Envie o **ID** ou **@username** do usuário.\n"
                "_Se não estiver no banco, será buscado automaticamente._",
                parse_mode='md',
                buttons=[[Button.inline("❌ Cancelar", b"cmd_premium_menu")]]
            )

        elif data == "premium_remove":
            if not owner:
                await event.answer("🚫", alert=True); return
            pending_states[chat_id] = {"action": "remove_premium", "data": {}}
            await message.edit(
                "➖ **Remover Premium**\n\n"
                "Envie o **ID** ou **@username** do usuário:",
                parse_mode='md',
                buttons=[[Button.inline("❌ Cancelar", b"cmd_premium_menu")]]
            )

        elif data == "premium_list":
            if not owner:
                await event.answer("🚫", alert=True); return
            db   = carregar_dados()
            text = "⭐ **Usuários Premium:**\n\n"
            found = False
            for uid, dados in iter_usuarios(db):
                prem = dados.get("premium", {})
                if prem.get("active"):
                    found = True
                    modules = prem.get("modules", [])
                    mods = ", ".join(PREMIUM_MODULES.get(m, m) for m in modules) or "Nenhum"
                    text += f"👤 `{dados['nome_atual']}` (`{uid}`)\n📦 {mods}\n\n"
            if not found:
                text += "_Nenhum usuário premium cadastrado._"
            await message.edit(text, parse_mode='md',
                               buttons=[[Button.inline("🔙 Premium", b"cmd_premium_menu")]])

        # ── Toggle módulo (novo formato: tmod|<uid>|<mod>) ──
        elif data.startswith("tmod|"):
            if not owner:
                await event.answer("🚫", alert=True); return
            try:
                _, target_uid, module = data.split("|", 2)
            except ValueError:
                await event.answer("⚠️ Callback inválido.", alert=True); return

            if chat_id not in pending_module_sel:
                pending_module_sel[chat_id] = {"target_uid": target_uid, "modules": set()}
            # se mudou de target (clicou em outro fluxo), reseta
            if pending_module_sel[chat_id].get("target_uid") != target_uid:
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

        # ── Confirmar premium (novo formato: cprem|<uid>) ──
        elif data.startswith("cprem|"):
            if not owner:
                await event.answer("🚫", alert=True); return
            try:
                _, target_uid = data.split("|", 1)
            except ValueError:
                await event.answer("⚠️ Callback inválido.", alert=True); return

            db = carregar_dados()
            if target_uid not in db:
                # tenta resolver via userbot
                await event.answer("🔎 Buscando usuário...")
                uid_res, _, _ = await upsert_usuario_externo(target_uid, fonte="Premium")
                db = carregar_dados()
                if not uid_res or uid_res not in db:
                    await event.answer("❌ Usuário não encontrado.", alert=True); return
                target_uid = uid_res

            sel = pending_module_sel.pop(chat_id, {}).get("modules", set())
            _ensure_user_shape(db[target_uid])
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

        # ── COMBO CONFIG ──
        elif data == "cmd_combo_config":
            if not owner:
                await event.answer("🚫", alert=True); return
            db       = carregar_dados()
            settings = db.get("_settings", {})
            await message.edit(
                f"🎛️ **Configuração de Combo**\n\n"
                f"📊 **Limites globais atuais:**\n"
                f"├ Free: **{settings.get('free_combo_limit', 100)}** combos\n"
                f"└ Premium: **{settings.get('premium_combo_limit', 500)}** combos\n\n"
                f"Para alterar:\n"
                f"`/setcombo <uid> <free_limit> <premium_limit>`\n"
                f"`/setcombo global <free_limit> <premium_limit>`",
                parse_mode='md',
                buttons=voltar_button()
            )

        # ── STATS ──
        elif data == "cmd_stats":
            db = carregar_dados()
            total = sum(1 for _ in iter_usuarios(db))
            prem  = sum(1 for _, d in iter_usuarios(db) if d.get("premium", {}).get("active"))
            chg   = sum(len(d.get("historico", [])) for _, d in iter_usuarios(db))
            await message.edit(
                f"📊 **Estatísticas**\n\n"
                f"👥 Usuários: **{total}**\n"
                f"⭐ Premium: **{prem}**\n"
                f"🔄 Alterações totais: **{chg}**\n"
                f"🕐 Última varredura: `{scan_stats.get('last_scan') or 'N/A'}`",
                parse_mode='md', buttons=voltar_button()
            )

        elif data == "cmd_about":
            await message.edit(
                "ℹ️ **User Info Bot Pro v3.1**\n\n"
                "Monitor profissional Telegram.\n"
                "Busca por ID/username/nome, histórico completo,\n"
                "premium granular, geração de combo Xtream.\n\n"
                "👨‍💻 _Créditos: Edivaldo Silva @Edkd1_",
                parse_mode='md', buttons=voltar_button()
            )

        elif data == "cmd_config":
            await message.edit(
                "⚙️ **Configurações**\n\n_Em breve mais opções._",
                parse_mode='md', buttons=voltar_button()
            )

        elif data == "cmd_recent":
            db = carregar_dados()
            ultimos = []
            for uid, d in iter_usuarios(db):
                for h in d.get("historico", []):
                    ultimos.append((h.get("data"), d.get("nome_atual"), uid, h))
            ultimos.sort(key=lambda x: x[0] or "", reverse=True)
            ultimos = ultimos[:20]
            text = "📋 **Últimas alterações:**\n\n"
            emoji_map = {"NOME": "📛", "USER": "🆔", "BIO": "📝", "PHONE": "📱"}
            for data_, nome, uid, h in ultimos:
                em = emoji_map.get(h.get("tipo"), "🔄")
                text += f"{em} `{data_}` — {nome} (`{uid}`)\n  {h['de']} ➜ {h['para']}\n\n"
            if not ultimos:
                text += "_Sem alterações registradas._"
            await message.edit(text, parse_mode='md', buttons=voltar_button())

        elif data == "cmd_scan":
            if not owner:
                await event.answer("🚫", alert=True); return
            await event.answer("🔄 Iniciando varredura...")
            asyncio.create_task(executar_varredura(notify_chat=chat_id))

        elif data == "cmd_export":
            if not owner:
                await event.answer("🚫", alert=True); return
            await bot.send_file(chat_id, FILE_PATH, caption="📤 Banco exportado.")
            await event.answer()

        # ── Paginação de busca (cache por chat_id) ──
        elif data.startswith("searchpg_"):
            try:
                page = int(data.split("_", 1)[1])
            except (ValueError, IndexError):
                await event.answer("⚠️ Página inválida.", alert=True); return

            cache = search_cache.get(chat_id)
            if not cache:
                await event.answer(
                    "⚠️ Cache de busca expirou. Faça uma nova busca.",
                    alert=True
                )
                return

            db_local = carregar_dados()
            results  = []
            for uid_c in cache["results_ids"]:
                if uid_c in db_local:
                    results.append(db_local[uid_c])

            await _enviar_resultados(
                event, cache["query"], results, sender_id, db_local,
                page=page, username_only=cache.get("username_only", False),
                edit=True
            )

        # ── Profile / Histórico ──
        elif data.startswith("profile_"):
            uid = data[len("profile_"):]
            db  = carregar_dados()
            if uid not in db:
                await event.answer("❌ Usuário sumiu do banco.", alert=True); return
            await message.edit(
                formatar_perfil(db[uid], sender_id, db),
                parse_mode='md',
                link_preview=False,
                buttons=[
                    *perfil_link_buttons(db[uid]),
                    [Button.inline("📜 Histórico", f"hist_{uid}_page_0".encode())],
                    *voltar_button()
                ]
            )

        elif data.startswith("hist_"):
            # Formato canônico: hist_<uid>_page_<n>
            # Aceita também hist_<uid>_<n> (compatibilidade)
            rest = data[len("hist_"):]
            try:
                if "_page_" in rest:
                    uid, page_s = rest.rsplit("_page_", 1)
                    page = int(page_s)
                else:
                    uid, page_s = rest.rsplit("_", 1)
                    page = int(page_s)
            except (ValueError, IndexError):
                await event.answer("⚠️ Histórico inválido.", alert=True); return

            db = carregar_dados()
            if uid not in db:
                await event.answer("❌ Sem dados.", alert=True); return

            viewer_str = str(sender_id)
            prem      = is_premium_user(db, viewer_str) or owner
            dados     = db[uid]
            historico = list(reversed(dados.get("historico", [])))

            if not prem:
                max_items = max(1, len(historico) // 5)
                historico = historico[:max_items]

            total       = len(historico)
            total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            page        = max(0, min(page, total_pages - 1))
            chunk       = historico[page * ITEMS_PER_PAGE:(page + 1) * ITEMS_PER_PAGE]

            text = (f"📜 **Histórico de** `{dados['nome_atual']}`\n"
                    f"ID: `{uid}` — pág. {page+1}/{total_pages}\n\n")

            emoji_map = {"NOME": "📛", "USER": "🆔", "BIO": "📝", "PHONE": "📱"}
            for h in chunk:
                em = emoji_map.get(h.get("tipo"), "🔄")
                text += f"{em} `{h['data']}`\n  {h['de']} ➜ {h['para']}\n  📍 _{h.get('grupo','N/A')}_\n\n"
            if not chunk:
                text += "_Sem registros._"
            if not prem:
                text += "⚠️ _Histórico limitado (Free)._"

            await message.edit(text, parse_mode='md',
                               buttons=paginar_buttons(f"hist_{uid}", page, total_pages))

        # ── COMBO ──
        elif data.startswith("combo_"):
            viewer_str = str(sender_id)
            db = carregar_dados()
            can_combo = (owner or
                         (is_premium_user(db, viewer_str) and has_module(db, viewer_str, "combo")))
            if not can_combo:
                await event.answer("🚫 Recurso exclusivo Premium.", alert=True); return
            free_lim, prem_lim = get_combo_limits(db, viewer_str)
            limit = prem_lim if (is_premium_user(db, viewer_str) or owner) else free_lim
            await event.answer(f"📋 Gerando até {limit} combos...")
            msg_temp = await bot.send_message(
                chat_id,
                f"⏳ **Gerando combo...**\nLimite: **{limit}**", parse_mode='md')
            combos = await gerar_combo(limit)
            if not combos:
                await msg_temp.edit("❌ **Nenhum combo encontrado.**", parse_mode='md'); return
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                             delete=False, encoding='utf-8') as f:
                f.write(f"# Combo gerado por @{BOT_USERNAME}\n")
                f.write(f"# Total: {len(combos)} | {datetime.now()}\n\n")
                f.write("\n".join(combos))
                tmp_path = f.name
            await bot.send_file(chat_id, tmp_path,
                                caption=f"📋 **{len(combos)} combos gerados!**\n_@Edkd1_",
                                parse_mode='md')
            os.unlink(tmp_path)
            await msg_temp.delete()

        elif data == "noop":
            await event.answer()
        else:
            log(f"⚠️ Callback não roteado: {data!r}")
            await event.answer("⚠️ Ação não reconhecida.", alert=True)

        # NÃO chamamos event.answer() de novo aqui — cada branch já é responsável
        # por responder. Chamadas duplicadas geram warnings na API do Telegram.

    except Exception as e:
        log(f"❌ Callback [{data}]: {type(e).__name__}: {e}")
        try:
            await event.answer("❌ Erro interno. Veja os logs.", alert=True)
        except Exception:
            pass

# ══════════════════════════════════════════════
# 💬  TEXTO LIVRE
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(func=lambda e: e.is_private and not (e.text or '').startswith('/')))
async def text_handler(event):
    chat_id   = event.chat_id
    sender_id = event.sender_id
    owner     = is_owner(sender_id)
    text      = (event.text or "").strip()
    db        = carregar_dados()

    sender = await event.get_sender()
    asyncio.create_task(salvar_usuario_dm(sender))

    bot_match = BOT_SEARCH_PATTERN.match(text)
    if bot_match:
        query = bot_match.group(1).strip()
        # Conforme solicitado: PRIMEIRO busca no banco (username_only=True),
        # só faz lookup externo se o banco não tem nada.
        results = buscar_usuario(query, username_only=True)
        if not results:
            results = await buscar_com_lookup(query, fonte="Bot+termo")
        db = carregar_dados()
        await _enviar_resultados(event, query, results, sender_id, db, username_only=True)
        return

    state = pending_states.get(chat_id)

    # ── toggle_hide ──
    if state and state["action"] == "toggle_hide":
        del pending_states[chat_id]
        field = state["data"]["field"]
        results = await buscar_com_lookup(text, fonte="Ocultar")
        if not results:
            await event.reply(f"❌ Usuário `{text}` não encontrado.",
                              parse_mode='md',
                              buttons=[[Button.inline("🔙 Ocultar infor", b"cmd_ocultar_menu")]])
            return
        target  = results[0]
        uid_str = str(target["id"])
        db = carregar_dados()
        _ensure_user_shape(db[uid_str])
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

    # ── add_premium ──
    if state and state["action"] == "add_premium":
        del pending_states[chat_id]
        wait_msg = await event.reply("🔎 Procurando usuário...", parse_mode='md')
        results = await buscar_com_lookup(text, fonte="Premium")
        if not results:
            await wait_msg.edit(
                f"❌ `{text}` não encontrado nem via lookup.\n"
                f"Verifique o ID/username e tente novamente.",
                parse_mode='md',
                buttons=[[Button.inline("🔙 Premium", b"cmd_premium_menu")]]
            )
            return
        target     = results[0]
        target_uid = str(target["id"])
        pending_module_sel[chat_id] = {"target_uid": target_uid, "modules": set()}
        await wait_msg.edit(
            f"⭐ **Selecionar módulos para:**\n"
            f"👤 `{target['nome_atual']}` (`{target_uid}`)\n"
            f"{target.get('username_atual','Nenhum')}\n\n"
            f"Marque os módulos desejados e confirme:",
            parse_mode='md',
            buttons=module_selection_buttons(chat_id, target_uid)
        )
        return

    # ── remove_premium ──
    if state and state["action"] == "remove_premium":
        del pending_states[chat_id]
        results = await buscar_com_lookup(text, fonte="Premium")
        if not results:
            await event.reply(f"❌ `{text}` não encontrado.", parse_mode='md',
                              buttons=[[Button.inline("🔙 Premium", b"cmd_premium_menu")]])
            return
        target     = results[0]
        target_uid = str(target["id"])
        db = carregar_dados()
        _ensure_user_shape(db[target_uid])
        db[target_uid]["premium"] = {"active": False, "modules": []}
        salvar_dados(db)
        await event.reply(
            f"✅ **Premium removido de:**\n👤 `{target['nome_atual']}` (`{target_uid}`)",
            parse_mode='md',
            buttons=[[Button.inline("🔙 Premium", b"cmd_premium_menu")]]
        )
        log(f"⭐ Premium removido: {target_uid}")
        return

    # ── busca genérica ──
    if state and state["action"] == "search":
        del pending_states[chat_id]
        results = await buscar_com_lookup(text, fonte="Busca")
        db = carregar_dados()
        await _enviar_resultados(event, text, results, sender_id, db)
        return

    await event.reply(
        f"💡 Use /start para abrir o menu.\n"
        f"Busca rápida: `@{BOT_USERNAME} @username`",
        parse_mode='md',
        buttons=menu_principal_buttons(owner)
    )

# ══════════════════════════════════════════════
# 💬  HANDLER GRUPOS (BotName + termo)
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(func=lambda e: not e.is_private))
async def group_handler(event):
    text = (event.text or "").strip()
    bot_match = BOT_SEARCH_PATTERN.match(text)
    if not bot_match:
        return
    query = bot_match.group(1).strip()
    # Banco primeiro, lookup externo só se não houver nada
    results = buscar_usuario(query, username_only=True)
    if not results:
        results = await buscar_com_lookup(query, fonte="Grupo")
    db = carregar_dados()
    await _enviar_resultados(event, query, results, event.sender_id, db, username_only=True)

# ══════════════════════════════════════════════
# 🎛️  /setcombo
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(pattern=r'/setcombo\s+(.+)'))
async def cmd_setcombo(event):
    if not is_owner(event.sender_id):
        await event.reply("🚫 Restrito ao owner."); return
    args = event.pattern_match.group(1).strip().split()
    if len(args) != 3:
        await event.reply("Uso: `/setcombo <uid|global> <free_limit> <premium_limit>`",
                          parse_mode='md'); return
    target, free_s, prem_s = args
    try:
        free_lim, prem_lim = int(free_s), int(prem_s)
    except ValueError:
        await event.reply("❌ Limites devem ser números inteiros."); return

    db = carregar_dados()
    if target.lower() == "global":
        db["_settings"]["free_combo_limit"]    = free_lim
        db["_settings"]["premium_combo_limit"] = prem_lim
        salvar_dados(db)
        await event.reply(
            f"✅ **Limites globais atualizados:**\nFree: `{free_lim}` | Premium: `{prem_lim}`",
            parse_mode='md')
    elif target in db:
        db[target].setdefault("custom_combo_limits", {})
        db[target]["custom_combo_limits"]["free"]    = free_lim
        db[target]["custom_combo_limits"]["premium"] = prem_lim
        salvar_dados(db)
        await event.reply(
            f"✅ **Limites para** `{db[target]['nome_atual']}`:\n"
            f"Free: `{free_lim}` | Premium: `{prem_lim}`", parse_mode='md')
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
