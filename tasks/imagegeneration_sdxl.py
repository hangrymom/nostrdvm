import json
import os
from multiprocessing.pool import ThreadPool
from pathlib import Path

import dotenv

from backends.nova_server import check_nova_server_status, send_request_to_nova_server
from interfaces.dvmtaskinterface import DVMTaskInterface
from utils.admin_utils import AdminConfig
from utils.backend_utils import keep_alive
from utils.dvmconfig import DVMConfig
from utils.nip89_utils import NIP89Config, check_and_set_d_tag
from utils.definitions import EventDefinitions
from utils.nostr_utils import check_and_set_private_key

"""
This File contains a Module to transform Text input on NOVA-Server and receive results back. 

Accepted Inputs: Prompt (text)
Outputs: An url to an Image
Params: -model         # models: juggernaut, dynavision, colossusProject, newreality, unstable
        -lora          # loras (weights on top of models) voxel, 
"""


class ImageGenerationSDXL(DVMTaskInterface):
    KIND: int = EventDefinitions.KIND_NIP90_GENERATE_IMAGE
    TASK: str = "text-to-image"
    FIX_COST: float = 50

    def __init__(self, name, dvm_config: DVMConfig, nip89config: NIP89Config,
                 admin_config: AdminConfig = None, options=None):
        super().__init__(name, dvm_config, nip89config, admin_config, options)

    def is_input_supported(self, tags):
        for tag in tags:
            if tag.as_vec()[0] == 'i':
                input_value = tag.as_vec()[1]
                input_type = tag.as_vec()[2]
                if input_type != "text":
                    return False

            elif tag.as_vec()[0] == 'output':
                output = tag.as_vec()[1]
                if (output == "" or
                        not (output == "image/png" or "image/jpg"
                             or output == "image/png;format=url" or output == "image/jpg;format=url")):
                    print("Output format not supported, skipping..")
                    return False

        return True

    def create_request_from_nostr_event(self, event, client=None, dvm_config=None):
        request_form = {"jobID": event.id().to_hex() + "_" + self.NAME.replace(" ", "")}
        request_form["trainerFilePath"] = 'modules\\stablediffusionxl\\stablediffusionxl.trainer'

        prompt = ""
        negative_prompt = ""
        if self.options.get("default_model") and self.options.get("default_model") != "":
            model = self.options['default_model']
        else:
            model = "stabilityai/stable-diffusion-xl-base-1.0"

        ratio_width = "1"
        ratio_height = "1"
        width = ""
        height = ""
        if self.options.get("default_lora") and self.options.get("default_lora") != "":
            lora = self.options['default_lora']
        else:
            lora = ""
        lora_weight = ""
        strength = ""
        guidance_scale = ""
        for tag in event.tags():
            if tag.as_vec()[0] == 'i':
                input_type = tag.as_vec()[2]
                if input_type == "text":
                    prompt = tag.as_vec()[1]

            elif tag.as_vec()[0] == 'param':
                print("Param: " + tag.as_vec()[1] + ": " + tag.as_vec()[2])
                if tag.as_vec()[1] == "negative_prompt":
                    negative_prompt = tag.as_vec()[2]
                elif tag.as_vec()[1] == "lora":
                    lora = tag.as_vec()[2]
                elif tag.as_vec()[1] == "lora_weight":
                    lora_weight = tag.as_vec()[2]
                elif tag.as_vec()[1] == "strength":
                    strength = float(tag.as_vec()[2])
                elif tag.as_vec()[1] == "guidance_scale":
                    guidance_scale = float(tag.as_vec()[2])
                elif tag.as_vec()[1] == "ratio":
                    if len(tag.as_vec()) > 3:
                        ratio_width = (tag.as_vec()[2])
                        ratio_height = (tag.as_vec()[3])
                    elif len(tag.as_vec()) == 3:
                        split = tag.as_vec()[2].split(":")
                        ratio_width = split[0]
                        ratio_height = split[1]
                    # if size is set it will overwrite ratio.
                elif tag.as_vec()[1] == "size":
                    if len(tag.as_vec()) > 3:
                        width = (tag.as_vec()[2])
                        height = (tag.as_vec()[3])
                    elif len(tag.as_vec()) == 3:
                        split = tag.as_vec()[2].split("x")
                        if len(split) > 1:
                            width = split[0]
                            height = split[1]
                elif tag.as_vec()[1] == "model":
                    model = tag.as_vec()[2]

        io_input = {
            "id": "input_prompt",
            "type": "input",
            "src": "request:text",
            "data": prompt
        }
        io_negative = {
            "id": "negative_prompt",
            "type": "input",
            "src": "request:text",
            "data": negative_prompt
        }
        io_output = {
            "id": "output_image",
            "type": "output",
            "src": "request:image"
        }

        request_form['data'] = json.dumps([io_input, io_negative, io_output])

        options = {
            "model": model,
            "ratio": ratio_width + '-' + ratio_height,
            "width": width,
            "height": height,
            "strength": strength,
            "guidance_scale": guidance_scale,
            "lora": lora,
            "lora_weight": lora_weight
        }
        request_form['options'] = json.dumps(options)

        return request_form

    def process(self, request_form):
        try:
            # Call the process route of NOVA-Server with our request form.
            response = send_request_to_nova_server(request_form, self.options['nova_server'])
            if bool(json.loads(response)['success']):
                print("Job " + request_form['jobID'] + " sent to NOVA-server")

            pool = ThreadPool(processes=1)
            thread = pool.apply_async(check_nova_server_status, (request_form['jobID'], self.options['nova_server']))
            print("Wait for results of NOVA-Server...")
            result = thread.get()
            return result

        except Exception as e:
            raise Exception(e)

# We build an example here that we can call by either calling this file directly from the main directory,
# or by adding it to our playground. You can call the example and adjust it to your needs or redefine it in the
# playground or elsewhere
def build_example(name, identifier, admin_config, server_address, default_model="stabilityai/stable-diffusion-xl"
                                                                                   "-base-1.0", default_lora=""):
    dvm_config = DVMConfig()
    dvm_config.PRIVATE_KEY = check_and_set_private_key(identifier)
    dvm_config.LNBITS_INVOICE_KEY = ""  # This one will not use Lnbits to create invoices, but rely on zaps
    dvm_config.LNBITS_URL = ""

    # A module might have options it can be initialized with, here we set a default model, and the nova-server
    # address it should use. These parameters can be freely defined in the task component
    options = {'default_model': default_model, 'default_lora': default_lora, 'nova_server': server_address}

    nip90params = {
        "negative_prompt": {
            "required": False,
            "values": []
        },
        "ratio": {
            "required": False,
            "values": ["1:1", "4:3", "16:9", "3:4", "9:16", "10:16"]
        }
    }
    nip89info = {
        "name": name,
        "image": "https://image.nostr.build/c33ca6fc4cc038ca4adb46fdfdfda34951656f87ee364ef59095bae1495ce669.jpg",
        "about": "I draw images based on a prompt with a Model called unstable diffusion",
        "encryptionSupported": True,
        "cashuAccepted": True,
        "nip90Params": nip90params
    }
    nip89config = NIP89Config()
    nip89config.DTAG = check_and_set_d_tag(identifier, name, dvm_config.PRIVATE_KEY,
                                                              nip89info["image"])
    nip89config.CONTENT = json.dumps(nip89info)
    return ImageGenerationSDXL(name=name, dvm_config=dvm_config, nip89config=nip89config,
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
    dvm = build_example("Unstable Diffusion", "unstable_diffusion", admin_config, os.getenv("NOVA_SERVER"), "stabilityai/stable-diffusion-xl", "")
    dvm.run()

    keep_alive()