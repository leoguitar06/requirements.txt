from io import BytesIO
import os
import threading
import time
import discord
from discord.ext import commands
from flask import Flask
from google import genai

# Configurazione API e Token (prelevati dalle variabili d'ambiente di Render)
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Inizializza il client di Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Configurazione del bot Discord con i permessi per leggere i messaggi e le immagini
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  print(f"Bot di costruzione loggato come {bot.user}!")


@bot.event
async def on_message(message):
  # Ignora i messaggi inviati dal bot stesso per evitare loop infiniti
  if message.author == bot.user:
    return

  # Controlla se il messaggio contiene almeno un'immagine allegata
  if message.attachments:
    for attachment in message.attachments:
      if any(
          attachment.filename.lower().endswith(ext)
          for ext in [".png", ".jpg", ".jpeg", ".webp"]
      ):
        print(
            f"Immagine ricevuta da {message.author}: {attachment.filename}"
        )
        await message.channel.send(
            "🔍 *Sto analizzando la foto della costruzione...*"
        )

        try:
          # Scarica l'immagine in memoria
          image_bytes = await attachment.read()

          # Prende il testo scritto dall'utente insieme alla foto (la didascalia)
          testo_utente = message.content if message.content else ""

          # Prompt avanzato per Gemini: analizza foto e testo per trovare lo stato e il nome
          prompt = (
              f"Analizza questa immagine di una costruzione e il testo allegato"
              f" scritto dall'utente: '{testo_utente}'.\n1. Determina se l'opera"
              " è 'In costruzione' o 'Completata'.\n2. Estrai dal testo"
              " dell'utente il nome della persona o l'autore (es. 'cristolino2014',"
              " 'Gabri', ecc.). Rispondi ESATTAMENTE in questo formato:\nSTATO:"
              " [In costruzione / Completata]\nAUTORE: [Il nome trovato,"
              " oppure 'nessuno']"
          )

          # Tentativi multipli con attesa progressiva per superare l'errore 503
          max_tentativi = 4
          tentativo = 0
          risposta_ia = None

          while tentativo < max_tentativi:
            try:
              response = ai_client.models.generate_content(
                  model="gemini-3.6-flash",
                  contents=[
                      prompt,
                      {
                          "inline_data": {
                              "data": image_bytes,
                              "mime_type": "image/jpeg",
                          }
                      },
                  ],
              )
              risposta_ia = response.text.strip()
              break
            except Exception as api_err:
              tentativo += 1
              if "503" in str(api_err) and tentativo < max_tentativi:
                attesa = tentativo * 5
                print(
                    f"Server sovraccarico (Errore 503). Tentativo"
                    f" {tentativo}/{max_tentativi}. Riprovo tra {attesa}"
                    " secondi..."
                )
                time.sleep(attesa)
              else:
                raise api_err

          # Elabora la risposta dell'IA
          stato = "In costruzione"
          autore = "nessuno"

          if risposta_ia:
            for riga in risposta_ia.split("\n"):
              if riga.startswith("STATO:"):
                stato = riga.replace("STATO:", "").strip()
              elif riga.startswith("AUTORE:"):
                autore = riga.replace("AUTORE:", "").strip()

          # Invia il messaggio finale in base a ciò che ha rilevato l'IA
          if "completata" in stato.lower():
            if autore.lower() != "nessuno" and autore != "":
              await message.channel.send(
                  f"Costruzione richiesta da {autore} completata! Scrivetemi"
                  " che altre costruzioni fare!"
              )
            else:
              await message.channel.send(
                  "Costruzione completata! Scrivetemi che altre costruzioni"
                  " fare!"
              )
          else:
            await message.channel.send("In costruzione!")

        except Exception as e:
          print(f"Errore durante l'analisi dell'immagine con l'IA: {e}")
          await message.channel.send(f"⚠️ Errore tecnico: `{str(e)}`")

  await bot.process_commands(message)


# === SERVER WEB FLASK (Per mantenere attivo il bot 24/7 su Render) ===
app = Flask("")


@app.route("/")
def home():
  return "Il bot delle costruzioni è attivo e operativo 24/7!"


def run_flask():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
  t_flask = threading.Thread(target=run_flask)
  t_flask.daemon = True
  t_flask.start()

  if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
  else:
    print("ERRORE: DISCORD_TOKEN non trovato nelle variabili ambiente!")
