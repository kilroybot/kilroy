# Faces

If you want to use a social media platform that is not supported by default,
you should implement your own face that conforms to the API.
Then you can use it in the system without changing any other parts.

There are default faces for
[Discord](https://github.com/kilroybot/kilroy-face-discord)
and [Twitter](https://github.com/kilroybot/kilroy-face-twitter).

## API

All communication is done with gRPC.
The gRPC definitions for a face can be found
[here](https://kilroybot.github.io/proto/kilroy/face/v1alpha/face.proto).
You can use them to generate stubs that conform to the API
for your own implementation in any language.

## Packages

If you want to write your implementation in Python, you can use
[`kilroy-face-server-py-sdk`](https://github.com/kilroybot/kilroy-face-server-py-sdk)
to make it easier.
It already implements a lot of the boilerplate code
and provides a convenient interface
that you just need to fill in with your logic.
