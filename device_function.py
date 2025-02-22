import os
import threading
import sys
import time

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from StreamDeck.Transport.Transport import TransportError
from networktables import NetworkTables
from ntcore import *
from wpilib import SmartDashboard

# Folder location of image assets used by this example.
ASSETS_PATH = os.path.join(os.path.dirname(__file__), "attributes")

# NetworkTables.initialize(server = "10.32.0.2")
NetworkTables.initialize(server = "localhost")
streamdeck_tables = NetworkTables.getTable("Stream_Deck")

global heartbeat_finnished
heartbeat_finnished = False

def heartbeat():
    i = 0
    global heartbeat_finnished
    while not heartbeat_finnished:
        streamdeck_tables.putNumber("Stream Deck HeartBeat", i)
        time.sleep(1)
        i += 1

# Generates a custom tile with run-time generated text and custom image via the
# PIL module.
def render_key_image(deck, icon_filename, font_filename, label_text):
    # Resize the source image asset to best-fit the dimensions of a single key,
    # leaving a margin at the bottom so that we can draw the key title
    # afterwards.
    icon = Image.open(icon_filename)
    image = PILHelper.create_scaled_key_image(deck, icon, margins=[0, 0, 0, 0])

    # Load a custom TrueType font and use it to overlay the key index, draw key
    # label onto the image a few pixels from the bottom of the key.
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_filename, 14)
    draw.text((image.width / 2, image.height - 5), text=label_text, font=font, anchor="ms", fill="white")

    return PILHelper.to_native_key_format(deck, image)


# Returns styling information for a key based on its position and state.
def get_key_style(deck, key, state):
    keys = {0: {"name": "L4",
                "icon": "{}.png".format("L4"),
                "font": "Roboto-Regular.ttf",
                "label": ""},
            1: {"name": "R4",
                "icon": "{}.png".format("R4"),
                "font": "Roboto-Regular.ttf",
                "label": ""},
            2: {"name": "Remove Algae Upper",
                "icon": "{}.png".format("WIP"),
                "font": "Roboto-Regular.ttf",
                "label": "Remove Upper Algae"},
            3: {"name": "exit",
                "icon": "{}.png".format("TeamLogo"),
                "font": "Roboto-Regular.ttf",
                "label": ""},
            4: {"name": "Net",
                "icon": "{}.png".format("WIP"),
                "font": "Roboto-Regular.ttf",
                "label": "Net"},
            5: {"name": "L3",
                "icon": "{}.png".format("L3"),
                "font": "Roboto-Regular.ttf",
                "label": ""},
            6: {"name": "R3",
                "icon": "{}.png".format("R3"),
                "font": "Roboto-Regular.ttf",
                "label": ""},
            7: {"name": "Remove Algae Lower",
                "icon": "{}.png".format("WIP"),
                "font": "Roboto-Regular.ttf",
                "label": "Remove Lower Algae"},
            8: {"name": "Algae Intake",
                "icon": "{}.png".format("WIP"),
                "font": "Roboto-Regular.ttf",
                "label": "Algae Intake"},
            9: {"name": "Eject Algae",
                "icon": "{}.png".format("WIP"),
                "font": "Roboto-Regular.ttf",
                "label": "Eject Algae"},
            10: {"name": "L2",
                "icon": "{}.png".format("L2"),
                "font": "Roboto-Regular.ttf",
                "label": ""},
            11: {"name": "R2",
                "icon": "{}.png".format("R2"),
                "font": "Roboto-Regular.ttf",
                "label": ""},
            12: {"name": "Trough",
                "icon": "{}.png".format("WIP"),
                "font": "Roboto-Regular.ttf",
                "label": "Trough"},
            13: {"name": "Ground Coral Intake",
                "icon": "{}.png".format("WIP"),
                "font": "Roboto-Regular.ttf",
                "label": "Ground Coral Intake"},
            14: {"name": "Eject Coral",
                "icon": "{}.png".format("WIP"),
                "font": "Roboto-Regular.ttf",
                "label": "Eject Coral"}}

    # if key == keys[0]:
    #     name = keys[0]["name"]
    #     icon = keys[0]["icon"]
    #     font = keys[0]["font"]
    #     label = keys[0]["label"]
    # elif key == keys[1]:
    #     name = keys[1]["name"]
    #     icon = keys[1]["icon"]
    #     font = keys[1]["font"]
    #     label = keys[1]["label"]
    # else:
    #     name = keys[14]["name"]
    #     icon = keys[14]["icon"]
    #     font = keys[14]["font"]
    #     label = keys[14]["label"]

        # name = "emoji"
        # icon = "{}.png".format("the last of em" if state else "the_third_image")
        # font = "Roboto-Regular.ttf"
        # label = "Pressed!" if state else "Key {}".format(key)

    return {
        "name": keys[key]["name"],
        "icon": os.path.join(ASSETS_PATH, keys[key]["icon"]),
        "font": os.path.join(ASSETS_PATH, keys[key]["font"]),
        "label": keys[key]["label"]
    }


# Creates a new key image based on the key index, style and current key state
# and updates the image on the StreamDeck.
def update_key_image(deck, key, state):
    # Determine what icon and label to use on the generated key.
    key_style = get_key_style(deck, key, state)

    # Generate the custom key with the requested image and label.
    image = render_key_image(deck, key_style["icon"], key_style["font"], key_style["label"])

    # Use a scoped-with on the deck to ensure we're the only thread using it
    # right now.
    with deck:
        # Update requested key with the generated image.
        deck.set_key_image(key, image)


# Prints key state change information, updates rhe key image and performs any
# associated actions when a key is pressed.
def key_change_callback(deck, key, state):
    # Print new key state
    print("Deck {} Key {} = {}".format(deck.id(), key, state), flush=True)    

    # Don't try to draw an image on a touch button
    if key >= deck.key_count():
        return

    # Update the key image based on the new key state.
    update_key_image(deck, key, state)

    # publishes key to networktables
    if state:
        streamdeck_tables.putNumber("pressedKey", key)
    else:
        streamdeck_tables.putNumber("pressedKey", -1)

    # Check if the key is changing to the pressed state.
    if state:
        key_style = get_key_style(deck, key, state)

        # When an exit button is pressed, close the application.
        if key_style["name"] == "exit":
            # Use a scoped-with on the deck to ensure we're the only thread
            # using it right now.
            with deck:
                # Reset deck, clearing all button images.
                deck.reset()

                # Close deck handle, terminating internal worker threads.
                deck.close()

                # Has its own thead, need to shut down to quit program
                NetworkTables.shutdown()

                global heartbeat_finnished
                heartbeat_finnished = True

if __name__ == "__main__":
    streamdecks = DeviceManager().enumerate()

    print("Found {} Stream Deck(s).\n".format(len(streamdecks)))

    for index, deck in enumerate(streamdecks):
        # This example only works with devices that have screens.
        if not deck.is_visual():
            continue

        deck.open()
        deck.reset()

        print("Opened '{}' device (serial number: '{}', fw: '{}')".format(
            deck.deck_type(), deck.get_serial_number(), deck.get_firmware_version()
        ))

        # Set initial screen brightness to 30%.
        deck.set_brightness(30)

        # Set initial key images.
        for key in range(deck.key_count()):
            update_key_image(deck, key, False)

        # Register callback function for when a key state changes.
        deck.set_key_callback(key_change_callback)

        t = threading.Thread(target=heartbeat)
        t.start()

        # Wait until all application threads have terminated (for this example,
        # this is when all deck handles are closed).
        for t in threading.enumerate():
            try:
                t.join()
            except RuntimeError:
                pass