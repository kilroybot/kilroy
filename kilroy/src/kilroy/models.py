from typing import Optional

from kilroytorch.models.distribution.sequential import (
    SequentialDistributionModel,
)
from kilroytorch.models.reward.sequential import SequentialRewardModel
from kilroytorch.utils import ShapeValidator, pack_padded, unpack_to_padded
from torch import Tensor
from torch.nn.utils.rnn import PackedSequence
from transformers import (
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
)


class DistributionHuggingFaceModel(
    SequentialDistributionModel[PackedSequence, PackedSequence]
):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.model = AutoModelForCausalLM.from_pretrained(path)
        self._input_validator = ShapeValidator((None, 1))
        self._output_validator = ShapeValidator(
            (None, self.model.config.vocab_size)
        )
        self.pad_value = 0

    def input_validator(self) -> Optional[ShapeValidator]:
        return self._input_validator

    def output_validator(self) -> Optional[ShapeValidator]:
        return self._output_validator

    def forward_internal(self, x: PackedSequence) -> PackedSequence:
        x, lengths = unpack_to_padded(x, pad_value=self.pad_value)
        x = x[:, :, 0]
        mask = x != self.pad_value
        y = self.model(x, attention_mask=mask)
        return pack_padded(y.logits, lengths)


class RewardHuggingFaceModel(SequentialRewardModel[PackedSequence]):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.model = AutoModelForSequenceClassification.from_pretrained(path)
        self._input_validator = ShapeValidator((None, 1))
        self.pad_value = 0

    def input_validator(self) -> Optional[ShapeValidator]:
        return self._input_validator

    def forward_internal(self, x: PackedSequence) -> Tensor:
        x, lengths = unpack_to_padded(x, pad_value=self.pad_value)
        x = x[:, :, 0]
        mask = x != self.pad_value
        y = self.model(x, attention_mask=mask)
        return y.logits[:, [1]].exp() * 2 - 1
