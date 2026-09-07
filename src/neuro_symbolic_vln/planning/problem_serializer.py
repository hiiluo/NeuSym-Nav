"""PDDL problem serializer from committed planning state."""

from __future__ import annotations

from collections.abc import Mapping

from neuro_symbolic_vln.contracts import CommittedPlanningState, GroundAtom
from neuro_symbolic_vln.planning.location_graph import graph_to_front_cell_atoms

VALID_PDDL_PREDICATES: frozenset[str] = frozenset(
    {
        "robot-at",
        "facing",
        "passable",
        "key-at",
        "door-at",
        "handempty",
        "holding",
        "door-locked",
        "door-open",
        "key-opens",
        "target-at",
        "task-satisfied",
    }
)

PREDICATE_ALIASES: Mapping[str, str] = {
    "at": "robot-at",
    "free": "passable",
}


def serialize_problem(state: CommittedPlanningState, goal_atom: GroundAtom) -> str:
    """Serializes a CommittedPlanningState and goal atom into a PDDL problem string.

    Only true_facts and known location_graph topology are emitted into :init.
    Unresolved required facts (unknowns) are never emitted.
    Non-domain facts (such as 'wall') are filtered out.
    """
    # 1. Normalize and filter true facts to domain-valid predicates only
    filtered_facts: list[GroundAtom] = []
    for atom in state.true_facts:
        norm_pred = PREDICATE_ALIASES.get(atom.predicate, atom.predicate)
        if norm_pred in VALID_PDDL_PREDICATES:
            filtered_facts.append(GroundAtom(norm_pred, atom.arguments))

    # Collect objects dynamically
    locations: set[str] = set(state.location_graph.nodes)
    robots: set[str] = {"robot"}
    keys: set[str] = set()
    doors: set[str] = set()
    targets: set[str] = set()

    for atom in filtered_facts:
        if atom.predicate == "robot-at" and len(atom.arguments) >= 2:
            robots.add(atom.arguments[0])
            locations.add(atom.arguments[1])
        elif atom.predicate == "key-at" and len(atom.arguments) >= 2:
            keys.add(atom.arguments[0])
            locations.add(atom.arguments[1])
        elif atom.predicate == "holding" and len(atom.arguments) >= 2:
            robots.add(atom.arguments[0])
            keys.add(atom.arguments[1])
        elif atom.predicate == "door-at" and len(atom.arguments) >= 2:
            doors.add(atom.arguments[0])
            locations.add(atom.arguments[1])
        elif atom.predicate in ("door-locked", "door-open") and atom.arguments:
            doors.add(atom.arguments[0])
        elif atom.predicate == "key-opens" and len(atom.arguments) >= 2:
            keys.add(atom.arguments[0])
            doors.add(atom.arguments[1])
        elif atom.predicate == "target-at" and len(atom.arguments) >= 2:
            targets.add(atom.arguments[0])
            locations.add(atom.arguments[1])
        elif atom.predicate == "passable" and atom.arguments:
            locations.add(atom.arguments[0])

    goal_pred = PREDICATE_ALIASES.get(goal_atom.predicate, goal_atom.predicate)
    norm_goal = GroundAtom(goal_pred, goal_atom.arguments)

    if norm_goal.predicate == "target-at" and len(norm_goal.arguments) >= 2:
        targets.add(norm_goal.arguments[0])
        locations.add(norm_goal.arguments[1])
    elif norm_goal.predicate == "robot-at" and len(norm_goal.arguments) >= 2:
        robots.add(norm_goal.arguments[0])
        locations.add(norm_goal.arguments[1])
    elif norm_goal.predicate == "holding" and len(norm_goal.arguments) >= 2:
        robots.add(norm_goal.arguments[0])
        keys.add(norm_goal.arguments[1])
    elif norm_goal.predicate in ("door-open", "door-locked") and norm_goal.arguments:
        doors.add(norm_goal.arguments[0])
    elif norm_goal.predicate == "key-at" and len(norm_goal.arguments) >= 2:
        keys.add(norm_goal.arguments[0])
        locations.add(norm_goal.arguments[1])
    elif norm_goal.predicate == "passable" and norm_goal.arguments:
        locations.add(norm_goal.arguments[0])

    objects_lines: list[str] = [
        "north east south west - heading",
        f"{' '.join(sorted(robots))} - robot",
    ]
    if locations:
        objects_lines.append(f"{' '.join(sorted(locations))} - location")
    if keys:
        objects_lines.append(f"{' '.join(sorted(keys))} - key")
    if doors:
        objects_lines.append(f"{' '.join(sorted(doors))} - door")
    if targets:
        objects_lines.append(f"{' '.join(sorted(targets))} - target")

    objects_block = "\n            ".join(objects_lines)

    # 2. INIT DECLARATION (Only domain true_facts, edges, and static rotations)
    init_facts: list[str] = []

    for atom in sorted(filtered_facts, key=lambda a: (a.predicate, a.arguments)):
        if atom.arguments:
            args_str = " ".join(atom.arguments)
            init_facts.append(f"({atom.predicate} {args_str})")
        else:
            init_facts.append(f"({atom.predicate})")

    # Topological connectivity from LocationGraph (sorted for determinism)
    for atom in sorted(
        graph_to_front_cell_atoms(state.location_graph),
        key=lambda a: (a.predicate, a.arguments),
    ):
        args_str = " ".join(atom.arguments)
        init_facts.append(f"({atom.predicate} {args_str})")

    # Static rotation relations
    static_rotation = [
        "(turn-left-of north west)",
        "(turn-left-of west south)",
        "(turn-left-of south east)",
        "(turn-left-of east north)",
        "(turn-right-of north east)",
        "(turn-right-of east south)",
        "(turn-right-of south west)",
        "(turn-right-of west north)",
    ]
    init_facts.extend(static_rotation)

    init_block = "\n            ".join(init_facts)

    # 3. GOAL DECLARATION
    if norm_goal.arguments:
        goal_args = " ".join(norm_goal.arguments)
        goal_predicate_str = f"({norm_goal.predicate} {goal_args})"
    else:
        goal_predicate_str = f"({norm_goal.predicate})"

    # 4. CONCATENATE INTO PDDL PROBLEM
    pddl_sequence = f"""(define (problem current-state)
    (:domain vln-minigrid)
    (:objects
        {objects_block}
    )
    (:init
        {init_block}
    )
    (:goal
        {goal_predicate_str}
    )
)
"""
    return pddl_sequence
