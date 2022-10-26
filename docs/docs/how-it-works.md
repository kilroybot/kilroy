# How it works

The goal is to be able to train a bot to generate social media posts
that are the most likely to engage with the audience.

How to achieve that?

## Posts

Posts need to be "understandable" by the bot.
It means that posts need to be mapped to the "language" of the bot.

Fortunately, if we assume the posts are textual only, this is not a problem.
Textual content can be simply seen
as a sequence of tokens (words, punctuation, etc.)
that are known to the bot.

If we use sufficiently powerful language model
(e.g. [GPT-2](https://huggingface.co/gpt2)),
that supports techniques such as
[Byte-level Byte-Pair Encoding (BBPE)](https://arxiv.org/abs/1909.03341),
then any text can be handled without any loss of information.

Posts often contain other types of content, such as images, videos, etc.
**Kilroy** doesn't support them by default.
No default implementation of a module can handle them.
However, all faces and the dashboard can handle posts with text and images,
if you are able to create them in your module.
So feel free to create your own module that can handle generating such posts.

## Model

The bot is a model that consists of some parameters representing its knowledge.
When talking about textual content, the model is a language model.
It operates on a sequence of tokens from known vocabulary
and predicts the probability of the next token in the sequence.
This way you can generate a sequence of tokens that make up an entire post.

One example of a family of such models is
[Transformers](https://en.wikipedia.org/wiki/Transformer_(machine_learning_model)).
And one example of a specific model is [GPT-2](https://huggingface.co/gpt2).

## Scores

The bot needs to be able to evaluate the quality of a post.
The score should be a single number that represents how good the post is.
The higher the score, the better the post.

You need to choose how you want your posts to be scored.
For example, you can choose to maximize the number of
likes, comments, views, impressions or some function of them.

The goal is to achieve higher and higher scores over time.

## Training

If we have a model that can generate something and a way to evaluate it,
then we can train the model to generate better things.

More specifically, we can use
[reinforcement learning](https://en.wikipedia.org/wiki/Reinforcement_learning)
techniques to train the model to make decisions that result in higher rewards.
In our case, this means generating posts that see bigger numbers.
