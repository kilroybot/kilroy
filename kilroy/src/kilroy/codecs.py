from kilroyshare.codec import Codec
from torch import Tensor, tensor
from transformers import AutoTokenizer


class HuggingFaceCodec(Codec[Tensor, str]):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.tokenizer = AutoTokenizer.from_pretrained(path)

    def encode(self, value: Tensor) -> str:
        return self.tokenizer.decode(
            value.flatten().tolist(), skip_special_tokens=True
        )

    def decode(self, value: str) -> Tensor:
        if not value.startswith(self.tokenizer.bos_token):
            value = self.tokenizer.bos_token + value
        return tensor(self.tokenizer.encode(value)).view(-1, 1)
