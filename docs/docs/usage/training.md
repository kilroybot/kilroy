# Training

Training is at the core of the system.
And you should be always training, as peoples reactions change over time.

## Modes

There are two modes of training, each covering a different use case.
For optimal performance, you should alternate between both modes.

### Offline

Offline mode enables you to train your model on a dataset of past posts.
This is useful to make your model used to
a specific style of internet language.
In most cases, you will be using some model pretrained on a large dataset
of articles written in formal English.
Then it's a good idea to adjust the model
so that it's able to "speak" in a way more similar to the language
used on a social media channel where you want to use it.

It uses simple supervised learning.

This process is pretty straightforward and should almost always result in
convergence with the proper parameters.
But watch out for overfitting, as it's easy to do.

Generally, you want your model to generate text
that is only stylistically similar to the existing posts
and not to copy them.

The face is responsible for defining
where exactly the existing posts are coming from.

### Online

Online mode works by constantly generating new posts, posting them and
then using the reactions to the posts as feedback to improve the model.

It uses reinforcement learning.

This is the most powerful mode,
as it allows you to train your model to generate posts
that are actually liked by the audience.
But it's also the most difficult to use,
as it requires a lot of tuning and experimentation.
It's also the most time-consuming,
as you need to wait for the reactions from people to come in,
and you can't post too often, as it will only annoy and distract your audience.

The controller is responsible for scheduling the generation of new posts
and the evaluation of the reactions to the posts.

## Dashboard

You can monitor and control the training process in the dashboard.

There is a quick view of the training status
and a detailed view of all the metrics.

You can control the training process by starting and stopping it.

![Training page](assets/pages/training.png){ loading=lazy } Training page
