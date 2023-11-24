import os
import signal
import sys
import time
from pathlib import Path
from threading import Thread

import dotenv
from nostr_sdk import Keys

from bot import Bot
from playground import build_pdf_extractor, build_translator, build_unstable_diffusion, build_sketcher, build_dalle
from utils.dvmconfig import DVMConfig


def run_nostr_dvm_with_local_config():
    # We extract the Publickey from our bot, so the DVMs know who they should listen and react to.
    bot_publickey = Keys.from_sk_str(os.getenv("BOT_PRIVATE_KEY")).public_key()

    # We will run an optional bot that can  communicate  with the DVMs
    # Note this is very basic for now and still under development
    bot_config = DVMConfig()
    bot_config.PRIVATE_KEY = os.getenv("BOT_PRIVATE_KEY")
    bot_config.LNBITS_INVOICE_KEY = os.getenv("LNBITS_INVOICE_KEY")
    bot_config.LNBITS_URL = os.getenv("LNBITS_HOST")

    # Spawn some DVMs in the playground and run them
    # You can add arbitrary DVMs there and instantiate them here

    # Spawn DVM1 Kind 5000: A local Text Extractor from PDFs
    pdfextractor = build_pdf_extractor("PDF Extractor", [bot_publickey])
    # If we don't add it to the bot, the bot will not provide access to the DVM
    pdfextractor.run()

    # Spawn DVM2 Kind 5002 Local Text Translation, calling the free Google API.
    translator = build_translator("Translator", [bot_publickey])
    bot_config.SUPPORTED_DVMS.append(translator)  # We add translator to the bot
    translator.run()

    # Spawn DVM3 Kind 5100 Image Generation This one uses a specific backend called nova-server.
    # If you want to use it, see the instructions in backends/nova_server
    if os.getenv("NOVA_SERVER") is not None and os.getenv("NOVA_SERVER") != "":
        unstable_artist = build_unstable_diffusion("Unstable Diffusion", [bot_publickey])
        bot_config.SUPPORTED_DVMS.append(unstable_artist)  # We add unstable Diffusion to the bot
        unstable_artist.run()

    # Spawn DVM4, another Instance of text-to-image, as before but use a different privatekey, model and lora this time.
    if os.getenv("NOVA_SERVER") is not None and os.getenv("NOVA_SERVER") != "":
        sketcher = build_sketcher("Sketcher", [bot_publickey])
        bot_config.SUPPORTED_DVMS.append(sketcher)  # We also add Sketcher to the bot
        sketcher.run()

    # Spawn DVM5, this one requires an OPENAI API Key and balance with OpenAI, you will move the task to them and pay
    # per call. Make sure you have enough balance and the DVM's cost is set higher than what you pay yourself, except, you know,
    # you're being generous.
    if os.getenv("OPENAI_API_KEY") is not None and os.getenv("OPENAI_API_KEY") != "":
        dalle = build_dalle("Dall-E 3", [bot_publickey])
        bot_config.SUPPORTED_DVMS.append(dalle)
        dalle.run()

    bot = Bot(bot_config)
    bot.run()

    # Keep the main function alive for libraries like openai
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print('Stay weird!')
        os.kill(os.getpid(), signal.SIGKILL)


if __name__ == '__main__':
    env_path = Path('.env')
    if env_path.is_file():
        print(f'loading environment from {env_path.resolve()}')
        dotenv.load_dotenv(env_path, verbose=True, override=True)
    else:
        raise FileNotFoundError(f'.env file not found at {env_path} ')
    run_nostr_dvm_with_local_config()