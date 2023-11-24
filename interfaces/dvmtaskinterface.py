import json
from threading import Thread

from utils.admin_utils import AdminConfig
from utils.dvmconfig import DVMConfig
from utils.nip89_utils import NIP89Announcement, NIP89Config
from dvm import DVM


class DVMTaskInterface:
    NAME: str
    KIND: int
    TASK: str
    COST: int
    PK: str
    DVM = DVM
    dvm_config: DVMConfig
    admin_config: AdminConfig

    def NIP89_announcement(self, nip89config: NIP89Config):
        nip89 = NIP89Announcement()
        nip89.name = self.NAME
        nip89.kind = self.KIND
        nip89.pk = self.PK
        nip89.dtag = nip89config.DTAG
        nip89.content = nip89config.CONTENT
        return nip89

    def init(self, name, dvm_config, admin_config, nip89config):
        self.NAME = name
        self.PK = dvm_config.PRIVATE_KEY
        if dvm_config.COST is not None:
            self.COST = dvm_config.COST

        dvm_config.SUPPORTED_DVMS = [self]
        dvm_config.DB = "db/" + self.NAME + ".db"
        dvm_config.NIP89 = self.NIP89_announcement(nip89config)
        self.dvm_config = dvm_config
        self.admin_config = admin_config


    def run(self):
        nostr_dvm_thread = Thread(target=self.DVM, args=[self.dvm_config, self.admin_config])
        nostr_dvm_thread.start()


    def is_input_supported(self, input_type, input_content) -> bool:
        """Check if input is supported for current Task."""
        pass

    def create_request_form_from_nostr_event(self, event, client=None, dvm_config=None) -> dict:
        """Parse input into a request form that will be given to the process method"""
        pass

    def process(self, request_form):
        "Process the data and return the result"
        pass

    @staticmethod
    def set_options(request_form):
        print("Setting options...")
        opts = []
        if request_form.get("options"):
            opts = json.loads(request_form["options"])
            print(opts)

        return dict(opts)