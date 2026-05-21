# ==============================
# Buscar columna con palabras clave (para placas)
# ==============================
def buscar_columna(fila: dict, contiene_subcadenas):
    for clave, valor in fila.items():
        nombre = str(clave).strip().lower()
        if all(sub in nombre for sub in contiene_subcadenas):
            return str(valor) if valor is not None else "" # Convertimos a string para evitar errores con números
    return None

# ==============================
# Buscar placa en las filas
# ==============================
def buscar_placa(placa: str, datos):
    # Limpiamos la placa que envía el usuario (quitamos guiones y espacios)
    placa_limpia = placa.replace("-", "").replace(" ", "").lower()
    
    for fila in datos:
        # Buscamos en posibles columnas y limpiamos los datos extraídos del Excel
        placa_carro = str(buscar_columna(fila, ["placa", "carro"]) or "").replace("-", "").replace(" ", "").lower()
        placa_moto = str(buscar_columna(fila, ["placa", "moto"]) or "").replace("-", "").replace(" ", "").lower()
        placa_general = str(buscar_columna(fila, ["placa"]) or "").replace("-", "").replace(" ", "").lower()
        
        # Si la placa coincide con la del carro, la moto o una columna general "Placa"
        if placa_limpia and placa_limpia in [placa_carro, placa_moto, placa_general]:
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

    # 1. Primero verificamos si el texto tiene formato de apartamento o torre
    tipo, apto, torre = interpretar_codigo(texto)

    if tipo and apto:
        try:
            apto_int = int(apto)
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

            if tipo == tipo_fila and apto_int == apto_fila:
                if tipo == "torre" and torre:
                    if torre_fila != str(torre):
                        continue

                estado_raw = str(fila.get("Estado", "")).strip().upper()
                emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

                placa_carro = buscar_columna(fila, ["placa", "carro"]) or "No registrada"
                placa_moto = buscar_columna(fila, ["placa", "moto"]) or "No registrada"

                respuesta = f"🏢 *Tipo:* {fila.get('Tipo Vivienda')}\n\n"
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
        
        # Si tenía formato de apartamento pero no existe en Excel
        await update.message.reply_text("❌ Vivienda no encontrada.")
        return

    # 2. Si no es un apartamento, asumimos que es una placa
    texto_limpio = texto.replace("-", "").replace(" ", "")
    
    # Las placas en Colombia suelen tener 5 o 6 caracteres
    if len(texto_limpio) >= 5:
        datos = worksheet.get_all_records()
        fila_encontrada = buscar_placa(texto, datos)
        
        if fila_encontrada:
            torre = fila_encontrada.get("Torre", "No encontrada")
            apto = fila_encontrada.get("Apartamento", "No encontrado")
            propietario = fila_encontrada.get("Propietario", "No registrado")
            saldo = fila_encontrada.get("Saldo", "No especificado")
            estado_raw = str(fila_encontrada.get("Estado", "")).strip().upper()
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            placa_carro = buscar_columna(fila_encontrada, ["placa", "carro"]) or "No registrada"
            placa_moto = buscar_columna(fila_encontrada, ["placa", "moto"]) or "No registrada"

            respuesta = f"🚗 *Placa buscada:* {texto.upper()}\n"
            respuesta += f"🏗️ *Torre:* {torre}\n"
            respuesta += f"🏠 *Apartamento:* {apto}\n"
            respuesta += f"👤 *Propietario:* {propietario}\n"
            respuesta += f"💰 *Saldo:* {saldo}\n"
            respuesta += f"{emoji} *Estado:* {estado_txt}\n"
            respuesta += f"🚗 *Placa carro:* {placa_carro}\n"
            respuesta += f"🏍️ *Placa moto:* {placa_moto}"

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("❌ Placa no encontrada.")
            return

    await update.message.reply_text("❌ Formato inválido.")
