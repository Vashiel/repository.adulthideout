# -*- coding: utf-8 -*-

import urllib.parse

# --- Benutzerdefiniertes Base64 für TubePornClassic ---

# Benutzerdefiniertes Alphabet aus dem JavaScript
CUSTOM_ALPHABET = "АВСDЕFGHIJKLМNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,~"
# Mapping für schnellen Index-Zugriff
DECODE_MAP = {char: index for index, char in enumerate(CUSTOM_ALPHABET)}

def custom_base64_decode(encoded_str):
    """
    Dekodiert einen String mittels des benutzerdefinierten Base64-Alphabets von TubePornClassic.
    Nachempfunden der base164_decode Funktion aus app.js.
    Gibt den dekodierten String oder None bei Fehlern zurück.
    """
    if not encoded_str:
        return None

    output_bytes = bytearray() # Verwende bytearray zum Sammeln der Bytes
    encoded_str = "".join(encoded_str.split()) # Whitespace entfernen
    i = 0
    str_len = len(encoded_str)

    while i < str_len:
        # Hole Indizes aus dem CUSTOM_ALPHABET map
        s_idx = DECODE_MAP.get(encoded_str[i], -1); i += 1
        if i >= str_len: i_idx = -1
        else: i_idx = DECODE_MAP.get(encoded_str[i], -1); i += 1

        if i >= str_len: l_idx = -1
        else: l_idx = DECODE_MAP.get(encoded_str[i], -1); i += 1

        if i >= str_len: n_idx = -1
        else: n_idx = DECODE_MAP.get(encoded_str[i], -1); i += 1

        # Fehlerbehandlung für ungültige Zeichen oder unerwartetes Ende
        if s_idx == -1 or i_idx == -1:
            # Loggen sollte idealerweise im Aufrufer geschehen
            # print(f"Invalid char or insufficient length in custom_base64_decode near pos {i}")
            return None # Abbruch bei Fehler

        # Bit-Operationen wie im JavaScript
        byte1 = (s_idx << 2) | (i_idx >> 4)
        output_bytes.append(byte1 & 0xFF) # Stelle sicher, dass es ein gültiger Bytewert ist

        if l_idx != -1 and l_idx != 64: # 64 wird im JS als "ignore padding" verwendet (64 != l)
            byte2 = ((i_idx & 15) << 4) | (l_idx >> 2)
            output_bytes.append(byte2 & 0xFF)

            if n_idx != -1 and n_idx != 64: # (64 != n)
                byte3 = ((l_idx & 3) << 6) | n_idx
                output_bytes.append(byte3 & 0xFF)

    # Dekodiere die resultierenden Bytes (oft latin-1 nach solchen Operationen)
    # und wende dann das Äquivalent von unescape an
    try:
        # Versuche, die Bytes direkt als latin-1 zu interpretieren
        intermediate_string = output_bytes.decode('latin-1')
        # Wende urllib.parse.unquote an (ersetzt JS unescape)
        final_string = urllib.parse.unquote(intermediate_string, encoding='latin-1', errors='replace')
        return final_string
    except Exception as e:
        # Loggen sollte idealerweise im Aufrufer geschehen
        # print(f"Error during final unquote/decode: {e}")
        # Fallback oder Fehler? Geben wir None zurück.
        return None