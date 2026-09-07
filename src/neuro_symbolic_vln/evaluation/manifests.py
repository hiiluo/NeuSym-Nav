from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neuro_symbolic_vln.contracts import EpisodeSpec
from neuro_symbolic_vln.env.tasks import (
    make_goto_goal_probe_env,
    make_locked_door_probe_env,
)
from neuro_symbolic_vln.evaluation.oracle import (
    ExactOracle,
    model_from_probe_env,
)

SCHEMA_VERSION = "1.0"

# Deterministic layout variation space (see docs/plan §15.1-15.2):
# combo index encodes heading, color and position variants.
_GOTO_COLORS = ("green", "blue", "purple", "yellow", "red")
_GOTO_TARGET_POSITIONS = ((3, 1), (4, 2))
_KEYDOOR_DISTRACTOR_COLORS = ("blue", "green", "purple", "yellow")
_DISTRACTOR_POSITIONS = ((1, 3), (2, 2))
_SPLIT_SEED_BASE = {"smoke": 10_000, "dev": 20_000}


class ManifestGenerationError(ValueError):
    """Raised for duplicate, cross-split or unsolvable layouts."""


def stable_hash(payload: dict[str, object]) -> str:
    """Deterministic sha256 over canonical JSON."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PublicManifest:
    schema_version: str
    episode_id: str
    family: str
    split: str
    generator_version: str
    seed: int
    layout_hash: str
    instruction: str
    task_spec: dict[str, Any]
    condition: dict[str, Any] | None
    public_action_budget: int
    config_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "family": self.family,
            "split": self.split,
            "generator_version": self.generator_version,
            "seed": self.seed,
            "layout_hash": self.layout_hash,
            "instruction": self.instruction,
            "task_spec": self.task_spec,
            "condition": self.condition,
            "public_action_budget": self.public_action_budget,
            "config_hash": self.config_hash,
        }

    def manifest_hash(self) -> str:
        return stable_hash(self.to_dict())

    def to_episode_spec(self) -> EpisodeSpec:
        """Public fields only: no oracle/sidecar data may reach the agent."""
        return EpisodeSpec(
            episode_id=self.episode_id,
            family=self.family,
            instruction=self.instruction,
            public_action_budget=self.public_action_budget,
            manifest_hash=self.manifest_hash(),
        )


@dataclass(frozen=True)
class EvaluationSidecar:
    schema_version: str
    episode_id: str
    solvable: bool
    optimal_grid_distance: int | None
    optimal_primitive_actions: int | None
    oracle_target_entity_id: str
    # Filled once N1 corruption (A-06) and evidence capture (A-07) land.
    observable_predicate_universe_hash: str | None = None
    uncorrupted_evidence_hash: str | None = None
    intervention: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "solvable": self.solvable,
            "optimal_grid_distance": self.optimal_grid_distance,
            "optimal_primitive_actions": self.optimal_primitive_actions,
            "oracle_target_entity_id": self.oracle_target_entity_id,
            "observable_predicate_universe_hash": (
                self.observable_predicate_universe_hash
            ),
            "uncorrupted_evidence_hash": self.uncorrupted_evidence_hash,
            "intervention": self.intervention,
        }


@dataclass(frozen=True)
class GenerationResult:
    public_manifests: tuple[PublicManifest, ...]
    sidecars: tuple[EvaluationSidecar, ...]


@dataclass(frozen=True)
class _Layout:
    family: str
    target: tuple[int, int]
    task_spec: dict[str, Any]
    layout_payload: dict[str, Any]
    env_kwargs: dict[str, Any]

    def build_env(self) -> Any:
        if self.family == "goto_type_color":
            return make_goto_goal_probe_env(**self.env_kwargs)
        return make_locked_door_probe_env(**self.env_kwargs)

    def instruction(self) -> str:
        if self.family == "goto_type_color":
            return (
                f"go to the {self.task_spec['target_color']} "
                f"{self.task_spec['target_type']}"
            )
        # Must match the core grammar (plan §9.1): pickup clause, open
        # clause, then goal clause.
        return "pick up the red key, open the red door, then go to the goal"

    def episode_id(self, split: str, combo: int) -> str:
        short = "goto" if self.family == "goto_type_color" else "keydoor"
        return f"{short}-{split}-{combo:04d}"


def _layouts_for_combo(combo: int) -> tuple[_Layout, _Layout]:
    """Two deterministic layouts (one per family) for a combo index.

    The combo space is partitioned across splits, so layouts never repeat
    within or across splits by construction; the generator still rejects
    any collision defensively.
    """
    heading = combo % 4

    goto_color = _GOTO_COLORS[(combo // 4) % len(_GOTO_COLORS)]
    goto_pos = _GOTO_TARGET_POSITIONS[combo // 20]
    goto = _Layout(
        family="goto_type_color",
        target=goto_pos,
        task_spec={
            "target_type": "ball",
            "target_color": goto_color,
            "target_pos": goto_pos,
            "agent_dir": heading,
        },
        layout_payload={
            "family": "goto_type_color",
            "target_type": "ball",
            "target_color": goto_color,
            "target_pos": goto_pos,
            "agent_dir": heading,
        },
        env_kwargs={
            "target_type": "ball",
            "target_color": goto_color,
            "target_pos": goto_pos,
            "agent_dir": heading,
        },
    )

    variant = (combo // 4) % 9
    if variant == 0:
        distractor_color: str | None = None
        distractor_pos = (1, 3)
    else:
        color_index = (variant - 1) % len(_KEYDOOR_DISTRACTOR_COLORS)
        distractor_color = _KEYDOOR_DISTRACTOR_COLORS[color_index]
        distractor_pos = _DISTRACTOR_POSITIONS[(variant - 1) // 4]
    keydoor = _Layout(
        family="key_door_goal",
        target=(4, 1),
        task_spec={
            "key_color": "red",
            "agent_dir": heading,
            "distractor_key_color": distractor_color,
            "distractor_key_pos": distractor_pos,
        },
        layout_payload={
            "family": "key_door_goal",
            "key_color": "red",
            "agent_dir": heading,
            "distractor_key_color": distractor_color,
            "distractor_key_pos": distractor_pos,
        },
        env_kwargs={
            "key_color": "red",
            "agent_dir": heading,
            "distractor_key_color": distractor_color,
            "distractor_key_pos": distractor_pos,
        },
    )
    return goto, keydoor


def generate_manifests(config: dict[str, Any]) -> GenerationResult:
    """Generate public manifests + sidecars from a generator config.

    Rejects unsolvable layouts and duplicate/cross-split layout hashes.
    """
    generator_version = str(config["generator_version"])
    budget = int(config["public_action_budget"])
    config_hash = stable_hash(config)
    oracle = ExactOracle()

    seen_layouts: dict[str, str] = {}
    publics: list[PublicManifest] = []
    sidecars: list[EvaluationSidecar] = []

    for split, split_config in config["splits"].items():
        start = int(split_config["combo_start"])
        count = int(split_config["combo_count"])
        seed_base = int(_SPLIT_SEED_BASE.get(split, 30_000))
        for combo in range(start, start + count):
            for layout in _layouts_for_combo(combo):
                episode_id = layout.episode_id(split, combo)
                env = layout.build_env()
                env.reset(seed=seed_base + combo)
                model = model_from_probe_env(env, layout.family, layout.target)
                solution = oracle.solve(model)
                if not solution.solvable:
                    raise ManifestGenerationError(
                        f"unsolvable layout: {episode_id}"
                    )
                layout_hash = stable_hash(layout.layout_payload)
                previous = seen_layouts.get(layout_hash)
                if previous is not None:
                    raise ManifestGenerationError(
                        f"layout {episode_id} already used in split {previous}"
                    )
                seen_layouts[layout_hash] = split

                publics.append(
                    PublicManifest(
                        schema_version=SCHEMA_VERSION,
                        episode_id=episode_id,
                        family=layout.family,
                        split=split,
                        generator_version=generator_version,
                        seed=seed_base + combo,
                        layout_hash=layout_hash,
                        instruction=layout.instruction(),
                        task_spec=layout.task_spec,
                        condition=None,
                        public_action_budget=budget,
                        config_hash=config_hash,
                    )
                )
                sidecars.append(
                    EvaluationSidecar(
                        schema_version=SCHEMA_VERSION,
                        episode_id=episode_id,
                        solvable=solution.solvable,
                        optimal_grid_distance=solution.optimal_grid_distance,
                        optimal_primitive_actions=(
                            solution.optimal_primitive_actions
                        ),
                        oracle_target_entity_id=(
                            layout.task_spec["target_color"] + "-ball"
                            if layout.family == "goto_type_color"
                            else "target-goal"
                        ),
                    )
                )
    return GenerationResult(tuple(publics), tuple(sidecars))


def _write_jsonl(path: Path, objects: list[dict[str, Any]]) -> None:
    lines = [
        json.dumps(obj, sort_keys=True, separators=(",", ":"))
        for obj in objects
    ]
    path.write_text("\n".join(lines) + "\n")


def write_manifests(
    output_dir: str | Path, result: GenerationResult
) -> dict[str, str]:
    """Write public JSONL + private sidecar JSONL + hash index."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    for split in {manifest.split for manifest in result.public_manifests}:
        publics = sorted(
            (m for m in result.public_manifests if m.split == split),
            key=lambda m: m.episode_id,
        )
        ids = {m.episode_id for m in publics}
        sidecars = sorted(
            (s for s in result.sidecars if s.episode_id in ids),
            key=lambda s: s.episode_id,
        )
        public_path = output / f"{split}.jsonl"
        sidecar_path = output / f"{split}.sidecar.jsonl"
        _write_jsonl(public_path, [m.to_dict() for m in publics])
        _write_jsonl(sidecar_path, [s.to_dict() for s in sidecars])
        written[split] = str(public_path)

    hashes = {
        m.episode_id: m.manifest_hash() for m in result.public_manifests
    }
    hashes_path = output / "manifest_hashes.json"
    hashes_path.write_text(
        json.dumps(hashes, sort_keys=True, indent=2) + "\n"
    )
    written["manifest_hashes.json"] = str(hashes_path)
    return written
