# Example

This example shows how to use **kilroy**
to train a language model on some social media environment.

It uses
[GPT-2 from HuggingFace](https://huggingface.co/gpt2) as the language model
and targets [Discord](https://discord.com) as the environment.

## Prerequisites

First, you need to have a Discord bot token.
You can obtain one [here](https://discord.com/developers/applications).

Then, you need to find a channel in some Discord server,
which you want to use from training.

Paste the bot token and channel ID into appropriate entries in the `.env` file.

You also need to install Docker and Docker Compose.
You can get them [here](https://docs.docker.com/get-docker).

And lastly, you need to get the necessary files.
You can get them [here](https://github.com/kilroybot/kilroy/tree/master/example).

## Running

To run the example, simply run the following command:

```bash
docker-compose up
```

This will start all the services.
The web app will be available at
[`http://localhost:14000`](http://localhost:14000).

## Persistence

This stack uses Docker volumes to persist data.
The services save their state on exit and load it back on start.
