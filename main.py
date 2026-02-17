import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import gspread

# ==============================
# Cargar variables de entorno
# ==============================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

SHEET_ID = SHEET_ID.strip() if SHEET_ID else None

if not BOT_TOKEN:
    raise RuntimeError("❌ Falta BOT_TOKEN en las variables de entorno")
if not SHEET_ID:
    raise RuntimeError("❌ Falta SHEET_ID en las variables de entorno")
if not GOOGLE_CREDENTIALS:
    raise RuntimeError("❌ Falta GOOGLE_CREDENTIALS en las variables de entorno")

# ==============================
# Conexión con Google Sheets
# ==============================
creds = json.loads(GOOGLE_CREDENTIALS)
gc = gspread.service_account_from_dict(creds)

try:
    sh = gc.open_by_key(SHEET_ID)
except Exception:
    sh = gc.open("BOT TAMBORA")

worksheet = sh.sheet1
print("✅ Google Sheet conectado correctamente")

# ==============================
# Mapeo de estados
# ==============================
ESTADOS = {
    "R": ("🔴", "Restricción"),
    "A": ("🟡", "Acuerdo"),
    "V": ("🟢", "Normal")
}

# ==============================
# Buscar columnas dinámicamente
# ==============================
def buscar_columna(fila: dict, contiene_subcadenas):
    for clave, valor in fila.items():
        nombre = str(clave).strip().lower()
        if all(sub in nombre for sub in contiene_subcadenas):
            return valor
    return None

# ==============================
# Interpretar código
# ==============================
def interpretar_codigo(texto: str):
    texto = texto.strip().lower().replace("-", "").replace(" ", "")

    print(f"[DEBUG] Texto normalizado: {texto}")

    # Caso 1201 → torre 1 apto 201
    if texto.isdigit() and len(texto) == 4:
        torre = texto[0]
        apto = texto[1:]
        return "torre", apto, torre

    # Caso torre1201 o t1201
    if texto.startswith("t"):
        numeros = ''.join(ch for ch in texto if ch.isdigit())
        if len(numeros) >= 3:
            if len(numeros) == 4:
                return "torre", numeros[1:], numeros[0]
            return "torre", numeros, None

    # Caso casa90 o c90
    if texto.startswith("c"):
        numeros = ''.join(ch for ch in texto if ch.isdigit())
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
        "👋 Hola, envíame la torre o casa.\n\n"
        "Ejemplos válidos:\n"
        "• 1201\n"
        "• T1201\n"
        "• torre1201\n"
        "• C90\n"
        "• casa90"
    )

# ==============================
# Handler principal
# ==============================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    print(f"[DEBUG] Texto recibido: {texto}")

    tipo_str, apto_str, torre_num = interpretar_codigo(texto)

    print(f"[DEBUG] Interpretado -> tipo={tipo_str}, apto={apto_str}, torre={torre_num}")

    if not tipo_str or not apto_str:
        await update.message.reply_text("❌ Formato incorrecto. Ejemplo: 1201 o C90")
        return

    try:
        apto_vivienda = int(apto_str)
    except ValueError:
        await update.message.reply_text("❌ Número inválido.")
        return

    datos = worksheet.get_all_records()

    for fila in datos:
        try:
            tipo_fila = str(fila.get("Tipo Vivienda")).lower().strip()
            apto_fila = int(fila.get("Apartamento"))
            torre_fila = str(fila.get("Torre")).strip() if fila.get("Torre") else None
        except (TypeError, ValueError):
            continue

        # Comparación principal
        if tipo_str == tipo_fila and apto_vivienda == apto_fila:

            # Si es torre y el usuario especificó número
            if tipo_str == "torre" and torre_num:
                if str(torre_num) != torre_fila:
                    continue

            estado_raw = str(fila.get("Estado", "")).strip().upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            saldo = buscar_columna(fila, ["saldo"]) or "N/A"
            placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrado"
            placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"

            respuesta = (
                f"🏢 *Tipo Vivienda:* {fila.get('Tipo Vivienda')}\n"
                f"{'🏗️ *Torre:* ' + str(fila.get('Torre')) + '\\n' if fila.get('Torre') else ''}"
                f"🏠 *Apartamento:* {fila.get('Apartamento')}\n"
                f"🧍‍♂️ *Propietario:* {fila.get('Propietario')}\n"
                f"💰 *Saldo:* {saldo}\n"
                f"{emoji} *Estado:* {estado_txt}\n"
                f"🚗 *Placa carro:* {placa_carro}\n"
                f"🏍️ *Placa moto:* {placa_moto}"
            )

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

    await update.message.reply_text("❌ No encontré información para esa vivienda.")

# ==============================
# Iniciar Bot
# ==============================
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("✅ Bot activo y escuchando...")
    application.run_polling()

if __name__ == "__main__":
    main()
