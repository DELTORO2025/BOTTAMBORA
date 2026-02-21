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
# Buscar columna con palabras clave (para placas)
# ==============================
def buscar_columna(fila: dict, contiene_subcadenas):
    for clave, valor in fila.items():
        nombre = str(clave).strip().lower()
        if all(sub in nombre for sub in contiene_subcadenas):
            return valor
    return None

# ==============================
# Interpretar código inteligente
# ==============================
def interpretar_codigo(texto: str):
    texto = texto.strip().lower().replace("-", "").replace(" ", "")

    if texto.isdigit() and len(texto) >= 4:
        apto = texto[-3:]
        torre = texto[:-3]
        if torre == "":
            return "casa", apto, None
        return "torre", apto, torre

    if texto.startswith("t"):
        numeros = ''.join(c for c in texto if c.isdigit())
        if len(numeros) >= 4:
            apto = numeros[-3:]
            torre = numeros[:-3]
            return "torre", apto, torre

    if texto.startswith("c"):
        numeros = ''.join(c for c in texto if c.isdigit())
        if numeros:
            return "casa", numeros, None

    if texto.isdigit():
        return "casa", texto, None

    return None, None, None

# ==============================
# Buscar placa en las filas
# ==============================
def buscar_placa(placa: str, datos):
    for fila in datos:
        placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrada"
        placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"
        
        # Verificar si la placa carro o moto coincide
        if placa_carro.strip().lower() == placa.strip().lower() or placa_moto.strip().lower() == placa.strip().lower():
            torre = fila.get("Torre", "No encontrada")
            return torre
    return None

# ==============================
# Comando /start
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Envíame:\n\n"
        "• 1201\n"
        "• 10201\n"
        "• T210104\n"
        "• C90\n"
        "• HMN835 (placa)"
    )

# ==============================
# Buscar vivienda
# ==============================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    tipo, apto, torre = interpretar_codigo(texto)

    # Si es una placa, buscamos la torre directamente
    if texto.strip().isalnum() and len(texto.strip()) >= 6:
        datos = worksheet.get_all_records()
        torre_encontrada = buscar_placa(texto, datos)
        
        if torre_encontrada:
            await update.message.reply_text(f"🚗 *Placa:* {texto}\n🏗️ *Torre:* {torre_encontrada}")
            return
        else:
            await update.message.reply_text("❌ Placa no encontrada.")
        return

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
            if tipo == "torre" and torre:
                if torre_fila != str(torre):
                    continue

            estado_raw = str(fila.get("Estado", "")).strip().upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            # Buscar placas con función inteligente
            placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrada"
            placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"

            # Construir respuesta segura
            respuesta = f"🏢 *Tipo:* {fila.get('Tipo Vivienda')}\n"

            if torre_fila:
                respuesta += f"🏗️ *Torre:* {torre_fila}\n"

            respuesta += f"🏠 *Apartamento:* {fila.get('Apartamento')}\n"
            respuesta += f"👤 *Propietario:* {fila.get('Propietario')}\n"
            respuesta += f"💰 *Saldo:* {fila.get('Saldo')}\n"
            respuesta += f"{emoji} *Estado:* {estado_txt}\n"
            respuesta += f"🚗 *Placa carro:* {placa_carro}\n"
            respuesta += f"🏍️ *Placa moto:* {placa_moto}"

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
