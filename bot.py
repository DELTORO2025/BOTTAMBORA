mport os
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

# 🔧 LIMPIEZA CRÍTICA
SHEET_ID = SHEET_ID.strip() if SHEET_ID else None

print("[ENV] BOT_TOKEN definido:", bool(BOT_TOKEN))
print("[ENV] SHEET_ID valor:", repr(SHEET_ID))
print("[ENV] SHEET_ID longitud:", len(SHEET_ID) if SHEET_ID else "None")
print("[ENV] GOOGLE_CREDENTIALS definido:", GOOGLE_CREDENTIALS is not None)

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
    print("📄 Intentando abrir Google Sheet por ID...")
    sh = gc.open_by_key(SHEET_ID)
except Exception as e:
    print("⚠️ Error abriendo por ID:", e)
    print("📄 Intentando abrir por NOMBRE (BOTGUITARRA)...")
    sh = gc.open("BOTGUITARRA")

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
# Utilidades para buscar columnas
# ==============================
def buscar_columna(fila: dict, contiene_subcadenas):
    for clave, valor in fila.items():
        nombre = str(clave).strip().lower()
        if all(sub in nombre for sub in contiene_subcadenas):
            return valor
    return None

# ==============================
# Comando /start
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola, envíame la torre y apartamento.\n"
        "Ejemplos válidos:\n"
        "• 1-101\n"
        "• 1101\n"
        "• T1101\n"
        "• 1 101"
    )

# ==============================
# Interpretar código (torre + apto)
# ==============================
def interpretar_codigo(texto: str):
    solo_numeros = ''.join(ch for ch in texto if ch.isdigit())
    if len(solo_numeros) < 3:
        return None, None
    return solo_numeros[0], solo_numeros[1:]

# ==============================
# Handler principal
# ==============================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    torre_str, apto_str = interpretar_codigo(texto)

    print(f"[LOG] Entrada: '{texto}' -> torre={torre_str}, apto={apto_str}")

    if not torre_str or not apto_str:
        await update.message.reply_text("Formato incorrecto. Ejemplo: 1-101 o 1101")
        return

    try:
        torre_busqueda = int(torre_str)
        apto_busqueda = int(apto_str)
    except ValueError:
        await update.message.reply_text("No pude interpretar los datos.")
        return

    datos = worksheet.get_all_records()
    print(f"[LOG] Registros cargados: {len(datos)}")

    for fila in datos:
        try:
            torre_fila = int(fila.get("Torre"))
            apto_fila = int(fila.get("Apartamento"))
        except (TypeError, ValueError):
            continue

        if torre_fila == torre_busqueda and apto_fila == apto_busqueda:
            estado_raw = str(fila.get("Estado", "")).upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            saldo = buscar_columna(fila, ["saldo"]) or "N/A"
            placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrado"
            placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"

            respuesta = (
                f"🏢 *Torre:* {fila.get('Torre')}\n"
                f"🏠 *Apartamento:* {fila.get('Apartamento')}\n"
                f"🧍‍♂️ *Propietario:* {fila.get('Propietario')}\n"
                f"💰 *Saldo:* {saldo}\n"
                f"{emoji} *Estado:* {estado_txt}\n"
                f"🚗 *Placa carro:* {placa_carro}\n"
                f"🏍️ *Placa moto:* {placa_moto}"
            )

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

    await update.message.reply_text("❌ No encontré información para ese apartamento.")

# ==============================
# Iniciar el bot
# ==============================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("🤖 BOT ACTIVO EN RAILWAY")
    app.run_polling()

if __name__ == "__main__":
    main()
