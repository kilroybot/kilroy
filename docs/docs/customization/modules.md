# Modules

If you want to use a model that is not supported by default,
you should implement your own module that conforms to the API.
Then you can use it in the system without changing any other parts.

There is a default implementation for any models that are supported by
[HuggingFace](https://github.com/kilroybot/kilroy-module-huggingface).

## API

All communication is done with gRPC.
The gRPC definitions for a module can be found
[here](https://kilroybot.github.io/proto/kilroy/module/v1alpha/module.proto).
You can use them to generate stubs that conform to the API
for your own implementation in any language.

## Packages

If you want to write your implementation in Python, you can use
[`kilroy-module-server-py-sdk`](https://github.com/kilroybot/kilroy-module-server-py-sdk)
to make it easier.
It already implements a lot of the boilerplate code
and provides a convenient interface
that you just need to fill in with your logic.

Furthermore,
if you want to use a [PyTorch](https://pytorch.org/) model, you can use
[`kilroy-module-pytorch-py-sdk`](https://github.com/kilroybot/kilroy-module-pytorch-py-sdk)
to make it even easier.
It's provides boilerplate code to help working with PyTorch models.
