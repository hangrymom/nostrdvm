import os
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

import dotenv
from nostr_sdk import Filter, Tag, Keys, EventBuilder, Client, EventId, PublicKey, Event, Timestamp, SingleLetterTag, \
    Alphabet
from nostr_sdk.nostr_sdk import Duration

from nostr_dvm.utils import definitions
from nostr_dvm.utils.definitions import EventDefinitions
from nostr_dvm.utils.nostr_utils import send_event


class NIP88Config:
    DTAG: str = ""
    TITLE: str = ""
    CONTENT: str = ""
    IMAGE: str = ""
    TIER_EVENT: str = ""
    PERK1DESC: str = ""
    PERK2DESC: str = ""
    PERK3DESC: str = ""
    PERK4DESC: str = ""
    PAYMENT_VERIFIER_PUBKEY: str = ""

    AMOUNT_DAILY: int = None
    AMOUNT_MONTHLY: int = None
    AMOUNT_YEARLY: int = None

def nip88_create_d_tag(name, pubkey, image):
    key_str = str(name + image + pubkey)
    d_tag = sha256(key_str.encode('utf-8')).hexdigest()[:16]
    return d_tag


def fetch_nip88_parameters_for_deletion(keys, eventid, client, dvmconfig):
    idfilter = Filter().id(EventId.from_hex(eventid)).limit(1)
    nip88events = client.get_events_of([idfilter], timedelta(seconds=dvmconfig.RELAY_TIMEOUT))
    d_tag = ""
    if len(nip88events) == 0:
        print("Event not found. Potentially gone.")

    for event in nip88events:
        print(event.as_json())
        for tag in event.tags():
            if tag.as_vec()[0] == "d":
                d_tag = tag.as_vec()[1]
        if d_tag == "":
            print("No dtag found")
            return

        if event.author().to_hex() == keys.public_key().to_hex():
            nip88_delete_announcement(event.id().to_hex(), keys, d_tag, client, dvmconfig)
            print("NIP88 announcement deleted from known relays!")
        else:
            print("Privatekey does not belong to event")


def fetch_nip88_event(keys, eventid, client, dvmconfig):
    idfilter = Filter().id(EventId.parse(eventid)).limit(1)
    nip88events = client.get_events_of([idfilter], timedelta(seconds=dvmconfig.RELAY_TIMEOUT))
    d_tag = ""
    if len(nip88events) == 0:
        print("Event not found. Potentially gone.")

    for event in nip88events:

        for tag in event.tags():
            if tag.as_vec()[0] == "d":
                d_tag = tag.as_vec()[1]
        if d_tag == "":
            print("No dtag found")
            return

        if event.author().to_hex() == keys.public_key().to_hex():
            print(event.as_json())
        else:
            print("Privatekey does not belong to event")


def nip88_delete_announcement(eid: str, keys: Keys, dtag: str, client: Client, config):
    e_tag = Tag.parse(["e", eid])
    a_tag = Tag.parse(
        ["a", str(EventDefinitions.KIND_NIP88_TIER_EVENT) + ":" + keys.public_key().to_hex() + ":" + dtag])
    event = EventBuilder(5, "", [e_tag, a_tag]).to_event(keys)
    send_event(event, client, config)


def nip88_has_active_subscription(user: PublicKey, tiereventdtag, client: Client, dvm_config):
    subscription_status = {
        "isActive": False,
        "validUntil": 0,
        "subscriptionId": "",
    }

    subscriptionfilter = Filter().kind(definitions.EventDefinitions.KIND_NIP88_PAYMENT_RECIPE).pubkey(
        PublicKey.parse(dvm_config.PUBLIC_KEY)).custom_tag(SingleLetterTag.uppercase(Alphabet.P),
                                                           [user.to_hex()]).limit(1)
    evts = client.get_events_of([subscriptionfilter], timedelta(seconds=5))
    if len(evts) > 0:
        print(evts[0].as_json())
        matchesdtag = False
        for tag in evts[0].tags():
            if tag.as_vec()[0] == "valid":
                subscription_status["validUntil"] = int(tag.as_vec()[2])
            elif tag.as_vec()[0] == "e":
                subscription_status["subscriptionId"] = tag.as_vec()[1]
            elif tag.as_vec()[0] == "tier":
                if tag.as_vec()[1] == tiereventdtag:
                    matchesdtag = True

        if subscription_status["validUntil"] > Timestamp.now().as_secs() & matchesdtag:
            subscription_status["isActive"] = True

    return subscription_status


def nip88_announce_tier(dvm_config, client):
    title_tag = Tag.parse(["title", str(dvm_config.NIP88.TITLE)])
    image_tag = Tag.parse(["image", str(dvm_config.NIP88.IMAGE)])
    d_tag = Tag.parse(["d", dvm_config.NIP88.DTAG])

    # may todo
    zaptag1 = Tag.parse(["zap", dvm_config.PUBLIC_KEY, "wss://damus.io", "19"])
    zaptag2 = Tag.parse(["zap", "", "wss://damus.io", "1"])
    p_tag = Tag.parse(["p", dvm_config.NIP88.PAYMENT_VERIFIER_PUBKEY])

    tags = [title_tag, image_tag, zaptag1, zaptag2, d_tag, p_tag]

    if dvm_config.NIP88.AMOUNT_DAILY is not None:
        amount_tag = Tag.parse(["amount", str(dvm_config.NIP88.AMOUNT_DAILY * 1000), "msats", "daily"])
        tags.append(amount_tag)

    if dvm_config.NIP88.AMOUNT_MONTHLY is not None:
        amount_tag = Tag.parse(["amount", str(dvm_config.NIP88.AMOUNT_MONTHLY * 1000), "msats", "monthly"])
        tags.append(amount_tag)

    if dvm_config.NIP88.AMOUNT_YEARLY is not None:
        amount_tag = Tag.parse(["amount", str(dvm_config.NIP88.AMOUNT_YEARLY * 1000), "msats", "yearly"])
        tags.append(amount_tag)

    if dvm_config.NIP88.PERK1DESC != "":
        perk_tag = Tag.parse(["perk", str(dvm_config.NIP88.PERK1DESC)])
        tags.append(perk_tag)
    if dvm_config.NIP88.PERK2DESC != "":
        perk_tag = Tag.parse(["perk", str(dvm_config.NIP88.PERK2DESC)])
        tags.append(perk_tag)
    if dvm_config.NIP88.PERK3DESC != "":
        perk_tag = Tag.parse(["perk", str(dvm_config.NIP88.PERK3DESC)])
        tags.append(perk_tag)
    if dvm_config.NIP88.PERK4DESC != "":
        perk_tag = Tag.parse(["perk", str(dvm_config.NIP88.PERK4DESC)])
        tags.append(perk_tag)

    keys = Keys.parse(dvm_config.NIP89.PK)
    content = dvm_config.NIP88.CONTENT
    event = EventBuilder(EventDefinitions.KIND_NIP88_TIER_EVENT, content, tags).to_event(keys)
    annotier_id = send_event(event, client=client, dvm_config=dvm_config)

    print("Announced NIP 88 Tier for " + dvm_config.NIP89.NAME)
    return annotier_id

    # Relay and payment-verification


# ["r", "wss://my-subscribers-only-relay.com"],
# ["p", "<payment-verifier-pubkey>"],

def check_and_set_d_tag_nip88(identifier, name, pk, imageurl):
    if not os.getenv("NIP88_DTAG_" + identifier.upper()):
        new_dtag = nip88_create_d_tag(name, Keys.parse(pk).public_key().to_hex(),
                                      imageurl)
        nip88_add_dtag_to_env_file("NIP88_DTAG_" + identifier.upper(), new_dtag)
        print("Some new dtag:" + new_dtag)
        return new_dtag
    else:
        return os.getenv("NIP88_DTAG_" + identifier.upper())


def check_and_set_tiereventid_nip88(identifier, index="1", eventid=None):
    if eventid is None:
        if not os.getenv("NIP88_TIEREVENT_" + index + identifier.upper()):
            print("No Tier Event ID set")
            return None
        else:
            return os.getenv("NIP88_TIEREVENT_" + index + identifier.upper())
    else:
        nip88_add_dtag_to_env_file("NIP88_TIEREVENT_" + index + identifier.upper(), eventid)
        return eventid


def nip88_add_dtag_to_env_file(dtag, oskey):
    env_path = Path('.env')
    if env_path.is_file():
        print(f'loading environment from {env_path.resolve()}')
        dotenv.load_dotenv(env_path, verbose=True, override=True)
        dotenv.set_key(env_path, dtag, oskey)

