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
# Buscar placa en las filas
# ==============================
def buscar_placa(placa: str, datos):
    for fila in datos:
        placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrada"
        placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"
        
        # Verificar si la placa carro o moto coincide
        if placa_carro.strip().lower() == placa.strip().lower() or placa_moto.strip().lower() == placa.strip().lower():
            return fila
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
# Buscar vivienda o placa
# ==============================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()

    # Verificar si es una placa (alfanumérica)
    if texto.isalnum() and len(texto) >= 6:  # Modificado para aceptar placas alfanuméricas
        datos = worksheet.get_all_records()
        fila_encontrada = buscar_placa(texto, datos)
        
        if fila_encontrada:
            # Construir la respuesta con toda la información
            torre = fila_encontrada.get("Torre", "No encontrada")
            apto = fila_encontrada.get("Apartamento", "No encontrado")
            propietario = fila_encontrada.get("Propietario", "No registrado")
            saldo = fila_encontrada.get("Saldo", "No especificado")
            estado_raw = str(fila_encontrada.get("Estado", "")).strip().upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            placa_carro = buscar_columna(fila_encontrada, ["placa", "carro"]) or "No registrada"
            placa_moto = buscar_columna(fila_encontrada, ["placa", "moto"]) or "No registrada"

            # Mejorar el formato de la respuesta
            respuesta = f"🚗 *Placa:* {texto}\n"
            respuesta += f"🏗️ *Torre:* {torre}\n"
            respuesta += f"🏠 *Apartamento:* {apto}\n"
            respuesta += f"👤 *Propietario:* {propietario}\n"
            respuesta += f"💰 *Saldo:* {saldo}\n"
            respuesta += f"{emoji} *Estado:* {estado_txt}\n"
            respuesta += f"🚗 *Placa carro:* {placa_carro}\n"
            respuesta += f"🏍️ *Placa moto:* {placa_moto}"

            # Enviar la respuesta completa y bien organizada
            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("❌ Placa no encontrada.")
        return

    # Si no es una placa, proceder con la búsqueda por apartamento o torre
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
            if tipo == "torre" and torre:
                if torre_fila != str(torre):
                    continue

            estado_raw = str(fila.get("Estado", "")).strip().upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            # Buscar placas con función inteligente
            placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrada"
            placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"

            # Construir respuesta con saltos de línea para mejor formato
            respuesta = f"🏢 *Tipo:* {fila.get('Tipo Vivienda')}\n\n"
            if torre_fila:
                respuesta += f"🏗️ *Torre:* {torre_fila}\n"
            respuesta += f"🏠 *Apartamento:* {fila.get('Apartamento')}\n"
            respuesta += f"👤 *Propietario:* {fila.get('Propietario')}\n"
            respuesta += f"💰 *Saldo:* {fila.get('Saldo')}\n"
            respuesta += f"{emoji} *Estado:* {estado_txt}\n"
            respuesta += f"🚗 *Placa carro:* {placa_carro}\n"
            respuesta += f"🏍️ *Placa moto:* {placa_moto}"

            # Enviar el mensaje asegurándose de que esté bien formateado
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
