import json
import os
import re
from pathlib import Path

import dotenv

from nostr_dvm.interfaces.dvmtaskinterface import DVMTaskInterface
from nostr_dvm.utils.admin_utils import AdminConfig
from nostr_dvm.utils.backend_utils import keep_alive
from nostr_dvm.utils.definitions import EventDefinitions
from nostr_dvm.utils.dvmconfig import DVMConfig
from nostr_dvm.utils.nip89_utils import NIP89Config, check_and_set_d_tag
from nostr_dvm.utils.nostr_utils import get_event_by_id, check_and_set_private_key
from nostr_dvm.utils.zap_utils import check_and_set_ln_bits_keys
from nostr_sdk import Keys

"""
This File contains a Module to extract Text from a PDF file locally on the DVM Machine

Accepted Inputs: Url to pdf file, Event containing an URL to a PDF file
Outputs: Text containing the extracted contents of the PDF file
Params:  None
"""


class TextExtractionPDF(DVMTaskInterface):
    KIND: int = EventDefinitions.KIND_NIP90_EXTRACT_TEXT
    TASK: str = "pdf-to-text"
    FIX_COST: float = 0
    dependencies = ["pypdf==3.17.1"]

    def __init__(self, name, dvm_config: DVMConfig, nip89config: NIP89Config,
                 admin_config: AdminConfig = None, options=None):
        super().__init__(name, dvm_config, nip89config, admin_config, options)



    def is_input_supported(self, tags):
        for tag in tags:
            if tag.as_vec()[0] == 'i':
                input_value = tag.as_vec()[1]
                input_type = tag.as_vec()[2]
                if input_type != "url" and input_type != "event":
                    return False
        return True

    def create_request_from_nostr_event(self, event, client=None, dvm_config=None):
        request_form = {"jobID": event.id().to_hex()}

        # default values
        input_type = "url"
        input_content = ""
        url = ""

        for tag in event.tags():
            if tag.as_vec()[0] == 'i':
                input_type = tag.as_vec()[2]
                input_content = tag.as_vec()[1]

        if input_type == "url":
            url = input_content
        # if event contains url to pdf, we checked for a pdf link before
        elif input_type == "event":
            evt = get_event_by_id(input_content, client=client, config=dvm_config)
            url = re.search("(?P<url>https?://[^\s]+)", evt.content()).group("url")

        options = {
            "url": url,
        }
        request_form['options'] = json.dumps(options)
        return request_form

    def process(self, request_form):
        from pypdf import PdfReader
        from pathlib import Path
        import requests

        options = DVMTaskInterface.set_options(request_form)

        try:
            file_path = Path('temp.pdf')
            response = requests.get(options["url"])
            file_path.write_bytes(response.content)
            reader = PdfReader(file_path)
            number_of_pages = len(reader.pages)
            text = ""
            for page_num in range(number_of_pages):
                page = reader.pages[page_num]
                text = text + page.extract_text()

            os.remove('temp.pdf')
            return text
        except Exception as e:
            raise Exception(e)


# We build an example here that we can call by either calling this file directly from the main directory,
# or by adding it to our playground. You can call the example and adjust it to your needs or redefine it in the
# playground or elsewhere
def build_example(name, identifier, admin_config):
    dvm_config = DVMConfig()
    dvm_config.PRIVATE_KEY = check_and_set_private_key(identifier)
    npub = Keys.from_sk_str(dvm_config.PRIVATE_KEY).public_key().to_bech32()
    invoice_key, admin_key, wallet_id, user_id, lnaddress = check_and_set_ln_bits_keys(identifier, npub)
    dvm_config.LNBITS_INVOICE_KEY = invoice_key
    dvm_config.LNBITS_ADMIN_KEY = admin_key  # The dvm might pay failed jobs back
    dvm_config.LNBITS_URL = os.getenv("LNBITS_HOST")
    admin_config.LUD16 = lnaddress
    # Add NIP89
    nip90params = {}
    nip89info = {
        "name": name,
        "image": "https://image.nostr.build/c33ca6fc4cc038ca4adb46fdfdfda34951656f87ee364ef59095bae1495ce669.jpg",
        "about": "I extract text from pdf documents. I only support Latin letters",
        "encryptionSupported": True,
        "cashuAccepted": True,
        "nip90Params": nip90params
    }

    nip89config = NIP89Config()
    nip89config.DTAG = check_and_set_d_tag(identifier, name, dvm_config.PRIVATE_KEY, nip89info["image"])
    nip89config.CONTENT = json.dumps(nip89info)
    return TextExtractionPDF(name=name, dvm_config=dvm_config, nip89config=nip89config,
                             admin_config=admin_config)


if __name__ == '__main__':
    env_path = Path('.env')
    if env_path.is_file():
        print(f'loading environment from {env_path.resolve()}')
        dotenv.load_dotenv(env_path, verbose=True, override=True)
    else:
        raise FileNotFoundError(f'.env file not found at {env_path} ')

    admin_config = AdminConfig()
    admin_config.REBROADCAST_NIP89 = False
    admin_config.UPDATE_PROFILE = False
    dvm = build_example("PDF Extractor", "pdf_extractor", admin_config)
    dvm.run()

    keep_alive()
