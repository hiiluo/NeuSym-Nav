#!/usr/bin/env python3
"""Visual, hands-free demonstration of the real V1R1 navigation pipeline.

Run with: ``uv run python scripts/pygame_demo.py``.
Type one of the supported instructions and press Start (or Enter).  The
application records state snapshots through the runner's observer hook and
then replays them at a presentation-friendly pace.  Rendering reads the
MiniGrid only to draw it; it does not provide input to the agent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Some X11 / remote-desktop sessions expose a display but no usable GLX
# context. SDL probes GLX while deciding whether to accelerate its framebuffer;
# this demo only uses 2D drawing, so disable that probe and use software.
os.environ.setdefault("SDL_FRAMEBUFFER_ACCELERATION", "0")
os.environ.setdefault("SDL_RENDER_DRIVER", "software")

import pygame

from neuro_symbolic_vln.agent_v1r1 import _make_env_and_verifier, run_v1r1_episode
from neuro_symbolic_vln.contracts import (
    EpisodeSpec,
    PrimitiveAction,
    StepResult,
    SymbolicAction,
)
from neuro_symbolic_vln.env.custom_map import (
    CustomMapEnv,
    CustomMapSpec,
    object_positions,
)
from neuro_symbolic_vln.env.verifier import GoToVerifier
from neuro_symbolic_vln.language.template_parser import (
    normalize_instruction,
    parse_instruction,
)

# Intentionally fits inside a 1920×1080 desktop, while giving a 2K display
# a much more presentation-friendly canvas than the original compact window.
WINDOW = (2288, 1287)
GRID_ORIGIN = (70, 230)
CELL = 138
BG = (16, 23, 35)
PANEL = (28, 40, 57)
TEXT = (235, 242, 250)
MUTED = (154, 174, 194)
ACCENT = (62, 202, 161)
ERROR = (245, 112, 112)
EXAMPLES = (
    "go to the green ball",
    "pick up the red key, open the red door, then go to the goal",
)


@dataclass(frozen=True)
class Snapshot:
    phase: str
    symbolic: str
    primitive: str
    succeeded: bool | None
    cells: tuple[tuple[tuple[str, str, bool, bool] | None, ...], ...]
    agent_pos: tuple[int, int]
    agent_dir: int
    carrying: str | None


def _world_snapshot(
    env: Any,
    phase: str,
    action: SymbolicAction | None,
    primitive: PrimitiveAction | None,
    result: StepResult | None,
) -> Snapshot:
    raw = env.unwrapped
    cells = tuple(
        tuple(
            None
            if (obj := raw.grid.get(x, y)) is None
            else (
                obj.type,
                getattr(obj, "color", "grey"),
                bool(getattr(obj, "is_locked", False)),
                bool(getattr(obj, "is_open", False)),
            )
            for x in range(raw.width)
        )
        for y in range(raw.height)
    )
    carrying = raw.carrying
    return Snapshot(
        phase=phase,
        symbolic="—" if action is None else action.name,
        primitive="—" if primitive is None else primitive.name,
        succeeded=None if result is None else result.action_succeeded,
        cells=cells,
        agent_pos=(int(raw.agent_pos[0]), int(raw.agent_pos[1])),
        agent_dir=int(raw.agent_dir),
        carrying=None if carrying is None else f"{carrying.color} {carrying.type}",
    )


def _family_for_instruction(instruction: str) -> tuple[str | None, str | None]:
    parsed = parse_instruction(instruction)
    if parsed.goal_program is None:
        return None, parsed.reason or "Unsupported instruction"
    family = parsed.goal_program.family
    # The two fixed probe maps are the actual experimental environments.
    canonical = {
        "goto_type_color": "go to the green ball",
        "key_door_goal": "pick up the red key, open the red door, then go to the goal",
    }[family]
    if normalize_instruction(instruction) != canonical:
        return None, f"Demo map expects: “{canonical}”"
    return family, None


def _record_episode(instruction: str) -> tuple[list[Snapshot], str]:
    family, problem = _family_for_instruction(instruction)
    if family is None:
        return [], problem or "Unsupported instruction"
    env, verifier, _ = _make_env_and_verifier(family, seed=0)
    episode = EpisodeSpec(
        episode_id="pygame-demo",
        family=family,
        instruction=instruction,
        public_action_budget=32,
        manifest_hash="pygame-demo",
    )
    snapshots: list[Snapshot] = []

    def observe(
        phase: str,
        action: SymbolicAction | None,
        primitive: PrimitiveAction | None,
        result: StepResult | None,
    ) -> None:
        snapshots.append(_world_snapshot(env, phase, action, primitive, result))

    outcome = run_v1r1_episode(
        seed=0,
        family=family,
        episode=episode,
        env=env,
        verifier=verifier,
        step_observer=observe,
    )
    status = (
        "SUCCESS" if outcome.task_success else f"STOPPED: {outcome.terminal_outcome}"
    )
    summary = (
        f"{status}  |  {outcome.step_count} primitives  |  "
        f"{outcome.replan_count} replans"
    )
    return snapshots, summary


def _initial_preview(instruction: str) -> Snapshot | None:
    """Create a display-only initial map; it is never exposed to the agent."""
    family, _ = _family_for_instruction(instruction)
    if family is None:
        return None
    env, _, _ = _make_env_and_verifier(family, seed=0)
    env.reset(seed=0)
    return _world_snapshot(env, "Initial map — awaiting Start", None, None, None)


def _record_custom_episode(
    spec: CustomMapSpec, instruction: str
) -> tuple[list[Snapshot], str]:
    """Validate a custom task then run it through the normal V1R1 runner."""
    problem = spec.validate()
    parsed = parse_instruction(instruction)
    if problem is not None:
        return [], problem
    if parsed.goal_program is None:
        return [], parsed.reason or "Unsupported instruction"
    family = parsed.goal_program.family
    if family == "goto_type_color":
        color, object_type = parsed.goal_program.ordered_subgoals[0].arguments
        matches = object_positions(spec, object_type, color)  # type: ignore[arg-type]
    else:
        key_color = parsed.goal_program.ordered_subgoals[0].arguments[0]
        door_color = parsed.goal_program.ordered_subgoals[1].arguments[0]
        if len(object_positions(spec, "key", key_color)) != 1:
            return [], "Place exactly one key matching the instruction."
        if len(object_positions(spec, "door", door_color)) != 1:
            return [], "Place exactly one locked door matching the instruction."
        matches = object_positions(spec, "goal")
    if len(matches) != 1:
        return [], "Instruction must identify exactly one target object."
    env = CustomMapEnv(spec)
    verifier = GoToVerifier(target_position=matches[0], env=env)
    episode = EpisodeSpec(
        episode_id="pygame-custom-demo",
        family=family,
        instruction=instruction,
        public_action_budget=max(64, spec.width * spec.height * 4),
        manifest_hash="pygame-custom-map",
    )
    snapshots: list[Snapshot] = []

    def observe(
        phase: str,
        action: SymbolicAction | None,
        primitive: PrimitiveAction | None,
        result: StepResult | None,
    ) -> None:
        snapshots.append(_world_snapshot(env, phase, action, primitive, result))

    result = run_v1r1_episode(
        family=family,
        episode=episode,
        env=env,
        verifier=verifier,
        step_observer=observe,
        # Frontier exploration may replan once per newly inspected region.
        # Keep a finite bound while scaling it to a user-authored map.
        max_replans=max(20, spec.width * spec.height * 2),
    )
    outcome = (
        "SUCCESS" if result.task_success else f"STOPPED: {result.terminal_outcome}"
    )
    return snapshots, f"{outcome}  |  {result.step_count} primitives"


def _text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    value: str,
    pos: tuple[int, int],
    color: tuple[int, int, int] = TEXT,
) -> None:
    surface.blit(font.render(value, True, color), pos)


def _draw_grid(surface: pygame.Surface, snap: Snapshot, font: pygame.font.Font) -> None:
    colors = {
        "red": (224, 81, 91),
        "green": (61, 188, 113),
        "yellow": (228, 191, 73),
        "grey": (149, 159, 171),
    }
    for y, row in enumerate(snap.cells):
        for x, obj in enumerate(row):
            rect = pygame.Rect(
                GRID_ORIGIN[0] + x * CELL, GRID_ORIGIN[1] + y * CELL, CELL - 3, CELL - 3
            )
            pygame.draw.rect(
                surface,
                (43, 55, 72) if obj is None else (56, 69, 85),
                rect,
                border_radius=5,
            )
            if obj is not None:
                kind, color, locked, opened = obj
                compact = CELL < 52
                radius = max(3, CELL // 4)
                if kind == "wall":
                    pygame.draw.rect(surface, (98, 111, 128), rect, border_radius=4)
                elif kind == "goal":
                    pygame.draw.circle(
                        surface,
                        (255, 209, 79),
                        rect.center,
                        radius,
                        width=max(2, radius // 3),
                    )
                    pygame.draw.line(
                        surface,
                        (255, 209, 79),
                        (rect.centerx, rect.centery - radius),
                        (rect.centerx, rect.centery + radius),
                        width=max(2, radius // 3),
                    )
                    if not compact:
                        _text(surface, font, "GOAL", (rect.x + 20, rect.y + 52), BG)
                elif kind == "door":
                    door_color = colors.get(color, colors["grey"])
                    pygame.draw.rect(
                        surface,
                        door_color if not opened else (89, 115, 107),
                        rect.inflate(-max(4, CELL // 4), -max(4, CELL // 7)),
                        border_radius=4,
                    )
                    if not compact:
                        _text(
                            surface,
                            font,
                            "OPEN" if opened else ("LOCK" if locked else "DOOR"),
                            (rect.x + 18, rect.y + 52),
                            TEXT,
                        )
                elif kind == "key":
                    pygame.draw.circle(
                        surface,
                        colors.get(color, colors["grey"]),
                        (rect.centerx - radius // 2, rect.centery - radius // 2),
                        max(3, radius // 2),
                    )
                    pygame.draw.rect(
                        surface,
                        colors.get(color, colors["grey"]),
                        (
                            rect.centerx,
                            rect.centery - radius // 4,
                            radius,
                            max(2, radius // 3),
                        ),
                    )
                    pygame.draw.rect(
                        surface,
                        colors.get(color, colors["grey"]),
                        (
                            rect.centerx + radius // 2,
                            rect.centery,
                            max(2, radius // 3),
                            radius // 2,
                        ),
                    )
                else:
                    pygame.draw.circle(
                        surface, colors.get(color, colors["grey"]), rect.center, radius
                    )
                    if not compact:
                        _text(
                            surface,
                            font,
                            kind.upper()[:4],
                            (rect.x + 20, rect.y + 52),
                            BG,
                        )
            if (x, y) == snap.agent_pos:
                direction = ((1, 0), (0, 1), (-1, 0), (0, -1))[snap.agent_dir]
                cx, cy = rect.center
                tip = (
                    cx + direction[0] * max(4, CELL // 3),
                    cy + direction[1] * max(4, CELL // 3),
                )
                side = (
                    -direction[1] * max(3, CELL // 5),
                    direction[0] * max(3, CELL // 5),
                )
                pygame.draw.polygon(
                    surface,
                    (87, 188, 255),
                    [tip, (cx + side[0], cy + side[1]), (cx - side[0], cy - side[1])],
                )


def _run_preset_demo() -> int:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW)
    pygame.display.set_caption("NeuSym-Nav | V1R1 autonomous demo")
    clock = pygame.time.Clock()
    title = pygame.font.SysFont("sans", 38, bold=True)
    body = pygame.font.SysFont("sans", 26)
    small = pygame.font.SysFont("sans", 20)
    instruction = "pick up the red key, open the red door, then go to the goal"
    preview = _initial_preview(instruction)
    active = True
    snapshots: list[Snapshot] = []
    index = 0
    last_advance = 0
    status = "Type an instruction, then press Start. Robot control is fully autonomous."
    running = True
    input_box = pygame.Rect(70, 108, 1200, 58)
    start_button = pygame.Rect(1300, 108, 170, 58)
    speed_button = pygame.Rect(1500, 108, 190, 58)
    back_button = pygame.Rect(WINDOW[0] - 190, 30, 140, 46)
    goto_example = pygame.Rect(980, 390, 670, 68)
    keydoor_example = pygame.Rect(980, 478, 670, 96)
    delay = 900

    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if back_button.collidepoint(event.pos):
                    pygame.quit()
                    return 1
                if input_box.collidepoint(event.pos):
                    active = True
                elif start_button.collidepoint(event.pos):
                    snapshots, status = _record_episode(instruction)
                    index, last_advance = 0, now
                elif speed_button.collidepoint(event.pos):
                    delay = {900: 550, 550: 250, 250: 900}[delay]
                    last_advance = now
                elif goto_example.collidepoint(event.pos):
                    instruction = EXAMPLES[0]
                    preview = _initial_preview(instruction)
                    snapshots = []
                    status = (
                        "Green-ball task selected. Review the initial map, "
                        "then press Start."
                    )
                elif keydoor_example.collidepoint(event.pos):
                    instruction = EXAMPLES[1]
                    preview = _initial_preview(instruction)
                    snapshots = []
                    status = (
                        "Key-door task selected. Review the initial map, "
                        "then press Start."
                    )
            elif event.type == pygame.KEYDOWN and active:
                if event.key == pygame.K_RETURN:
                    snapshots, status = _record_episode(instruction)
                    index, last_advance = 0, now
                elif event.key == pygame.K_BACKSPACE:
                    instruction = instruction[:-1]
                elif event.unicode and event.unicode.isprintable():
                    instruction += event.unicode
        if snapshots and index < len(snapshots) - 1 and now - last_advance >= delay:
            index += 1
            last_advance = now

        screen.fill(BG)
        pygame.draw.rect(screen, PANEL, back_button, border_radius=7)
        _text(screen, small, "← BACK", (back_button.x + 20, back_button.y + 13))
        _text(screen, title, "NeuSym-Nav · V1R1 closed-loop autonomous robot", (70, 30))
        pipeline = (
            "Instruction → parser → perception & belief → PDDL planner → "
            "controller → monitor"
        )
        _text(
            screen,
            small,
            pipeline,
            (72, 78),
            MUTED,
        )
        pygame.draw.rect(screen, (38, 52, 70), input_box, border_radius=7)
        pygame.draw.rect(
            screen, ACCENT if active else MUTED, input_box, width=2, border_radius=7
        )
        _text(screen, body, instruction, (88, 121))
        pygame.draw.rect(screen, ACCENT, start_button, border_radius=7)
        _text(screen, body, "START", (1342, 121), BG)
        pygame.draw.rect(screen, PANEL, speed_button, border_radius=7)
        _text(screen, small, f"Speed: {delay} ms", (1520, 126), TEXT)
        pygame.draw.line(screen, (60, 77, 96), (70, 195), (1690, 195), 1)

        snap = snapshots[index] if snapshots else preview
        if snap is not None:
            _draw_grid(screen, snap, small)
        if snapshots:
            pygame.draw.rect(
                screen, PANEL, pygame.Rect(945, 230, 745, 500), border_radius=10
            )
            _text(
                screen,
                title,
                f"Step {index + 1} / {len(snapshots)}",
                (980, 264),
                ACCENT,
            )
            _text(screen, body, "Current processing phase", (980, 340), MUTED)
            _text(screen, body, snap.phase, (980, 375))
            _text(screen, body, "Symbolic action", (980, 455), MUTED)
            _text(screen, body, snap.symbolic, (980, 490), ACCENT)
            _text(screen, body, "Primitive action", (980, 570), MUTED)
            primitive_result = (
                snap.primitive
                if snap.succeeded is None
                else f"{snap.primitive}  →  {'success' if snap.succeeded else 'failed'}"
            )
            _text(screen, body, primitive_result, (980, 605))
            _text(
                screen,
                small,
                f"Belief-visible carrying: {snap.carrying or 'nothing'}",
                (980, 675),
                MUTED,
            )
            _text(
                screen,
                small,
                "Blue triangle = robot heading. No keyboard movement controls.",
                (70, 940),
                MUTED,
            )
        else:
            pygame.draw.rect(
                screen, PANEL, pygame.Rect(945, 230, 745, 500), border_radius=10
            )
            _text(screen, title, "Initial map preview", (980, 264), ACCENT)
            _text(
                screen,
                body,
                "Click a task below to load its matching map:",
                (980, 326),
                MUTED,
            )
            pygame.draw.rect(screen, (42, 65, 82), goto_example, border_radius=8)
            _text(screen, body, "GO TO GREEN BALL", (1008, 408), ACCENT)
            _text(
                screen,
                small,
                "Instruction: go to the green ball",
                (1008, 434),
                TEXT,
            )
            pygame.draw.rect(screen, (42, 65, 82), keydoor_example, border_radius=8)
            _text(screen, body, "KEY → DOOR → GOAL", (1008, 498), ACCENT)
            _text(
                screen,
                small,
                "• pick up the red key, open the red door, then go to the goal",
                (1008, 532),
            )
            _text(
                screen,
                small,
                "Select an example or type a supported instruction, then press Start.",
                (980, 630),
                MUTED,
            )
        _text(
            screen,
            body,
            status,
            (70, 940),
            ACCENT
            if status.startswith("SUCCESS")
            else (ERROR if "expects" in status or "Unsupported" in status else TEXT),
        )
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    return 0


def main() -> int:
    """Choose between the reproducible probe maps and the map editor."""
    pygame.init()
    screen = pygame.display.set_mode(WINDOW)
    pygame.display.set_caption("NeuSym-Nav | choose demo mode")
    title = pygame.font.SysFont("sans", 48, bold=True)
    body = pygame.font.SysFont("sans", 27)
    small = pygame.font.SysFont("sans", 20)
    preset = pygame.Rect(170, 290, 650, 310)
    custom = pygame.Rect(940, 290, 650, 310)
    clock = pygame.time.Clock()
    chosen: str | None = None
    while chosen is None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return 0
            if event.type == pygame.MOUSEBUTTONDOWN:
                if preset.collidepoint(event.pos):
                    chosen = "preset"
                elif custom.collidepoint(event.pos):
                    chosen = "custom"
        screen.fill(BG)
        _text(screen, title, "NeuSym-Nav · choose a demonstration", (170, 120))
        _text(
            screen,
            body,
            "Both modes run the same V1R1 closed-loop agent autonomously.",
            (170, 190),
            MUTED,
        )
        pygame.draw.rect(screen, PANEL, preset, border_radius=16)
        pygame.draw.rect(screen, PANEL, custom, border_radius=16)
        _text(screen, title, "1. PRESET TASKS", (220, 345), ACCENT)
        _text(screen, body, "Choose a prepared map and", (220, 420))
        _text(screen, body, "its matching instruction.", (220, 458))
        _text(
            screen,
            small,
            "Best for a quick, reproducible presentation.",
            (220, 535),
            MUTED,
        )
        _text(screen, title, "2. CUSTOM MAP", (990, 345), ACCENT)
        _text(screen, body, "Design a map up to 35 × 35,", (990, 420))
        _text(screen, body, "then let V1R1 solve it.", (990, 458))
        _text(
            screen, small, "Place walls, objects, robot and heading.", (990, 535), MUTED
        )
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    if chosen == "preset":
        result = _run_preset_demo()
    else:
        from custom_map_editor import run_custom_editor

        result = run_custom_editor()
    return main() if result == 1 else result


if __name__ == "__main__":
    raise SystemExit(main())
