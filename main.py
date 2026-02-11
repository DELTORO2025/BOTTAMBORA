import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import gspread
from flask import Flask, request

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
    sh = gc.open_by_key(SHEET_ID)  # Usando el ID proporcionado
except Exception as e:
    print("⚠️ Error abriendo por ID:", e)
    print("📄 Intentando abrir por NOMBRE (BOT TAMBORA)...")
    sh = gc.open("BOT TAMBORA")  # Nombre correcto de la hoja de cálculo en Google Sheets

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
        "👋 Hola, envíame la torre o casa y apartamento.\n"
        "Ejemplos válidos:\n"
        "• 1-101\n"
        "• 1101\n"
        "• T1101\n"
        "• C230\n"
        "• 1 101"
    )

# ==============================
# Interpretar código (torre/casa + apto)
# ==============================
def interpretar_codigo(texto: str):
    # Eliminar caracteres no numéricos o letras
    solo_numeros = ''.join(ch for ch in texto if ch.isdigit())
    if len(solo_numeros) < 3:
        return None, None
    # Primer número es la torre/casa, el resto es el apartamento
    return solo_numeros[0], solo_numeros[1:]

# ==============================
# Handler principal
# ==============================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    tipo_str, apto_str = interpretar_codigo(texto)

    print(f"[LOG] Entrada: '{texto}' -> tipo={tipo_str}, apto={apto_str}")

    if not tipo_str or not apto_str:
        await update.message.reply_text("Formato incorrecto. Ejemplo: 1-101 o 1101")
        return

    # Verificar si es una torre o casa
    if tipo_str == "C" and 1 <= int(apto_str) <= 280:
        vivienda = "casa"
    elif tipo_str.isdigit() and 1 <= int(tipo_str) <= 21:
        vivienda = "torre"
    else:
        await update.message.reply_text("No pude interpretar los datos. Asegúrate de que el formato sea correcto.")
        return

    print(f"[LOG] Vivienda: {vivienda}, Apartamento: {apto_str}")

    try:
        tipo_vivienda = str(tipo_str)
        apto_vivienda = int(apto_str)
    except ValueError:
        await update.message.reply_text("No pude interpretar los datos.")
        return

    datos = worksheet.get_all_records()
    print(f"[LOG] Registros cargados: {len(datos)}")

    for fila in datos:
        print(f"[LOG] Comparando: {fila.get('Tipo Vivienda')} - {fila.get('Apartamento')}")

        try:
            tipo_fila = str(fila.get("Tipo Vivienda")).lower()
            apto_fila = int(fila.get("Apartamento"))
        except (TypeError, ValueError):
            continue

        # Agregar debug para comparar
        print(f"[LOG] Comparando {tipo_vivienda} con {tipo_fila} y {apto_vivienda} con {apto_fila}")

        # Compara los datos
        if tipo_vivienda.lower() == tipo_fila and apto_vivienda == apto_fila:
            estado_raw = str(fila.get("Estado", "")).upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            saldo = buscar_columna(fila, ["saldo"]) or "N/A"
            placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrado"
            placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"

            respuesta = (
                f"🏢 *Tipo Vivienda:* {fila.get('Tipo Vivienda')}\n"
                f"🏠 *Apartamento:* {fila.get('Apartamento')}\n"
                f"🧍‍♂️ *Propietario:* {fila.get('Propietario')}\n"
                f"💰 *Saldo:* {saldo}\n"
                f"{emoji} *Estado:* {estado_txt}\n"
                f"🚗 *Placa carro:* {placa_carro}\n"
                f"🏍️ *Placa moto:* {placa_moto}"
            )

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

    await update.message.reply_text("❌ No encontré información para ese apartamento o casa.")

# ==============================
# Configuración del Webhook con Flask
# ==============================
app = Flask(__name__)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = Update.de_json(json.loads(json_str), app.bot)
    app.bot.process_new_updates([update])
    return 'OK', 200

# ==============================
# Iniciar el bot con Webhook
# ==============================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    # Establecer un webhook
    app.run_webhook(
        listen="0.0.0.0",  # Asegúrate de que esto apunte a tu servidor
        port=5000,
        url_path=BOT_TOKEN,
        webhook_url="https://<tu-dominio>/path-to-webhook",  # Pon tu URL de webhook aquí
    )

if __name__ == "__main__":
    main()
