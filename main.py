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

          # Prompt per l'intelligenza artificiale visiva
          prompt = (
              "Analizza questa immagine di una costruzione/struttura in un"
              " videogioco o cantiere. Rispondi ESATTAMENTE con una di queste"
              " due frasi, senza aggiungere altro:\n1. 'In costruzione!'"
              " (se l'opera è incompleta, in corso, con materiali sparsi,"
              " impalcature o lavori a metà)\n2. 'Costruzione completata!"
              " Scrivetemi che altre costruzioni fare!' (se l'opera è"
              " finita, pulita, rifinita o completa)."
          )

          # Tentativi automatici in caso di sovraccarico (Errore 503)
          max_tentativi = 3
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
              break  # Se ha successo, esce dal ciclo
            except Exception as api_err:
              tentativo += 1
              if "503" in str(api_err) and tentativo < max_tentativi:
                print(
                    f"Server sovraccarico (Tentativo {tentativo}/{max_tentativi})."
                    " Rprovo tra 4 secondi..."
                )
                time.sleep(4)
              else:
                raise api_err  # Rilancia l'errore se non è un 503 o se abbiamo esaurito i tentativi

          # Invia la risposta nel canale in base a ciò che ha visto l'IA
          if risposta_ia and "completata" in risposta_ia.lower():
            await message.channel.send(
                "Costruzione completata! Scrivetemi che altre costruzioni fare!"
            )
          else:
            await message.channel.send("In costruzione!")

        except Exception as e:
          print(f"Errore durante l'analisi dell'immagine con l'IA: {e}")
          # Mostra l'errore tecnico direttamente su Discord se fallisce del tutto
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
