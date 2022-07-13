from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Tuple

from kilroyfaces.discord.auth import Auth as DiscordAuth
from kilroyfaces.discord.face import DiscordFace
from kilroyfaces.discord.scoring import ReactionsScorer
from kilroyfaces.discord.scraping import ChannelScraper
from kilroyfaces.twitter.auth import Auth as TwitterAuth
from kilroyfaces.twitter.face import TwitterFace
from kilroyfaces.twitter.scoring import (
    ImpressionsScorer,
    LikeScorer,
    RetweetScorer,
)
from kilroyfaces.twitter.scraping import FollowingScraper
from kilroylib.data import (
    FileCachingDatasetFactory,
    MemoryCachingDatasetFactory,
)
from kilroylib.training.offline.stop import (
    MaxDuration as OfflineMaxDuration,
    MaxEpochs as OfflineMaxEpochs,
    MaxUpdates as OfflineMaxUpdates,
    NeverStop as OfflineNeverStop,
    StopCondition as OfflineStopCondition,
)
from kilroylib.training.offline.trainer import (
    PostsLoader,
    Trainer as OfflineTrainer,
)
from kilroylib.training.online.stop import (
    MaxDuration as OnlineMaxDuration,
    MaxEpisodes as OnlineMaxEpisodes,
    MaxUpdates as OnlineMaxUpdates,
    NeverStop as OnlineNeverStop,
    StopCondition as OnlineStopCondition,
)
from kilroylib.training.online.trainer import (
    PostGenerator,
    PostScheduler,
    Trainer as OnlineTrainer,
)
from kilroyshare import Face, OfflineModule, OnlineModule
from kilroyshare.codec import Codec
from kilroytorch.adapters import SequentialDataAdapter
from kilroytorch.generators import SequentialGenerator
from kilroytorch.losses.blackbox import ReinforceLoss
from kilroytorch.losses.distance import MeanSquaredErrorLoss
from kilroytorch.losses.distribution import NegativeLogLikelihoodLoss
from kilroytorch.models.base import BaseModel
from kilroytorch.models.distribution.base import DistributionModel
from kilroytorch.models.reward.base import RewardModel
from kilroytorch.modules.offline import BasicOfflineModule
from kilroytorch.modules.online import (
    ActorCriticOnlineModule,
    BasicOnlineModule,
)
from kilroytorch.samplers.base import Sampler
from kilroytorch.samplers.categorical import (
    EpsilonNucleusCategoricalSampler,
    EpsilonProportionalCategoricalSampler,
    EpsilonTopKCategoricalSampler,
)
from torch.optim import Adam, Optimizer, RMSprop, SGD
from torch.optim.lr_scheduler import (
    ExponentialLR,
    ReduceLROnPlateau,
    _LRScheduler,
)

from kilroy.codecs import HuggingFaceCodec
from kilroy.config import (
    CodecConfig,
    Config,
    FaceConfig,
    GeneratorConfig,
    LRSchedulerConfig,
    ModelConfig,
    OfflineConfig,
    OnlineConfig,
    OptimizerConfig,
    SamplerConfig,
)
from kilroy.models import DistributionHuggingFaceModel, RewardHuggingFaceModel
from kilroy.runner import Runner


def lookup_model(models: Dict[str, BaseModel], name: str) -> BaseModel:
    try:
        return models[name]
    except KeyError:
        raise MisconfigurationError(f"Model {name} not found.")


def lookup_codec(codecs: Dict[str, Codec], name: str) -> Codec:
    try:
        return codecs[name]
    except KeyError:
        raise MisconfigurationError(f"Codec {name} not found.")


class MisconfigurationError(Exception):
    pass


class OptimizerFactory:
    class AdamFactory:
        @classmethod
        def create(
            cls, config: OptimizerConfig.AdamConfig, model: BaseModel
        ) -> Adam:
            return Adam(
                model.parameters(),
                lr=config.lr,
                betas=config.betas,
                eps=config.eps,
                weight_decay=config.weight_decay,
            )

    class RMSpropFactory:
        @classmethod
        def create(
            cls, config: OptimizerConfig.RMSpropConfig, model: BaseModel
        ) -> RMSprop:
            return RMSprop(
                model.parameters(),
                lr=config.lr,
                alpha=config.alpha,
                eps=config.eps,
                weight_decay=config.weight_decay,
            )

    class SGDFactory:
        @classmethod
        def create(
            cls, config: OptimizerConfig.SGDConfig, model: BaseModel
        ) -> SGD:
            return SGD(
                model.parameters(),
                lr=config.lr,
                momentum=config.momentum,
                dampening=config.dampening,
                weight_decay=config.weight_decay,
            )

    @classmethod
    def create(cls, config: OptimizerConfig, model: BaseModel) -> Optimizer:
        optimizer_type = config.__root__.type
        if optimizer_type == "adam":
            return cls.AdamFactory.create(config.__root__, model)
        elif optimizer_type == "rmsprop":
            return cls.RMSpropFactory.create(config.__root__, model)
        elif optimizer_type == "sgd":
            return cls.SGDFactory.create(config.__root__, model)
        else:
            raise MisconfigurationError(
                f"Invalid optimizer type: {optimizer_type}"
            )


class LRSchedulerFactory:
    class ExponentialFactory:
        @classmethod
        def create(
            cls,
            config: LRSchedulerConfig.ExponentialConfig,
            optimizer: Optimizer,
        ) -> ExponentialLR:
            return ExponentialLR(optimizer, gamma=config.gamma)

    class PlateauFactory:
        @classmethod
        def create(
            cls,
            config: LRSchedulerConfig.PlateauConfig,
            optimizer: Optimizer,
        ) -> ReduceLROnPlateau:
            return ReduceLROnPlateau(
                optimizer,
                factor=config.factor,
                patience=config.patience,
                threshold=config.threshold,
                threshold_mode=config.threshold_mode,
                cooldown=config.cooldown,
                eps=config.eps,
            )

    @classmethod
    def create(
        cls, config: LRSchedulerConfig, optimizer: Optimizer
    ) -> _LRScheduler:
        scheduler_type = config.__root__.type
        if scheduler_type == "exponential":
            return cls.ExponentialFactory.create(config.__root__, optimizer)
        elif scheduler_type == "plateau":
            return cls.PlateauFactory.create(config.__root__, optimizer)
        else:
            raise MisconfigurationError(
                f"Invalid lr scheduler type: {scheduler_type}"
            )


class SamplerFactory:
    class ProportionalConfig:
        @classmethod
        def create(
            cls, config: SamplerConfig.ProportionalConfig
        ) -> EpsilonProportionalCategoricalSampler:
            return EpsilonProportionalCategoricalSampler(
                epsilon=config.epsilon
            )

    class TopKConfig:
        @classmethod
        def create(
            cls, config: SamplerConfig.TopKConfig
        ) -> EpsilonTopKCategoricalSampler:
            return EpsilonTopKCategoricalSampler(
                epsilon=config.epsilon, k=config.k
            )

    class NucleusConfig:
        @classmethod
        def create(
            cls, config: SamplerConfig.NucleusConfig
        ) -> EpsilonNucleusCategoricalSampler:
            return EpsilonNucleusCategoricalSampler(
                epsilon=config.epsilon, p=config.p
            )

    @classmethod
    def create(cls, config: SamplerConfig) -> Sampler:
        sampler_type = config.__root__.type
        if sampler_type == "proportional":
            return cls.ProportionalConfig.create(config.__root__)
        elif sampler_type == "top_k":
            return cls.TopKConfig.create(config.__root__)
        elif sampler_type == "nucleus":
            return cls.NucleusConfig.create(config.__root__)
        else:
            raise MisconfigurationError(
                f"Invalid sampler type: {sampler_type}"
            )


class GeneratorFactory:
    @classmethod
    def create(
        cls, config: GeneratorConfig, codec: Codec
    ) -> SequentialGenerator:
        return SequentialGenerator(
            sampler=SamplerFactory.create(config.sampler),
            max_length=config.max_length,
            end_values=[
                codec.decode(token).flatten()[-1].item()
                for token in config.end_tokens
            ],
            context_values=[
                codec.decode(context) for context in config.contexts
            ],
        )


class ModelsFactory:
    class ModelFactory:
        class DistributionFactory:
            @classmethod
            def create(
                cls,
                config: ModelConfig.DistributionHuggingFaceConfig,
            ) -> DistributionModel:
                return DistributionHuggingFaceModel(config.path)

        class RewardFactory:
            @classmethod
            def create(
                cls, config: ModelConfig.RewardHuggingFaceConfig
            ) -> RewardModel:
                return RewardHuggingFaceModel(config.path)

        @classmethod
        def create(cls, config: ModelConfig) -> BaseModel:
            model_type = config.__root__.type
            if model_type == "distribution":
                return cls.DistributionFactory.create(config.__root__)
            elif model_type == "reward":
                return cls.RewardFactory.create(config.__root__)
            raise MisconfigurationError(f"Invalid model type: {model_type}")

    @classmethod
    def create(cls, config: Dict[str, ModelConfig]) -> Dict[str, BaseModel]:
        return {
            name: cls.ModelFactory.create(cfg) for name, cfg in config.items()
        }


class CodecsFactory:
    class CodecFactory:
        @classmethod
        def create(cls, config: CodecConfig) -> Codec:
            return HuggingFaceCodec(path=config.path)

    @classmethod
    def create(cls, config: Dict[str, CodecConfig]) -> Dict[str, Codec]:
        return {
            name: cls.CodecFactory.create(cfg) for name, cfg in config.items()
        }


class FaceFactory:
    class DiscordFaceFactory:
        @classmethod
        def create(cls, config: FaceConfig.DiscordConfig) -> DiscordFace:
            if config.scorer == "reactions":
                scorer = ReactionsScorer()
            else:
                raise MisconfigurationError(f"Invalid scorer: {config.scorer}")

            if config.scraper == "channel":
                scraper = ChannelScraper(config.channel_id)
            else:
                raise MisconfigurationError(
                    f"Invalid scraper: {config.scraper}"
                )

            return DiscordFace(
                channel_id=config.channel_id,
                auth=DiscordAuth(token=config.auth.token),
                scorer=scorer,
                scraper=scraper,
            )

    class TwitterFaceFactory:
        @classmethod
        def create(cls, config: FaceConfig.TwitterConfig) -> TwitterFace:
            if config.scorer == "likes":
                scorer = LikeScorer()
            elif config.scorer == "retweets":
                scorer = RetweetScorer()
            elif config.scorer == "impressions":
                scorer = ImpressionsScorer()
            else:
                raise MisconfigurationError(f"Invalid scorer: {config.scorer}")

            if config.scraper == "following":
                scraper = FollowingScraper()
            else:
                raise MisconfigurationError(
                    f"Invalid scraper: {config.scraper}"
                )

            return TwitterFace(
                auth=TwitterAuth(
                    consumer_key=config.auth.consumer_key,
                    consumer_secret=config.auth.consumer_secret,
                    token=config.auth.token,
                    secret=config.auth.secret,
                ),
                scorer=scorer,
                scraper=scraper,
            )

    @classmethod
    def create(cls, config: FaceConfig) -> Face:
        face_type = config.__root__.type
        if face_type == "discord":
            return cls.DiscordFaceFactory.create(config.__root__)
        elif face_type == "twitter":
            return cls.TwitterFaceFactory.create(config.__root__)
        raise MisconfigurationError(f"Invalid face type: {face_type}")


class OfflineFactory:
    class ModuleFactory:
        @classmethod
        def create(
            cls,
            config: OfflineConfig.ModuleConfig,
            models: Dict[str, BaseModel],
            codecs: Dict[str, Codec],
        ) -> OfflineModule:
            model = lookup_model(models, config.model)

            if not isinstance(model, DistributionModel):
                raise MisconfigurationError(
                    f"Model {config.model} is not a distribution model."
                )

            optimizer = OptimizerFactory.create(config.optimizer, model)

            return BasicOfflineModule(
                model=model,
                adapter=SequentialDataAdapter(),
                codec=lookup_codec(codecs, config.codec),
                optimizer=optimizer,
                loss=NegativeLogLikelihoodLoss(),
                lr_schedulers=[
                    LRSchedulerFactory.create(lr_scheduler_config, optimizer)
                    for lr_scheduler_config in config.lr_schedulers
                ],
            )

    class TrainerFactory:
        class StopConditionFactory:
            class NeverStopFactory:
                @classmethod
                def create(cls) -> OfflineNeverStop:
                    return OfflineNeverStop()

            class MaxDurationFactory:
                @classmethod
                def create(
                    cls,
                    config: OfflineConfig.TrainerConfig.StopConditionConfig.MaxDurationConfig,
                ) -> OfflineMaxDuration:
                    try:
                        return OfflineMaxDuration(
                            duration=timedelta(**config.duration)
                        )
                    except TypeError as e:
                        raise MisconfigurationError(
                            f"Invalid duration value: {config.duration}"
                        ) from e

            class MaxEpochsFactory:
                @classmethod
                def create(
                    cls,
                    config: OfflineConfig.TrainerConfig.StopConditionConfig.MaxEpochsConfig,
                ) -> OfflineMaxEpochs:
                    return OfflineMaxEpochs(epochs=config.epochs)

            class MaxUpdatesFactory:
                @classmethod
                def create(
                    cls,
                    config: OfflineConfig.TrainerConfig.StopConditionConfig.MaxUpdatesConfig,
                ) -> OfflineMaxUpdates:
                    return OfflineMaxUpdates(updates=config.updates)

            @classmethod
            def create(
                cls, config: OfflineConfig.TrainerConfig.StopConditionConfig
            ) -> OfflineStopCondition:
                stop_type = config.__root__.type
                if stop_type == "never":
                    return cls.NeverStopFactory.create()
                elif stop_type == "max_duration":
                    return cls.MaxDurationFactory.create(config.__root__)
                elif stop_type == "max_epochs":
                    return cls.MaxEpochsFactory.create(config.__root__)
                elif stop_type == "max_updates":
                    return cls.MaxUpdatesFactory.create(config.__root__)
                else:
                    raise MisconfigurationError(
                        f"Invalid stop condition type: {stop_type}"
                    )

        class PostsLoaderFactory:
            @classmethod
            def create(
                cls, config: OfflineConfig.TrainerConfig.PostsLoaderConfig
            ) -> PostsLoader:
                if config.dataset_factory == "memory":
                    dataset_factory = MemoryCachingDatasetFactory()
                elif config.dataset_factory == "file":
                    dataset_factory = FileCachingDatasetFactory()
                else:
                    raise MisconfigurationError(
                        f"Invalid dataset factory type: {config.dataset_factory}"
                    )
                return PostsLoader(
                    batch_size=config.batch_size,
                    dataset_factory=dataset_factory,
                )

        @classmethod
        def create(cls, config: OfflineConfig.TrainerConfig) -> OfflineTrainer:
            return OfflineTrainer(
                stop_condition=cls.StopConditionFactory.create(
                    config.stop_condition
                ),
                posts_loader=cls.PostsLoaderFactory.create(
                    config.posts_loader
                ),
                batch_iterations=config.batch_iterations,
                batches_per_update=config.batches_per_update,
            )

    @dataclass
    class Output:
        module: OfflineModule
        trainer: OfflineTrainer

    @classmethod
    def create(
        cls,
        config: OfflineConfig,
        models: Dict[str, BaseModel],
        codecs: Dict[str, Codec],
    ) -> Output:
        return OfflineFactory.Output(
            module=cls.ModuleFactory.create(config.module, models, codecs),
            trainer=cls.TrainerFactory.create(config.trainer),
        )


class OnlineFactory:
    class ModuleFactory:
        class BasicFactory:
            @classmethod
            def create(
                cls,
                config: OnlineConfig.ModuleConfig.BasicConfig,
                models: Dict[str, BaseModel],
                codecs: Dict[str, Codec],
            ) -> OnlineModule:
                model = lookup_model(models, config.model)

                if not isinstance(model, DistributionModel):
                    raise MisconfigurationError(
                        f"Model {config.model} is not a distribution model."
                    )

                codec = lookup_codec(codecs, config.codec)

                optimizer = OptimizerFactory.create(config.optimizer, model)

                return BasicOnlineModule(
                    model=model,
                    generator=GeneratorFactory.create(config.generator, codec),
                    adapter=SequentialDataAdapter(),
                    codec=codec,
                    optimizer=optimizer,
                    loss=ReinforceLoss(),
                    lr_schedulers=[
                        LRSchedulerFactory.create(
                            lr_scheduler_config, optimizer
                        )
                        for lr_scheduler_config in config.lr_schedulers
                    ],
                )

        class ActorCriticFactory:
            class OptimizersFactory:
                @classmethod
                def create(
                    cls,
                    config: OnlineConfig.ModuleConfig.ActorCriticConfig.OptimizersConfig,
                    actor: DistributionModel,
                    critic: RewardModel,
                ) -> Tuple[Optimizer, Optimizer]:
                    return (
                        OptimizerFactory.create(config.actor, actor),
                        OptimizerFactory.create(config.critic, critic),
                    )

            class LRSchedulersFactory:
                @classmethod
                def create(
                    cls,
                    config: OnlineConfig.ModuleConfig.ActorCriticConfig.LRSchedulersConfig,
                    actor_optimizer: Optimizer,
                    critic_optimizer: Optimizer,
                ) -> List[_LRScheduler]:
                    return [
                        LRSchedulerFactory.create(cfg, actor_optimizer)
                        for cfg in config.actor
                    ] + [
                        LRSchedulerFactory.create(cfg, critic_optimizer)
                        for cfg in config.critic
                    ]

            @classmethod
            def create(
                cls,
                config: OnlineConfig.ModuleConfig.ActorCriticConfig,
                models: Dict[str, BaseModel],
                codecs: Dict[str, Codec],
            ) -> OnlineModule:
                actor = lookup_model(models, config.actor)

                if not isinstance(actor, DistributionModel):
                    raise MisconfigurationError(
                        f"Actor {config.actor} is not a distribution model."
                    )

                codec = lookup_codec(codecs, config.codec)

                critic = lookup_model(models, config.critic)

                if not isinstance(critic, RewardModel):
                    raise MisconfigurationError(
                        f"Actor {config.critic} is not a reward model."
                    )

                if config.critic_codec is None:
                    critic_codec = None
                else:
                    critic_codec = lookup_codec(codecs, config.critic_codec)

                optimizers = cls.OptimizersFactory.create(
                    config.optimizers, actor, critic
                )

                return ActorCriticOnlineModule(
                    actor=actor,
                    critic=critic,
                    generator=GeneratorFactory.create(config.generator, codec),
                    adapter=SequentialDataAdapter(),
                    codec=codec,
                    optimizers=optimizers,
                    actor_loss=ReinforceLoss(),
                    critic_loss=MeanSquaredErrorLoss(),
                    lr_schedulers=cls.LRSchedulersFactory.create(
                        config.lr_schedulers, optimizers[0], optimizers[1]
                    ),
                    critic_codec=critic_codec,
                    actor_iterations=config.actor_iterations,
                )

        @classmethod
        def create(
            cls,
            config: OnlineConfig.ModuleConfig,
            models: Dict[str, BaseModel],
            codecs: Dict[str, Codec],
        ) -> OnlineModule:
            module_type = config.__root__.type
            if module_type == "basic":
                return cls.BasicFactory.create(config.__root__, models, codecs)
            elif module_type == "actor_critic":
                return cls.ActorCriticFactory.create(
                    config.__root__, models, codecs
                )
            else:
                raise MisconfigurationError(
                    f"Invalid stop condition type: {module_type}"
                )

    class TrainerFactory:
        class StopConditionFactory:
            class NeverStopFactory:
                @classmethod
                def create(cls) -> OnlineNeverStop:
                    return OnlineNeverStop()

            class MaxDurationFactory:
                @classmethod
                def create(
                    cls,
                    config: OnlineConfig.TrainerConfig.StopConditionConfig.MaxDurationConfig,
                ) -> OnlineMaxDuration:
                    try:
                        return OnlineMaxDuration(
                            duration=timedelta(**config.duration)
                        )
                    except TypeError as e:
                        raise MisconfigurationError(
                            f"Invalid duration value: {config.duration}"
                        ) from e

            class MaxEpisodesFactory:
                @classmethod
                def create(
                    cls,
                    config: OnlineConfig.TrainerConfig.StopConditionConfig.MaxEpisodesConfig,
                ) -> OnlineMaxEpisodes:
                    return OnlineMaxEpisodes(episodes=config.episodes)

            class MaxUpdatesFactory:
                @classmethod
                def create(
                    cls,
                    config: OnlineConfig.TrainerConfig.StopConditionConfig.MaxUpdatesConfig,
                ) -> OnlineMaxUpdates:
                    return OnlineMaxUpdates(updates=config.updates)

            @classmethod
            def create(
                cls, config: OnlineConfig.TrainerConfig.StopConditionConfig
            ) -> OnlineStopCondition:
                stop_type = config.__root__.type
                if stop_type == "never":
                    return cls.NeverStopFactory.create()
                elif stop_type == "max_duration":
                    return cls.MaxDurationFactory.create(config.__root__)
                elif stop_type == "max_episodes":
                    return cls.MaxEpisodesFactory.create(config.__root__)
                elif stop_type == "max_updates":
                    return cls.MaxUpdatesFactory.create(config.__root__)
                else:
                    raise MisconfigurationError(
                        f"Invalid stop condition type: {stop_type}"
                    )

        class GeneratorFactory:
            @classmethod
            def create(
                cls, config: OnlineConfig.TrainerConfig.GeneratorConfig
            ) -> PostGenerator:
                return PostGenerator(n=config.n)

        class SchedulerFactory:
            @classmethod
            def create(
                cls, config: OnlineConfig.TrainerConfig.SchedulerConfig
            ) -> PostScheduler:
                return PostScheduler(cooldown=timedelta(**config.cooldown))

        @classmethod
        def create(cls, config: OnlineConfig.TrainerConfig) -> OnlineTrainer:
            return OnlineTrainer(
                stop_condition=cls.StopConditionFactory.create(
                    config.stop_condition
                ),
                generator=cls.GeneratorFactory.create(config.generator),
                scheduler=cls.SchedulerFactory.create(config.scheduler),
                episode_iterations=config.episode_iterations,
                episodes_per_update=config.episodes_per_update,
            )

    @dataclass
    class Output:
        module: OnlineModule
        trainer: OnlineTrainer

    @classmethod
    def create(
        cls,
        config: OnlineConfig,
        models: Dict[str, BaseModel],
        codecs: Dict[str, Codec],
    ) -> Output:
        return OnlineFactory.Output(
            module=cls.ModuleFactory.create(config.module, models, codecs),
            trainer=cls.TrainerFactory.create(config.trainer),
        )


class RunnerFactory:
    @classmethod
    def create(cls, config: Config) -> Runner:
        models = ModelsFactory.create(config.models)
        codecs = CodecsFactory.create(config.codecs)
        face = FaceFactory.create(config.face)
        offline = OfflineFactory.create(config.offline, models, codecs)
        online = OnlineFactory.create(config.online, models, codecs)

        return Runner(
            face,
            offline.module,
            offline.trainer,
            online.module,
            online.trainer,
        )
