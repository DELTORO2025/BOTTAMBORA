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
        "• 1 101\n"
        "• casa90\n"
        "• torre 101"
    )

# ==============================
# Interpretar código (torre/casa + apto)
# ==============================
def interpretar_codigo(texto: str):
    texto = texto.strip().replace("-", "").replace(" ", "")  # Eliminar espacios y guiones

    # Detectar si la entrada tiene una letra para "torre" o "casa" y el número del apartamento
    solo_numeros = ''.join(ch for ch in texto if ch.isdigit())  # Extraer solo los números
    solo_letras = ''.join(ch for ch in texto if ch.isalpha())  # Extraer solo las letras

    # Depuración
    print(f"[DEBUG] Texto procesado: {texto}")
    print(f"[DEBUG] Solo letras extraídas: {solo_letras}")
    print(f"[DEBUG] Solo números extraídos: {solo_numeros}")

    # Si solo hay números
    if len(solo_numeros) >= 3:
        apto = solo_numeros
        tipo = None

        # Si tiene más de 3 dígitos, podemos asumir que es una torre o casa
        if 1 <= int(apto) <= 280:  # Límite de apartamentos para casa
            tipo = "casa"
        elif 1 <= int(apto) <= 21:  # Límite de apartamentos para torre
            tipo = "torre"
        else:
            tipo = None
    else:
        tipo = solo_letras.lower()  # Asignar el tipo según las letras
        apto = solo_numeros

    return tipo, apto

# ==============================
# Handler principal
# ==============================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()

    # Depuración para verificar el texto recibido
    print(f"[DEBUG] Texto recibido: {texto}")

    tipo_str, apto_str = interpretar_codigo(texto)

    # Depuración para verificar el tipo y apartamento
    print(f"[DEBUG] Entrada procesada -> tipo={tipo_str}, apto={apto_str}")

    if not tipo_str or not apto_str:
        await update.message.reply_text("Formato incorrecto. Ejemplo: 1-101 o 1101")
        return

    # Verificar si es una torre o casa
    if tipo_str == "casa" and 1 <= int(apto_str) <= 280:
        vivienda = "casa"
    elif tipo_str == "torre" and 1 <= int(apto_str) <= 21:
        vivienda = "torre"
    else:
        await update.message.reply_text("No pude interpretar los datos. Asegúrate de que el formato sea correcto.")
        return

    print(f"[DEBUG] Vivienda: {vivienda}, Apartamento: {apto_str}")

    try:
        tipo_vivienda = str(tipo_str)
        apto_vivienda = int(apto_str)
    except ValueError:
        await update.message.reply_text("No pude interpretar los datos.")
        return

    datos = worksheet.get_all_records()
    print(f"[DEBUG] Registros cargados: {len(datos)}")

    for fila in datos:
        # Depuración: Verificación de lo que se está comparando
        print(f"[DEBUG] Comparando tipo vivienda: {tipo_vivienda} con {fila.get('Tipo Vivienda')} y apartamento: {apto_vivienda} con {fila.get('Apartamento')}")

        try:
            tipo_fila = str(fila.get("Tipo Vivienda")).lower().strip()  # Asegurarse de que no haya espacios adicionales
            apto_fila = int(fila.get("Apartamento"))
        except (TypeError, ValueError):
            continue

        # Agregar depuración para comparar
        print(f"[DEBUG] Comparando {tipo_vivienda} con {tipo_fila} y {apto_vivienda} con {apto_fila}")

        if tipo_vivienda.lower() == tipo_fila and apto_vivienda == apto_fila:
            print(f"[DEBUG] ¡Coincidencia encontrada!")
            estado_raw = str(fila.get("Estado", "")).strip().upper()  # Asegurar que esté en mayúsculas
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

            # Depuración antes de enviar la respuesta
            print(f"[DEBUG] Respuesta enviada: {respuesta}")

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

    await update.message.reply_text("❌ No encontré información para esa vivienda.")

# ==============================
# Configuración del Bot y Polling
# ==============================
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Comandos
    application.add_handler(CommandHandler("start", start))

    # Mensajes
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    # Iniciar el bot con polling
    print("✅ Bot activo y escuchando...")
    application.run_polling()

if __name__ == "__main__":
    main()
