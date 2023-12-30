#!/usr/bin/env python3
"""
PyJourney: A Python module for automating interactions with the Midjourney bot in Discord.

This module enables automated sending of prompts to the Midjourney bot, handling of
responses, and image retrieval using Selenium WebDriver. It's designed to simplify
the process of generating images through the Midjourney bot on Discord.

Classes:
- PyJourney: Handles bot interactions and image retrieval.

Usage:
Intended for users automating Midjourney bot interactions, particularly for image
generation based on textual prompts.
"""
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
from hashlib import md5
import diskcache

DEFAULT_IMAGE_FETCH_TIMEOUT = 60 * 5
DEFAULT_CACHE_TTL = 60 * 60 * 24  # 1 Day


class PyJourneyException(Exception):
    """
    Base exception for errors specific to the PyJourney class.

    This exception is raised for general errors related to the PyJourney class's
    operations, such as invalid arguments or configuration issues.
    """


class PyJourneyBannedPromptDetectedException(Exception):
    """
    Exception raised when a banned prompt is detected by the Midjourney bot.

    This exception is specifically used to indicate that the provided prompt to
    the Midjourney bot has been flagged as banned, prohibiting further processing.
    """


class PyJourneyImageNotFoundInMessage(Exception):
    """
    Exception raised when an expected image is not found in a Discord message.

    This exception indicates that an image URL was expected to be found in a
    specific Discord message, but was not present. This may occur if the bot
    response does not include an image or if the image extraction fails.
    """


class PyJourneyUnexpectedStatusException(Exception):
    """
    Exception raised for unexpected status messages from the Midjourney bot
    which prevents us from retrieving the final image.

    This exception is used when the status message received from the Midjourney bot
    contains content that is not anticipated or is in an unexpected format, suggesting
    a possible issue with the bot's response or a change in its output format.
    """


def error_print(s: str):
    """
    Print an error message to standard error (stderr).

    This function writes a given string `s` to the stderr and ensures it's immediately flushed,
    making it useful for logging error messages.

    Args:
        s (str): The error message to be printed.
    """
    sys.stderr.write(s)
    sys.stderr.write("\n")
    sys.stderr.flush()


class PyJourney:
    """
    A class to interface with the Midjourney bot on Discord using Selenium WebDriver.

    This class automates interactions with Discord's Midjourney bot, including logging
    in to Discord, navigating to the bot's channel, sending messages, and retrieving
    image URLs.

    Attributes:
        discord_email (str): Email for Discord. Fetched from environment variables
                            if not provided.
        discord_password (str): Password for Discord. Fetched from environment
                                variables if not provided.
        discord_midjourney_bot_channel_url (str): URL of the Discord channel with
                                                the Midjourney bot.
        headless (bool): If true, runs WebDriver in headless mode.
    """

    def __init__(
        self,
        discord_email: Union[str, None] = None,
        discord_password: Union[str, None] = None,
        discord_midjourney_bot_channel_url: Union[str, None] = None,
        headless: bool = True,
    ):
        self._driver = None
        self._discord_email = discord_email or os.environ.get("DISCORD_EMAIL")
        self._discord_password = discord_password or os.environ.get("DISCORD_PASSWORD")
        self._channel_url = discord_midjourney_bot_channel_url or os.environ.get(
            "DISCORD_MIDJOURNEY_BOT_CHANNEL_URL"
        )
        self._headless = headless

    def _init_driver(self):
        """
        Initialize the Selenium WebDriver for Firefox.
        """
        options = Options()
        if self._headless:
            options.add_argument("--headless")
        self._driver = webdriver.Firefox(options=options)

    def _login_to_discord(self):
        """
        Log in to Discord using the provided credentials.

        This method navigates to the Discord login page and performs an automated
        login using the email and password attributes of the PyJourney class.
        """
        self._driver.get("https://discord.com/login")
        time.sleep(6)
        # Enter email
        email_field = self._driver.find_element(By.NAME, "email")
        email_field.send_keys(self._discord_email)
        time.sleep(0.5)
        # Enter password
        password_field = self._driver.find_element(By.NAME, "password")
        password_field.send_keys(self._discord_password)
        password_field.send_keys(Keys.RETURN)
        time.sleep(5)

    def _start_bot_chat(self):
        """
        Navigate to the Discord channel where the Midjourney bot is located.
        """
        self._driver.get(self._channel_url)
        time.sleep(10)

    def _send_message_to_midjourney_bot(self, message: str):
        """
        Send a message to the Midjourney bot in Discord.

        Args:
            message (str): The message to be sent to the Midjourney bot.
        """
        message_box = self._driver.find_element(
            By.XPATH, '//div[@role="textbox"][contains(@class,"slateTextArea")]'
        )
        message_box.click()
        message_box.send_keys(message)
        message_box.send_keys(Keys.RETURN)
        time.sleep(6)

    def _close_driver(self):
        """
        Close the Selenium WebDriver.
        """
        self._driver.quit()

    def _get_image_url_from_message_id(self, message_id: str) -> str:
        """
        Retrieve the image URL from a Discord message.

        Args:
            message_id (str): The ID of the Discord message containing the image link.

        Returns:
            str: The URL of the image in the specified message.
        """
        message_element = None
        link_element = None
        image_url = None
        try:
            message_element = self._driver.find_element(By.ID, message_id)
            link_element = message_element.find_element(By.CSS_SELECTOR, "a[href]")
            image_url = link_element.get_attribute("href")
            return image_url
        except Exception as exc:
            error_msg = f"Could not extract image URL from message_id: {message_id}"
            if message_element is not None:
                error_msg += (
                    "\nmessage_element:\n"
                    + message_element.get_attribute("outerHTML")
                    + "\n\n"
                )
            if link_element is not None:
                error_msg += (
                    "\nlink_element:\n"
                    + link_element.get_attribute("outerHTML")
                    + "\n\n"
                )
            raise PyJourneyImageNotFoundInMessage(error_msg) from exc

    @staticmethod
    def _split_image(image_url: str) -> list:
        """
        Split a single image from the given URL into four sub-images.

        This method downloads the image from the provided URL and splits it into four equal parts.

        Args:
            image_url (str): URL of the image to be split.

        Returns:
            List[Image]: A list of four PIL Image objects, each representing a quarter of the original image.
        """
        response = requests.get(image_url, timeout=DEFAULT_IMAGE_FETCH_TIMEOUT)
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
    def save_image(image: Image, filename: str):
        """
        Save a PIL Image object to a file.

        This method saves the given PIL Image object to a file with the specified filename,
        currently only supporting JPEG format.

        Args:
            image (Image): The PIL Image object to be saved.
            filename (str): The filename for the saved image, including the '.jpg' extension.

        Raises:
            PyJourneyException: If the file format is not JPEG.
        """
        if filename.split(".")[-1].upper() != "JPG":
            raise PyJourneyException("Can only save in .jpg format!")
        image.save(filename, format="JPEG")

    def _get_element_text_by_id(self, element_id: str) -> str:
        """
        Retrieve the text from a webpage element identified by its ID.

        Args:
            element_id (str): The ID of the element from which text is to be extracted.

        Returns:
            str: The text content of the specified element.
        """
        element = self._driver.find_element(By.ID, element_id)
        text = element.text
        return text

    @staticmethod
    def _handle_status_text(status_text: str):
        """
        Analyze and respond to the status text from the Midjourney bot.

        This method processes the status text received from the bot, checking for
        any indications of a banned prompt or other issues. It raises specific
        exceptions for different error conditions detected in the status text.

        Args:
            status_text (str): The status text to be analyzed.

        Raises:
            PyJourneyBannedPromptDetectedException: If the prompt is detected as banned.
            PyJourneyUnexpectedStatusException: If the status text contains unexpected content.
        """
        if "banned" in status_text.lower():
            raise PyJourneyBannedPromptDetectedException(status_text)
        pattern = r"@(\S+) \(([^()]+)\)"
        match = re.search(pattern, status_text)
        if match:
            username = match.group(1)
            status = match.group(2)
            error_print(f"Current status for @{username}: {status}")
        else:
            raise PyJourneyUnexpectedStatusException(status_text)

    def _get_4_images(self, prev_last_message_id: str) -> list:
        """
        Retrieve up to four images generated by the Midjourney bot.

        This method waits for new messages from the Midjourney bot after a prompt
        is sent, extracts the image URLs from the messages, and downloads and splits
        the images.

        Args:
            prev_last_message_id (str): The ID of the last message before sending the prompt.

        Returns:
            List[Image]: A list of up to four PIL Image objects generated by the Midjourney bot.
        """
        process_started_message_id = self._get_last_message_id()
        status_text = self._get_element_text_by_id(process_started_message_id)
        PyJourney._handle_status_text(status_text)
        while process_started_message_id == prev_last_message_id:
            time.sleep(0.5)
            process_started_message_id = self._get_last_message_id()
            status_text = self._get_element_text_by_id(process_started_message_id)
            PyJourney._handle_status_text(status_text)

        error_print(f"Process started ({process_started_message_id}) ...")
        result_message_id = self._get_last_message_id()
        while result_message_id == process_started_message_id:
            time.sleep(0.5)
            result_message_id = self._get_last_message_id()
        error_print(f"Image Generation Complete ({result_message_id})")

        image_url = self._get_image_url_from_message_id(result_message_id)
        error_print(f"Extracted Image: {image_url}")
        images = PyJourney._split_image(image_url=image_url)
        return images

    def _get_last_message_id(self):
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
        use_cache_file: Union[str, None] = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
    ) -> list:
        """
        Generate and retrieve images based on a given prompt using the Midjourney bot.

        This method sends a prompt to the Midjourney bot, waits for image generation,
        and saves the resulting images with an optional filename prefix. It handles
        connecting to Discord, navigating to the bot channel, sending the prompt,
        and processing the images. Optionally, it uses a disk cache to store and
        retrieve images based on the prompt and aspect ratio.

        Args:
            prompt (str): The prompt for the Midjourney bot.
            num_images (int): Number of images to generate (1-4).
            filename_prefix (Union[str, None]): Prefix for saved image filenames.
            aspect_ratio (str): Aspect ratio for images (e.g., "16:9").
            use_cache_file (Union[str, None]): Path to the cache file. If provided,
                cached images are used to avoid regenerating images for the same prompt.
                If None, caching is not used.
            cache_ttl (float): Time-to-live for cache entries, in seconds.

        Returns:
            List[Image]: PIL Image objects representing the generated images.

        Raises:
            PyJourneyException: If num_images is outside 1-4, or if Discord
                                credentials are not set.
            PyJourneyBannedPromptDetectedException: If the prompt is banned.
            PyJourneyUnexpectedStatusException: If unexpected content in bot's
                                                status message.
            Selenium WebDriver exceptions: Various exceptions from WebDriver
                                            operations, like connection issues.
        """

        if num_images < 0 or num_images > 4:
            raise PyJourneyException("num_images can be between 1 and 4")
        cache_key = md5(f"{prompt}_{aspect_ratio}".encode("utf-8")).hexdigest()
        if use_cache_file is not None:
            cache = diskcache.Cache(use_cache_file)
        else:
            cache = None

        if cache is not None and cache_key in cache:
            four_images = cache.get(cache_key)
        else:
            four_images = None

        if four_images is None:
            if not self._discord_email or not self._discord_password:
                raise PyJourneyException("Discord credentials are not set")
            error_print("Connecting to Discord ...")
            self._init_driver()
            try:
                self._login_to_discord()

                self._start_bot_chat()

                last_message_id = self._get_last_message_id()

                self._send_message_to_midjourney_bot(
                    f"/imagine prompt: {prompt} --ar {aspect_ratio}"
                )

                four_images = self._get_4_images(last_message_id)
                if cache is not None:
                    cache.set(cache_key, four_images, cache_ttl)
            finally:
                self._close_driver()

        if filename_prefix is not None:
            for i in range(num_images):
                filename = f"{filename_prefix}{i}.jpg"
                PyJourney.save_image(four_images[i], filename)
        return four_images[:num_images]


def _check_env_vars():
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


def main():
    """
    Entry point for the pyjourney command-line interface.

    Parses command-line arguments and executes the image
    generation process using the PyJourney class.
    """

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
    parser.add_argument(
        "--use_cache_file",
        type=str,
        default=None,
        help="If set, use this file for caching images. Default is None.",
    )
    args = parser.parse_args()

    _check_env_vars()

    mj_api = PyJourney()

    try:
        images = mj_api.imagine(
            prompt=args.prompt,
            filename_prefix=args.filename_prefix,
            num_images=args.num_images,
            aspect_ratio=args.aspect_ratio,
            use_cache_file=args.use_cache_file,
        )
        error_print("Image generation completed successfully.")
        for i, img in enumerate(images):
            filename = f"{args.filename_prefix}{i}.jpg"
            PyJourney.save_image(img, filename)
            error_print(f"Saved image in {filename}")
    except Exception as e:
        error_print(f"Error during image generation: {str(e)}")


if __name__ == "__main__":
    main()
