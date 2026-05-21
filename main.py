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
            return str(valor) # SOLUCIÓN: Asegurar que siempre sea un texto y no números puros
    return None

# ==============================
# Buscar placa en las filas
# ==============================
def buscar_placa(placa: str, datos):
    # SOLUCIÓN: Quitar espacios y guiones a la placa que escribe el usuario
    placa_limpia = placa.replace("-", "").replace(" ", "").strip().lower()
    
    for fila in datos:
        placa_carro = str(buscar_columna(fila, ["placa", "carro"]) or "No registrada")
        placa_moto = str(buscar_columna(fila, ["placa", "moto"]) or "No registrada")
        
        # SOLUCIÓN: Quitar espacios y guiones a las placas del Excel para que coincidan siempre
        pc_limpia = placa_carro.replace("-", "").replace(" ", "").strip().lower()
        pm_limpia = placa_moto.replace("-", "").replace(" ", "").strip().lower()

        if pc_limpia == placa_limpia or pm_limpia == placa_limpia:
            return fila
    return None

# ==============================
# Interpretar código inteligente (para torre y apartamento)
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
    
    # SOLUCIÓN: Limpiamos temporalmente para verificar si es placa
    texto_evaluar = texto.replace("-", "").replace(" ", "")

    # SOLUCIÓN: Usamos texto_evaluar. Se bajó a 5 por si buscan placas de motos
    if texto_evaluar.isalnum() and len(texto_evaluar) >= 5: 
        datos = worksheet.get_all_records()
        fila_encontrada = buscar_placa(texto, datos) # Se busca con el original
        
        if fila_encontrada:
            # Construir la respuesta con toda la información de la placa
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
