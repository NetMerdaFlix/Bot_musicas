# user_info_bot_v7.py
"""
🕵️ User Info Bot Pro v7.0 — Telethon Edition (Multi-Language + Combo Free)
Créditos: Edivaldo Silva @Edkd1

Novidades v7.0 (sobre a v6.0 — 100% das funcionalidades preservadas):
  - 🔢 Inline `@InforUser_Bot <ID>` agora busca SOMENTE por ID numérico
       do usuário alvo (a busca por username via inline foi removida —
       evita o conflito com o próprio @username do bot).
  - 🔍 Busca direta por NOME passa a ser exclusiva PREMIUM (ID e
       @username continuam livres para qualquer usuário).
  - 📋 Geração de combo agora é liberada para TODOS os usuários
       (Free e Premium). Free recebe no mínimo 200 linhas
       `usuario:senha` por combo (default global ajustável).
  - 🎛️ Owner pode alterar o limite de combo de qualquer usuário
       por **ID** ou **@username** via `/setcombo` — também via
       botões inline na seção "🎛️ Config. Combo".
  - 🔘 Todos os botões e ações continuam via inline com paginação
       completa (◀️ Avançar | ❌ Cancelar | ✔️ Confirmar | etc.).
  - 🌐 Sistema de idiomas dinâmico preservado (PT-BR | EN | ES) com
       lang.json gerado/lido automaticamente na mesma pasta do bot.
  - ✅ 100% das funcionalidades v6.0 preservadas (busca, premium,
       ocultar, varredura, paginação, histórico, lookup externo).
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
# lang.json fica na MESMA pasta do bot (não dentro de /data) — requisito v6
LANG_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang.json")
SESSION_USER = "session_monitor"
SESSION_BOT  = "session_bot"

ITEMS_PER_PAGE = 8
SCAN_INTERVAL  = 3600
MAX_HISTORY    = 50

# v7: a consulta inline `@InforUser_Bot <termo>` agora aceita SOMENTE ID numérico
# do usuário alvo. Isso elimina o conflito de "@bot @username" que falhava no
# Telegram. Para username, use o botão "🔍 Buscar Usuário" do menu inline.
BOT_SEARCH_PATTERN = re.compile(
    r'^@?' + re.escape(BOT_USERNAME) + r'\s+(\d{4,})\s*$',
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
# 🌐  SISTEMA DE IDIOMAS (i18n)  — v6.0
# ══════════════════════════════════════════════
# lang.json é gerado automaticamente caso não exista, contendo PT-BR, EN e ES.
# Cada usuário escolhe seu idioma pelo botão "🌐 Idioma" e a escolha é
# persistida em data/user_database.json -> entry["lang"]. O owner também pode
# alterar o idioma DEFAULT global do bot (campo db["_settings"]["lang_default"]).
#
# Para acrescentar/editar traduções, basta editar lang.json — alterações são
# recarregadas a cada chamada de t() (cache de 5s).

DEFAULT_LANG_DATA = json.loads(r'''{"_meta": {"version": "1.0", "default": "pt_br", "available": ["pt_br", "en", "es"], "names": {"pt_br": "🇧🇷 Português (BR)", "en": "🇺🇸 English", "es": "🇪🇸 Español"}}, "pt_br": {"lang_name": "Português (BR)", "menu_title": "🕵️ **User Info Bot Pro v6.0**\n\nSelecione uma opção:", "start_card": "╔══════════════════════════════╗\n║  🕵️ **User Info Bot Pro v6.0**  ║\n╚══════════════════════════════╝\n\nMonitor profissional de usuários Telegram.\n\n🔍 Busca por ID, @username, nome ou:\n`@{bot} termo` → busca só por username\n\n{role}\n\n👨‍💻 _Créditos: Edivaldo Silva @Edkd1_", "role_owner": "⭐ Painel owner ativo", "role_user": "👤 Modo usuário", "btn_buscar": "🔍 Buscar Usuário", "btn_stats": "📊 Estatísticas", "btn_recent": "📋 Últimas Alterações", "btn_config": "⚙️ Configurações", "btn_about": "ℹ️ Sobre", "btn_lang": "🌐 Idioma", "btn_scan": "🔄 Varredura", "btn_export": "📤 Exportar Banco", "btn_ocultar": "🙈 Ocultar infor", "btn_premium": "⭐ Gerenciar Premium", "btn_combo_cfg": "🎛️ Config. Combo", "btn_back_menu": "🔙 Menu Principal", "btn_back": "🔙 Voltar", "btn_history": "📜 Histórico", "btn_open_tg": "🔗 Abrir no Telegram", "btn_cancel": "❌ Cancelar", "btn_confirm": "✔️ Confirmar", "search_prompt": "🔍 **Modo Busca**\n\nEnvie:\n• `123456789` → por ID\n• `@username` → por username\n• `Nome` → por nome parcial\n• `@{bot} termo` → apenas username\n\n_Aguardando..._", "search_results": "🔍 **{n} resultado(s) para** `{q}`{tag}  —  pág. {p}/{tp}\n\n", "search_tag_user_only": " _(apenas username)_", "search_cache_expired": "⚠️ Cache de busca expirou. Faça uma nova busca.", "search_no_results": "❌ Nenhum resultado para `{q}`.", "limited_free": "⚠️ _Resultados limitados. Premium desbloqueia busca completa._\n\n", "stats_title": "📊 **Estatísticas**\n\n👥 Usuários: **{total}**\n⭐ Premium: **{prem}**\n🔄 Alterações totais: **{chg}**\n🕐 Última varredura: `{last}`", "about_text": "ℹ️ **User Info Bot Pro v6.0**\n\nMonitor profissional Telegram.\nBusca por ID/username/nome, histórico completo,\npremium granular, geração de combo Xtream,\nidiomas dinâmicos (PT-BR, EN, ES).\n\n👨‍💻 _Créditos: Edivaldo Silva @Edkd1_", "config_text": "⚙️ **Configurações**\n\nEscolha uma opção abaixo:", "lang_menu": "🌐 **Idioma / Language / Idioma**\n\nEscolha o idioma do bot:", "lang_changed": "✅ Idioma alterado para **{name}**.", "recent_title": "📋 **Últimas alterações:**\n\n", "recent_empty": "_Sem alterações registradas._", "ocultar_menu": "🙈 **Ocultar Informações**\n\nEscolha qual campo ocultar ou revelar para um usuário.\n_O bot pedirá o ID ou @username do alvo._", "ocultar_field_phone": "📵 Telefone", "ocultar_field_id": "🔒 ID", "ocultar_field_username": "👤 Username", "ocultar_field_bio": "📝 Bio", "ocultar_list_btn": "📋 Ver ocultações ativas", "ocultar_list_title": "📋 **Campos ocultos ativos:**\n\n", "ocultar_list_empty": "_Nenhum campo oculto no momento._", "ocultar_ask_target": "🙈 **Ocultar/Revelar campo:** `{field}`\n\nEnvie o **ID numérico** ou **@username** do usuário alvo:", "premium_menu": "⭐ **Gerenciar Premium**\n\nAdicione ou remova o status premium e escolha módulos.", "premium_add": "➕ Adicionar Premium", "premium_remove": "➖ Remover Premium", "premium_list": "📋 Listar Premiums", "premium_list_title": "⭐ **Usuários Premium:**\n\n", "premium_list_empty": "_Nenhum usuário premium cadastrado._", "premium_add_prompt": "➕ **Adicionar Premium**\n\nEnvie o **ID** ou **@username** do usuário.\n_Se não estiver no banco, será buscado automaticamente._", "premium_remove_prompt": "➖ **Remover Premium**\n\nEnvie o **ID** ou **@username** do usuário:", "premium_select_modules": "⭐ **Selecionar módulos para** `{uid}`\n\nMarque os módulos que o usuário vai receber:", "premium_activated": "✅ **Premium ativado!**\n\n👤 `{name}` (`{uid}`)\n\n**Módulos:**\n{mods}", "premium_removed": "✅ **Premium removido de:**\n👤 `{name}` (`{uid}`)", "owner_only": "🚫 Restrito ao owner.", "user_not_found": "❌ Usuário `{q}` não encontrado.", "scan_running": "⚠️ Varredura já em andamento!", "scan_started": "🔄 **Varredura iniciada...**\n⏳ Aguarde notificação ao finalizar.", "scan_done": "✅ **Varredura Concluída!**\n\n📂 Grupos: **{g}**\n👥 Usuários: **{u}**\n🔔 Alterações: **{c}**\n🕐 `{ts}`", "combo_premium_only": "🚫 Recurso exclusivo Premium.", "combo_generating": "⏳ **Gerando combo...**\nLimite: **{lim}**", "combo_none": "❌ **Nenhum combo encontrado.**", "combo_done": "📋 **{n} combos gerados!**\n_@Edkd1_", "combo_cfg_title": "🎛️ **Configuração de Combo**\n\n📊 **Limites globais atuais:**\n├ Free: **{f}** combos\n└ Premium: **{p}** combos\n\nPara alterar:\n`/setcombo <uid> <free_limit> <premium_limit>`\n`/setcombo global <free_limit> <premium_limit>`", "hint_use_start": "💡 Use /start para abrir o menu.\nBusca rápida: `@{bot} @username`", "history_title": "📜 **Histórico de** `{name}`\nID: `{uid}` — pág. {p}/{tp}\n\n", "history_empty": "_Sem registros._", "history_limited_free": "⚠️ _Histórico limitado (Free)._", "field_hidden": "🔒 _Oculto_", "field_hidden_admin": "🔒 _Oculto pelo administrador_", "field_unavailable": "_Não disponível_", "field_none": "_Nenhuma_", "field_none_label": "Nenhuma", "tag_hidden_for_others": " _(oculto para outros)_", "profile_header": "╔══════════════════════════╗\n║  🕵️ **PERFIL DO USUÁRIO**  ║\n╚══════════════════════════╝", "profile_premium_tag": " ⭐ **PREMIUM**", "label_name": "👤 **Nome:**", "label_username": "🆔 **Username:**", "label_id": "🔢 **ID:**", "label_access": "🔗 **Acesso:**", "label_phone": "📱 **Telefone:**", "action_invalid": "⚠️ Ação não reconhecida.", "internal_error": "❌ Erro interno. Veja os logs.", "page_invalid": "⚠️ Página inválida.", "field_hidden_action": "🔒 Ocultado", "field_revealed_action": "🔓 Revelado", "field_toggle_done": "{status} **campo `{field}`** para:\n👤 `{name}` (`{uid}`)"}, "en": {"lang_name": "English", "menu_title": "🕵️ **User Info Bot Pro v6.0**\n\nPick an option:", "start_card": "╔══════════════════════════════╗\n║  🕵️ **User Info Bot Pro v6.0**  ║\n╚══════════════════════════════╝\n\nProfessional Telegram user monitor.\n\n🔍 Search by ID, @username, name or:\n`@{bot} term` → username-only search\n\n{role}\n\n👨‍💻 _Credits: Edivaldo Silva @Edkd1_", "role_owner": "⭐ Owner panel active", "role_user": "👤 User mode", "btn_buscar": "🔍 Search User", "btn_stats": "📊 Statistics", "btn_recent": "📋 Recent Changes", "btn_config": "⚙️ Settings", "btn_about": "ℹ️ About", "btn_lang": "🌐 Language", "btn_scan": "🔄 Scan", "btn_export": "📤 Export DB", "btn_ocultar": "🙈 Hide info", "btn_premium": "⭐ Manage Premium", "btn_combo_cfg": "🎛️ Combo Config", "btn_back_menu": "🔙 Main Menu", "btn_back": "🔙 Back", "btn_history": "📜 History", "btn_open_tg": "🔗 Open in Telegram", "btn_cancel": "❌ Cancel", "btn_confirm": "✔️ Confirm", "search_prompt": "🔍 **Search Mode**\n\nSend:\n• `123456789` → by ID\n• `@username` → by username\n• `Name` → partial name\n• `@{bot} term` → username only\n\n_Waiting..._", "search_results": "🔍 **{n} result(s) for** `{q}`{tag}  —  page {p}/{tp}\n\n", "search_tag_user_only": " _(username only)_", "search_cache_expired": "⚠️ Search cache expired. Please search again.", "search_no_results": "❌ No results for `{q}`.", "limited_free": "⚠️ _Results limited. Premium unlocks full search._\n\n", "stats_title": "📊 **Statistics**\n\n👥 Users: **{total}**\n⭐ Premium: **{prem}**\n🔄 Total changes: **{chg}**\n🕐 Last scan: `{last}`", "about_text": "ℹ️ **User Info Bot Pro v6.0**\n\nProfessional Telegram monitor.\nSearch by ID/username/name, full history,\ngranular premium, Xtream combo generation,\ndynamic languages (PT-BR, EN, ES).\n\n👨‍💻 _Credits: Edivaldo Silva @Edkd1_", "config_text": "⚙️ **Settings**\n\nChoose an option below:", "lang_menu": "🌐 **Language / Idioma / Idioma**\n\nPick the bot language:", "lang_changed": "✅ Language changed to **{name}**.", "recent_title": "📋 **Recent changes:**\n\n", "recent_empty": "_No changes recorded._", "ocultar_menu": "🙈 **Hide Information**\n\nChoose which field to hide or reveal for a user.\n_The bot will ask for the target's ID or @username._", "ocultar_field_phone": "📵 Phone", "ocultar_field_id": "🔒 ID", "ocultar_field_username": "👤 Username", "ocultar_field_bio": "📝 Bio", "ocultar_list_btn": "📋 View active hides", "ocultar_list_title": "📋 **Active hidden fields:**\n\n", "ocultar_list_empty": "_No hidden fields right now._", "ocultar_ask_target": "🙈 **Hide/Reveal field:** `{field}`\n\nSend the **numeric ID** or **@username** of the target user:", "premium_menu": "⭐ **Manage Premium**\n\nAdd or remove premium status and choose modules.", "premium_add": "➕ Add Premium", "premium_remove": "➖ Remove Premium", "premium_list": "📋 List Premiums", "premium_list_title": "⭐ **Premium users:**\n\n", "premium_list_empty": "_No premium user registered._", "premium_add_prompt": "➕ **Add Premium**\n\nSend the **ID** or **@username** of the user.\n_If not in the database, it will be looked up automatically._", "premium_remove_prompt": "➖ **Remove Premium**\n\nSend the **ID** or **@username** of the user:", "premium_select_modules": "⭐ **Pick modules for** `{uid}`\n\nCheck the modules the user will receive:", "premium_activated": "✅ **Premium activated!**\n\n👤 `{name}` (`{uid}`)\n\n**Modules:**\n{mods}", "premium_removed": "✅ **Premium removed from:**\n👤 `{name}` (`{uid}`)", "owner_only": "🚫 Owner only.", "user_not_found": "❌ User `{q}` not found.", "scan_running": "⚠️ A scan is already running!", "scan_started": "🔄 **Scan started...**\n⏳ Wait for the completion notification.", "scan_done": "✅ **Scan complete!**\n\n📂 Groups: **{g}**\n👥 Users: **{u}**\n🔔 Changes: **{c}**\n🕐 `{ts}`", "combo_premium_only": "🚫 Premium-only feature.", "combo_generating": "⏳ **Generating combo...**\nLimit: **{lim}**", "combo_none": "❌ **No combo found.**", "combo_done": "📋 **{n} combos generated!**\n_@Edkd1_", "combo_cfg_title": "🎛️ **Combo Settings**\n\n📊 **Current global limits:**\n├ Free: **{f}** combos\n└ Premium: **{p}** combos\n\nTo change:\n`/setcombo <uid> <free_limit> <premium_limit>`\n`/setcombo global <free_limit> <premium_limit>`", "hint_use_start": "💡 Use /start to open the menu.\nQuick search: `@{bot} @username`", "history_title": "📜 **History of** `{name}`\nID: `{uid}` — page {p}/{tp}\n\n", "history_empty": "_No records._", "history_limited_free": "⚠️ _History limited (Free)._", "field_hidden": "🔒 _Hidden_", "field_hidden_admin": "🔒 _Hidden by admin_", "field_unavailable": "_Not available_", "field_none": "_None_", "field_none_label": "None", "tag_hidden_for_others": " _(hidden from others)_", "profile_header": "╔══════════════════════════╗\n║  🕵️ **USER PROFILE**       ║\n╚══════════════════════════╝", "profile_premium_tag": " ⭐ **PREMIUM**", "label_name": "👤 **Name:**", "label_username": "🆔 **Username:**", "label_id": "🔢 **ID:**", "label_access": "🔗 **Access:**", "label_phone": "📱 **Phone:**", "action_invalid": "⚠️ Action not recognized.", "internal_error": "❌ Internal error. Check the logs.", "page_invalid": "⚠️ Invalid page.", "field_hidden_action": "🔒 Hidden", "field_revealed_action": "🔓 Revealed", "field_toggle_done": "{status} **field `{field}`** for:\n👤 `{name}` (`{uid}`)"}, "es": {"lang_name": "Español", "menu_title": "🕵️ **User Info Bot Pro v6.0**\n\nElige una opción:", "start_card": "╔══════════════════════════════╗\n║  🕵️ **User Info Bot Pro v6.0**  ║\n╚══════════════════════════════╝\n\nMonitor profesional de usuarios de Telegram.\n\n🔍 Búsqueda por ID, @usuario, nombre o:\n`@{bot} término` → solo por @usuario\n\n{role}\n\n👨‍💻 _Créditos: Edivaldo Silva @Edkd1_", "role_owner": "⭐ Panel del propietario activo", "role_user": "👤 Modo usuario", "btn_buscar": "🔍 Buscar usuario", "btn_stats": "📊 Estadísticas", "btn_recent": "📋 Últimos cambios", "btn_config": "⚙️ Ajustes", "btn_about": "ℹ️ Acerca de", "btn_lang": "🌐 Idioma", "btn_scan": "🔄 Escaneo", "btn_export": "📤 Exportar BD", "btn_ocultar": "🙈 Ocultar info", "btn_premium": "⭐ Gestionar Premium", "btn_combo_cfg": "🎛️ Config. Combo", "btn_back_menu": "🔙 Menú principal", "btn_back": "🔙 Volver", "btn_history": "📜 Historial", "btn_open_tg": "🔗 Abrir en Telegram", "btn_cancel": "❌ Cancelar", "btn_confirm": "✔️ Confirmar", "search_prompt": "🔍 **Modo búsqueda**\n\nEnvía:\n• `123456789` → por ID\n• `@usuario` → por @usuario\n• `Nombre` → por nombre parcial\n• `@{bot} término` → solo @usuario\n\n_Esperando..._", "search_results": "🔍 **{n} resultado(s) para** `{q}`{tag}  —  pág. {p}/{tp}\n\n", "search_tag_user_only": " _(solo @usuario)_", "search_cache_expired": "⚠️ La caché de búsqueda expiró. Realiza una nueva búsqueda.", "search_no_results": "❌ Sin resultados para `{q}`.", "limited_free": "⚠️ _Resultados limitados. Premium desbloquea la búsqueda completa._\n\n", "stats_title": "📊 **Estadísticas**\n\n👥 Usuarios: **{total}**\n⭐ Premium: **{prem}**\n🔄 Cambios totales: **{chg}**\n🕐 Último escaneo: `{last}`", "about_text": "ℹ️ **User Info Bot Pro v6.0**\n\nMonitor profesional de Telegram.\nBúsqueda por ID/@usuario/nombre, historial completo,\npremium granular, generación de combo Xtream,\nidiomas dinámicos (PT-BR, EN, ES).\n\n👨‍💻 _Créditos: Edivaldo Silva @Edkd1_", "config_text": "⚙️ **Ajustes**\n\nElige una opción abajo:", "lang_menu": "🌐 **Idioma / Language / Idioma**\n\nElige el idioma del bot:", "lang_changed": "✅ Idioma cambiado a **{name}**.", "recent_title": "📋 **Últimos cambios:**\n\n", "recent_empty": "_Sin cambios registrados._", "ocultar_menu": "🙈 **Ocultar información**\n\nElige qué campo ocultar o revelar para un usuario.\n_El bot pedirá el ID o @usuario del objetivo._", "ocultar_field_phone": "📵 Teléfono", "ocultar_field_id": "🔒 ID", "ocultar_field_username": "👤 Usuario", "ocultar_field_bio": "📝 Bio", "ocultar_list_btn": "📋 Ver ocultaciones activas", "ocultar_list_title": "📋 **Campos ocultos activos:**\n\n", "ocultar_list_empty": "_Ningún campo oculto ahora._", "ocultar_ask_target": "🙈 **Ocultar/Revelar campo:** `{field}`\n\nEnvía el **ID numérico** o **@usuario** del objetivo:", "premium_menu": "⭐ **Gestionar Premium**\n\nAgrega o quita el estado premium y elige módulos.", "premium_add": "➕ Agregar Premium", "premium_remove": "➖ Quitar Premium", "premium_list": "📋 Listar Premium", "premium_list_title": "⭐ **Usuarios Premium:**\n\n", "premium_list_empty": "_Ningún usuario premium registrado._", "premium_add_prompt": "➕ **Agregar Premium**\n\nEnvía el **ID** o **@usuario** del usuario.\n_Si no está en la base, se buscará automáticamente._", "premium_remove_prompt": "➖ **Quitar Premium**\n\nEnvía el **ID** o **@usuario** del usuario:", "premium_select_modules": "⭐ **Selecciona módulos para** `{uid}`\n\nMarca los módulos que recibirá el usuario:", "premium_activated": "✅ **¡Premium activado!**\n\n👤 `{name}` (`{uid}`)\n\n**Módulos:**\n{mods}", "premium_removed": "✅ **Premium quitado de:**\n👤 `{name}` (`{uid}`)", "owner_only": "🚫 Solo para el propietario.", "user_not_found": "❌ Usuario `{q}` no encontrado.", "scan_running": "⚠️ ¡Ya hay un escaneo en curso!", "scan_started": "🔄 **Escaneo iniciado...**\n⏳ Espera la notificación al finalizar.", "scan_done": "✅ **¡Escaneo completado!**\n\n📂 Grupos: **{g}**\n👥 Usuarios: **{u}**\n🔔 Cambios: **{c}**\n🕐 `{ts}`", "combo_premium_only": "🚫 Función exclusiva Premium.", "combo_generating": "⏳ **Generando combo...**\nLímite: **{lim}**", "combo_none": "❌ **No se encontró ningún combo.**", "combo_done": "📋 **¡{n} combos generados!**\n_@Edkd1_", "combo_cfg_title": "🎛️ **Configuración de combo**\n\n📊 **Límites globales actuales:**\n├ Free: **{f}** combos\n└ Premium: **{p}** combos\n\nPara cambiar:\n`/setcombo <uid> <free_limit> <premium_limit>`\n`/setcombo global <free_limit> <premium_limit>`", "hint_use_start": "💡 Usa /start para abrir el menú.\nBúsqueda rápida: `@{bot} @usuario`", "history_title": "📜 **Historial de** `{name}`\nID: `{uid}` — pág. {p}/{tp}\n\n", "history_empty": "_Sin registros._", "history_limited_free": "⚠️ _Historial limitado (Free)._", "field_hidden": "🔒 _Oculto_", "field_hidden_admin": "🔒 _Oculto por el administrador_", "field_unavailable": "_No disponible_", "field_none": "_Ninguna_", "field_none_label": "Ninguna", "tag_hidden_for_others": " _(oculto para otros)_", "profile_header": "╔══════════════════════════╗\n║  🕵️ **PERFIL DEL USUARIO** ║\n╚══════════════════════════╝", "profile_premium_tag": " ⭐ **PREMIUM**", "label_name": "👤 **Nombre:**", "label_username": "🆔 **Usuario:**", "label_id": "🔢 **ID:**", "label_access": "🔗 **Acceso:**", "label_phone": "📱 **Teléfono:**", "action_invalid": "⚠️ Acción no reconocida.", "internal_error": "❌ Error interno. Revisa los logs.", "page_invalid": "⚠️ Página inválida.", "field_hidden_action": "🔒 Ocultado", "field_revealed_action": "🔓 Revelado", "field_toggle_done": "{status} **campo `{field}`** para:\n👤 `{name}` (`{uid}`)"}}''')

_lang_cache = {"data": None, "ts": 0.0}

def _ensure_lang_file():
    """Cria lang.json com os 3 idiomas se ele não existir."""
    if os.path.exists(LANG_FILE):
        return
    # Tenta copiar do bundle do projeto (public/lang.json) — fallback ao default mínimo
    try:
        with open(LANG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_LANG_DATA, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[lang] erro ao criar lang.json: {e}")

def carregar_idiomas(force: bool = False) -> dict:
    import time
    now = time.time()
    if not force and _lang_cache["data"] is not None and (now - _lang_cache["ts"]) < 5:
        return _lang_cache["data"]
    _ensure_lang_file()
    try:
        with open(LANG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[lang] erro ao ler lang.json, usando default: {e}")
        data = DEFAULT_LANG_DATA
    _lang_cache["data"] = data
    _lang_cache["ts"]   = now
    return data

def idiomas_disponiveis() -> list:
    data = carregar_idiomas()
    meta = data.get("_meta", {})
    return meta.get("available", ["pt_br", "en", "es"])

def nome_idioma(code: str) -> str:
    data = carregar_idiomas()
    return data.get("_meta", {}).get("names", {}).get(code, code)

def get_lang_default() -> str:
    """Idioma global do bot (settable pelo owner)."""
    data = carregar_idiomas()
    try:
        db = json.load(open(FILE_PATH, 'r', encoding='utf-8')) if os.path.exists(FILE_PATH) else {}
    except Exception:
        db = {}
    return (db.get("_settings", {}) or {}).get(
        "lang_default", data.get("_meta", {}).get("default", "pt_br")
    )

def get_user_lang(user_id) -> str:
    """Idioma escolhido pelo usuário; cai no default global se não existir."""
    uid = str(user_id)
    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            db = json.load(f)
    except Exception:
        return get_lang_default()
    entry = db.get(uid, {})
    return entry.get("lang") or get_lang_default()

def set_user_lang(user_id, code: str):
    uid = str(user_id)
    db  = carregar_dados()
    if uid not in db:
        db[uid] = {
            "id": int(user_id) if str(user_id).lstrip("-").isdigit() else user_id,
            "nome_atual": "Sem nome",
            "username_atual": "Nenhum",
            "fonte": "Idioma",
            "historico": [],
            "grupos": [],
            "hidden_info": dict(DEFAULT_HIDDEN),
            "premium": {"active": False, "modules": []},
            "custom_combo_limits": {},
        }
    db[uid]["lang"] = code
    salvar_dados(db)

def t(key: str, user_id=None, lang: str = None, **fmt) -> str:
    """
    Tradução. Usa o idioma do usuário (ou explícito), com fallback em pt_br
    e na própria chave caso a tradução esteja faltando.
    """
    data = carregar_idiomas()
    if lang is None:
        lang = get_user_lang(user_id) if user_id is not None else get_lang_default()
    bundle  = data.get(lang) or {}
    fallback = data.get("pt_br") or {}
    txt = bundle.get(key, fallback.get(key, key))
    if fmt:
        try:
            return txt.format(**fmt)
        except Exception:
            return txt
    return txt

# ══════════════════════════════════════════════
# 📁  ARQUIVOS / BANCO
# ══════════════════════════════════════════════
os.makedirs(FOLDER_PATH, exist_ok=True)

def _ensure_files():
    if not os.path.exists(FILE_PATH):
        default_db = {"_settings": {"free_combo_limit": 200, "premium_combo_limit": 1000,
                                    "lang_default": "pt_br"}}
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_db, f, indent=2, ensure_ascii=False)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] Log iniciado\n")
    _ensure_lang_file()

_ensure_files()

def carregar_dados() -> dict:
    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            db = json.load(f)
    except (json.JSONDecodeError, IOError):
        db = {}
    if "_settings" not in db:
        db["_settings"] = {"free_combo_limit": 200, "premium_combo_limit": 1000,
                           "lang_default": "pt_br"}
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
    global_free    = settings.get("free_combo_limit",    200)
    global_premium = settings.get("premium_combo_limit", 1000)
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
def menu_principal_buttons(owner: bool = False, uid=None) -> list:
    # v7: "📋 Gerar combo" agora aparece para TODOS os usuários (Free e Premium)
    base = [
        [Button.inline(t("btn_buscar", uid),  b"cmd_buscar"),
         Button.inline(t("btn_stats",  uid),  b"cmd_stats")],
        [Button.inline("📋 Gerar Combo",      b"combo_run"),
         Button.inline(t("btn_recent", uid),  b"cmd_recent")],
        [Button.inline(t("btn_config", uid),  b"cmd_config"),
         Button.inline(t("btn_about",  uid),  b"cmd_about")],
        [Button.inline(t("btn_lang",   uid),  b"cmd_lang")],
    ]
    if owner:
        base.insert(1, [
            Button.inline(t("btn_scan",   uid), b"cmd_scan"),
            Button.inline(t("btn_export", uid), b"cmd_export"),
        ])
        base.insert(2, [
            Button.inline(t("btn_ocultar", uid), b"cmd_ocultar_menu"),
            Button.inline(t("btn_premium", uid), b"cmd_premium_menu"),
        ])
        base.insert(3, [
            Button.inline(t("btn_combo_cfg", uid), b"cmd_combo_config"),
        ])
    return base

def voltar_button(uid=None) -> list:
    return [[Button.inline(t("btn_back_menu", uid), b"cmd_menu")]]

def paginar_buttons(prefix: str, page: int, total_pages: int, uid=None) -> list:
    nav = []
    if page > 0:
        nav.append(Button.inline("◀️", f"{prefix}_page_{page-1}".encode()))
    nav.append(Button.inline(f"📄 {page+1}/{total_pages}", b"noop"))
    if page < total_pages - 1:
        nav.append(Button.inline("▶️", f"{prefix}_page_{page+1}".encode()))
    return [nav, [Button.inline(t("btn_back_menu", uid), b"cmd_menu")]]

def lang_menu_buttons(uid=None) -> list:
    """Botões de seleção de idioma — gerados dinamicamente a partir do lang.json."""
    rows = []
    current = get_user_lang(uid) if uid is not None else get_lang_default()
    for code in idiomas_disponiveis():
        mark = "✅ " if code == current else ""
        rows.append([Button.inline(f"{mark}{nome_idioma(code)}",
                                   f"setlang|{code}".encode())])
    if uid is not None and is_owner(uid):
        # Owner pode definir como default global (replica em _settings)
        rows.append([Button.inline("📌 Salvar como padrão (owner)",
                                   f"setlang|default|{current}".encode())])
    rows.append([Button.inline(t("btn_back_menu", uid), b"cmd_menu")])
    return rows



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
            t("scan_done", notify_chat,
              g=scan_stats['groups_scanned'],
              u=scan_stats['users_scanned'],
              c=scan_stats['changes_detected'],
              ts=agora),
            parse_mode='md', buttons=voltar_button(notify_chat)
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
    uid   = event.sender_id
    role  = t("role_owner", uid) if owner else t("role_user", uid)
    await event.respond(
        t("start_card", uid, bot=BOT_USERNAME, role=role),
        parse_mode='md',
        buttons=menu_principal_buttons(owner, uid)
    )

@bot.on(events.NewMessage(pattern='/lang'))
async def cmd_lang_msg(event):
    uid = event.sender_id
    await event.respond(
        t("lang_menu", uid),
        parse_mode='md',
        buttons=lang_menu_buttons(uid)
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
                t("menu_title", sender_id),
                parse_mode='md',
                buttons=menu_principal_buttons(owner, sender_id)
            )

        elif data == "cmd_lang":
            await message.edit(
                t("lang_menu", sender_id),
                parse_mode='md',
                buttons=lang_menu_buttons(sender_id)
            )

        elif data.startswith("setlang|"):
            parts = data.split("|")
            # setlang|<code>            → muda idioma do usuário
            # setlang|default|<code>    → owner: muda idioma padrão global
            if len(parts) == 3 and parts[1] == "default":
                if not owner:
                    await event.answer(t("owner_only", sender_id), alert=True); return
                code = parts[2]
                if code not in idiomas_disponiveis():
                    await event.answer("?", alert=True); return
                db = carregar_dados()
                db.setdefault("_settings", {})["lang_default"] = code
                salvar_dados(db)
                await event.answer(f"📌 default → {nome_idioma(code)}")
            else:
                code = parts[1]
                if code not in idiomas_disponiveis():
                    await event.answer("?", alert=True); return
                set_user_lang(sender_id, code)
                await event.answer(t("lang_changed", sender_id, name=nome_idioma(code)))
            # Recarrega menu de idioma com a marca ✅ atualizada
            await message.edit(
                t("lang_menu", sender_id),
                parse_mode='md',
                buttons=lang_menu_buttons(sender_id)
            )

        elif data == "cmd_buscar":
            pending_states[chat_id] = {"action": "search", "data": {}}
            await message.edit(
                t("search_prompt", sender_id, bot=BOT_USERNAME),
                parse_mode='md', buttons=voltar_button(sender_id)
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
                await event.answer(t("owner_only", sender_id), alert=True); return
            db       = carregar_dados()
            settings = db.get("_settings", {})
            await message.edit(
                t("combo_cfg_title", sender_id,
                  f=settings.get('free_combo_limit', 100),
                  p=settings.get('premium_combo_limit', 500)),
                parse_mode='md',
                buttons=voltar_button(sender_id)
            )

        # ── STATS ──
        elif data == "cmd_stats":
            db = carregar_dados()
            total = sum(1 for _ in iter_usuarios(db))
            prem  = sum(1 for _, d in iter_usuarios(db) if d.get("premium", {}).get("active"))
            chg   = sum(len(d.get("historico", [])) for _, d in iter_usuarios(db))
            await message.edit(
                t("stats_title", sender_id, total=total, prem=prem, chg=chg,
                  last=scan_stats.get('last_scan') or 'N/A'),
                parse_mode='md', buttons=voltar_button(sender_id)
            )

        elif data == "cmd_about":
            await message.edit(
                t("about_text", sender_id),
                parse_mode='md', buttons=voltar_button(sender_id)
            )

        elif data == "cmd_config":
            await message.edit(
                t("config_text", sender_id),
                parse_mode='md',
                buttons=[
                    [Button.inline(t("btn_lang", sender_id), b"cmd_lang")],
                    [Button.inline(t("btn_back_menu", sender_id), b"cmd_menu")],
                ]
            )

        elif data == "cmd_recent":
            db = carregar_dados()
            ultimos = []
            for uid, d in iter_usuarios(db):
                for h in d.get("historico", []):
                    ultimos.append((h.get("data"), d.get("nome_atual"), uid, h))
            ultimos.sort(key=lambda x: x[0] or "", reverse=True)
            ultimos = ultimos[:20]
            text = t("recent_title", sender_id)
            emoji_map = {"NOME": "📛", "USER": "🆔", "BIO": "📝", "PHONE": "📱"}
            for data_, nome, uid, h in ultimos:
                em = emoji_map.get(h.get("tipo"), "🔄")
                text += f"{em} `{data_}` — {nome} (`{uid}`)\n  {h['de']} ➜ {h['para']}\n\n"
            if not ultimos:
                text += t("recent_empty", sender_id)
            await message.edit(text, parse_mode='md', buttons=voltar_button(sender_id))

        elif data == "cmd_scan":
            if not owner:
                await event.answer(t("owner_only", sender_id), alert=True); return
            await event.answer("🔄 …")
            asyncio.create_task(executar_varredura(notify_chat=chat_id))

        elif data == "cmd_export":
            if not owner:
                await event.answer(t("owner_only", sender_id), alert=True); return
            await bot.send_file(chat_id, FILE_PATH, caption="📤")
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

        # ── COMBO (v7: liberado para TODOS os usuários, Free e Premium) ──
        elif data == "combo_run" or data.startswith("combo_"):
            viewer_str = str(sender_id)
            db = carregar_dados()
            free_lim, prem_lim = get_combo_limits(db, viewer_str)
            is_prem = is_premium_user(db, viewer_str) or owner
            limit   = prem_lim if is_prem else free_lim
            # Mínimo absoluto: 200 linhas para qualquer usuário Free
            if not is_prem and limit < 200:
                limit = 200
            await event.answer(f"📋 Gerando até {limit} combos...")
            msg_temp = await bot.send_message(
                chat_id,
                f"⏳ **Gerando combo...**\nLimite: **{limit}**\n_(usuário: `{viewer_str}`)_",
                parse_mode='md',
                buttons=[[Button.inline("❌ Cancelar", b"cmd_menu")]]
            )
            combos = await gerar_combo(limit)
            if not combos:
                await msg_temp.edit(
                    "❌ **Nenhum combo encontrado.**",
                    parse_mode='md',
                    buttons=voltar_button(sender_id)
                )
                return
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                             delete=False, encoding='utf-8') as f:
                f.write(f"# Combo gerado por @{BOT_USERNAME}\n")
                f.write(f"# Usuário: {viewer_str} | Total: {len(combos)} | {datetime.now()}\n\n")
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
        # v7: padrão garante que `query` é um ID numérico (\d{4,})
        query = bot_match.group(1).strip()
        results = buscar_usuario(query)  # match exato por ID dentro do banco
        if not results:
            results = await buscar_com_lookup(query, fonte="Bot+ID")
        db = carregar_dados()
        await _enviar_resultados(event, query, results, sender_id, db)
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
    # v7: busca por NOME (texto livre) é exclusiva PREMIUM/owner.
    # ID numérico e @username continuam livres para todos.
    if state and state["action"] == "search":
        del pending_states[chat_id]
        db = carregar_dados()
        viewer_str = str(sender_id)
        is_id      = text.lstrip('-').isdigit()
        is_user    = text.startswith('@') or re.fullmatch(r'[A-Za-z0-9_]{4,}', text) is not None
        is_prem    = is_premium_user(db, viewer_str) or owner
        if not (is_id or is_user) and not is_prem:
            await event.reply(
                "🔒 **Busca por nome é exclusiva Premium.**\n\n"
                "💡 Você pode buscar livremente por:\n"
                "• `123456789` → ID numérico\n"
                "• `@username` → username\n\n"
                "Para buscar por nome, peça acesso Premium ao owner.",
                parse_mode='md',
                buttons=voltar_button(sender_id)
            )
            return
        results = await buscar_com_lookup(text, fonte="Busca")
        db = carregar_dados()
        await _enviar_resultados(event, text, results, sender_id, db)
        return

    await event.reply(
        f"💡 Use /start para abrir o menu.\n"
        f"Busca rápida (apenas ID): `@{BOT_USERNAME} 123456789`",
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
    # v7: query é sempre um ID numérico
    query = bot_match.group(1).strip()
    results = buscar_usuario(query)
    if not results:
        results = await buscar_com_lookup(query, fonte="Grupo+ID")
    db = carregar_dados()
    await _enviar_resultados(event, query, results, event.sender_id, db)

# ══════════════════════════════════════════════
# 🎛️  /setcombo
# ══════════════════════════════════════════════
@bot.on(events.NewMessage(pattern=r'/setcombo\s+(.+)'))
async def cmd_setcombo(event):
    """v7: aceita ID numérico, @username ou 'global'."""
    if not is_owner(event.sender_id):
        await event.reply("🚫 Restrito ao owner."); return
    args = event.pattern_match.group(1).strip().split()
    if len(args) != 3:
        await event.reply(
            "Uso:\n"
            "`/setcombo <uid|@username|global> <free_limit> <premium_limit>`\n\n"
            "Exemplos:\n"
            "`/setcombo global 200 1000`\n"
            "`/setcombo 123456789 500 2000`\n"
            "`/setcombo @fulano 500 2000`",
            parse_mode='md'); return
    target_raw, free_s, prem_s = args
    try:
        free_lim, prem_lim = int(free_s), int(prem_s)
    except ValueError:
        await event.reply("❌ Limites devem ser números inteiros."); return

    db = carregar_dados()

    # 1) global
    if target_raw.lower() == "global":
        db.setdefault("_settings", {})["free_combo_limit"]    = free_lim
        db["_settings"]["premium_combo_limit"]                = prem_lim
        salvar_dados(db)
        await event.reply(
            f"✅ **Limites globais atualizados:**\n"
            f"Free: `{free_lim}` | Premium: `{prem_lim}`",
            parse_mode='md')
        return

    # 2) Resolve por ID ou @username (com lookup externo se preciso)
    target_uid = None
    if target_raw.isdigit():
        target_uid = target_raw
    if target_uid is None or target_uid not in db:
        results = await buscar_com_lookup(target_raw, fonte="setcombo")
        if results:
            target_uid = str(results[0]["id"])

    if not target_uid or target_uid not in db:
        await event.reply(
            f"❌ Alvo `{target_raw}` não encontrado (banco + lookup).",
            parse_mode='md'); return

    _ensure_user_shape(db[target_uid])
    db[target_uid]["custom_combo_limits"]["free"]    = free_lim
    db[target_uid]["custom_combo_limits"]["premium"] = prem_lim
    salvar_dados(db)
    await event.reply(
        f"✅ **Limites para** `{db[target_uid]['nome_atual']}` (`{target_uid}`):\n"
        f"Free: `{free_lim}` | Premium: `{prem_lim}`",
        parse_mode='md')

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

    log("🚀 User Info Bot Pro v7.0 iniciado — @Edkd1")
    log(f"📁 Arquivos: {FOLDER_PATH}/")
    log(f"🔄 Auto-scan a cada {SCAN_INTERVAL//60} min")
    log(f"🤖 Inline busca por ID: '@{BOT_USERNAME} 123456789'")

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
