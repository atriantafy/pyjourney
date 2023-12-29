#!/usr/bin/env python3
import os
import sys
import re
from typing import Union
import argparse
from io import BytesIO
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
import requests
from PIL import Image


class PyJourneyException(Exception):
    pass


class PyJourneyBannedPromptDetectedException(Exception):
    pass


class PyJourneyUnexpectedStatusException(Exception):
    pass


def error_print(s):
    sys.stderr.write(s)
    sys.stderr.write("\n")
    sys.stderr.flush()


class PyJourney:
    def __init__(
        self,
        discord_email: Union[str, None] = None,
        discord_password: Union[str, None] = None,
        discord_midjourney_bot_channel_url: Union[str, None] = None,
        headless: bool = True,
    ):
        self._discord_email = discord_email or os.environ.get("DISCORD_EMAIL")
        self._discord_password = discord_password or os.environ.get("DISCORD_PASSWORD")
        self._channel_url = discord_midjourney_bot_channel_url or os.environ.get(
            "DISCORD_MIDJOURNEY_BOT_CHANNEL_URL"
        )
        self._headless = headless

    def init_driver(self):
        # Initialize the Selenium WebDriver for Firefox
        options = Options()
        if self._headless:
            options.add_argument("--headless")
        self._driver = webdriver.Firefox(options=options)

    def login_to_discord(self):
        # Navigate to Discord login page and log in
        self._driver.get("https://discord.com/login")
        time.sleep(6)  # Wait for page to load

        # Enter email
        email_field = self._driver.find_element(By.NAME, "email")
        email_field.send_keys(self._discord_email)
        time.sleep(0.5)
        # Enter password
        password_field = self._driver.find_element(By.NAME, "password")
        password_field.send_keys(self._discord_password)
        password_field.send_keys(Keys.RETURN)

        time.sleep(5)  # Wait for Discord to log in

    def start_bot_chat(self):
        # Navigate to the specific channel where the Midjourney bot is and send a message
        self._driver.get(self._channel_url)
        time.sleep(10)  # Wait for channel to load

    def send_message_to_midjourney_bot(self, message):
        message_box = self._driver.find_element(
            By.XPATH, '//div[@role="textbox"][contains(@class,"slateTextArea")]'
        )
        message_box.click()
        message_box.send_keys(message)
        message_box.send_keys(Keys.RETURN)
        time.sleep(6)

    def close_driver(self):
        self._driver.quit()

    def get_image_url_from_message_id(self, message_id):
        message_element = self._driver.find_element(By.ID, message_id)
        link_element = message_element.find_element(By.CSS_SELECTOR, "a[href]")
        image_url = link_element.get_attribute("href")
        return image_url

    @staticmethod
    def split_image(image_url):
        response = requests.get(image_url)
        if response.status_code != 200:
            return None

        original_image = Image.open(BytesIO(response.content))

        width, height = original_image.size
        sub_image_width = width // 2
        sub_image_height = height // 2

        images = []
        for i in range(2):
            for j in range(2):
                left = j * sub_image_width
                upper = i * sub_image_height
                right = left + sub_image_width
                lower = upper + sub_image_height

                cropped_image = original_image.crop((left, upper, right, lower))
                images.append(cropped_image)

        return images

    @staticmethod
    def save_image(image, filename):
        # Extract the format from the filename
        format = filename.split(".")[-1].upper()
        if format != "JPG":
            raise PyJourneyException("Can only save in .jpg format!")
        # Save the image with the extracted format
        image.save(filename, format="JPEG")

    def get_element_text_by_id(self, element_id):
        element = self._driver.find_element(By.ID, element_id)
        text = element.text
        return text

    @staticmethod
    def handle_status_text(status_text: str):
        if "banned" in status_text.lower():
            raise PyJourneyBannedPromptDetectedException(status_text)
        # pattern = r"@(\S+) \((.*)\)"
        pattern = r"@(\S+) \(([^()]+)\)"
        match = re.search(pattern, status_text)
        if match:
            username = match.group(1)
            status = match.group(2)
            error_print(f"Current status for @{username}: {status}")
        else:
            raise PyJourneyUnexpectedStatusException(status_text)

    def get_4_images(self, prev_last_message_id):
        process_started_message_id = self.get_last_message_id()
        status_text = self.get_element_text_by_id(process_started_message_id)
        PyJourney.handle_status_text(status_text)
        while process_started_message_id == prev_last_message_id:
            time.sleep(0.5)
            process_started_message_id = self.get_last_message_id()
            status_text = self.get_element_text_by_id(process_started_message_id)
            PyJourney.handle_status_text(status_text)

        error_print(f"Process started ({process_started_message_id}) ...")
        result_message_id = self.get_last_message_id()
        while result_message_id == process_started_message_id:
            time.sleep(0.5)
            result_message_id = self.get_last_message_id()
        error_print(f"Image Generation Complete ({result_message_id})")

        image_url = self.get_image_url_from_message_id(result_message_id)
        error_print(f"Extracted Image: {image_url}")
        images = PyJourney.split_image(image_url=image_url)
        return images

    def get_last_message_id(self):
        messages = self._driver.find_elements(
            By.XPATH, "//li[starts-with(@id, 'chat-messages-')]"
        )

        if messages:
            return messages[-1].get_attribute("id")
        else:
            return None

    def imagine(
        self,
        prompt: str,
        num_images: int,
        filename_prefix: Union[str, None] = None,
        aspect_ratio: str = "16:9",
    ):
        if num_images < 0 or num_images > 4:
            raise PyJourneyException("num_images can be between 1 and 4")
        if not self._discord_email or not self._discord_password:
            raise PyJourneyException("Discord credentials are not set")
        error_print("Connecting to Discord ...")
        self.init_driver()
        try:
            self.login_to_discord()

            self.start_bot_chat()

            last_message_id = self.get_last_message_id()

            self.send_message_to_midjourney_bot(
                f"/imagine prompt: {prompt} --ar {aspect_ratio}"
            )

            images = self.get_4_images(last_message_id)
            if filename_prefix is not None:
                for i in range(num_images):
                    filename = f"{filename_prefix}{i}.jpg"
                    PyJourney.save_image(images[i], filename)
                    error_print(f"Saved image in {filename}")
            return images[:num_images]
        finally:
            self.close_driver()


def check_env_vars():
    for var_name in [
        "DISCORD_EMAIL",
        "DISCORD_PASSWORD",
        "DISCORD_MIDJOURNEY_BOT_CHANNEL_URL",
    ]:
        if os.environ.get(var_name) is None:
            error_print(
                f"You must set the environment variable '{var_name}' before running this script."
            )
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Midjourney Images")
    parser.add_argument("prompt", type=str, help="Prompt to send to Midjourney bot")
    parser.add_argument(
        "filename_prefix", type=str, help="Filename prefix for saved images"
    )
    parser.add_argument(
        "--num_images",
        type=int,
        default=4,
        choices=range(1, 5),
        help="Number of images to save (1-4). Default is 4.",
    )
    parser.add_argument(
        "--aspect_ratio",
        type=str,
        default="16:9",
        help="Aspect ratio for the images (default: '16:9').",
    )

    args = parser.parse_args()

    check_env_vars()

    mj_api = PyJourney()

    mj_api.imagine(
        prompt=args.prompt,
        filename_prefix=args.filename_prefix,
        num_images=args.num_images,
        aspect_ratio=args.aspect_ratio,
    )
