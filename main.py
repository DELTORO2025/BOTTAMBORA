import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import gspread

# ==============================
# Cargar variables
# ==============================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not BOT_TOKEN or not SHEET_ID or not GOOGLE_CREDENTIALS:
    raise RuntimeError("❌ Faltan variables de entorno")

# ==============================
# Conexión Google Sheets
# ==============================
creds = json.loads(GOOGLE_CREDENTIALS)
gc = gspread.service_account_from_dict(creds)
sh = gc.open_by_key(SHEET_ID)
worksheet = sh.sheet1

print("✅ Google Sheet conectado correctamente")

# ==============================
# Estados
# ==============================
ESTADOS = {
    "R": ("🔴", "Restricción"),
    "A": ("🟡", "Acuerdo"),
    "V": ("🟢", "Normal")
}

# ==============================
# Interpretar código
# ==============================
def interpretar_codigo(texto: str):
    texto = texto.strip().lower().replace("-", "").replace(" ", "")

    # Caso 1201 → Torre 1, Apto 201
    if texto.isdigit() and len(texto) == 4:
        torre = texto[0]
        apto = texto[1:]
        return "torre", apto, torre

    # Caso T1201 o torre1201
    if texto.startswith("t"):
        numeros = ''.join(c for c in texto if c.isdigit())
        if len(numeros) == 4:
            return "torre", numeros[1:], numeros[0]
        elif numeros:
            return "torre", numeros, None

    # Caso C90 o casa90
    if texto.startswith("c"):
        numeros = ''.join(c for c in texto if c.isdigit())
        if numeros:
            return "casa", numeros, None

    # Solo número → asumir casa
    if texto.isdigit():
        return "casa", texto, None

    return None, None, None

# ==============================
# Comando /start
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Envíame:\n\n"
        "• 1201\n"
        "• T1201\n"
        "• C90\n"
        "• casa90"
    )

# ==============================
# Buscar vivienda
# ==============================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    tipo, apto, torre = interpretar_codigo(texto)

    if not tipo or not apto:
        await update.message.reply_text("❌ Formato inválido.")
        return

    try:
        apto = int(apto)
    except ValueError:
        await update.message.reply_text("❌ Número inválido.")
        return

    datos = worksheet.get_all_records()

    for fila in datos:
        try:
            tipo_fila = str(fila.get("Tipo Vivienda", "")).lower().strip()
            apto_fila = int(fila.get("Apartamento", 0))
            torre_fila = str(fila.get("Torre", "")).strip()
        except (ValueError, TypeError):
            continue

        if tipo == tipo_fila and apto == apto_fila:

            # Si es torre y el usuario especificó torre
            if tipo == "torre" and torre:
                if torre_fila != str(torre):
                    continue

            estado_raw = str(fila.get("Estado", "")).strip().upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            # Construir respuesta sin errores de f-string
            respuesta = f"🏢 *Tipo:* {fila.get('Tipo Vivienda')}\n"

            if torre_fila:
                respuesta += f"🏗️ *Torre:* {torre_fila}\n"

            respuesta += f"🏠 *Apartamento:* {fila.get('Apartamento')}\n"
            respuesta += f"👤 *Propietario:* {fila.get('Propietario')}\n"
            respuesta += f"💰 *Saldo:* {fila.get('Saldo')}\n"
            respuesta += f"{emoji} *Estado:* {estado_txt}"

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

    await update.message.reply_text("❌ No encontrado.")

# ==============================
# Iniciar Bot
# ==============================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("🤖 Bot activo...")
    app.run_polling()

if __name__ == "__main__":
    main()
