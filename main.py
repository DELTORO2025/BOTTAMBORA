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
        "👋 Hola, envíame el código de la torre o casa.\n"
        "Ejemplos válidos:\n"
        "• 1101 (Torre)\n"
        "• C1 (Casa)\n"
        "• C220 (Casa)\n"
        "• T1101 (Torre)"
    )

# ==============================
# Interpretar código (torre o casa)
# ==============================
def interpretar_codigo(texto: str):
    texto = texto.strip().upper()
    
    # Si el texto comienza con "T" o es solo un número, es una torre
    if texto.startswith("T"):
        tipo_vivienda = "Torre"
        codigo_vivienda = texto[1:]  # El código de la torre o apartamento
    # Si el texto comienza con "C", es una casa
    elif texto.startswith("C"):
        tipo_vivienda = "Casa"
        codigo_vivienda = texto[1:]  # El código de la casa
        # Validar si el número de casa es válido (1-250)
        if not 1 <= int(codigo_vivienda) <= 250:
            tipo_vivienda = "Invalido"
    else:
        tipo_vivienda = "Desconocido"
        codigo_vivienda = texto  # El código del apartamento o casa

    # Retornamos tipo de vivienda y código
    return tipo_vivienda, codigo_vivienda

# ==============================
# Handler principal
# ==============================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    tipo_vivienda, codigo_vivienda = interpretar_codigo(texto)

    print(f"[LOG] Entrada: '{texto}' -> tipo={tipo_vivienda}, código={codigo_vivienda}")

    if tipo_vivienda == "Desconocido" or not codigo_vivienda:
        await update.message.reply_text("Formato incorrecto. Ejemplo: T1101 o C1")
        return
    elif tipo_vivienda == "Invalido":
        await update.message.reply_text("El número de casa debe estar entre 1 y 250.")
        return

    try:
        codigo_busqueda = int(codigo_vivienda)
    except ValueError:
        await update.message.reply_text("No pude interpretar los datos.")
        return

    datos = worksheet.get_all_records()
    print(f"[LOG] Registros cargados: {len(datos)}")

    for fila in datos:
        try:
            tipo_fila = fila.get("Tipo Vivienda", "").strip()
            codigo_fila = int(fila.get("Código", 0))
        except (TypeError, ValueError):
            continue

        if tipo_fila == tipo_vivienda and codigo_fila == codigo_busqueda:
            estado_raw = str(fila.get("Estado", "")).upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            saldo = buscar_columna(fila, ["saldo"]) or "N/A"
            placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrado"
            placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"

            respuesta = (
                f"🏢 *Tipo de Vivienda:* {tipo_fila}\n"
                f"🏠 *Código:* {fila.get('Código')}\n"
                f"🧍‍♂️ *Propietario:* {fila.get('Propietario')}\n"
                f"💰 *Saldo:* {saldo}\n"
                f"{emoji} *Estado:* {estado_txt}\n"
                f"🚗 *Placa carro:* {placa_carro}\n"
                f"🏍️ *Placa moto:* {placa_moto}"
            )

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

    await update.message.reply_text(f"❌ No encontré información para esa {tipo_vivienda}.")

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
