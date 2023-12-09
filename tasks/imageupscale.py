import json
import os
from multiprocessing.pool import ThreadPool
from pathlib import Path

import dotenv

from backends.nserver.utils import check_server_status, send_request_to_server
from interfaces.dvmtaskinterface import DVMTaskInterface
from utils.admin_utils import AdminConfig
from utils.backend_utils import keep_alive
from utils.dvmconfig import DVMConfig
from utils.nip89_utils import NIP89Config, check_and_set_d_tag
from utils.definitions import EventDefinitions
from utils.nostr_utils import check_and_set_private_key
from utils.zap_utils import check_and_set_ln_bits_keys
from nostr_sdk import Keys

"""
This File contains a Module to upscale an image from an url by factor 2-4 

Accepted Inputs: link to image (url)
Outputs: An url to an Image
Params: -upscale        2,3,4
"""


class ImageUpscale(DVMTaskInterface):
    KIND: int = EventDefinitions.KIND_NIP90_GENERATE_IMAGE
    TASK: str = "image-to-image"
    FIX_COST: float = 20

    def __init__(self, name, dvm_config: DVMConfig, nip89config: NIP89Config,
                 admin_config: AdminConfig = None, options=None):
        super().__init__(name, dvm_config, nip89config, admin_config, options)

    def is_input_supported(self, tags):
        hasurl = False
        for tag in tags:
            if tag.as_vec()[0] == 'i':
                input_value = tag.as_vec()[1]
                input_type = tag.as_vec()[2]
                if input_type == "url":
                    hasurl = True

        if not hasurl:
            return False

        return True

    def create_request_from_nostr_event(self, event, client=None, dvm_config=None):
        request_form = {"jobID": event.id().to_hex() + "_" + self.NAME.replace(" ", "")}
        request_form["trainerFilePath"] = r'modules\image_upscale\image_upscale_realesrgan.trainer'
        url = ""
        out_scale = 4

        for tag in event.tags():
            if tag.as_vec()[0] == 'i':
                input_type = tag.as_vec()[2]
                if input_type == "url":
                    url = tag.as_vec()[1]

            elif tag.as_vec()[0] == 'param':
                print("Param: " + tag.as_vec()[1] + ": " + tag.as_vec()[2])
                if tag.as_vec()[1] == "upscale":
                    out_scale = tag.as_vec()[2]



        io_input_image = {
        "id": "input_image",
        "type": "input",
        "src": "url:Image",
        "uri": url
        }

        io_output = {
            "id": "output_image",
            "type": "output",
            "src": "request:image"
        }

        request_form['data'] = json.dumps([io_input_image, io_output])

        options = {
            "outscale": out_scale,

        }
        request_form['options'] = json.dumps(options)

        return request_form

    def process(self, request_form):
        try:
            # Call the process route of NOVA-Server with our request form.
            response = send_request_to_server(request_form, self.options['server'])
            if bool(json.loads(response)['success']):
                print("Job " + request_form['jobID'] + " sent to server")

            pool = ThreadPool(processes=1)
            thread = pool.apply_async(check_server_status, (request_form['jobID'], self.options['server']))
            print("Wait for results of server...")
            result = thread.get()
            return result

        except Exception as e:
            raise Exception(e)

# We build an example here that we can call by either calling this file directly from the main directory,
# or by adding it to our playground. You can call the example and adjust it to your needs or redefine it in the
# playground or elsewhere
def build_example(name, identifier, admin_config, server_address):
    dvm_config = DVMConfig()
    dvm_config.PRIVATE_KEY = check_and_set_private_key(identifier)
    npub = Keys.from_sk_str(dvm_config.PRIVATE_KEY).public_key().to_bech32()
    invoice_key, admin_key, wallet_id, user_id, lnaddress = check_and_set_ln_bits_keys(identifier, npub)
    dvm_config.LNBITS_INVOICE_KEY = invoice_key
    dvm_config.LNBITS_ADMIN_KEY = admin_key  # The dvm might pay failed jobs back
    dvm_config.LNBITS_URL = os.getenv("LNBITS_HOST")
    admin_config.LUD16 = lnaddress

    nip90params = {
        "upscale": {
            "required": False,
            "values": ["2", "3", "4"]
        }
    }
    nip89info = {
        "name": name,
        "image": "https://image.nostr.build/229c14e440895da30de77b3ca145d66d4b04efb4027ba3c44ca147eecde891f1.jpg",
        "about": "I upscale an image using realESRGan up to factor 4 (default is factor 4)",
        "encryptionSupported": True,
        "cashuAccepted": True,
        "nip90Params": nip90params
    }

    # A module might have options it can be initialized with, here we set a default model, lora and the server
    options = {'server': server_address}

    nip89config = NIP89Config()
    nip89config.DTAG = check_and_set_d_tag(identifier, name, dvm_config.PRIVATE_KEY,
                                                              nip89info["image"])
    nip89config.CONTENT = json.dumps(nip89info)
    # We add an optional AdminConfig for this one, and tell the dvm to rebroadcast its NIP89
    return ImageUpscale(name=name, dvm_config=dvm_config, nip89config=nip89config,
                                      admin_config=admin_config, options=options)


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
    admin_config.LUD16 = ""
    dvm = build_example("Image Upscaler", "imageupscale", admin_config, os.getenv("N_SERVER"))
    dvm.run()

    keep_alive()