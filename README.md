# PyJourney

PyJourney is a versatile Python module that provides both a command-line tool and a programmable class to generate images with the Midjourney bot via Discord using Selenium in the backend.

## Key Features

- **Command-Line Interface**: PyJourney includes a command-line tool that allows users to quickly send prompts to the Midjourney bot and retrieve generated images, all from the terminal.
- **Programmable Class**: For more advanced use cases, PyJourney offers a Python class that can be integrated into scripts and applications, providing greater flexibility and control over the image generation process.

With PyJourney, users can effortlessly create images using Midjourney's AI, either through simple command-line commands or by embedding PyJourney's capabilities into larger Python applications.

## Requirements

Before using PyJourney, ensure you meet the following requirements:

1. **Discord Account**: You must have an active Discord account.
2. **Midjourney Subscription**: A paid subscription to Midjourney is necessary, as PyJourney interacts with the Midjourney bot via private messages, which are available only to paying members.
3. **Environment Variables**: Create an `.env` file in your project's root directory with the following variables:
    - `DISCORD_EMAIL`: Your Discord account's email.
    - `DISCORD_PASSWORD`: Your Discord account's password.
    - `DISCORD_MIDJOURNEY_BOT_CHANNEL_URL`: The URL of the Discord channel where the Midjourney bot is located. You can get this URL by navigating to your Discord channel with the Midjourney bot, clicking on the gear icon next to the channel name, and copying the 'Channel Link'.

Example `.env` file content:
```env
EXPORT DISCORD_EMAIL='your_email@example.com'
EXPORT DISCORD_PASSWORD='yourPassword123'
EXPORT DISCORD_MIDJOURNEY_BOT_CHANNEL_URL='https://discord.com/channels/.../...'
```

Remember to source this `.env` file in your terminal session before running pyjourney:

```bash
source .env
```


## Limitations

PyJourney has a few limitations to keep in mind:

- **Subscription Requirement**: As PyJourney sends private messages to the Midjourney bot, a paid Midjourney subscription is required.
- **Single Image Processing**: Currently, PyJourney is designed to process only one image at a time.
- **Exclusive Account Use**: Ensure that the Discord account is not being used elsewhere while PyJourney is running, as concurrent use may interfere with the bot's operation.
- **Authentication Method**: PyJourney uses your Discord email and password for authentication. It does not utilize Discord's API for login, which means you need to provide these credentials directly.
- **Environment Variables**: You need to provide the required environment variables (as described in the Requirements section above) before running pyjourney. In a future version I might introduce a better way of storing credentials in an encrypted form and managed by the tool so that you don't have to deal with this.

### Example Usage of PyJourney

Here is a simple example demonstrating how to use the `PyJourney` class to generate an image from a textual prompt:

```python
from pyjourney import PyJourney

# Initialize PyJourney with your Discord credentials.
# Ensure these environment variables are set: DISCORD_EMAIL, DISCORD_PASSWORD
# and DISCORD_MIDJOURNEY_BOT_CHANNEL_URL to point to the Midjourney bot channel where you want to send prompts.
mj_api = PyJourney()

# Set your prompt and the desired number of images (1-4).
prompt = "a futuristic city skyline at dusk"
num_images = 1  # In this example, we only want to generate one image.
images = mj_api.imagine(prompt=prompt, num_images=num_images)
```

In this example, we have used the `.imagine()` method to send the prompt "a futuristic city skyline at dusk" to the Midjourney bot and requested to generate one image. The image is returned in the images variable.