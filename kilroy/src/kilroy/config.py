from typing import (
    Annotated,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
)

from pydantic import BaseModel, Field, conlist


class OptimizerConfig(BaseModel):
    class AdamConfig(BaseModel):
        type: Literal["adam"] = "adam"
        lr: float = 0.001
        betas: Tuple[float, float] = (0.9, 0.999)
        eps: float = 1e-8
        weight_decay: float = 0

    class RMSpropConfig(BaseModel):
        type: Literal["rmsprop"] = "rmsprop"
        lr: float = 0.01
        momentum: float = 0
        alpha: float = 0.99
        eps: float = 1e-8
        weight_decay: float = 0

    class SGDConfig(BaseModel):
        type: Literal["sgd"] = "sgd"
        lr: float
        momentum: float = 0
        weight_decay: float = 0
        dampening: float = 0

    __root__: Annotated[
        Union[AdamConfig, RMSpropConfig, SGDConfig],
        Field(discriminator="type"),
    ]


class LRSchedulerConfig(BaseModel):
    class ExponentialConfig(BaseModel):
        type: Literal["exponential"] = "exponential"
        gamma: float

    class PlateauConfig(BaseModel):
        type: Literal["plateau"] = "plateau"
        factor: float = 0.1
        patience: int = 10
        threshold: float = 0.0001
        threshold_mode: Literal["rel", "abs"] = "rel"
        cooldown: int = 0
        eps: float = 1e-8

    __root__: Annotated[
        Union[ExponentialConfig, PlateauConfig],
        Field(discriminator="type"),
    ]


class SamplerConfig(BaseModel):
    class ProportionalConfig(BaseModel):
        type: Literal["proportional"] = "proportional"
        epsilon: float = 0

    class TopKConfig(BaseModel):
        type: Literal["top_k"] = "top_k"
        k: int
        epsilon: float = 0

    class NucleusConfig(BaseModel):
        type: Literal["nucleus"] = "nucleus"
        p: float
        epsilon: float = 0

    __root__: Annotated[
        Union[
            ProportionalConfig,
            TopKConfig,
            NucleusConfig,
        ],
        Field(discriminator="type"),
    ]


class GeneratorConfig(BaseModel):
    sampler: SamplerConfig = SamplerConfig(
        __root__=SamplerConfig.ProportionalConfig()
    )
    max_length: int
    end_tokens: conlist(str, min_items=1) = [""]
    contexts: conlist(str, min_items=1) = [""]


class ModelConfig(BaseModel):
    class DistributionHuggingFaceConfig(BaseModel):
        type: Literal["distribution"] = "distribution"
        source: Literal["huggingface"] = "huggingface"
        path: str

    class RewardHuggingFaceConfig(BaseModel):
        type: Literal["reward"] = "reward"
        source: Literal["huggingface"] = "huggingface"
        path: str

    __root__: Annotated[
        Union[DistributionHuggingFaceConfig, RewardHuggingFaceConfig],
        Field(discriminator="type"),
    ]


class CodecConfig(BaseModel):
    type: Literal["huggingface"] = "huggingface"
    path: str


class FaceConfig(BaseModel):
    class DiscordConfig(BaseModel):
        class Auth(BaseModel):
            token: str

        type: Literal["discord"] = "discord"
        channel_id: int
        auth: Auth
        scorer: Literal["reactions"] = "reactions"
        scraper: Literal["channel"] = "channel"

    class TwitterConfig(BaseModel):
        class Auth(BaseModel):
            consumer_key: str
            consumer_secret: str
            token: str
            secret: str

        type: Literal["twitter"] = "twitter"
        auth: Auth
        scorer: Literal["likes", "retweets", "impressions"] = "likes"
        scraper: Literal["following"] = "following"

    __root__: Annotated[
        Union[DiscordConfig, TwitterConfig],
        Field(discriminator="type"),
    ]


class OfflineConfig(BaseModel):
    class TrainerConfig(BaseModel):
        class StopConditionConfig(BaseModel):
            class NeverStopConfig(BaseModel):
                type: Literal["never"] = "never"

            class MaxDurationConfig(BaseModel):
                type: Literal["max_duration"] = "max_duration"
                duration: Dict[str, float]

            class MaxEpochsConfig(BaseModel):
                type: Literal["max_epochs"] = "max_epochs"
                epochs: int

            class MaxUpdatesConfig(BaseModel):
                type: Literal["max_updates"] = "max_updates"
                updates: int

            __root__: Annotated[
                Union[
                    NeverStopConfig,
                    MaxDurationConfig,
                    MaxEpochsConfig,
                    MaxUpdatesConfig,
                ],
                Field(discriminator="type"),
            ]

        class PostsLoaderConfig(BaseModel):
            batch_size: int
            dataset_factory: Literal["memory", "file"]

        stop_condition: StopConditionConfig = (
            StopConditionConfig.MaxEpochsConfig(epochs=1)
        )
        posts_loader: PostsLoaderConfig = PostsLoaderConfig(
            batch_size=1, dataset_factory="memory"
        )
        batch_iterations: int = 1
        batches_per_update: int = 1

    class ModuleConfig(BaseModel):
        type: Literal["basic"] = "basic"
        model: str
        codec: str
        optimizer: OptimizerConfig
        lr_schedulers: List[LRSchedulerConfig] = []

    trainer: TrainerConfig
    module: ModuleConfig


class OnlineConfig(BaseModel):
    class TrainerConfig(BaseModel):
        class StopConditionConfig(BaseModel):
            class NeverStopConfig(BaseModel):
                type: Literal["never"] = "never"

            class MaxDurationConfig(BaseModel):
                type: Literal["max_duration"] = "max_duration"
                duration: Dict[str, float]

            class MaxEpisodesConfig(BaseModel):
                type: Literal["max_episodes"] = "max_episodes"
                episodes: int

            class MaxUpdatesConfig(BaseModel):
                type: Literal["max_updates"] = "max_updates"
                updates: int

            __root__: Annotated[
                Union[
                    NeverStopConfig,
                    MaxDurationConfig,
                    MaxEpisodesConfig,
                    MaxUpdatesConfig,
                ],
                Field(discriminator="type"),
            ]

        class GeneratorConfig(BaseModel):
            n: int

        class SchedulerConfig(BaseModel):
            cooldown: Dict[str, float]

        stop_condition: StopConditionConfig = (
            StopConditionConfig.MaxEpisodesConfig(episodes=1)
        )
        generator: GeneratorConfig = GeneratorConfig(n=1)
        scheduler: SchedulerConfig = SchedulerConfig(cooldown={"seconds": 1})
        episode_iterations: int = 1
        episodes_per_update: int = 1

    class ModuleConfig(BaseModel):
        class BasicConfig(BaseModel):
            type: Literal["basic"] = "basic"
            model: str
            codec: str
            generator: GeneratorConfig
            optimizer: OptimizerConfig
            lr_schedulers: List[LRSchedulerConfig] = []

        class ActorCriticConfig(BaseModel):
            class OptimizersConfig(BaseModel):
                actor: OptimizerConfig
                critic: OptimizerConfig

            class LRSchedulersConfig(BaseModel):
                actor: List[LRSchedulerConfig] = []
                critic: List[LRSchedulerConfig] = []

            type: Literal["actor_critic"] = "actor_critic"
            actor: str
            critic: str
            codec: str
            critic_codec: Optional[str] = None
            generator: GeneratorConfig
            optimizers: OptimizersConfig
            lr_schedulers: LRSchedulersConfig = LRSchedulersConfig()
            actor_iterations: int = 100

        __root__: Annotated[
            Union[BasicConfig, ActorCriticConfig],
            Field(discriminator="type"),
        ]

    trainer: TrainerConfig
    module: ModuleConfig


class Config(BaseModel):
    models: Dict[str, ModelConfig]
    codecs: Dict[str, CodecConfig]
    face: FaceConfig
    offline: OfflineConfig
    online: OnlineConfig
